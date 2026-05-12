"""
Identity Wizard - First-run dialog for setting up per-machine user identity.

Shown once on first launch when no identity.json exists. The user picks a
short username, a display name, and a color. After this completes, every
note/stroke/action created by this app stamps the local username for
attribution. No login, no auth — identity is purely advisory and lives only
on this machine.

This is part of the Option B migration (per-machine identity instead of a
shared user roster). See option_b_migration_plan.md for context.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...config import Config
from ...services.identity import (
    Identity,
    generate_color_from_name,
    sanitize_username,
)


# Dialog dimensions — kept compact; this is a one-form wizard, not a setup.
_DIALOG_WIDTH = 440
_COLOR_SWATCH_SIZE = 28


class IdentityWizard(QDialog):
    """
    First-run identity setup dialog.

    Cannot be cancelled — closing the dialog (Esc, X button, Cancel) is
    treated as rejection by the caller, which exits the app. This mirrors
    the behavior of the existing SetupWizard so first-run flows feel
    consistent.

    Usage:
        wizard = IdentityWizard()
        if wizard.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        Config.save_identity(wizard.get_identity())
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Welcome to Action Library")
        self.setModal(True)
        self.setMinimumWidth(_DIALOG_WIDTH)

        # Disable the close (X) button — like SetupWizard, the app exits on
        # rejection, so we don't want users to think closing means "skip."
        # They can still hit Esc or Cancel; both reject.
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint
        )

        # Color picked by the user (or auto-generated). Initialized after
        # username is set so it gets a deterministic palette pick.
        self._color: str = generate_color_from_name(self._guess_username())

        self._build_ui()
        self._wire_signals()
        self._refresh_validity()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        # Title
        title = QLabel("Set up your identity")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Description — explains what this is and why it's per-machine.
        description = QLabel(
            "Your name and color will be used to attribute notes, drawings, "
            "and other actions you take in the library.\n\n"
            "This is stored only on this machine. Other artists using the "
            "same shared library will set up their own identity on their "
            "own machines."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #aaa;")
        layout.addWidget(description)

        layout.addSpacing(4)

        # Form: username, display name, color
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        guessed_username = self._guess_username()
        guessed_display = self._title_case(guessed_username)

        self._username_field = QLineEdit(guessed_username)
        self._username_field.setPlaceholderText("alice")
        form.addRow("Username:", self._username_field)

        self._display_field = QLineEdit(guessed_display)
        self._display_field.setPlaceholderText("Alice Chen")
        form.addRow("Display name:", self._display_field)

        # Color row: swatch + button
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

        layout.addLayout(form)

        # Validation hint label — populated by _refresh_validity()
        self._hint_label = QLabel("")
        self._hint_label.setWordWrap(True)
        self._hint_label.setStyleSheet("color: #d97757; font-size: 11px;")
        self._hint_label.setMinimumHeight(18)
        layout.addWidget(self._hint_label)

        layout.addStretch()

        # Buttons — Cancel (exits app via rejection) + Continue
        button_row = QHBoxLayout()
        button_row.addStretch()
        self._cancel_button = QPushButton("Cancel")
        self._continue_button = QPushButton("Continue")
        self._continue_button.setDefault(True)
        button_row.addWidget(self._cancel_button)
        button_row.addWidget(self._continue_button)
        layout.addLayout(button_row)

    def _wire_signals(self) -> None:
        self._username_field.textChanged.connect(self._on_username_changed)
        self._display_field.textChanged.connect(self._refresh_validity)
        self._color_button.clicked.connect(self._on_pick_color)
        self._continue_button.clicked.connect(self._on_continue)
        self._cancel_button.clicked.connect(self.reject)

    # ----------------------------------------------------- Validity helpers

    def _refresh_validity(self) -> None:
        """Enable Continue only when both fields have valid values."""
        sanitized = sanitize_username(self._username_field.text())
        display = self._display_field.text().strip()

        if not sanitized:
            self._hint_label.setText(
                "Username must contain at least one letter or number."
            )
            self._continue_button.setEnabled(False)
            return

        if not display:
            self._hint_label.setText("Display name cannot be empty.")
            self._continue_button.setEnabled(False)
            return

        # Show sanitized username if it differs from input — informs the user
        # that "Alice Chen" will be saved as "alice_chen".
        if sanitized != self._username_field.text():
            self._hint_label.setText(
                f"Username will be saved as: {sanitized}"
            )
            self._hint_label.setStyleSheet(
                "color: #888; font-size: 11px;"
            )
        else:
            self._hint_label.setText("")

        self._continue_button.setEnabled(True)

    def _on_username_changed(self, _text: str) -> None:
        """When the user edits the username, regenerate the auto-color."""
        # Don't override the color if the user already manually picked one.
        # We track that implicitly by remembering whether the current color
        # matches the auto-generated value for the previous username.
        # (Simple heuristic: always re-derive from username unless the user
        # has clicked the color picker; we set a flag in _on_pick_color.)
        if not getattr(self, "_color_manually_picked", False):
            self._color = generate_color_from_name(
                sanitize_username(self._username_field.text())
            )
            self._update_color_swatch()
        self._refresh_validity()

    def _on_pick_color(self) -> None:
        """Open the system color dialog."""
        initial = QColor(self._color)
        chosen = QColorDialog.getColor(
            initial, self, "Pick your identity color"
        )
        if chosen.isValid():
            self._color = chosen.name()
            self._color_manually_picked = True
            self._update_color_swatch()

    def _update_color_swatch(self) -> None:
        self._color_swatch.setStyleSheet(
            f"background-color: {self._color}; border-radius: 4px;"
        )

    # ------------------------------------------------------------ Lifecycle

    def _on_continue(self) -> None:
        """Validate one more time, then accept."""
        sanitized = sanitize_username(self._username_field.text())
        display = self._display_field.text().strip()
        if not sanitized or not display:
            # Should be unreachable since the button is disabled, but defend.
            self._refresh_validity()
            return
        self.accept()

    def get_identity(self) -> Identity:
        """
        Return the identity the user just configured.

        Only valid to call after exec() returned Accepted.
        """
        return Identity(
            name=sanitize_username(self._username_field.text()),
            display_name=self._display_field.text().strip(),
            color=self._color,
        )

    # ---------------------------------------------------- Defaults helpers

    @staticmethod
    def _guess_username() -> str:
        """
        Best-effort guess at a sensible default username.

        Tries getpass.getuser() (cross-platform), then $USER, then a
        hardcoded fallback. Sanitized before returning.
        """
        candidate = ""
        try:
            candidate = getpass.getuser() or ""
        except Exception:
            candidate = os.environ.get("USER", "") or os.environ.get(
                "USERNAME", ""
            )
        sanitized = sanitize_username(candidate)
        return sanitized or "artist"

    @staticmethod
    def _title_case(name: str) -> str:
        """Convert a username into a readable display-name default."""
        if not name:
            return ""
        return " ".join(part.capitalize() for part in name.replace("_", " ").split())


__all__ = ["IdentityWizard"]
