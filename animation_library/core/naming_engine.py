"""
Naming Engine - Template-based naming system for studio pipeline integration

Provides structured naming for animations with:
- Template-based name generation
- Field validation and normalization
- Context extraction from Blender scene/path
- Immutable version management
"""

import re
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path


class ContextMode(Enum):
    """Context extraction mode for naming fields."""
    SCENE_NAME = "scene_name"
    FOLDER_PATH = "folder_path"
    MANUAL = "manual"


@dataclass
class FieldDefinition:
    """Definition of a naming field."""
    name: str
    label: str
    required: bool = True
    default: str = ""
    max_length: int = 50
    uppercase: bool = False
    lowercase: bool = False
    numeric: bool = False


@dataclass
class FieldSpec:
    """Parsed field specification from template."""
    name: str
    format_spec: Optional[str] = None
    is_version: bool = False


class NamingValidationError(Exception):
    """Raised when naming validation fails."""
    pass


class ImmutableFieldError(Exception):
    """Raised when attempting to modify an immutable field."""
    pass


class FieldValidator:
    """Validates field values for pipeline safety."""

    # Safe characters for filenames and pipeline tools
    VALID_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')

    # Default field rules
    DEFAULT_RULES = {
        'show': {'max_length': 20, 'uppercase': True},
        'project': {'max_length': 20, 'uppercase': True},
        'seq': {'max_length': 10},
        'sequence': {'max_length': 10},
        'episode': {'max_length': 10},
        'shot': {'max_length': 10},
        'asset': {'max_length': 50, 'lowercase': True},
        'task': {'max_length': 20, 'lowercase': True},
        'variant': {'max_length': 30, 'lowercase': True},
    }

    @classmethod
    def validate_field(cls, name: str, value: str, rules: Dict = None) -> Tuple[bool, str]:
        """
        Validate a single field value.

        Args:
            name: Field name
            value: Field value to validate
            rules: Optional custom rules dict

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return False, f"{name} is required"

        if not cls.VALID_PATTERN.match(value):
            return False, f"{name} contains invalid characters (use a-z, A-Z, 0-9, _)"

        field_rules = rules or cls.DEFAULT_RULES.get(name, {})

        max_length = field_rules.get('max_length', 50)
        if len(value) > max_length:
            return False, f"{name} exceeds max length ({max_length})"

        if field_rules.get('numeric') and not value.isdigit():
            return False, f"{name} must be numeric"

        return True, ""

    @classmethod
    def normalize_field(cls, name: str, value: str, rules: Dict = None) -> str:
        """
        Normalize field value according to rules.

        Args:
            name: Field name
            value: Field value to normalize
            rules: Optional custom rules dict

        Returns:
            Normalized value
        """
        if not value:
            return value

        field_rules = rules or cls.DEFAULT_RULES.get(name, {})

        # Strip whitespace
        value = value.strip()

        # Replace spaces with underscores
        value = value.replace(' ', '_')

        # Apply case rules
        if field_rules.get('uppercase'):
            return value.upper()
        if field_rules.get('lowercase'):
            return value.lower()

        return value


class NamingTemplate:
    """
    Parses and renders naming templates.

    Template format: {field} or {field:format}
    Examples:
        {show}_{shot}_v{version:03}  -> MYSHOW_0100_v001
        {asset}_{task}_v{version:04} -> hero_walk_anim_v0001
    """

    FIELD_PATTERN = re.compile(r'\{(\w+)(?::([^}]+))?\}')

    def __init__(self, template: str):
        """
        Initialize template parser.

        Args:
            template: Template string with {field} placeholders
        """
        self.template = template
        self.fields = self._extract_fields()

    def _extract_fields(self) -> List[FieldSpec]:
        """Extract field names and format specs from template."""
        fields = []
        for match in self.FIELD_PATTERN.finditer(self.template):
            fields.append(FieldSpec(
                name=match.group(1),
                format_spec=match.group(2),
                is_version=match.group(1) == "version"
            ))
        return fields

    def get_required_fields(self) -> List[str]:
        """Return field names (excluding version)."""
        return [f.name for f in self.fields if not f.is_version]

    def get_all_field_names(self) -> List[str]:
        """Return all field names including version."""
        return [f.name for f in self.fields]

    def render(self, field_data: Dict[str, str], version: int) -> str:
        """
        Render template with field values.

        Args:
            field_data: Dict of field values (no version)
            version: Version number (managed separately)

        Returns:
            Rendered name string
        """
        # Merge field_data with version
        all_data = {**field_data, "version": version}

        result = self.template
        for field_spec in self.fields:
            placeholder = f"{{{field_spec.name}}}"
            if field_spec.format_spec:
                placeholder = f"{{{field_spec.name}:{field_spec.format_spec}}}"

            value = all_data.get(field_spec.name, "")
            if field_spec.format_spec and isinstance(value, (int, float)):
                # Apply format spec (e.g., :03 for zero-padding)
                formatted = format(value, field_spec.format_spec)
            elif field_spec.format_spec and field_spec.name == "version":
                # Version is always int
                formatted = format(int(value), field_spec.format_spec)
            else:
                formatted = str(value)

            result = result.replace(placeholder, formatted)

        return result

    def validate(self, field_data: Dict[str, str]) -> List[str]:
        """
        Return list of missing required fields.

        Args:
            field_data: Dict of field values

        Returns:
            List of missing field names
        """
        required = self.get_required_fields()
        return [f for f in required if not field_data.get(f)]

    def parse_name(self, name: str) -> Optional[Dict[str, str]]:
        """
        Attempt to parse a name back into field values.

        This is a best-effort reverse parsing - may not work for all templates.

        Args:
            name: Name string to parse

        Returns:
            Dict of field values if parsing succeeded, None otherwise
        """
        # Build regex pattern from template
        pattern = self.template
        for field_spec in self.fields:
            placeholder = f"{{{field_spec.name}}}"
            if field_spec.format_spec:
                placeholder = f"{{{field_spec.name}:{field_spec.format_spec}}}"

            if field_spec.is_version:
                # Version is digits
                pattern = pattern.replace(placeholder, r'(?P<version>\d+)')
            else:
                # Other fields are word characters
                pattern = pattern.replace(placeholder, f'(?P<{field_spec.name}>\\w+)')

        try:
            match = re.match(f'^{pattern}$', name)
            if match:
                return match.groupdict()
        except re.error:
            pass

        return None


class StudioSettings:
    """
    Studio naming configuration.

    Stores template, context mode, and field definitions.
    """

    DEFAULT_TEMPLATE = "{asset}_v{version:03}"
    DEFAULT_FIELDS = [
        FieldDefinition("show", "Show", required=False),
        FieldDefinition("seq", "Sequence", required=False),
        FieldDefinition("shot", "Shot", required=False),
        FieldDefinition("asset", "Asset Name", required=True),
        FieldDefinition("task", "Task", required=False, default="anim"),
    ]

    def __init__(self, settings_dict: Dict[str, Any] = None):
        """
        Initialize studio settings.

        Args:
            settings_dict: Optional settings dictionary to load from
        """
        if settings_dict:
            self._load_from_dict(settings_dict)
        else:
            self._set_defaults()

    def _set_defaults(self):
        """Set default values."""
        self.studio_mode_enabled = False
        self.naming_template = self.DEFAULT_TEMPLATE
        self.context_mode = ContextMode.MANUAL
        self.context_patterns = {
            "scene_name": r"^(?P<show>[A-Z]+)_(?P<seq>\d+)_(?P<shot>\d+)_(?P<asset>\w+)",
            "folder_path": r"/projects/(?P<show>[^/]+)/(?P<seq>[^/]+)/(?P<shot>[^/]+)"
        }
        self.field_definitions = self.DEFAULT_FIELDS

    def _load_from_dict(self, data: Dict[str, Any]):
        """Load settings from dictionary."""
        self.studio_mode_enabled = data.get('studio_mode_enabled', False)
        self.naming_template = data.get('naming_template', self.DEFAULT_TEMPLATE)
        self.context_mode = ContextMode(data.get('context_mode', 'manual'))
        self.context_patterns = data.get('context_patterns', {
            "scene_name": "",
            "folder_path": ""
        })

        # Load field definitions
        field_defs = data.get('field_definitions', [])
        if field_defs:
            self.field_definitions = [
                FieldDefinition(
                    name=f.get('name', ''),
                    label=f.get('label', f.get('name', '')),
                    required=f.get('required', True),
                    default=f.get('default', ''),
                    max_length=f.get('max_length', 50),
                    uppercase=f.get('uppercase', False),
                    lowercase=f.get('lowercase', False),
                    numeric=f.get('numeric', False)
                )
                for f in field_defs
            ]
        else:
            self.field_definitions = self.DEFAULT_FIELDS

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for storage."""
        return {
            'studio_mode_enabled': self.studio_mode_enabled,
            'naming_template': self.naming_template,
            'context_mode': self.context_mode.value,
            'context_patterns': self.context_patterns,
            'field_definitions': [
                {
                    'name': f.name,
                    'label': f.label,
                    'required': f.required,
                    'default': f.default,
                    'max_length': f.max_length,
                    'uppercase': f.uppercase,
                    'lowercase': f.lowercase,
                    'numeric': f.numeric
                }
                for f in self.field_definitions
            ]
        }

    def get_template(self) -> NamingTemplate:
        """Get NamingTemplate instance."""
        return NamingTemplate(self.naming_template)

    def get_field_definition(self, name: str) -> Optional[FieldDefinition]:
        """Get field definition by name."""
        for f in self.field_definitions:
            if f.name == name:
                return f
        return None


class NamingEngine:
    """
    Orchestrates name generation.

    Combines template, context extraction, and validation.
    """

    def __init__(self, settings: StudioSettings):
        """
        Initialize naming engine.

        Args:
            settings: Studio settings instance
        """
        self.settings = settings
        self.template = settings.get_template()

    def generate_name(
        self,
        field_data: Dict[str, str],
        version: int = 1
    ) -> str:
        """
        Generate animation name from fields.

        Args:
            field_data: Dict of field values
            version: Version number

        Returns:
            Generated name string

        Raises:
            NamingValidationError: If required fields are missing
        """
        # Normalize fields
        normalized = {}
        for name, value in field_data.items():
            field_def = self.settings.get_field_definition(name)
            rules = {}
            if field_def:
                rules = {
                    'max_length': field_def.max_length,
                    'uppercase': field_def.uppercase,
                    'lowercase': field_def.lowercase,
                    'numeric': field_def.numeric
                }
            normalized[name] = FieldValidator.normalize_field(name, value, rules)

        # Validate required fields
        missing = self.template.validate(normalized)
        if missing:
            raise NamingValidationError(f"Missing required fields: {', '.join(missing)}")

        # Validate field values
        for name, value in normalized.items():
            if value:  # Only validate non-empty fields
                field_def = self.settings.get_field_definition(name)
                rules = {}
                if field_def:
                    rules = {
                        'max_length': field_def.max_length,
                        'uppercase': field_def.uppercase,
                        'lowercase': field_def.lowercase,
                        'numeric': field_def.numeric
                    }
                is_valid, error = FieldValidator.validate_field(name, value, rules)
                if not is_valid:
                    raise NamingValidationError(error)

        return self.template.render(normalized, version)

    def prepare_capture_data(
        self,
        field_data: Dict[str, str],
        version: int = 1,
        version_group_id: str = None
    ) -> Dict[str, Any]:
        """
        Prepare animation data for database storage.

        Args:
            field_data: Dict of field values
            version: Version number
            version_group_id: Optional version group for new versions

        Returns:
            Dict with name, naming_fields, naming_template, version
        """
        name = self.generate_name(field_data, version)

        return {
            'name': name,
            'naming_fields': json.dumps(field_data),
            'naming_template': self.settings.naming_template,
            'version': version
        }


class FieldRenamer:
    """
    Handles field-based renaming.

    Version field is NEVER editable - only the other fields can be changed.
    """

    def __init__(self, settings: StudioSettings):
        """
        Initialize field renamer.

        Args:
            settings: Studio settings instance
        """
        self.settings = settings
        self.template = settings.get_template()
        self.engine = NamingEngine(settings)

    def get_editable_fields(self, naming_fields_json: str) -> Dict[str, str]:
        """
        Get current field values for editing.

        Args:
            naming_fields_json: JSON string of naming fields

        Returns:
            Dict of field values (version excluded)
        """
        if not naming_fields_json:
            return {}

        try:
            return json.loads(naming_fields_json)
        except json.JSONDecodeError:
            return {}

    def generate_new_name(
        self,
        new_field_data: Dict[str, str],
        version: int
    ) -> str:
        """
        Generate new name from updated field values.

        Args:
            new_field_data: Updated field values
            version: Version number (immutable)

        Returns:
            New display name

        Raises:
            NamingValidationError: If validation fails
        """
        return self.engine.generate_name(new_field_data, version)

    def prepare_rename_updates(
        self,
        new_field_data: Dict[str, str],
        version: int
    ) -> Dict[str, Any]:
        """
        Prepare database updates for rename operation.

        Args:
            new_field_data: Updated field values
            version: Version number (immutable)

        Returns:
            Dict with name and naming_fields updates
        """
        new_name = self.generate_new_name(new_field_data, version)

        return {
            'name': new_name,
            'naming_fields': json.dumps(new_field_data)
        }


# ==================== Settings I/O ====================

def load_studio_settings() -> StudioSettings:
    """
    Load studio settings from config file.

    Returns:
        StudioSettings instance
    """
    from ..config import Config
    import json

    settings_file = Config.get_settings_file()
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                all_settings = json.load(f)
                studio_data = all_settings.get('studio_naming', {})
                return StudioSettings(studio_data)
        except Exception:
            pass

    return StudioSettings()


def save_studio_settings(settings: StudioSettings) -> bool:
    """
    Save studio settings to config file.

    Args:
        settings: StudioSettings instance to save

    Returns:
        True if saved successfully
    """
    from ..config import Config
    import json

    try:
        settings_file = Config.get_settings_file()
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing settings
        all_settings = {}
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    all_settings = json.load(f)
            except Exception:
                pass

        # Update studio naming section
        all_settings['studio_naming'] = settings.to_dict()

        # Save back
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(all_settings, f, indent=2)

        return True
    except Exception:
        return False


__all__ = [
    'ContextMode',
    'FieldDefinition',
    'FieldSpec',
    'FieldValidator',
    'NamingTemplate',
    'NamingValidationError',
    'ImmutableFieldError',
    'StudioSettings',
    'NamingEngine',
    'FieldRenamer',
    'load_studio_settings',
    'save_studio_settings',
]
