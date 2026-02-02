import bpy
import os
import shutil
import tempfile
import json
import uuid
from pathlib import Path
from datetime import datetime
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from ..utils.queue_client import animation_queue_client
from ..utils.utils import get_active_armature, safe_report_error, DEFAULT_POSE_NAME
from ..utils.logger import get_logger

# Initialize logger
logger = get_logger()


class ANIMLIB_OT_capture_pose(Operator):
    """Capture current pose and send to library"""
    bl_idname = "animlib.capture_pose"
    bl_label = "Capture Pose"
    bl_description = "Capture the current pose and save it to the library"

    # Modal operator state tracking
    _timer = None
    _state = None
    _context_data = None
    _start_time = None
    _last_activity_time = None

    # Timeout configuration (in seconds)
    MODAL_TIMEOUT = 300  # 5 minutes total timeout
    STATE_TIMEOUT = 60   # 1 minute per state (watchdog)

    def invoke(self, context, event):
        """Start the modal capture operation"""
        wm = context.window_manager
        scene = context.scene

        # Set capture flag immediately - this will trigger UI update
        armature = get_active_armature(context)
        if not armature:
            safe_report_error(self, "Please select an armature object")
            return {'CANCELLED'}

        # Check if armature is in pose mode or has pose bones
        if not armature.pose or not armature.pose.bones:
            self.report({'ERROR'}, "Armature has no pose bones")
            return {'CANCELLED'}

        wm.animlib_is_capturing = True

        # Initialize state machine
        self._state = 'DETECT_RIG'
        self._context_data = {
            'scene': scene,
            'armature': armature,
            'wm': wm
        }

        # Initialize timeout tracking
        import time
        self._start_time = time.time()
        self._last_activity_time = time.time()

        # Add timer for modal updates (runs every 0.1 seconds)
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        # Force UI update to hide button immediately
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        """Handle modal execution - called periodically by timer"""
        # Only process on timer events
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        import time

        # Timeout watchdog - prevent indefinite hangs
        current_time = time.time()

        # Check total operation timeout
        if self._start_time and (current_time - self._start_time) > self.MODAL_TIMEOUT:
            logger.error(f"Pose capture timed out after {self.MODAL_TIMEOUT}s")
            self.report({'ERROR'}, "Capture timed out - operation took too long")
            self.cleanup(context)
            return {'CANCELLED'}

        # Check state timeout (watchdog for stuck states)
        if self._last_activity_time and (current_time - self._last_activity_time) > self.STATE_TIMEOUT:
            logger.error(f"Pose capture stuck in state '{self._state}' for {self.STATE_TIMEOUT}s")
            self.report({'ERROR'}, f"Capture stuck in '{self._state}' - cancelling")
            self.cleanup(context)
            return {'CANCELLED'}

        wm = self._context_data['wm']
        scene = self._context_data['scene']

        try:
            if self._state == 'DETECT_RIG':
                # Detect rig type
                armature = self._context_data['armature']

                if scene.animlib_use_detected_rig_type:
                    rig_type, confidence = animation_queue_client.detect_rig_type(armature)
                    if rig_type == 'unknown':
                        self.report({'WARNING'}, f"Could not detect rig type (confidence: {confidence:.2f})")
                else:
                    rig_type = scene.animlib_rig_type.strip()
                    if not rig_type:
                        rig_type = 'custom'
                    self.report({'INFO'}, f"Using custom rig type: {rig_type}")

                self._context_data['rig_type'] = rig_type
                self._state = 'DETERMINE_NAME'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'DETERMINE_NAME':
                # Determine pose name from panel field
                pose_name = scene.animlib_pose_name.strip()
                if not pose_name:
                    pose_name = DEFAULT_POSE_NAME

                self._context_data['pose_name'] = pose_name
                self._state = 'CREATE_ACTION'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'CREATE_ACTION':
                # Create single-frame action from current pose
                armature = self._context_data['armature']
                pose_name = self._context_data['pose_name']

                action = self.create_pose_action(armature, pose_name, scene)
                if not action:
                    self.report({'ERROR'}, "Failed to create pose action")
                    self.cleanup(context)
                    return {'CANCELLED'}

                self._context_data['action'] = action
                self._state = 'SAVE_POSE'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'SAVE_POSE':
                # Save pose to library
                action = self._context_data['action']
                pose_name = self._context_data['pose_name']
                rig_type = self._context_data['rig_type']
                armature = self._context_data['armature']

                blend_path, json_path, metadata = self.save_pose_to_library(
                    action, armature, pose_name, rig_type, scene
                )

                if not blend_path or not json_path:
                    self.report({'ERROR'}, "Failed to save pose files")
                    self.cleanup(context)
                    return {'CANCELLED'}

                self._state = 'CLEANUP'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'CLEANUP':
                # Clear form fields
                scene.animlib_pose_name = DEFAULT_POSE_NAME
                scene.animlib_description = ""
                scene.animlib_tags = ""

                # Report success
                pose_name = self._context_data['pose_name']
                self.report({'INFO'}, f"Pose '{pose_name}' saved successfully")

                # Cleanup and finish
                self.cleanup(context)
                return {'FINISHED'}

        except Exception as e:
            logger.error(f"Error during pose capture: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.report({'ERROR'}, f"Pose capture failed: {str(e)}")
            self.cleanup(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def cleanup(self, context):
        """Cleanup modal operation resources"""
        wm = context.window_manager

        # Remove timer
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None

        # Clear capture flag - button will reappear
        wm.animlib_is_capturing = False

        # Force UI update
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        # Clear state
        self._state = None
        self._context_data = None
        self._start_time = None
        self._last_activity_time = None

    def cancel(self, context):
        """Called when user cancels (ESC key)"""
        self.report({'INFO'}, "Pose capture cancelled")
        self.cleanup(context)

    def create_pose_action(self, armature, pose_name, scene):
        """
        Create a single-frame action from current pose.

        Args:
            armature: Armature object with pose
            pose_name: Name for the action
            scene: Blender scene

        Returns:
            Created action or None on failure
        """
        from ..utils.utils import (
            BLENDER_5_0_OR_LATER,
            init_action_for_blender_5,
            new_action_fcurve,
        )

        try:
            # Create new action
            action = bpy.data.actions.new(name=pose_name)

            # Initialize for Blender 5.0+ (creates layers, strips, slots)
            slot = None
            if BLENDER_5_0_OR_LATER:
                slot = init_action_for_blender_5(action, slot_name=pose_name)
                if not slot:
                    logger.error("Failed to initialize action for Blender 5.0")
                    bpy.data.actions.remove(action)
                    return None

            # Determine which bones to capture
            if scene.animlib_selected_bones_only:
                # Use bpy.context.selected_pose_bones for reliable selection detection across Blender versions
                selected = bpy.context.selected_pose_bones
                bones = selected if selected else []
                if not bones:
                    logger.warning("No bones selected, capturing all bones")
                    bones = armature.pose.bones
            else:
                bones = armature.pose.bones

            captured_bone_names = []

            # For each bone, insert keyframe at frame 0
            for bone in bones:
                captured_bone_names.append(bone.name)

                # Get bone's data path
                data_path_loc = f'pose.bones["{bone.name}"].location'
                data_path_scale = f'pose.bones["{bone.name}"].scale'

                # Handle rotation based on rotation mode
                if bone.rotation_mode == 'QUATERNION':
                    data_path_rot = f'pose.bones["{bone.name}"].rotation_quaternion'
                    rot_values = bone.rotation_quaternion
                    rot_indices = range(4)
                elif bone.rotation_mode == 'AXIS_ANGLE':
                    data_path_rot = f'pose.bones["{bone.name}"].rotation_axis_angle'
                    rot_values = bone.rotation_axis_angle
                    rot_indices = range(4)
                else:
                    # Euler rotation
                    data_path_rot = f'pose.bones["{bone.name}"].rotation_euler'
                    rot_values = bone.rotation_euler
                    rot_indices = range(3)

                # Create FCurves and keyframes for location
                for i, value in enumerate(bone.location):
                    fcurve = new_action_fcurve(action, data_path_loc, index=i, slot=slot, group_name=bone.name)
                    if fcurve:
                        fcurve.keyframe_points.insert(0, value, options={'FAST'})

                # Create FCurves and keyframes for rotation
                for i in rot_indices:
                    fcurve = new_action_fcurve(action, data_path_rot, index=i, slot=slot, group_name=bone.name)
                    if fcurve:
                        fcurve.keyframe_points.insert(0, rot_values[i], options={'FAST'})

                # Create FCurves and keyframes for scale
                for i, value in enumerate(bone.scale):
                    fcurve = new_action_fcurve(action, data_path_scale, index=i, slot=slot, group_name=bone.name)
                    if fcurve:
                        fcurve.keyframe_points.insert(0, value, options={'FAST'})

            # Store captured bone names in action's custom properties
            action["captured_bones"] = captured_bone_names
            action["is_pose"] = True

            logger.info(f"Created pose action with {len(captured_bone_names)} bones")
            return action

        except Exception as e:
            logger.error(f"Error creating pose action: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def save_pose_to_library(self, action, armature, pose_name, rig_type, scene):
        """
        Save pose action to library.

        Args:
            action: Blender action containing pose
            armature: Armature object
            pose_name: Name for the pose
            rig_type: Detected or custom rig type
            scene: Blender scene

        Returns:
            Tuple of (blend_path, json_path, metadata) or (None, None, None) on failure
        """
        try:
            from ..preferences import get_library_path

            # Get library path from preferences
            library_path = get_library_path()
            if not library_path:
                logger.error("No library path set in preferences")
                return None, None, None

            library_dir = Path(library_path)

            # Create unique pose ID
            pose_id = str(uuid.uuid4())

            # Sanitize pose name for filesystem
            import re
            safe_pose_name = re.sub(r'[<>:"/\\|?*]', '_', pose_name)
            safe_pose_name = safe_pose_name.strip(' .')
            safe_pose_name = re.sub(r'_+', '_', safe_pose_name) or 'unnamed_pose'

            # Check for collision - if folder exists, add numeric suffix
            pose_folder = library_dir / "library" / "poses" / safe_pose_name
            if pose_folder.exists():
                # Check if it's a different pose by reading JSON
                existing_pose_id = None
                for json_file in pose_folder.glob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        existing_pose_id = data.get('id')
                        break
                    except:
                        continue

                if existing_pose_id and existing_pose_id != pose_id:
                    # Different pose with same name - add numeric suffix
                    suffix = 2
                    while True:
                        new_folder = library_dir / "library" / "poses" / f"{safe_pose_name}_{suffix}"
                        if not new_folder.exists():
                            pose_folder = new_folder
                            safe_pose_name = f"{safe_pose_name}_{suffix}"
                            logger.info(f"Pose name collision, using: {safe_pose_name}")
                            break
                        suffix += 1

            pose_folder.mkdir(parents=True, exist_ok=True)

            # All files use the pose name (not UUID) for human-readability
            blend_path = pose_folder / f"{safe_pose_name}.blend"
            json_path = pose_folder / f"{safe_pose_name}.json"
            thumbnail_path = pose_folder / f"{safe_pose_name}.png"

            # Create minimal blend file with just the action
            temp_fd, temp_path = tempfile.mkstemp(suffix='.blend')
            os.close(temp_fd)

            bpy.data.libraries.write(temp_path, {action}, compress=True)

            # Move to final location
            shutil.move(temp_path, str(blend_path))

            # Create thumbnail from current pose
            self.create_thumbnail(armature, scene, str(thumbnail_path))

            # Get bone info
            captured_bones = action.get("captured_bones", [])
            if not captured_bones:
                captured_bones = [bone.name for bone in armature.data.bones]

            # Parse tags
            tags = [tag.strip() for tag in scene.animlib_tags.split(',') if tag.strip()]

            # Create JSON metadata
            metadata = {
                'id': pose_id,
                'app_version': '1.3.0',  # For one-time v1.2→v1.3 migration detection
                'name': pose_name,
                'description': scene.animlib_description,
                'author': scene.animlib_author,
                'tags': tags,
                'rig_type': rig_type,
                'armature_name': armature.name,
                'bone_count': len(captured_bones),
                'bone_names': captured_bones,
                'is_partial': scene.animlib_selected_bones_only and len(captured_bones) < len(armature.pose.bones),
                'action_name': action.name,
                # Pose-specific: single frame
                'frame_start': 0,
                'frame_end': 0,
                'frame_count': 1,
                'duration_seconds': 0,
                'fps': scene.render.fps,
                # File paths
                'json_file_path': str(json_path),
                'blend_file_path': str(blend_path),
                'preview_path': '',  # No video preview for poses
                'thumbnail_path': str(thumbnail_path),
                'created_date': datetime.now().isoformat(),
                'file_size_mb': blend_path.stat().st_size / (1024 * 1024),
                # Poses don't use versioning - they're simple, disposable building blocks
                # Pose flag - critical for filtering
                'is_pose': 1
            }

            # Save JSON metadata
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved pose: {blend_path}")
            logger.debug(f"Saved metadata: {json_path}")
            return str(blend_path), str(json_path), metadata

        except Exception as e:
            logger.error(f"Error saving pose to library: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None, None

    def create_thumbnail(self, armature, scene, thumbnail_path):
        """Create thumbnail from current pose"""
        try:
            from ..preferences import get_preview_settings
            prefs = get_preview_settings()

            # Store current settings
            original_filepath = scene.render.filepath
            original_format = scene.render.image_settings.file_format
            original_color_mode = scene.render.image_settings.color_mode
            original_frame = scene.frame_current
            original_resolution_x = scene.render.resolution_x
            original_resolution_y = scene.render.resolution_y
            original_resolution_percentage = scene.render.resolution_percentage
            original_film_transparent = scene.render.film_transparent
            viewport_settings = None

            try:
                # Configure render settings for single frame
                scene.render.filepath = thumbnail_path
                scene.render.image_settings.file_format = 'PNG'
                scene.render.image_settings.color_mode = 'RGBA'
                scene.render.resolution_x = prefs['resolution_x']
                scene.render.resolution_y = prefs['resolution_y']
                scene.render.resolution_percentage = 100
                scene.render.film_transparent = True

                # Configure viewport for clean preview with transparent background
                viewport_settings = self.setup_viewport_for_preview(scene, prefs)

                # Render single frame
                bpy.ops.render.opengl(write_still=True)

                logger.debug(f"Created pose thumbnail: {thumbnail_path}")

            finally:
                # Always restore viewport settings
                self.restore_viewport_settings(viewport_settings)

                # Restore original settings
                scene.render.filepath = original_filepath
                scene.render.image_settings.file_format = original_format
                scene.render.image_settings.color_mode = original_color_mode
                scene.frame_set(original_frame)
                scene.render.resolution_x = original_resolution_x
                scene.render.resolution_y = original_resolution_y
                scene.render.resolution_percentage = original_resolution_percentage
                scene.render.film_transparent = original_film_transparent

        except Exception as e:
            logger.error(f"Error creating pose thumbnail: {e}")

    def setup_viewport_for_preview(self, scene, prefs):
        """Configure viewport shading for preview rendering"""
        try:
            viewport_settings = {}

            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Store original settings
                            viewport_settings['show_overlays'] = space.overlay.show_overlays
                            viewport_settings['show_gizmo'] = space.show_gizmo
                            viewport_settings['show_region_ui'] = space.show_region_ui
                            viewport_settings['show_region_toolbar'] = space.show_region_toolbar
                            viewport_settings['show_region_header'] = space.show_region_header
                            viewport_settings['shading_type'] = space.shading.type
                            viewport_settings['background_type'] = space.shading.background_type
                            viewport_settings['background_color'] = tuple(space.shading.background_color)

                            # Store viewport view settings
                            viewport_settings['view_location'] = space.region_3d.view_location.copy()
                            viewport_settings['view_rotation'] = space.region_3d.view_rotation.copy()
                            viewport_settings['view_distance'] = space.region_3d.view_distance
                            viewport_settings['view_perspective'] = space.region_3d.view_perspective

                            # Configure for clean preview
                            space.shading.type = 'SOLID'
                            space.overlay.show_overlays = False
                            space.show_gizmo = False
                            space.show_region_ui = False
                            space.show_region_toolbar = False
                            space.show_region_header = False

                            # Transparent background for thumbnail
                            space.shading.background_type = 'VIEWPORT'
                            space.shading.background_color = (0.0, 0.0, 0.0)

                            # Use STUDIO lighting for quality previews
                            space.shading.light = 'STUDIO'
                            space.shading.studio_light = 'forest.exr'
                            space.shading.studiolight_intensity = 1.0

                            # Switch to camera view if enabled and camera exists
                            use_camera = prefs.get('use_camera', False)
                            if use_camera and scene.camera:
                                space.region_3d.view_perspective = 'CAMERA'
                                logger.debug(f"Switched to camera view: {scene.camera.name}")

                            return viewport_settings
                    break

            return viewport_settings

        except Exception as e:
            logger.error(f"Error setting up viewport for preview: {e}")
            return {}

    def restore_viewport_settings(self, viewport_settings):
        """Restore original viewport settings after preview generation"""
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
                                # Force restore to visible defaults
                                space.overlay.show_overlays = True
                                space.show_gizmo = True
                                space.show_region_ui = True
                                space.show_region_toolbar = True
                                space.show_region_header = True
                                space.shading.background_type = 'THEME'

                            logger.debug("Viewport settings restored")
                            break
                    break

        except Exception as e:
            logger.error(f"Error restoring viewport settings: {e}")


# Classes to register
classes = [
    ANIMLIB_OT_capture_pose,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
