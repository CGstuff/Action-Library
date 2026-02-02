import bpy
from bpy.types import PropertyGroup

# Template preset definitions
NAMING_PRESETS = {
    'SIMPLE': '{asset}',
    'PROJECT': '{project}_{asset}',
    'SHOT': '{show}_{seq}_{shot}_{task}',
    'FULL': '{show}_{assetType}_{asset}_{dept}_{variant}',
    # Extended presets
    'SERIES': '{show}_{episode}_{shot}_{task}',
    'GAME': '{project}_{character}_{action}',
    'ASSET': '{show}_{asset}_{task}',
    'CHARACTER': '{show}_{character}_{action}',
    'CINEMATIC': '{project}_{seq}_{shot}_{layer}',
}

# Scene name pattern presets (regex with named groups)
SCENE_PATTERN_PRESETS = {
    'SHOW_SEQ_SHOT': r'(?P<show>\w+)_(?P<seq>\w+)_(?P<shot>\w+)',
    'SHOW_SHOT': r'(?P<show>\w+)_(?P<shot>\w+)',
    'SHOW_ASSET': r'(?P<show>\w+)_(?P<asset>\w+)',
    'PROJECT_ASSET': r'(?P<project>\w+)_(?P<asset>\w+)',
    # Extended presets
    'SHOW_EP_SHOT': r'(?P<show>\w+)_(?P<episode>E?\d+)_(?P<shot>\w+)',
    'PROJECT_CHAR_ACTION': r'(?P<project>\w+)_(?P<character>\w+)_(?P<action>\w+)',
    'SHOW_CHAR_ACTION': r'(?P<show>\w+)_(?P<character>\w+)_(?P<action>\w+)',
}

# Folder path pattern presets (regex with named groups)
FOLDER_PATTERN_PRESETS = {
    'SHOW_SEQ_SHOT': r'/(?P<show>\w+)/(?P<seq>\w+)/(?P<shot>\w+)/',
    'SHOW_SHOT': r'/(?P<show>\w+)/shots/(?P<shot>\w+)/',
    'PROJECT_ASSET': r'/(?P<project>\w+)/assets/(?P<asset>\w+)/',
    # Extended presets
    'SHOW_EP_SHOT': r'/(?P<show>\w+)/(?P<episode>ep\d+|EP\d+|e\d+)/(?P<shot>\w+)/',
    'PROJECT_CHAR': r'/(?P<project>\w+)/characters/(?P<character>\w+)/',
    'SHOW_SEQ_SHOT_TASK': r'/(?P<show>\w+)/(?P<seq>\w+)/(?P<shot>\w+)/(?P<task>\w+)/',
    'GAME_ANIM': r'/(?P<project>\w+)/animations/(?P<character>\w+)/(?P<action>\w+)/',
}


def update_naming_preset(self, context):
    """Update naming_template when preset changes."""
    if self.naming_preset != 'CUSTOM':
        self.naming_template = NAMING_PRESETS.get(self.naming_preset, '{asset}')


def update_scene_pattern_preset(self, context):
    """Update context_pattern_scene when preset changes."""
    if self.context_scene_pattern_preset != 'CUSTOM':
        self.context_pattern_scene = SCENE_PATTERN_PRESETS.get(
            self.context_scene_pattern_preset, ''
        )


def update_folder_pattern_preset(self, context):
    """Update context_pattern_folder when preset changes."""
    if self.context_folder_pattern_preset != 'CUSTOM':
        self.context_pattern_folder = FOLDER_PATTERN_PRESETS.get(
            self.context_folder_pattern_preset, ''
        )


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
    
    preview_use_camera: bpy.props.BoolProperty(
        name="Use Scene Camera",
        description="Render thumbnails/previews from scene camera instead of current viewport angle. Provides consistent framing if you have a camera set up",
        default=False
    )

    # Socket Communication Settings
    socket_port: bpy.props.IntProperty(
        name="Socket Port",
        description="TCP port for communication with desktop app (must match app settings)",
        default=9876,
        min=1024,
        max=65535
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

    # Experimental Features
    experimental_features: bpy.props.BoolProperty(
        name="Enable Experimental Features",
        description="Show experimental features that are still in development (use at your own risk)",
        default=False
    )

    # Studio Naming Settings
    studio_mode_enabled: bpy.props.BoolProperty(
        name="Enable Studio Mode",
        description="Use template-based naming for animations",
        default=False
    )

    naming_preset: bpy.props.EnumProperty(
        name="Template Preset",
        description="Choose a preset naming template or create your own",
        items=[
            ('SIMPLE', 'Simple', 'Basic naming: {asset} → walk_v001'),
            ('PROJECT', 'Project', 'Project + asset: {project}_{asset} → MYPROJ_walk_v001'),
            ('SHOT', 'Shot-based', 'Full shot context: {show}_{seq}_{shot}_{task} → SHOW_010_0100_anim_v001'),
            ('FULL', 'Full Pipeline', 'Complete pipeline: {show}_{assetType}_{asset}_{dept}_{variant}'),
            ('SERIES', 'TV Series', 'Episodic content: {show}_{episode}_{shot}_{task} → SHOW_E01_0100_anim_v001'),
            ('GAME', 'Game Animation', 'Game dev: {project}_{character}_{action} → HERO_warrior_run_v001'),
            ('ASSET', 'Asset-focused', 'Simple asset: {show}_{asset}_{task} → PROJ_hero_walk_v001'),
            ('CHARACTER', 'Character', 'Character animation: {show}_{character}_{action} → SHOW_hero_jump_v001'),
            ('CINEMATIC', 'Cinematic', 'Cutscenes/VFX: {project}_{seq}_{shot}_{layer} → PROJ_010_0100_fg_v001'),
            ('CUSTOM', 'Custom', 'Define your own template'),
        ],
        default='SIMPLE',
        update=update_naming_preset
    )

    naming_template: bpy.props.StringProperty(
        name="Naming Template",
        description="Base template for animation names. Use {field} placeholders. Version suffix is added automatically",
        default="{asset}"
    )

    version_padding: bpy.props.IntProperty(
        name="Version Padding",
        description="Number of digits for version number (e.g., 3 = v001, 4 = v0001)",
        default=3,
        min=1,
        max=6
    )

    context_mode: bpy.props.EnumProperty(
        name="Context Mode",
        description="How to extract naming fields automatically",
        items=[
            ('MANUAL', 'Manual Entry', 'Enter all fields manually'),
            ('SCENE_NAME', 'From Scene Name', 'Extract fields from Blender scene name'),
            ('FOLDER_PATH', 'From Folder Path', 'Extract fields from .blend file path')
        ],
        default='MANUAL'
    )

    # Scene name pattern presets
    context_scene_pattern_preset: bpy.props.EnumProperty(
        name="Scene Pattern",
        description="Choose a pattern to extract fields from scene name",
        items=[
            ('SHOW_SEQ_SHOT', 'SHOW_SEQ_SHOT', 'e.g., MYSHOW_010_0100 extracts show, seq, shot'),
            ('SHOW_SHOT', 'SHOW_SHOT', 'e.g., MYSHOW_0100 extracts show, shot'),
            ('SHOW_ASSET', 'SHOW_ASSET', 'e.g., MYSHOW_walk extracts show, asset'),
            ('PROJECT_ASSET', 'PROJECT_ASSET', 'e.g., PROJECT_walk extracts project, asset'),
            ('SHOW_EP_SHOT', 'SHOW_EP_SHOT', 'e.g., MYSHOW_E01_0100 extracts show, episode, shot'),
            ('PROJECT_CHAR_ACTION', 'PROJECT_CHAR_ACTION', 'e.g., HERO_warrior_run extracts project, character, action'),
            ('SHOW_CHAR_ACTION', 'SHOW_CHAR_ACTION', 'e.g., SHOW_hero_jump extracts show, character, action'),
            ('CUSTOM', 'Custom Regex', 'Define your own regex pattern (advanced)'),
        ],
        default='SHOW_SEQ_SHOT',
        update=update_scene_pattern_preset
    )

    context_pattern_scene: bpy.props.StringProperty(
        name="Scene Name Pattern",
        description="Regex pattern with named groups to extract fields from scene name. Example: (?P<show>\\w+)_(?P<shot>\\w+)",
        default=r"(?P<show>\w+)_(?P<seq>\w+)_(?P<shot>\w+)"
    )

    # Folder path pattern presets
    context_folder_pattern_preset: bpy.props.EnumProperty(
        name="Folder Pattern",
        description="Choose a pattern to extract fields from file path",
        items=[
            ('SHOW_SEQ_SHOT', 'show/seq/shot/', 'e.g., /MYSHOW/010/0100/ extracts show, seq, shot'),
            ('SHOW_SHOT', 'show/shots/shot/', 'e.g., /MYSHOW/shots/0100/ extracts show, shot'),
            ('PROJECT_ASSET', 'project/assets/asset/', 'e.g., /PROJECT/assets/walk/ extracts project, asset'),
            ('SHOW_EP_SHOT', 'show/episode/shot/', 'e.g., /MYSHOW/EP01/0100/ extracts show, episode, shot'),
            ('PROJECT_CHAR', 'project/characters/char/', 'e.g., /HERO/characters/warrior/ extracts project, character'),
            ('SHOW_SEQ_SHOT_TASK', 'show/seq/shot/task/', 'e.g., /SHOW/010/0100/anim/ extracts show, seq, shot, task'),
            ('GAME_ANIM', 'project/animations/char/action/', 'e.g., /GAME/animations/hero/run/ extracts project, character, action'),
            ('CUSTOM', 'Custom Regex', 'Define your own regex pattern (advanced)'),
        ],
        default='SHOW_SEQ_SHOT',
        update=update_folder_pattern_preset
    )

    context_pattern_folder: bpy.props.StringProperty(
        name="Folder Path Pattern",
        description="Regex pattern with named groups to extract fields from file path. Example: /(?P<show>\\w+)/(?P<seq>\\w+)/(?P<shot>\\w+)/",
        default=r"/(?P<show>\w+)/(?P<seq>\w+)/(?P<shot>\w+)/"
    )
