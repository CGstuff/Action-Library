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


# =============================================================================
# Action Slots
# =============================================================================
# Since Blender 4.4 an action holds one channelbag of fcurves PER SLOT, and
# animation_data.action_slot picks the one an object plays. One action can hold
# several takes for a rig, or animation for other rigs, props and cameras.
# Every helper below takes the slot to work on; code acting on a rig passes
# get_active_slot(rig). On Blender 4.4/4.5 the legacy action.fcurves API is
# NOT slot-aware either - it always means the first slot - so reads go through
# the channelbag on every version that has slots.

_warned_multi_slot_actions = set()


def get_active_slot(obj):
    """The slot obj is playing, or None (no action, or no slot assigned)."""
    anim_data = getattr(obj, 'animation_data', None)
    if not anim_data or not anim_data.action:
        return None
    return getattr(anim_data, 'action_slot', None)


def find_slot(action, handle):
    """Slot of action with this handle, or None if it was removed."""
    if not action or handle is None or not hasattr(action, 'slots'):
        return None
    return next((s for s in action.slots if s.handle == handle), None)


def _resolve_slot(action, slot):
    """slot itself, or the action's only slot when none was given.

    Falling back to the first slot of a MULTI-slot action is what made the
    addon ignore the slot the rig was playing, so it's logged: a caller that
    reaches it should be passing a slot.
    """
    if slot is not None:
        return slot
    slots = getattr(action, 'slots', None)
    if not slots:
        return None
    if len(slots) > 1 and action.name not in _warned_multi_slot_actions:
        _warned_multi_slot_actions.add(action.name)
        logger.warning(f"No slot given for multi-slot action '{action.name}' - using its first slot")
    return slots[0]


def get_channelbag(action, slot, ensure=False):
    """Channelbag holding slot's fcurves in action, or None.

    The one place that assumes a single layer with a single keyframe strip,
    which is all Blender currently supports. ensure=True creates whatever is
    missing.
    """
    if not action or slot is None or not hasattr(action, 'layers'):
        return None
    try:
        if not action.layers:
            if not ensure:
                return None
            action.layers.new(name="Layer")
        layer = action.layers[0]
        if not layer.strips:
            if not ensure:
                return None
            layer.strips.new(type='KEYFRAME')
        return layer.strips[0].channelbag(slot, ensure=ensure)
    except Exception as e:
        logger.warning(f"Failed to get channelbag for slot in '{action.name}': {e}")
        return None


def get_action_fcurves(action, slot=None):
    """
    Get one slot's fcurves from action

    Args:
        action: Blender action object
        slot: Action slot to read. Omit only for single-slot actions
              (library files, freshly built actions).

    Returns:
        FCurves collection or empty list
    """
    if not action:
        return []

    if hasattr(action, 'slots'):
        channelbag = get_channelbag(action, _resolve_slot(action, slot))
        return channelbag.fcurves if channelbag else []

    # Pre-slot Blender
    return action.fcurves if hasattr(action, 'fcurves') else []


def find_action_fcurve(action, data_path, index=0, slot=None):
    """
    Find fcurve in one slot of action by data path

    Args:
        action: Blender action object
        data_path: FCurve data path (e.g., 'pose.bones["Bone"].location')
        index: Array index (default 0)
        slot: Action slot to search (see get_action_fcurves)

    Returns:
        FCurve or None
    """
    if not action:
        return None

    if hasattr(action, 'slots'):
        channelbag = get_channelbag(action, _resolve_slot(action, slot))
        return channelbag.fcurves.find(data_path, index=index) if channelbag else None

    if hasattr(action, 'fcurves'):
        return action.fcurves.find(data_path, index=index)
    return None


def new_action_fcurve(action, data_path, index=0, slot=None, group_name=None):
    """
    Create new fcurve in one slot of action

    Args:
        action: Blender action object
        data_path: FCurve data path
        index: Array index (default 0)
        slot: Action slot to add to (see get_action_fcurves)
        group_name: Optional action group name

    Returns:
        New FCurve or None
    """
    if not action:
        return None

    slot = _resolve_slot(action, slot) if hasattr(action, 'slots') else None
    if slot is not None:
        channelbag = get_channelbag(action, slot, ensure=True)
        if channelbag is None:
            logger.warning(f"Failed to get channelbag for slot")
            return None
        try:
            if not group_name:
                return channelbag.fcurves.new(data_path, index=index)
            try:
                return channelbag.fcurves.new(data_path, index=index, group_name=group_name)
            except TypeError:
                # Blender without group_name on channelbag fcurves.new()
                fcurve = channelbag.fcurves.new(data_path, index=index)
                fcurve.group = channelbag.groups.get(group_name) or channelbag.groups.new(group_name)
                return fcurve
        except Exception as e:
            logger.warning(f"Failed to create fcurve via channelbag: {e}")
            return None

    # Action has no slot yet. Blender 4.4/4.5's legacy API creates the layer,
    # strip and slot itself; 5.0 removed it, so 5.0 callers must run
    # init_action_for_blender_5() first.
    if hasattr(action, 'fcurves'):
        if group_name:
            return action.fcurves.new(data_path, index=index, action_group=group_name)
        return action.fcurves.new(data_path, index=index)

    logger.warning(f"No slot or layers available for action")
    return None


def copy_action_with_slots(action, slots):
    """
    Copy action keeping only the given slots - curves, keys, handles and
    modifiers as-is.

    Used to save slots to the library without the action's other takes or
    other objects' animation. The copy carries no library tracking. The caller
    owns the copy and must remove it from bpy.data when done.
    """
    # Match by identifier, not handle: identifiers are unique within an action
    # and survive the copy.
    keep = {s.identifier for s in slots}
    action_copy = action.copy()
    for other in [s for s in action_copy.slots if s.identifier not in keep]:
        action_copy.slots.remove(other)

    if len(action_copy.slots) != len(keep):
        bpy.data.actions.remove(action_copy)
        names = ", ".join(s.name_display for s in slots)
        raise RuntimeError(f"Could not isolate slots ({names}) in a copy of '{action.name}'")

    for key in (SLOT_TRACKING_PROP, BUNDLE_TRACKING_PROP) + LIBRARY_TRACKING_KEYS:
        if key in action_copy:
            del action_copy[key]
    return action_copy


def copy_action_with_only_slot(action, slot):
    """copy_action_with_slots() for a single slot."""
    return copy_action_with_slots(action, [slot])


class SlotInfo:
    """One slot of an action, sorted by what it is to a given rig (see classify_slots)."""

    # Kinds an "All Slots" capture saves
    CAPTURED_KINDS = ('ACTIVE', 'TAKE')

    def __init__(self, slot, kind, reason=""):
        self.slot = slot
        self.kind = kind
        self.reason = reason

    @property
    def captured(self):
        return self.kind in self.CAPTURED_KINDS


def classify_slots(action, armature):
    """
    Sort every slot of action by what it is to armature (animation_slots_spec.md §3).

    ACTIVE        the slot the rig is playing
    TAKE          unused, and every bone it animates exists on the rig
    NON_OBJECT    shape keys, materials, camera data... - not playable by an object
    OTHER_RIG     played by another armature
    OTHER_OBJECT  played by another object
    EMPTY         no keyframes
    BONE_MISMATCH unused, but animates bones this rig doesn't have
    UNKNOWN       unused and animates no bones - could be anyone's

    The bone check reads the rig's bones as they are now, so a bone added to
    the rig counts straight away.

    Returns:
        list of SlotInfo, in slot order
    """
    active = get_active_slot(armature)
    active_handle = active.handle if active is not None else None
    infos = []
    for slot in action.slots:
        if not is_object_slot(slot):
            what = {'KEY': 'shape key'}.get(slot.target_id_type, slot.target_id_type.lower().replace('_', ' '))
            infos.append(SlotInfo(slot, 'NON_OBJECT', f"for {what} data, not an object"))
            continue
        if slot.handle == active_handle:
            infos.append(SlotInfo(slot, 'ACTIVE'))
            continue

        users = [u for u in (slot.users() if hasattr(slot, 'users') else []) if u != armature]
        rig_user = next((u for u in users if getattr(u, 'type', None) == 'ARMATURE'), None)
        if rig_user is not None:
            infos.append(SlotInfo(slot, 'OTHER_RIG', f"used by {rig_user.name}"))
            continue
        if users:
            infos.append(SlotInfo(slot, 'OTHER_OBJECT', f"used by {users[0].name}"))
            continue

        if get_action_keyframe_count(action, slot) == 0:
            infos.append(SlotInfo(slot, 'EMPTY', "empty"))
            continue

        bones = slot_animated_bones(action, slot)
        if not bones:
            infos.append(SlotInfo(slot, 'UNKNOWN', "animates no bones - assign it to the rig once to include it"))
            continue
        missing = bones.difference(armature.data.bones.keys())
        if missing:
            count = len(missing)
            infos.append(SlotInfo(slot, 'BONE_MISMATCH', f"animates {count} bone{'s' if count != 1 else ''} this rig doesn't have"))
            continue
        infos.append(SlotInfo(slot, 'TAKE'))
    return infos


_CLASSIFY_TTL = 0.5
_classify_cache = {}          # (action name, armature name) -> (timestamp, summary)


def classify_slots_cached(action, armature):
    """
    classify_slots() for panel draw(), recomputed at most every _CLASSIFY_TTL seconds.

    Returns plain (slot name, kind, reason) tuples, never the slots: a slot
    deleted between redraws would leave a dangling reference, and Blender only
    guards ID datablocks against that. Captures call classify_slots() directly
    so they always see the rig as it is.
    """
    import time as _time
    key = (action.name, armature.name)
    now = _time.time()
    cached = _classify_cache.get(key)
    if cached and (now - cached[0]) < _CLASSIFY_TTL:
        return cached[1]
    infos = [(i.slot.name_display, i.kind, i.reason) for i in classify_slots(action, armature)]
    _classify_cache[key] = (now, infos)
    if len(_classify_cache) > 32:
        oldest = min(_classify_cache.items(), key=lambda kv: kv[1][0])[0]
        _classify_cache.pop(oldest, None)
    return infos


def is_object_slot(slot):
    """True if slot can be played by an object (not shape keys, materials, camera data...)."""
    return slot.target_id_type in ('OBJECT', 'UNSPECIFIED')


def slot_animated_bones(action, slot):
    """Names of the bones slot animates."""
    bones = {extract_bone_name_from_data_path(fc.data_path) for fc in get_action_fcurves(action, slot)}
    bones.discard(None)
    return bones


def slot_matches_rig(action, slot, armature):
    """True if slot animates bones and EVERY one of them exists on armature.

    Checked against the armature's bones as they are now - never cached - so
    a bone added to the rig counts straight away.
    """
    bones = slot_animated_bones(action, slot)
    return bool(bones) and bones.issubset(armature.data.bones.keys())


def pick_slot_for_rig(action, armature, preferred_identifier=None):
    """
    Which slot of a library action armature should play.

    The capture records its slot as primary_slot_identifier; that wins.
    Library files saved before slot support can hold several slots,
    including other objects' - never pick one of those just because it's
    first, or a camera's location curves end up moving the rig.

    Returns:
        ActionSlot, or None if the action has no slot an object can play
    """
    candidates = [s for s in action.slots if is_object_slot(s)]
    if not candidates:
        return None
    if preferred_identifier:
        preferred = next((s for s in candidates if s.identifier == preferred_identifier), None)
        if preferred is not None:
            return preferred
    if len(candidates) == 1:
        return candidates[0]
    for rule in (lambda s: slot_matches_rig(action, s, armature),
                 lambda s: bool(slot_animated_bones(action, s))):
        match = next((s for s in candidates if rule(s)), None)
        if match is not None:
            return match
    return candidates[0]


def _enum_values(prop_name):
    """identifier -> value for an enum property of Keyframe (for bulk copy)."""
    return {item.identifier: item.value
            for item in bpy.types.Keyframe.bl_rna.properties[prop_name].enum_items}


# Per-segment properties: they describe the curve from this key to the NEXT one
_SEGMENT_PROPS = ('interpolation', 'easing', 'amplitude', 'back', 'period')
_ENUM_KEY_PROPS = ('interpolation', 'easing', 'handle_left_type', 'handle_right_type', 'type')
_FLOAT_KEY_PROPS = ('amplitude', 'back', 'period')


def copy_fcurve(src, channelbag, frame_map=None, reverse=False):
    """
    Copy src into channelbag with its full curve shape.

    keyframe_points.insert() only stores frame and value; handles,
    interpolation and easing come from Blender's defaults, so curves change
    shape. This copies every key property in bulk instead.

    Args:
        src: FCurve to copy
        channelbag: Destination channelbag (one slot of one action)
        frame_map: Optional function mapping source frames to destination
                   frames (keys AND handles go through it)
        reverse: frame_map runs backwards in time - keys are written in
                 reverse order, handles swap sides and each segment's
                 interpolation/easing moves to the key that now starts it

    Returns:
        The new FCurve
    """
    dst = channelbag.fcurves.new(src.data_path, index=src.array_index)
    if src.group is not None:
        dst.group = channelbag.groups.get(src.group.name) or channelbag.groups.new(src.group.name)
    dst.extrapolation = src.extrapolation
    dst.auto_smoothing = src.auto_smoothing

    kps = src.keyframe_points
    n = len(kps)
    if n == 0:
        return dst

    def read(prop, size=1, fill=0.0):
        values = [fill] * (n * size)
        kps.foreach_get(prop, values)
        return values

    co, hl, hr = read('co', 2), read('handle_left', 2), read('handle_right', 2)
    props = {p: read(p, fill=0) for p in _ENUM_KEY_PROPS}
    props.update({p: read(p) for p in _FLOAT_KEY_PROPS})

    fmap = frame_map or (lambda x: x)
    if reverse:
        order = range(n - 1, -1, -1)
        easing = _enum_values('easing')
        swap_easing = {easing['EASE_IN']: easing['EASE_OUT'], easing['EASE_OUT']: easing['EASE_IN']}
    else:
        order = range(n)

    new_co, new_hl, new_hr = [], [], []
    new_props = {p: [] for p in props}
    for i in order:
        new_co += [fmap(co[2 * i]), co[2 * i + 1]]
        if reverse:
            # Mirrored in time: the right handle becomes the left one
            new_hl += [fmap(hr[2 * i]), hr[2 * i + 1]]
            new_hr += [fmap(hl[2 * i]), hl[2 * i + 1]]
            new_props['handle_left_type'].append(props['handle_right_type'][i])
            new_props['handle_right_type'].append(props['handle_left_type'][i])
            new_props['type'].append(props['type'][i])
            # The segment now starting at key i was the one ending at it
            seg = i - 1 if i > 0 else i
            for p in _SEGMENT_PROPS:
                value = props[p][seg]
                new_props[p].append(swap_easing.get(value, value) if p == 'easing' else value)
        else:
            new_hl += [fmap(hl[2 * i]), hl[2 * i + 1]]
            new_hr += [fmap(hr[2 * i]), hr[2 * i + 1]]
            for p in props:
                new_props[p].append(props[p][i])

    dst.keyframe_points.add(n)
    dkps = dst.keyframe_points
    dkps.foreach_set('co', new_co)
    # Handle types before positions: AUTO/VECTOR recompute their own positions
    # on update(), FREE/ALIGNED keep what we set.
    for p in _ENUM_KEY_PROPS + _FLOAT_KEY_PROPS:
        dkps.foreach_set(p, new_props[p])
    dkps.foreach_set('handle_left', new_hl)
    dkps.foreach_set('handle_right', new_hr)
    dst.update()
    return dst


def copy_slot(src_action, src_slot, dst_action, dst_slot, bones=None, reverse=False):
    """
    Copy one slot's curves into a slot of another (or the same) action.

    Args:
        bones: Optional set of bone names - only their curves are copied
               (non-bone curves are skipped too)
        reverse: Play the slot backwards over its own keyframe range

    Returns:
        Number of fcurves copied
    """
    channelbag = get_channelbag(dst_action, dst_slot, ensure=True)
    if channelbag is None:
        raise RuntimeError(f"Could not get channelbag for slot '{dst_slot.name_display}'")

    frame_map = None
    if reverse:
        start, end = get_action_keyframe_range(src_action, src_slot)
        if start is not None:
            frame_map = lambda x: end - (x - start)

    copied = 0
    for fcurve in get_action_fcurves(src_action, src_slot):
        if bones is not None and extract_bone_name_from_data_path(fcurve.data_path) not in bones:
            continue
        copy_fcurve(fcurve, channelbag, frame_map=frame_map, reverse=reverse and frame_map is not None)
        copied += 1
    return copied


def derive_action(src_action, name, bones=None, reverse=False):
    """
    New action with every object slot of src_action copied through copy_slot.

    Slots keep their names, so their identifiers - and the slot a capture
    marked as primary - carry over. Slots that end up empty (filtered out)
    are dropped.

    Returns:
        The new action, or None if nothing was copied
    """
    new_action = bpy.data.actions.new(name=name)
    copied = 0
    for src_slot in [s for s in src_action.slots if is_object_slot(s)]:
        dst_slot = new_action.slots.new('OBJECT', src_slot.name_display)
        count = copy_slot(src_action, src_slot, new_action, dst_slot, bones=bones, reverse=reverse)
        if count == 0:
            new_action.slots.remove(dst_slot)
        copied += count
    if copied == 0:
        bpy.data.actions.remove(new_action)
        return None
    return new_action


def describe_slot(action, slot):
    """JSON-ready summary of one slot, for library metadata."""
    fcurves = get_action_fcurves(action, slot)
    start, end = get_action_keyframe_range(action, slot)
    bones = slot_animated_bones(action, slot)
    return {
        'identifier': slot.identifier,
        'name': slot.name_display,
        'handle': slot.handle,
        'target_id_type': slot.target_id_type,
        'frame_start': start,
        'frame_end': end,
        'keyframe_count': get_action_keyframe_count(action, slot),
        'fcurve_count': len(fcurves),
        'animated_bone_count': len(bones),
    }


# =============================================================================
# Library tracking ("this slot came from library animation X, version N")
# =============================================================================
# Kept PER SLOT in action["animlib_slots"][str(slot.handle)], because one action
# can hold several unrelated animations. Actions tracked before slots stored
# these keys on the action itself; they're read as belonging to the first slot
# and moved into the per-slot dict on the next write.

BUNDLE_TRACKING_PROP = "animlib_bundle"   # tracking for an "All Slots" capture
LIBRARY_TRACKING_KEYS = (
    "animlib_imported",
    "animlib_app_version",
    "animlib_uuid",
    "animlib_name",
    "animlib_version",
    "animlib_version_label",
    "animlib_version_group_id",
    "animlib_rig_type",
)
SLOT_TRACKING_PROP = "animlib_slots"


def _is_first_slot(action, slot):
    return slot is None or not action.slots or slot.handle == action.slots[0].handle


def get_library_tracking(action, slot):
    """Library tracking for slot as a plain dict ({} if not from the library)."""
    if not action:
        return {}
    per_slot = action.get(SLOT_TRACKING_PROP)
    if per_slot is not None:
        if slot is None:
            return {}
        entry = per_slot.get(str(slot.handle))
        return entry.to_dict() if entry is not None else {}
    if _is_first_slot(action, slot):
        return {key: action[key] for key in LIBRARY_TRACKING_KEYS if key in action}
    return {}


def _migrate_legacy_tracking(action):
    """Move action-level tracking keys to the first slot's entry."""
    if SLOT_TRACKING_PROP in action:
        return
    legacy = {key: action[key] for key in LIBRARY_TRACKING_KEYS if key in action}
    if not legacy or not action.slots:
        return
    action[SLOT_TRACKING_PROP] = {str(action.slots[0].handle): legacy}
    for key in legacy:
        del action[key]


def set_library_tracking(action, slot, tracking):
    """Store tracking (see library_tracking_from_metadata) for slot."""
    if slot is None:
        # Slotless action (nothing to key by) - keep the pre-slot layout
        for key, value in tracking.items():
            action[key] = value
        return
    _migrate_legacy_tracking(action)
    if SLOT_TRACKING_PROP not in action:
        action[SLOT_TRACKING_PROP] = {}
    action[SLOT_TRACKING_PROP][str(slot.handle)] = tracking


def clear_library_tracking(action, slot):
    """Forget that slot came from the library (stale or archived entry)."""
    if slot is None or SLOT_TRACKING_PROP not in action:
        if _is_first_slot(action, slot):
            for key in LIBRARY_TRACKING_KEYS:
                if key in action:
                    del action[key]
        return
    per_slot = action[SLOT_TRACKING_PROP]
    if str(slot.handle) in per_slot:
        del per_slot[str(slot.handle)]


def get_bundle_tracking(action):
    """Library tracking for the action as an "All Slots" entry ({} if none).

    Kept apart from the per-slot tracking: a slot captured on its own and the
    whole set of the rig's slots captured together are different library
    animations, so neither should offer to version the other.
    """
    if not action:
        return {}
    bundle = action.get(BUNDLE_TRACKING_PROP)
    return bundle.to_dict() if bundle is not None else {}


def set_bundle_tracking(action, tracking):
    """Store tracking (see library_tracking_from_metadata) for the action as a bundle."""
    action[BUNDLE_TRACKING_PROP] = tracking


def clear_bundle_tracking(action):
    """Forget that the action came from the library as an "All Slots" entry."""
    if BUNDLE_TRACKING_PROP in action:
        del action[BUNDLE_TRACKING_PROP]


def library_tracking_from_metadata(metadata):
    """Tracking dict from library metadata (capture JSON uses 'id', apply uses 'uuid').

    Values are converted explicitly: Blender 5.0 rejects some ID property types.
    """
    uuid = metadata.get('id') or metadata.get('uuid') or ''
    return {
        "animlib_imported": True,
        "animlib_app_version": "1.3.0",  # For one-time v1.2→v1.3 migration detection
        "animlib_uuid": str(uuid),
        "animlib_version_group_id": str(metadata.get('version_group_id') or uuid),
        "animlib_version": int(metadata.get('version') or 1),
        "animlib_version_label": str(metadata.get('version_label') or 'v001'),
        "animlib_name": str(metadata.get('name') or ''),
        "animlib_rig_type": str(metadata.get('rig_type') or ''),
    }


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

# Panel draw() runs on Blender's ONE UI thread, on every redraw - mouse move,
# frame change, selection change. Walking every keyframe of every fcurve there
# means the addon competes with the user's own input for that thread: on a
# 1800-fcurve rig it measured tens of milliseconds PER REDRAW, which reads as
# "the addon locked my bones" because Blender is simply too busy to process the
# drag. Nothing was ever locked.
#
# The panel only needs these to print a line of text, so a value up to
# _STATS_TTL seconds old is indistinguishable from a fresh one. Operators that
# actually capture animation still call the uncached functions.
_STATS_TTL = 0.5
_action_stats_cache = {}      # (action name, slot handle) -> (timestamp, start, end, count)


def get_action_stats_cached(action, slot=None):
    """(first_frame, last_frame, keyframe_count) for display. Cheap to call often.

    Recomputed at most every _STATS_TTL seconds per action slot. Use the uncached
    get_action_keyframe_range/count when the exact current value matters.
    """
    if not action:
        return None, None, 0

    import time as _time
    # Keyed per slot too, or switching slots would show the old slot's numbers
    key = (action.name, slot.handle if slot is not None else None)
    now = _time.time()
    cached = _action_stats_cache.get(key)
    if cached and (now - cached[0]) < _STATS_TTL:
        return cached[1], cached[2], cached[3]

    start, end = get_action_keyframe_range(action, slot)
    count = get_action_keyframe_count(action, slot)
    _action_stats_cache[key] = (now, start, end, count)

    # Don't let the cache grow with every action the user ever selects.
    if len(_action_stats_cache) > 32:
        oldest = min(_action_stats_cache.items(), key=lambda kv: kv[1][0])[0]
        _action_stats_cache.pop(oldest, None)

    return start, end, count


def invalidate_action_stats(action_name=None):
    """Drop cached stats - after a capture or apply changes an action."""
    if action_name is None:
        _action_stats_cache.clear()
    else:
        for key in [k for k in _action_stats_cache if k[0] == action_name]:
            _action_stats_cache.pop(key, None)


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