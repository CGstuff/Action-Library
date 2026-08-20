import bpy
from bpy.types import Operator

from ..preferences.AL_preferences import get_desktop_app_library_path


class ANIMLIB_OT_sync_library_path(Operator):
    """Sync the library path from the Action Library desktop app"""
    bl_idname = "animlib.sync_library_path"
    bl_label = "Sync Library Path from Desktop App"

    def execute(self, context):
        desktop_path = get_desktop_app_library_path()
        if not desktop_path:
            self.report({'WARNING'}, "Desktop app library path not found. "
                        "Set it in the Action Library desktop app first.")
            return {'CANCELLED'}

        # Route through sync_now() rather than assigning here: it's the single
        # place that knows how to read the pointer, and force=True refreshes the
        # mtime cache the background timer relies on. Assigning directly would
        # leave that cache stale.
        from ..utils.library_path_sync import sync_now
        changed = sync_now(force=True)

        if changed:
            self.report({'INFO'}, f"Library path synced: {desktop_path}")
        else:
            self.report({'INFO'}, f"Library path already matches: {desktop_path}")
        return {'FINISHED'}
