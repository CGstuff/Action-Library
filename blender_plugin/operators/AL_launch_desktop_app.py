import bpy
from bpy.types import Operator
from ..utils.logger import get_logger

# Initialize logger
logger = get_logger()

class ANIMLIB_OT_launch_desktop_app(Operator):
    """Launch the Animation Library desktop application"""
    bl_idname = "animlib.launch_desktop_app"
    bl_label = "Launch Desktop App"
    bl_description = "Launch the Animation Library desktop application"

    def execute(self, context):
        import sys
        import os
        import subprocess

        try:
            # Get addon preferences
            addon_name = __name__.split('.')[0]
            prefs = context.preferences.addons[addon_name].preferences

            # PRODUCTION MODE: Just launch the exe directly
            if prefs.desktop_app_launch_mode == 'PRODUCTION':
                if not prefs.desktop_app_exe_path:
                    self.report({'ERROR'}, "Please configure executable path in preferences")
                    return {'CANCELLED'}

                if not os.path.exists(prefs.desktop_app_exe_path):
                    self.report({'ERROR'}, f"Executable not found: {prefs.desktop_app_exe_path}")
                    return {'CANCELLED'}

                try:
                    # Launch exe in detached mode
                    subprocess.Popen([prefs.desktop_app_exe_path],
                                   creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                    self.report({'INFO'}, "Animation Library launched successfully")
                    return {'FINISHED'}
                except Exception as launch_error:
                    self.report({'ERROR'}, f"Failed to launch exe: {str(launch_error)}")
                    logger.error(f"Error launching exe: {launch_error}")
                    return {'CANCELLED'}

            # DEVELOPMENT MODE: Launch run.py directly
            if prefs.desktop_app_launch_mode == 'DEVELOPMENT':
                if not prefs.desktop_app_script_path:
                    self.report({'ERROR'}, "Please configure script path in preferences (run.py)")
                    return {'CANCELLED'}

                if not os.path.exists(prefs.desktop_app_script_path):
                    self.report({'ERROR'}, f"Script not found: {prefs.desktop_app_script_path}")
                    return {'CANCELLED'}

                # V2: Script path should point to run.py
                # Get v2 root from run.py location
                app_root = os.path.dirname(os.path.abspath(prefs.desktop_app_script_path))

                try:
                    # Launch run.py directly with Python
                    python_exe = prefs.python_executable_path or 'python'

                    subprocess.Popen(
                        [python_exe, prefs.desktop_app_script_path],
                        cwd=app_root,
                        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                    )

                    self.report({'INFO'}, "Animation Library v2 launched successfully (dev mode)")
                    return {'FINISHED'}
                except Exception as launch_error:
                    self.report({'ERROR'}, f"Failed to launch: {str(launch_error)}")
                    logger.error(f"Launch error: {launch_error}")
                    return {'CANCELLED'}

            # If we get here, no mode was selected
            self.report({'ERROR'}, "Please select a launch mode in preferences")
            return {'CANCELLED'}

        except ModuleNotFoundError as e:
            self.report({'ERROR'}, "Please configure script/executable path in preferences")
            logger.error(f"Module import error when launching app: {e}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to launch application: {str(e)}")
            logger.error(f"Error launching desktop app: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}