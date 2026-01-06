"""
ColorPickerRow - Individual color picker row component

Pattern: QWidget with color preview button, hex input, and reset button
Inspired by: Old repo's theme editor color picker
"""

import re
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QColorDialog
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor


class ColorPickerRow(QWidget):
    """
    Single color picker row with label, preview button, hex input, and reset

    Features:
    - Color preview button (opens QColorDialog)
    - Hex input field with validation
    - Reset button to restore original color
    - Emits signal when color changes

    Usage:
        picker = ColorPickerRow("Background Primary", "#252525")
        picker.color_changed.connect(on_color_changed)
    """

    # Signal emitted when color changes
    color_changed = pyqtSignal(str)  # Emits new hex color

    def __init__(self, label: str, initial_color: str, parent=None):
        """
        Initialize color picker row

        Args:
            label: Display label (e.g., "Background Primary")
            initial_color: Initial hex color (e.g., "#252525")
            parent: Parent widget
        """
        super().__init__(parent)

        self.label_text = label
        self.current_color = initial_color
        self.original_color = initial_color

        self._create_ui()

    def _create_ui(self):
        """Create horizontal layout: [Label] [ColorButton] [HexInput] [Reset]"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label (e.g., "Background Primary")
        label = QLabel(self.label_text)
        label.setMinimumWidth(150)
        layout.addWidget(label)

        # Color preview button
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(60, 30)
        self.color_btn.setStyleSheet(f"background-color: {self.current_color}; border: 1px solid #666;")
        self.color_btn.clicked.connect(self._open_color_dialog)
        self.color_btn.setToolTip("Click to pick color")
        layout.addWidget(self.color_btn)

        # Hex input field
        self.hex_input = QLineEdit(self.current_color)
        self.hex_input.setMaxLength(7)
        self.hex_input.setFixedWidth(90)
        self.hex_input.setPlaceholderText("#RRGGBB")
        self.hex_input.textChanged.connect(self._on_hex_changed)
        self.hex_input.setToolTip("Enter hex color (e.g., #252525)")
        layout.addWidget(self.hex_input)

        # Reset button
        reset_btn = QPushButton("Reset")
        reset_btn.setFixedWidth(60)
        reset_btn.clicked.connect(self._on_reset)
        reset_btn.setToolTip("Reset to original color")
        layout.addWidget(reset_btn)

        # Stretch to push everything to the left
        layout.addStretch()

    def _open_color_dialog(self):
        """Open Qt color picker dialog"""
        color = QColorDialog.getColor(
            QColor(self.current_color),
            self,
            f"Pick Color - {self.label_text}"
        )

        if color.isValid():
            self.set_color(color.name())

    def _on_hex_changed(self, text):
        """
        Handle hex input text change

        Validates hex format and updates color if valid
        """
        # Validate hex format (#RRGGBB)
        if re.match(r'^#[0-9a-fA-F]{6}$', text):
            self.set_color(text)

    def _on_reset(self):
        """Reset color to original value"""
        self.set_color(self.original_color)

    def set_color(self, hex_color: str):
        """
        Update color and emit signal

        Args:
            hex_color: Hex color string (e.g., "#252525")
        """
        # Normalize hex color
        if not hex_color.startswith('#'):
            hex_color = '#' + hex_color

        hex_color = hex_color.upper()

        self.current_color = hex_color

        # Update button background
        self.color_btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #666;")

        # Update hex input (block signals to avoid recursion)
        self.hex_input.blockSignals(True)
        self.hex_input.setText(hex_color)
        self.hex_input.blockSignals(False)

        # Emit signal
        self.color_changed.emit(hex_color)

    def get_color(self) -> str:
        """
        Get current color

        Returns:
            Current hex color
        """
        return self.current_color


__all__ = ['ColorPickerRow']
