"""
Animation Library Protocol - Single source of truth for Desktop↔Blender IPC.

This package defines all message types, validation rules, and shared constants
for communication between the Animation Library desktop app and Blender plugin.

Architecture:
    Desktop App writes messages → Blender Plugin validates and processes
    Blender Plugin sends responses → Desktop App receives

Communication Methods:
    1. Socket-based (preferred): Real-time TCP socket (~10-50ms latency)
    2. File-based (fallback): JSON queue files (~100-500ms latency)

Usage - Desktop App:
    from animation_library.protocol import build_apply_animation

    # Build a message
    msg = build_apply_animation(
        animation_id='uuid-here',
        animation_name='Walk Cycle',
        options={'apply_mode': 'NEW'}
    )

    # Send via socket or write to queue file

Usage - Blender Plugin:
    from ..protocol import validate_message, get_field_value

    # Validate incoming message
    is_valid, error = validate_message(incoming_msg)
    if not is_valid:
        return build_error_response(error)

    # Extract fields with fallback handling
    animation_id = get_field_value(msg, 'animation_id')

Sync Strategy:
    The protocol/ directory is copied from animation_library to blender_plugin
    during addon install/update. Both sides read from the same schema.
"""

# Schema definitions
from .schema import (
    FieldDef,
    MessageDef,
    ResponseDef,
    MESSAGE_TYPES,
    RESPONSE_FIELDS,
    APPLY_OPTIONS_SCHEMA,
    get_message_def,
    get_field_def,
)

# Message builders and validators
from .messages import (
    # Core functions
    build_message,
    validate_message,
    validate_options,
    get_field_value,
    normalize_message,

    # Response builders
    build_response,
    build_success_response,
    build_error_response,

    # Convenience builders
    build_apply_animation,
    build_apply_pose,
    build_blend_pose_start,
    build_blend_pose,
    build_blend_pose_end,
    build_select_bones,

    # Exceptions
    ValidationError,
)

# Constants
from .constants import (
    # Queue
    QUEUE_DIR_NAME,
    FALLBACK_QUEUE_DIR,
    APPLY_ANIMATION_FILE,
    APPLY_POSE_FILE,
    QUEUE_FILE_PATTERN,

    # Socket
    DEFAULT_SOCKET_PORT,
    SOCKET_HOST,
    SOCKET_PORT_ENV_VAR,
    SOCKET_CONNECT_TIMEOUT,
    SOCKET_RECEIVE_TIMEOUT,
    SOCKET_COMMAND_TIMEOUT,
    MAX_CONNECTION_RETRIES,
    RETRY_DELAY_MS,

    # Enums
    MessageStatus,
    ApplyMode,
    RigType,
    CommandType,

    # Polling
    SOCKET_POLL_INTERVAL_MS,
    QUEUE_TIME_BUDGET_MS,
    MAX_HEAVY_COMMANDS_PER_TICK,
    HEAVY_COMMANDS,

    # Version
    PROTOCOL_VERSION,
)


__all__ = [
    # Schema
    'FieldDef',
    'MessageDef',
    'ResponseDef',
    'MESSAGE_TYPES',
    'RESPONSE_FIELDS',
    'APPLY_OPTIONS_SCHEMA',
    'get_message_def',
    'get_field_def',

    # Message functions
    'build_message',
    'validate_message',
    'validate_options',
    'get_field_value',
    'normalize_message',
    'build_response',
    'build_success_response',
    'build_error_response',
    'build_apply_animation',
    'build_apply_pose',
    'build_blend_pose_start',
    'build_blend_pose',
    'build_blend_pose_end',
    'build_select_bones',
    'ValidationError',

    # Constants
    'QUEUE_DIR_NAME',
    'FALLBACK_QUEUE_DIR',
    'APPLY_ANIMATION_FILE',
    'APPLY_POSE_FILE',
    'QUEUE_FILE_PATTERN',
    'DEFAULT_SOCKET_PORT',
    'SOCKET_HOST',
    'SOCKET_PORT_ENV_VAR',
    'SOCKET_CONNECT_TIMEOUT',
    'SOCKET_RECEIVE_TIMEOUT',
    'SOCKET_COMMAND_TIMEOUT',
    'MAX_CONNECTION_RETRIES',
    'RETRY_DELAY_MS',
    'MessageStatus',
    'ApplyMode',
    'RigType',
    'CommandType',
    'SOCKET_POLL_INTERVAL_MS',
    'QUEUE_TIME_BUDGET_MS',
    'MAX_HEAVY_COMMANDS_PER_TICK',
    'HEAVY_COMMANDS',
    'PROTOCOL_VERSION',
]
