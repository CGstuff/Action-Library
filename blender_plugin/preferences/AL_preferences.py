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

        # Socket Communication Settings
        box = layout.box()
        box.label(text="Socket Communication", icon='URL')
        col = box.column(align=True)
        col.prop(self, "socket_port")

        # Desktop App Launch Settings
        box = layout.box()
        box.label(text="Desktop App Launch Configuration", icon='SETTINGS')

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

        # Studio Naming Settings
        box = layout.box()
        box.label(text="Studio Naming", icon='FILE_TEXT')

        box.prop(self, "studio_mode_enabled")

        if self.studio_mode_enabled:
            # Template preset selector
            col = box.column(align=True)
            col.label(text="Template:")
            col.prop(self, "naming_preset", text="")

            # Show template field only for custom mode
            if self.naming_preset == 'CUSTOM':
                col.separator()
                col.label(text="Custom Template:")
                col.prop(self, "naming_template", text="")

                # Show available fields reference
                fields_box = col.box()
                fields_box.label(text="Available Fields:", icon='INFO')
                fields_col = fields_box.column(align=True)
                fields_col.scale_y = 0.8
                fields_col.label(text="Core: {asset}, {show}, {project}, {shot}, {seq}, {task}, {variant}")
                fields_col.label(text="Character: {character}, {action}, {episode}")
                fields_col.label(text="Pipeline: {assetType}, {dept}, {layer}")
                fields_col.label(text="Aliases: {char}={character}, {ep}={episode}, {anim}={asset}")

            box.separator()

            # Version padding
            row = box.row(align=True)
            row.label(text="Version Format:")
            row.prop(self, "version_padding", text="Digits")

            # Show full template preview
            padding = self.version_padding
            version_suffix = f"_v{{version:0{padding}}}"
            full_template = f"{self.naming_template}{version_suffix}"
            example_version = "0" * (padding - 1) + "1"
            # Build example by replacing all supported fields
            example = self.naming_template
            field_examples = {
                "{asset}": "walk",
                "{show}": "SHOW",
                "{shot}": "0100",
                "{seq}": "010",
                "{task}": "anim",
                "{project}": "PROJ",
                "{assetType}": "char",
                "{dept}": "anim",
                "{variant}": "main",
                "{episode}": "E01",
                "{character}": "hero",
                "{action}": "run",
                "{layer}": "fg",
            }
            for field, value in field_examples.items():
                example = example.replace(field, value)
            example = f"{example}_v{example_version}"

            preview_box = box.box()
            preview_box.label(text=f"Template: {full_template}")
            preview_box.label(text=f"Example: {example}")

            box.separator()

            # Context mode
            col = box.column(align=True)
            col.label(text="Auto-fill Fields From:")
            col.prop(self, "context_mode", text="")

            # Show pattern input based on mode
            if self.context_mode == 'SCENE_NAME':
                col.separator()
                col.label(text="Pattern:")
                col.prop(self, "context_scene_pattern_preset", text="")

                # Show custom regex only if Custom is selected
                if self.context_scene_pattern_preset == 'CUSTOM':
                    col.separator()
                    col.label(text="Custom Regex (advanced):")
                    col.prop(self, "context_pattern_scene", text="")
                    col.label(text="Use (?P<field>\\w+) for named groups", icon='INFO')

                # Show current scene name for reference
                col.separator()
                col.label(text=f"Current scene: {bpy.context.scene.name}", icon='SCENE_DATA')

            elif self.context_mode == 'FOLDER_PATH':
                col.separator()
                col.label(text="Pattern:")
                col.prop(self, "context_folder_pattern_preset", text="")

                # Show custom regex only if Custom is selected
                if self.context_folder_pattern_preset == 'CUSTOM':
                    col.separator()
                    col.label(text="Custom Regex (advanced):")
                    col.prop(self, "context_pattern_folder", text="")
                    col.label(text="Use (?P<field>\\w+) for named groups", icon='INFO')

                # Show current file path for reference
                col.separator()
                filepath = bpy.data.filepath or "(file not saved)"
                if len(filepath) > 50:
                    filepath = "..." + filepath[-47:]
                col.label(text=f"Current path: {filepath}", icon='FILE_FOLDER')

            box.separator()
            box.label(text="Common fields: show, seq, shot, asset, task, project, variant", icon='INFO')

        # Debug Settings
        box = layout.box()
        box.label(text="Debug Settings", icon='CONSOLE')
        box.prop(self, "debug_mode", text="Enable Debug Logging")
        box.label(text="Enable for detailed console output during troubleshooting", icon='INFO')

        # Experimental Features
        box = layout.box()
        box.label(text="Experimental Features", icon='EXPERIMENTAL')
        box.prop(self, "experimental_features")
        if self.experimental_features:
            box.label(text="Experimental: Slot Management", icon='DOCUMENTS')


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


def is_experimental_enabled():
    """Check if experimental features are enabled in preferences"""
    try:
        addon_name = __name__.split('.')[0]
        if addon_name not in bpy.context.preferences.addons:
            return False
        prefs = bpy.context.preferences.addons[addon_name].preferences
        return prefs.experimental_features
    except Exception:
        return False

def get_preview_settings():
    """Get preview settings from preferences"""
    try:
        addon_name = __name__.split('.')[0]
        prefs = bpy.context.preferences.addons[addon_name].preferences
        return {
            'resolution_x': prefs.preview_resolution_x,
            'resolution_y': prefs.preview_resolution_y,
        }
    except:
        # Return default settings if preferences not available
        return {
            'resolution_x': 640,
            'resolution_y': 640,
        }


def get_naming_settings():
    """Get studio naming settings from preferences"""
    try:
        addon_name = __name__.split('.')[0]
        prefs = bpy.context.preferences.addons[addon_name].preferences

        # Get base template and version padding
        base_template = prefs.naming_template
        version_padding = getattr(prefs, 'version_padding', 3)

        # Auto-append version suffix (hardcoded, user cannot remove)
        full_template = f"{base_template}_v{{version:0{version_padding}}}"

        return {
            'studio_mode_enabled': prefs.studio_mode_enabled,
            'naming_template': full_template,
            'base_template': base_template,
            'version_padding': version_padding,
            'context_mode': prefs.context_mode,
            'context_pattern_scene': prefs.context_pattern_scene,
            'context_pattern_folder': prefs.context_pattern_folder
        }
    except:
        return {
            'studio_mode_enabled': False,
            'naming_template': '{asset}_v{version:03}',
            'base_template': '{asset}',
            'version_padding': 3,
            'context_mode': 'MANUAL',
            'context_pattern_scene': '',
            'context_pattern_folder': ''
        }