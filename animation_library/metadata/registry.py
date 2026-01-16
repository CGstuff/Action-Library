"""
Metadata Field Registry - Single source of truth for all animation metadata fields.

This module defines all metadata fields used in the Animation Library:
- Field types and validation rules
- Categories for organization
- UI hints for auto-generated forms
- Required/optional status

Benefits:
- Central documentation of all fields
- Validation rules in one place
- UI generation from registry
- Type safety and consistency

Usage:
    from animation_library.metadata import ANIMATION_FIELDS, get_field, validate_field

    # Get field definition
    field = get_field('frame_count')
    print(field.type, field.required)

    # Validate a value
    is_valid, error = validate_field('status', 'wip')

Note: This registry documents the column-based schema. No EAV migration needed -
the animation library keeps metadata in columns for performance and simplicity.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Callable, Dict, Tuple
from enum import Enum


class FieldType(Enum):
    """Supported field types."""
    STRING = "string"
    INTEGER = "integer"
    REAL = "real"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    JSON = "json"


class FieldCategory(Enum):
    """Field categories for organization."""
    CORE = "core"              # UUID, name, description
    RIG = "rig"                # Rig type, armature, bones
    TIMING = "timing"          # Frames, duration, FPS
    FILES = "files"            # File paths
    ORGANIZATION = "organization"  # Tags, folders
    USER = "user"              # Favorites, recent, order
    VERSIONING = "versioning"  # Version tracking
    LIFECYCLE = "lifecycle"    # Status workflow
    POSE = "pose"              # Pose-specific flags
    NAMING = "naming"          # Studio naming fields
    DISPLAY = "display"        # Thumbnail/gradient
    TIMESTAMPS = "timestamps"  # Created/modified


@dataclass
class FieldDef:
    """
    Definition for a metadata field.

    Attributes:
        name: Database column name
        display_name: Human-readable label for UI
        field_type: Data type (string, integer, real, boolean, timestamp, json)
        category: Category for grouping
        required: Whether field is required
        default: Default value
        choices: Valid choices for enum fields
        validator: Custom validation function
        description: Documentation string
        ui_widget: Suggested UI widget type
        show_in_card: Show in card/thumbnail view
        show_in_details: Show in details panel
        editable: Whether user can edit
        sortable: Whether field can be used for sorting
    """
    name: str
    display_name: str
    field_type: FieldType
    category: FieldCategory
    required: bool = False
    default: Any = None
    choices: Optional[List[Any]] = None
    validator: Optional[Callable[[Any], bool]] = None
    description: str = ""
    ui_widget: str = "text"
    show_in_card: bool = False
    show_in_details: bool = True
    editable: bool = True
    sortable: bool = False


# ============================================================================
# FIELD DEFINITIONS - All 35+ Animation Metadata Fields
# ============================================================================

ANIMATION_FIELDS: Dict[str, FieldDef] = {
    # -------------------------------------------------------------------------
    # CORE FIELDS
    # -------------------------------------------------------------------------
    "uuid": FieldDef(
        name="uuid",
        display_name="UUID",
        field_type=FieldType.STRING,
        category=FieldCategory.CORE,
        required=True,
        editable=False,
        description="Unique identifier for this animation"
    ),
    "name": FieldDef(
        name="name",
        display_name="Name",
        field_type=FieldType.STRING,
        category=FieldCategory.CORE,
        required=True,
        ui_widget="text",
        show_in_card=True,
        sortable=True,
        description="Animation display name"
    ),
    "description": FieldDef(
        name="description",
        display_name="Description",
        field_type=FieldType.STRING,
        category=FieldCategory.CORE,
        required=False,
        ui_widget="textarea",
        description="Optional description"
    ),
    "folder_id": FieldDef(
        name="folder_id",
        display_name="Folder",
        field_type=FieldType.INTEGER,
        category=FieldCategory.CORE,
        required=True,
        ui_widget="folder_picker",
        sortable=True,
        description="Parent folder ID"
    ),

    # -------------------------------------------------------------------------
    # RIG INFORMATION
    # -------------------------------------------------------------------------
    "rig_type": FieldDef(
        name="rig_type",
        display_name="Rig Type",
        field_type=FieldType.STRING,
        category=FieldCategory.RIG,
        required=True,
        choices=["rigify", "mixamo", "auto_rig_pro", "epic_skeleton", "unknown"],
        ui_widget="select",
        show_in_card=True,
        sortable=True,
        description="Type of rig (Rigify, Mixamo, etc.)"
    ),
    "armature_name": FieldDef(
        name="armature_name",
        display_name="Armature",
        field_type=FieldType.STRING,
        category=FieldCategory.RIG,
        required=False,
        ui_widget="text",
        description="Name of the armature object"
    ),
    "bone_count": FieldDef(
        name="bone_count",
        display_name="Bones",
        field_type=FieldType.INTEGER,
        category=FieldCategory.RIG,
        required=False,
        ui_widget="number",
        show_in_details=True,
        sortable=True,
        description="Number of bones in the armature"
    ),

    # -------------------------------------------------------------------------
    # ANIMATION TIMING
    # -------------------------------------------------------------------------
    "frame_start": FieldDef(
        name="frame_start",
        display_name="Start Frame",
        field_type=FieldType.INTEGER,
        category=FieldCategory.TIMING,
        required=False,
        ui_widget="number",
        description="First frame of animation"
    ),
    "frame_end": FieldDef(
        name="frame_end",
        display_name="End Frame",
        field_type=FieldType.INTEGER,
        category=FieldCategory.TIMING,
        required=False,
        ui_widget="number",
        description="Last frame of animation"
    ),
    "frame_count": FieldDef(
        name="frame_count",
        display_name="Frames",
        field_type=FieldType.INTEGER,
        category=FieldCategory.TIMING,
        required=False,
        ui_widget="number",
        show_in_card=True,
        sortable=True,
        description="Total number of frames"
    ),
    "duration_seconds": FieldDef(
        name="duration_seconds",
        display_name="Duration (s)",
        field_type=FieldType.REAL,
        category=FieldCategory.TIMING,
        required=False,
        ui_widget="number",
        show_in_card=True,
        sortable=True,
        description="Duration in seconds"
    ),
    "fps": FieldDef(
        name="fps",
        display_name="FPS",
        field_type=FieldType.INTEGER,
        category=FieldCategory.TIMING,
        required=False,
        default=24,
        ui_widget="number",
        description="Frames per second"
    ),

    # -------------------------------------------------------------------------
    # FILE INFORMATION
    # -------------------------------------------------------------------------
    "blend_file_path": FieldDef(
        name="blend_file_path",
        display_name="Blend File",
        field_type=FieldType.STRING,
        category=FieldCategory.FILES,
        required=False,
        editable=False,
        ui_widget="filepath",
        description="Path to the .blend file"
    ),
    "json_file_path": FieldDef(
        name="json_file_path",
        display_name="Metadata File",
        field_type=FieldType.STRING,
        category=FieldCategory.FILES,
        required=False,
        editable=False,
        ui_widget="filepath",
        description="Path to the .json metadata file"
    ),
    "preview_path": FieldDef(
        name="preview_path",
        display_name="Preview",
        field_type=FieldType.STRING,
        category=FieldCategory.FILES,
        required=False,
        editable=False,
        ui_widget="filepath",
        description="Path to preview video (.webm)"
    ),
    "thumbnail_path": FieldDef(
        name="thumbnail_path",
        display_name="Thumbnail",
        field_type=FieldType.STRING,
        category=FieldCategory.FILES,
        required=False,
        editable=False,
        ui_widget="filepath",
        description="Path to thumbnail image (.png)"
    ),
    "file_size_mb": FieldDef(
        name="file_size_mb",
        display_name="File Size (MB)",
        field_type=FieldType.REAL,
        category=FieldCategory.FILES,
        required=False,
        editable=False,
        ui_widget="number",
        sortable=True,
        description="Total file size in megabytes"
    ),

    # -------------------------------------------------------------------------
    # ORGANIZATION
    # -------------------------------------------------------------------------
    "tags": FieldDef(
        name="tags",
        display_name="Tags",
        field_type=FieldType.STRING,
        category=FieldCategory.ORGANIZATION,
        required=False,
        ui_widget="tags",
        description="Comma-separated or JSON array of tags"
    ),
    "author": FieldDef(
        name="author",
        display_name="Author",
        field_type=FieldType.STRING,
        category=FieldCategory.ORGANIZATION,
        required=False,
        ui_widget="text",
        sortable=True,
        description="Animation author"
    ),

    # -------------------------------------------------------------------------
    # USER FEATURES
    # -------------------------------------------------------------------------
    "is_favorite": FieldDef(
        name="is_favorite",
        display_name="Favorite",
        field_type=FieldType.BOOLEAN,
        category=FieldCategory.USER,
        required=False,
        default=False,
        ui_widget="checkbox",
        show_in_card=True,
        sortable=True,
        description="Marked as favorite"
    ),
    "last_viewed_date": FieldDef(
        name="last_viewed_date",
        display_name="Last Viewed",
        field_type=FieldType.TIMESTAMP,
        category=FieldCategory.USER,
        required=False,
        editable=False,
        sortable=True,
        description="Last time animation was viewed"
    ),
    "custom_order": FieldDef(
        name="custom_order",
        display_name="Custom Order",
        field_type=FieldType.INTEGER,
        category=FieldCategory.USER,
        required=False,
        editable=False,
        sortable=True,
        description="Custom sort order within folder"
    ),
    "is_locked": FieldDef(
        name="is_locked",
        display_name="Locked",
        field_type=FieldType.BOOLEAN,
        category=FieldCategory.USER,
        required=False,
        default=False,
        ui_widget="checkbox",
        description="Prevent accidental deletion"
    ),

    # -------------------------------------------------------------------------
    # VERSIONING
    # -------------------------------------------------------------------------
    "version": FieldDef(
        name="version",
        display_name="Version",
        field_type=FieldType.INTEGER,
        category=FieldCategory.VERSIONING,
        required=False,
        default=1,
        editable=False,
        sortable=True,
        description="Version number (1, 2, 3, ...)"
    ),
    "version_label": FieldDef(
        name="version_label",
        display_name="Version Label",
        field_type=FieldType.STRING,
        category=FieldCategory.VERSIONING,
        required=False,
        default="v001",
        ui_widget="text",
        show_in_card=True,
        description="Human-readable version label"
    ),
    "version_group_id": FieldDef(
        name="version_group_id",
        display_name="Version Group",
        field_type=FieldType.STRING,
        category=FieldCategory.VERSIONING,
        required=False,
        editable=False,
        description="Groups all versions of same animation"
    ),
    "is_latest": FieldDef(
        name="is_latest",
        display_name="Is Latest",
        field_type=FieldType.BOOLEAN,
        category=FieldCategory.VERSIONING,
        required=False,
        default=True,
        editable=False,
        sortable=True,
        description="Whether this is the latest version"
    ),

    # -------------------------------------------------------------------------
    # LIFECYCLE STATUS
    # -------------------------------------------------------------------------
    "status": FieldDef(
        name="status",
        display_name="Status",
        field_type=FieldType.STRING,
        category=FieldCategory.LIFECYCLE,
        required=False,
        default="none",
        choices=["none", "wip", "review", "approved"],
        ui_widget="select",
        show_in_card=True,
        sortable=True,
        validator=lambda v: v in ("none", "wip", "review", "approved"),
        description="Lifecycle status (WIP, Review, Approved)"
    ),

    # -------------------------------------------------------------------------
    # POSE FLAGS
    # -------------------------------------------------------------------------
    "is_pose": FieldDef(
        name="is_pose",
        display_name="Is Pose",
        field_type=FieldType.BOOLEAN,
        category=FieldCategory.POSE,
        required=False,
        default=False,
        ui_widget="checkbox",
        show_in_card=True,
        description="True for poses, False for animations"
    ),
    "is_partial": FieldDef(
        name="is_partial",
        display_name="Partial Pose",
        field_type=FieldType.BOOLEAN,
        category=FieldCategory.POSE,
        required=False,
        default=False,
        ui_widget="checkbox",
        description="Pose affects only selected bones"
    ),

    # -------------------------------------------------------------------------
    # STUDIO NAMING ENGINE
    # -------------------------------------------------------------------------
    "naming_fields": FieldDef(
        name="naming_fields",
        display_name="Naming Fields",
        field_type=FieldType.JSON,
        category=FieldCategory.NAMING,
        required=False,
        ui_widget="json",
        description='JSON dict: {"show":"PROJ","shot":"010",...}'
    ),
    "naming_template": FieldDef(
        name="naming_template",
        display_name="Naming Template",
        field_type=FieldType.STRING,
        category=FieldCategory.NAMING,
        required=False,
        ui_widget="text",
        description='Template: "{show}_{asset}_v{version:03}"'
    ),

    # -------------------------------------------------------------------------
    # DISPLAY / THUMBNAIL
    # -------------------------------------------------------------------------
    "use_custom_thumbnail_gradient": FieldDef(
        name="use_custom_thumbnail_gradient",
        display_name="Custom Gradient",
        field_type=FieldType.BOOLEAN,
        category=FieldCategory.DISPLAY,
        required=False,
        default=False,
        ui_widget="checkbox",
        description="Use custom gradient for thumbnail"
    ),
    "thumbnail_gradient_top": FieldDef(
        name="thumbnail_gradient_top",
        display_name="Gradient Top",
        field_type=FieldType.STRING,
        category=FieldCategory.DISPLAY,
        required=False,
        ui_widget="color",
        description="Top color for thumbnail gradient"
    ),
    "thumbnail_gradient_bottom": FieldDef(
        name="thumbnail_gradient_bottom",
        display_name="Gradient Bottom",
        field_type=FieldType.STRING,
        category=FieldCategory.DISPLAY,
        required=False,
        ui_widget="color",
        description="Bottom color for thumbnail gradient"
    ),

    # -------------------------------------------------------------------------
    # TIMESTAMPS
    # -------------------------------------------------------------------------
    "created_date": FieldDef(
        name="created_date",
        display_name="Created",
        field_type=FieldType.TIMESTAMP,
        category=FieldCategory.TIMESTAMPS,
        required=False,
        editable=False,
        sortable=True,
        description="Date animation was created"
    ),
    "modified_date": FieldDef(
        name="modified_date",
        display_name="Modified",
        field_type=FieldType.TIMESTAMP,
        category=FieldCategory.TIMESTAMPS,
        required=False,
        editable=False,
        sortable=True,
        description="Date animation was last modified"
    ),
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_field(name: str) -> Optional[FieldDef]:
    """
    Get a field definition by name.

    Args:
        name: Field name

    Returns:
        FieldDef or None if not found
    """
    return ANIMATION_FIELDS.get(name)


def get_fields_by_category(category: FieldCategory) -> Dict[str, FieldDef]:
    """
    Get all fields in a category.

    Args:
        category: Field category

    Returns:
        Dict of field_name -> FieldDef
    """
    return {
        name: field
        for name, field in ANIMATION_FIELDS.items()
        if field.category == category
    }


def get_required_fields() -> Dict[str, FieldDef]:
    """Get all required fields."""
    return {
        name: field
        for name, field in ANIMATION_FIELDS.items()
        if field.required
    }


def get_sortable_fields() -> List[str]:
    """Get names of all sortable fields."""
    return [
        name for name, field in ANIMATION_FIELDS.items()
        if field.sortable
    ]


def get_card_fields() -> List[str]:
    """Get names of fields shown in card view."""
    return [
        name for name, field in ANIMATION_FIELDS.items()
        if field.show_in_card
    ]


def get_editable_fields() -> Dict[str, FieldDef]:
    """Get all user-editable fields."""
    return {
        name: field
        for name, field in ANIMATION_FIELDS.items()
        if field.editable
    }


def validate_field(name: str, value: Any) -> Tuple[bool, Optional[str]]:
    """
    Validate a field value.

    Args:
        name: Field name
        value: Value to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    field_def = ANIMATION_FIELDS.get(name)
    if not field_def:
        return True, None  # Unknown fields allowed

    # Check required
    if field_def.required and value is None:
        return False, f"Field '{name}' is required"

    if value is None:
        return True, None  # Optional field, None is OK

    # Check type (basic check)
    type_map = {
        FieldType.STRING: str,
        FieldType.INTEGER: int,
        FieldType.REAL: (int, float),
        FieldType.BOOLEAN: (bool, int),  # Allow int for SQLite
        FieldType.TIMESTAMP: str,  # Stored as ISO string
        FieldType.JSON: (str, dict, list),
    }

    expected_type = type_map.get(field_def.field_type)
    if expected_type and not isinstance(value, expected_type):
        return False, f"Field '{name}' expected {field_def.field_type.value}, got {type(value).__name__}"

    # Check choices
    if field_def.choices and value not in field_def.choices:
        return False, f"Field '{name}' must be one of: {field_def.choices}"

    # Run custom validator
    if field_def.validator and not field_def.validator(value):
        return False, f"Field '{name}' failed validation"

    return True, None


def validate_animation(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate all fields in an animation data dict.

    Args:
        data: Animation data dict

    Returns:
        Tuple of (all_valid, list_of_errors)
    """
    errors = []

    # Check required fields
    for name, field_def in ANIMATION_FIELDS.items():
        if field_def.required and name not in data:
            errors.append(f"Missing required field: {name}")

    # Validate provided values
    for name, value in data.items():
        is_valid, error = validate_field(name, value)
        if not is_valid:
            errors.append(error)

    return len(errors) == 0, errors


__all__ = [
    # Types
    'FieldDef',
    'FieldType',
    'FieldCategory',

    # Registry
    'ANIMATION_FIELDS',

    # Functions
    'get_field',
    'get_fields_by_category',
    'get_required_fields',
    'get_sortable_fields',
    'get_card_fields',
    'get_editable_fields',
    'validate_field',
    'validate_animation',
]
