"""
BlenderIntegrationTab - Blender integration settings for Animation Library v2

Provides UI for:
- Blender executable path configuration
- Addon installation
- Launch mode configuration (PRODUCTION/DEVELOPMENT)
- Test launch functionality
"""

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

from ...config import Config
from ...services.addon_installer_service import AddonInstallerService


class BlenderIntegrationTab(QWidget):
    """Blender integration settings tab"""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        # Load settings from config
        self.settings = Config.load_blender_settings()
        self.blender_path = self.settings.get('blender_exe_path', '')

        # Initialize addon installer
        self.addon_installer = AddonInstallerService()

        self._init_ui()

    def _init_ui(self):
        """Initialize UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Sharp button style
        self._button_style = """
            QPushButton {
                border-radius: 0px;
            }
        """

        # Blender executable section
        layout.addWidget(self._create_blender_path_section())

        # Addon installation section
        layout.addWidget(self._create_addon_installation_section())

        layout.addStretch()

    def _create_blender_path_section(self):
        """Create Blender executable path selection section"""
        blender_group = QGroupBox("Blender Executable")
        blender_layout = QVBoxLayout(blender_group)

        # Path selection
        path_layout = QHBoxLayout()
        path_label = QLabel("Path:")
        path_label.setFixedWidth(80)
        path_layout.addWidget(path_label)

        self.blender_path_input = QLineEdit(str(self.blender_path))
        self.blender_path_input.setPlaceholderText("Select blender.exe")
        path_layout.addWidget(self.blender_path_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet(self._button_style)
        browse_btn.clicked.connect(self.browse_blender_exe)
        path_layout.addWidget(browse_btn)

        blender_layout.addLayout(path_layout)

        # Verify button
        verify_btn = QPushButton("Verify Blender")
        verify_btn.setStyleSheet(self._button_style)
        verify_btn.clicked.connect(self.verify_blender)
        blender_layout.addWidget(verify_btn)

        # Status label
        self.blender_status_label = QLabel("")
        self.blender_status_label.setWordWrap(True)
        blender_layout.addWidget(self.blender_status_label)

        return blender_group

    def _create_addon_installation_section(self):
        """Create addon installation section"""
        addon_group = QGroupBox("Addon Installation")
        addon_layout = QVBoxLayout(addon_group)

        info_label = QLabel("Install the Animation Library addon to Blender.")
        info_label.setWordWrap(True)
        addon_layout.addWidget(info_label)

        install_btn = QPushButton("Install Addon")
        install_btn.setStyleSheet(self._button_style)
        install_btn.clicked.connect(self.install_addon)
        addon_layout.addWidget(install_btn)

        self.addon_status_label = QLabel("")
        self.addon_status_label.setWordWrap(True)
        addon_layout.addWidget(self.addon_status_label)

        note_label = QLabel(
            "Note: After installation, restart Blender and enable the addon in:\n"
            "Edit > Preferences > Add-ons > Search for 'Animation Library'"
        )
        note_label.setWordWrap(True)
        current_theme = self.theme_manager.get_current_theme()
        if current_theme:
            palette = current_theme.palette
            note_label.setStyleSheet(
                f"font-style: italic; color: {palette.text_secondary}; opacity: 0.6;"
            )
        else:
            note_label.setStyleSheet("font-style: italic; opacity: 0.6;")
        addon_layout.addWidget(note_label)

        return addon_group

    def browse_blender_exe(self):
        """Browse for Blender executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Blender Executable",
            "",
            "Blender Executable (blender.exe);;All Files (*)"
        )

        if file_path:
            self.blender_path_input.setText(file_path)
            self.blender_path = file_path

    def verify_blender(self):
        """Verify Blender executable"""
        blender_path = self.blender_path_input.text().strip()

        if not blender_path:
            self.blender_status_label.setText("Please select a Blender executable first.")
            self.blender_status_label.setStyleSheet("color: orange;")
            return

        is_valid, message, version = self.addon_installer.verify_blender_executable(blender_path)

        if is_valid:
            self.blender_status_label.setText(f"✓ {message}")
            self.blender_status_label.setStyleSheet("color: green;")
            self.blender_path = blender_path
        else:
            self.blender_status_label.setText(f"✗ {message}")
            self.blender_status_label.setStyleSheet("color: red;")

    def install_addon(self):
        """Install addon to Blender"""
        blender_path = self.blender_path_input.text().strip()

        if not blender_path:
            QMessageBox.warning(
                self,
                "No Blender Path",
                "Please select and verify Blender executable first."
            )
            return

        # Verify first
        is_valid, message, version = self.addon_installer.verify_blender_executable(blender_path)
        if not is_valid:
            QMessageBox.warning(
                self,
                "Invalid Blender",
                f"Blender verification failed:\n{message}"
            )
            return

        # Install
        success, install_message = self.addon_installer.install_addon(blender_path)

        if success:
            self.addon_status_label.setText(f"✓ Installation successful")
            self.addon_status_label.setStyleSheet("color: green;")
            QMessageBox.information(self, "Success", install_message)

            # Save Blender path after successful installation
            self.save_settings()
        else:
            self.addon_status_label.setText(f"✗ Installation failed")
            self.addon_status_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "Installation Failed", install_message)

    def save_settings(self):
        """Save all settings to config"""
        settings = {
            'blender_exe_path': self.blender_path_input.text().strip(),
        }

        Config.save_blender_settings(settings)


__all__ = ['BlenderIntegrationTab']
