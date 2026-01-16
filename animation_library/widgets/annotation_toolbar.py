"""
Annotation Toolbar Widget

Compact toolbar for drawover annotation mode with:
- Tool selection (pen, line, arrow, rect, circle)
- Color picker with presets
- Undo/Redo buttons
- Clear button

Emits signals for tool changes, color changes, and actions.
"""

from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QFrame, QButtonGroup
)
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QColor

from .drawover_canvas import DrawingTool
from .drawing_toolbar import ColorPicker
from ..utils.icon_loader import IconLoader
from ..utils.icon_utils import colorize_white_svg
from ..themes.theme_manager import get_theme_manager


class AnnotationToolbar(QWidget):
    """Compact annotation toolbar for drawover mode."""

    # Signals
    tool_changed = pyqtSignal(object)  # DrawingTool
    color_changed = pyqtSignal(QColor)
    undo_clicked = pyqtSignal()
    redo_clicked = pyqtSignal()
    clear_clicked = pyqtSignal()

    # Tool definitions: (icon_name, DrawingTool, tooltip)
    TOOLS = [
        ("pen", DrawingTool.PEN, "Freehand pen (P)"),
        ("line", DrawingTool.LINE, "Straight line (L)"),
        ("arrow_draw", DrawingTool.ARROW, "Arrow (A)"),
        ("rectangle", DrawingTool.RECT, "Rectangle (R)"),
        ("circle", DrawingTool.CIRCLE, "Circle (C)"),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tool_buttons: Dict[DrawingTool, QPushButton] = {}
        self._current_tool = DrawingTool.PEN

        self._setup_ui()
        self._connect_signals()

        # Select pen by default
        if DrawingTool.PEN in self._tool_buttons:
            self._tool_buttons[DrawingTool.PEN].setChecked(True)

    def _setup_ui(self):
        """Build the toolbar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Get theme icon color
        theme = get_theme_manager().get_current_theme()
        self._icon_color = theme.palette.header_icon_color if theme else "#e0e0e0"

        # Button style
        self._tool_btn_style = """
            QPushButton { background: #2d2d2d; border: 1px solid #444; border-radius: 3px; }
            QPushButton:hover { background: #3a3a3a; border-color: #555; }
            QPushButton:checked { background: #FF5722; border-color: #FF5722; }
            QPushButton:disabled { background: #252525; border-color: #333; }
        """

        # Tool button group (exclusive selection)
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)

        # Create tool buttons
        for icon_name, tool, tooltip in self.TOOLS:
            btn = self._create_tool_button(icon_name, tooltip)
            self._tool_group.addButton(btn)
            self._tool_buttons[tool] = btn
            layout.addWidget(btn)

        # Separator
        layout.addWidget(self._create_separator())

        # Color picker
        self._color_picker = ColorPicker()
        layout.addWidget(self._color_picker)

        # Separator
        layout.addWidget(self._create_separator())

        # Undo button
        self._undo_btn = self._create_action_button("undo", "Undo (Ctrl+Z)")
        layout.addWidget(self._undo_btn)

        # Redo button
        self._redo_btn = self._create_action_button("redo", "Redo (Ctrl+Y)")
        layout.addWidget(self._redo_btn)

        # Clear button (with warning color)
        self._clear_btn = self._create_action_button("clear", "Clear all annotations")
        clear_style = self._tool_btn_style.replace("#FF5722", "#f44336")
        self._clear_btn.setStyleSheet(clear_style)
        layout.addWidget(self._clear_btn)

    def _create_tool_button(self, icon_name: str, tooltip: str) -> QPushButton:
        """Create a checkable tool button with icon."""
        btn = QPushButton()
        btn.setFixedSize(28, 28)
        btn.setCheckable(True)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(self._tool_btn_style)

        icon_path = IconLoader.get(icon_name)
        btn.setIcon(colorize_white_svg(icon_path, self._icon_color))
        btn.setIconSize(QSize(18, 18))

        return btn

    def _create_action_button(self, icon_name: str, tooltip: str) -> QPushButton:
        """Create a non-checkable action button with icon."""
        btn = QPushButton()
        btn.setFixedSize(28, 28)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(self._tool_btn_style)

        icon_path = IconLoader.get(icon_name)
        btn.setIcon(colorize_white_svg(icon_path, self._icon_color))
        btn.setIconSize(QSize(18, 18))

        return btn

    def _create_separator(self) -> QFrame:
        """Create a vertical separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background: #444; max-width: 1px;")
        return sep

    def _connect_signals(self):
        """Connect internal signals."""
        # Tool buttons
        for tool, btn in self._tool_buttons.items():
            btn.clicked.connect(lambda checked, t=tool: self._on_tool_clicked(t))

        # Color picker
        self._color_picker.color_changed.connect(self.color_changed.emit)

        # Action buttons
        self._undo_btn.clicked.connect(self.undo_clicked.emit)
        self._redo_btn.clicked.connect(self.redo_clicked.emit)
        self._clear_btn.clicked.connect(self.clear_clicked.emit)

    def _on_tool_clicked(self, tool: DrawingTool):
        """Handle tool button click."""
        self._current_tool = tool
        self.tool_changed.emit(tool)

    # ==================== PUBLIC API ====================

    @property
    def current_tool(self) -> DrawingTool:
        """Get the currently selected tool."""
        return self._current_tool

    @property
    def current_color(self) -> QColor:
        """Get the currently selected color."""
        return self._color_picker.current_color

    def set_tool(self, tool: DrawingTool):
        """Set the active tool programmatically."""
        if tool in self._tool_buttons:
            self._tool_buttons[tool].setChecked(True)
            self._current_tool = tool

    def set_color(self, color: QColor):
        """Set the current color programmatically."""
        self._color_picker.current_color = color

    def set_undo_enabled(self, enabled: bool):
        """Enable/disable the undo button."""
        self._undo_btn.setEnabled(enabled)

    def set_redo_enabled(self, enabled: bool):
        """Enable/disable the redo button."""
        self._redo_btn.setEnabled(enabled)

    def update_theme(self):
        """Update icons when theme changes."""
        theme = get_theme_manager().get_current_theme()
        self._icon_color = theme.palette.header_icon_color if theme else "#e0e0e0"

        # Update all tool button icons
        for (icon_name, tool, _) in self.TOOLS:
            if tool in self._tool_buttons:
                icon_path = IconLoader.get(icon_name)
                self._tool_buttons[tool].setIcon(
                    colorize_white_svg(icon_path, self._icon_color)
                )

        # Update action button icons
        for btn, icon_name in [
            (self._undo_btn, "undo"),
            (self._redo_btn, "redo"),
            (self._clear_btn, "clear"),
        ]:
            icon_path = IconLoader.get(icon_name)
            btn.setIcon(colorize_white_svg(icon_path, self._icon_color))
