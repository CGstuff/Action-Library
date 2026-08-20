bl_info = {
    "name": "Action Library",
    "author": "CG_stuff",
    "version": (1, 5, 1),
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
    """Sync the library path from the desktop app on file load.

    This used to bail out early whenever the addon already had *any* path set,
    which made it a one-time setup step: the first sync worked, and after that
    the addon never looked at the desktop app again. Changing the library
    location in the app therefore left Blender pointed at the old one until you
    hit the refresh button by hand.

    The desktop app owns the library location, so we always take its value.
    """
    try:
        from .utils.library_path_sync import sync_now
        sync_now(force=True)
    except Exception:
        pass


def register():
    global _auto_sync_handler_added

    # Addon updater - checks github.com/CGstuff/Action-Library for newer release
    # tags and can update the addon in place.
    #
    # Wrapped: the updater is an OPTIONAL extra, so a failure inside it must
    # never stop Action Library itself from loading. (It did exactly that once -
    # an invalid config value raised during its register(), which aborted this
    # whole function and left the addon with no panel and no preferences.)
    try:
        from . import addon_updater_ops
        addon_updater_ops.register(bl_info)
    except Exception as e:
        print(f"[Action Library] Addon updater failed to register (continuing without it): {e}")

    # Register icon loader first
    icon_loader.register()
    # Register all classes AFTER properties are defined
    register_all()

    # Add auto-sync handler
    if not _auto_sync_handler_added:
        bpy.app.handlers.load_post.append(_auto_sync_library_path)
        _auto_sync_handler_added = True

    # Watch the desktop app's pointer file, so changing the library location in
    # the app reaches Blender within a couple of seconds instead of waiting for
    # the next file load.
    from .utils.library_path_sync import start_path_sync
    start_path_sync()

def unregister():
    global _auto_sync_handler_added

    try:
        from . import addon_updater_ops
        addon_updater_ops.unregister()
    except Exception:
        pass

    from .utils.library_path_sync import stop_path_sync
    stop_path_sync()

    # Remove auto-sync handler
    if _auto_sync_handler_added and _auto_sync_library_path in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_auto_sync_library_path)
        _auto_sync_handler_added = False

    unregister_all()

    # Unregister icon loader last
    icon_loader.unregister()

if __name__ == "__main__":
    register()