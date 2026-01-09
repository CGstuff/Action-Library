"""
Global configuration for Animation Library v2

Combines best practices from:
- Current animation_library
- Maya Studio Library patterns
- Hybrid plan optimizations
"""

import os
from pathlib import Path
from typing import Final, Optional, Union


class Config:
    """Central configuration class for all application settings"""

    # Application metadata
    APP_NAME: Final[str] = "Action Library"
    APP_VERSION: Final[str] = "1.0.0"
    APP_AUTHOR: Final[str] = "CGstuff"

    # Paths
    APP_ROOT: Final[Path] = Path(__file__).parent
    ASSETS_DIR: Final[Path] = APP_ROOT.parent / "assets"
    ICONS_DIR: Final[Path] = ASSETS_DIR / "icons"
    FONTS_DIR: Final[Path] = ASSETS_DIR / "fonts"
    STYLES_DIR: Final[Path] = ASSETS_DIR / "styles"

    # Database configuration
    DATABASE_VERSION: Final[int] = 1
    DB_FOLDER_NAME: Final[str] = ".actionlibrary"  # Hidden folder at library root
    DEFAULT_DB_NAME: Final[str] = "database.db"  # Version-agnostic name
    LEGACY_DB_NAME: Final[str] = "animation_library_v2.db"  # Old name for migration

    # Performance settings (Hybrid plan + Maya-inspired)
    PIXMAP_CACHE_SIZE_KB: Final[int] = 512 * 1024  # 512 MB
    THUMBNAIL_THREAD_COUNT: Final[int] = 4  # Background workers
    BATCH_SIZE: Final[int] = 100  # Items to load per batch

    # UI settings
    DEFAULT_CARD_SIZE: Final[int] = 160  # Grid mode card size
    MIN_CARD_SIZE: Final[int] = 80
    MAX_CARD_SIZE: Final[int] = 300
    CARD_SIZE_STEP: Final[int] = 20

    DEFAULT_VIEW_MODE: Final[str] = "grid"  # "grid" or "list"
    LIST_ROW_HEIGHT: Final[int] = 50  # Compact list mode (was 60)

    # Hover video preview settings
    HOVER_VIDEO_DELAY_MS: Final[int] = 500  # Delay before showing popup (ms)
    HOVER_VIDEO_SIZE: Final[int] = 300  # Popup size in pixels
    HOVER_VIDEO_POSITION: Final[str] = "cursor"  # "cursor", "right", "left", "above", "below"
    HOVER_VIDEO_FADE_DURATION: Final[int] = 200  # Fade animation duration (ms)
    HOVER_VIDEO_AUTO_HIDE_DELAY: Final[int] = 0  # 0 = hide when mouse leaves, >0 = auto-hide after N ms
    HOVER_VIDEO_FOLLOW_MOUSE: Final[bool] = True  # Follow mouse movement

    # Thumbnail settings
    THUMBNAIL_SIZE: Final[int] = 300  # Max size for stored thumbnails
    PREVIEW_VIDEO_FPS: Final[int] = 30
    PREVIEW_VIDEO_DURATION_SEC: Final[int] = 3

    # Theme settings
    DEFAULT_THEME: Final[str] = "dark"  # "light" or "dark"

    # Default gradient colors (if no custom gradient set)
    DEFAULT_GRADIENT_TOP: Final[tuple] = (0.25, 0.35, 0.55)  # Normalized RGB
    DEFAULT_GRADIENT_BOTTOM: Final[tuple] = (0.5, 0.5, 0.5)

    # Window settings
    DEFAULT_WINDOW_WIDTH: Final[int] = 1400
    DEFAULT_WINDOW_HEIGHT: Final[int] = 900
    DEFAULT_SPLITTER_SIZES: Final[list] = [250, 800, 350]  # Left, center, right

    # Folder tree settings
    VIRTUAL_FOLDERS: Final[list] = [
        "All Animations",
        "Recent",
        "Favorites",
    ]

    # Performance monitoring (Maya-inspired)
    ENABLE_PERFORMANCE_LOGGING: Final[bool] = True
    LOG_EVERY_N_THUMBNAILS: Final[int] = 100

    # Feature flags
    ENABLE_HOVER_VIDEO: Final[bool] = False  # Disabled for performance - using metadata panel preview instead
    ENABLE_DRAG_DROP: Final[bool] = True
    ENABLE_MULTI_SELECT: Final[bool] = True

    # Database schema
    DB_SCHEMA_VERSION: Final[int] = 1

    # Archive and Trash settings (two-stage deletion)
    ARCHIVE_FOLDER_NAME: Final[str] = ".archive"  # First stage: soft delete, no expiry
    TRASH_FOLDER_NAME: Final[str] = ".trash"      # Second stage: staging for hard delete
    ALLOW_HARD_DELETE: bool = False               # Setting toggle for permanent deletion

    @classmethod
    def get_user_data_dir(cls) -> Path:
        """Get user data directory (in app directory for portability)"""
        # Use app directory for portable installation (not AppData)
        user_dir = cls.APP_ROOT.parent / 'data'
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    @classmethod
    def get_database_folder(cls) -> Path:
        """Get the hidden .actionlibrary folder path"""
        library_path = cls.load_library_path()
        if library_path and library_path.exists():
            db_folder = library_path / cls.DB_FOLDER_NAME
            db_folder.mkdir(parents=True, exist_ok=True)
            return db_folder
        else:
            # Fallback to user data dir if no library configured
            db_folder = cls.get_user_data_dir() / cls.DB_FOLDER_NAME
            db_folder.mkdir(parents=True, exist_ok=True)
            return db_folder

    @classmethod
    def get_database_path(cls) -> Path:
        """Get full path to database file (in hidden .actionlibrary folder)"""
        return cls.get_database_folder() / cls.DEFAULT_DB_NAME

    @classmethod
    def get_legacy_database_path(cls) -> Optional[Path]:
        """Get path to legacy database if it exists (for migration)"""
        library_path = cls.load_library_path()
        if library_path and library_path.exists():
            legacy_path = library_path / cls.LEGACY_DB_NAME
            if legacy_path.exists():
                return legacy_path
        return None

    @classmethod
    def get_cache_dir(cls) -> Path:
        """Get cache directory for thumbnails and previews"""
        cache_dir = cls.get_user_data_dir() / 'cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @classmethod
    def get_thumbnails_dir(cls) -> Path:
        """Get thumbnails directory"""
        thumb_dir = cls.get_cache_dir() / 'thumbnails'
        thumb_dir.mkdir(parents=True, exist_ok=True)
        return thumb_dir

    @classmethod
    def get_previews_dir(cls) -> Path:
        """Get video previews directory"""
        preview_dir = cls.get_cache_dir() / 'previews'
        preview_dir.mkdir(parents=True, exist_ok=True)
        return preview_dir

    @classmethod
    def get_settings_file(cls) -> Path:
        """Get settings JSON file path"""
        return cls.get_user_data_dir() / 'settings.json'

    # Library Path Settings
    LIBRARY_CONFIG_FILE: Final[str] = "library_path.txt"

    # Blender Integration Settings
    BLENDER_CONFIG_FILE: Final[str] = "blender_settings.json"
    DEFAULT_ADDON_FOLDER_NAME: Final[str] = "animation_library_addon"
    QUEUE_POLL_INTERVAL_MS: Final[int] = 500  # Blender poll frequency
    QUEUE_MAX_AGE_SECONDS: Final[int] = 300  # Auto-cleanup old requests

    @classmethod
    def get_blender_settings_file(cls) -> Path:
        """Get Blender settings JSON file path"""
        return cls.get_user_data_dir() / cls.BLENDER_CONFIG_FILE

    @classmethod
    def load_blender_settings(cls) -> dict:
        """
        Load Blender integration settings

        Returns:
            dict: Blender settings with keys:
                - blender_exe_path: str (path to blender.exe)
                - launch_mode: str ('PRODUCTION' or 'DEVELOPMENT')
                - script_path: str (path to run.py for dev mode)
                - python_exe: str (Python executable for dev mode)
        """
        settings_file = cls.get_blender_settings_file()
        if settings_file.exists():
            try:
                import json
                with open(settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass  # Return defaults below

        # Return defaults if file doesn't exist or error occurred
        return {
            'blender_exe_path': '',
            'launch_mode': 'PRODUCTION',
            'script_path': '',
            'python_exe': 'python'
        }

    @classmethod
    def save_blender_settings(cls, settings: dict) -> bool:
        """
        Save Blender integration settings

        Args:
            settings: dict with Blender configuration

        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            import json
            settings_file = cls.get_blender_settings_file()
            settings_file.parent.mkdir(parents=True, exist_ok=True)

            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            return True
        except Exception:
            return False

    @classmethod
    def get_library_config_path(cls) -> Path:
        """Get library path configuration file"""
        return cls.get_user_data_dir() / cls.LIBRARY_CONFIG_FILE

    @classmethod
    def load_library_path(cls) -> Optional[Path]:
        """
        Load saved library path from config file

        Returns:
            Path: Library path if configured and exists, None otherwise
        """
        config_file = cls.get_library_config_path()
        if config_file.exists():
            try:
                path_str = config_file.read_text(encoding='utf-8').strip()
                if path_str and Path(path_str).exists():
                    return Path(path_str)
            except Exception:
                pass

        # Default: check if 'storage' folder exists in app directory
        default_storage = cls.APP_ROOT.parent / 'storage'
        if default_storage.exists():
            # Save it for next time
            cls.save_library_path(default_storage)
            return default_storage

        return None

    @classmethod
    def save_library_path(cls, path: Union[str, Path]) -> bool:
        """
        Save library path to config file

        Args:
            path: Path to animation library folder

        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            config_file = cls.get_library_config_path()
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(str(path), encoding='utf-8')
            return True
        except Exception:
            return False

    @classmethod
    def is_first_run(cls) -> bool:
        """
        Check if this is the first time the application is running.

        Returns:
            True if no library path is configured
        """
        return cls.load_library_path() is None

    @classmethod
    def load_allow_hard_delete(cls) -> bool:
        """
        Load the ALLOW_HARD_DELETE setting from settings file

        Returns:
            bool: True if hard delete is allowed, False otherwise
        """
        settings_file = cls.get_settings_file()
        if settings_file.exists():
            try:
                import json
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    return settings.get('allow_hard_delete', cls.ALLOW_HARD_DELETE)
            except Exception:
                pass
        return cls.ALLOW_HARD_DELETE

    @classmethod
    def save_allow_hard_delete(cls, allowed: bool) -> bool:
        """
        Save the ALLOW_HARD_DELETE setting to settings file

        Args:
            allowed: Whether hard delete should be allowed

        Returns:
            bool: True if saved successfully
        """
        try:
            import json
            settings_file = cls.get_settings_file()
            settings_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing settings
            settings = {}
            if settings_file.exists():
                try:
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                except Exception:
                    pass

            # Update setting
            settings['allow_hard_delete'] = allowed

            # Save back
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            return True
        except Exception:
            return False

    # ==================== LIFECYCLE STATUS ====================
    # 'none' = no status (for solo animators using as simple asset browser)
    # Other statuses = pipeline workflow (for studios)
    LIFECYCLE_STATUSES = {
        'none': {'color': None, 'label': 'None'},  # No badge displayed
        'wip': {'color': '#FF9800', 'label': 'WIP'},
        'review': {'color': '#2196F3', 'label': 'In Review'},
        'approved': {'color': '#4CAF50', 'label': 'Approved'},
        'needs_work': {'color': '#F44336', 'label': 'Needs Work'},
        'final': {'color': '#9C27B0', 'label': 'Final'},
    }


# Export for convenient imports
__all__ = ['Config']
