import bpy
from bpy.types import Panel, UIList
from ..utils.queue_client import animation_queue_client
from ..utils.utils import get_action_keyframe_range, get_action_keyframe_count
from ..utils import icon_loader
from ..preferences.AL_preferences import get_library_path
from ..operators import ANIMLIB_OT_update_preview


class ANIMLIB_UL_slots(UIList):
    """UIList for displaying Action slots"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Draw each slot in the list"""
        import json

        armature = context.active_object
        if not armature or not armature.animation_data or not armature.animation_data.action:
            return

        action = armature.animation_data.action
        scene = context.scene

        # Get merge selection state (use index as key since ActionSlot has no .name)
        selection_dict = json.loads(scene.animlib_merge_selected_slots or "{}")
        slot_key = str(index)  # Use index as key
        is_merge_selected = selection_dict.get(slot_key, False)

        # Get active slot (which Action is playing)
        active_slot = None
        if hasattr(armature.animation_data, 'action_slot'):
            active_slot = armature.animation_data.action_slot

        # Check if this slot is active (playing)
        is_active = (active_slot == item) if active_slot else (index == 0)

        # Main row for the entire item
        row = layout.row(align=True)

        # Checkbox for merge selection
        checkbox_op = row.operator(
            "animlib.toggle_slot_selection",
            text="",
            icon='CHECKBOX_HLT' if is_merge_selected else 'CHECKBOX_DEHLT',
            emboss=False
        )
        checkbox_op.slot_index = index

        # Draw slot with active indicator
        if is_active:
            row.label(text=f"★ Slot {index + 1}", icon='LAYER_ACTIVE')
        else:
            row.label(text=f"   Slot {index + 1}", icon='LAYER_USED')

        # Inline action buttons
        button_row = row.row(align=True)

        # Activate button (only if not already active)
        if not is_active:
            activate_op = button_row.operator("animlib.activate_slot", text="", icon='PLAY', emboss=False)
            activate_op.slot_index = index

        # Duplicate button
        duplicate_op = button_row.operator("animlib.duplicate_slot", text="", icon='DUPLICATE', emboss=False)
        duplicate_op.slot_index = index

        # Delete button (only if more than one slot)
        if len(action.slots) > 1:
            delete_op = button_row.operator("animlib.delete_slot", text="", icon='TRASH', emboss=False)
            delete_op.slot_index = index


class ANIMLIB_PT_main_panel(Panel):
    """Main Animation Library panel"""
    bl_label = "Animation Library"
    bl_idname = "ANIMLIB_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Library status section
        library_path = get_library_path()

        # Header with library status
        header_row = layout.row(align=True)
        header_row.label(text="Animation Library", icon='ANIM')

        # Status indicator
        status_box = layout.box()
        status_row = status_box.row(align=True)
        if library_path:
            status_row.label(text="Library Ready", icon='CHECKMARK')
            # Compact path display
            if len(library_path) > 40:
                short_path = "..." + library_path[-37:]
            else:
                short_path = library_path
            status_box.label(text=short_path, icon='FILE_FOLDER')
        else:
            status_row.label(text="Not Configured", icon='ERROR')
            op = status_box.operator("preferences.addon_show", text="Open Preferences")
            op.module = __name__.split('.')[0]

        # 1. Desktop App Launch Button - Prominent!
        layout.separator()
        launch_box = layout.box()
        launch_row = launch_box.row()
        launch_row.scale_y = 2.0

        # Use custom icon if available, otherwise fall back to default
        icon_id = icon_loader.get_icon_id(icon_loader.Icons.LAUNCH_APP)
        if icon_id:
            launch_row.operator("animlib.launch_desktop_app", text="Launch Desktop App", icon_value=icon_id)
        else:
            launch_row.operator("animlib.launch_desktop_app", text="Launch Desktop App", icon='PLAY')

        # Show quick settings access
        settings_row = launch_box.row()
        settings_row.scale_y = 1.2
        op = settings_row.operator("preferences.addon_show", text="Configure Launch Settings", icon='PREFERENCES')
        op.module = __name__.split('.')[0]

        # 2. Collapsible Action Details Section
        armature = context.active_object
        has_animation = (armature and
                        armature.type == 'ARMATURE' and
                        armature.animation_data and
                        armature.animation_data.action)

        if has_animation:
            layout.separator()
            action_details_box = layout.box()

            # Collapsible header - show armature name so user knows which rig will be captured
            header_row = action_details_box.row()
            icon = 'DOWNARROW_HLT' if scene.animlib_show_action_details else 'RIGHTARROW'
            header_row.prop(scene, "animlib_show_action_details", text=f"Capture from: {armature.name}", icon=icon, emboss=False)

            # Show content only if expanded
            if scene.animlib_show_action_details:
                action = armature.animation_data.action

                # Current Action info
                info_grid = action_details_box.column(align=True)
                info_grid.label(text=f"Action: {action.name}", icon='ACTION')

                # Get keyframe range
                keyframe_start, keyframe_end = get_action_keyframe_range(action)

                if keyframe_start is not None and keyframe_end is not None:
                    info_grid.label(text=f"Frames: {keyframe_start}-{keyframe_end}", icon='KEYFRAME_HLT')
                    duration = (keyframe_end - keyframe_start + 1) / scene.render.fps
                    info_grid.label(text=f"Duration: {duration:.2f}s", icon='TIME')
                    kf_count = get_action_keyframe_count(action)
                    info_grid.label(text=f"Keyframes: {kf_count}", icon='KEYFRAME')
                else:
                    info_grid.label(text="No keyframes found", icon='ERROR')

                action_details_box.separator()

                # Capture form
                form_grid = action_details_box.column(align=True)

                # Action name with toggle
                name_row = form_grid.row(align=True)
                name_col = name_row.column()
                name_col.enabled = not scene.animlib_use_action_name
                name_col.prop(scene, "animlib_animation_name", icon='SORTALPHA')
                name_row.prop(scene, "animlib_use_action_name", text="", icon='ACTION')

                if scene.animlib_use_action_name:
                    form_grid.label(text=f"Will use: {action.name}", icon='INFO')

                form_grid.prop(scene, "animlib_description", icon='TEXT')
                form_grid.prop(scene, "animlib_tags", icon='BOOKMARKS')
                form_grid.prop(scene, "animlib_author", icon='USER')

                # Capture button
                if library_path:
                    # Only show button if not currently capturing
                    if not context.window_manager.animlib_is_capturing:
                        capture_row = action_details_box.row()
                        capture_row.scale_y = 1.5
                        capture_row.operator("animlib.capture_animation", text="Capture Action", icon='REC')
                    else:
                        # Show status message while capturing
                        status_row = action_details_box.row()
                        status_row.scale_y = 1.5
                        status_row.label(text="Capturing Animation...", icon='SORTTIME')

                    # Update Preview button (only show when not capturing or updating)
                    if not context.window_manager.animlib_is_capturing and not context.window_manager.animlib_is_updating_preview:
                        update_row = action_details_box.row()
                        update_row.scale_y = 1.3

                        # Check if desktop app is running
                        is_connected = ANIMLIB_OT_update_preview.is_server_available()

                        # Button will be grayed out if desktop app not running (poll handles this)
                        update_row.operator("animlib.update_preview", text="Update Preview", icon='FILE_REFRESH')

                        # Show hint if not connected
                        if not is_connected:
                            hint_row = action_details_box.row()
                            hint_row.label(text="Desktop app not running", icon='INFO')
                    elif context.window_manager.animlib_is_updating_preview:
                        # Show status message while updating
                        status_row = action_details_box.row()
                        status_row.scale_y = 1.3
                        status_row.label(text="Updating Preview...", icon='SORTTIME')
                else:
                    disabled_row = action_details_box.row()
                    disabled_row.label(text="Library Not Configured", icon='ERROR')

        # 3. Collapsible Desktop Integration Section
        layout.separator()
        integration_box = layout.box()

        # Collapsible header
        header_row = integration_box.row()
        icon = 'DOWNARROW_HLT' if scene.animlib_show_desktop_integration else 'RIGHTARROW'
        header_row.prop(scene, "animlib_show_desktop_integration", text="Desktop Integration", icon=icon, emboss=False)

        # Show content only if expanded
        if scene.animlib_show_desktop_integration:
            # Auto-apply status indicator
            status_row = integration_box.row()
            status_row.label(text="Auto-Apply: Active", icon='CHECKMARK')

            # Note about options controlled by desktop app
            options_row = integration_box.row()
            options_row.label(text="Options set in Desktop App", icon='SETTINGS')

            # Manual apply button (backup if auto-apply misses something)
            apply_row = integration_box.row()
            apply_row.scale_y = 1.2
            apply_row.operator("animlib.check_apply_queue", text="Manual Apply", icon='IMPORT')

            # Show selected bones info if "Selected Bones Only" is enabled in desktop app
            if armature and armature.type == 'ARMATURE' and context.mode == 'POSE':
                selected_bones = context.selected_pose_bones
                if selected_bones:
                    bone_info = integration_box.column(align=True)
                    bone_info.label(text=f"Selected bones: {len(selected_bones)}", icon='BONE_DATA')
                    if len(selected_bones) <= 2:
                        bone_names = ", ".join([b.name for b in selected_bones])
                        bone_info.label(text=f"  {bone_names}")
                    else:
                        first_bone = selected_bones[0].name
                        bone_info.label(text=f"  {first_bone} (+{len(selected_bones)-1} more)")

            # Root Motion Continuity section (INSERT mode specific - stays in Blender)
            integration_box.separator()
            root_motion_box = integration_box.box()
            root_motion_box.prop(scene, "animlib_enable_root_motion_continuity", icon='ORIENTATION_GLOBAL')

            # Only show bone picker and axis options if enabled
            if scene.animlib_enable_root_motion_continuity:
                # Bone picker UI - only shown if we have an armature
                if armature and armature.type == 'ARMATURE':
                    root_motion_box.prop_search(
                        scene, "animlib_root_bone_name",
                        armature.pose, "bones",
                        text="Root Bone",
                        icon='BONE_DATA'
                    )

                    # Show validation indicator
                    if scene.animlib_root_bone_name in armature.pose.bones:
                        info_row = root_motion_box.row()
                        info_row.label(text=f"Using: {scene.animlib_root_bone_name}", icon='CHECKMARK')
                    else:
                        warning_row = root_motion_box.row()
                        warning_row.label(text="Bone not found in rig", icon='ERROR')
                else:
                    root_motion_box.label(text="Select armature to choose bone", icon='INFO')

                # Axis selection
                root_motion_box.label(text="Apply to Axes:")
                axis_row = root_motion_box.row(align=True)
                axis_row.prop(scene, "animlib_root_motion_x", toggle=True)
                axis_row.prop(scene, "animlib_root_motion_y", toggle=True)
                axis_row.prop(scene, "animlib_root_motion_z", toggle=True)

                # Show hint about INSERT mode
                hint_row = root_motion_box.row()
                hint_row.label(text="Active in INSERT mode", icon='INFO')

            # Quick usage tips
            integration_box.separator()
            tips_column = integration_box.column(align=True)
            tips_column.label(text="Usage:", icon='INFO')
            tips_column.label(text="  1. Select armature in Blender")
            tips_column.label(text="  2. Double-click animation in app")
            tips_column.label(text="  3. Animation auto-applies!")

        # Current rig info section
        armature = context.active_object
        if armature and armature.type == 'ARMATURE':
            layout.separator()
            detected_rig_type, confidence = animation_queue_client.detect_rig_type(armature)

            rig_box = layout.box()
            # Header with rig icon
            rig_header = rig_box.row(align=True)
            rig_header.label(text="Active Rig", icon='ARMATURE_DATA')

            # Rig details in a clean grid
            rig_grid = rig_box.column(align=True)

            # Rig type override row (similar to action name)
            type_row = rig_grid.row(align=True)
            type_col = type_row.column()
            type_col.enabled = not scene.animlib_use_detected_rig_type
            type_col.prop(scene, "animlib_rig_type", text="Type")
            type_row.prop(scene, "animlib_use_detected_rig_type", text="", icon='ARMATURE_DATA')

            # Show detected type as reference
            detected_row = rig_grid.row(align=True)
            if detected_rig_type != 'unknown':
                detected_row.label(text=f"Detected: {detected_rig_type.title()}", icon='CHECKMARK')
            else:
                detected_row.label(text="Detected: Unknown", icon='QUESTION')

            # Bone count
            bone_row = rig_grid.row(align=True)
            bone_row.label(text=f"{len(armature.data.bones)} Bones", icon='BONE_DATA')

            # Confidence indicator (only if not unknown)
            if detected_rig_type != 'unknown':
                conf_row = rig_grid.row(align=True)
                if confidence > 0.8:
                    conf_row.label(text=f"High Confidence ({confidence:.1f})", icon='CHECKMARK')
                elif confidence > 0.5:
                    conf_row.label(text=f"Medium Confidence ({confidence:.1f})", icon='REMOVE')
                else:
                    conf_row.label(text=f"Low Confidence ({confidence:.1f})", icon='ERROR')

        # Slot Management Section (only show if action has slots)
        if armature and armature.animation_data and armature.animation_data.action:
            action = armature.animation_data.action
            if hasattr(action, 'slots') and len(action.slots) > 0:
                layout.separator()
                slot_box = layout.box()
                slot_header = slot_box.row(align=True)
                slot_header.label(text="Slot Management", icon='DOCUMENTS')

                # Show action name
                slot_box.label(text=f"Action: {action.name}", icon='ACTION')

                # UIList for slots
                row = slot_box.row()
                row.template_list(
                    "ANIMLIB_UL_slots",  # UIList type
                    "",  # list_id
                    action,  # data containing the collection
                    "slots",  # property name of the collection
                    scene,  # data containing the active index
                    "animlib_active_slot_index"  # property name for active index
                )

                # Selection controls
                if len(action.slots) > 1:
                    import json

                    slot_box.separator()

                    # Select All / Deselect All buttons
                    select_row = slot_box.row(align=True)
                    select_row.operator("animlib.select_all_slots", text="Select All", icon='CHECKBOX_HLT')
                    select_row.operator("animlib.deselect_all_slots", text="Deselect All", icon='CHECKBOX_DEHLT')

                    # Selection counter
                    selection_dict = json.loads(scene.animlib_merge_selected_slots or "{}")
                    selected_count = sum(1 for v in selection_dict.values() if v)
                    slot_box.label(text=f"Selected: {selected_count}/{len(action.slots)}", icon='INFO')

                    # Merge options
                    slot_box.prop(scene, "animlib_merge_mode", text="Merge Mode")
                    slot_box.prop(scene, "animlib_merge_include_unique", text="Include Unique FCurves")

                    # Merge button (enabled only when 2+ selected)
                    merge_enabled = selected_count >= 2
                    merge_row = slot_box.row()
                    merge_row.enabled = merge_enabled
                    merge_row.scale_y = 1.3
                    merge_row.operator("animlib.merge_slots", text="Merge Selected Slots", icon='UGLYPACKAGE')