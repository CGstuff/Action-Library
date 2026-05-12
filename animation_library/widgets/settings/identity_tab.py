"""
IdentityTab - Settings tab for editing per-machine identity.

Lets the user change the name / display name / color set in the first-run
identity wizard. Writes directly to identity.json via Config.save_identity()
when Apply is hit, then emits identity_changed on the event bus so the
header pill (and any other listener) refreshes immediately.

Part of the Option B migration. See option_b_migration_plan.md Phase 5.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...config import Config
from ...events.event_bus import get_event_bus
from ...services.identity import (
    Identity,
    generate_color_from_name,
    sanitize_username,
)


_COLOR_SWATCH_SIZE = 24


class IdentityTab(QWidget):
    """Settings tab for viewing and editing per-machine identity."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self._theme_manager = theme_manager

        # Track whether the user clicked the color picker so we don't
        # auto-regenerate color from the name when they're typing.
        self._color_manually_picked: bool = False

        # Current identity from disk (may be None on weird edge cases — the
        # first-run wizard normally guarantees one exists by the time the
        # main window is up).
        identity = Config.load_identity()
        self._color: str = identity.color if identity else generate_color_from_name("artist")
        self._initial_name: str = identity.name if identity else ""

        self._build_ui(identity)
        self._wire_signals()

    # ------------------------------------------------------------------ UI

    def _build_ui(self, identity) -> None:
        # Sharp styling matches the rest of the settings tabs.
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3a3a3a;
                border-radius: 0px;
                margin-top: 12px;
                padding: 12px;
                padding-top: 24px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #e0e0e0;
            }
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #555;
                border-radius: 0px;
                padding: 6px 8px;
                color: #e0e0e0;
            }
            QLineEdit:focus { border-color: #3A8FB7; }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 0px;
                padding: 6px 12px;
                color: #e0e0e0;
            }
            QPushButton:hover { background-color: #4a4a4a; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        identity_group = QGroupBox("Identity")
        group_layout = QVBoxLayout(identity_group)

        # Description — explains what identity is and that it's per-machine.
        description = QLabel(
            "Your name and color identify your notes, drawings, and other "
            "actions in the library. Stored on this machine only — other "
            "artists on the same shared library set up their own identity."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #aaa; font-size: 11px;")
        group_layout.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self._username_field = QLineEdit(identity.name if identity else "")
        self._username_field.setPlaceholderText("alice")
        form.addRow("Username:", self._username_field)

        self._display_field = QLineEdit(identity.display_name if identity else "")
        self._display_field.setPlaceholderText("Alice Chen")
        form.addRow("Display name:", self._display_field)

        # Color row
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        self._color_swatch = QLabel()
        self._color_swatch.setFixedSize(_COLOR_SWATCH_SIZE, _COLOR_SWATCH_SIZE)
        self._update_color_swatch()
        color_row.addWidget(self._color_swatch)

        self._color_button = QPushButton("Pick another color...")
        color_row.addWidget(self._color_button)
        color_row.addStretch()

        color_row_widget = QWidget()
        color_row_widget.setLayout(color_row)
        form.addRow("Color:", color_row_widget)

        group_layout.addLayout(form)

        # Validation hint / username-rename warning
        self._hint_label = QLabel("")
        self._hint_label.setWordWrap(True)
        self._hint_label.setStyleSheet("color: #888; font-size: 11px; margin-top: 4px;")
        self._hint_label.setMinimumHeight(18)
        group_layout.addWidget(self._hint_label)

        layout.addWidget(identity_group)

        # Standing warning about renaming — existing notes won't re-attribute.
        rename_warning = QLabel(
            "Note: changing your username does not retroactively rename "
            "existing notes or strokes. Old attributions stay as written. "
            "Pick the new name carefully if collaborating with others."
        )
        rename_warning.setWordWrap(True)
        rename_warning.setStyleSheet(
            "color: #d97757; font-size: 11px; "
            "padding: 8px; border: 1px solid #444; "
            "background-color: #2a2018;"
        )
        layout.addWidget(rename_warning)

        layout.addStretch()

    def _wire_signals(self) -> None:
        self._username_field.textChanged.connect(self._on_username_changed)
        self._display_field.textChanged.connect(self._refresh_hint)
        self._color_button.clicked.connect(self._on_pick_color)

    # ---------------------------------------------------- Field interactions

    def _on_username_changed(self, _text: str) -> None:
        # Auto-regenerate color from username unless the user has manually
        # picked one this session.
        if not self._color_manually_picked:
            self._color = generate_color_from_name(
                sanitize_username(self._username_field.text())
            )
            self._update_color_swatch()
        self._refresh_hint()

    def _on_pick_color(self) -> None:
        initial = QColor(self._color)
        chosen = QColorDialog.getColor(initial, self, "Pick your identity color")
        if chosen.isValid():
            self._color = chosen.name()
            self._color_manually_picked = True
            self._update_color_swatch()

    def _update_color_swatch(self) -> None:
        self._color_swatch.setStyleSheet(
            f"background-color: {self._color}; border-radius: 4px;"
        )

    def _refresh_hint(self) -> None:
        sanitized = sanitize_username(self._username_field.text())
        if sanitized and sanitized != self._username_field.text():
            self._hint_label.setText(f"Username will be saved as: {sanitized}")
        else:
            self._hint_label.setText("")

    # ---------------------------------------------------------- Persistence

    def save_settings(self) -> None:
        """
        Persist the identity if it actually changed and is valid.

        Called by SettingsDialog._on_apply on Apply / OK. Silently no-ops
        if the form is invalid (empty fields) — the wizard guarantees a
        valid identity exists, so an empty save here means "user cleared
        the field but didn't intend to" rather than "delete identity."
        """
        sanitized = sanitize_username(self._username_field.text())
        display = self._display_field.text().strip()
        if not sanitized or not display:
            return  # invalid — preserve existing identity on disk

        new_identity = Identity(
            name=sanitized, display_name=display, color=self._color
        )

        existing = Config.load_identity()
        if existing == new_identity:
            return  # nothing changed

        if Config.save_identity(new_identity):
            # Notify listeners (header pill, etc.) so they refresh.
            get_event_bus().identity_changed.emit(new_identity)


__all__ = ['IdentityTab']
