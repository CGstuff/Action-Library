"""
DrawingToolbar - Toolbar for drawover annotation tools

Provides UI for:
- Tool selection (pen, line, arrow, rect, circle, text, eraser)
- Color picker with preset colors
- Brush size slider
- Undo/Redo buttons
- Clear frame button
"""

from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider,
    QLabel, QFrame, QButtonGroup, QColorDialog, QToolTip,
    QSizePolicy, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter, QCursor

from .drawover_canvas import DrawingTool


class ColorButton(QPushButton):
    """Button that displays a color swatch."""

    color_changed = pyqtSignal(QColor)

    def __init__(self, color: QColor, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()
        self.clicked.connect(self._on_clicked)

    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, value: QColor):
        self._color = value
        self._update_style()

    def _update_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color.name()};
                border: 2px solid #555;
                border-radius: 0px;
            }}
            QPushButton:hover {{
                border-color: #888;
            }}
            QPushButton:checked {{
                border-color: #fff;
                border-width: 3px;
            }}
        """)

    def _on_clicked(self):
        self.color_changed.emit(self._color)


class ColorPicker(QWidget):
    """Color picker with preset colors and custom color option."""

    color_changed = pyqtSignal(QColor)

    PRESET_COLORS = [
        '#FF5722',  # Orange (default)
        '#F44336',  # Red
        '#E91E63',  # Pink
        '#9C27B0',  # Purple
        '#2196F3',  # Blue
        '#00BCD4',  # Cyan
        '#4CAF50',  # Green
        '#FFEB3B',  # Yellow
        '#FFFFFF',  # White
        '#000000',  # Black
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_color = QColor('#FF5722')
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Current color display button (opens color dialog)
        self._current_btn = QPushButton()
        self._current_btn.setFixedSize(32, 32)
        self._current_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._current_btn.setToolTip("Current color - Click to open color picker")
        self._current_btn.clicked.connect(self._open_color_dialog)
        self._update_current_button()
        layout.addWidget(self._current_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background: #555; max-width: 1px;")
        layout.addWidget(sep)

        # Preset color buttons
        self._preset_buttons: List[ColorButton] = []
        for color_hex in self.PRESET_COLORS:
            btn = ColorButton(QColor(color_hex))
            btn.color_changed.connect(self._on_preset_clicked)
            self._preset_buttons.append(btn)
            layout.addWidget(btn)

    def _update_current_button(self):
        self._current_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._current_color.name()};
                border: 2px solid #666;
                border-radius: 0px;
            }}
            QPushButton:hover {{
                border-color: #999;
            }}
        """)

    def _on_preset_clicked(self, color: QColor):
        self._current_color = color
        self._update_current_button()
        self.color_changed.emit(color)

    def _open_color_dialog(self):
        color = QColorDialog.getColor(
            self._current_color,
            self,
            "Choose Annotation Color"
        )
        if color.isValid():
            self._current_color = color
            self._update_current_button()
            self.color_changed.emit(color)

    @property
    def current_color(self) -> QColor:
        return self._current_color

    @current_color.setter
    def current_color(self, value: QColor):
        self._current_color = value
        self._update_current_button()


class ToolButton(QPushButton):
    """Tool selection button with icon/text."""

    def __init__(
        self,
        tool: DrawingTool,
        text: str,
        tooltip: str,
        parent: Optional[QWidget] = None
    ):
        super().__init__(text, parent)
        self._tool = tool
        self.setCheckable(True)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self._setup_style()

    @property
    def tool(self) -> DrawingTool:
        return self._tool

    def _setup_style(self):
        self.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #ccc;
                border: 1px solid #555;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border-color: #666;
            }
            QPushButton:checked {
                background-color: #FF5722;
                color: white;
                border-color: #FF5722;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #666;
            }
        """)


class DrawingToolbar(QWidget):
    """
    Toolbar widget for drawover annotation tools.

    Signals:
        tool_changed(DrawingTool): Emitted when tool selection changes
        color_changed(QColor): Emitted when color changes
        brush_size_changed(int): Emitted when brush size changes
        undo_clicked(): Emitted when undo button clicked
        redo_clicked(): Emitted when redo button clicked
        clear_clicked(): Emitted when clear button clicked
    """

    tool_changed = pyqtSignal(object)  # DrawingTool
    color_changed = pyqtSignal(QColor)
    brush_size_changed = pyqtSignal(int)
    undo_clicked = pyqtSignal()
    redo_clicked = pyqtSignal()
    clear_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_tool = DrawingTool.NONE
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Tool selection section
        tools_frame = QFrame()
        tools_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 1px solid #444;
                border-radius: 0px;
            }
        """)
        tools_layout = QHBoxLayout(tools_frame)
        tools_layout.setContentsMargins(4, 4, 4, 4)
        tools_layout.setSpacing(2)

        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        self._tool_buttons: dict[DrawingTool, ToolButton] = {}

        # Define tools with labels and tooltips
        tools = [
            (DrawingTool.NONE, "OFF", "Disable drawing (passthrough mode)"),
            (DrawingTool.PEN, "PEN", "Freehand pen tool"),
            (DrawingTool.LINE, "LINE", "Straight line tool"),
            (DrawingTool.ARROW, "ARR", "Arrow tool"),
            (DrawingTool.RECT, "RECT", "Rectangle tool"),
            (DrawingTool.CIRCLE, "CIRC", "Circle/Ellipse tool"),
            (DrawingTool.TEXT, "TXT", "Text annotation tool"),
            (DrawingTool.ERASER, "ERAS", "Eraser tool"),
        ]

        for tool, text, tooltip in tools:
            btn = ToolButton(tool, text, tooltip)
            self._tool_group.addButton(btn)
            self._tool_buttons[tool] = btn
            tools_layout.addWidget(btn)

        # Set NONE as default
        self._tool_buttons[DrawingTool.NONE].setChecked(True)

        self._tool_group.buttonClicked.connect(self._on_tool_clicked)

        layout.addWidget(tools_frame)

        # Separator
        layout.addWidget(self._create_separator())

        # Color picker section
        color_frame = QFrame()
        color_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 1px solid #444;
                border-radius: 0px;
            }
        """)
        color_layout = QHBoxLayout(color_frame)
        color_layout.setContentsMargins(4, 4, 4, 4)
        color_layout.setSpacing(4)

        color_label = QLabel("Color:")
        color_label.setStyleSheet("color: #aaa; border: none;")
        color_layout.addWidget(color_label)

        self._color_picker = ColorPicker()
        self._color_picker.color_changed.connect(self._on_color_changed)
        color_layout.addWidget(self._color_picker)

        layout.addWidget(color_frame)

        # Separator
        layout.addWidget(self._create_separator())

        # Brush size section
        size_frame = QFrame()
        size_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 1px solid #444;
                border-radius: 0px;
            }
        """)
        size_layout = QHBoxLayout(size_frame)
        size_layout.setContentsMargins(4, 4, 4, 4)
        size_layout.setSpacing(4)

        size_label = QLabel("Size:")
        size_label.setStyleSheet("color: #aaa; border: none;")
        size_layout.addWidget(size_label)

        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(1, 30)
        self._size_slider.setValue(3)
        self._size_slider.setFixedWidth(80)
        self._size_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #333;
                height: 6px;
                border-radius: 0px;
            }
            QSlider::handle:horizontal {
                background: #FF5722;
                width: 14px;
                margin: -4px 0;
                border-radius: 0px;
            }
            QSlider::sub-page:horizontal {
                background: #FF5722;
                border-radius: 0px;
            }
        """)
        self._size_slider.valueChanged.connect(self._on_size_changed)
        size_layout.addWidget(self._size_slider)

        self._size_value = QLabel("3")
        self._size_value.setFixedWidth(24)
        self._size_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._size_value.setStyleSheet("color: #ccc; border: none;")
        size_layout.addWidget(self._size_value)

        layout.addWidget(size_frame)

        # Separator
        layout.addWidget(self._create_separator())

        # Action buttons section
        actions_frame = QFrame()
        actions_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 1px solid #444;
                border-radius: 0px;
            }
        """)
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(4, 4, 4, 4)
        actions_layout.setSpacing(2)

        # Undo button
        self._undo_btn = QPushButton("UNDO")
        self._undo_btn.setFixedSize(50, 28)
        self._undo_btn.setToolTip("Undo last stroke (Ctrl+Z)")
        self._undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._undo_btn.clicked.connect(self.undo_clicked.emit)
        self._style_action_button(self._undo_btn)
        actions_layout.addWidget(self._undo_btn)

        # Redo button
        self._redo_btn = QPushButton("REDO")
        self._redo_btn.setFixedSize(50, 28)
        self._redo_btn.setToolTip("Redo last stroke (Ctrl+Y)")
        self._redo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._redo_btn.clicked.connect(self.redo_clicked.emit)
        self._style_action_button(self._redo_btn)
        actions_layout.addWidget(self._redo_btn)

        # Clear button
        self._clear_btn = QPushButton("CLEAR")
        self._clear_btn.setFixedSize(50, 28)
        self._clear_btn.setToolTip("Clear all strokes on this frame")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear_clicked.emit)
        self._style_action_button(self._clear_btn, danger=True)
        actions_layout.addWidget(self._clear_btn)

        layout.addWidget(actions_frame)

        # Stretch to push everything left
        layout.addStretch()

    def _create_separator(self) -> QFrame:
        """Create a vertical separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background: transparent; max-width: 8px;")
        return sep

    def _style_action_button(self, btn: QPushButton, danger: bool = False):
        """Apply style to action button."""
        if danger:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d;
                    color: #f44336;
                    border: 1px solid #555;
                    border-radius: 0px;
                    font-weight: bold;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #f44336;
                    color: white;
                    border-color: #f44336;
                }
                QPushButton:pressed {
                    background-color: #d32f2f;
                }
                QPushButton:disabled {
                    background-color: #1a1a1a;
                    color: #555;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d;
                    color: #ccc;
                    border: 1px solid #555;
                    border-radius: 0px;
                    font-weight: bold;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #3a3a3a;
                    border-color: #666;
                }
                QPushButton:pressed {
                    background-color: #444;
                }
                QPushButton:disabled {
                    background-color: #1a1a1a;
                    color: #555;
                }
            """)

    def _on_tool_clicked(self, button: QPushButton):
        """Handle tool button click."""
        if isinstance(button, ToolButton):
            self._current_tool = button.tool
            self.tool_changed.emit(button.tool)

    def _on_color_changed(self, color: QColor):
        """Handle color change."""
        self.color_changed.emit(color)

    def _on_size_changed(self, value: int):
        """Handle brush size change."""
        self._size_value.setText(str(value))
        self.brush_size_changed.emit(value)

    # ==================== Public API ====================

    @property
    def current_tool(self) -> DrawingTool:
        return self._current_tool

    def set_tool(self, tool: DrawingTool):
        """Set the current tool."""
        if tool in self._tool_buttons:
            self._tool_buttons[tool].setChecked(True)
            self._current_tool = tool

    @property
    def current_color(self) -> QColor:
        return self._color_picker.current_color

    def set_color(self, color: QColor):
        """Set the current color."""
        self._color_picker.current_color = color

    @property
    def brush_size(self) -> int:
        return self._size_slider.value()

    def set_brush_size(self, size: int):
        """Set the brush size."""
        self._size_slider.setValue(size)

    def set_undo_enabled(self, enabled: bool):
        """Enable/disable undo button."""
        self._undo_btn.setEnabled(enabled)

    def set_redo_enabled(self, enabled: bool):
        """Enable/disable redo button."""
        self._redo_btn.setEnabled(enabled)

    def set_read_only(self, read_only: bool):
        """Set read-only mode (disables all tools except NONE)."""
        for tool, btn in self._tool_buttons.items():
            if tool != DrawingTool.NONE:
                btn.setEnabled(not read_only)

        self._color_picker.setEnabled(not read_only)
        self._size_slider.setEnabled(not read_only)
        self._clear_btn.setEnabled(not read_only)

        if read_only:
            self.set_tool(DrawingTool.NONE)


__all__ = ['DrawingToolbar', 'DrawingTool']
