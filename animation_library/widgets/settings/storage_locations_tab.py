"""
StorageLocationsTab - Library path and storage configuration

Provides UI for:
- Animation library path configuration
- Application folder location display
- Folder browsing functionality
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QFileDialog, QMessageBox, QCheckBox
)
from pathlib import Path
import subprocess
import sys

from ...config import Config


class StorageLocationsTab(QWidget):
    """Storage locations settings tab"""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._init_ui()

    def _init_ui(self):
        """Initialize UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Locations Group
        locations_group = QGroupBox("Storage Locations")
        locations_layout = QVBoxLayout(locations_group)

        # App root location
        app_root_label = QLabel(f"<b>Application Folder:</b><br>{Config.get_user_data_dir()}")
        app_root_label.setWordWrap(True)
        locations_layout.addWidget(app_root_label)

        open_app_btn = QPushButton("Open Application Folder")
        open_app_btn.clicked.connect(lambda: self._open_folder(Config.get_user_data_dir()))
        locations_layout.addWidget(open_app_btn)

        locations_layout.addSpacing(10)

        # Library path location
        library_path = Config.load_library_path()
        self.library_label = QLabel(
            f"<b>Animation Library:</b><br>{library_path if library_path else 'Not configured'}"
        )
        self.library_label.setWordWrap(True)
        locations_layout.addWidget(self.library_label)

        library_buttons_layout = QHBoxLayout()

        if library_path:
            open_library_btn = QPushButton("Open Library Folder")
            open_library_btn.clicked.connect(lambda: self._open_folder(library_path))
            library_buttons_layout.addWidget(open_library_btn)

        change_library_btn = QPushButton("Change Library Location...")
        change_library_btn.clicked.connect(self._change_library_location)
        library_buttons_layout.addWidget(change_library_btn)

        library_buttons_layout.addStretch()
        locations_layout.addLayout(library_buttons_layout)

        layout.addWidget(locations_group)

        # Info section
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)

        info_text = QLabel(
            "Your animation library can be located anywhere on your computer. "
            "This is ideal for large libraries or network storage.\n\n"
            "The application folder contains themes, configuration, and temporary storage. "
            "The animation library contains your saved animations, metadata, and previews."
        )
        info_text.setWordWrap(True)

        # Apply theme styling if available
        current_theme = self.theme_manager.get_current_theme()
        if current_theme:
            palette = current_theme.palette
            info_text.setStyleSheet(
                f"font-style: italic; color: {palette.text_secondary};"
            )
        else:
            info_text.setStyleSheet("font-style: italic; color: gray;")

        info_layout.addWidget(info_text)

        layout.addWidget(info_group)

        # Deletion Settings Group
        deletion_group = QGroupBox("Deletion Settings")
        deletion_layout = QVBoxLayout(deletion_group)

        # Hard delete checkbox
        self.hard_delete_checkbox = QCheckBox("Allow permanent deletion")
        self.hard_delete_checkbox.setChecked(Config.load_allow_hard_delete())
        self.hard_delete_checkbox.toggled.connect(self._on_hard_delete_changed)
        deletion_layout.addWidget(self.hard_delete_checkbox)

        # Warning text
        hard_delete_warning = QLabel(
            "When enabled, you can permanently delete items from the Trash folder. "
            "This is typically reserved for leads in a studio environment.\n\n"
            "Two-stage deletion workflow:\n"
            "1. Archive: Animations are soft-deleted and can be restored\n"
            "2. Trash: Archived items can be moved here for permanent deletion"
        )
        hard_delete_warning.setWordWrap(True)

        # Apply theme styling
        current_theme = self.theme_manager.get_current_theme()
        if current_theme:
            palette = current_theme.palette
            hard_delete_warning.setStyleSheet(
                f"font-style: italic; color: {palette.text_secondary}; margin-top: 5px;"
            )
        else:
            hard_delete_warning.setStyleSheet("font-style: italic; color: gray; margin-top: 5px;")

        deletion_layout.addWidget(hard_delete_warning)

        layout.addWidget(deletion_group)

        layout.addStretch()

    def _on_hard_delete_changed(self, checked: bool):
        """Handle hard delete checkbox toggle"""
        Config.save_allow_hard_delete(checked)

    def _change_library_location(self):
        """Change animation library location"""
        current_path = Config.load_library_path()
        if not current_path:
            current_path = Path.home() / "AnimationLibrary"

        new_path = QFileDialog.getExistingDirectory(
            self,
            "Select New Animation Library Folder",
            str(current_path),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if new_path:
            # Confirm the change
            reply = QMessageBox.question(
                self,
                "Change Library Location",
                f"Change animation library location to:\n{new_path}\n\n"
                "Note: This will not move existing animations. "
                "You'll need to manually copy them if desired.\n\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Save new path
                if Config.save_library_path(new_path):
                    # Create directory structure
                    new_path_obj = Path(new_path)
                    (new_path_obj / "library").mkdir(parents=True, exist_ok=True)
                    (new_path_obj / "animations").mkdir(parents=True, exist_ok=True)

                    # Update label
                    self.library_label.setText(
                        f"<b>Animation Library:</b><br>{new_path}"
                    )

                    QMessageBox.information(
                        self,
                        "Success",
                        f"Library location changed to:\n{new_path}\n\n"
                        "Please restart the application for changes to take effect."
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        "Failed to save library location. Please try again."
                    )

    def _open_folder(self, folder_path):
        """Open folder in system file explorer"""
        folder_path = Path(folder_path)

        if not folder_path.exists():
            QMessageBox.warning(
                self,
                "Folder Not Found",
                f"The folder does not exist:\n{folder_path}"
            )
            return

        try:
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', str(folder_path)])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(folder_path)])
            else:  # Linux
                subprocess.Popen(['xdg-open', str(folder_path)])
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open folder:\n{folder_path}\n\nError: {str(e)}"
            )


__all__ = ['StorageLocationsTab']
