"""
Naming Engine for Blender Plugin

Handles context extraction and name generation during capture.
Mirrors the desktop app's naming engine but optimized for Blender context.
"""

import re
import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import bpy


class ContextMode(Enum):
    """Context extraction mode for naming fields."""
    SCENE_NAME = "scene_name"
    FOLDER_PATH = "folder_path"
    MANUAL = "manual"


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
        self.template = template
        self.fields = self._extract_fields()

    def _extract_fields(self) -> List[Dict[str, Any]]:
        """Extract field names and format specs from template."""
        fields = []
        for match in self.FIELD_PATTERN.finditer(self.template):
            fields.append({
                'name': match.group(1),
                'format_spec': match.group(2),
                'is_version': match.group(1) == "version"
            })
        return fields

    def get_required_fields(self) -> List[str]:
        """Return field names (excluding version)."""
        return [f['name'] for f in self.fields if not f['is_version']]

    def render(self, field_data: Dict[str, str], version: int) -> str:
        """Render template with field values."""
        all_data = {**field_data, "version": version}

        result = self.template
        for field in self.fields:
            name = field['name']
            format_spec = field['format_spec']

            placeholder = f"{{{name}}}"
            if format_spec:
                placeholder = f"{{{name}:{format_spec}}}"

            value = all_data.get(name, "")
            if format_spec and name == "version":
                formatted = format(int(value), format_spec)
            elif format_spec and isinstance(value, (int, float)):
                formatted = format(value, format_spec)
            else:
                formatted = str(value)

            result = result.replace(placeholder, formatted)

        return result

    def validate(self, field_data: Dict[str, str]) -> List[str]:
        """Return list of missing required fields."""
        required = self.get_required_fields()
        return [f for f in required if not field_data.get(f)]


class ContextProvider:
    """
    Extracts naming context from Blender environment.
    Only one mode active at a time.
    """

    def __init__(self, mode: ContextMode, pattern: str = None):
        self.mode = mode
        self.pattern = None
        if pattern:
            try:
                self.pattern = re.compile(pattern)
            except re.error:
                pass

    def extract(self) -> Dict[str, str]:
        """Extract field values from current context."""
        if self.mode == ContextMode.SCENE_NAME:
            return self._from_scene_name()
        elif self.mode == ContextMode.FOLDER_PATH:
            return self._from_folder_path()
        else:
            return {}  # Manual mode returns empty

    def _from_scene_name(self) -> Dict[str, str]:
        """Parse Blender scene name using regex pattern."""
        scene_name = bpy.context.scene.name

        if not self.pattern:
            return {}

        match = self.pattern.match(scene_name)
        if match:
            return {k: v for k, v in match.groupdict().items() if v}
        return {}

    def _from_folder_path(self) -> Dict[str, str]:
        """Parse current .blend file path using regex pattern."""
        filepath = bpy.data.filepath

        if not filepath or not self.pattern:
            return {}

        # Normalize path separators
        filepath = filepath.replace("\\", "/")

        match = self.pattern.search(filepath)
        if match:
            return {k: v for k, v in match.groupdict().items() if v}
        return {}


class FieldValidator:
    """Validates field values for pipeline safety."""

    VALID_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')

    @classmethod
    def validate_field(cls, name: str, value: str) -> Tuple[bool, str]:
        """Validate a single field value."""
        if not value:
            return False, f"{name} is required"

        if not cls.VALID_PATTERN.match(value):
            return False, f"{name} contains invalid characters (use a-z, A-Z, 0-9, _)"

        return True, ""

    @classmethod
    def validate_all_fields(cls, field_data: Dict[str, str], required_fields: List[str]) -> Dict[str, Tuple[bool, str]]:
        """
        Validate all field values.

        Args:
            field_data: Dict of field name -> value
            required_fields: List of required field names

        Returns:
            Dict of field name -> (is_valid, error_message)
        """
        results = {}
        for field_name in required_fields:
            value = field_data.get(field_name, '')
            results[field_name] = cls.validate_field(field_name, value)
        return results

    @classmethod
    def normalize_field(cls, name: str, value: str, uppercase: bool = False, lowercase: bool = False) -> str:
        """Normalize field value."""
        if not value:
            return value

        value = value.strip().replace(' ', '_')

        if uppercase:
            return value.upper()
        if lowercase:
            return value.lower()

        return value


class BlenderNamingEngine:
    """
    Orchestrates name generation in Blender.

    Loads settings from Blender addon preferences and generates names
    based on template and context.
    """

    def __init__(self, library_path: str = None):
        """
        Initialize naming engine.

        Args:
            library_path: Path to library folder (not used, kept for compatibility)
        """
        self._library_path = library_path
        self._settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Load studio naming settings from Blender addon preferences."""
        try:
            addon_name = __name__.split('.')[0]
            prefs = bpy.context.preferences.addons[addon_name].preferences

            # Map context mode enum to lowercase string
            context_mode_map = {
                'MANUAL': 'manual',
                'SCENE_NAME': 'scene_name',
                'FOLDER_PATH': 'folder_path'
            }

            # Get base template and version padding
            base_template = prefs.naming_template
            version_padding = getattr(prefs, 'version_padding', 3)

            # Auto-append version suffix (user cannot edit this part)
            full_template = f"{base_template}_v{{version:0{version_padding}}}"

            return {
                'studio_mode_enabled': prefs.studio_mode_enabled,
                'naming_template': full_template,
                'base_template': base_template,
                'version_padding': version_padding,
                'context_mode': context_mode_map.get(prefs.context_mode, 'manual'),
                'context_patterns': {
                    'scene_name': prefs.context_pattern_scene,
                    'folder_path': prefs.context_pattern_folder
                },
                'field_definitions': []
            }
        except Exception:
            return self._get_default_settings()

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings."""
        return {
            'studio_mode_enabled': False,
            'naming_template': "{asset}_v{version:03}",
            'base_template': "{asset}",
            'version_padding': 3,
            'context_mode': 'manual',
            'context_patterns': {
                'scene_name': '',
                'folder_path': ''
            },
            'field_definitions': []
        }

    @property
    def is_studio_mode_enabled(self) -> bool:
        """Check if studio mode is enabled."""
        return self._settings.get('studio_mode_enabled', False)

    @property
    def template(self) -> NamingTemplate:
        """Get current naming template."""
        template_str = self._settings.get('naming_template', "{asset}_v{version:03}")
        return NamingTemplate(template_str)

    @property
    def context_mode(self) -> ContextMode:
        """Get current context mode."""
        mode_str = self._settings.get('context_mode', 'manual')
        try:
            return ContextMode(mode_str)
        except ValueError:
            return ContextMode.MANUAL

    def get_context_provider(self) -> ContextProvider:
        """Get context provider for current mode."""
        mode = self.context_mode
        patterns = self._settings.get('context_patterns', {})

        if mode == ContextMode.SCENE_NAME:
            pattern = patterns.get('scene_name', '')
        elif mode == ContextMode.FOLDER_PATH:
            pattern = patterns.get('folder_path', '')
        else:
            pattern = ''

        return ContextProvider(mode, pattern)

    def extract_context(self) -> Dict[str, str]:
        """Extract context based on current mode."""
        provider = self.get_context_provider()
        return provider.extract()

    def get_required_fields(self) -> List[str]:
        """Get list of required field names from template."""
        return self.template.get_required_fields()

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
            ValueError: If required fields are missing
        """
        # Validate required fields
        missing = self.template.validate(field_data)
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        return self.template.render(field_data, version)

    def prepare_capture_data(
        self,
        field_data: Dict[str, str],
        version: int = 1,
    ) -> Dict[str, Any]:
        """
        Prepare animation data for saving.

        Args:
            field_data: Dict of field values
            version: Version number

        Returns:
            Dict with name, naming_fields, naming_template
        """
        name = self.generate_name(field_data, version)

        return {
            'name': name,
            'naming_fields': json.dumps(field_data),
            'naming_template': self._settings.get('naming_template', ''),
        }


# Singleton instance
_naming_engine: Optional[BlenderNamingEngine] = None


def get_naming_engine(library_path: str = None) -> BlenderNamingEngine:
    """Get or create the naming engine singleton."""
    global _naming_engine

    if _naming_engine is None or library_path:
        _naming_engine = BlenderNamingEngine(library_path)

    return _naming_engine


def reload_naming_settings(library_path: str = None):
    """Reload naming settings from config file."""
    global _naming_engine
    _naming_engine = BlenderNamingEngine(library_path)


__all__ = [
    'ContextMode',
    'NamingTemplate',
    'ContextProvider',
    'FieldValidator',
    'BlenderNamingEngine',
    'get_naming_engine',
    'reload_naming_settings',
]
