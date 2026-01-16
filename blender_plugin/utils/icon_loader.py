"""
Icon loader system for the Animation Library Blender addon.

This module handles loading custom icons from PNG files and managing icon IDs
for use in Blender UI elements.

IMPORTANT: Icon Source Files
-----------------------------
- Source icons are SVG files located in: ui/icons/
- PNG versions are automatically generated during build via: tools/svg_to_png_converter.py
- Run pre_build.py before building to convert SVG → PNG for Blender
- This icons/ directory should contain PNG files generated from SVG sources

Blender requires PNG/raster images. SVG files are used as the master source
and converted to PNG automatically during the build process.
"""

import bpy
import bpy.utils.previews
import os
from .logger import get_logger

logger = get_logger()

# Global variable to store icon previews
preview_collections = {}


def get_icon_id(icon_name):
    """
    Get the icon ID for a given icon name.

    Args:
        icon_name: Name of the icon file without extension (e.g., "AL" for "AL.png")

    Returns:
        Icon ID that can be used in Blender UI, or 0 if icon not found
    """
    pcoll = preview_collections.get("main")
    if pcoll and icon_name in pcoll:
        return pcoll[icon_name].icon_id
    else:
        logger.warning(f"Icon '{icon_name}' not found, using default")
        return 0


def register():
    """
    Register icon previews and load all icons from the icons directory.
    Called when the addon is enabled.
    """
    import bpy.utils.previews

    # Create a new preview collection
    pcoll = bpy.utils.previews.new()

    # Get the icons directory path
    icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons")
    if not os.path.exists(icons_dir):
        logger.error(f"Icons directory not found: {icons_dir}")
        preview_collections["main"] = pcoll
        return

    # Load all PNG files from the icons directory
    icon_count = 0
    for filename in os.listdir(icons_dir):
        if filename.endswith(".png"):
            icon_name = os.path.splitext(filename)[0]  # Remove .png extension
            icon_path = os.path.join(icons_dir, filename)

            try:
                # Load the icon
                pcoll.load(icon_name, icon_path, 'IMAGE')
                logger.debug(f"Loaded icon: {icon_name} from {icon_path}")
                icon_count += 1
            except Exception as e:
                logger.error(f"Failed to load icon {icon_name}: {e}")

    logger.info(f"Icon loader registered: {icon_count} icons loaded from {icons_dir}")

    # Store the preview collection
    preview_collections["main"] = pcoll


def unregister():
    """
    Unregister icon previews and clean up resources.
    Called when the addon is disabled.
    """
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()

    logger.info("Icon loader unregistered")


# Icon name constants for easy reference
# Add new icon names here as you create them
class Icons:
    """Constants for icon names used in the addon"""
    LAUNCH_APP = "AL"  # Animation Library launch icon
