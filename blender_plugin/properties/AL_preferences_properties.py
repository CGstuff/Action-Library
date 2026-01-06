import bpy
from bpy.types import PropertyGroup

class ANIMLIB_PreferencesProperties(PropertyGroup):
    actions_library_path: bpy.props.StringProperty(
        name="Actions Library Path",
        description="Path where animation actions (.blend files) are stored",
        default="",
        maxlen=1024,
        subtype='DIR_PATH'
    )
    
    # Preview Settings
    preview_resolution_x: bpy.props.IntProperty(
        name="Preview Width",
        description="Width resolution for animation previews",
        default=640,
        min=320,
        max=1920
    )
    
    preview_resolution_y: bpy.props.IntProperty(
        name="Preview Height",
        description="Height resolution for animation previews",
        default=640,
        min=240,
        max=1080
    )

    preview_quality: bpy.props.EnumProperty(
        name="Preview Quality",
        description="Quality settings for viewport preview generation",
        items=[
            ('LOW', 'Low', 'Fast viewport render with flat lighting'),
            ('MEDIUM', 'Medium', 'Solid shading with studio lighting'),
            ('HIGH', 'High', 'High quality solid shading with enhanced lighting')
        ],
        default='MEDIUM'
    )

    preview_use_lighting: bpy.props.BoolProperty(
        name="Use Custom Lighting",
        description="Add custom lighting setup for better preview quality",
        default=True
    )

    preview_background: bpy.props.EnumProperty(
        name="Preview Background",
        description="Background for animation previews",
        items=[
            ('TRANSPARENT', 'Transparent', 'Transparent background'),
            ('WHITE', 'White', 'White background'),
            ('GRAY', 'Gray', 'Gray background'),
            ('BLACK', 'Black', 'Black background')
        ],
        default='GRAY'
    )

    # Desktop App Launch Settings
    desktop_app_launch_mode: bpy.props.EnumProperty(
        name="Launch Mode",
        description="How to launch the desktop application",
        items=[
            ('PRODUCTION', 'Production (Executable)', 'Launch compiled .exe file'),
            ('DEVELOPMENT', 'Development (Python Script)', 'Launch Python script directly (requires Python environment)')
        ],
        default='PRODUCTION'
    )

    desktop_app_exe_path: bpy.props.StringProperty(
        name="Executable Path",
        description="Path to the compiled AnimationLibrary.exe",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )

    desktop_app_script_path: bpy.props.StringProperty(
        name="Script Path",
        description="Path to studio_main.py (for development mode)",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )

    python_executable_path: bpy.props.StringProperty(
        name="Python Executable",
        description="Path to Python executable (python.exe)",
        default="python",
        maxlen=1024,
        subtype='FILE_PATH'
    )

    # Debug Settings
    debug_mode: bpy.props.BoolProperty(
        name="Debug Mode",
        description="Enable detailed logging for troubleshooting",
        default=False
    )
