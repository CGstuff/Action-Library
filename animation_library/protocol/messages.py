"""
Protocol Messages - Builder and validator functions for IPC messages.

This module provides functions to build well-formed messages for Desktop→Blender
communication and validate incoming messages against the schema.

Usage:
    from animation_library.protocol import build_message, validate_message

    # Build a message (Desktop side)
    msg = build_message('apply_animation', {
        'animation_id': 'uuid-here',
        'animation_name': 'Walk Cycle',
        'options': {'apply_mode': 'NEW'}
    })

    # Validate a message (Blender side)
    is_valid, error = validate_message(incoming_msg)
"""

from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from .schema import (
    MESSAGE_TYPES,
    RESPONSE_FIELDS,
    APPLY_OPTIONS_SCHEMA,
    get_message_def,
    FieldDef,
    MessageDef,
)


class ValidationError(Exception):
    """Raised when message validation fails."""
    pass


def build_message(
    message_type: str,
    data: Dict[str, Any],
    include_timestamp: bool = True
) -> Dict[str, Any]:
    """
    Build a well-formed message from the given data.

    This function:
    1. Validates that the message type exists
    2. Extracts fields from data according to the schema
    3. Applies fallbacks for missing fields
    4. Applies defaults for optional fields
    5. Adds the 'type' field automatically

    Args:
        message_type: The type of message to build (e.g., 'apply_animation')
        data: Source data dict to extract fields from
        include_timestamp: Whether to add a timestamp field

    Returns:
        A well-formed message dict ready for sending

    Raises:
        ValidationError: If required fields are missing or invalid
    """
    msg_def = get_message_def(message_type)
    if not msg_def:
        raise ValidationError(f"Unknown message type: {message_type}")

    message = {'type': message_type}

    if include_timestamp:
        message['timestamp'] = datetime.now().isoformat()

    for field_def in msg_def.fields:
        value = _extract_field_value(field_def, data)

        # Check required fields
        if value is None:
            if field_def.required:
                raise ValidationError(
                    f"Missing required field '{field_def.name}' for message type '{message_type}'"
                )
            elif field_def.default is not None:
                value = field_def.default

        # Validate type and custom validator
        if value is not None:
            if not isinstance(value, field_def.field_type):
                raise ValidationError(
                    f"Field '{field_def.name}' has invalid type. "
                    f"Expected {field_def.field_type}, got {type(value).__name__}"
                )

            if field_def.validator and not field_def.validator(value):
                raise ValidationError(
                    f"Field '{field_def.name}' failed validation"
                )

        # Only include non-None values (or explicit defaults)
        if value is not None:
            message[field_def.name] = value

    return message


def _extract_field_value(field_def: FieldDef, data: Dict[str, Any]) -> Any:
    """
    Extract a field value from data, trying fallbacks if needed.

    Args:
        field_def: The field definition
        data: Source data dict

    Returns:
        The field value or None
    """
    # Try primary field name
    value = data.get(field_def.name)
    if value is not None:
        return value

    # Try fallback field names
    for fallback in field_def.fallbacks:
        value = data.get(fallback)
        if value is not None:
            return value

    return None


def validate_message(
    message: Dict[str, Any],
    message_type: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate an incoming message against its schema.

    Args:
        message: The message dict to validate
        message_type: Optional type override (defaults to message['type'])

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(message, dict):
        return False, "Message must be a dictionary"

    msg_type = message_type or message.get('type')
    if not msg_type:
        return False, "Missing message type"

    msg_def = get_message_def(msg_type)
    if not msg_def:
        # Unknown message types are allowed but logged
        return True, None

    for field_def in msg_def.fields:
        result = _validate_field(field_def, message)
        if not result[0]:
            return result

    return True, None


def _validate_field(
    field_def: FieldDef,
    message: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Validate a single field against its definition.

    Args:
        field_def: The field definition
        message: The message dict

    Returns:
        Tuple of (is_valid, error_message)
    """
    value = _extract_field_value(field_def, message)

    # Check required fields
    if value is None:
        if field_def.required:
            return False, f"Missing required field: {field_def.name}"
        return True, None

    # Check type
    if not isinstance(value, field_def.field_type):
        return False, (
            f"Field '{field_def.name}' has invalid type. "
            f"Expected {field_def.field_type}, got {type(value).__name__}"
        )

    # Run custom validator
    if field_def.validator and not field_def.validator(value):
        return False, f"Field '{field_def.name}' failed validation"

    return True, None


def validate_options(options: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate animation apply options against the schema.

    Args:
        options: The options dict to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(options, dict):
        return False, "Options must be a dictionary"

    for field_name, field_def in APPLY_OPTIONS_SCHEMA.items():
        value = options.get(field_name)

        if value is None:
            continue

        if not isinstance(value, field_def.field_type):
            return False, (
                f"Option '{field_name}' has invalid type. "
                f"Expected {field_def.field_type}, got {type(value).__name__}"
            )

        if field_def.validator and not field_def.validator(value):
            return False, f"Option '{field_name}' failed validation"

    return True, None


def get_field_value(
    message: Dict[str, Any],
    field_name: str,
    default: Any = None
) -> Any:
    """
    Get a field value from a message, handling fallbacks.

    This is useful on the receiving side to extract values with proper
    fallback handling as defined in the schema.

    Args:
        message: The message dict
        field_name: Primary field name to look for
        default: Default value if field not found

    Returns:
        The field value or default
    """
    msg_type = message.get('type')
    if not msg_type:
        return message.get(field_name, default)

    msg_def = get_message_def(msg_type)
    if not msg_def:
        return message.get(field_name, default)

    # Find the field definition
    field_def = None
    for fd in msg_def.fields:
        if fd.name == field_name:
            field_def = fd
            break

    if not field_def:
        return message.get(field_name, default)

    value = _extract_field_value(field_def, message)
    return value if value is not None else (field_def.default or default)


def normalize_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a message by applying defaults and resolving fallbacks.

    This creates a new message dict with:
    - All field values resolved from fallbacks
    - Default values applied for missing optional fields
    - Original message structure preserved

    Args:
        message: The message to normalize

    Returns:
        A normalized copy of the message
    """
    msg_type = message.get('type')
    if not msg_type:
        return dict(message)

    msg_def = get_message_def(msg_type)
    if not msg_def:
        return dict(message)

    normalized = {'type': msg_type}

    # Copy timestamp if present
    if 'timestamp' in message:
        normalized['timestamp'] = message['timestamp']

    # Process each field
    for field_def in msg_def.fields:
        value = _extract_field_value(field_def, message)

        if value is None and field_def.default is not None:
            value = field_def.default

        if value is not None:
            normalized[field_def.name] = value

    return normalized


def build_response(
    status: str,
    message: str = "",
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build a standard response message.

    Args:
        status: 'success' or 'error'
        message: Human-readable message
        data: Optional additional data

    Returns:
        Response dict
    """
    response = {
        'status': status,
        'message': message,
    }
    if data:
        response['data'] = data
    return response


def build_success_response(
    message: str = "",
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build a success response."""
    return build_response('success', message, data)


def build_error_response(
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build an error response."""
    return build_response('error', message, data)


# ============================================================================
# CONVENIENCE BUILDERS for common message types
# ============================================================================

def build_apply_animation(
    animation_id: str,
    animation_name: str = "Unknown",
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build an apply_animation message.

    Args:
        animation_id: Animation UUID
        animation_name: Display name
        options: Apply options (apply_mode, mirror, reverse, etc.)

    Returns:
        Message dict ready for sending
    """
    data = {
        'animation_id': animation_id,
        'animation_name': animation_name,
    }
    if options:
        data['options'] = options
    return build_message('apply_animation', data)


def build_apply_pose(
    pose_id: str,
    pose_name: str,
    blend_file_path: str,
    mirror: bool = False
) -> Dict[str, Any]:
    """
    Build an apply_pose message.

    Args:
        pose_id: Pose UUID
        pose_name: Display name
        blend_file_path: Path to .blend file
        mirror: Whether to mirror L/R bones

    Returns:
        Message dict ready for sending
    """
    return build_message('apply_pose', {
        'pose_id': pose_id,
        'pose_name': pose_name,
        'blend_file_path': blend_file_path,
        'mirror': mirror,
    })


def build_blend_pose_start(
    pose_id: str,
    pose_name: str,
    blend_file_path: str
) -> Dict[str, Any]:
    """Build a blend_pose_start message."""
    return build_message('blend_pose_start', {
        'pose_id': pose_id,
        'pose_name': pose_name,
        'blend_file_path': blend_file_path,
    })


def build_blend_pose(
    blend_factor: float,
    mirror: bool = False
) -> Dict[str, Any]:
    """Build a blend_pose message."""
    return build_message('blend_pose', {
        'blend_factor': blend_factor,
        'mirror': mirror,
    })


def build_blend_pose_end(
    cancelled: bool = False,
    insert_keyframes: bool = False
) -> Dict[str, Any]:
    """Build a blend_pose_end message."""
    return build_message('blend_pose_end', {
        'cancelled': cancelled,
        'insert_keyframes': insert_keyframes,
    })


def build_select_bones(
    bone_names: List[str],
    mirror: bool = False,
    add_to_selection: bool = False
) -> Dict[str, Any]:
    """Build a select_bones message."""
    return build_message('select_bones', {
        'bone_names': bone_names,
        'mirror': mirror,
        'add_to_selection': add_to_selection,
    })


__all__ = [
    # Core functions
    'build_message',
    'validate_message',
    'validate_options',
    'get_field_value',
    'normalize_message',

    # Response builders
    'build_response',
    'build_success_response',
    'build_error_response',

    # Convenience builders
    'build_apply_animation',
    'build_apply_pose',
    'build_blend_pose_start',
    'build_blend_pose',
    'build_blend_pose_end',
    'build_select_bones',

    # Exceptions
    'ValidationError',
]
