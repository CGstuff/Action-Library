"""
ApplyPanel - Panel for applying animations to Blender with options

Features:
- Big "Apply to Blender" button
- Apply mode selection (New Action / Insert at Playhead)
- Option checkboxes (Mirror, Reverse, Selected Bones, Use Slots)
- Settings persistence
"""

from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QFrame, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings

from ..config import Config
from ..themes.theme_manager import get_theme_manager


class ApplyPanel(QWidget):
    """
    Panel for applying animations to Blender with options.

    Layout:
        ┌─────────────────────────────────┐
        │  APPLY TO BLENDER               │
        │  [========= BIG BUTTON ========]│
        │                                 │
        │  Apply Mode: [New Action     v] │
        │                                 │
        │  [ ] Mirror Animation (L<->R)   │
        │  [ ] Reverse Animation          │
        │  [ ] Selected Bones Only        │
        │  [ ] Use Action Slots (4.5+)    │
        └─────────────────────────────────┘

    Signals:
        apply_clicked: Emitted when apply button is clicked with options dict
    """

    apply_clicked = pyqtSignal(dict)  # Emits options dict

    def __init__(self, parent=None):
        super().__init__(parent)

        # Current animation (set from outside)
        self._current_animation: Optional[Dict[str, Any]] = None

        # Theme manager
        self._theme_manager = get_theme_manager()

        # Create UI
        self._create_widgets()
        self._create_layout()
        self._connect_signals()

        # Load saved options
        self._load_options()

        # Apply theme
        self._apply_theme()
        self._theme_manager.theme_changed.connect(self._apply_theme)

    def _create_widgets(self):
        """Create panel widgets"""

        # Big apply button
        self._apply_button = QPushButton("APPLY ACTION TO BLENDER")
        self._apply_button.setMinimumHeight(50)
        self._apply_button.setEnabled(False)  # Disabled until animation selected
        self._apply_button.setCursor(Qt.CursorShape.PointingHandCursor)

        # Apply mode combo
        self._mode_label = QLabel("Apply Mode:")
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["New Action", "Insert at Playhead"])
        self._mode_combo.setToolTip(
            "New Action: Create a new action with the animation\n"
            "Insert at Playhead: Insert keyframes at current frame"
        )

        # Option checkboxes
        self._mirror_check = QCheckBox("Mirror Animation (L<->R)")
        self._mirror_check.setToolTip("Mirror left/right bones (e.g., swap Left Hand with Right Hand)")

        self._reverse_check = QCheckBox("Reverse Animation")
        self._reverse_check.setToolTip("Play the animation backwards")

        self._bones_check = QCheckBox("Selected Bones Only")
        self._bones_check.setToolTip("Only apply animation to currently selected bones in Blender")

        self._slots_check = QCheckBox("Use Action Slots (requires existing action)")
        self._slots_check.setToolTip(
            "Experimental: Add animation to a slot on the current action.\n"
            "Requires an action with a slot to already exist on the armature.\n"
            "For future Blender animation layers workflow."
        )

        # Separator line
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        self._separator.setFrameShadow(QFrame.Shadow.Sunken)

    def _create_layout(self):
        """Create panel layout"""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Big apply button
        main_layout.addWidget(self._apply_button)

        # Separator
        main_layout.addWidget(self._separator)

        # Apply mode row
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self._mode_label)
        mode_layout.addWidget(self._mode_combo, 1)
        main_layout.addLayout(mode_layout)

        # Spacer
        main_layout.addSpacing(4)

        # Options group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(4)
        options_layout.addWidget(self._mirror_check)
        options_layout.addWidget(self._reverse_check)
        options_layout.addWidget(self._bones_check)
        options_layout.addWidget(self._slots_check)
        main_layout.addWidget(options_group)

        # Push everything to top
        main_layout.addStretch()

    def _connect_signals(self):
        """Connect widget signals"""

        self._apply_button.clicked.connect(self._on_apply_clicked)

        # Save options when changed
        self._mode_combo.currentIndexChanged.connect(self._save_options)
        self._mirror_check.stateChanged.connect(self._save_options)
        self._reverse_check.stateChanged.connect(self._save_options)
        self._bones_check.stateChanged.connect(self._save_options)
        self._slots_check.stateChanged.connect(self._save_options)

    def _apply_theme(self, theme_name: str = None):
        """Apply theme colors to widgets"""

        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        # Style the big apply button with accent color
        accent = theme.palette.accent
        text_color = theme.palette.text_primary
        self._apply_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: 0px;
                border-radius: 0px;
                padding: 10px;
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {self._lighten_color(accent, 15)};
                border: 0px;
                border-radius: 0px;
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(accent, 15)};
                border: 0px;
                border-radius: 0px;
            }}
            QPushButton:disabled {{
                background-color: #666666;
                color: #999999;
                border: 0px;
                border-radius: 0px;
            }}
        """)

        # Style checkboxes - gray unchecked, accent when checked (sharp, no bevels)
        checkbox_style = f"""
            QCheckBox {{
                color: {text_color};
                spacing: 8px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 0px;
                border-radius: 0px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: #555555;
                border: 0px;
                border-radius: 0px;
            }}
            QCheckBox::indicator:unchecked:hover {{
                background-color: #666666;
                border: 0px;
                border-radius: 0px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {accent};
                border: 0px;
                border-radius: 0px;
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {self._lighten_color(accent, 15)};
                border: 0px;
                border-radius: 0px;
            }}
        """
        self._mirror_check.setStyleSheet(checkbox_style)
        self._reverse_check.setStyleSheet(checkbox_style)
        self._bones_check.setStyleSheet(checkbox_style)
        self._slots_check.setStyleSheet(checkbox_style)

    def _lighten_color(self, hex_color: str, percent: int) -> str:
        """Lighten a hex color by percentage"""
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = min(255, r + int(r * percent / 100))
        g = min(255, g + int(g * percent / 100))
        b = min(255, b + int(b * percent / 100))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _darken_color(self, hex_color: str, percent: int) -> str:
        """Darken a hex color by percentage"""
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = max(0, r - int(r * percent / 100))
        g = max(0, g - int(g * percent / 100))
        b = max(0, b - int(b * percent / 100))
        return f"#{r:02x}{g:02x}{b:02x}"

    # ==================== PUBLIC API ====================

    def set_animation(self, animation: Optional[Dict[str, Any]]):
        """
        Set the current animation for apply.

        Args:
            animation: Animation data dict or None to clear
        """
        self._current_animation = animation
        self._apply_button.setEnabled(animation is not None)

    def clear(self):
        """Clear the current animation"""
        self.set_animation(None)

    def get_options(self) -> Dict[str, Any]:
        """
        Get current apply options.

        Returns:
            Dict with keys:
                - apply_mode: "NEW" or "INSERT"
                - mirror: bool
                - reverse: bool
                - selected_bones_only: bool
                - use_slots: bool
        """
        return {
            "apply_mode": "NEW" if self._mode_combo.currentIndex() == 0 else "INSERT",
            "mirror": self._mirror_check.isChecked(),
            "reverse": self._reverse_check.isChecked(),
            "selected_bones_only": self._bones_check.isChecked(),
            "use_slots": self._slots_check.isChecked()
        }

    def get_current_animation(self) -> Optional[Dict[str, Any]]:
        """Get the currently set animation"""
        return self._current_animation

    # ==================== INTERNAL ====================

    def _on_apply_clicked(self):
        """Handle apply button click"""
        if self._current_animation:
            options = self.get_options()
            self.apply_clicked.emit(options)

    def _load_options(self):
        """Load saved options from settings"""
        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)

        # Apply mode
        mode_index = settings.value("apply/mode_index", 0, type=int)
        self._mode_combo.setCurrentIndex(mode_index)

        # Checkboxes
        self._mirror_check.setChecked(settings.value("apply/mirror", False, type=bool))
        self._reverse_check.setChecked(settings.value("apply/reverse", False, type=bool))
        self._bones_check.setChecked(settings.value("apply/selected_bones", False, type=bool))
        self._slots_check.setChecked(settings.value("apply/use_slots", False, type=bool))

    def _save_options(self):
        """Save current options to settings"""
        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)

        settings.setValue("apply/mode_index", self._mode_combo.currentIndex())
        settings.setValue("apply/mirror", self._mirror_check.isChecked())
        settings.setValue("apply/reverse", self._reverse_check.isChecked())
        settings.setValue("apply/selected_bones", self._bones_check.isChecked())
        settings.setValue("apply/use_slots", self._slots_check.isChecked())


__all__ = ['ApplyPanel']
