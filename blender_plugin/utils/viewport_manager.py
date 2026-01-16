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

                            # Use STUDIO lighting for quality previews
                            space.shading.light = 'STUDIO'
                            # Try studio lights in order of preference
                            for light in ['studio.sl', 'rim.sl', 'outdoor.sl', 'Default']:
                                try:
                                    space.shading.studio_light = light
                                    logger.debug(f"Using studio light: {light}")
                                    break
                                except TypeError:
                                    continue
                            space.shading.studiolight_intensity = 1.0

                            return viewport_settings
                    break

            return viewport_settings

        except Exception as e:
            logger.error(f"Error setting up viewport for preview: {e}")
            return {}

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
        original_frame = scene.frame_current
        original_start = scene.frame_start
        original_end = scene.frame_end

        try:
            # Temporarily set the scene range for the animation render only
            scene.frame_start = keyframe_start
            scene.frame_end = keyframe_end

            frame_count = keyframe_end - keyframe_start + 1
            logger.info(f"[RENDER] Starting OpenGL animation render: {frame_count} frames ({keyframe_start}-{keyframe_end})")

            # Find a 3D View area for context override (required for Blender 4.0+/5.0)
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

            # Use context override with view_context=True for proper viewport render
            if view3d_area and view3d_region:
                with bpy.context.temp_override(area=view3d_area, region=view3d_region):
                    result = bpy.ops.render.opengl(animation=True, view_context=True)
                    logger.debug(f"render.opengl result: {result}")
            else:
                logger.warning("No 3D View found for viewport render, trying without override")
                result = bpy.ops.render.opengl(animation=True, view_context=True)
                logger.debug(f"render.opengl result: {result}")

            logger.info("[RENDER] OpenGL animation render complete")

            # Immediately restore original timeline
            scene.frame_start = original_start
            scene.frame_end = original_end
            scene.frame_current = original_frame

        except Exception as e:
            logger.error(f"Error rendering keyframe range: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Make sure we restore timeline even if there's an error
            try:
                scene.frame_start = original_start
                scene.frame_end = original_end
                scene.frame_current = original_frame
            except:
                pass
