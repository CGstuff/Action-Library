import bpy
import time
from bpy.types import Operator
from ..utils.utils import (get_active_armature, get_channelbag, copy_fcurve, find_slot)
from ..utils.logger import get_logger

logger = get_logger()


def _quat_mul(a, b):
    """Hamilton product a*b for (w, x, y, z) quaternions (compose rotations)."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw]


def _blend_quaternions(quats, mode='AVERAGE'):
    """Blend a list of (w, x, y, z) quaternions -> a single NORMALIZED quaternion.

    Quaternions are sign-aligned to the first one before blending: q and -q
    represent the same rotation, and without alignment an average can cancel to
    garbage. AVERAGE = normalized linear blend (nlerp); ADD = compose (stack) the
    rotations via quaternion multiplication. This replaces the old, invalid
    component-by-component averaging of rotation channels.
    """
    import math
    if not quats:
        return (1.0, 0.0, 0.0, 0.0)
    ref = quats[0]
    aligned = []
    for q in quats:
        dot = q[0] * ref[0] + q[1] * ref[1] + q[2] * ref[2] + q[3] * ref[3]
        aligned.append([-c for c in q] if dot < 0.0 else list(q))
    if mode == 'ADD':
        result = aligned[0]
        for q in aligned[1:]:
            result = _quat_mul(result, q)
    else:  # AVERAGE / default -> normalized linear blend
        n = float(len(aligned))
        result = [sum(q[i] for q in aligned) / n for i in range(4)]
    mag = math.sqrt(result[0] ** 2 + result[1] ** 2 + result[2] ** 2 + result[3] ** 2)
    if mag < 1e-8:
        return (1.0, 0.0, 0.0, 0.0)
    return tuple(c / mag for c in result)

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
            new_slot = action.slots.new('OBJECT', f"{source_slot.name_display}_copy")

            # Get channelbag for both slots
            try:
                source_channelbag = get_channelbag(action, source_slot)
                new_channelbag = get_channelbag(action, new_slot, ensure=True)

                # Copy all fcurves from source to new slot, with their full
                # curve shape (insert() alone dropped handles and interpolation)
                fcurve_count = len(source_channelbag.fcurves) if source_channelbag else 0
                for fcurve in (source_channelbag.fcurves if source_channelbag else []):
                    copy_fcurve(fcurve, new_channelbag)

                logger.info(f"Duplicated slot '{source_slot.name_display}' with {fcurve_count} fcurves")
                self.report({'INFO'}, f"Duplicated '{source_slot.name_display}'")
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
            armature = get_active_armature(context)
            action = armature.animation_data.action if armature and armature.animation_data else None
            if not action or not (0 <= self.slot_index < len(action.slots)):
                self.report({'ERROR'}, "Invalid slot index")
                return {'CANCELLED'}

            # Parse current selection dict. Keyed by slot handle: indices shift
            # when a slot is deleted, handles don't.
            selection_dict = json.loads(scene.animlib_merge_selected_slots or "{}")
            slot_key = str(action.slots[self.slot_index].handle)

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
            # Select all slots (keyed by slot handle)
            selection_dict = {str(slot.handle): True for slot in action.slots}

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

            # Get selected slots (handles stored as string keys in JSON; ones
            # whose slot has since been deleted are ignored)
            selection_dict = json.loads(scene.animlib_merge_selected_slots or "{}")
            selected_slots = [slot for handle_str, selected in selection_dict.items()
                              if selected and (slot := find_slot(action, int(handle_str))) is not None]

            if len(selected_slots) < 2:
                self.report({'ERROR'}, "Select at least 2 slots to merge")
                return {'CANCELLED'}

            # Get merge settings
            merge_mode = scene.animlib_merge_mode
            include_unique = scene.animlib_merge_include_unique

            # Create merged slot
            merged_slot_name = f"Merged_{int(time.time())}"
            merged_slot = action.slots.new('OBJECT', merged_slot_name)
            merged_channelbag = get_channelbag(action, merged_slot, ensure=True)

            logger.info(f"Merging {len(selected_slots)} slots: {[s.name_display for s in selected_slots]}")

            # Get channelbags for all input slots
            input_channelbags = []
            for slot in selected_slots:
                cb = get_channelbag(action, slot)
                if cb:
                    input_channelbags.append((slot.handle, cb))

            if len(input_channelbags) < 2:
                self.report({'ERROR'}, "Could not access channelbags for selected slots")
                action.slots.remove(merged_slot)
                return {'CANCELLED'}

            # Collect fcurve keys GROUPED BY data_path, so a rotation quaternion's
            # four components can be blended AS A QUATERNION. Averaging a
            # quaternion's components independently (the old behaviour) is
            # mathematically invalid - the result isn't a unit quaternion and the
            # rotation is distorted.
            paths = {}  # data_path -> set(array_index)
            for slot_index, cb in input_channelbags:
                for fcurve in cb.fcurves:
                    paths.setdefault(fcurve.data_path, set()).add(fcurve.array_index)

            logger.info(f"Merging {len(paths)} channels across {len(input_channelbags)} slots")

            def _fcurve_at(cb, data_path, array_index):
                return next((fc for fc in cb.fcurves
                             if fc.data_path == data_path and fc.array_index == array_index), None)

            def _sample(fcurve, frame):
                """Value of an fcurve at a frame (exact keyframe or interpolated)."""
                if fcurve is None:
                    return None
                kf = next((k for k in fcurve.keyframe_points if abs(k.co[0] - frame) < 0.001), None)
                return kf.co[1] if kf else self.interpolate_fcurve(fcurve, frame)

            merged_count = 0
            for data_path, indices in paths.items():
                is_quat = data_path.endswith('rotation_quaternion') and {0, 1, 2, 3}.issubset(indices)

                # Slots that actually drive this channel.
                driving = [cb for _, cb in input_channelbags
                           if any(_fcurve_at(cb, data_path, i) for i in indices)]

                # Only one slot drives it: copy as-is if the user opted in.
                if len(driving) < 2:
                    if include_unique and driving:
                        cb = driving[0]
                        for i in sorted(indices):
                            src = _fcurve_at(cb, data_path, i)
                            if not src:
                                continue
                            dst = merged_channelbag.fcurves.new(data_path, index=i)
                            for k in src.keyframe_points:
                                dst.keyframe_points.insert(k.co[0], k.co[1])
                            dst.update()
                            merged_count += 1
                    continue

                if is_quat:
                    # Blend as a quaternion (sign-aligned, normalized) per frame.
                    all_frames = set()
                    for cb in driving:
                        for i in range(4):
                            fc = _fcurve_at(cb, data_path, i)
                            if fc:
                                all_frames.update(k.co[0] for k in fc.keyframe_points)
                    merged = {i: merged_channelbag.fcurves.new(data_path, index=i) for i in range(4)}
                    for frame in sorted(all_frames):
                        quats = []
                        for cb in driving:
                            q = []
                            for i in range(4):
                                v = _sample(_fcurve_at(cb, data_path, i), frame)
                                q.append(v if v is not None else (1.0 if i == 0 else 0.0))
                            quats.append(q)
                        bq = _blend_quaternions(quats, merge_mode)
                        for i in range(4):
                            merged[i].keyframe_points.insert(frame, bq[i])
                    for fc in merged.values():
                        fc.update()
                    merged_count += 4
                else:
                    # Non-rotation channels (location, scale, custom props):
                    # per-component blend is correct. NOTE: rotation_euler is still
                    # blended component-wise here, which is imperfect for large
                    # angles - a proper fix would convert euler->quat->euler.
                    for array_index in sorted(indices):
                        source_fcurves = [fc for cb in driving
                                          if (fc := _fcurve_at(cb, data_path, array_index))]
                        if not source_fcurves:
                            continue
                        merged_fcurve = merged_channelbag.fcurves.new(data_path, index=array_index)
                        all_frames = set()
                        for fc in source_fcurves:
                            all_frames.update(k.co[0] for k in fc.keyframe_points)
                        for frame in sorted(all_frames):
                            values = [v for fc in source_fcurves
                                      if (v := _sample(fc, frame)) is not None]
                            if not values:
                                continue
                            if merge_mode == 'AVERAGE':
                                blended = sum(values) / len(values)
                            elif merge_mode == 'ADD':
                                blended = sum(values)
                            else:
                                blended = values[0]
                            merged_fcurve.keyframe_points.insert(frame, blended)
                        merged_fcurve.update()
                        merged_count += 1

            # Activate the merged slot
            if hasattr(armature.animation_data, 'action_slot'):
                armature.animation_data.action_slot = merged_slot

            logger.info(f"Successfully merged {merged_count} fcurves into slot: {merged_slot_name}")
            self.report({'INFO'}, f"Merged {len(selected_slots)} slots into: {merged_slot_name}")
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