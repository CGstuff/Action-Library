"""
Annotation Toolbar Widget

Single-row toolbar for drawover annotation with:
- Tool selection (pen, line, rect, circle)
- Color picker with presets
- Undo/Redo/Clear buttons

The display options (nav, hide, hold, ghost) are placed separately below the timeline.
"""

from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QButtonGroup,
    QMenu, QWidgetAction, QSpinBox, QCheckBox, QLabel, QColorDialog, QSlider
)
from PyQt6.QtCore import pyqtSignal, QSize, Qt
from PyQt6.QtGui import QColor

from .drawover_canvas import DrawingTool
from .drawing_toolbar import ColorPicker
from ..utils.icon_loader import IconLoader
from ..utils.icon_utils import colorize_white_svg
from ..themes.theme_manager import get_theme_manager


class GhostSettingsPopup(QMenu):
    """Popup menu for ghost/onion skin settings."""

    settings_changed = pyqtSignal(dict)  # Emits full settings dict
    ghost_toggled = pyqtSignal(bool)     # Emits enabled state

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                border: 1px solid #444;
                padding: 8px;
            }
            QLabel { color: #e0e0e0; }
            QSpinBox {
                background: #3a3a3a;
                border: 1px solid #555;
                color: #e0e0e0;
                padding: 2px 4px;
                min-width: 40px;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 0px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #555555;
                border: none;
            }
            QCheckBox::indicator:unchecked:hover {
                background-color: #666666;
            }
            QCheckBox::indicator:checked {
                background-color: #4a90e2;
                border: none;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #5a9ff2;
            }
            QPushButton {
                background: #3a3a3a;
                border: 1px solid #555;
                color: #e0e0e0;
                padding: 4px 8px;
                min-width: 60px;
            }
            QPushButton:hover { background: #4a4a4a; }
            QPushButton#enableBtn {
                background: #3a6a3a;
                border-color: #4a8a4a;
            }
            QPushButton#enableBtn:checked {
                background: #6a3a3a;
                border-color: #8a4a4a;
            }
        """)

        self._enabled = False
        self._before_frames = 2
        self._after_frames = 2
        self._linked = True
        self._sketches_only = True  # True = only frames with sketches, False = all frames
        self._before_color = QColor("#FF5555")  # Red tint
        self._after_color = QColor("#55FF55")   # Green tint

        self._build_ui()

    def _build_ui(self):
        """Build the popup UI."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Enable/Disable toggle at top
        self._enable_btn = QPushButton("Enable Ghost")
        self._enable_btn.setObjectName("enableBtn")
        self._enable_btn.setCheckable(True)
        self._enable_btn.setChecked(self._enabled)
        self._enable_btn.clicked.connect(self._on_enable_toggled)
        self._update_enable_button()
        layout.addWidget(self._enable_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #444;")
        layout.addWidget(sep)

        # Before frames
        before_row = QHBoxLayout()
        before_label = QLabel("Before:")
        before_label.setFixedWidth(50)
        self._before_spin = QSpinBox()
        self._before_spin.setRange(0, 5)
        self._before_spin.setValue(self._before_frames)
        self._before_spin.valueChanged.connect(self._on_before_changed)

        self._before_color_btn = QPushButton()
        self._before_color_btn.setFixedSize(24, 24)
        self._before_color_btn.setStyleSheet(
            f"background-color: {self._before_color.name()}; border: 1px solid #555;"
        )
        self._before_color_btn.clicked.connect(self._pick_before_color)

        before_row.addWidget(before_label)
        before_row.addWidget(self._before_spin)
        before_row.addWidget(self._before_color_btn)
        layout.addLayout(before_row)

        # After frames
        after_row = QHBoxLayout()
        after_label = QLabel("After:")
        after_label.setFixedWidth(50)
        self._after_spin = QSpinBox()
        self._after_spin.setRange(0, 5)
        self._after_spin.setValue(self._after_frames)
        self._after_spin.valueChanged.connect(self._on_after_changed)

        self._after_color_btn = QPushButton()
        self._after_color_btn.setFixedSize(24, 24)
        self._after_color_btn.setStyleSheet(
            f"background-color: {self._after_color.name()}; border: 1px solid #555;"
        )
        self._after_color_btn.clicked.connect(self._pick_after_color)

        after_row.addWidget(after_label)
        after_row.addWidget(self._after_spin)
        after_row.addWidget(self._after_color_btn)
        layout.addLayout(after_row)

        # Link checkbox
        self._link_check = QCheckBox("Link values")
        self._link_check.setChecked(self._linked)
        self._link_check.toggled.connect(self._on_link_toggled)
        layout.addWidget(self._link_check)

        # Separator before frame mode
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background: #444;")
        layout.addWidget(sep2)

        # Frame mode label
        mode_label = QLabel("Frame Mode:")
        mode_label.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(mode_label)

        # Sketches only radio (default)
        self._sketches_only_radio = QCheckBox("Consider only sketches")
        self._sketches_only_radio.setChecked(self._sketches_only)
        self._sketches_only_radio.setToolTip(
            "Show ghost from nearest frames that have annotations\n"
            "(skips empty frames)"
        )
        self._sketches_only_radio.toggled.connect(self._on_sketches_only_toggled)
        layout.addWidget(self._sketches_only_radio)

        # All frames radio
        self._all_frames_radio = QCheckBox("Consider all frames")
        self._all_frames_radio.setChecked(not self._sketches_only)
        self._all_frames_radio.setToolTip(
            "Show ghost from exactly N frames before/after\n"
            "(includes empty frames)"
        )
        self._all_frames_radio.toggled.connect(self._on_all_frames_toggled)
        layout.addWidget(self._all_frames_radio)

        # Add to menu as widget action
        action = QWidgetAction(self)
        action.setDefaultWidget(container)
        self.addAction(action)

    def _on_enable_toggled(self, checked: bool):
        """Handle enable/disable toggle."""
        self._enabled = checked
        self._update_enable_button()
        self.ghost_toggled.emit(checked)
        self._emit_settings()

    def _update_enable_button(self):
        """Update enable button text and style."""
        if self._enabled:
            self._enable_btn.setText("Disable Ghost")
        else:
            self._enable_btn.setText("Enable Ghost")

    def _on_before_changed(self, value: int):
        self._before_frames = value
        if self._linked:
            self._after_spin.blockSignals(True)
            self._after_spin.setValue(value)
            self._after_frames = value
            self._after_spin.blockSignals(False)
        self._emit_settings()

    def _on_after_changed(self, value: int):
        self._after_frames = value
        if self._linked:
            self._before_spin.blockSignals(True)
            self._before_spin.setValue(value)
            self._before_frames = value
            self._before_spin.blockSignals(False)
        self._emit_settings()

    def _on_link_toggled(self, checked: bool):
        self._linked = checked
        if checked:
            # Sync values when linking
            self._after_spin.setValue(self._before_frames)
            self._after_frames = self._before_frames

    def _on_sketches_only_toggled(self, checked: bool):
        """Handle 'Consider only sketches' toggle."""
        if checked:
            self._sketches_only = True
            # Uncheck the other option
            self._all_frames_radio.blockSignals(True)
            self._all_frames_radio.setChecked(False)
            self._all_frames_radio.blockSignals(False)
            self._emit_settings()

    def _on_all_frames_toggled(self, checked: bool):
        """Handle 'Consider all frames' toggle."""
        if checked:
            self._sketches_only = False
            # Uncheck the other option
            self._sketches_only_radio.blockSignals(True)
            self._sketches_only_radio.setChecked(False)
            self._sketches_only_radio.blockSignals(False)
            self._emit_settings()

    def _pick_before_color(self):
        color = QColorDialog.getColor(self._before_color, self, "Before Color")
        if color.isValid():
            self._before_color = color
            self._before_color_btn.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid #555;"
            )
            self._emit_settings()

    def _pick_after_color(self):
        color = QColorDialog.getColor(self._after_color, self, "After Color")
        if color.isValid():
            self._after_color = color
            self._after_color_btn.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid #555;"
            )
            self._emit_settings()

    def _emit_settings(self):
        self.settings_changed.emit(self.get_settings())

    def get_settings(self) -> dict:
        return {
            'enabled': self._enabled,
            'before_frames': self._before_frames,
            'after_frames': self._after_frames,
            'before_color': self._before_color,
            'after_color': self._after_color,
            'linked': self._linked,
            'sketches_only': self._sketches_only  # True = only frames with sketches, False = all frames
        }

    def is_enabled(self) -> bool:
        """Check if ghost mode is enabled."""
        return self._enabled

    def set_enabled(self, enabled: bool):
        """Set ghost enabled state (updates UI)."""
        self._enabled = enabled
        self._enable_btn.setChecked(enabled)
        self._update_enable_button()


class AnnotationToolbar(QWidget):
    """Single-row annotation toolbar for drawing tools only."""

    # Signals
    tool_changed = pyqtSignal(object)  # DrawingTool
    color_changed = pyqtSignal(QColor)
    brush_size_changed = pyqtSignal(int)  # 1-30
    opacity_changed = pyqtSignal(float)  # 0.0-1.0
    undo_clicked = pyqtSignal()
    redo_clicked = pyqtSignal()
    clear_clicked = pyqtSignal()
    delete_all_clicked = pyqtSignal()  # Nuclear option - delete ALL annotations

    # Tool definitions: (icon_name, DrawingTool, tooltip, shortcut)
    TOOLS = [
        ("pen", DrawingTool.PEN, "Thin pen - fixed 2px (P)", "P"),
        ("brush", DrawingTool.BRUSH, "Brush - pressure sensitive (B)", "B"),
        ("line", DrawingTool.LINE, "Straight line (L)", "L"),
        ("arrow_draw", DrawingTool.ARROW, "Arrow (A)", "A"),
        ("rectangle", DrawingTool.RECT, "Rectangle (R)", "R"),
        ("circle", DrawingTool.CIRCLE, "Circle (C)", "C"),
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
        """Build the single-row toolbar UI."""
        # Set minimum height to ensure toolbar isn't clipped
        # ColorPicker has 32px buttons, plus margins = 40px minimum
        self.setMinimumHeight(40)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Get theme icon color
        theme = get_theme_manager().get_current_theme()
        self._icon_color = theme.palette.header_icon_color if theme else "#e0e0e0"

        # Button styles
        self._tool_btn_style = """
            QPushButton { background: #2d2d2d; border: 1px solid #444; border-radius: 3px; }
            QPushButton:hover { background: #3a3a3a; border-color: #555; }
            QPushButton:checked { background: #FF5722; border-color: #FF5722; }
            QPushButton:disabled { background: #252525; border-color: #333; }
        """

        # ===== Brush Size Slider Section =====
        brush_size_icon = QLabel()
        icon_path = IconLoader.get("brush_size")
        brush_size_icon.setPixmap(colorize_white_svg(icon_path, self._icon_color).pixmap(18, 18))
        brush_size_icon.setToolTip("Brush Size")
        layout.addWidget(brush_size_icon)

        self._brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self._brush_size_slider.setProperty("cardsize", "true")  # Use theme styling
        self._brush_size_slider.setRange(1, 30)
        self._brush_size_slider.setValue(3)
        self._brush_size_slider.setFixedWidth(80)
        self._brush_size_slider.setFixedHeight(20)
        self._brush_size_slider.setToolTip("Brush Size (1-30)")
        layout.addWidget(self._brush_size_slider)

        self._brush_size_label = QLabel("3")
        self._brush_size_label.setFixedWidth(20)
        self._brush_size_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        layout.addWidget(self._brush_size_label)

        layout.addWidget(self._create_separator())

        # ===== Opacity Slider Section =====
        opacity_icon = QLabel()
        icon_path = IconLoader.get("opacity")
        opacity_icon.setPixmap(colorize_white_svg(icon_path, self._icon_color).pixmap(18, 18))
        opacity_icon.setToolTip("Opacity")
        layout.addWidget(opacity_icon)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setProperty("cardsize", "true")  # Use theme styling
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(100)
        self._opacity_slider.setFixedWidth(80)
        self._opacity_slider.setFixedHeight(20)
        self._opacity_slider.setToolTip("Opacity (0-100%)")
        layout.addWidget(self._opacity_slider)

        self._opacity_label = QLabel("100%")
        self._opacity_label.setFixedWidth(32)
        self._opacity_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        layout.addWidget(self._opacity_label)

        layout.addWidget(self._create_separator())

        # Tool button group (exclusive selection)
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)

        # Create tool buttons
        for icon_name, tool, tooltip, shortcut in self.TOOLS:
            btn = self._create_tool_button(icon_name, tooltip)
            self._tool_group.addButton(btn)
            self._tool_buttons[tool] = btn
            layout.addWidget(btn)

        layout.addWidget(self._create_separator())

        # Color picker
        self._color_picker = ColorPicker()
        layout.addWidget(self._color_picker)

        layout.addWidget(self._create_separator())

        # Undo button
        self._undo_btn = self._create_action_button("undo", "Undo (Ctrl+Z)")
        layout.addWidget(self._undo_btn)

        # Redo button
        self._redo_btn = self._create_action_button("redo", "Redo (Ctrl+Y)")
        layout.addWidget(self._redo_btn)

        # Clear button (current frame)
        self._clear_btn = self._create_action_button("clear", "Clear annotations on this frame")
        clear_style = self._tool_btn_style.replace("#FF5722", "#f44336")
        self._clear_btn.setStyleSheet(clear_style)
        layout.addWidget(self._clear_btn)

        # Spacer before nuclear option
        layout.addSpacing(12)

        # Delete All button (nuclear option)
        self._delete_all_btn = self._create_action_button("delete_all", "DELETE ALL annotations on ALL frames")
        nuclear_style = """
            QPushButton { background: #4a2020; border: 1px solid #8b0000; border-radius: 3px; }
            QPushButton:hover { background: #6a2020; border-color: #aa0000; }
            QPushButton:pressed { background: #8b0000; }
        """
        self._delete_all_btn.setStyleSheet(nuclear_style)
        layout.addWidget(self._delete_all_btn)

        layout.addStretch()

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
        # Sliders
        self._brush_size_slider.valueChanged.connect(self._on_brush_size_changed)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)

        # Tool buttons
        for tool, btn in self._tool_buttons.items():
            btn.clicked.connect(lambda checked, t=tool: self._on_tool_clicked(t))

        # Color picker
        self._color_picker.color_changed.connect(self.color_changed.emit)

        # Action buttons
        self._undo_btn.clicked.connect(self.undo_clicked.emit)
        self._redo_btn.clicked.connect(self.redo_clicked.emit)
        self._clear_btn.clicked.connect(self.clear_clicked.emit)
        self._delete_all_btn.clicked.connect(self.delete_all_clicked.emit)

    def _on_brush_size_changed(self, value: int):
        """Handle brush size slider change."""
        self._brush_size_label.setText(str(value))
        self.brush_size_changed.emit(value)

    def _on_opacity_changed(self, value: int):
        """Handle opacity slider change."""
        self._opacity_label.setText(f"{value}%")
        # Convert 0-100 to 0.0-1.0
        self.opacity_changed.emit(value / 100.0)

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

    @property
    def brush_size(self) -> int:
        """Get current brush size."""
        return self._brush_size_slider.value()

    @brush_size.setter
    def brush_size(self, value: int):
        """Set brush size (1-30)."""
        self._brush_size_slider.setValue(max(1, min(30, value)))

    @property
    def opacity(self) -> float:
        """Get current opacity (0.0-1.0)."""
        return self._opacity_slider.value() / 100.0

    @opacity.setter
    def opacity(self, value: float):
        """Set opacity (0.0-1.0)."""
        self._opacity_slider.setValue(int(max(0.0, min(1.0, value)) * 100))

    def update_theme(self):
        """Update icons when theme changes."""
        theme = get_theme_manager().get_current_theme()
        self._icon_color = theme.palette.header_icon_color if theme else "#e0e0e0"

        # Update all tool button icons
        for (icon_name, tool, _, _) in self.TOOLS:
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
            (self._delete_all_btn, "delete_all"),
        ]:
            icon_path = IconLoader.get(icon_name)
            btn.setIcon(colorize_white_svg(icon_path, self._icon_color))
