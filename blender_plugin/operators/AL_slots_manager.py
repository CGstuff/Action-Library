import bpy
import time
from bpy.types import Operator
from ..utils.utils import (get_active_armature)
from ..utils.logger import get_logger

logger = get_logger()

class ANIMLIB_OT_delete_slot(Operator):
    """Delete the selected Action slot from the current action"""
    bl_idname = "animlib.delete_slot"
    bl_label = "Delete Slot"
    bl_description = "Delete the selected Action slot and all its keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    slot_index: bpy.props.IntProperty(
        name="Slot Index",
        description="Index of the slot to delete",
        default=0
    )

    def invoke(self, context, event):
        """Show confirmation dialog"""
        armature = get_active_armature(context)
        if not armature or not armature.animation_data or not armature.animation_data.action:
            self.report({'ERROR'}, "No action found")
            return {'CANCELLED'}

        action = armature.animation_data.action

        if not hasattr(action, 'slots') or len(action.slots) == 0:
            self.report({'ERROR'}, "No slots found")
            return {'CANCELLED'}

        if self.slot_index < 0 or self.slot_index >= len(action.slots):
            self.report({'ERROR'}, "Invalid slot index")
            return {'CANCELLED'}

        # Warn if it's the only slot
        if len(action.slots) == 1:
            self.report({'WARNING'}, "Cannot delete the only remaining slot")
            return {'CANCELLED'}

        # Show confirmation dialog
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            armature = get_active_armature(context)
            if not armature or not armature.animation_data or not armature.animation_data.action:
                self.report({'ERROR'}, "No action found")
                return {'CANCELLED'}

            action = armature.animation_data.action

            if self.slot_index < 0 or self.slot_index >= len(action.slots):
                self.report({'ERROR'}, "Invalid slot index")
                return {'CANCELLED'}

            # Get the slot to delete
            slot_to_delete = action.slots[self.slot_index]

            # If this is the active slot, switch to another one first
            if hasattr(armature.animation_data, 'action_slot'):
                if armature.animation_data.action_slot == slot_to_delete:
                    # Switch to the first different slot
                    for i, slot in enumerate(action.slots):
                        if i != self.slot_index:
                            armature.animation_data.action_slot = slot
                            logger.info(f"Switched active slot before deletion")
                            break

            # Delete the slot
            action.slots.remove(slot_to_delete)
            logger.info(f"Deleted slot at index {self.slot_index}")

            # Adjust selected index if needed
            if self.slot_index >= len(action.slots):
                context.scene.animlib_active_slot_index = len(action.slots) - 1

            self.report({'INFO'}, f"Deleted Slot {self.slot_index + 1}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to delete slot: {str(e)}")
            logger.error(f"Error deleting slot: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class ANIMLIB_OT_activate_slot(Operator):
    """Activate the selected Action slot (make it play)"""
    bl_idname = "animlib.activate_slot"
    bl_label = "Activate Slot"
    bl_description = "Make the selected slot active (plays this Action)"

    slot_index: bpy.props.IntProperty(
        name="Slot Index",
        description="Index of the slot to activate",
        default=0
    )

    def execute(self, context):
        try:
            armature = get_active_armature(context)
            if not armature or not armature.animation_data or not armature.animation_data.action:
                self.report({'ERROR'}, "No action found")
                return {'CANCELLED'}

            action = armature.animation_data.action

            if self.slot_index < 0 or self.slot_index >= len(action.slots):
                self.report({'ERROR'}, "Invalid slot index")
                return {'CANCELLED'}

            # Activate the selected slot
            if hasattr(armature.animation_data, 'action_slot'):
                armature.animation_data.action_slot = action.slots[self.slot_index]
                logger.info(f"Activated slot index {self.slot_index}")
                self.report({'INFO'}, f"Activated Slot {self.slot_index + 1}")
            else:
                self.report({'WARNING'}, "Slot activation not supported in this Blender version")
                return {'CANCELLED'}

            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to activate slot: {str(e)}")
            logger.error(f"Error activating slot: {e}")
            return {'CANCELLED'}


class ANIMLIB_OT_duplicate_slot(Operator):
    """Duplicate the selected Action slot"""
    bl_idname = "animlib.duplicate_slot"
    bl_label = "Duplicate Slot"
    bl_description = "Create a copy of the selected slot"
    bl_options = {'REGISTER', 'UNDO'}

    slot_index: bpy.props.IntProperty(
        name="Slot Index",
        description="Index of the slot to duplicate",
        default=0
    )

    def execute(self, context):
        try:
            armature = get_active_armature(context)
            if not armature or not armature.animation_data or not armature.animation_data.action:
                self.report({'ERROR'}, "No action found")
                return {'CANCELLED'}

            action = armature.animation_data.action

            if self.slot_index < 0 or self.slot_index >= len(action.slots):
                self.report({'ERROR'}, "Invalid slot index")
                return {'CANCELLED'}

            source_slot = action.slots[self.slot_index]

            # Create new slot
            new_slot = action.slots.new('OBJECT', f"Slot_{int(time.time())}_copy")

            # Get channelbag for both slots
            try:
                source_channelbag = action.layers[0].strips[0].channelbag(source_slot)
                new_channelbag = action.layers[0].strips[0].channelbag(new_slot, ensure=True)

                # Copy all fcurves from source to new slot
                for fcurve in source_channelbag.fcurves:
                    new_fcurve = new_channelbag.fcurves.new(fcurve.data_path, index=fcurve.array_index)
                    for keyframe in fcurve.keyframe_points:
                        new_fcurve.keyframe_points.insert(keyframe.co[0], keyframe.co[1])
                    new_fcurve.update()

                logger.info(f"Duplicated slot {self.slot_index} with {len(source_channelbag.fcurves)} fcurves")
                self.report({'INFO'}, f"Duplicated Slot {self.slot_index + 1}")
                return {'FINISHED'}

            except Exception as e:
                logger.error(f"Failed to copy fcurves: {e}")
                # Clean up the slot we created
                action.slots.remove(new_slot)
                raise

        except Exception as e:
            self.report({'ERROR'}, f"Failed to duplicate slot: {str(e)}")
            logger.error(f"Error duplicating slot: {e}")
            return {'CANCELLED'}


class ANIMLIB_OT_toggle_slot_selection(Operator):
    """Toggle a slot for merging"""
    bl_idname = "animlib.toggle_slot_selection"
    bl_label = "Toggle Slot Selection"
    bl_description = "Select or deselect this slot for merge operations"

    slot_index: bpy.props.IntProperty(
        name="Slot Index",
        description="Index of the slot to toggle",
        default=0
    )

    def execute(self, context):
        import json
        scene = context.scene

        try:
            # Parse current selection dict (use string index as key)
            selection_dict = json.loads(scene.animlib_merge_selected_slots or "{}")
            slot_key = str(self.slot_index)

            # Toggle selection
            current_state = selection_dict.get(slot_key, False)
            selection_dict[slot_key] = not current_state

            # Save back to scene
            scene.animlib_merge_selected_slots = json.dumps(selection_dict)

            # Force UI redraw
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

            return {'FINISHED'}

        except Exception as e:
            logger.error(f"Error toggling slot selection: {e}")
            self.report({'ERROR'}, f"Failed to toggle selection: {str(e)}")
            return {'CANCELLED'}


class ANIMLIB_OT_select_all_slots(Operator):
    """Select all slots for merging"""
    bl_idname = "animlib.select_all_slots"
    bl_label = "Select All Slots"
    bl_description = "Select all slots for merge operations"

    def execute(self, context):
        import json
        scene = context.scene
        armature = get_active_armature(context)

        if not armature or not armature.animation_data or not armature.animation_data.action:
            self.report({'ERROR'}, "No action found")
            return {'CANCELLED'}

        action = armature.animation_data.action

        if not hasattr(action, 'slots') or len(action.slots) == 0:
            self.report({'ERROR'}, "No slots found")
            return {'CANCELLED'}

        try:
            # Select all slots (use string indices as keys)
            selection_dict = {}
            for index in range(len(action.slots)):
                selection_dict[str(index)] = True

            scene.animlib_merge_selected_slots = json.dumps(selection_dict)

            # Force UI redraw
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

            self.report({'INFO'}, f"Selected all {len(action.slots)} slots")
            return {'FINISHED'}

        except Exception as e:
            logger.error(f"Error selecting all slots: {e}")
            self.report({'ERROR'}, f"Failed to select all: {str(e)}")
            return {'CANCELLED'}


class ANIMLIB_OT_deselect_all_slots(Operator):
    """Deselect all slots"""
    bl_idname = "animlib.deselect_all_slots"
    bl_label = "Deselect All Slots"
    bl_description = "Clear slot selection for merge operations"

    def execute(self, context):
        import json
        scene = context.scene

        try:
            # Clear all selections
            scene.animlib_merge_selected_slots = json.dumps({})

            # Force UI redraw
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

            self.report({'INFO'}, "Cleared slot selection")
            return {'FINISHED'}

        except Exception as e:
            logger.error(f"Error deselecting all slots: {e}")
            self.report({'ERROR'}, f"Failed to deselect all: {str(e)}")
            return {'CANCELLED'}


class ANIMLIB_OT_merge_slots(Operator):
    """Merge multiple selected slots by blending their keyframes"""
    bl_idname = "animlib.merge_slots"
    bl_label = "Merge Slots"
    bl_description = "Merge selected slots into a new slot by blending keyframe values"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        """Show confirmation dialog"""
        import json
        scene = context.scene

        # Count selected slots
        selection_dict = json.loads(scene.animlib_merge_selected_slots or "{}")
        selected_count = sum(1 for v in selection_dict.values() if v)

        if selected_count < 2:
            self.report({'ERROR'}, "Select at least 2 slots to merge")
            return {'CANCELLED'}

        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        import json

        try:
            scene = context.scene
            armature = get_active_armature(context)

            if not armature or not armature.animation_data or not armature.animation_data.action:
                self.report({'ERROR'}, "No action found")
                return {'CANCELLED'}

            action = armature.animation_data.action

            if not hasattr(action, 'slots') or len(action.slots) == 0:
                self.report({'ERROR'}, "No slots found")
                return {'CANCELLED'}

            # Get selected slots (indices stored as string keys in JSON)
            selection_dict = json.loads(scene.animlib_merge_selected_slots or "{}")
            selected_slot_indices = [int(index_str) for index_str, selected in selection_dict.items() if selected]

            if len(selected_slot_indices) < 2:
                self.report({'ERROR'}, "Select at least 2 slots to merge")
                return {'CANCELLED'}

            # Get merge settings
            merge_mode = scene.animlib_merge_mode
            include_unique = scene.animlib_merge_include_unique

            # Create merged slot
            merged_slot_name = f"Merged_{int(time.time())}"
            merged_slot = action.slots.new('OBJECT', merged_slot_name)
            merged_channelbag = action.layers[0].strips[0].channelbag(merged_slot, ensure=True)

            logger.info(f"Merging {len(selected_slot_indices)} slots at indices: {selected_slot_indices}")

            # Get channelbags for all input slots
            input_channelbags = []
            for slot_index in selected_slot_indices:
                if slot_index < len(action.slots):
                    slot = action.slots[slot_index]
                    try:
                        cb = action.layers[0].strips[0].channelbag(slot)
                        if cb:
                            input_channelbags.append((slot_index, cb))
                    except Exception as e:
                        logger.warning(f"Could not get channelbag for slot index {slot_index}: {e}")

            if len(input_channelbags) < 2:
                self.report({'ERROR'}, "Could not access channelbags for selected slots")
                action.slots.remove(merged_slot)
                return {'CANCELLED'}

            # Collect all unique (data_path, array_index) pairs across all slots
            all_fcurve_keys = set()
            for slot_index, cb in input_channelbags:
                for fcurve in cb.fcurves:
                    all_fcurve_keys.add((fcurve.data_path, fcurve.array_index))

            logger.info(f"Found {len(all_fcurve_keys)} unique fcurve keys to merge")

            # For each fcurve key, merge keyframes
            merged_count = 0
            for data_path, array_index in all_fcurve_keys:
                # Get fcurves from each slot for this key
                source_fcurves = []
                for slot_index, cb in input_channelbags:
                    fcurve = next(
                        (fc for fc in cb.fcurves
                         if fc.data_path == data_path and fc.array_index == array_index),
                        None
                    )
                    if fcurve:
                        source_fcurves.append(fcurve)

                # Check if we should process this fcurve
                if len(source_fcurves) < 2:
                    # Only one slot has this fcurve
                    if include_unique and source_fcurves:
                        # Copy as-is
                        fcurve_to_copy = source_fcurves[0]
                        new_fcurve = merged_channelbag.fcurves.new(data_path, index=array_index)
                        for keyframe in fcurve_to_copy.keyframe_points:
                            new_fcurve.keyframe_points.insert(keyframe.co[0], keyframe.co[1])
                        new_fcurve.update()
                        merged_count += 1
                    continue

                # Create merged fcurve
                merged_fcurve = merged_channelbag.fcurves.new(data_path, index=array_index)

                # Collect all unique frame numbers across all source fcurves
                all_frames = set()
                for fcurve in source_fcurves:
                    for keyframe in fcurve.keyframe_points:
                        all_frames.add(keyframe.co[0])

                all_frames = sorted(all_frames)

                # For each frame, blend values from all fcurves
                for frame in all_frames:
                    values = []

                    for fcurve in source_fcurves:
                        # Find keyframe at this exact frame
                        keyframe = next(
                            (kf for kf in fcurve.keyframe_points if abs(kf.co[0] - frame) < 0.001),
                            None
                        )

                        if keyframe:
                            # Exact match - use value
                            values.append(keyframe.co[1])
                        else:
                            # No exact keyframe - interpolate
                            interpolated_value = self.interpolate_fcurve(fcurve, frame)
                            if interpolated_value is not None:
                                values.append(interpolated_value)

                    # Blend values based on mode
                    if values:
                        if merge_mode == 'AVERAGE':
                            blended_value = sum(values) / len(values)
                        elif merge_mode == 'ADD':
                            blended_value = sum(values)
                        else:
                            blended_value = values[0]

                        # Insert blended keyframe
                        merged_fcurve.keyframe_points.insert(frame, blended_value)

                merged_fcurve.update()
                merged_count += 1

            # Activate the merged slot
            if hasattr(armature.animation_data, 'action_slot'):
                armature.animation_data.action_slot = merged_slot

            logger.info(f"Successfully merged {merged_count} fcurves into slot: {merged_slot_name}")
            self.report({'INFO'}, f"Merged {len(selected_slot_indices)} slots into: {merged_slot_name}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to merge slots: {str(e)}")
            logger.error(f"Error merging slots: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

    def interpolate_fcurve(self, fcurve, frame):
        """
        Simple linear interpolation for fcurve at a given frame.
        If frame is before first keyframe or after last, return boundary value.
        """
        keyframes = fcurve.keyframe_points

        if not keyframes or len(keyframes) == 0:
            return None

        # If frame is at keyframe, return exact value
        exact_kf = next((kf for kf in keyframes if abs(kf.co[0] - frame) < 0.001), None)
        if exact_kf:
            return exact_kf.co[1]

        # Find surrounding keyframes
        before = None
        after = None

        for kf in keyframes:
            if kf.co[0] < frame:
                before = kf
            elif kf.co[0] > frame and after is None:
                after = kf
                break

        # Boundary cases
        if before is None:
            return keyframes[0].co[1]
        if after is None:
            return keyframes[-1].co[1]

        # Linear interpolation
        t = (frame - before.co[0]) / (after.co[0] - before.co[0])
        value = before.co[1] + t * (after.co[1] - before.co[1])

        return value