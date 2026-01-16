"""
ApplyPanel - Panel for applying animations to Blender with options

Features:
- For Actions: Two buttons "Apply New Action" and "Apply at Playhead"
- For Poses: Single "Apply Pose to Blender" button
- Option checkboxes (Mirror, Reverse, Selected Bones, Use Slots)
- Settings persistence
- Optional hide of Mirror/Slots toggles for power users (keyboard shortcuts available)

Keyboard shortcuts (always available):
- Ctrl+double-click for Mirror
- Shift+double-click for Use Slots
- Alt+double-click for Insert at Playhead (actions only)
"""

from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings

from ..config import Config
from ..themes.theme_manager import get_theme_manager


class ApplyPanel(QWidget):
    """
    Panel for applying animations to Blender with options.

    Layout for Actions:
        ┌─────────────────────────────────┐
        │  [Apply New Action][At Playhead]│
        │                                 │
        │  [ ] Mirror Animation (L<->R)   │
        │  [ ] Reverse Animation          │
        │  [ ] Selected Bones Only        │
        │  [ ] Use Action Slots           │
        └─────────────────────────────────┘

    Layout for Poses:
        ┌─────────────────────────────────┐
        │  [=== Apply Pose to Blender ===]│
        │                                 │
        │  [ ] Mirror Pose (L<->R)        │
        │  [ ] Selected Bones Only        │
        └─────────────────────────────────┘

    Signals:
        apply_clicked: Emitted when apply button is clicked with options dict
    """

    apply_clicked = pyqtSignal(dict)  # Emits options dict

    def __init__(self, parent=None):
        super().__init__(parent)

        # Current animation (set from outside)
        self._current_animation: Optional[Dict[str, Any]] = None
        self._is_pose: bool = False

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

        # === Action buttons (shown for animations) ===
        self._new_action_button = QPushButton("Apply New Action")
        self._new_action_button.setMinimumHeight(40)
        self._new_action_button.setEnabled(False)
        self._new_action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_action_button.setToolTip("Create a new action with this animation")

        self._playhead_button = QPushButton("At Playhead")
        self._playhead_button.setMinimumHeight(40)
        self._playhead_button.setEnabled(False)
        self._playhead_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._playhead_button.setToolTip("Insert keyframes at current frame\nShortcut: Alt+double-click")

        # === Pose button (shown for poses) ===
        self._pose_button = QPushButton("Apply Pose to Blender")
        self._pose_button.setMinimumHeight(50)
        self._pose_button.setEnabled(False)
        self._pose_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pose_button.setToolTip("Apply this pose to the selected armature")

        # Option checkboxes
        self._mirror_check = QCheckBox("Mirror Animation (L<->R)")
        self._mirror_check.setToolTip("Mirror left/right bones (e.g., swap Left Hand with Right Hand)\nShortcut: Ctrl+double-click")

        self._reverse_check = QCheckBox("Reverse Animation")
        self._reverse_check.setToolTip("Play the animation backwards")

        self._bones_check = QCheckBox("Selected Bones Only")
        self._bones_check.setToolTip("Only apply animation to currently selected bones in Blender")

        self._slots_check = QCheckBox("Use Action Slots")
        self._slots_check.setToolTip(
            "Add animation to a slot on the current action.\n"
            "Requires an action with a slot to already exist on the armature.\n"
            "Shortcut: Shift+double-click"
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

        # Action buttons row (for animations)
        self._action_buttons_layout = QHBoxLayout()
        self._action_buttons_layout.setSpacing(4)
        self._action_buttons_layout.addWidget(self._new_action_button)
        self._action_buttons_layout.addWidget(self._playhead_button)

        # Container widget for action buttons
        self._action_buttons_widget = QWidget()
        self._action_buttons_widget.setLayout(self._action_buttons_layout)
        main_layout.addWidget(self._action_buttons_widget)

        # Pose button (for poses)
        main_layout.addWidget(self._pose_button)

        # Separator
        main_layout.addWidget(self._separator)

        # Options group
        self._options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(self._options_group)
        options_layout.setSpacing(4)
        options_layout.addWidget(self._mirror_check)
        options_layout.addWidget(self._reverse_check)
        options_layout.addWidget(self._bones_check)
        options_layout.addWidget(self._slots_check)
        main_layout.addWidget(self._options_group)

        # Push everything to top
        main_layout.addStretch()

        # Initially hide pose button (default to action mode)
        self._pose_button.hide()

    def _connect_signals(self):
        """Connect widget signals"""

        self._new_action_button.clicked.connect(self._on_new_action_clicked)
        self._playhead_button.clicked.connect(self._on_playhead_clicked)
        self._pose_button.clicked.connect(self._on_pose_clicked)

        # Save options when changed
        self._mirror_check.stateChanged.connect(self._save_options)
        self._reverse_check.stateChanged.connect(self._save_options)
        self._bones_check.stateChanged.connect(self._save_options)
        self._slots_check.stateChanged.connect(self._save_options)

    def _apply_theme(self, theme_name: str = None):
        """Apply theme colors to widgets"""

        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        accent = theme.palette.accent
        text_color = theme.palette.text_primary

        # Style for main action buttons (Apply New Action, Apply Pose)
        primary_button_style = f"""
            QPushButton {{
                background-color: {accent};
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: 0px;
                border-radius: 0px;
                padding: 8px;
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
        """

        # Style for secondary button (At Playhead) - slightly muted
        secondary_button_style = f"""
            QPushButton {{
                background-color: #555555;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: 0px;
                border-radius: 0px;
                padding: 8px;
                outline: none;
            }}
            QPushButton:hover {{
                background-color: #666666;
                border: 0px;
                border-radius: 0px;
            }}
            QPushButton:pressed {{
                background-color: #444444;
                border: 0px;
                border-radius: 0px;
            }}
            QPushButton:disabled {{
                background-color: #444444;
                color: #777777;
                border: 0px;
                border-radius: 0px;
            }}
        """

        self._new_action_button.setStyleSheet(primary_button_style)
        self._playhead_button.setStyleSheet(secondary_button_style)
        self._pose_button.setStyleSheet(primary_button_style)

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
        self._is_pose = animation.get('is_pose', 0) == 1 if animation else False

        has_animation = animation is not None

        # Update button visibility and enabled state based on pose vs action
        if self._is_pose:
            # Pose mode: show single pose button, hide action buttons
            self._action_buttons_widget.hide()
            self._pose_button.show()
            self._pose_button.setEnabled(has_animation)

            # Update labels for pose mode
            self._mirror_check.setText("Mirror Pose (L<->R)")

            # Hide options that don't apply to poses
            self._reverse_check.hide()
            self._slots_check.hide()
        else:
            # Action mode: show action buttons, hide pose button
            self._action_buttons_widget.show()
            self._pose_button.hide()
            self._new_action_button.setEnabled(has_animation)
            self._playhead_button.setEnabled(has_animation)

            # Update labels for animation mode
            self._mirror_check.setText("Mirror Animation (L<->R)")

            # Show all options
            self._reverse_check.show()
            self._slots_check.show()

        # Update visibility of hidden toggles
        self._update_shortcut_toggles_visibility()

    def clear(self):
        """Clear the current animation"""
        self.set_animation(None)

    def get_options(self, apply_mode: str = "NEW") -> Dict[str, Any]:
        """
        Get current apply options.

        Args:
            apply_mode: "NEW" or "INSERT" - which apply mode to use

        Returns:
            Dict with keys:
                - apply_mode: "NEW" or "INSERT"
                - mirror: bool
                - reverse: bool
                - selected_bones_only: bool
                - use_slots: bool
        """
        return {
            "apply_mode": apply_mode,
            "mirror": self._mirror_check.isChecked(),
            "reverse": self._reverse_check.isChecked(),
            "selected_bones_only": self._bones_check.isChecked(),
            "use_slots": self._slots_check.isChecked()
        }

    def get_current_animation(self) -> Optional[Dict[str, Any]]:
        """Get the currently set animation"""
        return self._current_animation

    def is_pose(self) -> bool:
        """Check if current animation is a pose"""
        return self._is_pose

    # ==================== INTERNAL ====================

    def _on_new_action_clicked(self):
        """Handle Apply New Action button click"""
        if self._current_animation:
            options = self.get_options(apply_mode="NEW")
            self.apply_clicked.emit(options)

    def _on_playhead_clicked(self):
        """Handle At Playhead button click"""
        if self._current_animation:
            options = self.get_options(apply_mode="INSERT")
            self.apply_clicked.emit(options)

    def _on_pose_clicked(self):
        """Handle Apply Pose button click"""
        if self._current_animation:
            options = self.get_options(apply_mode="NEW")
            self.apply_clicked.emit(options)

    def _load_options(self):
        """Load saved options from settings"""
        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)

        # Checkboxes
        self._mirror_check.setChecked(settings.value("apply/mirror", False, type=bool))
        self._reverse_check.setChecked(settings.value("apply/reverse", False, type=bool))
        self._bones_check.setChecked(settings.value("apply/selected_bones", False, type=bool))
        self._slots_check.setChecked(settings.value("apply/use_slots", False, type=bool))

        # Apply visibility setting for power user mode
        self._update_shortcut_toggles_visibility()

    def _save_options(self):
        """Save current options to settings"""
        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)

        settings.setValue("apply/mirror", self._mirror_check.isChecked())
        settings.setValue("apply/reverse", self._reverse_check.isChecked())
        settings.setValue("apply/selected_bones", self._bones_check.isChecked())
        settings.setValue("apply/use_slots", self._slots_check.isChecked())

    def _update_shortcut_toggles_visibility(self):
        """Update visibility of Mirror and Slots toggles based on settings"""
        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)
        hide_toggles = settings.value("apply/hide_shortcut_toggles", False, type=bool)

        self._mirror_check.setVisible(not hide_toggles)
        self._slots_check.setVisible(not hide_toggles)

    def set_shortcut_toggles_visible(self, visible: bool):
        """Show or hide the Mirror and Slots toggles (for power users)"""
        self._mirror_check.setVisible(visible)
        self._slots_check.setVisible(visible)

        # Save preference
        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)
        settings.setValue("apply/hide_shortcut_toggles", not visible)


__all__ = ['ApplyPanel']
