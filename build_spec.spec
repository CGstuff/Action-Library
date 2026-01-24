# -*- mode: python ; coding: utf-8 -*-
"""
Action Library - PyInstaller Spec File

Build command:
    pyinstaller build_spec.spec

Output:
    dist/ActionLibrary/
        ActionLibrary.exe
        _internal/
        storage/  (created by build.bat)
"""

import os
from pathlib import Path

block_cipher = None

# Get the project root directory
PROJECT_ROOT = Path(SPECPATH)

# Data files to include
datas = [
    # Application icon (for window/taskbar icon at runtime)
    (str(PROJECT_ROOT / 'AL.ico'), '.'),

    # Assets (Icon.png for about/wizard)
    (str(PROJECT_ROOT / 'assets'), 'assets'),

    # Icons (SVG files)
    (str(PROJECT_ROOT / 'animation_library' / 'icons'), 'animation_library/icons'),

    # Folder preset icons
    (str(PROJECT_ROOT / 'animation_library' / 'icons' / 'folder_presets'), 'animation_library/icons/folder_presets'),

    # Themes (JSON files)
    (str(PROJECT_ROOT / 'animation_library' / 'themes' / 'built_in'), 'animation_library/themes/built_in'),
    (str(PROJECT_ROOT / 'animation_library' / 'themes' / 'custom'), 'animation_library/themes/custom'),

    # Blender plugin (for addon installer feature)
    (str(PROJECT_ROOT / 'blender_plugin'), 'blender_plugin'),

    # Installation script (must be physical file for Blender to run it)
    (str(PROJECT_ROOT / 'animation_library' / 'services' / 'utils' / 'install_addon.py'), 'animation_library/services/utils'),
]

# Version file (injected by build process)
version_file = PROJECT_ROOT / 'animation_library' / 'version.txt'
if version_file.exists():
    datas.append((str(version_file), 'animation_library'))

# Include ffmpeg binary if present (for video preview generation)
ffmpeg_path = PROJECT_ROOT / 'blender_plugin' / 'bin' / 'ffmpeg.exe'
if ffmpeg_path.exists():
    datas.append((str(ffmpeg_path), 'blender_plugin/bin'))

# Hidden imports that PyInstaller might miss
hiddenimports = [
    # PyQt6 modules
    'PyQt6.QtSvg',
    'PyQt6.QtSvgWidgets',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',

    # OpenCV for video processing
    'cv2',

    # Standard library modules that might be dynamically imported
    'json',
    'sqlite3',
    'logging.handlers',
    'pathlib',
    'typing',

    # Animation library modules
    'animation_library',
    'animation_library.main',
    'animation_library.config',
    'animation_library.widgets',
    'animation_library.widgets.main_window',
    'animation_library.services',
    'animation_library.services.database_service',
    'animation_library.themes',
    'animation_library.themes.theme_manager',
    'animation_library.models',
    'animation_library.views',
    'animation_library.utils',
    'animation_library.events',
    'animation_library.core',
]

a = Analysis(
    [str(PROJECT_ROOT / 'run.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy.testing',
        'scipy',
        'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ActionLibrary',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window (windowed mode)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / 'AL.ico'),  # App icon (Windows .ico format)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ActionLibrary',
)
