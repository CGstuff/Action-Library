"""
Animation Library v2 - Main Entry Point

A high-performance animation library for Blender with modern Qt6 architecture.

Usage:
    python -m animation_library.main
"""

import sys
import shutil
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmapCache, QIcon
from PyQt6.QtCore import Qt

from .config import Config
from .themes.theme_manager import get_theme_manager
from .events.event_bus import get_event_bus
from .utils.logging_config import LoggingConfig


def sync_protocol_to_library():
    """
    Copy protocol schema files to library/.schema/protocol/ for Blender addon access.

    This ensures the Blender addon can import the protocol from the library path
    without needing a separate copy bundled with the addon.
    """
    library_path = Config.load_library_path()
    if not library_path or not library_path.exists():
        return

    # Source: protocol/ directory next to this file
    source_protocol = Path(__file__).parent / 'protocol'
    if not source_protocol.exists():
        return

    # Destination: library/.schema/protocol/
    dest_schema = library_path / '.schema'
    dest_protocol = dest_schema / 'protocol'

    try:
        # Create .schema directory if needed
        dest_schema.mkdir(parents=True, exist_ok=True)

        # Copy protocol files (overwrite existing)
        if dest_protocol.exists():
            shutil.rmtree(dest_protocol)
        shutil.copytree(source_protocol, dest_protocol)

    except Exception as e:
        # Non-fatal - addon can fall back to bundled copy
        print(f"[Animation Library] Warning: Could not sync protocol to library: {e}")


def _get_icon_path() -> Path:
    """
    Get the path to the application icon.

    Handles both running from source and PyInstaller builds.

    Returns:
        Path to the icon file, or None if not found
    """
    # Check if running as PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = Path(sys._MEIPASS)
    else:
        # Running from source - icon is in project root
        base_path = Path(__file__).parent.parent

    icon_path = base_path / 'AL.ico'

    # Also check in current directory (for portable builds)
    if not icon_path.exists():
        icon_path = Path.cwd() / 'AL.ico'

    return icon_path if icon_path.exists() else None


def setup_application() -> QApplication:
    """
    Initialize and configure the Qt application

    Returns:
        Configured QApplication instance
    """
    # Create application
    app = QApplication(sys.argv)

    # Set application metadata
    app.setApplicationName(Config.APP_NAME)
    app.setApplicationVersion(Config.APP_VERSION)
    app.setOrganizationName(Config.APP_AUTHOR)

    # Set application icon (for taskbar and titlebar)
    icon_path = _get_icon_path()
    if icon_path and icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Note: High DPI scaling is enabled by default in PyQt6

    # Configure global pixmap cache (512 MB for thumbnail performance)
    QPixmapCache.setCacheLimit(Config.PIXMAP_CACHE_SIZE_KB)

    # Initialize theme manager and apply default theme
    theme_manager = get_theme_manager()
    stylesheet = theme_manager.get_current_stylesheet()
    app.setStyleSheet(stylesheet)

    # Initialize event bus (singleton)
    event_bus = get_event_bus()

    # Connect theme changes to stylesheet updates
    def on_theme_changed(theme_name: str):
        """Update stylesheet when theme changes"""
        new_stylesheet = theme_manager.get_current_stylesheet()
        app.setStyleSheet(new_stylesheet)

    theme_manager.theme_changed.connect(on_theme_changed)

    return app


def main():
    """
    Main entry point for Animation Library v2

    Creates the application, sets up the main window, and runs the event loop.
    """
    # Setup logging first
    log_dir = Config.get_user_data_dir() / 'logs'
    LoggingConfig.setup_logging(log_dir)

    logger = LoggingConfig.get_logger(__name__)
    logger.info(f"Starting {Config.APP_NAME} {Config.APP_VERSION}...")
    logger.info(f"Database: {Config.get_database_path()}")
    logger.info(f"Cache: {Config.get_cache_dir()}")

    # Sync protocol schema to library for Blender addon access
    sync_protocol_to_library()

    # Setup application
    app = setup_application()

    # Create and show main window
    from .widgets.main_window import MainWindow
    window = MainWindow()
    window.show()

    logger.info(f"Application started successfully!")
    logger.info(f"Theme: {get_theme_manager().get_current_theme().name}")
    logger.info(f"Pixmap cache: {Config.PIXMAP_CACHE_SIZE_KB / 1024:.0f} MB")

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
