bl_info = {
    "name": "Action Library",
    "author": "CG_stuff",
    "version": (1, 4, 3),
    "blender": (4, 5, 0),  # Minimum version; supports up to 5.0+
    "location": "3D Viewport > Sidebar > Animation Library",
    "description": "Capture and manage Actions across different rig types",
    "category": "Animation",
}

import bpy
from bpy.app.handlers import persistent
from .utils import icon_loader
from .registration import register_all, unregister_all

_auto_sync_handler_added = False


@persistent
def _auto_sync_library_path(dummy):
    """Auto-sync library path from desktop app on file load (first-time setup only)."""
    try:
        addon_name = __name__.split('.')[0]
        if addon_name not in bpy.context.preferences.addons:
            return
        prefs = bpy.context.preferences.addons[addon_name].preferences
        # Only auto-sync if the addon has no path configured
        if prefs.actions_library_path:
            return
        from .preferences.AL_preferences import get_desktop_app_library_path
        desktop_path = get_desktop_app_library_path()
        if desktop_path:
            prefs.actions_library_path = desktop_path
            print(f"[Action Library] Auto-synced library path: {desktop_path}")
    except Exception:
        pass


def register():
    global _auto_sync_handler_added
    # Register icon loader first
    icon_loader.register()
    # Register all classes AFTER properties are defined
    register_all()

    # Add auto-sync handler
    if not _auto_sync_handler_added:
        bpy.app.handlers.load_post.append(_auto_sync_library_path)
        _auto_sync_handler_added = True

def unregister():
    global _auto_sync_handler_added
    # Remove auto-sync handler
    if _auto_sync_handler_added and _auto_sync_library_path in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_auto_sync_library_path)
        _auto_sync_handler_added = False

    unregister_all()

    # Unregister icon loader last
    icon_loader.unregister()

if __name__ == "__main__":
    register()