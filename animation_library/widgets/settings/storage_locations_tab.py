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

        # Sharp button style
        self._button_style = """
            QPushButton {
                border-radius: 0px;
            }
        """

        # Locations Group
        locations_group = QGroupBox("Storage Locations")
        locations_layout = QVBoxLayout(locations_group)

        # App root location
        app_root_label = QLabel(f"<b>Application Folder:</b><br>{Config.get_user_data_dir()}")
        app_root_label.setWordWrap(True)
        locations_layout.addWidget(app_root_label)

        open_app_btn = QPushButton("Open Application Folder")
        open_app_btn.setStyleSheet(self._button_style)
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
            open_library_btn.setStyleSheet(self._button_style)
            open_library_btn.clicked.connect(lambda: self._open_folder(library_path))
            library_buttons_layout.addWidget(open_library_btn)

        change_library_btn = QPushButton("Change Library Location...")
        change_library_btn.setStyleSheet(self._button_style)
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

        # Style checkbox - gray unchecked, accent when checked
        current_theme = self.theme_manager.get_current_theme()
        accent = current_theme.palette.accent if current_theme else "#4a90e2"
        text_color = current_theme.palette.text_primary if current_theme else "#ffffff"
        self.hard_delete_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {text_color};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: #555555;
                border: none;
            }}
            QCheckBox::indicator:unchecked:hover {{
                background-color: #666666;
            }}
            QCheckBox::indicator:checked {{
                background-color: {accent};
                border: none;
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {accent};
            }}
        """)
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
        """Change animation library location, then relaunch into it."""
        from ...services.library_switch import reset_library_services, switch_library
        from ...utils.app_restart import restart_application

        current_path = Config.load_library_path()
        if not current_path:
            current_path = Path.home() / "AnimationLibrary"

        new_path = QFileDialog.getExistingDirectory(
            self,
            "Select New Animation Library Folder",
            str(current_path),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if not new_path:
            return

        if Config.load_library_path() and Path(new_path) == Path(current_path):
            QMessageBox.information(
                self,
                "No Change",
                "That is already the current library location."
            )
            return

        main_window = self._find_main_window()

        reply = QMessageBox.question(
            self,
            "Change Library Location",
            f"Change animation library location to:\n{new_path}\n\n"
            "Existing animations are NOT moved - an empty folder becomes a new, "
            "empty library.\n\n"
            + ("Blender picks up the change automatically.\n\n"
               if main_window is not None else
               "Action Library will restart to load it. Blender picks up the "
               "change automatically.\n\n")
            + "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if main_window is not None:
            # In-place switch: rebinds the whole UI to the new library without
            # restarting. Writing the pointer also releases the Blender addon,
            # which polls it and follows within ~2s.
            ok, message = main_window.switch_to_library(new_path)
            if not ok:
                QMessageBox.warning(
                    self,
                    "Change Failed",
                    f"Could not change library location:\n\n{message}"
                )
                return

            self.library_label.setText(f"<b>Animation Library:</b><br>{new_path}")

            # Close Settings. This dialog is rebuilt on every open, but the tabs
            # already alive right now captured the OLD services when they were
            # constructed (e.g. MaintenanceTab), so leaving it open would let you
            # run an integrity check against a closed database.
            dialog = self.window()
            if dialog is not None and dialog is not main_window:
                dialog.close()
            return

        # No main window found (shouldn't happen in the real app) - fall back to
        # the relaunch path. Don't tear the services down until the new instance
        # is confirmed, or a failed relaunch leaves this one with dead services.
        ok, message = switch_library(new_path, reset_services=False)
        if not ok:
            QMessageBox.warning(
                self,
                "Change Failed",
                f"Could not change library location:\n\n{message}"
            )
            return

        self.library_label.setText(f"<b>Animation Library:</b><br>{new_path}")

        if not restart_application(on_confirmed=reset_library_services):
            QMessageBox.information(
                self,
                "Restart Required",
                f"Library location changed to:\n{new_path}\n\n"
                "Action Library could not restart itself - please close and "
                "reopen it to finish loading the new library."
            )

    def _find_main_window(self):
        """Locate the MainWindow so we can switch library in place.

        Returns None if it can't be found, in which case the caller falls back to
        relaunching.
        """
        from ..main_window import MainWindow

        widget = self
        while widget is not None:
            if isinstance(widget, MainWindow):
                return widget
            widget = widget.parent()

        from PyQt6.QtWidgets import QApplication
        for top_level in QApplication.topLevelWidgets():
            if isinstance(top_level, MainWindow):
                return top_level
        return None

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
