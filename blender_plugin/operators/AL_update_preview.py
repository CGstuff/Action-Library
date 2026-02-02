import bpy
import json
import os
import glob
import shutil
import subprocess
import re
from bpy.types import Operator
from ..utils.utils import (get_action_keyframe_range, get_active_armature,
                   has_animation_data, safe_report_error)
from ..utils.logger import get_logger
from pathlib import Path
from ..preferences import get_preview_settings, get_library_path
from datetime import datetime

# Initialize logger
logger = get_logger()

class ANIMLIB_OT_update_preview(Operator):
    """Update preview video and thumbnail for the current animation"""
    bl_idname = "animlib.update_preview"
    bl_label = "Update Preview"
    bl_description = "Re-render preview video and thumbnail for the current animation (must be a library animation)"

    # Modal operator state tracking
    _timer = None
    _state = None
    _context_data = None

    @classmethod
    def poll(cls, context):
        """Check if the operator can run"""
        # Check if armature with action exists
        armature = get_active_armature(context)
        if not armature or not has_animation_data(armature):
            return False

        # Check if the action has library metadata (was imported from library)
        action = armature.animation_data.action if armature.animation_data else None
        if not action:
            return False

        # Must have animlib_uuid to update preview
        uuid = action.get("animlib_uuid", "")
        if not uuid:
            return False

        # Must have library path configured
        library_path = get_library_path()
        if not library_path:
            return False

        return True

    @classmethod
    def is_server_available(cls):
        """Check if desktop app is available (via queue directory)"""
        library_path = get_library_path()
        if not library_path:
            return False

        queue_dir = Path(library_path) / ".queue"
        return queue_dir.exists()

    def invoke(self, context, event):
        """Start the modal update preview operation"""
        wm = context.window_manager

        # Set update flag immediately
        wm.animlib_is_updating_preview = True

        # Validate armature
        armature = get_active_armature(context)
        if not armature:
            safe_report_error(self, "Please select an armature object")
            wm.animlib_is_updating_preview = False
            return {'CANCELLED'}

        if not has_animation_data(armature):
            safe_report_error(self, "No Action data found on selected armature")
            wm.animlib_is_updating_preview = False
            return {'CANCELLED'}

        # Get action and UUID
        action = armature.animation_data.action
        uuid = action.get("animlib_uuid", "")
        if not uuid:
            safe_report_error(self, "This action is not from the library. Capture it first.")
            wm.animlib_is_updating_preview = False
            return {'CANCELLED'}

        # Get library path
        library_path = get_library_path()
        if not library_path:
            safe_report_error(self, "Library path not configured")
            wm.animlib_is_updating_preview = False
            return {'CANCELLED'}

        # Derive folder from animation name (O(1) - no scanning)
        library_dir = Path(library_path)
        animation_name = action.get("animlib_name", action.name)

        # Get base name (strip version suffix) for folder
        base_name = re.sub(r'_v\d{2,4}$', '', animation_name)
        safe_base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
        safe_base_name = safe_base_name.strip(' .') or 'unnamed'
        safe_base_name = re.sub(r'_+', '_', safe_base_name)

        # Folder is library/actions/{base_name}/
        animation_folder = library_dir / "library" / "actions" / safe_base_name

        # Verify animation folder exists
        if not animation_folder.exists():
            safe_report_error(self, f"Animation folder not found: {animation_folder}")
            wm.animlib_is_updating_preview = False
            return {'CANCELLED'}

        # Sanitize animation name for filename
        safe_anim_name = re.sub(r'[<>:"/\\|?*]', '_', animation_name)
        safe_anim_name = safe_anim_name.strip(' .') or 'unnamed'
        safe_anim_name = re.sub(r'_+', '_', safe_anim_name)

        preview_path = animation_folder / f"{safe_anim_name}.webm"
        thumbnail_path = animation_folder / f"{safe_anim_name}.png"

        # Initialize state machine - start with RELEASE_FILES to notify desktop app first
        self._state = 'RELEASE_FILES'
        self._wait_counter = 0  # Counter for waiting after release notification
        self._context_data = {
            'armature': armature,
            'action': action,
            'wm': wm,
            'scene': context.scene,
            'uuid': uuid,
            'library_path': library_path,
            'preview_path': str(preview_path),
            'thumbnail_path': str(thumbnail_path),
            'animation_name': action.get("animlib_name", action.name)
        }

        # Add timer for modal updates
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        # Force UI update
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        logger.info(f"Starting preview update for animation: {uuid}")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        """Handle modal execution"""
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        wm = self._context_data['wm']

        try:
            logger.debug(f"[UPDATE_PREVIEW] Modal state: {self._state}")

            if self._state == 'RELEASE_FILES':
                # First, notify desktop app to release the video file
                uuid = self._context_data['uuid']
                library_path = self._context_data['library_path']
                animation_name = self._context_data['animation_name']
                preview_path = self._context_data['preview_path']

                self.notify_preview_updating(uuid, library_path, animation_name, preview_path)
                logger.info(f"[UPDATE_PREVIEW] Notified desktop to release files, waiting...")

                self._state = 'WAIT_FOR_RELEASE'
                self._wait_counter = 0
                return {'RUNNING_MODAL'}

            elif self._state == 'WAIT_FOR_RELEASE':
                # Wait for desktop app to release the file (5 timer ticks = 500ms with 0.1s timer)
                self._wait_counter += 1
                if self._wait_counter < 5:
                    return {'RUNNING_MODAL'}

                logger.info(f"[UPDATE_PREVIEW] Wait complete, proceeding with render")
                self._state = 'RENDER_PREVIEW'
                return {'RUNNING_MODAL'}

            elif self._state == 'RENDER_PREVIEW':
                # Re-render preview and thumbnail
                armature = self._context_data['armature']
                scene = self._context_data['scene']
                uuid = self._context_data['uuid']
                preview_path = self._context_data['preview_path']
                thumbnail_path = self._context_data['thumbnail_path']

                logger.info(f"[UPDATE_PREVIEW] Starting render for {uuid}")
                success = self.update_preview_files(
                    uuid, preview_path, thumbnail_path, armature, scene
                )
                logger.info(f"[UPDATE_PREVIEW] Render complete, success={success}")

                if not success:
                    self.report({'ERROR'}, "Failed to update preview files")
                    self.cleanup(context)
                    return {'CANCELLED'}

                self._state = 'NOTIFY_DESKTOP'
                return {'RUNNING_MODAL'}

            elif self._state == 'NOTIFY_DESKTOP':
                # Notify desktop app via queue file
                uuid = self._context_data['uuid']
                library_path = self._context_data['library_path']
                animation_name = self._context_data['animation_name']

                self.notify_desktop_app(uuid, library_path, animation_name)

                self.report({'INFO'}, f"Preview updated for: {animation_name}")
                self.cleanup(context)
                return {'FINISHED'}

            else:
                # Unknown state - should never happen, but prevent infinite loop
                logger.error(f"[UPDATE_PREVIEW] Unknown state: {self._state}, cancelling")
                self.cleanup(context)
                return {'CANCELLED'}

        except Exception as e:
            logger.error(f"Error during preview update: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.report({'ERROR'}, f"Preview update failed: {str(e)}")
            self.cleanup(context)
            return {'CANCELLED'}

    def cleanup(self, context):
        """Cleanup modal operation resources"""
        wm = context.window_manager

        # Remove timer
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None

        # Clear update flag
        wm.animlib_is_updating_preview = False

        # Force UI update
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        # Clear state
        self._state = None
        self._context_data = None

    def cancel(self, context):
        """Called when user cancels (ESC key)"""
        self.report({'INFO'}, "Preview update cancelled")
        self.cleanup(context)

    def _safe_remove_file(self, file_path, max_attempts=5, delay=0.5):
        """Safely remove a file with retry logic for locked files"""
        import time
        for attempt in range(max_attempts):
            try:
                os.remove(file_path)
                logger.debug(f"Removed file: {file_path}")
                return True
            except PermissionError:
                if attempt < max_attempts - 1:
                    logger.warning(f"File locked, retry {attempt + 1}/{max_attempts}: {file_path}")
                    time.sleep(delay)
                else:
                    logger.error(f"Could not remove locked file after {max_attempts} attempts: {file_path}")
                    raise
        return False

    def notify_preview_updating(self, uuid, library_path, animation_name, preview_path):
        """Write notification file to tell desktop app to release the preview file"""
        try:
            queue_dir = Path(library_path) / ".queue"
            queue_dir.mkdir(parents=True, exist_ok=True)

            # Create notification file - desktop app will release the file
            notification_file = queue_dir / f"preview_updating_{uuid[:8]}.json"
            notification_data = {
                "type": "preview_updating",
                "animation_id": uuid,
                "animation_name": animation_name,
                "preview_path": preview_path,
                "timestamp": datetime.now().isoformat()
            }

            with open(notification_file, 'w', encoding='utf-8') as f:
                json.dump(notification_data, f)

            logger.info(f"Notified desktop app to release file: {notification_file}")
            return True

        except Exception as e:
            logger.warning(f"Failed to notify desktop app: {e}")
            return False

    def notify_desktop_app(self, uuid, library_path, animation_name):
        """Write notification file for desktop app to refresh preview"""
        try:
            queue_dir = Path(library_path) / ".queue"
            queue_dir.mkdir(parents=True, exist_ok=True)

            # Create notification file
            notification_file = queue_dir / f"preview_updated_{uuid[:8]}.json"
            notification_data = {
                "type": "preview_updated",
                "animation_id": uuid,
                "animation_name": animation_name,
                "timestamp": datetime.now().isoformat()
            }

            with open(notification_file, 'w', encoding='utf-8') as f:
                json.dump(notification_data, f)

            logger.info(f"Notified desktop app: {notification_file}")

        except Exception as e:
            logger.warning(f"Failed to notify desktop app: {e}")
            # Not critical - preview is still updated

    def update_preview_files(self, uuid, preview_path, thumbnail_path, armature, scene):
        """Re-render preview video and thumbnail for existing animation"""
        try:
            # Get animation timing from current action
            action = armature.animation_data.action if armature.animation_data else None
            if action:
                keyframe_start, keyframe_end = get_action_keyframe_range(action)
                if keyframe_start is None:
                    keyframe_start = scene.frame_start
                    keyframe_end = scene.frame_end
            else:
                keyframe_start = scene.frame_start
                keyframe_end = scene.frame_end

            # Get preview settings
            prefs = get_preview_settings()

            # Try to remove existing files first (they might be locked by desktop app)
            for file_path in [preview_path, thumbnail_path]:
                if os.path.exists(file_path):
                    try:
                        self._safe_remove_file(file_path)
                    except PermissionError:
                        logger.warning(f"Skipping locked file, will try again during render: {file_path}")

            # Re-render thumbnail
            logger.info(f"Re-rendering thumbnail: {thumbnail_path}")
            self.render_thumbnail(armature, scene, thumbnail_path, keyframe_start, prefs)

            # Re-render preview video
            logger.info(f"Re-rendering preview video: {preview_path}")
            self.render_preview_video(armature, scene, preview_path, keyframe_start, keyframe_end, prefs)

            logger.info(f"Successfully updated preview files for animation: {uuid}")
            return True

        except Exception as e:
            logger.error(f"Error updating preview files: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def render_thumbnail(self, armature, scene, thumbnail_path, first_frame, prefs):
        """Render thumbnail from first frame - copied from working capture_animation.py"""
        try:
            # Store ALL current settings
            original_filepath = scene.render.filepath
            original_format = scene.render.image_settings.file_format
            original_color_mode = scene.render.image_settings.color_mode
            original_frame = scene.frame_current
            original_resolution_x = scene.render.resolution_x
            original_resolution_y = scene.render.resolution_y
            original_resolution_percentage = scene.render.resolution_percentage
            original_film_transparent = scene.render.film_transparent
            viewport_settings = None

            # Store media_type if available (Blender 4.5+/5.0)
            original_media_type = None
            if hasattr(scene.render.image_settings, 'media_type'):
                original_media_type = scene.render.image_settings.media_type

            try:
                # Set to first frame
                scene.frame_set(first_frame)

                # Temporarily switch to PNG image format
                # IMPORTANT: In Blender 4.5+/5.0, must set media_type to 'IMAGE' first
                if hasattr(scene.render.image_settings, 'media_type'):
                    scene.render.image_settings.media_type = 'IMAGE'
                scene.render.image_settings.file_format = 'PNG'
                scene.render.image_settings.color_mode = 'RGBA'
                scene.render.filepath = thumbnail_path
                scene.render.resolution_x = prefs['resolution_x']
                scene.render.resolution_y = prefs['resolution_y']
                scene.render.resolution_percentage = 100
                scene.render.film_transparent = True

                # Configure viewport for clean preview with transparent background
                viewport_settings = self.setup_viewport_for_preview(scene, prefs, transparent_bg=True)

                # Render single frame
                bpy.ops.render.opengl(write_still=True)

                logger.debug(f"Created transparent thumbnail: {thumbnail_path}")

            finally:
                # Always restore viewport settings
                self.restore_viewport_settings(viewport_settings)

                # Restore ALL original settings
                scene.render.filepath = original_filepath
                # Restore media_type first (Blender 4.5+/5.0), then file_format
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

    def render_preview_video(self, armature, scene, preview_path, frame_start, frame_end, prefs):
        """Render preview video - copied from working capture_animation.py"""
        try:
            # Store current settings
            original_filepath = scene.render.filepath
            original_format = scene.render.image_settings.file_format
            original_frame_start = scene.frame_start
            original_frame_end = scene.frame_end
            original_resolution_x = scene.render.resolution_x
            original_resolution_y = scene.render.resolution_y
            original_resolution_percentage = scene.render.resolution_percentage
            original_engine = scene.render.engine
            original_film_transparent = scene.render.film_transparent
            viewport_settings = None

            # Store media_type if available (Blender 4.5+/5.0)
            original_media_type = None
            if hasattr(scene.render.image_settings, 'media_type'):
                original_media_type = scene.render.image_settings.media_type

            try:
                # Check if media_type exists (Blender 4.5+/5.0)
                has_media_type = hasattr(scene.render.image_settings, 'media_type')
                use_ffmpeg_direct = False

                try:
                    # Try Blender 4.x direct FFMPEG approach
                    if has_media_type:
                        scene.render.image_settings.media_type = 'VIDEO'
                    scene.render.image_settings.file_format = 'FFMPEG'
                    scene.render.ffmpeg.format = 'WEBM'
                    scene.render.ffmpeg.codec = 'WEBM'
                    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
                    scene.render.ffmpeg.audio_codec = 'NONE'
                    scene.render.filepath = str(preview_path).replace('.webm', '')
                    use_ffmpeg_direct = True
                    logger.debug("Using direct FFMPEG video output (Blender 4.x)")
                except (TypeError, AttributeError):
                    # Blender 5.0+ - render to PNG frames, combine later
                    if has_media_type:
                        scene.render.image_settings.media_type = 'IMAGE'
                    scene.render.image_settings.file_format = 'PNG'
                    scene.render.filepath = str(preview_path).replace('.webm', '_frame_####')
                    use_ffmpeg_direct = False
                    logger.debug("Using PNG frame sequence (Blender 5.0+)")

                # Resolution from preferences
                scene.render.resolution_x = prefs['resolution_x']
                scene.render.resolution_y = prefs['resolution_y']
                scene.render.resolution_percentage = 100

                # Keep viewport background visible (no transparency needed)
                scene.render.film_transparent = False

                # Configure viewport for clean preview
                viewport_settings = self.setup_viewport_for_preview(scene, prefs)

                # Render animation using keyframe range
                self.render_keyframe_range(scene, frame_start, frame_end)

                # Handle output files
                preview_path_obj = Path(preview_path)
                parent_dir = preview_path_obj.parent
                base_name = preview_path_obj.stem

                if use_ffmpeg_direct:
                    # Blender 4.x - rename the video file with frame numbers
                    # Use a specific pattern to find files with frame numbers appended (e.g., name0001-0050.webm)
                    frame_number_pattern = str(parent_dir / f"{base_name}[0-9]*-[0-9]*.webm")
                    rendered_files = glob.glob(frame_number_pattern)
                    logger.debug(f"Looking for rendered files with pattern: {frame_number_pattern}")

                    if rendered_files:
                        # Take the first matching file (there should only be one)
                        actual_file = rendered_files[0]
                        logger.debug(f"Found rendered file: {actual_file}")

                        # Delete the old file first if it exists
                        old_file_removed = False
                        if os.path.exists(str(preview_path)):
                            try:
                                self._safe_remove_file(str(preview_path))
                                old_file_removed = True
                            except PermissionError:
                                logger.warning(f"Could not remove old file (may be locked): {preview_path}")

                        # Rename the new file to the correct name
                        if old_file_removed or not os.path.exists(str(preview_path)):
                            try:
                                os.rename(actual_file, str(preview_path))
                                logger.info(f"Renamed video file: {actual_file} -> {preview_path}")
                            except Exception as e:
                                logger.error(f"Failed to rename video file: {e}")
                                # Keep the new file with frame numbers - at least user has updated content
                        else:
                            # Old file still exists and couldn't be deleted
                            # Keep both files - user will have updated content in the frame-numbered file
                            logger.warning(f"Keeping both files - old: {preview_path}, new: {actual_file}")
                    else:
                        # Fallback: check if the file was created directly with correct name
                        if os.path.exists(str(preview_path)):
                            logger.info(f"Video file already at correct path: {preview_path}")
                        else:
                            logger.warning("Could not find rendered video file")
                else:
                    # Blender 5.0+ - combine PNG frames into WebM using FFmpeg
                    frame_pattern = str(parent_dir / f"{base_name}_frame_*.png")
                    png_files = sorted(glob.glob(frame_pattern))
                    logger.debug(f"Found {len(png_files)} PNG frames matching {frame_pattern}")

                    if png_files:
                        success = self.combine_frames_to_video(
                            parent_dir,
                            f"{base_name}_frame_",
                            preview_path,
                            scene.render.fps,
                            png_files
                        )
                        if not success:
                            logger.warning("Failed to create video from frames")
                        # Clean up PNG frames
                        for png_file in png_files:
                            try:
                                os.remove(png_file)
                            except:
                                pass
                    else:
                        logger.warning("No PNG frames rendered")

                logger.debug(f"Created viewport animation preview: {preview_path}")

            finally:
                # Always restore viewport settings first
                self.restore_viewport_settings(viewport_settings)

                # Restore original render settings
                scene.render.filepath = original_filepath
                # Restore media_type first (Blender 4.5+/5.0), then file_format
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
            logger.error(f"Error creating animation preview: {e}")

    def setup_viewport_for_preview(self, scene, prefs, transparent_bg=False):
        """Configure viewport shading for preview rendering - copied from working capture_animation.py"""
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

                            # Store viewport view settings (camera angle)
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

                            if transparent_bg:
                                space.shading.background_type = 'VIEWPORT'
                                space.shading.background_color = (0.0, 0.0, 0.0)

                            # Use STUDIO lighting for quality previews
                            space.shading.light = 'STUDIO'
                            for light in ['studio.sl', 'rim.sl', 'outdoor.sl', 'Default']:
                                try:
                                    space.shading.studio_light = light
                                    logger.debug(f"Using studio light: {light}")
                                    break
                                except TypeError:
                                    continue
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
        """Restore original viewport settings - copied from working capture_animation.py"""
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

    def render_keyframe_range(self, scene, keyframe_start, keyframe_end):
        """Render animation using keyframe range - copied from working capture_animation.py"""
        try:
            original_frame = scene.frame_current
            original_start = scene.frame_start
            original_end = scene.frame_end

            # Temporarily set the scene range for the animation render only
            scene.frame_start = keyframe_start
            scene.frame_end = keyframe_end

            logger.debug(f"Rendering viewport animation: frames {keyframe_start} to {keyframe_end}")

            # Use built-in OpenGL animation render with context override
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
                    result = bpy.ops.render.opengl(animation=True, view_context=True)
                    logger.debug(f"render.opengl result: {result}")
            else:
                logger.warning("No 3D View found for viewport render, trying without override")
                result = bpy.ops.render.opengl(animation=True, view_context=True)
                logger.debug(f"render.opengl result: {result}")

            # Immediately restore original timeline
            scene.frame_start = original_start
            scene.frame_end = original_end
            scene.frame_current = original_frame

        except Exception as e:
            logger.error(f"Error rendering keyframe range: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                scene.frame_start = original_start
                scene.frame_end = original_end
                scene.frame_current = original_frame
            except:
                pass

    def find_ffmpeg_executable(self):
        """Find FFmpeg executable using hybrid detection: system PATH -> bundled -> None"""
        try:
            # First, check system PATH using shutil.which()
            system_ffmpeg = shutil.which('ffmpeg')
            if system_ffmpeg:
                logger.debug(f"Found FFmpeg in system PATH: {system_ffmpeg}")
                return system_ffmpeg

            # Second, check bundled bin/ directory
            addon_dir = os.path.dirname(__file__)
            bundled_ffmpeg = os.path.join(addon_dir, '..', 'bin', 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
            bundled_ffmpeg = os.path.abspath(bundled_ffmpeg)

            if os.path.isfile(bundled_ffmpeg) and os.access(bundled_ffmpeg, os.X_OK):
                logger.debug(f"Found bundled FFmpeg: {bundled_ffmpeg}")
                return bundled_ffmpeg

            # Not found anywhere
            logger.warning("FFmpeg not found in system PATH or bundled directory")
            return None

        except Exception as e:
            logger.error(f"Error finding FFmpeg: {e}")
            return None

    def combine_frames_to_video(self, frames_dir, frame_prefix, output_path, fps, png_files):
        """Combine PNG frames into WebM video using FFmpeg (for Blender 5.0+)"""
        try:
            ffmpeg_path = self.find_ffmpeg_executable()
            if not ffmpeg_path:
                logger.warning("FFmpeg not available - cannot create video from frames")
                return False

            if not png_files:
                logger.warning("No PNG files provided")
                return False

            # Extract the first frame number to determine start_number
            first_file = Path(png_files[0]).name
            # Match pattern like: uuid_frame_0001.png
            match = re.search(r'(\d+)\.png$', first_file)
            if match:
                start_number = int(match.group(1))
            else:
                start_number = 1

            input_pattern = str(frames_dir / f"{frame_prefix}%04d.png")
            logger.debug(f"FFmpeg input pattern: {input_pattern}, start_number: {start_number}")

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

            logger.debug(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")

            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                logger.info(f"Created video from frames: {output_path}")
                return True
            else:
                logger.error(f"FFmpeg failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error combining frames to video: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
