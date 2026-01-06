"""
GradientPickerDialog - Dialog for selecting custom gradients
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QDialogButtonBox, QColorDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class GradientPickerDialog(QDialog):
    """Dialog for picking custom gradient colors"""

    def __init__(self, parent=None, current_top=None, current_bottom=None):
        super().__init__(parent)

        # Default gradient colors (normalized RGB 0-1)
        self.top_color = current_top or (0.25, 0.35, 0.55)
        self.bottom_color = current_bottom or (0.5, 0.5, 0.5)

        self.setWindowTitle("Custom Gradient")
        self.setModal(True)
        self.resize(350, 200)

        self._create_ui()

    def _create_ui(self):
        """Create dialog UI"""
        layout = QVBoxLayout(self)

        # Instructions
        label = QLabel("Choose gradient colors for thumbnail background:")
        layout.addWidget(label)

        # Top color picker
        top_layout = QHBoxLayout()
        top_label = QLabel("Top Color:")
        top_layout.addWidget(top_label)

        self._top_color_btn = QPushButton()
        self._top_color_btn.setFixedSize(80, 30)
        self._update_color_button(self._top_color_btn, self.top_color)
        self._top_color_btn.clicked.connect(self._pick_top_color)
        top_layout.addWidget(self._top_color_btn)
        top_layout.addStretch()

        layout.addLayout(top_layout)

        # Bottom color picker
        bottom_layout = QHBoxLayout()
        bottom_label = QLabel("Bottom Color:")
        bottom_layout.addWidget(bottom_label)

        self._bottom_color_btn = QPushButton()
        self._bottom_color_btn.setFixedSize(80, 30)
        self._update_color_button(self._bottom_color_btn, self.bottom_color)
        self._bottom_color_btn.clicked.connect(self._pick_bottom_color)
        bottom_layout.addWidget(self._bottom_color_btn)
        bottom_layout.addStretch()

        layout.addLayout(bottom_layout)

        layout.addStretch()

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _update_color_button(self, button, rgb_normalized):
        """Update button color preview"""
        # Convert normalized RGB (0-1) to 0-255
        r = int(rgb_normalized[0] * 255)
        g = int(rgb_normalized[1] * 255)
        b = int(rgb_normalized[2] * 255)

        button.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb({r}, {g}, {b});
                border: 2px solid #888;
            }}
        """)

    def _pick_top_color(self):
        """Show color picker for top color"""
        # Convert to QColor
        r = int(self.top_color[0] * 255)
        g = int(self.top_color[1] * 255)
        b = int(self.top_color[2] * 255)
        initial = QColor(r, g, b)

        color = QColorDialog.getColor(initial, self, "Pick Top Color")
        if color.isValid():
            # Convert to normalized RGB
            self.top_color = (
                color.red() / 255.0,
                color.green() / 255.0,
                color.blue() / 255.0
            )
            self._update_color_button(self._top_color_btn, self.top_color)

    def _pick_bottom_color(self):
        """Show color picker for bottom color"""
        # Convert to QColor
        r = int(self.bottom_color[0] * 255)
        g = int(self.bottom_color[1] * 255)
        b = int(self.bottom_color[2] * 255)
        initial = QColor(r, g, b)

        color = QColorDialog.getColor(initial, self, "Pick Bottom Color")
        if color.isValid():
            # Convert to normalized RGB
            self.bottom_color = (
                color.red() / 255.0,
                color.green() / 255.0,
                color.blue() / 255.0
            )
            self._update_color_button(self._bottom_color_btn, self.bottom_color)

    def get_gradient(self):
        """Get selected gradient colors"""
        return self.top_color, self.bottom_color


__all__ = ['GradientPickerDialog']
