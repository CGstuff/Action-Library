"""
IconPickerDialog - Dialog for selecting folder icon presets
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QPushButton,
    QLabel, QDialogButtonBox, QWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

from ...utils.icon_loader import IconLoader
from ...themes.theme_manager import get_theme_manager


class IconPickerDialog(QDialog):
    """Dialog for picking folder icon from presets"""

    def __init__(self, presets, current_icon_id=None, parent=None):
        super().__init__(parent)
        self.presets = presets
        self.current_icon_id = current_icon_id
        self.selected_icon_id = None

        self.setWindowTitle("Choose Folder Icon")
        self.setModal(True)
        self.resize(400, 300)

        self._create_ui()

    def _create_ui(self):
        """Create dialog UI"""
        layout = QVBoxLayout(self)

        # Icon grid
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(10)

        # Get theme color for icons
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#1a1a1a"

        # Create icon buttons (3 columns)
        row, col = 0, 0
        for preset in self.presets:
            btn = QPushButton()

            # Load and colorize icon
            icon_path = IconLoader.get(preset['icon_key'])
            icon = IconLoader.colorize_icon(icon_path, icon_color)
            btn.setIcon(icon)
            btn.setIconSize(QSize(48, 48))
            btn.setFixedSize(80, 80)
            btn.setToolTip(preset['name'])
            btn.setProperty("icon_id", preset['id'])

            # Highlight current selection
            if preset['id'] == self.current_icon_id:
                btn.setStyleSheet("background-color: #4a90e2;")

            btn.clicked.connect(lambda checked, id=preset['id']: self._on_icon_clicked(id))

            grid.addWidget(btn, row, col)

            col += 1
            if col >= 3:
                col = 0
                row += 1

        layout.addWidget(grid_widget)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_icon_clicked(self, icon_id: str):
        """Handle icon button click"""
        self.selected_icon_id = icon_id

        # Update button styles
        for btn in self.findChildren(QPushButton):
            if btn.property("icon_id") == icon_id:
                btn.setStyleSheet("background-color: #4a90e2;")
            else:
                btn.setStyleSheet("")

    def get_selected_icon(self) -> Optional[str]:
        """Get selected icon ID"""
        return self.selected_icon_id


__all__ = ['IconPickerDialog']
