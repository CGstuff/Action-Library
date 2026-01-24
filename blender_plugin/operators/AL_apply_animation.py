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
    get_action_fcurves, find_action_fcurve, new_action_fcurve
)
from ..preferences.AL_preferences import get_library_path

# Initialize logger
logger = get_logger()


def get_quaternion_at_frame(action, bone_name, frame):
    """
    Read all 4 quaternion components from fcurves at a given frame.

    Args:
        action: Blender action to read from
        bone_name: Name of the bone
        frame: Frame number to evaluate at

    Returns:
        mathutils.Quaternion with the rotation at that frame
    """
    from mathutils import Quaternion

    quat_path = f'pose.bones["{bone_name}"].rotation_quaternion'
    components = [1.0, 0.0, 0.0, 0.0]  # Default quaternion (identity): W=1, X=0, Y=0, Z=0

    for i in range(4):
        fcurve = find_action_fcurve(action, quat_path, index=i)
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
            
            # Get blend file path
            blend_file_path = animation.get('blend_file_path')
            if not blend_file_path or not os.path.exists(blend_file_path):
                self.report({'ERROR'}, f"Action blend file not found: {blend_file_path}")
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
                animation_metadata=animation_metadata
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

    def mirror_action(self, source_action, rig_type, target_armature):
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
        try:
            logger.info("Starting mirror operation using Blender's native paste flipped")

            # Store original context
            original_action = target_armature.animation_data.action if target_armature.animation_data else None
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

            # Temporarily apply source action
            target_armature.animation_data.action = source_action

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
            frame_start, frame_end = get_action_keyframe_range(source_action)

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
                if original_area_type and area:
                    area.type = original_area_type
            except:
                pass

            return None

    def reverse_action(self, source_action, frame_start, frame_end):
        """
        Create a reversed version of an action.

        Args:
            source_action: Source action to reverse
            frame_start: First frame of animation
            frame_end: Last frame of animation

        Returns:
            Reversed action or None if reversing fails
        """
        from ..utils.utils import BLENDER_5_0_OR_LATER, init_action_for_blender_5

        try:
            logger.info(f"Reversing action '{source_action.name}' (frames {frame_start}-{frame_end})")

            # Create new action for reversed animation
            reversed_action = bpy.data.actions.new(name=f"{source_action.name}_reversed")

            # For Blender 5.0+, initialize the action with proper layer/strip/slot structure
            slot = None
            if BLENDER_5_0_OR_LATER:
                slot = init_action_for_blender_5(reversed_action, slot_name="Reversed")
                if not slot:
                    logger.error("Failed to initialize action for Blender 5.0")

            # Copy fcurves with reversed keyframe positions
            copied_count = 0
            for fcurve in get_action_fcurves(source_action):
                new_fcurve = new_action_fcurve(
                    reversed_action,
                    fcurve.data_path,
                    index=fcurve.array_index,
                    slot=slot
                )

                if new_fcurve is None:
                    logger.warning(f"Failed to create fcurve for {fcurve.data_path}")
                    continue

                # Copy keyframes with reversed frame positions
                for keyframe in fcurve.keyframe_points:
                    reversed_frame = frame_end - (keyframe.co[0] - frame_start)
                    new_fcurve.keyframe_points.insert(reversed_frame, keyframe.co[1])

                new_fcurve.update()
                copied_count += 1

            logger.info(f"Created reversed action with {copied_count} fcurves")
            return reversed_action

        except Exception as e:
            logger.error(f"Error reversing action: {e}")
            import traceback
            traceback.print_exc()
            return None

    def apply_animation_from_blend_file(self, target_armature, blend_file_path, frame_start, frame_end, animation_name=None, apply_mode='NEW', apply_selected_bones_only=False, selected_bones=None, use_slots=False, mirror_animation=False, reverse_animation=False, rig_type='rigify', animation_metadata=None):
        """Apply animation by loading action from blend file, optionally filtering to selected bones and using slots

        Args:
            animation_metadata: Optional dict with library tracking info:
                - uuid: Animation UUID
                - version_group_id: Version group for linking versions
                - version: Version number (1, 2, 3...)
                - version_label: Human-readable version (v001, v002...)
                - name: Animation name
                - rig_type: Rig type
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

            # Mirror the action if requested
            if mirror_animation:
                logger.info(f"Mirroring Action with rig type: {rig_type}")
                mirrored_action = self.mirror_action(source_action, rig_type, target_armature)

                if mirrored_action:
                    # Remove original action and use mirrored version
                    bpy.data.actions.remove(source_action)
                    source_action = mirrored_action
                    logger.info("Successfully created mirrored Action")
                else:
                    logger.warning("Failed to mirror Action - Action may not support mirroring. Applying original Action instead.")
                    # Continue with original action

            # Create animation data if it doesn't exist
            if not target_armature.animation_data:
                target_armature.animation_data_create()

            # Handle different apply modes
            if apply_mode == 'INSERT':
                # INSERT mode: Merge keyframes into existing action at playhead
                return self.insert_animation_at_playhead(
                    target_armature,
                    source_action,
                    frame_start,
                    frame_end,
                    apply_selected_bones_only,
                    selected_bones,
                    use_slots,
                    reverse_animation
                )
            else:
                # NEW mode: Replace with new action or add to slot
                if use_slots:
                    # SLOT MODE: Add Action as a new slot on current action
                    logger.debug("NEW + SLOT mode: Adding Action as new slot")

                    # Get or create action (persistent action for all slots)
                    current_action = target_armature.animation_data.action
                    if not current_action:
                        # No action exists, create a persistent shared action
                        action_name = f"{target_armature.name}_SlottedActions"
                        logger.debug(f"No existing action, creating persistent action: {action_name}")
                        current_action = bpy.data.actions.new(name=action_name)
                        target_armature.animation_data.action = current_action
                        logger.info(f"Created persistent action '{action_name}' for slot-based Actions")

                    # Ensure action has layer and strip (required for Blender 4.4+ layered actions)
                    if hasattr(current_action, 'layers') and len(current_action.layers) == 0:
                        logger.debug("Action has no layers, creating layer and strip")
                        # Note: In Blender 4.4+, layers/strips may be auto-created
                        # This check is defensive in case they're not

                    # Get or create slot with sequential naming
                    existing_slot_count = len(current_action.slots)
                    display_name = animation_name or source_action.name
                    slot_name = f"{display_name}_slot_{existing_slot_count + 1}"
                    try:
                        # Check if action already has slots (Blender auto-creates first slot)
                        if len(current_action.slots) > 0:
                            # Check if the first slot is empty (no channelbag or no fcurves)
                            first_slot = current_action.slots[0]
                            try:
                                first_channelbag = current_action.layers[0].strips[0].channelbag(first_slot)
                                is_empty = len(first_channelbag.fcurves) == 0 if first_channelbag else True
                            except:
                                is_empty = True

                            if is_empty:
                                # Reuse the empty auto-created slot
                                new_slot = first_slot
                                logger.debug(f"Reusing existing empty slot for: {slot_name}")
                            else:
                                # First slot has data, create a new slot
                                new_slot = current_action.slots.new('OBJECT', slot_name)
                                logger.debug(f"Created new slot: {slot_name}")
                        else:
                            # No slots exist, create the first one
                            new_slot = current_action.slots.new('OBJECT', slot_name)
                            logger.debug(f"Created first slot: {slot_name}")
                    except Exception as e:
                        logger.error(f"Failed to create animation slot: {e}")
                        # Fallback to standard NEW mode
                        logger.warning("Falling back to standard NEW mode")
                        use_slots = False
                        new_slot = None

                    # Only proceed with slot mode if slot was created successfully
                    if new_slot:
                        # Get the channelbag for the new slot (Blender 4.4+ Layered Actions API)
                        channelbag = None
                        try:
                            # Use ensure=True to create channelbag if it doesn't exist yet
                            channelbag = current_action.layers[0].strips[0].channelbag(new_slot, ensure=True)
                            logger.debug(f"Got channelbag for slot '{slot_name}', fcurve count before: {len(channelbag.fcurves)}")
                        except Exception as e:
                            logger.error(f"Failed to get channelbag for slot: {e}")
                            logger.error(traceback.format_exc())
                            logger.warning("Channelbag access failed - slot mode not available in this Blender version")
                            # Will trigger fallback to standard NEW mode below

                        # Filter bones if needed
                        bones_to_apply = None
                        if apply_selected_bones_only and selected_bones:
                            bones_to_apply = set(selected_bones)
                            logger.debug(f"NEW + SLOT mode: Filtering to selected bones: {bones_to_apply}")

                        # Copy keyframes from source action to the new slot (only if channelbag succeeded)
                        copied_fcurves = 0
                        if channelbag:
                            for fcurve in get_action_fcurves(source_action):
                                # Check if this fcurve affects a bone we want to apply
                                should_copy = True
                                if bones_to_apply:
                                    # Extract bone name from data_path like 'pose.bones["BoneName"].location'
                                    if 'pose.bones[' in fcurve.data_path:
                                        try:
                                            bone_name = fcurve.data_path.split('"')[1]
                                            if bone_name not in bones_to_apply:
                                                should_copy = False
                                        except IndexError:
                                            logger.warning(f"Could not parse bone name from: {fcurve.data_path}")
                                            should_copy = False
                                    else:
                                        # Not a bone fcurve, skip when filtering
                                        should_copy = False

                                if should_copy:
                                    # Create new fcurve in the channelbag (slot-specific)
                                    new_fcurve = channelbag.fcurves.new(
                                        fcurve.data_path,
                                        index=fcurve.array_index
                                    )
                                    logger.debug(f"Created fcurve in slot channelbag: {fcurve.data_path}")

                                    # Copy keyframe points at original or reversed frame positions
                                    for keyframe in fcurve.keyframe_points:
                                        if reverse_animation:
                                            # Simply reverse: first frame becomes last, last becomes first
                                            reversed_frame = frame_end - (keyframe.co[0] - frame_start)
                                            new_fcurve.keyframe_points.insert(reversed_frame, keyframe.co[1])
                                        else:
                                            new_fcurve.keyframe_points.insert(keyframe.co[0], keyframe.co[1])
                                    # Update fcurve
                                    new_fcurve.update()
                                    copied_fcurves += 1

                        # Validate that we copied something
                        logger.info(f"Finished copying fcurves. Total copied: {copied_fcurves}, channelbag: {channelbag is not None}")

                        if copied_fcurves == 0:
                            logger.warning("No fcurves were copied to the new slot. Action may be empty or all fcurves were filtered out.")
                            # If channelbag failed (broke out of loop), fall back to standard NEW mode
                            if channelbag is None:
                                logger.warning("Channelbag was None - triggering fallback to standard NEW mode")
                                new_slot = None  # Trigger the fallback block below

                        # Only proceed if slot mode succeeded
                        logger.debug(f"Checking slot activation: new_slot={new_slot is not None}, copied_fcurves={copied_fcurves}")
                        if new_slot and copied_fcurves > 0:
                            # Set the new slot as active
                            target_armature.animation_data.action_slot = new_slot
                            logger.info(f"Created and activated new slot: {slot_name} with {copied_fcurves} fcurves")

                            # Remove source action as we've copied what we need
                            bpy.data.actions.remove(source_action)
                        else:
                            # Slot mode failed, trigger standard NEW mode fallback
                            logger.warning("Slot mode failed, using standard NEW mode")
                            new_slot = None
                    else:
                        # Fallback: use standard NEW mode if slot creation failed
                        logger.debug("Using fallback to standard NEW mode")
                        if apply_selected_bones_only and selected_bones:
                            filtered_action = self.create_filtered_action(source_action, selected_bones, target_armature)
                            if filtered_action:
                                target_armature.animation_data.action = filtered_action
                            else:
                                target_armature.animation_data.action = source_action
                        else:
                            target_armature.animation_data.action = source_action

                else:
                    # Standard NEW mode: Replace with new action
                    # Apply the action - filter to selected bones if needed
                    if apply_selected_bones_only and selected_bones:
                        filtered_action = self.create_filtered_action(source_action, selected_bones, target_armature)
                        if filtered_action:
                            action_to_apply = filtered_action
                        else:
                            action_to_apply = source_action
                    else:
                        action_to_apply = source_action

                    # Apply reverse if requested (standard NEW mode)
                    if reverse_animation:
                        logger.info("Reversing animation for standard NEW mode")
                        reversed_action = self.reverse_action(action_to_apply, frame_start, frame_end)
                        if reversed_action:
                            # Remove original and use reversed
                            if action_to_apply != source_action:
                                bpy.data.actions.remove(action_to_apply)
                            bpy.data.actions.remove(source_action)
                            target_armature.animation_data.action = reversed_action
                            # For Blender 5.0+, we must also set the action_slot
                            from ..utils.utils import BLENDER_5_0_OR_LATER
                            if BLENDER_5_0_OR_LATER and reversed_action.slots:
                                target_armature.animation_data.action_slot = reversed_action.slots[0]
                                logger.debug(f"Set action_slot for reversed action")
                        else:
                            logger.warning("Failed to reverse animation, using original")
                            target_armature.animation_data.action = action_to_apply
                    else:
                        target_armature.animation_data.action = action_to_apply

            # Set animation slot for Blender 4.5+ compatibility (non-slot mode)
            if not use_slots:
                current_action = target_armature.animation_data.action
                if hasattr(target_armature.animation_data, 'action_slot') and current_action and current_action.slots:
                    target_armature.animation_data.action_slot = current_action.slots[0]
            
            # Force viewport and animation update
            bpy.context.view_layer.update()
            bpy.context.scene.frame_set(bpy.context.scene.frame_current)
            
            # Ensure armature is in pose mode for Action
            # if bpy.context.active_object == target_armature and bpy.context.mode != 'POSE':
            #     bpy.ops.object.mode_set(mode='POSE')

            # Don't modify scene timeline at all when applying Actions
            # The user's cinematic timeline should remain untouched
            scene = bpy.context.scene

            # Store library metadata on the applied action for version tracking
            if animation_metadata:
                current_action = target_armature.animation_data.action
                if current_action:
                    self._store_library_metadata(current_action, animation_metadata)
                    logger.debug(f"Stored library metadata on action '{current_action.name}'")

            logger.info(f"Applied Action from {blend_file_path}")
            return True

        except Exception as e:
            logger.error(f"Error applying Action from blend file: {e}")
            return False

    def _store_library_metadata(self, action, metadata):
        """Store library tracking metadata on an action as custom properties

        This allows the capture operator to detect that an action came from
        the library and offer versioning options.

        Args:
            action: Blender action to store metadata on
            metadata: Dict with uuid, version_group_id, version, version_label, name, rig_type
        """
        action["animlib_imported"] = True
        action["animlib_app_version"] = "1.3.0"  # For one-time v1.2→v1.3 migration detection
        action["animlib_uuid"] = metadata.get('uuid', '')
        action["animlib_version_group_id"] = metadata.get('version_group_id', metadata.get('uuid', ''))
        action["animlib_version"] = metadata.get('version', 1)
        action["animlib_version_label"] = metadata.get('version_label', 'v001')
        action["animlib_name"] = metadata.get('name', '')
        action["animlib_rig_type"] = metadata.get('rig_type', '')
    
    def insert_animation_at_playhead(self, target_armature, source_action, frame_start, frame_end, apply_selected_bones_only=False, selected_bones=None, use_slots=False, reverse_animation=False):
        """Insert Action keyframes into existing action at playhead position, optionally into active slot"""
        try:
            scene = bpy.context.scene

            # Get or create action
            existing_action = target_armature.animation_data.action
            if not existing_action:
                # No existing action, create new one
                logger.debug("INSERT mode: No existing action, creating new action")
                existing_action = bpy.data.actions.new(name=f"Inserted_{source_action.name}")
                target_armature.animation_data.action = existing_action
            else:
                logger.debug(f"INSERT mode: Inserting into existing action '{existing_action.name}'")

            # Calculate frame offset based on playhead position
            current_frame = scene.frame_current
            frame_offset = current_frame - frame_start

            logger.debug(f"INSERT mode: Playhead at frame {current_frame}, offset: {frame_offset}")
            logger.debug(f"INSERT mode: Source Action frames {frame_start} to {frame_end}")

            # Get active slot if using slot mode
            active_slot = None
            if use_slots:
                active_slot = target_armature.animation_data.action_slot if hasattr(target_armature.animation_data, 'action_slot') else None
                if active_slot:
                    logger.debug(f"INSERT + SLOT mode: Inserting into active slot '{active_slot.name}'")
                else:
                    # No active slot, create one
                    logger.debug("INSERT + SLOT mode: No active slot, creating one")
                    slot_name = f"Slot_{int(time.time())}"
                    try:
                        # Blender 4.4+ requires id_type parameter: slots.new(id_type, name)
                        active_slot = existing_action.slots.new('OBJECT', slot_name)
                        target_armature.animation_data.action_slot = active_slot
                        logger.debug(f"Created new slot: {slot_name}")
                    except Exception as e:
                        logger.error(f"Failed to create animation slot: {e}")
                        logger.warning("Falling back to standard INSERT mode")
                        use_slots = False
                        active_slot = None

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
                    existing_fcurve = find_action_fcurve(existing_action, root_location_path, index=axis_index)
                    if existing_fcurve:
                        previous_value = existing_fcurve.evaluate(previous_frame)
                    else:
                        previous_value = 0.0
                        logger.debug(f"No existing location {axis_name} fcurve for root bone, using 0.0")

                    # Get source animation's start position for this axis
                    source_fcurve = find_action_fcurve(source_action, root_location_path, index=axis_index)
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
                    has_quat_fcurves = any(find_action_fcurve(source_action, root_quat_path, i) for i in range(4))
                    has_euler_fcurves = any(find_action_fcurve(source_action, root_euler_path, i) for i in range(3))

                    if has_quat_fcurves:
                        # QUATERNION: Use proper quaternion multiplication
                        # delta = prev @ src.inverted() so that delta @ src = prev
                        prev_quat = get_quaternion_at_frame(existing_action, root_bone_name, previous_frame)
                        src_quat = get_quaternion_at_frame(source_action, root_bone_name, frame_start)
                        delta_quat = prev_quat @ src_quat.inverted()

                        logger.info(f"Root quaternion delta computed: {delta_quat}")
                        logger.debug(f"  prev_quat at frame {previous_frame}: {prev_quat}")
                        logger.debug(f"  src_quat at frame {frame_start}: {src_quat}")

                    elif has_euler_fcurves:
                        # EULER: Simple addition works for euler angles
                        for axis_index in range(3):  # 0=X, 1=Y, 2=Z
                            axis_name = ['X', 'Y', 'Z'][axis_index]

                            # Get previous animation's end rotation for this axis
                            existing_fcurve = find_action_fcurve(existing_action, root_euler_path, index=axis_index)
                            if existing_fcurve:
                                previous_value = existing_fcurve.evaluate(previous_frame)
                            else:
                                previous_value = 0.0

                            # Get source animation's start rotation for this axis
                            source_fcurve = find_action_fcurve(source_action, root_euler_path, index=axis_index)
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
            for source_fcurve in get_action_fcurves(source_action):
                # Check if this fcurve affects a bone we want to apply
                if bones_to_apply:
                    # Extract bone name from data_path like 'pose.bones["BoneName"].location'
                    if 'pose.bones[' in source_fcurve.data_path:
                        bone_name = source_fcurve.data_path.split('"')[1]
                        if bone_name not in bones_to_apply:
                            continue  # Skip this bone

                # Find or create matching fcurve in existing action
                existing_fcurve = find_action_fcurve(existing_action, source_fcurve.data_path, index=source_fcurve.array_index)
                if not existing_fcurve:
                    existing_fcurve = new_action_fcurve(existing_action, source_fcurve.data_path, index=source_fcurve.array_index)

                    # Assign to active slot if using slot mode
                    if active_slot and hasattr(existing_fcurve, 'action_slot'):
                        existing_fcurve.action_slot = active_slot

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
                        original_quat = get_quaternion_at_frame(source_action, root_bone_name, keyframe_time)
                        # Apply the delta rotation: new_quat = delta @ original
                        new_quat = delta_quat @ original_quat
                        # Extract the component for this fcurve (array_index: 0=W, 1=X, 2=Y, 3=Z)
                        value = new_quat[source_fcurve.array_index]

                    existing_fcurve.keyframe_points.insert(new_frame, value)
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

    def create_filtered_action(self, source_action, selected_bones, target_armature):
        """Create a new action with only fcurves affecting selected bones"""
        from ..utils.utils import BLENDER_5_0_OR_LATER, init_action_for_blender_5

        try:
            # Create a new action
            filtered_action = bpy.data.actions.new(name=f"{source_action.name}_filtered")

            # For Blender 5.0+, initialize the action with proper layer/strip/slot structure
            slot = None
            if BLENDER_5_0_OR_LATER:
                slot = init_action_for_blender_5(filtered_action, slot_name="Filtered")
                if not slot:
                    logger.error("Failed to initialize filtered action for Blender 5.0")

            # Track which bones we're filtering for
            bone_data_paths = set()
            for bone_name in selected_bones:
                # Check if bone exists in target armature
                if bone_name in target_armature.pose.bones:
                    # Add common pose bone data paths
                    bone_data_paths.add(f'pose.bones["{bone_name}"].location')
                    bone_data_paths.add(f'pose.bones["{bone_name}"].rotation_euler')
                    bone_data_paths.add(f'pose.bones["{bone_name}"].rotation_quaternion')
                    bone_data_paths.add(f'pose.bones["{bone_name}"].scale')
                else:
                    logger.warning(f"Bone '{bone_name}' not found in target armature")

            if not bone_data_paths:
                logger.warning("No valid bone data paths found")
                return None

            # Copy relevant fcurves from source to filtered action
            copied_count = 0
            for src_fcurve in get_action_fcurves(source_action):
                # Check if this fcurve affects one of our selected bones
                for bone_path in bone_data_paths:
                    if src_fcurve.data_path.startswith(bone_path):
                        # Copy this fcurve
                        new_fcurve = new_action_fcurve(
                            filtered_action,
                            src_fcurve.data_path,
                            index=src_fcurve.array_index,
                            slot=slot
                        )
                        
                        # Copy keyframe points
                        new_fcurve.keyframe_points.add(len(src_fcurve.keyframe_points))
                        for i, src_keyframe in enumerate(src_fcurve.keyframe_points):
                            new_keyframe = new_fcurve.keyframe_points[i]
                            new_keyframe.co = src_keyframe.co
                            new_keyframe.handle_left = src_keyframe.handle_left
                            new_keyframe.handle_right = src_keyframe.handle_right
                            new_keyframe.handle_left_type = src_keyframe.handle_left_type
                            new_keyframe.handle_right_type = src_keyframe.handle_right_type
                            new_keyframe.interpolation = src_keyframe.interpolation
                        
                        new_fcurve.update()
                        copied_count += 1
                        break
                        
            logger.info(f"Copied {copied_count} fcurves for selected bones")
            
            if copied_count == 0:
                # Clean up empty action
                bpy.data.actions.remove(filtered_action)
                return None
                
            return filtered_action
            
        except Exception as e:
            logger.error(f"Error creating filtered action: {e}")
            return None
      
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

            # Process the most recent pending request (already sorted by queue_client)
            request_file = pending_files[0]

            # Read request data using queue client
            request_data = animation_queue_client.read_request(request_file)

            if not request_data or request_data.get('status') != 'pending':
                self.report({'INFO'}, "No pending requests")
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
            blend_file_path = request_data.get('blend_file_path')

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
_POLL_INTERVAL = 0.1  # Poll every 0.1 seconds (faster for responsive pose apply)


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
            return _POLL_INTERVAL  # Nothing to do

        logger.debug(f"Found {len(pending_files)} pending queue file(s)")

        # Get window manager and check for windows
        wm = bpy.context.window_manager
        if not wm.windows:
            logger.debug("No windows available")
            return _POLL_INTERVAL

        window = wm.windows[0]

        # Find a VIEW_3D area for context
        area = None
        for a in window.screen.areas:
            if a.type == 'VIEW_3D':
                area = a
                break

        if not area:
            logger.debug("No VIEW_3D area found")
            return _POLL_INTERVAL

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
            return _POLL_INTERVAL

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
