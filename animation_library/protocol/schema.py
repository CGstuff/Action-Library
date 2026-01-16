"""
Protocol Schema - Single source of truth for Desktop↔Blender communication.

This module defines all message types exchanged between the Animation Library
desktop app and the Blender plugin.

Usage:
    from animation_library.protocol import MESSAGE_TYPES, FieldDef

    # Get field definitions for a message type
    msg_def = MESSAGE_TYPES['apply_animation']
    print(msg_def.fields)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Union, Tuple


@dataclass
class FieldDef:
    """
    Definition for a single message field.

    Attributes:
        name: Field name as it appears in the message JSON
        field_type: Expected Python type (or tuple of types)
        required: Whether the field is required
        default: Default value if not provided (None = no default)
        validator: Optional validation function (value) -> bool
        description: Human-readable description
        fallbacks: Alternative field names to try if primary is missing
    """
    name: str
    field_type: Union[type, Tuple[type, ...]] = str
    required: bool = False
    default: Any = None
    validator: Optional[Callable[[Any], bool]] = None
    description: str = ""
    fallbacks: List[str] = field(default_factory=list)


@dataclass
class MessageDef:
    """
    Definition for a message type.

    Attributes:
        type_name: The 'type' field value in the message
        direction: 'desktop_to_blender' or 'blender_to_desktop'
        fields: List of FieldDef objects
        description: Human-readable description of the message purpose
        is_stateful: Whether this message is part of a stateful session
        session_group: Group name for stateful sessions (e.g., 'blend_pose')
    """
    type_name: str
    direction: str
    fields: List[FieldDef]
    description: str = ""
    is_stateful: bool = False
    session_group: Optional[str] = None


# ============================================================================
# FIELD DEFINITIONS - Reusable field templates
# ============================================================================

# Animation/Pose identifiers
ANIMATION_ID_FIELD = FieldDef(
    name='animation_id',
    field_type=str,
    required=True,
    description='UUID of the animation to apply'
)

POSE_ID_FIELD = FieldDef(
    name='pose_id',
    field_type=str,
    required=False,
    fallbacks=['animation_id'],
    description='UUID of the pose to apply (can also use animation_id)'
)

# Names (for display)
ANIMATION_NAME_FIELD = FieldDef(
    name='animation_name',
    field_type=str,
    required=False,
    default='Unknown',
    description='Animation name for display purposes'
)

POSE_NAME_FIELD = FieldDef(
    name='pose_name',
    field_type=str,
    required=False,
    fallbacks=['animation_name'],
    default='Unknown Pose',
    description='Pose name for display purposes'
)

# File paths
BLEND_FILE_PATH_FIELD = FieldDef(
    name='blend_file_path',
    field_type=str,
    required=True,
    description='Path to the .blend file containing the action'
)

# Options
MIRROR_FIELD = FieldDef(
    name='mirror',
    field_type=bool,
    required=False,
    default=False,
    description='Apply with L/R bone swapping'
)

APPLY_OPTIONS_FIELD = FieldDef(
    name='options',
    field_type=dict,
    required=False,
    default=None,
    description='Animation apply options (apply_mode, mirror, reverse, etc.)'
)

# Blend factor
BLEND_FACTOR_FIELD = FieldDef(
    name='blend_factor',
    field_type=(int, float),
    required=True,
    validator=lambda v: 0.0 <= v <= 1.0,
    description='Blend factor from 0.0 (original) to 1.0 (full pose)'
)

# Bone selection
BONE_NAMES_FIELD = FieldDef(
    name='bone_names',
    field_type=list,
    required=True,
    validator=lambda v: all(isinstance(b, str) for b in v),
    description='List of bone names to select'
)

ADD_TO_SELECTION_FIELD = FieldDef(
    name='add_to_selection',
    field_type=bool,
    required=False,
    default=False,
    description='Add to current selection instead of replacing'
)

# Blend session
CANCELLED_FIELD = FieldDef(
    name='cancelled',
    field_type=bool,
    required=False,
    default=False,
    description='Whether the blend session was cancelled'
)

INSERT_KEYFRAMES_FIELD = FieldDef(
    name='insert_keyframes',
    field_type=bool,
    required=False,
    default=False,
    description='Insert keyframes for affected bones'
)


# ============================================================================
# MESSAGE TYPE DEFINITIONS
# ============================================================================

MESSAGE_TYPES: Dict[str, MessageDef] = {
    # -------------------------------------------------------------------------
    # Animation Application
    # -------------------------------------------------------------------------
    'apply_animation': MessageDef(
        type_name='apply_animation',
        direction='desktop_to_blender',
        description='Apply an animation to the active armature',
        fields=[
            ANIMATION_ID_FIELD,
            ANIMATION_NAME_FIELD,
            APPLY_OPTIONS_FIELD,
        ]
    ),

    # -------------------------------------------------------------------------
    # Pose Application
    # -------------------------------------------------------------------------
    'apply_pose': MessageDef(
        type_name='apply_pose',
        direction='desktop_to_blender',
        description='Apply a pose instantly to the active armature',
        fields=[
            POSE_ID_FIELD,
            FieldDef(
                name='animation_id',
                field_type=str,
                required=False,
                description='Alias for pose_id (backwards compatibility)'
            ),
            POSE_NAME_FIELD,
            BLEND_FILE_PATH_FIELD,
            MIRROR_FIELD,
        ]
    ),

    # -------------------------------------------------------------------------
    # Pose Blending Session (Stateful - 3 messages)
    # -------------------------------------------------------------------------
    'blend_pose_start': MessageDef(
        type_name='blend_pose_start',
        direction='desktop_to_blender',
        description='Start a pose blending session',
        is_stateful=True,
        session_group='blend_pose',
        fields=[
            FieldDef(
                name='pose_id',
                field_type=str,
                required=True,
                description='UUID of the pose to blend to'
            ),
            POSE_NAME_FIELD,
            BLEND_FILE_PATH_FIELD,
        ]
    ),

    'blend_pose': MessageDef(
        type_name='blend_pose',
        direction='desktop_to_blender',
        description='Update blend factor during active session',
        is_stateful=True,
        session_group='blend_pose',
        fields=[
            BLEND_FACTOR_FIELD,
            MIRROR_FIELD,
        ]
    ),

    'blend_pose_end': MessageDef(
        type_name='blend_pose_end',
        direction='desktop_to_blender',
        description='End the pose blending session',
        is_stateful=True,
        session_group='blend_pose',
        fields=[
            CANCELLED_FIELD,
            INSERT_KEYFRAMES_FIELD,
            FieldDef(
                name='apply',
                field_type=bool,
                required=False,
                default=True,
                description='Whether to apply the final pose (alias for !cancelled)'
            ),
        ]
    ),

    # -------------------------------------------------------------------------
    # Bone Selection
    # -------------------------------------------------------------------------
    'select_bones': MessageDef(
        type_name='select_bones',
        direction='desktop_to_blender',
        description='Select bones in pose mode',
        fields=[
            BONE_NAMES_FIELD,
            MIRROR_FIELD,
            ADD_TO_SELECTION_FIELD,
        ]
    ),

    # -------------------------------------------------------------------------
    # Status/Info Queries
    # -------------------------------------------------------------------------
    'get_armature_info': MessageDef(
        type_name='get_armature_info',
        direction='desktop_to_blender',
        description='Get info about the active armature',
        fields=[]
    ),

    'get_status': MessageDef(
        type_name='get_status',
        direction='desktop_to_blender',
        description='Get Blender status (version, mode, etc.)',
        fields=[]
    ),

    'ping': MessageDef(
        type_name='ping',
        direction='desktop_to_blender',
        description='Connection test',
        fields=[]
    ),
}


# ============================================================================
# RESPONSE SCHEMA
# ============================================================================

@dataclass
class ResponseDef:
    """Definition for response messages from Blender."""
    status: str  # 'success' or 'error'
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


# Standard response fields
RESPONSE_FIELDS = {
    'status': FieldDef(
        name='status',
        field_type=str,
        required=True,
        validator=lambda v: v in ('success', 'error'),
        description="Response status: 'success' or 'error'"
    ),
    'message': FieldDef(
        name='message',
        field_type=str,
        required=False,
        default='',
        description='Human-readable response message'
    ),
    'data': FieldDef(
        name='data',
        field_type=dict,
        required=False,
        default=None,
        description='Additional response data'
    ),
}


# ============================================================================
# APPLY OPTIONS SCHEMA
# ============================================================================

APPLY_OPTIONS_SCHEMA = {
    'apply_mode': FieldDef(
        name='apply_mode',
        field_type=str,
        required=False,
        default='NEW',
        validator=lambda v: v in ('NEW', 'INSERT'),
        description="'NEW' replaces action, 'INSERT' inserts keyframes"
    ),
    'mirror': FieldDef(
        name='mirror',
        field_type=bool,
        required=False,
        default=False,
        description='Mirror animation (swap L/R bones)'
    ),
    'reverse': FieldDef(
        name='reverse',
        field_type=bool,
        required=False,
        default=False,
        description='Play animation in reverse'
    ),
    'selected_bones_only': FieldDef(
        name='selected_bones_only',
        field_type=bool,
        required=False,
        default=False,
        description='Apply only to selected bones'
    ),
    'use_slots': FieldDef(
        name='use_slots',
        field_type=bool,
        required=False,
        default=False,
        description='Use action slots (Blender 4.4+)'
    ),
}


def get_message_def(message_type: str) -> Optional[MessageDef]:
    """
    Get the message definition for a given type.

    Args:
        message_type: The 'type' field value

    Returns:
        MessageDef or None if not found
    """
    return MESSAGE_TYPES.get(message_type)


def get_field_def(message_type: str, field_name: str) -> Optional[FieldDef]:
    """
    Get a specific field definition from a message type.

    Args:
        message_type: The message type name
        field_name: The field name

    Returns:
        FieldDef or None if not found
    """
    msg_def = MESSAGE_TYPES.get(message_type)
    if not msg_def:
        return None

    for field_def in msg_def.fields:
        if field_def.name == field_name:
            return field_def

    return None


__all__ = [
    'FieldDef',
    'MessageDef',
    'ResponseDef',
    'MESSAGE_TYPES',
    'RESPONSE_FIELDS',
    'APPLY_OPTIONS_SCHEMA',
    'get_message_def',
    'get_field_def',
]
