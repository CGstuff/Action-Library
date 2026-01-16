import bpy
from bpy.types import Panel, UIList
from ..utils.queue_client import animation_queue_client
from ..utils.utils import get_action_keyframe_range, get_action_keyframe_count
from ..utils import icon_loader
from ..preferences.AL_preferences import get_library_path, is_experimental_enabled
from ..operators import ANIMLIB_OT_update_preview
from ..utils.naming_engine import get_naming_engine, FieldValidator


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
    """Main Animation Library panel - Header, status, and launch"""
    bl_label = "Animation Library"
    bl_idname = "ANIMLIB_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'

    def draw_header(self, context):
        """Draw connection status indicator in header"""
        layout = self.layout
        from ..utils.socket_server import is_server_running, get_connected_clients_count

        # Connection status indicator
        row = layout.row(align=True)
        if is_server_running() and get_connected_clients_count() > 0:
            row.label(text="", icon='CHECKMARK')  # Connected
        else:
            row.label(text="", icon='X')  # Not connected

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Library status section
        library_path = get_library_path()

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

        # Desktop App Launch Button - Prominent!
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


class ANIMLIB_PT_capture(Panel):
    """Capture sub-panel - Animation and Pose capture"""
    bl_label = "Capture"
    bl_idname = "ANIMLIB_PT_capture"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'
    bl_parent_id = "ANIMLIB_PT_main_panel"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        library_path = get_library_path()

        armature = context.active_object
        has_animation = (armature and
                        armature.type == 'ARMATURE' and
                        armature.animation_data and
                        armature.animation_data.action)

        # Capture Action Section
        if has_animation:
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

                # Rig Type field (moved from Active Rig section)
                detected_rig_type, confidence = animation_queue_client.detect_rig_type(armature)
                type_row = form_grid.row(align=True)
                type_col = type_row.column()
                type_col.enabled = not scene.animlib_use_detected_rig_type
                type_col.prop(scene, "animlib_rig_type", text="Rig Type")
                type_row.prop(scene, "animlib_use_detected_rig_type", text="", icon='ARMATURE_DATA')

                if scene.animlib_use_detected_rig_type:
                    if detected_rig_type != 'unknown':
                        form_grid.label(text=f"Detected: {detected_rig_type.title()}", icon='INFO')
                    else:
                        form_grid.label(text="Detected: Unknown", icon='INFO')

                form_grid.prop(scene, "animlib_description", icon='TEXT')
                form_grid.prop(scene, "animlib_tags", icon='BOOKMARKS')
                form_grid.prop(scene, "animlib_author", icon='USER')

                # Studio Naming Section
                if library_path:
                    try:
                        naming_engine = get_naming_engine(library_path)
                        if naming_engine.is_studio_mode_enabled:
                            action_details_box.separator()
                            naming_box = action_details_box.box()

                            # Header with toggle
                            naming_header = naming_box.row()
                            naming_header.prop(scene, "animlib_use_studio_naming", text="Studio Naming", icon='FILE_TEXT')

                            if scene.animlib_use_studio_naming:
                                # Show template fields based on what's configured
                                naming_form = naming_box.column(align=True)
                                required_fields = naming_engine.get_required_fields()

                                # Map field names to scene properties (expanded list)
                                field_props = {
                                    # Core fields
                                    'show': 'animlib_naming_show',
                                    'seq': 'animlib_naming_seq',
                                    'sequence': 'animlib_naming_seq',
                                    'shot': 'animlib_naming_shot',
                                    'asset': 'animlib_naming_asset',
                                    'task': 'animlib_naming_task',
                                    'variant': 'animlib_naming_variant',
                                    # Common aliases
                                    'showname': 'animlib_naming_showname',
                                    'project': 'animlib_naming_project',
                                    'character': 'animlib_naming_character',
                                    'char': 'animlib_naming_character',
                                    'episode': 'animlib_naming_episode',
                                    'ep': 'animlib_naming_episode',
                                    'name': 'animlib_naming_asset',
                                    'anim': 'animlib_naming_asset',
                                    'animation': 'animlib_naming_asset',
                                    # Pipeline fields
                                    'assettype': 'animlib_naming_asset',
                                    'dept': 'animlib_naming_task',
                                    'department': 'animlib_naming_task',
                                }

                                # Track which custom fields we've used for unmapped fields
                                custom_field_index = 0
                                custom_fields = ['animlib_naming_custom1', 'animlib_naming_custom2', 'animlib_naming_custom3']
                                unmapped_to_custom = {}

                                # Fields that can use action name
                                asset_field_names = {'asset', 'name', 'anim', 'animation', 'assettype'}

                                # Get action name if toggle is enabled
                                action_name_for_asset = ""
                                if scene.animlib_asset_use_action_name:
                                    armature = context.active_object
                                    if armature and armature.type == 'ARMATURE' and armature.animation_data and armature.animation_data.action:
                                        action_name_for_asset = armature.animation_data.action.name

                                # First pass: collect field data for validation
                                field_data = {}
                                for field_name in required_fields:
                                    prop_name = field_props.get(field_name.lower())
                                    if prop_name and hasattr(scene, prop_name):
                                        # Use action name for asset fields if toggle is enabled
                                        if field_name.lower() in asset_field_names and scene.animlib_asset_use_action_name and action_name_for_asset:
                                            field_data[field_name] = action_name_for_asset
                                        else:
                                            field_data[field_name] = getattr(scene, prop_name, '')
                                    elif field_name in unmapped_to_custom:
                                        custom_prop = unmapped_to_custom[field_name]
                                        field_data[field_name] = getattr(scene, custom_prop, '')
                                    elif custom_field_index < len(custom_fields):
                                        custom_prop = custom_fields[custom_field_index]
                                        unmapped_to_custom[field_name] = custom_prop
                                        field_data[field_name] = getattr(scene, custom_prop, '')
                                        custom_field_index += 1

                                # Also get context-extracted values
                                context_fields = naming_engine.extract_context()
                                for k, v in context_fields.items():
                                    if k not in field_data or not field_data[k]:
                                        field_data[k] = v

                                # Validate all fields
                                validation_results = FieldValidator.validate_all_fields(field_data, required_fields)

                                # Reset custom field index for display
                                custom_field_index = 0

                                # Second pass: display fields with validation indicators
                                for field_name in required_fields:
                                    prop_name = field_props.get(field_name.lower())
                                    is_valid, error_msg = validation_results.get(field_name, (True, ''))
                                    is_asset_field = field_name.lower() in asset_field_names

                                    # Create row with field + validation indicator
                                    field_row = naming_form.row(align=True)

                                    if prop_name and hasattr(scene, prop_name):
                                        # For asset fields, show toggle for "Use Action Name"
                                        if is_asset_field:
                                            sub = field_row.row(align=True)
                                            sub.enabled = not scene.animlib_asset_use_action_name
                                            sub.prop(scene, prop_name, text=field_name.title())
                                            field_row.prop(scene, "animlib_asset_use_action_name", text="", icon='ACTION', toggle=True)
                                        else:
                                            field_row.prop(scene, prop_name, text=field_name.title())
                                    elif field_name in unmapped_to_custom:
                                        custom_prop = unmapped_to_custom[field_name]
                                        field_row.prop(scene, custom_prop, text=field_name.title())
                                    elif custom_field_index < len(custom_fields):
                                        custom_prop = custom_fields[custom_field_index]
                                        unmapped_to_custom[field_name] = custom_prop
                                        field_row.prop(scene, custom_prop, text=field_name.title())
                                        custom_field_index += 1
                                    else:
                                        naming_form.label(text=f"{field_name}: (no slot available)", icon='ERROR')
                                        continue

                                    # Add validation indicator
                                    if is_valid:
                                        field_row.label(text="", icon='CHECKMARK')
                                    else:
                                        field_row.label(text="", icon='ERROR')

                                # Live Preview Box - More prominent
                                naming_box.separator()
                                preview_box = naming_box.box()
                                preview_header = preview_box.row()
                                preview_header.label(text="Live Preview", icon='SYNTAX_ON')

                                try:
                                    version = scene.animlib_version_next_number if scene.animlib_is_versioning else 1
                                    preview_name = naming_engine.generate_name(field_data, version)

                                    # Show the generated name prominently
                                    name_row = preview_box.row()
                                    name_row.scale_y = 1.2
                                    name_row.label(text=preview_name, icon='FILE_TEXT')

                                    # Show validation status
                                    all_valid = all(v[0] for v in validation_results.values())
                                    if all_valid:
                                        status_row = preview_box.row()
                                        status_row.label(text="Ready to capture", icon='CHECKMARK')
                                except ValueError as e:
                                    # Missing fields
                                    missing = [f for f, (valid, _) in validation_results.items() if not valid]
                                    error_row = preview_box.row()
                                    error_row.alert = True
                                    error_row.label(text=f"Fill required: {', '.join(missing)}", icon='ERROR')
                                except Exception:
                                    error_row = preview_box.row()
                                    error_row.label(text="(fill required fields)", icon='ERROR')
                    except Exception:
                        pass  # Naming engine not available, skip section

                # Capture button
                if library_path:
                    # Check if action has library metadata
                    is_library_action = action.get("animlib_imported", False)

                    # Show library action indicator (when action came from library)
                    if is_library_action and not scene.animlib_is_versioning:
                        library_box = action_details_box.box()
                        library_row = library_box.row()
                        library_row.label(text="Library Action Detected", icon='LIBRARY_DATA_DIRECT')

                        source_name = action.get("animlib_name", "Unknown")
                        source_version_label = action.get("animlib_version_label", "v001")

                        library_info = library_box.column(align=True)
                        library_info.label(text=f"Source: {source_name} ({source_version_label})")
                        library_info.label(text="Capture will offer version options", icon='INFO')

                    # Show versioning mode indicator if user already chose to version
                    elif scene.animlib_is_versioning:
                        version_box = action_details_box.box()
                        version_box.alert = True
                        version_row = version_box.row()
                        version_row.label(text="VERSION MODE ACTIVE", icon='FILE_REFRESH')
                        version_info = version_box.column(align=True)
                        version_label = f"v{scene.animlib_version_next_number:03d}"
                        version_info.label(text=f"Base: {scene.animlib_version_source_name}")
                        version_info.label(text=f"Next: {scene.animlib_version_source_name}_{version_label}")

                        # Cancel versioning button
                        cancel_row = version_box.row()
                        cancel_row.operator("animlib.cancel_versioning", text="Cancel Version Mode", icon='X')

                    # Only show button if not currently capturing
                    if not context.window_manager.animlib_is_capturing:
                        capture_row = action_details_box.row()
                        capture_row.scale_y = 1.5
                        if scene.animlib_is_versioning:
                            version_label = f"v{scene.animlib_version_next_number:03d}"
                            capture_row.operator("animlib.capture_animation", text=f"Capture as {version_label}", icon='ACTION')
                        else:
                            capture_row.operator("animlib.capture_animation", text="Capture Action", icon='ACTION')

                        # Capture Selected button (for capturing selected keyframes only)
                        from ..operators.AL_capture_selected import has_selected_keyframes
                        capture_sel_row = action_details_box.row()
                        capture_sel_row.scale_y = 1.2
                        capture_sel_row.enabled = has_selected_keyframes(action)
                        capture_sel_row.operator("animlib.capture_selected", text="Capture Selected", icon='KEYFRAME_HLT')
                    else:
                        # Show status message while capturing
                        status_row = action_details_box.row()
                        status_row.scale_y = 1.5
                        status_row.label(text="Capturing Animation...", icon='SORTTIME')

                    # Update Preview button (only show when not capturing or updating)
                    if not context.window_manager.animlib_is_capturing and not context.window_manager.animlib_is_updating_preview:
                        update_row = action_details_box.row()
                        update_row.scale_y = 1.3

                        # Check if action is from library
                        has_uuid = bool(action.get("animlib_uuid", ""))

                        # Button will be grayed out if action not from library (poll handles this)
                        update_row.operator("animlib.update_preview", text="Update Preview", icon='FILE_REFRESH')

                        # Show hint if action is not from library
                        if not has_uuid:
                            hint_row = action_details_box.row()
                            hint_row.label(text="Only for library animations", icon='INFO')
                    elif context.window_manager.animlib_is_updating_preview:
                        # Show status message while updating
                        status_row = action_details_box.row()
                        status_row.scale_y = 1.3
                        status_row.label(text="Updating Preview...", icon='SORTTIME')
                else:
                    disabled_row = action_details_box.row()
                    disabled_row.label(text="Library Not Configured", icon='ERROR')

        # Pose Capture Section (shows when armature is selected, even without action)
        if armature and armature.type == 'ARMATURE' and library_path:
            layout.separator()
            pose_box = layout.box()
            pose_header = pose_box.row()
            pose_header.label(text="Capture Pose", icon='ARMATURE_DATA')

            # Pose form
            pose_form = pose_box.column(align=True)
            pose_form.prop(scene, "animlib_pose_name", icon='SORTALPHA')
            pose_form.prop(scene, "animlib_selected_bones_only", icon='RESTRICT_SELECT_OFF')

            # Show selected bone count if capturing selected only
            if scene.animlib_selected_bones_only and context.mode == 'POSE':
                selected_bones = context.selected_pose_bones
                if selected_bones:
                    pose_form.label(text=f"Will capture {len(selected_bones)} bones", icon='INFO')
                else:
                    pose_form.label(text="No bones selected!", icon='ERROR')

            # Capture Pose button
            if not context.window_manager.animlib_is_capturing:
                capture_pose_row = pose_box.row()
                capture_pose_row.scale_y = 1.5
                capture_pose_row.operator("animlib.capture_pose", text="Capture Pose", icon='ARMATURE_DATA')
            else:
                status_row = pose_box.row()
                status_row.scale_y = 1.5
                status_row.label(text="Capturing...", icon='SORTTIME')

        # Show message if no armature selected
        if not armature or armature.type != 'ARMATURE':
            layout.separator()
            no_rig_box = layout.box()
            no_rig_box.label(text="Select an armature to capture", icon='INFO')


class ANIMLIB_PT_extra(Panel):
    """Extra sub-panel - Root Motion and Slot Management"""
    bl_label = "Extra"
    bl_idname = "ANIMLIB_PT_extra"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'
    bl_parent_id = "ANIMLIB_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}  # Collapsed by default

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        armature = context.active_object
        has_armature = armature and armature.type == 'ARMATURE'

        # Root Motion Continuity section
        root_motion_box = layout.box()
        root_motion_box.label(text="Root Motion", icon='ORIENTATION_GLOBAL')
        root_motion_box.prop(scene, "animlib_enable_root_motion_continuity")

        # Only show bone picker and axis options if enabled
        if scene.animlib_enable_root_motion_continuity:
            # Bone picker UI - only shown if we have an armature
            if has_armature:
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

            # Location axes
            root_motion_box.label(text="Location:")
            loc_row = root_motion_box.row(align=True)
            loc_row.prop(scene, "animlib_root_motion_loc_x", toggle=True)
            loc_row.prop(scene, "animlib_root_motion_loc_y", toggle=True)
            loc_row.prop(scene, "animlib_root_motion_loc_z", toggle=True)

            # Rotation continuity (single toggle - handles both Euler and Quaternion)
            root_motion_box.prop(scene, "animlib_root_motion_rotation")

            # Show hint about INSERT mode
            hint_row = root_motion_box.row()
            hint_row.label(text="Active in INSERT mode", icon='INFO')

        # Slot Management Section (experimental - only show if enabled in preferences)
        if is_experimental_enabled() and has_armature and armature.animation_data and armature.animation_data.action:
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


# Panel registration list
classes = [
    ANIMLIB_UL_slots,
    ANIMLIB_PT_main_panel,
    ANIMLIB_PT_capture,
    ANIMLIB_PT_extra,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
