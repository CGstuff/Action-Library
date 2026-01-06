"""
Animation Library v2 - Main Entry Point

A high-performance animation library for Blender with modern Qt6 architecture.

Usage:
    python -m animation_library.main
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmapCache
from PyQt6.QtCore import Qt

from .config import Config
from .themes.theme_manager import get_theme_manager
from .events.event_bus import get_event_bus
from .utils.logging_config import LoggingConfig


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
