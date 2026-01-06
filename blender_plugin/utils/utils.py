"""
Shared utility functions for the Animation Library Blender plugin
"""
import bpy
import re
from .logger import get_logger

# Initialize logger
logger = get_logger()

# Constants
ADDON_NAME = "Animation Library"
DEFAULT_ANIMATION_NAME = "New Action"

# Blender version check for API compatibility
BLENDER_5_0_OR_LATER = bpy.app.version >= (5, 0, 0)


# =============================================================================
# Blender 5.0 Compatibility Helpers
# =============================================================================
# In Blender 5.0, the legacy action.fcurves API was removed.
# FCurves must now be accessed through channelbags via slots.

def get_action_fcurves(action, slot=None):
    """
    Get fcurves from action, compatible with Blender 4.x and 5.0+

    Args:
        action: Blender action object
        slot: Optional action slot (for 5.0+, uses first slot if None)

    Returns:
        FCurves collection or empty list
    """
    if not action:
        return []

    if BLENDER_5_0_OR_LATER:
        # Blender 5.0+ - must use channelbag API
        try:
            from bpy_extras import anim_utils
            if slot is None and hasattr(action, 'slots') and action.slots:
                slot = action.slots[0]
            if slot:
                channelbag = anim_utils.action_get_channelbag_for_slot(action, slot)
                return channelbag.fcurves if channelbag else []
        except Exception as e:
            logger.warning(f"Failed to get fcurves via channelbag: {e}")
            return []
        return []
    else:
        # Blender 4.x - legacy API
        return action.fcurves if hasattr(action, 'fcurves') else []


def find_action_fcurve(action, data_path, index=0, slot=None):
    """
    Find fcurve in action by data path, compatible with Blender 4.x and 5.0+

    Args:
        action: Blender action object
        data_path: FCurve data path (e.g., 'pose.bones["Bone"].location')
        index: Array index (default 0)
        slot: Optional action slot (for 5.0+)

    Returns:
        FCurve or None
    """
    if not action:
        return None

    if BLENDER_5_0_OR_LATER:
        try:
            from bpy_extras import anim_utils
            if slot is None and hasattr(action, 'slots') and action.slots:
                slot = action.slots[0]
            if slot:
                channelbag = anim_utils.action_get_channelbag_for_slot(action, slot)
                if channelbag:
                    return channelbag.fcurves.find(data_path, index=index)
        except Exception as e:
            logger.warning(f"Failed to find fcurve via channelbag: {e}")
        return None
    else:
        # Blender 4.x - legacy API
        if hasattr(action, 'fcurves'):
            return action.fcurves.find(data_path, index=index)
        return None


def new_action_fcurve(action, data_path, index=0, slot=None, group_name=None):
    """
    Create new fcurve in action, compatible with Blender 4.x and 5.0+

    Args:
        action: Blender action object
        data_path: FCurve data path
        index: Array index (default 0)
        slot: Optional action slot (for 5.0+)
        group_name: Optional action group name

    Returns:
        New FCurve or None
    """
    if not action:
        return None

    if BLENDER_5_0_OR_LATER:
        try:
            from bpy_extras import anim_utils
            if slot is None and hasattr(action, 'slots') and action.slots:
                slot = action.slots[0]
            if slot:
                channelbag = anim_utils.action_ensure_channelbag_for_slot(action, slot)
                if channelbag:
                    if group_name:
                        return channelbag.fcurves.new(data_path, index=index, group_name=group_name)
                    else:
                        return channelbag.fcurves.new(data_path, index=index)
        except Exception as e:
            logger.warning(f"Failed to create fcurve via channelbag: {e}")
        return None
    else:
        # Blender 4.x - legacy API
        if hasattr(action, 'fcurves'):
            if group_name:
                return action.fcurves.new(data_path, index=index, action_group=group_name)
            else:
                return action.fcurves.new(data_path, index=index)
        return None


def has_action_fcurves(action, slot=None):
    """
    Check if action has any fcurves, compatible with Blender 4.x and 5.0+

    Args:
        action: Blender action object
        slot: Optional action slot (for 5.0+)

    Returns:
        bool
    """
    fcurves = get_action_fcurves(action, slot)
    return len(fcurves) > 0 if fcurves else False

# Mirror bone naming patterns for different rig types
MIRROR_PATTERNS = {
    'rigify': {
        'left': '.L',
        'right': '.R'
    },
    'mixamo': {
        'left': 'Left',
        'right': 'Right'
    },
    'auto_rig_pro': {
        'left': '.l',
        'right': '.r'
    },
    'epic_skeleton': {
        'left': '_l',
        'right': '_r'
    }
}

def get_action_keyframe_range(action, slot=None):
    """Get the actual first and last keyframe in the action"""
    fcurves = get_action_fcurves(action, slot)
    if not fcurves:
        return None, None

    # Find min and max keyframe across all fcurves
    min_frame = float('inf')
    max_frame = float('-inf')

    for fcurve in fcurves:
        if fcurve.keyframe_points:
            for keyframe in fcurve.keyframe_points:
                frame = int(keyframe.co[0])  # co[0] is the frame number
                min_frame = min(min_frame, frame)
                max_frame = max(max_frame, frame)

    # If no keyframes found, return None
    if min_frame == float('inf') or max_frame == float('-inf'):
        return None, None

    return min_frame, max_frame

def get_action_keyframe_count(action, slot=None):
    """Get total number of keyframes in the action"""
    fcurves = get_action_fcurves(action, slot)
    if not fcurves:
        return 0

    total_keyframes = 0
    for fcurve in fcurves:
        if fcurve.keyframe_points:
            total_keyframes += len(fcurve.keyframe_points)

    return total_keyframes

def get_active_armature(context):
    """Get the active armature object, return None if not an armature"""
    armature = context.active_object
    if armature and armature.type == 'ARMATURE':
        return armature
    return None

def has_animation_data(armature):
    """Check if armature has valid animation data with action"""
    return (armature and 
            armature.animation_data and 
            armature.animation_data.action)

def safe_report_error(operator, message):
    """Safely report an error message to the operator"""
    try:
        operator.report({'ERROR'}, message)
    except Exception:
        logger.error(message)

def safe_report_info(operator, message):
    """Safely report an info message to the operator"""
    try:
        operator.report({'INFO'}, message)
    except Exception:
        logger.info(message)

def extract_bone_name_from_data_path(data_path):
    """
    Extract bone name from fcurve data path
    Example: 'pose.bones["arm.L"].location' -> 'arm.L'
    """
    match = re.search(r'pose\.bones\["([^"]+)"\]', data_path)
    if match:
        return match.group(1)
    return None

def get_mirrored_bone_name(bone_name, rig_type='rigify'):
    """
    Get the mirrored bone name for a given bone

    Args:
        bone_name: Original bone name (e.g., 'arm.L', 'LeftShoulder')
        rig_type: One of 'rigify', 'mixamo', 'auto_rig_pro', 'epic_skeleton'

    Returns:
        str or None: Mirrored bone name, or None if bone doesn't have mirror pair
    """
    if rig_type not in MIRROR_PATTERNS:
        return None

    patterns = MIRROR_PATTERNS[rig_type]
    left_pattern = patterns['left']
    right_pattern = patterns['right']

    # Check if bone has left suffix
    if bone_name.endswith(left_pattern):
        return bone_name[:-len(left_pattern)] + right_pattern
    elif left_pattern in bone_name and not bone_name.endswith(left_pattern):
        # Handle cases like "LeftArm" where pattern is not at the end
        return bone_name.replace(left_pattern, right_pattern)

    # Check if bone has right suffix
    if bone_name.endswith(right_pattern):
        return bone_name[:-len(right_pattern)] + left_pattern
    elif right_pattern in bone_name and not bone_name.endswith(right_pattern):
        # Handle cases like "RightArm" where pattern is not at the end
        return bone_name.replace(right_pattern, left_pattern)

    # No mirror pattern found
    return None

def detect_mirror_support(action, rig_type='rigify', slot=None):
    """
    Analyze action to determine if it supports mirroring based on bone naming conventions

    Args:
        action: Blender action object
        rig_type: One of 'rigify', 'mixamo', 'auto_rig_pro', 'epic_skeleton'
        slot: Optional action slot (for Blender 5.0+)

    Returns:
        bool: True if animation has mirrored bone pairs and can be mirrored
    """
    fcurves = get_action_fcurves(action, slot)
    if not fcurves:
        return False

    # Extract all unique bone names from fcurves
    bone_names = set()
    for fcurve in fcurves:
        bone_name = extract_bone_name_from_data_path(fcurve.data_path)
        if bone_name:
            bone_names.add(bone_name)

    if not bone_names:
        return False

    # Count bones with mirror pairs
    mirrored_bones = 0
    checked_bones = set()

    for bone_name in bone_names:
        if bone_name in checked_bones:
            continue

        mirror_name = get_mirrored_bone_name(bone_name, rig_type)
        if mirror_name and mirror_name in bone_names:
            mirrored_bones += 1
            checked_bones.add(bone_name)
            checked_bones.add(mirror_name)

    # Consider animation mirror-capable if at least 3 bone pairs exist
    # (e.g., arms, legs, shoulders - typical minimum for useful mirroring)
    return mirrored_bones >= 3