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
            
            # Look for animation in new unified structure
            # First try library folder (root level)
            animation_folder = library_dir / "library" / self.animation_id
            json_file = animation_folder / f"{self.animation_id}.json"
            
            # If not found in library, search in animations subfolders  
            if not json_file.exists():
                animations_dir = library_dir / "animations"
                if animations_dir.exists():
                    # Search for the animation ID in any subfolder
                    for root_path in animations_dir.rglob(self.animation_id):
                        if root_path.is_dir():
                            potential_json = root_path / f"{self.animation_id}.json"
                            if potential_json.exists():
                                json_file = potential_json
                                animation_folder = root_path
                                break

            if not json_file.exists():
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

            # Apply animation by loading from blend file
            success = self.apply_animation_from_blend_file(
                armature,
                blend_file_path,
                frame_start,
                frame_end,
                apply_mode=apply_mode,
                apply_selected_bones_only=self.apply_selected_bones_only,
                selected_bones=selected_bones,
                use_slots=use_slots,
                mirror_animation=mirror_animation,
                reverse_animation=reverse_animation,
                rig_type=animation_rig_type
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
            original_area_type = bpy.context.area.type if bpy.context.area else None

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
            # Save current area type
            area = bpy.context.area
            old_type = area.type
            area.type = 'DOPESHEET_EDITOR'

            # Set dope sheet to Action Editor mode
            for space in area.spaces:
                if space.type == 'DOPESHEET_EDITOR':
                    space.mode = 'ACTION'
                    break

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

            # Insert a single keyframe on all selected bones to create fcurves
            # This is required for paste to work
            bpy.ops.anim.keyframe_insert_menu(type='WholeCharacter')
            logger.info(f"Inserted initial keyframe at frame {frame_start}")

            # Select all keyframes in new action
            bpy.ops.action.select_all(action='SELECT')

            # Paste flipped - this uses Blender's built-in mirroring logic
            bpy.ops.action.paste(flipped=True)
            logger.info("Pasted keyframes with flipped option")

            # Clean up: delete the initial keyframe we created (only at start frame)
            # The pasted keys should now be there
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
                if original_area_type and bpy.context.area:
                    bpy.context.area.type = original_area_type
            except:
                pass

            return None

    def apply_animation_from_blend_file(self, target_armature, blend_file_path, frame_start, frame_end, apply_mode='NEW', apply_selected_bones_only=False, selected_bones=None, use_slots=False, mirror_animation=False, reverse_animation=False, rig_type='rigify'):
        """Apply animation by loading action from blend file, optionally filtering to selected bones and using slots"""
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

                    # Get or create slot
                    slot_name = f"{source_action.name}_{int(time.time())}"
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
                            target_armature.animation_data.action = filtered_action
                        else:
                            target_armature.animation_data.action = source_action
                    else:
                        target_armature.animation_data.action = source_action

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

            logger.info(f"Applied Action from {blend_file_path}")
            return True

        except Exception as e:
            logger.error(f"Error applying Action from blend file: {e}")
            return False
    
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
            # Calculate root bone offset if feature is enabled
            root_offsets = [0.0, 0.0, 0.0]  # X, Y, Z offsets
            root_bone_name = scene.animlib_root_bone_name
            enable_root_continuity = scene.animlib_enable_root_motion_continuity

            if enable_root_continuity and root_bone_name:
                logger.debug(f"Root motion continuity enabled for bone: {root_bone_name}")

                # Get axis settings
                apply_axes = [
                    scene.animlib_root_motion_x,
                    scene.animlib_root_motion_y,
                    scene.animlib_root_motion_z
                ]

                # Build the data path for the root bone location
                root_location_path = f'pose.bones["{root_bone_name}"].location'

                # Get the frame just before insertion point for sampling previous animation end
                previous_frame = current_frame - 1

                # Calculate offset for each enabled axis
                for axis_index in range(3):  # 0=X, 1=Y, 2=Z
                    if not apply_axes[axis_index]:
                        continue  # Skip disabled axes

                    axis_name = ['X', 'Y', 'Z'][axis_index]

                    # Get previous animation's end position for this axis
                    existing_fcurve = find_action_fcurve(existing_action, root_location_path, index=axis_index)
                    if existing_fcurve:
                        previous_value = existing_fcurve.evaluate(previous_frame)
                    else:
                        previous_value = 0.0
                        logger.debug(f"No existing {axis_name} fcurve for root bone, using 0.0")

                    # Get source animation's start position for this axis
                    source_fcurve = find_action_fcurve(source_action, root_location_path, index=axis_index)
                    if source_fcurve:
                        source_start_value = source_fcurve.evaluate(frame_start)
                    else:
                        source_start_value = 0.0
                        logger.debug(f"No source {axis_name} fcurve for root bone, using 0.0")

                    # Calculate offset to align source start with previous end
                    root_offsets[axis_index] = previous_value - source_start_value

                    logger.info(f"Root motion {axis_name} offset: {root_offsets[axis_index]:.3f} (prev: {previous_value:.3f}, src: {source_start_value:.3f})")

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

                # ========== CHECK IF THIS IS ROOT BONE LOCATION FCURVE ==========
                # Determine if we need to apply root motion offset to this fcurve
                apply_root_offset = False
                root_offset_value = 0.0

                if enable_root_continuity and root_bone_name:
                    bone_name = extract_bone_name_from_data_path(source_fcurve.data_path)
                    if bone_name == root_bone_name and '.location' in source_fcurve.data_path:
                        # This is a root bone location fcurve
                        axis_index = source_fcurve.array_index
                        if axis_index < 3 and root_offsets[axis_index] != 0.0:
                            apply_root_offset = True
                            root_offset_value = root_offsets[axis_index]
                            logger.debug(f"Applying root offset {root_offset_value:.3f} to {bone_name}.location[{axis_index}]")

                # Copy keyframes with frame offset and optional reversal
                for keyframe in source_fcurve.keyframe_points:
                    if reverse_animation:
                        # Simply reverse: first frame becomes last, last becomes first
                        reversed_frame = frame_end - (keyframe.co.x - frame_start)
                        new_frame = reversed_frame + frame_offset
                    else:
                        new_frame = keyframe.co.x + frame_offset

                    # Apply root motion offset if applicable
                    value = keyframe.co.y
                    if apply_root_offset:
                        value += root_offset_value

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
        try:
            # Create a new action
            filtered_action = bpy.data.actions.new(name=f"{source_action.name}_filtered")
            
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
                            index=src_fcurve.array_index
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
    """Check for pending Action apply requests from desktop app"""
    bl_idname = "animlib.check_apply_queue"
    bl_label = "Check Apply Queue"
    bl_description = "Check for Actions queued for application from desktop app"
    
    def execute(self, context):
        try:
            # Get pending requests from queue client
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


# ==================== AUTO-POLLING TIMER ====================

# Global flag to track if timer is running
_queue_poll_timer_running = False
_POLL_INTERVAL = 0.5  # Poll every 0.5 seconds


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
        print("[AnimLib] Timer already running")
        return  # Already running

    _queue_poll_timer_running = True

    # Register the timer if not already registered
    # Use 2.0 second delay to ensure Blender is fully initialized
    if not bpy.app.timers.is_registered(_auto_poll_queue):
        bpy.app.timers.register(_auto_poll_queue, first_interval=2.0)
        print("[AnimLib] Queue poll timer STARTED - auto-apply enabled")
        logger.info("Queue poll timer started (with temp_override)")
    else:
        print("[AnimLib] Timer was already registered")


def stop_queue_poll_timer():
    """Stop the auto-polling timer"""
    global _queue_poll_timer_running

    _queue_poll_timer_running = False

    # Unregister the timer if registered
    if bpy.app.timers.is_registered(_auto_poll_queue):
        bpy.app.timers.unregister(_auto_poll_queue)
        logger.info("Queue poll timer stopped")
