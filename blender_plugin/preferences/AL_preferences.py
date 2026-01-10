import bpy
from bpy.types import AddonPreferences
from ..properties.AL_preferences_properties import ANIMLIB_PreferencesProperties
import os

class ANIMLIB_AddonPreferences(AddonPreferences, ANIMLIB_PreferencesProperties):
    bl_idname = __name__.split('.')[0]  # Gets the addon name

    def draw(self, context):
        layout = self.layout
        
        # Library Path Settings
        box = layout.box()
        box.label(text="Animation Library Settings", icon='PREFERENCES')
        
        row = box.row()
        row.prop(self, "actions_library_path")
        
        # Show current path status
        if self.actions_library_path:
            if os.path.exists(self.actions_library_path):
                box.label(text=f"✓ Path exists: {self.actions_library_path}", icon='CHECKMARK')
            else:
                box.label(text=f"✗ Path not found: {self.actions_library_path}", icon='ERROR')
        else:
            box.label(text="Please set the actions library path", icon='INFO')
        
        # Helper buttons
        row = box.row()
        row.operator("animlib.create_library_folder", text="Create Library Folder")
        
        # Preview Settings
        box = layout.box()
        box.label(text="Preview Generation Settings", icon='RENDER_ANIMATION')
        
        # Resolution settings
        col = box.column(align=True)
        col.label(text="Resolution:")
        row = col.row(align=True)
        row.prop(self, "preview_resolution_x")
        row.prop(self, "preview_resolution_y")
        
        # Quality settings
        col = box.column(align=True)
        col.prop(self, "preview_quality")
        col.prop(self, "preview_background")
        col.prop(self, "preview_use_lighting")

        # Transparent video info
        box.separator()
        box.label(text="Animation previews created as transparent WebM videos", icon='INFO')
        box.label(text="Background gradients customizable in desktop app", icon='INFO')
        box.label(text="Requires FFmpeg 6.0+ (see FFMPEG_INSTALL.md)", icon='URL')

        # Preview info
        box.label(text="Previews use viewport shading with overlays disabled for clean output", icon='INFO')

        # Desktop App Launch Settings
        box = layout.box()
        box.label(text="Desktop App Launch Configuration", icon='SETTINGS')

        # Info about where to actually launch
        info_row = box.row()
        info_row.label(text="Launch from: 3D Viewport > Animation Library panel", icon='INFO')

        box.separator()

        # Launch mode selector
        col = box.column(align=True)
        col.prop(self, "desktop_app_launch_mode", text="Mode")

        box.separator()

        # Production mode settings
        if self.desktop_app_launch_mode == 'PRODUCTION':
            col = box.column(align=True)
            col.label(text="Executable Path:")
            col.prop(self, "desktop_app_exe_path", text="")

            # Show path status
            if self.desktop_app_exe_path:
                if os.path.exists(self.desktop_app_exe_path):
                    col.label(text="✓ Executable found", icon='CHECKMARK')
                else:
                    col.label(text="✗ Executable not found", icon='ERROR')
            else:
                col.label(text="Please select AnimationLibrary.exe", icon='INFO')

            box.separator()
            box.label(text="Build executable with: build.bat", icon='INFO')
            box.label(text="Location: dist/AnimationLibrary/AnimationLibrary.exe", icon='INFO')

        # Development mode settings
        else:
            col = box.column(align=True)
            col.label(text="Python Script Path:")
            col.prop(self, "desktop_app_script_path", text="")

            # Show script status
            if self.desktop_app_script_path:
                if os.path.exists(self.desktop_app_script_path):
                    col.label(text="✓ Script found", icon='CHECKMARK')
                else:
                    col.label(text="✗ Script not found", icon='ERROR')
            else:
                col.label(text="Please select studio_main.py", icon='INFO')

            box.separator()

            col = box.column(align=True)
            col.label(text="Python Executable:")
            col.prop(self, "python_executable_path", text="")
            col.label(text="(Leave as 'python' to use system default)", icon='INFO')

        # Optional test launch from preferences
        box.separator()
        row = box.row()
        row.scale_y = 1.0
        row.operator("animlib.launch_desktop_app", text="Test Launch", icon='PLAY')
        row.label(text="(or use main panel)", icon='INFO')

        # Debug Settings
        box = layout.box()
        box.label(text="Debug Settings", icon='CONSOLE')
        box.prop(self, "debug_mode", text="Enable Debug Logging")
        box.label(text="Enable for detailed console output during troubleshooting", icon='INFO')


def get_library_path():
    """Get the actions library path from preferences"""
    try:
        addon_name = __name__.split('.')[0]
        if addon_name not in bpy.context.preferences.addons:
            return ""
        prefs = bpy.context.preferences.addons[addon_name].preferences
        return prefs.actions_library_path
    except Exception:
        return ""

def get_preview_settings():
    """Get preview settings from preferences"""
    try:
        addon_name = __name__.split('.')[0]
        prefs = bpy.context.preferences.addons[addon_name].preferences
        return {
            'resolution_x': prefs.preview_resolution_x,
            'resolution_y': prefs.preview_resolution_y,
            'quality': prefs.preview_quality,
            'use_lighting': prefs.preview_use_lighting,
            'background': prefs.preview_background
        }
    except:
        # Return default settings if preferences not available
        return {
            'resolution_x': 640,
            'resolution_y': 480,
            'quality': 'MEDIUM',
            'use_lighting': True,
            'background': 'GRAY'
        }