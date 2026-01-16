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
DEFAULT_POSE_NAME = "New Pose"

# Blender version check for API compatibility
BLENDER_5_0_OR_LATER = bpy.app.version >= (5, 0, 0)


# =============================================================================
# Blender Version Compatibility Adapter
# =============================================================================
# These helpers abstract away API differences between Blender versions

def select_bone(pose_bone, select: bool = True):
    """
    Select or deselect a pose bone, compatible with Blender 4.x and 5.0+.

    In Blender 5.0+, the `select` property moved from Bone to PoseBone.

    Args:
        pose_bone: PoseBone object
        select: True to select, False to deselect
    """
    if BLENDER_5_0_OR_LATER:
        pose_bone.select = select
    else:
        pose_bone.bone.select = select


def is_bone_selected(pose_bone) -> bool:
    """
    Check if a pose bone is selected, compatible with Blender 4.x and 5.0+.

    Args:
        pose_bone: PoseBone object

    Returns:
        True if selected
    """
    if BLENDER_5_0_OR_LATER:
        return pose_bone.select
    else:
        return pose_bone.bone.select


def deselect_all_bones(armature):
    """
    Deselect all bones on an armature, compatible with Blender 4.x and 5.0+.

    Args:
        armature: Armature object in pose mode
    """
    if armature and armature.pose:
        for pose_bone in armature.pose.bones:
            select_bone(pose_bone, False)


# =============================================================================
# Context Management Utilities
# =============================================================================

from contextlib import contextmanager


@contextmanager
def temporary_area_type(area, new_type):
    """
    Context manager for safely changing an area type and restoring it.

    Ensures the area type is always restored even if an exception occurs,
    preventing Blender UI from being left in an inconsistent state.

    Args:
        area: Blender Area object
        new_type: Target area type (e.g., 'DOPESHEET_EDITOR', 'VIEW_3D')

    Yields:
        The area object for convenience

    Examples:
        >>> with temporary_area_type(area, 'DOPESHEET_EDITOR') as a:
        ...     # Perform operations in dopesheet context
        ...     bpy.ops.action.copy()
        >>> # Area type is automatically restored
    """
    if area is None:
        yield area
        return

    original_type = area.type

    try:
        area.type = new_type
        yield area
    finally:
        try:
            area.type = original_type
        except Exception as e:
            logger.warning(f"Could not restore area type to {original_type}: {e}")


@contextmanager
def find_and_use_area(area_types=('VIEW_3D', 'DOPESHEET_EDITOR', 'GRAPH_EDITOR')):
    """
    Context manager to find a suitable area when context.area is None.

    This is useful for socket/timer-based operations where bpy.context.area
    may not be set.

    Args:
        area_types: Tuple of acceptable area types to search for

    Yields:
        Found area object, or None if no suitable area found

    Examples:
        >>> with find_and_use_area() as area:
        ...     if area:
        ...         with temporary_area_type(area, 'VIEW_3D'):
        ...             bpy.ops.view3d.some_operator()
    """
    area = bpy.context.area

    if area is None:
        # Search for a suitable area
        for window in bpy.context.window_manager.windows:
            for a in window.screen.areas:
                if a.type in area_types:
                    area = a
                    break
            if area:
                break

    yield area


# =============================================================================
# Blender 5.0 Compatibility Helpers
# =============================================================================
# In Blender 5.0, the legacy action.fcurves API was removed.
# FCurves must now be accessed through channelbags via slots.


def init_action_for_blender_5(action, slot_name="Slot"):
    """
    Initialize a new action for Blender 5.0+ with proper layer/strip/slot structure.

    In Blender 5.0, actions require layers, strips, and slots to store fcurves.
    Structure: Action → Layers → Strips → Channelbags → FCurves

    The correct order according to Blender 5.0 API:
    1. Create layer
    2. Create keyframe strip on layer
    3. Create slot
    4. Get channelbag via strip.channelbag(slot, ensure=True)

    Args:
        action: Blender action object
        slot_name: Name for the slot (default "Slot")

    Returns:
        The created slot, or None if setup failed
    """
    if not BLENDER_5_0_OR_LATER:
        return None

    if not action:
        return None

    try:
        # Step 1: Create layer FIRST (required for strips and channelbags)
        layer = None
        if hasattr(action, 'layers'):
            if len(action.layers) == 0:
                layer = action.layers.new(name="Layer")
                logger.debug(f"Created layer for action '{action.name}'")
            else:
                layer = action.layers[0]
                logger.debug(f"Using existing layer for action '{action.name}'")

        if not layer:
            logger.error(f"Failed to create/get layer for action '{action.name}'")
            return None

        # Step 2: Create keyframe strip on layer
        strip = None
        if hasattr(layer, 'strips'):
            if len(layer.strips) == 0:
                try:
                    strip = layer.strips.new(type='KEYFRAME')
                    logger.debug(f"Created keyframe strip for action '{action.name}'")
                except Exception as e:
                    logger.error(f"Could not create strip: {e}")
                    return None
            else:
                strip = layer.strips[0]
                logger.debug(f"Using existing strip for action '{action.name}'")

        if not strip:
            logger.error(f"Failed to create/get strip for action '{action.name}'")
            return None

        # Step 3: Create slot
        slot = None
        if hasattr(action, 'slots'):
            slot = action.slots.new('OBJECT', slot_name)
            logger.debug(f"Created slot for action '{action.name}'")

        if not slot:
            logger.error(f"Failed to create slot for action '{action.name}'")
            return None

        # Step 4: Get channelbag for the slot using strip.channelbag() - the correct Blender 5.0 API
        try:
            channelbag = strip.channelbag(slot, ensure=True)
            if channelbag:
                logger.debug(f"Channelbag created via strip.channelbag()")
            else:
                logger.warning(f"strip.channelbag() returned None")
        except Exception as e:
            logger.warning(f"strip.channelbag() failed: {e}")
            # Fallback to anim_utils helper
            try:
                from bpy_extras import anim_utils
                channelbag = anim_utils.action_ensure_channelbag_for_slot(action, slot)
                if channelbag:
                    logger.debug(f"Channelbag created via anim_utils fallback")
            except Exception as e2:
                logger.error(f"All channelbag creation methods failed: {e2}")

        return slot

    except Exception as e:
        logger.error(f"Failed to initialize action for Blender 5.0: {e}")
        import traceback
        traceback.print_exc()
        return None


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
        # Blender 5.0+ - must use channelbag API via strip
        try:
            if slot is None and hasattr(action, 'slots') and action.slots:
                slot = action.slots[0]
            if slot and hasattr(action, 'layers') and action.layers:
                layer = action.layers[0]
                if hasattr(layer, 'strips') and layer.strips:
                    strip = layer.strips[0]
                    # Use strip.channelbag() - the correct Blender 5.0 API
                    channelbag = strip.channelbag(slot)
                    return channelbag.fcurves if channelbag else []
            # Fallback to anim_utils
            from bpy_extras import anim_utils
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
            if slot is None and hasattr(action, 'slots') and action.slots:
                slot = action.slots[0]
            if slot and hasattr(action, 'layers') and action.layers:
                layer = action.layers[0]
                if hasattr(layer, 'strips') and layer.strips:
                    strip = layer.strips[0]
                    # Use strip.channelbag() - the correct Blender 5.0 API
                    channelbag = strip.channelbag(slot)
                    if channelbag:
                        return channelbag.fcurves.find(data_path, index=index)
            # Fallback to anim_utils
            from bpy_extras import anim_utils
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
            if slot is None and hasattr(action, 'slots') and action.slots:
                slot = action.slots[0]
            if slot and hasattr(action, 'layers') and action.layers:
                layer = action.layers[0]
                if hasattr(layer, 'strips') and layer.strips:
                    strip = layer.strips[0]
                    # Use strip.channelbag() directly - this is the correct Blender 5.0 API
                    channelbag = strip.channelbag(slot, ensure=True)
                    if channelbag:
                        if group_name:
                            return channelbag.fcurves.new(data_path, index=index, group_name=group_name)
                        else:
                            return channelbag.fcurves.new(data_path, index=index)
                    else:
                        logger.warning(f"Failed to get channelbag for slot")
                else:
                    logger.warning(f"Action has no strips - action may not be initialized properly")
            else:
                logger.warning(f"No slot or layers available for action")
        except Exception as e:
            logger.warning(f"Failed to create fcurve via channelbag: {e}")
            import traceback
            traceback.print_exc()
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