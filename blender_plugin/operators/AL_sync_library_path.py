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

        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        old_path = prefs.actions_library_path

        if old_path == desktop_path:
            self.report({'INFO'}, f"Library path already matches: {desktop_path}")
            return {'FINISHED'}

        prefs.actions_library_path = desktop_path
        self.report({'INFO'}, f"Library path synced: {desktop_path}")
        return {'FINISHED'}
