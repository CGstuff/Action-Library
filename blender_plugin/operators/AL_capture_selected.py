import bpy
import os
import re
import shutil
import subprocess
import json
import tempfile
import glob
import uuid as uuid_module
from pathlib import Path
from datetime import datetime
from bpy.types import Operator
from bpy.props import StringProperty
from ..utils.queue_client import animation_queue_client
from ..utils.utils import (
    get_action_fcurves, new_action_fcurve, init_action_for_blender_5,
    get_active_armature, has_animation_data, safe_report_error,
    get_action_keyframe_range, BLENDER_5_0_OR_LATER
)
from ..utils.logger import get_logger
from ..utils.naming_engine import get_naming_engine
from ..preferences import get_library_path, get_preview_settings

# Initialize logger
logger = get_logger()


def get_selected_keyframe_range(action):
    """
    Find min/max frame of selected keyframes across all fcurves.

    Args:
        action: Blender action to check

    Returns:
        (min_frame, max_frame) tuple, or (None, None) if no selection
    """
    min_frame, max_frame = None, None

    for fcurve in get_action_fcurves(action):
        if not fcurve.keyframe_points:
            continue
        for kp in fcurve.keyframe_points:
            if kp.select_control_point:
                frame = int(kp.co[0])
                if min_frame is None or frame < min_frame:
                    min_frame = frame
                if max_frame is None or frame > max_frame:
                    max_frame = frame

    return min_frame, max_frame


def has_selected_keyframes(action):
    """Check if action has any selected keyframes."""
    for fcurve in get_action_fcurves(action):
        if not fcurve.keyframe_points:
            continue
        for kp in fcurve.keyframe_points:
            if kp.select_control_point:
                return True
    return False


def create_action_from_selection(source_action, selection_start, selection_end, action_name):
    """
    Create a new action containing only selected keyframes, shifted to start at frame 1.

    Args:
        source_action: Source action to copy from
        selection_start: First frame of selection
        selection_end: Last frame of selection
        action_name: Name for the new action

    Returns:
        New Blender action with selected keyframes
    """
    # Create new action
    new_action = bpy.data.actions.new(name=action_name)

    # Initialize for Blender 5.0+ if needed
    if BLENDER_5_0_OR_LATER:
        init_action_for_blender_5(new_action, slot_name="Slot")

    # Calculate frame offset to shift keyframes to start at frame 1
    frame_offset = selection_start - 1

    # Copy selected keyframes from each fcurve
    for src_fcurve in get_action_fcurves(source_action):
        if not src_fcurve.keyframe_points:
            continue

        # Check if this fcurve has any selected keyframes
        has_selected = any(kp.select_control_point for kp in src_fcurve.keyframe_points)
        if not has_selected:
            continue

        # Get the group name if available
        group_name = src_fcurve.group.name if src_fcurve.group else None

        # Create corresponding fcurve in new action
        new_fcurve = new_action_fcurve(
            new_action,
            src_fcurve.data_path,
            src_fcurve.array_index,
            group_name=group_name
        )

        if not new_fcurve:
            logger.warning(f"Failed to create fcurve: {src_fcurve.data_path}[{src_fcurve.array_index}]")
            continue

        # Copy selected keyframes with shifted frame numbers
        for kp in src_fcurve.keyframe_points:
            if kp.select_control_point:
                new_frame = int(kp.co[0]) - frame_offset
                new_kp = new_fcurve.keyframe_points.insert(new_frame, kp.co[1], options={'FAST'})
                # Copy keyframe properties
                new_kp.interpolation = kp.interpolation
                new_kp.easing = kp.easing
                if hasattr(kp, 'handle_left_type'):
                    new_kp.handle_left_type = kp.handle_left_type
                    new_kp.handle_right_type = kp.handle_right_type
                    new_kp.handle_left = (kp.handle_left[0] - frame_offset, kp.handle_left[1])
                    new_kp.handle_right = (kp.handle_right[0] - frame_offset, kp.handle_right[1])

        new_fcurve.update()

    logger.info(f"Created action '{action_name}' with keyframes shifted from {selection_start}-{selection_end} to 1-{selection_end - selection_start + 1}")
    return new_action


class ANIMLIB_OT_capture_selected(Operator):
    """Create a new animation from selected keyframes"""
    bl_idname = "animlib.capture_selected"
    bl_label = "Capture Selected Keyframes"
    bl_description = "Create a new animation from selected keyframes in the current action"

    # Modal operator state tracking
    _timer = None
    _state = None
    _context_data = None
    _start_time = None
    _last_activity_time = None

    # Timeout configuration (in seconds)
    MODAL_TIMEOUT = 300  # 5 minutes total timeout
    STATE_TIMEOUT = 60   # 1 minute per state (watchdog)

    @classmethod
    def poll(cls, context):
        """Check if operator can run"""
        armature = get_active_armature(context)
        if not armature or not has_animation_data(armature):
            return False

        action = armature.animation_data.action if armature.animation_data else None
        if not action:
            return False

        # Check for selected keyframes
        return has_selected_keyframes(action)

    def invoke(self, context, event):
        """Start the capture operation"""
        scene = context.scene
        armature = get_active_armature(context)

        if not armature or not armature.animation_data or not armature.animation_data.action:
            safe_report_error(self, "No action found on armature")
            return {'CANCELLED'}

        action = armature.animation_data.action

        # Get selected keyframe range
        sel_start, sel_end = get_selected_keyframe_range(action)
        if sel_start is None:
            safe_report_error(self, "No keyframes selected. Select keyframes in Dopesheet or Graph Editor.")
            return {'CANCELLED'}

        # Store context data
        self._context_data = {
            'scene': scene,
            'armature': armature,
            'source_action': action,
            'selection_start': sel_start,
            'selection_end': sel_end,
        }

        # Check naming mode - use scene properties from Extra panel
        library_path = get_library_path()
        naming_engine = get_naming_engine(library_path)

        if scene.animlib_use_studio_naming and naming_engine.is_studio_mode_enabled:
            # Studio naming mode - use naming engine
            self._context_data['use_studio_naming'] = True
            self._context_data['naming_engine'] = naming_engine
        else:
            # Simple naming mode - use scene properties
            self._context_data['use_studio_naming'] = False

        # Start modal immediately (no popup - fields are in Extra panel)
        return self._start_modal(context)

    def _start_modal(self, context):
        """Start the modal execution"""
        import time

        wm = context.window_manager

        # Set capturing flag
        wm.animlib_is_capturing = True
        self._context_data['wm'] = wm

        # Initialize state machine
        self._state = 'DETERMINE_NAME'

        # Initialize timeout tracking
        self._start_time = time.time()
        self._last_activity_time = time.time()

        # Add timer for modal updates
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        # Force UI update
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        logger.info(f"Starting capture selected: frames {self._context_data['selection_start']}-{self._context_data['selection_end']}")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        """Handle modal execution"""
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        import time

        # Timeout watchdog - prevent indefinite hangs
        current_time = time.time()

        # Check total operation timeout
        if self._start_time and (current_time - self._start_time) > self.MODAL_TIMEOUT:
            logger.error(f"Capture selected timed out after {self.MODAL_TIMEOUT}s")
            self.report({'ERROR'}, "Capture timed out - operation took too long")
            self.cleanup(context)
            return {'CANCELLED'}

        # Check state timeout (watchdog for stuck states)
        if self._last_activity_time and (current_time - self._last_activity_time) > self.STATE_TIMEOUT:
            logger.error(f"Capture selected stuck in state '{self._state}' for {self.STATE_TIMEOUT}s")
            self.report({'ERROR'}, f"Capture stuck in '{self._state}' - cancelling")
            self.cleanup(context)
            return {'CANCELLED'}

        wm = self._context_data['wm']
        scene = self._context_data['scene']

        try:
            if self._state == 'DETERMINE_NAME':
                # Determine animation name from scene properties (same as normal capture)
                source_action = self._context_data['source_action']

                if self._context_data.get('use_studio_naming'):
                    # Studio naming mode
                    naming_engine = self._context_data.get('naming_engine')
                    try:
                        field_data = self._collect_naming_fields(scene, naming_engine)
                        context_fields = naming_engine.extract_context()
                        for key, value in context_fields.items():
                            if key not in field_data or not field_data[key]:
                                field_data[key] = value

                        # Always v001 for new capture
                        animation_name = naming_engine.generate_name(field_data, version=1)
                        self._context_data['animation_name'] = animation_name
                        self._context_data['naming_fields'] = field_data
                        logger.info(f"Studio naming: {animation_name}")
                    except ValueError as e:
                        logger.warning(f"Studio naming failed: {e}")
                        safe_report_error(self, f"Naming failed: {e}. Please fill required fields.")
                        self.cleanup(context)
                        return {'CANCELLED'}
                else:
                    # Simple naming mode - use scene properties from Extra panel
                    if scene.animlib_use_action_name and source_action.name:
                        animation_name = source_action.name
                    else:
                        animation_name = scene.animlib_animation_name

                    if not animation_name.strip():
                        safe_report_error(self, "Please enter an animation name in the panel")
                        self.cleanup(context)
                        return {'CANCELLED'}

                    self._context_data['animation_name'] = animation_name.strip()
                    logger.info(f"Simple naming: {animation_name}")

                self._state = 'CHECK_COLLISION'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'CHECK_COLLISION':
                # Check if animation with same base name exists
                animation_name = self._context_data['animation_name']

                from pathlib import Path
                from ..preferences import get_library_path
                library_path = get_library_path()

                if library_path:
                    base_name = self._strip_version_suffix(animation_name)
                    safe_base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
                    safe_base_name = safe_base_name.strip(' .')
                    safe_base_name = re.sub(r'_+', '_', safe_base_name) or 'unnamed'

                    library_dir = Path(library_path)
                    existing_folder = library_dir / "library" / "actions" / safe_base_name

                    if existing_folder.exists() and any(existing_folder.iterdir()):
                        logger.error(f"Collision: folder '{safe_base_name}' already exists")
                        self.report({'ERROR'}, f"Animation '{base_name}' already exists! Please choose a different name.")
                        self.cleanup(context)
                        return {'CANCELLED'}

                self._state = 'CREATE_ACTION'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'CREATE_ACTION':
                # Create new action from selected keyframes
                source_action = self._context_data['source_action']
                sel_start = self._context_data['selection_start']
                sel_end = self._context_data['selection_end']
                animation_name = self._context_data['animation_name']

                new_action = create_action_from_selection(
                    source_action, sel_start, sel_end, animation_name
                )

                if not new_action:
                    self.report({'ERROR'}, "Failed to create action from selection")
                    self.cleanup(context)
                    return {'CANCELLED'}

                self._context_data['new_action'] = new_action
                self._state = 'DETECT_RIG'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'DETECT_RIG':
                # Get rig type from scene properties (same as normal capture)
                armature = self._context_data['armature']

                if scene.animlib_use_detected_rig_type:
                    # Auto-detect rig type
                    detected_rig_type, confidence = animation_queue_client.detect_rig_type(armature)
                    rig_type = detected_rig_type
                    if rig_type == 'unknown':
                        self.report({'WARNING'}, f"Could not detect rig type (confidence: {confidence:.2f})")
                else:
                    # Use manual rig type from panel - strip whitespace and default to 'custom'
                    rig_type = scene.animlib_rig_type.strip()
                    if not rig_type:
                        rig_type = 'custom'
                    self.report({'INFO'}, f"Using custom rig type: {rig_type}")

                self._context_data['rig_type'] = rig_type
                logger.info(f"Rig type: {rig_type}")

                self._state = 'SAVE_ACTION'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'SAVE_ACTION':
                # Save action to library
                new_action = self._context_data['new_action']
                animation_name = self._context_data['animation_name']
                rig_type = self._context_data['rig_type']
                armature = self._context_data['armature']

                # Build naming info if studio mode
                naming_info = None
                if self._context_data.get('naming_fields'):
                    naming_info = {
                        'naming_fields': self._context_data['naming_fields'],
                        'naming_template': ''
                    }

                # Save to library using our own implementation
                blend_file_path, json_file_path, saved_metadata = self.save_action_to_library(
                    new_action, animation_name, rig_type, scene, armature,
                    version_info=None,  # Always v001
                    naming_info=naming_info
                )

                if not blend_file_path:
                    self.report({'ERROR'}, "Failed to save animation to library")
                    self.cleanup(context)
                    return {'CANCELLED'}

                self._context_data['saved_metadata'] = saved_metadata
                self._state = 'CLEANUP'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'CLEANUP':
                # Update the new action with library metadata
                new_action = self._context_data['new_action']
                saved_metadata = self._context_data.get('saved_metadata', {})

                if saved_metadata:
                    # Mark action as from library
                    # Use explicit string conversion to avoid ID property type errors in Blender 5.0
                    new_action["animlib_imported"] = True
                    new_action["animlib_uuid"] = str(saved_metadata.get('id', '') or '')
                    new_action["animlib_version_group_id"] = str(saved_metadata.get('version_group_id', saved_metadata.get('id', '')) or '')
                    new_action["animlib_version"] = int(saved_metadata.get('version', 1) or 1)
                    new_action["animlib_version_label"] = str(saved_metadata.get('version_label', 'v001') or 'v001')
                    new_action["animlib_name"] = str(saved_metadata.get('name', '') or '')
                    new_action["animlib_rig_type"] = str(saved_metadata.get('rig_type', '') or '')

                animation_name = self._context_data['animation_name']
                sel_start = self._context_data['selection_start']
                sel_end = self._context_data['selection_end']

                self.report({'INFO'}, f"Captured '{animation_name}' from frames {sel_start}-{sel_end}")
                self.cleanup(context)
                return {'FINISHED'}

            else:
                logger.error(f"Unknown state: {self._state}")
                self.cleanup(context)
                return {'CANCELLED'}

        except Exception as e:
            logger.error(f"Error during capture selected: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.report({'ERROR'}, f"Capture failed: {e}")
            self.cleanup(context)
            return {'CANCELLED'}

    def cleanup(self, context):
        """Clean up modal operation"""
        wm = context.window_manager

        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None

        wm.animlib_is_capturing = False

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        self._state = None
        self._context_data = None
        self._start_time = None
        self._last_activity_time = None

    def cancel(self, context):
        """Handle cancellation"""
        self.report({'INFO'}, "Capture cancelled")
        self.cleanup(context)

    def _strip_version_suffix(self, name: str) -> str:
        """Strip version suffix like _v001 from name"""
        pattern = r'_v\d{1,4}$'
        return re.sub(pattern, '', name)

    def _collect_naming_fields(self, scene, naming_engine=None) -> dict:
        """Collect naming field values from scene properties."""
        fields = {}

        field_props = {
            'show': 'animlib_naming_show',
            'seq': 'animlib_naming_seq',
            'sequence': 'animlib_naming_seq',
            'shot': 'animlib_naming_shot',
            'asset': 'animlib_naming_asset',
            'task': 'animlib_naming_task',
            'variant': 'animlib_naming_variant',
            'showname': 'animlib_naming_showname',
            'project': 'animlib_naming_project',
            'character': 'animlib_naming_character',
            'char': 'animlib_naming_character',
            'episode': 'animlib_naming_episode',
            'ep': 'animlib_naming_episode',
            'name': 'animlib_naming_asset',
            'anim': 'animlib_naming_asset',
            'animation': 'animlib_naming_asset',
        }

        asset_field_names = {'asset', 'name', 'anim', 'animation', 'assettype'}
        use_action_name = getattr(scene, 'animlib_asset_use_action_name', False)
        action_name = ""
        if use_action_name and self._context_data:
            source_action = self._context_data.get('source_action')
            if source_action:
                action_name = source_action.name

        custom_fields = ['animlib_naming_custom1', 'animlib_naming_custom2', 'animlib_naming_custom3']

        if naming_engine:
            required_fields = naming_engine.get_required_fields()
            custom_field_index = 0

            for field_name in required_fields:
                field_lower = field_name.lower()
                prop_name = field_props.get(field_lower)

                if prop_name and hasattr(scene, prop_name):
                    if field_lower in asset_field_names and use_action_name and action_name:
                        fields[field_name] = action_name.strip()
                    else:
                        value = getattr(scene, prop_name, '')
                        if value:
                            fields[field_name] = value.strip()
                elif custom_field_index < len(custom_fields):
                    custom_prop = custom_fields[custom_field_index]
                    value = getattr(scene, custom_prop, '')
                    if value:
                        fields[field_name] = value.strip()
                    custom_field_index += 1
        else:
            for field_name, prop_name in field_props.items():
                if field_name.lower() in asset_field_names and use_action_name and action_name:
                    fields[field_name] = action_name.strip()
                else:
                    value = getattr(scene, prop_name, '')
                    if value:
                        fields[field_name] = value.strip()

        return fields

    def save_action_to_library(self, action, animation_name, rig_type, scene, armature, version_info=None, naming_info=None):
        """Save action to library .blend file and create JSON metadata"""
        try:
            library_path = get_library_path()
            if not library_path:
                logger.error("No library path set in preferences")
                return None, None, None

            library_dir = Path(library_path)

            # Create unique animation ID
            animation_id = str(uuid_module.uuid4())

            # Get base name without version suffix for folder name
            base_name = self._strip_version_suffix(animation_name)
            safe_base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
            safe_base_name = safe_base_name.strip(' .')
            safe_base_name = re.sub(r'_+', '_', safe_base_name) or 'unnamed'

            # Sanitize animation name for filename
            safe_anim_name = re.sub(r'[<>:"/\\|?*]', '_', animation_name)
            safe_anim_name = safe_anim_name.strip(' .')
            safe_anim_name = re.sub(r'_+', '_', safe_anim_name) or 'unnamed'

            # Create animation folder: library/actions/{base_name}/
            animation_folder = library_dir / "library" / "actions" / safe_base_name
            animation_folder.mkdir(parents=True, exist_ok=True)

            # File paths
            blend_path = animation_folder / f"{safe_anim_name}.blend"
            json_path = animation_folder / f"{safe_anim_name}.json"
            preview_path = animation_folder / f"{safe_anim_name}.webm"
            thumbnail_path = animation_folder / f"{safe_anim_name}.png"

            # Create minimal blend file with just the action
            temp_fd, temp_path = tempfile.mkstemp(suffix='.blend')
            os.close(temp_fd)
            bpy.data.libraries.write(temp_path, {action}, compress=True)
            shutil.move(temp_path, str(blend_path))

            # Get keyframe range from the new action (shifted to start at 1)
            keyframe_start, keyframe_end = get_action_keyframe_range(action)
            if keyframe_start is None or keyframe_end is None:
                keyframe_start = 1
                keyframe_end = 1

            # Render thumbnail and preview from the ORIGINAL selection range
            # (visually identical to the new action, but simpler - no action swapping needed)
            # selection_start/end are passed in from the operator's context
            sel_start = self._context_data['selection_start']
            sel_end = self._context_data['selection_end']

            self.create_thumbnail(armature, scene, str(thumbnail_path), sel_start)
            self.create_animation_preview(armature, scene, str(preview_path), sel_start, sel_end)

            # Get bone info
            bone_names = [bone.name for bone in armature.data.bones]
            tags = [tag.strip() for tag in scene.animlib_tags.split(',') if tag.strip()]

            # Version group ID
            final_version_group_id = animation_id

            # Create metadata
            metadata = {
                'id': animation_id,
                'app_version': '1.3.0',  # Prevents legacy detection by desktop app scanner
                'name': animation_name,
                'description': scene.animlib_description,
                'author': scene.animlib_author,
                'tags': tags,
                'rig_type': rig_type,
                'armature_name': armature.name,
                'bone_count': len(bone_names),
                'bone_names': bone_names,
                'action_name': action.name,
                'frame_start': keyframe_start,
                'frame_end': keyframe_end,
                'frame_count': keyframe_end - keyframe_start + 1,
                'duration_seconds': (keyframe_end - keyframe_start + 1) / scene.render.fps,
                'fps': scene.render.fps,
                'json_file_path': str(json_path),
                'blend_file_path': str(blend_path),
                'preview_path': str(preview_path),
                'thumbnail_path': str(thumbnail_path),
                'created_date': datetime.now().isoformat(),
                'file_size_mb': blend_path.stat().st_size / (1024 * 1024),
                'version': 1,
                'version_label': 'v001',
                'version_group_id': final_version_group_id,
                'is_latest': 1,
                'naming_fields': json.dumps(naming_info.get('naming_fields', {})) if naming_info else None,
                'naming_template': naming_info.get('naming_template', '') if naming_info else None
            }

            # Save JSON metadata
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved animation: {blend_path}")
            return str(blend_path), str(json_path), metadata

        except Exception as e:
            logger.error(f"Error saving action to library: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None, None

    def create_thumbnail(self, armature, scene, thumbnail_path, first_frame):
        """Create thumbnail from first frame"""
        try:
            prefs = get_preview_settings()

            # Store original settings
            original_filepath = scene.render.filepath
            original_format = scene.render.image_settings.file_format
            original_color_mode = scene.render.image_settings.color_mode
            original_frame = scene.frame_current
            original_resolution_x = scene.render.resolution_x
            original_resolution_y = scene.render.resolution_y
            original_resolution_percentage = scene.render.resolution_percentage
            original_film_transparent = scene.render.film_transparent
            viewport_settings = None

            original_media_type = None
            if hasattr(scene.render.image_settings, 'media_type'):
                original_media_type = scene.render.image_settings.media_type

            try:
                scene.frame_set(first_frame)

                if hasattr(scene.render.image_settings, 'media_type'):
                    scene.render.image_settings.media_type = 'IMAGE'
                scene.render.image_settings.file_format = 'PNG'
                scene.render.image_settings.color_mode = 'RGBA'
                scene.render.filepath = thumbnail_path
                scene.render.resolution_x = prefs['resolution_x']
                scene.render.resolution_y = prefs['resolution_y']
                scene.render.resolution_percentage = 100
                scene.render.film_transparent = True

                viewport_settings = self.setup_viewport_for_preview(scene, prefs, transparent_bg=True)
                bpy.ops.render.opengl(write_still=True)
                logger.debug(f"Created thumbnail: {thumbnail_path}")

            finally:
                self.restore_viewport_settings(viewport_settings)
                scene.render.filepath = original_filepath
                if original_media_type and hasattr(scene.render.image_settings, 'media_type'):
                    scene.render.image_settings.media_type = original_media_type
                scene.render.image_settings.file_format = original_format
                scene.render.image_settings.color_mode = original_color_mode
                scene.frame_set(original_frame)
                scene.render.resolution_x = original_resolution_x
                scene.render.resolution_y = original_resolution_y
                scene.render.resolution_percentage = original_resolution_percentage
                scene.render.film_transparent = original_film_transparent

        except Exception as e:
            logger.error(f"Error creating thumbnail: {e}")

    def create_animation_preview(self, armature, scene, preview_path, keyframe_start, keyframe_end):
        """Create preview video"""
        try:
            prefs = get_preview_settings()

            original_filepath = scene.render.filepath
            original_format = scene.render.image_settings.file_format
            original_frame_start = scene.frame_start
            original_frame_end = scene.frame_end
            original_resolution_x = scene.render.resolution_x
            original_resolution_y = scene.render.resolution_y
            original_resolution_percentage = scene.render.resolution_percentage
            original_film_transparent = scene.render.film_transparent
            viewport_settings = None

            original_media_type = None
            if hasattr(scene.render.image_settings, 'media_type'):
                original_media_type = scene.render.image_settings.media_type

            try:
                use_ffmpeg_direct = False
                has_media_type = hasattr(scene.render.image_settings, 'media_type')

                try:
                    if has_media_type:
                        scene.render.image_settings.media_type = 'VIDEO'
                    scene.render.image_settings.file_format = 'FFMPEG'
                    scene.render.ffmpeg.format = 'WEBM'
                    scene.render.ffmpeg.codec = 'WEBM'
                    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
                    scene.render.ffmpeg.audio_codec = 'NONE'
                    scene.render.filepath = str(preview_path).replace('.webm', '')
                    use_ffmpeg_direct = True
                except (TypeError, AttributeError):
                    if has_media_type:
                        scene.render.image_settings.media_type = 'IMAGE'
                    scene.render.image_settings.file_format = 'PNG'
                    scene.render.filepath = str(preview_path).replace('.webm', '_frame_####')
                    use_ffmpeg_direct = False

                scene.render.resolution_x = prefs['resolution_x']
                scene.render.resolution_y = prefs['resolution_y']
                scene.render.resolution_percentage = 100
                scene.render.film_transparent = False

                viewport_settings = self.setup_viewport_for_preview(scene, prefs)
                self.render_keyframe_range(scene, keyframe_start, keyframe_end)

                # Handle output files
                preview_path_obj = Path(preview_path)
                parent_dir = preview_path_obj.parent
                base_name = preview_path_obj.stem

                if use_ffmpeg_direct:
                    pattern = str(parent_dir / f"{base_name}*.webm")
                    rendered_files = glob.glob(pattern)
                    if rendered_files:
                        for actual_file in rendered_files:
                            if actual_file != str(preview_path):
                                if os.path.exists(str(preview_path)):
                                    os.remove(str(preview_path))
                                os.rename(actual_file, str(preview_path))
                                break
                else:
                    frame_pattern = str(parent_dir / f"{base_name}_frame_*.png")
                    png_files = sorted(glob.glob(frame_pattern))
                    if png_files:
                        self.combine_frames_to_video(parent_dir, f"{base_name}_frame_", preview_path, scene.render.fps, png_files)
                        for png_file in png_files:
                            try:
                                os.remove(png_file)
                            except Exception as e:
                                logger.debug(f"Could not remove temp PNG {png_file}: {e}")

            finally:
                self.restore_viewport_settings(viewport_settings)
                scene.render.filepath = original_filepath
                if original_media_type and hasattr(scene.render.image_settings, 'media_type'):
                    scene.render.image_settings.media_type = original_media_type
                scene.render.image_settings.file_format = original_format
                scene.frame_start = original_frame_start
                scene.frame_end = original_frame_end
                scene.render.resolution_x = original_resolution_x
                scene.render.resolution_y = original_resolution_y
                scene.render.resolution_percentage = original_resolution_percentage
                scene.render.film_transparent = original_film_transparent

        except Exception as e:
            logger.error(f"Error creating preview: {e}")

    def render_keyframe_range(self, scene, keyframe_start, keyframe_end):
        """Render animation using keyframe range"""
        try:
            original_frame = scene.frame_current
            original_start = scene.frame_start
            original_end = scene.frame_end

            scene.frame_start = keyframe_start
            scene.frame_end = keyframe_end

            view3d_area = None
            view3d_region = None
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    view3d_area = area
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            view3d_region = region
                            break
                    break

            if view3d_area and view3d_region:
                with bpy.context.temp_override(area=view3d_area, region=view3d_region):
                    bpy.ops.render.opengl(animation=True, view_context=True)
            else:
                bpy.ops.render.opengl(animation=True, view_context=True)

            scene.frame_start = original_start
            scene.frame_end = original_end
            scene.frame_current = original_frame

        except Exception as e:
            logger.error(f"Error rendering keyframe range: {e}")

    def setup_viewport_for_preview(self, scene, prefs, transparent_bg=False):
        """Configure viewport for preview rendering"""
        try:
            viewport_settings = {}

            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            viewport_settings['show_overlays'] = space.overlay.show_overlays
                            viewport_settings['show_gizmo'] = space.show_gizmo
                            viewport_settings['show_region_ui'] = space.show_region_ui
                            viewport_settings['show_region_toolbar'] = space.show_region_toolbar
                            viewport_settings['show_region_header'] = space.show_region_header
                            viewport_settings['shading_type'] = space.shading.type
                            viewport_settings['background_type'] = space.shading.background_type
                            viewport_settings['background_color'] = tuple(space.shading.background_color)
                            viewport_settings['view_location'] = space.region_3d.view_location.copy()
                            viewport_settings['view_rotation'] = space.region_3d.view_rotation.copy()
                            viewport_settings['view_distance'] = space.region_3d.view_distance
                            viewport_settings['view_perspective'] = space.region_3d.view_perspective

                            space.shading.type = 'SOLID'
                            space.overlay.show_overlays = False
                            space.show_gizmo = False
                            space.show_region_ui = False
                            space.show_region_toolbar = False
                            space.show_region_header = False

                            if transparent_bg:
                                space.shading.background_type = 'VIEWPORT'
                                space.shading.background_color = (0.0, 0.0, 0.0)

                            space.shading.light = 'STUDIO'
                            for light in ['studio.sl', 'rim.sl', 'outdoor.sl', 'Default']:
                                try:
                                    space.shading.studio_light = light
                                    break
                                except TypeError:
                                    continue
                            space.shading.studiolight_intensity = 1.0

                            return viewport_settings
                    break

            return viewport_settings

        except Exception as e:
            logger.error(f"Error setting up viewport: {e}")
            return {}

    def restore_viewport_settings(self, viewport_settings):
        """Restore viewport settings"""
        try:
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            if viewport_settings:
                                space.overlay.show_overlays = viewport_settings.get('show_overlays', True)
                                space.show_gizmo = viewport_settings.get('show_gizmo', True)
                                space.show_region_ui = viewport_settings.get('show_region_ui', True)
                                space.show_region_toolbar = viewport_settings.get('show_region_toolbar', True)
                                space.show_region_header = viewport_settings.get('show_region_header', True)
                                space.shading.type = viewport_settings.get('shading_type', 'SOLID')
                                space.shading.background_type = viewport_settings.get('background_type', 'THEME')
                                space.shading.background_color = viewport_settings.get('background_color', (0.05, 0.05, 0.05))

                                if 'view_location' in viewport_settings:
                                    space.region_3d.view_location = viewport_settings['view_location']
                                if 'view_rotation' in viewport_settings:
                                    space.region_3d.view_rotation = viewport_settings['view_rotation']
                                if 'view_distance' in viewport_settings:
                                    space.region_3d.view_distance = viewport_settings['view_distance']
                                if 'view_perspective' in viewport_settings:
                                    space.region_3d.view_perspective = viewport_settings['view_perspective']
                            else:
                                space.overlay.show_overlays = True
                                space.show_gizmo = True
                                space.show_region_ui = True
                                space.show_region_toolbar = True
                                space.show_region_header = True
                                space.shading.background_type = 'THEME'
                            break
                    break

        except Exception as e:
            logger.error(f"Error restoring viewport: {e}")

    def combine_frames_to_video(self, frames_dir, frame_prefix, output_path, fps, png_files):
        """Combine PNG frames into WebM video using FFmpeg"""
        try:
            ffmpeg_path = shutil.which('ffmpeg')
            if not ffmpeg_path:
                addon_dir = os.path.dirname(__file__)
                bundled_ffmpeg = os.path.join(addon_dir, '..', 'bin', 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
                bundled_ffmpeg = os.path.abspath(bundled_ffmpeg)
                if os.path.isfile(bundled_ffmpeg):
                    ffmpeg_path = bundled_ffmpeg

            if not ffmpeg_path or not png_files:
                return False

            first_file = Path(png_files[0]).name
            match = re.search(r'(\d+)\.png$', first_file)
            start_number = int(match.group(1)) if match else 1

            input_pattern = str(frames_dir / f"{frame_prefix}%04d.png")

            ffmpeg_cmd = [
                ffmpeg_path,
                '-framerate', str(int(fps)),
                '-start_number', str(start_number),
                '-i', input_pattern,
                '-c:v', 'libvpx-vp9',
                '-b:v', '0',
                '-crf', '30',
                '-pix_fmt', 'yuv420p',
                '-y',
                str(output_path)
            ]

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0

        except Exception as e:
            logger.error(f"Error combining frames: {e}")
            return False
