import bpy
from bpy.types import Operator
from ..utils.queue_client import animation_queue_client
from ..utils.utils import (get_action_keyframe_range, get_active_armature,
                   has_animation_data, safe_report_error)
from ..utils.logger import get_logger
from pathlib import Path
from ..preferences import get_preview_settings
from ..utils.viewport_manager import ViewportManager

# Initialize logger
logger = get_logger()

class ANIMLIB_OT_update_preview(Operator):
    """Update preview video and thumbnail for selected animation"""
    bl_idname = "animlib.update_preview"
    bl_label = "Update Preview"
    bl_description = "Re-render preview video and thumbnail for the selected animation in desktop app"

    # Modal operator state tracking
    _timer = None
    _state = None
    _context_data = None

    # Connection status cache to avoid checking every frame
    _connection_cache = {
        'available': False,
        'last_check': 0,
        'check_interval': 2.0  # Check every 2 seconds
    }

    @classmethod
    def poll(cls, context):
        """Check if the operator can run (desktop app must be running)"""
        # Check if armature with action exists
        armature = get_active_armature(context)
        if not armature or not has_animation_data(armature):
            return False

        # Check if desktop app (TCP server) is reachable (cached)
        return cls.is_server_available()

    @classmethod
    def is_server_available(cls):
        """Quick check if TCP server is available (with caching to avoid performance issues)"""
        import socket
        import time

        current_time = time.time()
        cache = cls._connection_cache

        # Return cached result if within check interval
        if current_time - cache['last_check'] < cache['check_interval']:
            return cache['available']

        # Perform actual check
        try:
            # Try to connect to the server with a very short timeout
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(0.05)  # 50ms timeout
            result = test_socket.connect_ex(('localhost', 8888))
            test_socket.close()
            is_available = (result == 0)
        except Exception:
            is_available = False

        # Update cache
        cache['available'] = is_available
        cache['last_check'] = current_time

        return is_available

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

        # Initialize state machine
        self._state = 'GET_SELECTED_UUID'
        self._context_data = {
            'armature': armature,
            'wm': wm,
            'scene': context.scene
        }

        # Add timer for modal updates
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        # Force UI update
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        """Handle modal execution"""
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        wm = self._context_data['wm']

        try:
            if self._state == 'GET_SELECTED_UUID':
                # Get selected animation UUID from desktop app
                # TODO: Queue-based implementation needed
                # response = animation_queue_client.get_selected_animation_uuid()
                response = {'status': 'error', 'message': 'Feature not yet implemented with queue system'}

                if response.get('status') != 'success':
                    self.report({'ERROR'}, "Failed to connect to desktop app")
                    self.cleanup(context)
                    return {'CANCELLED'}

                uuid = response.get('uuid')
                if not uuid:
                    self.report({'ERROR'}, "No animation selected in desktop app")
                    self.cleanup(context)
                    return {'CANCELLED'}

                # Get animation data
                animation_data = response.get('animation')
                if not animation_data:
                    self.report({'ERROR'}, "Failed to get animation data")
                    self.cleanup(context)
                    return {'CANCELLED'}

                self._context_data['uuid'] = uuid
                self._context_data['animation_data'] = animation_data
                self._state = 'UPDATE_PREVIEW'
                return {'RUNNING_MODAL'}

            elif self._state == 'UPDATE_PREVIEW':
                # Re-render preview and thumbnail
                uuid = self._context_data['uuid']
                animation_data = self._context_data['animation_data']
                armature = self._context_data['armature']
                scene = self._context_data['scene']

                success = self.update_preview_files(uuid, animation_data, armature, scene)

                if not success:
                    self.report({'ERROR'}, "Failed to update preview files")
                    self.cleanup(context)
                    return {'CANCELLED'}

                self._state = 'NOTIFY_DESKTOP'
                return {'RUNNING_MODAL'}

            elif self._state == 'NOTIFY_DESKTOP':
                # Notify desktop app to refresh preview
                uuid = self._context_data['uuid']
                # TODO: Queue-based implementation needed
                # response = animation_queue_client.notify_preview_updated(uuid)
                response = {'status': 'success'}

                if response.get('status') == 'success':
                    self.report({'INFO'}, "Preview updated successfully")
                else:
                    self.report({'WARNING'}, "Preview updated but desktop app notification failed")

                self.cleanup(context)
                return {'FINISHED'}

        except Exception as e:
            logger.error(f"Error during preview update: {str(e)}")
            self.report({'ERROR'}, f"Preview update failed: {str(e)}")
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

    def update_preview_files(self, uuid, animation_data, armature, scene):
        """Re-render preview video and thumbnail for existing animation"""
        try:
            # Get file paths from animation data
            preview_path = animation_data.get('preview_path')
            thumbnail_path = animation_data.get('thumbnail_path')

            if not preview_path or not thumbnail_path:
                logger.error("Missing preview or thumbnail path in animation data")
                return False

            # Get animation timing
            frame_start = animation_data.get('frame_start', scene.frame_start)
            frame_end = animation_data.get('frame_end', scene.frame_end)

            # Get active action's keyframe range
            action = armature.animation_data.action if armature.animation_data else None
            if action:
                keyframe_start, keyframe_end = get_action_keyframe_range(action)
                if keyframe_start is not None:
                    frame_start = keyframe_start
                    frame_end = keyframe_end

            # Get preview settings
            prefs = get_preview_settings()

            # Re-render thumbnail
            logger.info(f"Re-rendering thumbnail: {thumbnail_path}")
            self.render_thumbnail(armature, scene, thumbnail_path, frame_start, prefs)

            # Re-render preview video
            logger.info(f"Re-rendering preview video: {preview_path}")
            self.render_preview_video(armature, scene, preview_path, frame_start, frame_end, prefs)

            logger.info(f"Successfully updated preview files for animation: {uuid}")
            return True

        except Exception as e:
            logger.error(f"Error updating preview files: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def render_thumbnail(self, armature, scene, thumbnail_path, first_frame, prefs):
        """Render thumbnail from first frame"""
        # Store current settings
        original_filepath = scene.render.filepath
        original_format = scene.render.image_settings.file_format
        original_frame = scene.frame_current
        original_resolution_x = scene.render.resolution_x
        original_resolution_y = scene.render.resolution_y
        original_resolution_percentage = scene.render.resolution_percentage
        original_film_transparent = scene.render.film_transparent
        viewport_settings = None

        try:
            # Set to first frame
            scene.frame_set(first_frame)

            # Configure render settings
            scene.render.filepath = thumbnail_path
            scene.render.image_settings.file_format = 'PNG'
            scene.render.resolution_x = prefs['resolution_x']
            scene.render.resolution_y = prefs['resolution_y']
            scene.render.resolution_percentage = 100
            scene.render.film_transparent = True

            # Setup viewport for clean preview (uses current viewport angle)
            viewport_settings = ViewportManager.setup_viewport_for_preview(scene, prefs)

            # Render single frame
            bpy.ops.render.opengl(write_still=True)

            logger.debug(f"Created thumbnail: {thumbnail_path}")

        finally:
            # Always restore viewport settings first (overlays, gizmos, etc.)
            if viewport_settings:
                ViewportManager.restore_viewport_settings(viewport_settings)
                logger.info("Thumbnail render complete - viewport restored")
            else:
                logger.warning("No viewport settings captured - forcing overlay restore")
                self.force_restore_overlays()

            # Restore original render settings
            scene.render.filepath = original_filepath
            scene.render.image_settings.file_format = original_format
            scene.frame_set(original_frame)
            scene.render.resolution_x = original_resolution_x
            scene.render.resolution_y = original_resolution_y
            scene.render.resolution_percentage = original_resolution_percentage
            scene.render.film_transparent = original_film_transparent

    def render_preview_video(self, armature, scene, preview_path, frame_start, frame_end, prefs):
        """Render preview video"""

        # Store current settings
        original_filepath = scene.render.filepath
        original_format = scene.render.image_settings.file_format
        original_frame_start = scene.frame_start
        original_frame_end = scene.frame_end
        original_resolution_x = scene.render.resolution_x
        original_resolution_y = scene.render.resolution_y
        original_resolution_percentage = scene.render.resolution_percentage
        original_film_transparent = scene.render.film_transparent
        viewport_settings = None

        try:
            # Render to temporary MP4 first
            temp_mp4_path = str(preview_path).replace('.webm', '_temp.mp4')
            scene.render.filepath = temp_mp4_path
            scene.render.image_settings.file_format = 'FFMPEG'
            scene.render.ffmpeg.format = 'MPEG4'
            scene.render.ffmpeg.codec = 'H264'
            scene.render.ffmpeg.constant_rate_factor = 'HIGH'
            scene.render.resolution_x = prefs['resolution_x']
            scene.render.resolution_y = prefs['resolution_y']
            scene.render.resolution_percentage = 100
            scene.render.film_transparent = True

            # Set frame range
            scene.frame_start = frame_start
            scene.frame_end = frame_end

            # Setup viewport for clean preview (uses current viewport angle)
            viewport_settings = ViewportManager.setup_viewport_for_preview(scene, prefs)

            # Render animation
            ViewportManager.render_keyframe_range(scene, frame_start, frame_end)

            # Convert MP4 to transparent WebM
            self.convert_to_transparent_webm(temp_mp4_path, preview_path)

            logger.debug(f"Created preview video: {preview_path}")

        finally:
            # Always restore viewport settings first (overlays, gizmos, etc.)
            if viewport_settings:
                ViewportManager.restore_viewport_settings(viewport_settings)
                logger.info("Video render complete - viewport restored")
            else:
                logger.warning("No viewport settings captured - forcing overlay restore")
                self.force_restore_overlays()

            # Restore original render settings
            scene.render.filepath = original_filepath
            scene.render.image_settings.file_format = original_format
            scene.frame_start = original_frame_start
            scene.frame_end = original_frame_end
            scene.render.resolution_x = original_resolution_x
            scene.render.resolution_y = original_resolution_y
            scene.render.resolution_percentage = original_resolution_percentage
            scene.render.film_transparent = original_film_transparent

    def force_restore_overlays(self):
        """Force restore overlays on all 3D viewports as a fallback"""
        try:
            logger.info("Force restoring overlays on all viewports")
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.overlay.show_overlays = True
                            space.show_gizmo = True
                            space.show_region_ui = True
                            space.show_region_toolbar = True
                            space.show_region_header = True
                            area.tag_redraw()
                            logger.info("Forced overlay restoration complete")
        except Exception as e:
            logger.error(f"Error forcing overlay restore: {e}")

    def convert_to_transparent_webm(self, mp4_path, webm_path):
        """Convert MP4 to transparent WebM using FFmpeg"""
        import subprocess
        import os

        try:
            # Check if FFmpeg is available
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("FFmpeg not found, keeping MP4 format")
                if os.path.exists(mp4_path):
                    os.rename(mp4_path, webm_path)
                return

            # Convert to WebM with transparency using colorkey filter
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', mp4_path,
                '-c:v', 'libvpx-vp9',
                '-pix_fmt', 'yuva420p',
                '-vf', 'colorkey=0x000000:0.3:0.2',
                '-b:v', '1M',
                '-crf', '30',
                '-an',
                webm_path
            ]

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                # Remove temporary MP4
                if os.path.exists(mp4_path):
                    os.remove(mp4_path)
                logger.debug("Converted to transparent WebM")
            else:
                logger.warning(f"FFmpeg conversion failed, keeping MP4")
                if os.path.exists(mp4_path):
                    os.rename(mp4_path, webm_path)

        except Exception as e:
            logger.error(f"Error converting to WebM: {e}")
            if os.path.exists(mp4_path):
                os.rename(mp4_path, webm_path)
