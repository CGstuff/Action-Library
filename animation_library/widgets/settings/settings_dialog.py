"""
SettingsDialog - Application settings dialog for Animation Library v2
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QDialogButtonBox
)
from PyQt6.QtCore import Qt

from ...config import Config
from .storage_locations_tab import StorageLocationsTab
from .blender_integration_tab import BlenderIntegrationTab
from .theme_tab import ThemeTab
from .library_tab import LibraryTab


class SettingsDialog(QDialog):
    """
    Main settings dialog with tabbed interface

    Features:
    - Storage locations (library path configuration)
    - Blender integration settings (executable path, addon installation, launch modes)
    - OK/Cancel/Apply buttons
    - Persistent window size (saved to config)

    Usage:
        dialog = SettingsDialog(theme_manager, parent=main_window)
        if dialog.exec():
            # Settings were saved
            pass
    """

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        self.setWindowTitle(f"Settings - {Config.APP_NAME}")
        self.setModal(True)
        self.resize(700, 500)

        self._create_ui()

    def _create_ui(self):
        """Create UI layout"""
        layout = QVBoxLayout(self)

        # Sharp button style for dialog buttons
        button_style = """
            QPushButton {
                border-radius: 0px;
            }
        """

        # Tab widget
        self.tab_widget = QTabWidget()

        # Storage Locations tab (first - most fundamental)
        self.storage_tab = StorageLocationsTab(self.theme_manager, self)
        self.tab_widget.addTab(self.storage_tab, "Storage Locations")

        # Blender Integration tab
        self.blender_tab = BlenderIntegrationTab(self.theme_manager, self)
        self.tab_widget.addTab(self.blender_tab, "Blender Integration")

        # Theme customization tab
        self.theme_tab = ThemeTab(self.theme_manager, self)
        self.tab_widget.addTab(self.theme_tab, "Appearance")

        # Library management tab (export/import)
        self.library_tab = LibraryTab(self.theme_manager, self)
        self.tab_widget.addTab(self.library_tab, "Backup")

        layout.addWidget(self.tab_widget)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply
        )

        # Apply sharp style to dialog buttons
        for button in button_box.buttons():
            button.setStyleSheet(button_style)

        layout.addWidget(button_box)

    def _on_apply(self):
        """Handle Apply button - save settings without closing dialog"""
        self.blender_tab.save_settings()
        self.theme_tab.save_settings()

    def accept(self):
        """Handle OK button - save and close"""
        self._on_apply()
        super().accept()


__all__ = ['SettingsDialog']
