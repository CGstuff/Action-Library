"""
Protocol Constants - Shared constants for Desktop↔Blender communication.

This module contains all shared constants used by both the desktop app
and the Blender plugin for IPC communication.

Usage:
    from animation_library.protocol import QUEUE_DIR_NAME, DEFAULT_SOCKET_PORT
"""

# ============================================================================
# QUEUE CONFIGURATION
# ============================================================================

# Directory name for file-based queue (relative to library path)
QUEUE_DIR_NAME = ".queue"

# Fallback queue directory name (in system temp)
FALLBACK_QUEUE_DIR = "animation_library_queue"

# Queue file names
APPLY_ANIMATION_FILE = "apply_animation.json"
APPLY_POSE_FILE = "apply_pose.json"  # Currently uses same as animation

# File patterns for queue polling
QUEUE_FILE_PATTERN = "apply_*.json"


# ============================================================================
# SOCKET CONFIGURATION
# ============================================================================

# Default socket port
DEFAULT_SOCKET_PORT = 9876

# Socket host (localhost only for security)
SOCKET_HOST = "127.0.0.1"

# Environment variable for port override
SOCKET_PORT_ENV_VAR = "ANIMLIB_SOCKET_PORT"

# Connection timeouts (seconds)
SOCKET_CONNECT_TIMEOUT = 5.0
SOCKET_RECEIVE_TIMEOUT = 30.0
SOCKET_COMMAND_TIMEOUT = 2.0

# Retry configuration
MAX_CONNECTION_RETRIES = 3
RETRY_DELAY_MS = 100


# ============================================================================
# MESSAGE STATUS VALUES
# ============================================================================

class MessageStatus:
    """Standard status values for messages and responses."""
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
    PROCESSING = "processing"
    CANCELLED = "cancelled"


# ============================================================================
# APPLY MODES
# ============================================================================

class ApplyMode:
    """Animation apply mode options."""
    NEW = "NEW"        # Replace current action
    INSERT = "INSERT"  # Insert keyframes into current action


# ============================================================================
# RIG TYPES
# ============================================================================

class RigType:
    """Known rig type identifiers."""
    RIGIFY = "rigify"
    MIXAMO = "mixamo"
    AUTO_RIG_PRO = "auto_rig_pro"
    EPIC_SKELETON = "epic_skeleton"
    UNKNOWN = "unknown"


# ============================================================================
# COMMAND TYPES (for quick reference)
# ============================================================================

class CommandType:
    """Message type constants for Desktop→Blender commands."""
    # Animation/Pose
    APPLY_ANIMATION = "apply_animation"
    APPLY_POSE = "apply_pose"

    # Pose blending session
    BLEND_POSE_START = "blend_pose_start"
    BLEND_POSE = "blend_pose"
    BLEND_POSE_END = "blend_pose_end"

    # Bone selection
    SELECT_BONES = "select_bones"

    # Info queries
    GET_ARMATURE_INFO = "get_armature_info"
    GET_STATUS = "get_status"
    PING = "ping"


# ============================================================================
# POLLING CONFIGURATION
# ============================================================================

# Timer interval for socket listener modal operator (milliseconds)
SOCKET_POLL_INTERVAL_MS = 50

# Time budget for processing commands per tick (milliseconds)
QUEUE_TIME_BUDGET_MS = 16

# Maximum heavy commands per tick
MAX_HEAVY_COMMANDS_PER_TICK = 1

# Commands considered "heavy" (block main thread longer)
HEAVY_COMMANDS = frozenset([
    CommandType.APPLY_ANIMATION,
    CommandType.APPLY_POSE,
    CommandType.BLEND_POSE_END,
])


# ============================================================================
# PROTOCOL VERSION
# ============================================================================

# Protocol version for future compatibility checking
PROTOCOL_VERSION = "1.0.0"


__all__ = [
    # Queue
    'QUEUE_DIR_NAME',
    'FALLBACK_QUEUE_DIR',
    'APPLY_ANIMATION_FILE',
    'APPLY_POSE_FILE',
    'QUEUE_FILE_PATTERN',

    # Socket
    'DEFAULT_SOCKET_PORT',
    'SOCKET_HOST',
    'SOCKET_PORT_ENV_VAR',
    'SOCKET_CONNECT_TIMEOUT',
    'SOCKET_RECEIVE_TIMEOUT',
    'SOCKET_COMMAND_TIMEOUT',
    'MAX_CONNECTION_RETRIES',
    'RETRY_DELAY_MS',

    # Enums/Constants
    'MessageStatus',
    'ApplyMode',
    'RigType',
    'CommandType',

    # Polling
    'SOCKET_POLL_INTERVAL_MS',
    'QUEUE_TIME_BUDGET_MS',
    'MAX_HEAVY_COMMANDS_PER_TICK',
    'HEAVY_COMMANDS',

    # Version
    'PROTOCOL_VERSION',
]
