import bpy
import os
import time
from bpy.types import Operator
from bpy.props import StringProperty
import tempfile
import json
from pathlib import Path
import traceback
from ..utils.queue_client import animation_queue_client
from ..utils.logger import get_logger
from ..utils.utils import (
    get_action_keyframe_range, extract_bone_name_from_data_path,
    get_action_fcurves, find_action_fcurve, new_action_fcurve,
    get_active_slot, find_slot, set_library_tracking, set_bundle_tracking,
    library_tracking_from_metadata,
    pick_slot_for_rig, is_object_slot, slot_matches_rig, copy_slot, derive_action
)
from ..preferences.AL_preferences import get_library_path

# Initialize logger
logger = get_logger()


def _blend_from_folder(folder):
    """Return the path to the .blend inside an asset folder, or None.

    Resolution is by folder (located via UUID), not by filename, so a name
    that has drifted from the stored path (post-rename) still resolves. If the
    folder holds multiple .blend files the choice is stable (sorted).
    """
    if not folder:
        return None
    blends = sorted(Path(folder).glob("*.blend"))
    return str(blends[0]) if blends else None


def _find_asset_by_uuid(library_dir, target_uuid):
    """Locate an asset's JSON + folder by scanning the local library for its UUID.

    Scans hot storage (library/actions, library/poses, legacy library/) and cold
    storage (_versions/). Resolution is purely by the UUID stored in each JSON,
    so it is independent of the drive letter and of any stale/embedded absolute
    path. Returns (json_path, folder) or (None, None).
    """
    if not library_dir or not target_uuid:
        return None, None
    library_dir = Path(library_dir)

    search_folders = []
    library_folder = library_dir / "library"
    if library_folder.exists():
        for sub in ("actions", "poses"):
            p = library_folder / sub
            if p.exists():
                search_folders.append(p)
        # Legacy: assets directly under library/
        search_folders.append(library_folder)

    def _matches(json_path):
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError, OSError):
            return False
        return (data.get("id") or data.get("uuid")) == target_uuid

    for search_folder in search_folders:
        for folder in search_folder.iterdir():
            if folder.is_dir() and folder.name not in ("actions", "poses"):
                for pj in folder.glob("*.json"):
                    if _matches(pj):
                        return pj, folder

    # Cold storage: _versions/{base}/{version}/
    versions_folder = library_dir / "_versions"
    if versions_folder.exists():
        for anim_folder in versions_folder.iterdir():
            if anim_folder.is_dir():
                for version_folder in anim_folder.iterdir():
                    if version_folder.is_dir():
                        for pj in version_folder.glob("*.json"):
                            if _matches(pj):
                                return pj, version_folder

    return None, None


def get_quaternion_at_frame(action, bone_name, frame, slot=None):
    """
    Read all 4 quaternion components from fcurves at a given frame.

    Args:
        action: Blender action to read from
        bone_name: Name of the bone
        frame: Frame number to evaluate at
        slot: Slot of action to read

    Returns:
        mathutils.Quaternion with the rotation at that frame
    """
    from mathutils import Quaternion

    quat_path = f'pose.bones["{bone_name}"].rotation_quaternion'
    components = [1.0, 0.0, 0.0, 0.0]  # Default quaternion (identity): W=1, X=0, Y=0, Z=0

    for i in range(4):
        fcurve = find_action_fcurve(action, quat_path, index=i, slot=slot)
        if fcurve:
            components[i] = fcurve.evaluate(frame)

    return Quaternion(components)

class ANIMLIB_OT_apply_animation(Operator):
    """Apply selected Action to current armature"""
    bl_idname = "animlib.apply_animation"
    bl_label = "Apply Action"
    bl_description = "Apply selected Action to the active armature"

    animation_id: StringProperty()
    apply_selected_bones_only: bpy.props.BoolProperty(default=False)
    selected_bones_list: StringProperty(default="")

    # Options from desktop app (overrides scene properties when set)
    apply_mode: StringProperty(default="")  # "NEW" or "INSERT", empty = use scene property
    use_slots: bpy.props.BoolProperty(default=False)
    mirror_animation: bpy.props.BoolProperty(default=False)
    reverse_animation: bpy.props.BoolProperty(default=False)
    options_from_queue: bpy.props.BoolProperty(default=False)  # True when options come from queue
    
    def are_rigs_compatible(self, rig_type1, rig_type2):
        """Check if two rig types are compatible for animation sharing"""
        # Same rig type is always compatible
        # Since we're detecting based on controller bone naming conventions,
        # rigs of the same type will have compatible bone structures
        # regardless of armature name (Dude, John, Jack, Joe, etc.)
        if rig_type1 == rig_type2:
            return True
        
        # Allow unknown rigs to work with any rig (less strict for edge cases)
        if rig_type1 == 'unknown' or rig_type2 == 'unknown':
            return True
        
        # Different rig types are generally incompatible due to different
        # controller bone naming conventions (e.g. Rigify vs Mixamo vs Auto-Rig Pro)
        return False
    
    def execute(self, context):
        armature = context.active_object
        
        # Validate selection
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select an armature object")
            return {'CANCELLED'}
        
        # Get current rig type
        current_rig_type, _ = animation_queue_client.detect_rig_type(armature)
        
        try:
            # Get library path from preferences
            library_path = get_library_path()
            
            if not library_path:
                self.report({'ERROR'}, "No library path set in preferences")
                return {'CANCELLED'}
            
            # Load animation metadata from JSON
            library_dir = Path(library_path)
            json_file = None
            animation_folder = None

            # Search library folder (hot storage) for animation by UUID
            # Check library/actions/, library/poses/, and library/ (legacy)
            library_folder = library_dir / "library"
            search_folders = []
            if library_folder.exists():
                # New structure: library/actions/ and library/poses/
                actions_folder = library_folder / "actions"
                poses_folder = library_folder / "poses"
                if actions_folder.exists():
                    search_folders.append(actions_folder)
                if poses_folder.exists():
                    search_folders.append(poses_folder)
                # Legacy: direct children of library/
                search_folders.append(library_folder)

            for search_folder in search_folders:
                for folder in search_folder.iterdir():
                    if folder.is_dir() and folder.name not in ('actions', 'poses'):
                        for potential_json in folder.glob("*.json"):
                            try:
                                with open(potential_json, 'r') as f:
                                    data = json.load(f)
                                animation_uuid = data.get('id') or data.get('uuid')
                                if animation_uuid == self.animation_id:
                                    json_file = potential_json
                                    animation_folder = folder
                                    break
                            except (json.JSONDecodeError, IOError):
                                continue
                    if json_file:
                        break
                if json_file:
                    break

            # Also check _versions folder (cold storage) for old versions
            if not json_file:
                versions_folder = library_dir / "_versions"
                if versions_folder.exists():
                    for anim_folder in versions_folder.iterdir():
                        if anim_folder.is_dir():
                            for version_folder in anim_folder.iterdir():
                                if version_folder.is_dir():
                                    for potential_json in version_folder.glob("*.json"):
                                        try:
                                            with open(potential_json, 'r') as f:
                                                data = json.load(f)
                                            animation_uuid = data.get('id') or data.get('uuid')
                                            if animation_uuid == self.animation_id:
                                                json_file = potential_json
                                                animation_folder = version_folder
                                                break
                                        except (json.JSONDecodeError, IOError):
                                            continue
                                if json_file:
                                    break
                        if json_file:
                            break

            if not json_file:
                self.report({'ERROR'}, f"Action metadata not found: {self.animation_id}")
                return {'CANCELLED'}
            
            with open(json_file, 'r') as f:
                animation = json.load(f)
            
            # Check rig compatibility (allow same rig families)
            animation_rig_type = animation.get('rig_type')
            if not self.are_rigs_compatible(animation_rig_type, current_rig_type):
                self.report({'ERROR'},
                    f"Rig type mismatch: Action is for '{animation_rig_type}', "
                    f"current armature is '{current_rig_type}'")
                return {'CANCELLED'}
            
            # Resolve the blend file. The embedded blend_file_path can be stale
            # (the asset was renamed since capture) or point at another machine's
            # drive letter. We already located the asset's folder by UUID above,
            # so fall back to that folder's .blend - this makes apply rename-safe
            # and drive-independent (fixes cross-machine apply for read-only peers).
            blend_file_path = animation.get('blend_file_path')
            if not blend_file_path or not os.path.exists(blend_file_path):
                blend_file_path = _blend_from_folder(animation_folder)
            if not blend_file_path or not os.path.exists(blend_file_path):
                self.report({'ERROR'}, f"Action blend file not found in {animation_folder}")
                return {'CANCELLED'}
            
            frame_start = animation.get('frame_start')
            frame_end = animation.get('frame_end')
            animation_name = animation.get('name')
            
            # Parse selected bones list
            selected_bones = []
            if self.apply_selected_bones_only and self.selected_bones_list:
                selected_bones = [bone.strip() for bone in self.selected_bones_list.split(',') if bone.strip()]

            # Get apply options - prefer operator properties (from queue) over scene properties
            if self.options_from_queue:
                # Options from desktop app queue
                apply_mode = self.apply_mode if self.apply_mode else "NEW"
                use_slots = self.use_slots
                mirror_animation = self.mirror_animation
                reverse_animation = self.reverse_animation
                logger.debug("Using options from desktop app queue")
            else:
                # Legacy: use scene properties (for manual Blender UI usage)
                apply_mode = bpy.context.scene.animlib_apply_mode
                use_slots = bpy.context.scene.animlib_use_slots
                mirror_animation = bpy.context.scene.animlib_mirror_animation
                reverse_animation = bpy.context.scene.animlib_reverse_animation
                logger.debug("Using options from scene properties")

            logger.debug(f"Applying Action with mode: {apply_mode}, use_slots: {use_slots}, mirror: {mirror_animation}, reverse: {reverse_animation}")

            # Build animation metadata for library tracking
            animation_metadata = {
                'uuid': self.animation_id,
                'version_group_id': animation.get('version_group_id', self.animation_id),
                'version': animation.get('version', 1),
                'version_label': animation.get('version_label', 'v001'),
                'name': animation.get('name', animation_name),
                'rig_type': animation_rig_type
            }

            # Apply animation by loading from blend file
            success = self.apply_animation_from_blend_file(
                armature,
                blend_file_path,
                frame_start,
                frame_end,
                animation_name=animation_name,
                apply_mode=apply_mode,
                apply_selected_bones_only=self.apply_selected_bones_only,
                selected_bones=selected_bones,
                use_slots=use_slots,
                mirror_animation=mirror_animation,
                reverse_animation=reverse_animation,
                rig_type=animation_rig_type,
                animation_metadata=animation_metadata,
                primary_slot_identifier=animation.get('primary_slot_identifier'),
                slot_mode=animation.get('slot_mode', 'active')
            )

            if success:
                self.report({'INFO'}, f"Applied Action '{animation_name}' successfully")
            else:
                self.report({'ERROR'}, "Failed to apply Action keyframes")
                return {'CANCELLED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error applying Action: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}

    def mirror_action(self, source_action, rig_type, target_armature, source_slot=None):
        """
        Create a mirrored version of an action using Blender's native copy/paste flipped operators

        This mimics the manual workflow:
        1. Apply source action temporarily
        2. Copy all keyframes
        3. Create new action with single keyframe
        4. Paste flipped using Blender's built-in mirroring

        Args:
            source_action: Source action to mirror
            rig_type: Rig type for bone naming convention (unused, for compatibility)
            target_armature: Target armature

        Returns:
            Mirrored action or None if mirroring fails
        """
        # Initialize before the try so the except can always restore context
        # safely. Previously original_area_type/area could be referenced before
        # assignment, raising a NameError inside the except that got swallowed -
        # leaving the viewport stranded as a Dope Sheet after a failed mirror.
        original_action = None
        original_slot_handle = None
        area = None
        original_area_type = None
        try:
            logger.info("Starting mirror operation using Blender's native paste flipped")

            # Store original context
            original_action = target_armature.animation_data.action if target_armature.animation_data else None
            original_slot = get_active_slot(target_armature)
            original_slot_handle = original_slot.handle if original_slot else None
            original_mode = bpy.context.mode

            # Find an available area - context.area may be None when called from socket/timer
            area = bpy.context.area
            if area is None:
                # Find a 3D View or any suitable area from the current screen
                for window in bpy.context.window_manager.windows:
                    for a in window.screen.areas:
                        if a.type in ('VIEW_3D', 'DOPESHEET_EDITOR', 'GRAPH_EDITOR'):
                            area = a
                            break
                    if area:
                        break

            if area is None:
                logger.error("No suitable area found for mirror operation")
                return None

            original_area_type = area.type

            # Ensure animation data exists
            if not target_armature.animation_data:
                target_armature.animation_data_create()

            # Temporarily apply source action, playing the slot to mirror
            target_armature.animation_data.action = source_action
            if source_slot is not None:
                target_armature.animation_data.action_slot = source_slot

            # Switch to pose mode if needed
            if bpy.context.active_object != target_armature:
                bpy.context.view_layer.objects.active = target_armature

            if bpy.context.mode != 'POSE':
                bpy.ops.object.mode_set(mode='POSE')

            # Select all bones
            bpy.ops.pose.select_all(action='SELECT')

            # Switch to Dope Sheet context to copy keyframes
            old_type = area.type
            area.type = 'DOPESHEET_EDITOR'

            # Set dope sheet to Action Editor mode
            for space in area.spaces:
                if space.type == 'DOPESHEET_EDITOR':
                    space.mode = 'ACTION'
                    break

            # Find the region for context override
            region = None
            for r in area.regions:
                if r.type == 'WINDOW':
                    region = r
                    break

            # Find window for context override
            window = bpy.context.window
            if window is None:
                for w in bpy.context.window_manager.windows:
                    window = w
                    break

            # Use context override for dopesheet operators
            with bpy.context.temp_override(window=window, area=area, region=region):
                # Select all keyframes
                bpy.ops.action.select_all(action='SELECT')

                # Copy keyframes
                bpy.ops.action.copy()
                logger.info("Copied all keyframes from source action")

            # Create new action for mirrored animation
            mirrored_action = bpy.data.actions.new(name=f"{source_action.name}_mirrored")
            target_armature.animation_data.action = mirrored_action

            # Get frame range from source action
            frame_start, frame_end = get_action_keyframe_range(source_action, source_slot)

            if frame_start is None:
                frame_start = 1

            # Set current frame to start frame
            bpy.context.scene.frame_set(int(frame_start))

            # Switch back to 3D View for keyframe insert
            area.type = 'VIEW_3D'

            # Find 3D view region
            view3d_region = None
            for r in area.regions:
                if r.type == 'WINDOW':
                    view3d_region = r
                    break

            # Insert a single keyframe on all selected bones to create fcurves
            # This is required for paste to work
            with bpy.context.temp_override(window=window, area=area, region=view3d_region):
                bpy.ops.anim.keyframe_insert_menu(type='WholeCharacter')
            logger.info(f"Inserted initial keyframe at frame {frame_start}")

            # Switch back to dopesheet for paste
            area.type = 'DOPESHEET_EDITOR'
            for space in area.spaces:
                if space.type == 'DOPESHEET_EDITOR':
                    space.mode = 'ACTION'
                    break

            # Re-find region after area type change
            for r in area.regions:
                if r.type == 'WINDOW':
                    region = r
                    break

            # Use context override for dopesheet operators again
            with bpy.context.temp_override(window=window, area=area, region=region):
                # Select all keyframes in new action
                bpy.ops.action.select_all(action='SELECT')

                # Paste flipped - this uses Blender's built-in mirroring logic
                bpy.ops.action.paste(flipped=True)
                logger.info("Pasted keyframes with flipped option")

                # Clean up
                bpy.ops.action.select_all(action='DESELECT')

            # Restore original area type
            area.type = old_type

            # Restore original context
            if original_mode == 'OBJECT' or original_mode != 'POSE':
                bpy.ops.object.mode_set(mode='OBJECT')

            logger.info(f"Successfully created mirrored action: {mirrored_action.name}")
            return mirrored_action

        except Exception as e:
            logger.error(f"Error mirroring action with native operators: {e}")
            logger.error(traceback.format_exc())

            # Try to restore context
            try:
                if original_action:
                    target_armature.animation_data.action = original_action
                    original_slot = find_slot(original_action, original_slot_handle)
                    if original_slot is not None:
                        target_armature.animation_data.action_slot = original_slot
                if original_area_type and area:
                    area.type = original_area_type
            except:
                pass

            return None

    def apply_animation_from_blend_file(self, target_armature, blend_file_path, frame_start, frame_end, animation_name=None, apply_mode='NEW', apply_selected_bones_only=False, selected_bones=None, use_slots=False, mirror_animation=False, reverse_animation=False, rig_type='rigify', animation_metadata=None, primary_slot_identifier=None, slot_mode='active'):
        """Apply animation by loading action from blend file, optionally filtering to selected bones and using slots

        Args:
            animation_metadata: Optional dict with library tracking info:
                - uuid: Animation UUID
                - version_group_id: Version group for linking versions
                - version: Version number (1, 2, 3...)
                - version_label: Human-readable version (v001, v002...)
                - name: Animation name
                - rig_type: Rig type
            primary_slot_identifier: The slot the capture marked as the one
                to play (library JSON). None for files saved before slot
                support - the slot is then picked by pick_slot_for_rig().
            slot_mode: 'all' for an "All Slots" library entry, else 'active'
        """
        try:
            # Validate slot support if requested
            if use_slots:
                if not hasattr(bpy.types, 'ActionSlot'):
                    logger.warning("Animation slots are not supported in this Blender version (requires 4.5+). Falling back to standard mode.")
                    use_slots = False
                else:
                    logger.debug("Slot mode enabled and supported")

            # Load actions from the blend file
            with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
                # Load all actions from the file
                data_to.actions = data_from.actions

            if not data_to.actions:
                logger.error("No actions found in blend file")
                return False

            # Apply the first action (our saved action)
            source_action = data_to.actions[0]

            # Rename action to the user-friendly animation name
            if animation_name:
                source_action.name = animation_name

            # Which of the file's slots this rig plays. Files saved before slot
            # support can hold several, including other objects' animation.
            source_slot = pick_slot_for_rig(source_action, target_armature, primary_slot_identifier)
            if source_slot is None:
                logger.error(f"Action '{source_action.name}' has no slot an object can play")
                bpy.data.actions.remove(source_action)
                return False
            if len(source_action.slots) > 1:
                logger.info(f"Action '{source_action.name}' has {len(source_action.slots)} slots - playing '{source_slot.name_display}'")

            # Mirror the action if requested
            if mirror_animation:
                logger.info(f"Mirroring Action with rig type: {rig_type}")
                mirrored_action = self.mirror_action(source_action, rig_type, target_armature, source_slot)

                if mirrored_action:
                    # Remove original action and use mirrored version. Only the
                    # playing slot is mirrored (animation_slots_spec.md Q3).
                    bpy.data.actions.remove(source_action)
                    source_action = mirrored_action
                    source_slot = pick_slot_for_rig(source_action, target_armature)
                    logger.info("Successfully created mirrored Action")
                else:
                    logger.warning("Failed to mirror Action - Action may not support mirroring. Applying original Action instead.")
                    # Continue with original action

            # The range of the slot that will play. The JSON's range is the
            # same for new captures, but for older multi-slot files it was
            # always the first slot's.
            slot_start, slot_end = get_action_keyframe_range(source_action, source_slot)
            if slot_start is not None:
                frame_start, frame_end = slot_start, slot_end

            # Create animation data if it doesn't exist
            if not target_armature.animation_data:
                target_armature.animation_data_create()

            # Bones to apply (only those on this rig), or None for all
            bones = None
            if apply_selected_bones_only and selected_bones:
                bones = {b for b in selected_bones if b in target_armature.pose.bones}
                logger.debug(f"Filtering to selected bones: {bones}")

            # Handle different apply modes
            if apply_mode == 'INSERT':
                # INSERT mode: Merge keyframes into existing action at playhead
                return self.insert_animation_at_playhead(
                    target_armature,
                    source_action,
                    source_slot,
                    frame_start,
                    frame_end,
                    apply_selected_bones_only,
                    selected_bones,
                    use_slots,
                    reverse_animation
                )

            # NEW mode: add to the rig's action as new slot(s), or replace it
            if use_slots:
                if self._add_as_new_slots(target_armature, source_action, source_slot,
                                          animation_name, bones, reverse_animation):
                    # Remove source action as we've copied what we need
                    bpy.data.actions.remove(source_action)
                else:
                    logger.warning("Slot mode failed, using standard NEW mode")
                    use_slots = False

            if not use_slots:
                # Standard NEW mode: Replace with new action, filtered to the
                # selected bones and/or reversed if requested
                primary_identifier = source_slot.identifier
                action_to_apply = source_action
                if bones is not None or reverse_animation:
                    derived = derive_action(source_action, source_action.name,
                                            bones=bones, reverse=reverse_animation)
                    if derived:
                        name = source_action.name
                        bpy.data.actions.remove(source_action)
                        derived.name = name
                        action_to_apply = derived
                    else:
                        logger.warning("Nothing left after filtering to the selected bones - applying the whole Action")

                target_armature.animation_data.action = action_to_apply
                # Assigning an action doesn't reliably pick the right slot
                # (Blender matches by the rig's last slot name) - set it.
                target_armature.animation_data.action_slot = pick_slot_for_rig(
                    action_to_apply, target_armature, primary_identifier)

            # Force viewport and animation update
            bpy.context.view_layer.update()
            bpy.context.scene.frame_set(bpy.context.scene.frame_current)

            # Ensure armature is in pose mode for Action
            # if bpy.context.active_object == target_armature and bpy.context.mode != 'POSE':
            #     bpy.ops.object.mode_set(mode='POSE')

            # Don't modify scene timeline at all when applying Actions
            # The user's cinematic timeline should remain untouched
            scene = bpy.context.scene

            # Store library metadata for version tracking
            if animation_metadata:
                current_action = target_armature.animation_data.action
                if current_action and slot_mode == 'all':
                    # An "All Slots" entry is tracked as a bundle - but only when
                    # the rig now plays the library action itself. Added as
                    # slots, it's merged into the rig's own action, which as a
                    # whole isn't that library animation.
                    if not use_slots:
                        set_bundle_tracking(current_action, library_tracking_from_metadata(animation_metadata))
                        logger.debug(f"Stored bundle library metadata on action '{current_action.name}'")
                elif current_action:
                    self._store_library_metadata(current_action, get_active_slot(target_armature), animation_metadata)
                    logger.debug(f"Stored library metadata on action '{current_action.name}'")

            logger.info(f"Applied Action from {blend_file_path}")
            return True

        except Exception as e:
            logger.error(f"Error applying Action from blend file: {e}")
            return False

    def _add_as_new_slots(self, target_armature, source_action, source_slot, animation_name, bones, reverse):
        """
        Add a library action to the rig's action as new slot(s) and play it.

        The playing slot is always added. Any other slot of the library
        action is added too if every bone it animates is on this rig (a
        multi-slot capture); other objects' slots never are.

        Returns:
            True if at least one slot was added and made active
        """
        current_action = target_armature.animation_data.action
        if not current_action:
            # No action exists, create a persistent shared action
            action_name = f"{target_armature.name}_SlottedActions"
            current_action = bpy.data.actions.new(name=action_name)
            target_armature.animation_data.action = current_action
            logger.info(f"Created persistent action '{action_name}' for slot-based Actions")

        to_add = [source_slot] + [
            s for s in source_action.slots
            if s.handle != source_slot.handle and is_object_slot(s)
            and slot_matches_rig(source_action, s, target_armature)
        ]
        display_name = animation_name or source_action.name

        added = []
        primary_new = None
        for src_slot in to_add:
            if len(to_add) == 1:
                slot_name = f"{display_name}_slot_{len(current_action.slots) + 1}"
            else:
                slot_name = f"{display_name}_{src_slot.name_display}"

            # Blender auto-creates an empty first slot - reuse it rather than
            # leaving it behind
            reused = (not added and len(current_action.slots) > 0
                      and not get_action_fcurves(current_action, current_action.slots[0]))
            try:
                if reused:
                    dst_slot = current_action.slots[0]
                    dst_slot.name_display = slot_name
                else:
                    dst_slot = current_action.slots.new('OBJECT', slot_name)
                count = copy_slot(source_action, src_slot, current_action, dst_slot,
                                  bones=bones, reverse=reverse)
            except Exception as e:
                logger.error(f"Failed to add slot '{slot_name}': {e}")
                logger.error(traceback.format_exc())
                continue

            if count == 0:
                logger.warning(f"No fcurves copied for slot '{slot_name}' (all filtered out?)")
                if not reused:
                    current_action.slots.remove(dst_slot)
                continue

            added.append(dst_slot)
            if src_slot.handle == source_slot.handle:
                primary_new = dst_slot
            logger.info(f"Created slot '{dst_slot.name_display}' with {count} fcurves")

        if not added:
            return False

        # Set the new slot as active
        target_armature.animation_data.action_slot = primary_new or added[0]
        return True

    def _store_library_metadata(self, action, slot, metadata):
        """Store library tracking metadata for one slot of an action

        This allows the capture operator to detect that the slot came from
        the library and offer versioning options.

        Args:
            action: Blender action to store metadata on
            slot: The slot the library animation now lives in
            metadata: Dict with uuid, version_group_id, version, version_label, name, rig_type
        """
        set_library_tracking(action, slot, library_tracking_from_metadata(metadata))
    
    def insert_animation_at_playhead(self, target_armature, source_action, source_slot, frame_start, frame_end, apply_selected_bones_only=False, selected_bones=None, use_slots=False, reverse_animation=False):
        """Insert one slot of source_action into the rig's active slot at the playhead"""
        try:
            scene = bpy.context.scene

            # Get or create action
            existing_action = target_armature.animation_data.action
            if not existing_action:
                # No existing action, create new one.
                #
                # A bare bpy.data.actions.new() has no layer, strip or slot. On
                # Blender 5.0+ new_action_fcurve() needs all three to place an
                # fcurve, so without this every fcurve came back None and the
                # whole insert failed - leaving an empty, slotless action that
                # drives nothing. Applying "At Playhead" onto a rig with no
                # action at all hit this every time.
                logger.debug("INSERT mode: No existing action, creating new action")
                existing_action = bpy.data.actions.new(name=f"Inserted_{source_action.name}")
                target_armature.animation_data.action = existing_action

                from ..utils.utils import init_action_for_blender_5
                new_slot = init_action_for_blender_5(
                    existing_action, slot_name=f"Slot_{int(time.time())}"
                )
                if new_slot:
                    # Bind the slot, or the action still won't drive the rig.
                    # Picked up below as active_slot, so no duplicate is made.
                    try:
                        target_armature.animation_data.action_slot = new_slot
                        logger.debug(f"INSERT mode: bound new slot '{new_slot.name_display}'")
                    except Exception as e:
                        logger.warning(f"Could not bind action slot: {e}")
            else:
                logger.debug(f"INSERT mode: Inserting into existing action '{existing_action.name}'")

            # Calculate frame offset based on playhead position
            current_frame = scene.frame_current
            frame_offset = current_frame - frame_start

            logger.debug(f"INSERT mode: Playhead at frame {current_frame}, offset: {frame_offset}")
            logger.debug(f"INSERT mode: Source Action frames {frame_start} to {frame_end}")

            # Keys go into the slot the rig is playing, whether or not "use
            # slots" is on - inserting into the action's first slot instead
            # put them somewhere the rig wasn't looking.
            target_slot = get_active_slot(target_armature)
            if target_slot is None:
                slot_name = f"Slot_{int(time.time())}"
                # Blender 4.4+ requires id_type parameter: slots.new(id_type, name)
                target_slot = existing_action.slots.new('OBJECT', slot_name)
                target_armature.animation_data.action_slot = target_slot
                logger.debug(f"INSERT mode: rig had no slot, created '{slot_name}'")
            logger.debug(f"INSERT mode: Inserting '{source_slot.name_display}' into slot '{target_slot.name_display}'")

            # Filter bones if needed
            bones_to_apply = None
            if apply_selected_bones_only and selected_bones:
                bones_to_apply = set(selected_bones)
                logger.debug(f"INSERT mode: Filtering to selected bones: {bones_to_apply}")

            # ========== ROOT MOTION CONTINUITY LOGIC ==========
            # Calculate root bone offsets for location and rotation if feature is enabled
            root_loc_offsets = [0.0, 0.0, 0.0]  # Location X, Y, Z offsets
            root_rot_euler_offsets = [0.0, 0.0, 0.0]  # Euler rotation X, Y, Z offsets
            delta_quat = None  # Quaternion delta for proper quaternion composition
            root_bone_name = scene.animlib_root_bone_name
            enable_root_continuity = scene.animlib_enable_root_motion_continuity
            enable_rotation_continuity = scene.animlib_root_motion_rotation

            if enable_root_continuity and root_bone_name:
                logger.debug(f"Root motion continuity enabled for bone: {root_bone_name}")

                # Get the frame just before insertion point for sampling previous animation end
                previous_frame = current_frame - 1

                # Get location axis settings
                loc_axes = [
                    scene.animlib_root_motion_loc_x,
                    scene.animlib_root_motion_loc_y,
                    scene.animlib_root_motion_loc_z
                ]

                # Build the data paths for the root bone
                root_location_path = f'pose.bones["{root_bone_name}"].location'
                root_euler_path = f'pose.bones["{root_bone_name}"].rotation_euler'
                root_quat_path = f'pose.bones["{root_bone_name}"].rotation_quaternion'

                # Calculate LOCATION offsets for each enabled axis (addition works for location)
                for axis_index in range(3):  # 0=X, 1=Y, 2=Z
                    if not loc_axes[axis_index]:
                        continue  # Skip disabled axes

                    axis_name = ['X', 'Y', 'Z'][axis_index]

                    # Get previous animation's end position for this axis
                    existing_fcurve = find_action_fcurve(existing_action, root_location_path, index=axis_index, slot=target_slot)
                    if existing_fcurve:
                        previous_value = existing_fcurve.evaluate(previous_frame)
                    else:
                        previous_value = 0.0
                        logger.debug(f"No existing location {axis_name} fcurve for root bone, using 0.0")

                    # Get source animation's start position for this axis
                    source_fcurve = find_action_fcurve(source_action, root_location_path, index=axis_index, slot=source_slot)
                    if source_fcurve:
                        source_start_value = source_fcurve.evaluate(frame_start)
                    else:
                        source_start_value = 0.0
                        logger.debug(f"No source location {axis_name} fcurve for root bone, using 0.0")

                    # Calculate offset to align source start with previous end
                    root_loc_offsets[axis_index] = previous_value - source_start_value

                    logger.info(f"Root location {axis_name} offset: {root_loc_offsets[axis_index]:.3f} (prev: {previous_value:.3f}, src: {source_start_value:.3f})")

                # Calculate ROTATION offsets if rotation continuity is enabled
                if enable_rotation_continuity:
                    # Check if source uses quaternion or euler rotation
                    has_quat_fcurves = any(find_action_fcurve(source_action, root_quat_path, i, slot=source_slot) for i in range(4))
                    has_euler_fcurves = any(find_action_fcurve(source_action, root_euler_path, i, slot=source_slot) for i in range(3))

                    if has_quat_fcurves:
                        # QUATERNION: Use proper quaternion multiplication
                        # delta = prev @ src.inverted() so that delta @ src = prev
                        prev_quat = get_quaternion_at_frame(existing_action, root_bone_name, previous_frame, target_slot)
                        src_quat = get_quaternion_at_frame(source_action, root_bone_name, frame_start, source_slot)
                        delta_quat = prev_quat @ src_quat.inverted()

                        logger.info(f"Root quaternion delta computed: {delta_quat}")
                        logger.debug(f"  prev_quat at frame {previous_frame}: {prev_quat}")
                        logger.debug(f"  src_quat at frame {frame_start}: {src_quat}")

                    elif has_euler_fcurves:
                        # EULER: Simple addition works for euler angles
                        for axis_index in range(3):  # 0=X, 1=Y, 2=Z
                            axis_name = ['X', 'Y', 'Z'][axis_index]

                            # Get previous animation's end rotation for this axis
                            existing_fcurve = find_action_fcurve(existing_action, root_euler_path, index=axis_index, slot=target_slot)
                            if existing_fcurve:
                                previous_value = existing_fcurve.evaluate(previous_frame)
                            else:
                                previous_value = 0.0

                            # Get source animation's start rotation for this axis
                            source_fcurve = find_action_fcurve(source_action, root_euler_path, index=axis_index, slot=source_slot)
                            if source_fcurve:
                                source_start_value = source_fcurve.evaluate(frame_start)
                            else:
                                source_start_value = 0.0

                            # Calculate offset
                            root_rot_euler_offsets[axis_index] = previous_value - source_start_value

                            if root_rot_euler_offsets[axis_index] != 0.0:
                                logger.info(f"Root euler {axis_name} offset: {root_rot_euler_offsets[axis_index]:.3f}")

            # ========== END ROOT MOTION LOGIC ==========

            # Copy fcurves from source action to existing action with offset
            copied_count = 0
            for source_fcurve in get_action_fcurves(source_action, source_slot):
                # Check if this fcurve affects a bone we want to apply
                if bones_to_apply:
                    # Extract bone name from data_path like 'pose.bones["BoneName"].location'
                    if 'pose.bones[' in source_fcurve.data_path:
                        bone_name = source_fcurve.data_path.split('"')[1]
                        if bone_name not in bones_to_apply:
                            continue  # Skip this bone

                # Find or create matching fcurve in existing action
                existing_fcurve = find_action_fcurve(existing_action, source_fcurve.data_path, index=source_fcurve.array_index, slot=target_slot)
                if not existing_fcurve:
                    existing_fcurve = new_action_fcurve(existing_action, source_fcurve.data_path, index=source_fcurve.array_index, slot=target_slot)

                    if not existing_fcurve:
                        # Couldn't create the channel - skip it rather than
                        # crashing the whole insert on a None further down, and
                        # name the channel so the cause is findable.
                        logger.warning(
                            f"INSERT mode: could not create fcurve for "
                            f"{source_fcurve.data_path}[{source_fcurve.array_index}] - skipping"
                        )
                        continue

                # ========== CHECK IF THIS IS ROOT BONE LOCATION OR ROTATION FCURVE ==========
                # Determine if we need to apply root motion offset to this fcurve
                apply_loc_offset = False
                apply_euler_offset = False
                apply_quat_delta = False
                root_offset_value = 0.0

                if enable_root_continuity and root_bone_name:
                    bone_name = extract_bone_name_from_data_path(source_fcurve.data_path)
                    if bone_name == root_bone_name:
                        axis_index = source_fcurve.array_index
                        if '.location' in source_fcurve.data_path:
                            # This is a root bone location fcurve - use addition
                            if axis_index < 3 and root_loc_offsets[axis_index] != 0.0:
                                apply_loc_offset = True
                                root_offset_value = root_loc_offsets[axis_index]
                                logger.debug(f"Applying location offset {root_offset_value:.3f} to {bone_name}.location[{axis_index}]")
                        elif '.rotation_euler' in source_fcurve.data_path:
                            # This is a root bone euler rotation fcurve - use addition
                            if axis_index < 3 and root_rot_euler_offsets[axis_index] != 0.0:
                                apply_euler_offset = True
                                root_offset_value = root_rot_euler_offsets[axis_index]
                                logger.debug(f"Applying euler offset {root_offset_value:.3f} to {bone_name}.rotation_euler[{axis_index}]")
                        elif '.rotation_quaternion' in source_fcurve.data_path and delta_quat is not None:
                            # This is a root bone quaternion fcurve - use quaternion multiplication
                            apply_quat_delta = True
                            logger.debug(f"Will apply quaternion delta to {bone_name}.rotation_quaternion[{axis_index}]")

                # Copy keyframes with frame offset and optional reversal
                for keyframe in source_fcurve.keyframe_points:
                    if reverse_animation:
                        # Simply reverse: first frame becomes last, last becomes first
                        reversed_frame = frame_end - (keyframe.co.x - frame_start)
                        new_frame = reversed_frame + frame_offset
                    else:
                        new_frame = keyframe.co.x + frame_offset

                    # Determine the value to insert
                    value = keyframe.co.y

                    if apply_loc_offset or apply_euler_offset:
                        # Location and Euler: simple addition works
                        value += root_offset_value
                    elif apply_quat_delta:
                        # Quaternion: use proper quaternion multiplication
                        # Read the full quaternion at this keyframe's time from source
                        keyframe_time = keyframe.co.x
                        original_quat = get_quaternion_at_frame(source_action, root_bone_name, keyframe_time, source_slot)
                        # Apply the delta rotation: new_quat = delta @ original
                        new_quat = delta_quat @ original_quat
                        # Extract the component for this fcurve (array_index: 0=W, 1=X, 2=Y, 3=Z)
                        value = new_quat[source_fcurve.array_index]

                    new_kf = existing_fcurve.keyframe_points.insert(new_frame, value)

                    # Carry the SOURCE's curve shape across.
                    #
                    # insert() only stores frame + value. Everything else is
                    # taken from the preceding key in the destination channel -
                    # or, when that channel is empty, from Blender's "Default
                    # Interpolation" preference. That's why applying at the
                    # playhead onto a rig with no action smoothed out stepped
                    # blocking, while doing it after another apply looked fine:
                    # it was inheriting, never preserving.
                    if new_kf is not None:
                        try:
                            new_kf.interpolation = keyframe.interpolation
                            new_kf.easing = keyframe.easing
                            new_kf.type = keyframe.type
                            new_kf.amplitude = keyframe.amplitude
                            new_kf.back = keyframe.back
                            new_kf.period = keyframe.period

                            # Handles are ABSOLUTE positions, so they have to
                            # travel with the key: the same frame offset, plus
                            # the same value delta when the value was changed
                            # (root-motion continuity).
                            dy = value - keyframe.co.y
                            if reverse_animation:
                                # Time is mirrored, so handles swap sides too.
                                def _map_x(hx):
                                    return (frame_end - (hx - frame_start)) + frame_offset
                                l_type = keyframe.handle_right_type
                                r_type = keyframe.handle_left_type
                                l_pos = (_map_x(keyframe.handle_right.x),
                                         keyframe.handle_right.y + dy)
                                r_pos = (_map_x(keyframe.handle_left.x),
                                         keyframe.handle_left.y + dy)
                            else:
                                l_type = keyframe.handle_left_type
                                r_type = keyframe.handle_right_type
                                l_pos = (keyframe.handle_left.x + frame_offset,
                                         keyframe.handle_left.y + dy)
                                r_pos = (keyframe.handle_right.x + frame_offset,
                                         keyframe.handle_right.y + dy)

                            # Types before positions: AUTO/VECTOR recompute
                            # their own positions, FREE/ALIGNED keep what we set.
                            new_kf.handle_left_type = l_type
                            new_kf.handle_right_type = r_type
                            new_kf.handle_left = l_pos
                            new_kf.handle_right = r_pos
                        except Exception as e:
                            # Curve shape is a refinement - never lose the
                            # keyframe itself over it.
                            logger.debug(f"Could not copy curve shape: {e}")

                    copied_count += 1

                # Update fcurve
                existing_fcurve.update()

            logger.info(f"INSERT mode: Copied {copied_count} keyframes with offset {frame_offset}")

            # Remove the source action since we've copied what we need
            bpy.data.actions.remove(source_action)

            # Force viewport update
            bpy.context.view_layer.update()
            bpy.context.scene.frame_set(bpy.context.scene.frame_current)

            return True

        except Exception as e:
            logger.error(f"Error inserting Action at playhead: {e}")
            traceback.print_exc()
            return False

class ANIMLIB_OT_check_apply_queue(Operator):
    """Check for pending Action apply requests and version requests from desktop app"""
    bl_idname = "animlib.check_apply_queue"
    bl_label = "Check Apply Queue"
    bl_description = "Check for Actions queued for application from desktop app"

    def execute(self, context):
        try:
            # Get pending apply requests from queue client
            pending_files = animation_queue_client.get_pending_apply_requests()

            if not pending_files:
                self.report({'INFO'}, "No pending apply requests")
                return {'FINISHED'}

            # Process the oldest pending request first (FIFO; queue_client sorts
            # oldest-first) so rapid successive applies run in submission order.
            request_file = pending_files[0]

            # Read request data using queue client
            request_data = animation_queue_client.read_request(request_file)

            if not request_data or request_data.get('status') != 'pending':
                # Unreadable, or already handled. Leaving it on disk meant the
                # 10Hz poll re-read it forever.
                animation_queue_client.mark_request_completed(request_file)
                self.report({'INFO'}, "Discarded a stale queue request")
                return {'FINISHED'}

            # Check request type - pose or animation
            request_type = request_data.get('type', 'animation')

            if request_type == 'pose':
                # Handle pose apply request
                return self._apply_pose_request(context, request_data, request_file)

            # Apply the animation
            animation_id = request_data.get('animation_id')
            animation_name = request_data.get('animation_name', 'Unknown')

            # Get options from queue (sent by desktop app)
            options = request_data.get('options', {})
            apply_mode = options.get('apply_mode', 'NEW')
            mirror = options.get('mirror', False)
            reverse = options.get('reverse', False)
            use_slots = options.get('use_slots', False)
            selected_bones_only_option = options.get('selected_bones_only', False)

            logger.debug(f"Queue options: mode={apply_mode}, mirror={mirror}, reverse={reverse}, slots={use_slots}, bones_only={selected_bones_only_option}")

            # Handle selected bones only option
            apply_selected_bones_only = selected_bones_only_option
            selected_bones = []

            if apply_selected_bones_only:
                # Get currently selected bones if in pose mode
                armature = context.active_object
                if armature and armature.type == 'ARMATURE' and context.mode == 'POSE':
                    selected_bones = [bone.name for bone in context.selected_pose_bones]
                    if not selected_bones:
                        self.report({'WARNING'}, "No bones selected! Applying to all bones.")
                        apply_selected_bones_only = False
                else:
                    self.report({'WARNING'}, "Not in pose mode or no armature selected! Applying to all bones.")
                    apply_selected_bones_only = False

                if selected_bones:
                    self.report({'INFO'}, f"Applying to {len(selected_bones)} selected bones: {', '.join(selected_bones[:3])}{'...' if len(selected_bones) > 3 else ''}")

            # Apply animation with options from desktop app queue
            bpy.ops.animlib.apply_animation(
                animation_id=animation_id,
                apply_selected_bones_only=apply_selected_bones_only,
                selected_bones_list=','.join(selected_bones) if selected_bones else '',
                apply_mode=apply_mode,
                use_slots=use_slots,
                mirror_animation=mirror,
                reverse_animation=reverse,
                options_from_queue=True  # Signal that options come from queue
            )
            
            # Mark request as completed using queue client
            animation_queue_client.mark_request_completed(request_file)

            self.report({'INFO'}, f"Applied queued Action: {animation_name}")

        except Exception as e:
            # Consume the request even though it failed. This used to fall
            # through with the file still on disk, so the 10Hz poll re-ran the
            # apply operator forever - stomping the user's pose on every tick
            # and making the rig look permanently locked. The queue file lives
            # in the library, so it survived restarts too: disabling the addon
            # "fixed" it only because that stopped the timer.
            # The pose path already did this on every failure branch.
            try:
                animation_queue_client.mark_request_completed(request_file)
            except Exception:
                pass
            self.report({'ERROR'}, f"Error checking apply queue: {str(e)}")

        return {'FINISHED'}

    def _apply_pose_request(self, context, request_data, request_file):
        """
        Apply a pose request from the desktop app queue.

        Poses are single-frame actions. We apply them instantly by loading the action
        and using apply_pose_from_action() for immediate application.

        Args:
            context: Blender context
            request_data: Request data dict from queue file
            request_file: Path to the queue file

        Returns:
            Operator result ('FINISHED' or 'CANCELLED')
        """
        try:
            armature = context.active_object

            # Validate armature selection
            if not armature or armature.type != 'ARMATURE':
                self.report({'ERROR'}, "Please select an armature object")
                animation_queue_client.mark_request_completed(request_file)
                return {'CANCELLED'}

            pose_id = request_data.get('animation_id') or request_data.get('pose_id')
            pose_name = request_data.get('animation_name') or request_data.get('pose_name', 'Unknown Pose')

            # Resolve the pose blend by UUID from the local library first, so it
            # works after a rename and on machines with a different drive letter.
            # The path the desktop app sent (request_data['blend_file_path']) is an
            # absolute path with the sender's drive letter, so it is only a fallback.
            blend_file_path = request_data.get('blend_file_path')
            if pose_id:
                try:
                    local_lib = get_library_path()
                    if local_lib:
                        _pj, _folder = _find_asset_by_uuid(local_lib, pose_id)
                        local_blend = _blend_from_folder(_folder)
                        if local_blend:
                            blend_file_path = local_blend
                except Exception as e:
                    logger.debug(f"Pose UUID resolution failed, using sent path: {e}")

            if not blend_file_path or not os.path.exists(blend_file_path):
                self.report({'ERROR'}, f"Pose blend file not found: {blend_file_path}")
                animation_queue_client.mark_request_completed(request_file)
                return {'CANCELLED'}

            logger.info(f"Applying pose: {pose_name} from {blend_file_path}")

            # Load the pose action from blend file
            with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
                data_to.actions = data_from.actions

            if not data_to.actions:
                self.report({'ERROR'}, "No actions found in pose file")
                animation_queue_client.mark_request_completed(request_file)
                return {'CANCELLED'}

            pose_action = data_to.actions[0]

            # Ensure armature has pose data
            if not armature.pose:
                self.report({'ERROR'}, "Armature has no pose data")
                bpy.data.actions.remove(pose_action)
                animation_queue_client.mark_request_completed(request_file)
                return {'CANCELLED'}

            # Apply the pose using Blender's built-in method (instant application)
            # This applies all transforms from the action at frame 0
            try:
                armature.pose.apply_pose_from_action(pose_action, evaluation_time=0.0)
                logger.info(f"Applied pose using apply_pose_from_action()")
            except AttributeError:
                # Fallback for older Blender versions: manually apply transforms
                logger.debug("apply_pose_from_action not available, using manual method")
                self._apply_pose_manually(armature, pose_action)

            # Clean up - remove the loaded action
            bpy.data.actions.remove(pose_action)

            # Force viewport update
            bpy.context.view_layer.update()

            # Mark request as completed
            animation_queue_client.mark_request_completed(request_file)

            self.report({'INFO'}, f"Applied pose: {pose_name}")
            return {'FINISHED'}

        except Exception as e:
            logger.error(f"Error applying pose: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error applying pose: {str(e)}")
            animation_queue_client.mark_request_completed(request_file)
            return {'CANCELLED'}

    def _apply_pose_manually(self, armature, pose_action):
        """
        Manually apply pose transforms from an action (fallback method).

        Args:
            armature: Target armature object
            pose_action: Blender action containing pose keyframes
        """
        for fcurve in get_action_fcurves(pose_action):
            if not fcurve.keyframe_points:
                continue

            # Get the value at frame 0
            value = fcurve.evaluate(0)

            # Parse the data path to get bone and property
            data_path = fcurve.data_path
            if 'pose.bones[' not in data_path:
                continue

            try:
                # Extract bone name: pose.bones["BoneName"].location
                bone_name = data_path.split('"')[1]

                if bone_name not in armature.pose.bones:
                    continue

                pose_bone = armature.pose.bones[bone_name]

                # Extract property name and set value
                if '.location' in data_path:
                    pose_bone.location[fcurve.array_index] = value
                elif '.rotation_quaternion' in data_path:
                    pose_bone.rotation_quaternion[fcurve.array_index] = value
                elif '.rotation_euler' in data_path:
                    pose_bone.rotation_euler[fcurve.array_index] = value
                elif '.scale' in data_path:
                    pose_bone.scale[fcurve.array_index] = value
            except (IndexError, KeyError) as e:
                logger.debug(f"Could not apply fcurve {data_path}: {e}")


# ==================== AUTO-POLLING TIMER ====================

# Global flag to track if timer is running
_queue_poll_timer_running = False
_POLL_INTERVAL = 0.1        # responsive, while the app is connected
# Waiting on the user (no rig selected, no 3D viewport). Retrying ten times a
# second changes nothing and keeps the main thread busy while they work.
_POLL_BLOCKED_INTERVAL = 1.0
# An apply request nobody can satisfy is abandoned rather than retried forever.
_REQUEST_MAX_AGE_SECONDS = 120
_POLL_IDLE_INTERVAL = 1.0   # no app connected - nothing can enqueue work


def _discard_stale_requests(pending_files):
    """Delete apply requests older than _REQUEST_MAX_AGE_SECONDS."""
    import time as _time
    now = _time.time()
    for request_file in pending_files:
        try:
            if now - request_file.stat().st_mtime > _REQUEST_MAX_AGE_SECONDS:
                request_file.unlink()
                logger.warning(
                    f"Discarded stale apply request (older than "
                    f"{_REQUEST_MAX_AGE_SECONDS}s): {request_file.name}")
        except OSError:
            pass


def _auto_poll_queue():
    """
    Timer callback that automatically checks for and applies queued animations.
    Uses temp_override to provide proper context for operator calls (Blender 4.0+).
    """
    global _queue_poll_timer_running

    if not _queue_poll_timer_running:
        return None  # Stop timer

    try:
        # Quick check for pending files (cheap operation)
        pending_files = animation_queue_client.get_pending_apply_requests()

        if not pending_files:
            # Only the desktop app writes to this queue. With none connected,
            # polling the library folder 10x a second buys nothing - and on a
            # shared drive each of those is a network round-trip on the main
            # thread. A connecting app restores the fast rate on the next tick.
            try:
                from ..utils.socket_server import get_connected_clients_count
                if get_connected_clients_count() == 0:
                    return _POLL_IDLE_INTERVAL
            except Exception:
                pass
            return _POLL_INTERVAL  # Nothing to do

        logger.debug(f"Found {len(pending_files)} pending queue file(s)")

        # Abandon anything too old to still be wanted. Every 'can't act on this
        # yet' path below leaves the file in place on purpose (the user may be
        # about to select a rig), so without an upper bound a request that can
        # NEVER be satisfied is retried for the life of the session.
        _discard_stale_requests(pending_files)

        # Get window manager and check for windows
        wm = bpy.context.window_manager
        if not wm.windows:
            logger.debug("No windows available")
            return _POLL_BLOCKED_INTERVAL

        window = wm.windows[0]

        # Find a VIEW_3D area for context
        area = None
        for a in window.screen.areas:
            if a.type == 'VIEW_3D':
                area = a
                break

        if not area:
            logger.debug("No VIEW_3D area found")
            return _POLL_BLOCKED_INTERVAL

        # Find a region in the area
        region = None
        for r in area.regions:
            if r.type == 'WINDOW':
                region = r
                break

        # Get the active object from view layer (this persists even in timer context)
        view_layer = window.view_layer
        active_object = view_layer.objects.active

        if not active_object or active_object.type != 'ARMATURE':
            logger.debug(f"No armature selected (active: {active_object})")
            return _POLL_BLOCKED_INTERVAL

        logger.info(f"Auto-applying animation to: {active_object.name}")

        # Use temp_override to call operator with proper context including active object
        with bpy.context.temp_override(window=window, area=area, region=region, object=active_object):
            # Now we have proper context - call check_apply_queue operator
            bpy.ops.animlib.check_apply_queue()

    except Exception as e:
        logger.error(f"Error in auto-poll timer: {e}")
        import traceback
        traceback.print_exc()

    return _POLL_INTERVAL  # Continue polling


def start_queue_poll_timer():
    """Start the auto-polling timer"""
    global _queue_poll_timer_running

    if _queue_poll_timer_running:
        return  # Already running

    _queue_poll_timer_running = True

    # Refresh queue directory now that preferences are loaded
    animation_queue_client.refresh_queue_dir()

    # Register the timer if not already registered
    # Use 2.0 second delay to ensure Blender is fully initialized
    if not bpy.app.timers.is_registered(_auto_poll_queue):
        bpy.app.timers.register(_auto_poll_queue, first_interval=2.0)
        logger.info("Queue poll timer started")


def stop_queue_poll_timer():
    """Stop the auto-polling timer"""
    global _queue_poll_timer_running

    _queue_poll_timer_running = False

    # Unregister the timer if registered
    if bpy.app.timers.is_registered(_auto_poll_queue):
        bpy.app.timers.unregister(_auto_poll_queue)
        logger.info("Queue poll timer stopped")
