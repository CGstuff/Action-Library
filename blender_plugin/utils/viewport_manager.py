"""
Viewport management for animation preview rendering
Extracted from operators.py to follow Single Responsibility Principle
"""
import bpy
from typing import Dict
from .logger import get_logger

# Initialize logger
logger = get_logger()


class ViewportManager:
    """Handles viewport configuration for preview rendering"""

    @staticmethod
    def setup_viewport_for_preview(scene, prefs: Dict) -> Dict:
        """
        Configure viewport shading for preview rendering

        Args:
            scene: Blender scene
            prefs: Preview preferences

        Returns:
            Dictionary of original settings to restore
        """
        try:
            viewport_settings = {}

            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Store original settings
                            viewport_settings = {
                                'show_overlays': space.overlay.show_overlays,
                                'show_gizmo': space.show_gizmo,
                                'show_region_ui': space.show_region_ui,
                                'show_region_toolbar': space.show_region_toolbar,
                                'show_region_header': space.show_region_header,
                                'shading_type': space.shading.type,
                            }

                            # Configure for clean preview
                            space.shading.type = 'SOLID'
                            space.overlay.show_overlays = False
                            space.show_gizmo = False
                            space.show_region_ui = False
                            space.show_region_toolbar = False
                            space.show_region_header = False

                            # Configure lighting
                            ViewportManager._setup_lighting(space, prefs)

                            return viewport_settings
                    break

            return viewport_settings

        except Exception as e:
            logger.error(f"Error setting up viewport for preview: {e}")
            return {}

    @staticmethod
    def _setup_lighting(space, prefs: Dict) -> None:
        """Setup viewport lighting based on preferences"""
        if prefs.get('use_lighting', True):
            if prefs.get('quality', 'MEDIUM') == 'LOW':
                space.shading.light = 'FLAT'
            else:
                space.shading.light = 'STUDIO'
                space.shading.studio_light = 'forest.exr'
                space.shading.studiolight_intensity = 1.0
        else:
            space.shading.light = 'FLAT'

    @staticmethod
    def restore_viewport_settings(viewport_settings: Dict) -> None:
        """
        Restore original viewport settings after preview generation

        Args:
            viewport_settings: Settings dictionary from setup_viewport_for_preview
        """
        try:
            if not viewport_settings:
                logger.warning("No viewport settings to restore")
                return

            restored = False
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            logger.info(f"Restoring viewport settings: overlays={viewport_settings.get('show_overlays', True)}")
                            space.overlay.show_overlays = viewport_settings.get('show_overlays', True)
                            space.show_gizmo = viewport_settings.get('show_gizmo', True)
                            space.show_region_ui = viewport_settings.get('show_region_ui', True)
                            space.show_region_toolbar = viewport_settings.get('show_region_toolbar', True)
                            space.show_region_header = viewport_settings.get('show_region_header', True)
                            space.shading.type = viewport_settings.get('shading_type', 'SOLID')

                            # Force viewport redraw to show changes
                            area.tag_redraw()
                            restored = True
                            break
                    break

            if restored:
                logger.info("Viewport settings restored successfully")
            else:
                logger.warning("Could not find VIEW_3D area to restore settings")

        except Exception as e:
            logger.error(f"Error restoring viewport settings: {e}")
            import traceback
            logger.error(traceback.format_exc())

    @staticmethod
    def render_keyframe_range(scene, keyframe_start: int, keyframe_end: int) -> None:
        """
        Render animation using keyframe range without modifying scene timeline

        Args:
            scene: Blender scene
            keyframe_start: Start frame
            keyframe_end: End frame
        """
        try:
            # Store current frame and timeline
            original_frame = scene.frame_current
            original_start = scene.frame_start
            original_end = scene.frame_end

            # Temporarily set the scene range for the animation render only
            scene.frame_start = keyframe_start
            scene.frame_end = keyframe_end

            # Use built-in OpenGL animation render
            bpy.ops.render.opengl(animation=True)

            # Immediately restore original timeline
            scene.frame_start = original_start
            scene.frame_end = original_end
            scene.frame_current = original_frame

        except Exception as e:
            logger.error(f"Error rendering keyframe range: {e}")
            # Make sure we restore timeline even if there's an error
            try:
                scene.frame_start = original_start
                scene.frame_end = original_end
                scene.frame_current = original_frame
            except:
                pass
