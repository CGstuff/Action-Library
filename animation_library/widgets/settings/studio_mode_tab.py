"""
OperationModeTab - Settings tab for Solo/Studio/Pipeline mode switching.

Operation Modes:
- Solo: No restrictions, simple workflow for individual use
- Studio: Soft delete with restore, persistent review notes, audit logging
- Pipeline: Controlled by Pipeline Control app — local status changes blocked

NOTE (Option B Phase 3): user roster + role UI was removed from this tab.
Identity is per-machine (see services/identity.py + Config.load_identity());
the shared notes-DB users table still exists for legacy data but is no
longer surfaced or managed here. Permissions UI was a derivative of the
role system and is also gone — Phase 4 deletes the permissions module
entirely. What remains: the three mode radios + Pipeline indicator.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QGroupBox, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import pyqtSignal

from ...services.notes_database import get_notes_database


class StudioModeTab(QWidget):
    """Settings tab for Solo/Studio/Pipeline mode configuration."""

    mode_changed = pyqtSignal(str)  # 'solo', 'studio', or 'pipeline'

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._notes_db = get_notes_database()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        # Sharp styling for the tab — matches the rest of the settings UI.
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
            QRadioButton {
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 0px;
            }
            QRadioButton::indicator:unchecked {
                background-color: #2a2a2a;
                border: 1px solid #555;
            }
            QRadioButton::indicator:checked {
                background-color: #3A8FB7;
                border: 1px solid #3A8FB7;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Mode selection group
        mode_group = QGroupBox("Operation Mode")
        mode_layout = QVBoxLayout(mode_group)

        self._mode_btn_group = QButtonGroup(self)

        # Solo mode option
        self._solo_radio = QRadioButton("Solo Mode (Single User)")
        self._solo_radio.setStyleSheet("font-weight: bold; font-size: 12px;")
        mode_layout.addWidget(self._solo_radio)

        solo_desc = QLabel("No restrictions. Simple workflow for individual use.")
        solo_desc.setStyleSheet("color: #888; margin-left: 22px; margin-bottom: 12px; font-size: 11px;")
        mode_layout.addWidget(solo_desc)

        # Studio mode option
        self._studio_radio = QRadioButton("Studio Mode (Multi-User)")
        self._studio_radio.setStyleSheet("font-weight: bold; font-size: 12px;")
        mode_layout.addWidget(self._studio_radio)

        studio_desc = QLabel("Soft delete with restore. Persistent review notes. Audit logging.")
        studio_desc.setStyleSheet("color: #888; margin-left: 22px; margin-bottom: 12px; font-size: 11px;")
        mode_layout.addWidget(studio_desc)

        # Pipeline mode option
        self._pipeline_radio = QRadioButton("Pipeline Mode (Pipeline Control)")
        self._pipeline_radio.setStyleSheet("font-weight: bold; font-size: 12px;")
        mode_layout.addWidget(self._pipeline_radio)

        pipeline_desc = QLabel("Status controlled by Pipeline Control. Local status changes disabled.")
        pipeline_desc.setStyleSheet("color: #888; margin-left: 22px; margin-bottom: 8px; font-size: 11px;")
        mode_layout.addWidget(pipeline_desc)

        # Pipeline mode indicator
        self._pipeline_indicator = QLabel("Pipeline Control is the maestro for this library.")
        self._pipeline_indicator.setStyleSheet("""
            color: #FF9800;
            margin-left: 22px;
            font-size: 11px;
            font-style: italic;
        """)
        self._pipeline_indicator.setVisible(False)
        mode_layout.addWidget(self._pipeline_indicator)

        self._mode_btn_group.addButton(self._solo_radio, 0)
        self._mode_btn_group.addButton(self._studio_radio, 1)
        self._mode_btn_group.addButton(self._pipeline_radio, 2)
        self._mode_btn_group.idToggled.connect(self._on_mode_changed)

        layout.addWidget(mode_group)

        layout.addStretch()

    def _load_settings(self):
        """Load current operation mode from the shared notes DB."""
        mode = self._notes_db.get_operation_mode()

        if mode == 'pipeline':
            self._pipeline_radio.setChecked(True)
        elif mode == 'studio':
            self._studio_radio.setChecked(True)
        else:
            self._solo_radio.setChecked(True)

        self._update_ui_visibility()

    def _update_ui_visibility(self):
        """Update visibility based on mode."""
        # Pipeline indicator only visible in pipeline mode.
        self._pipeline_indicator.setVisible(self._pipeline_radio.isChecked())

    def _on_mode_changed(self, button_id: int, checked: bool):
        """Handle mode radio button change."""
        if checked:
            self._update_ui_visibility()

    def save_settings(self):
        """Persist the selected operation mode."""
        if self._pipeline_radio.isChecked():
            mode = 'pipeline'
        elif self._studio_radio.isChecked():
            mode = 'studio'
        else:
            mode = 'solo'

        # Operation mode is INTENTIONALLY shared (Pipeline Control reads it
        # from the notes DB to detect AL's mode). It's the only setting in
        # this tab; per-machine identity now lives in identity.json.
        self._notes_db.set_setting('app_mode', mode)

        from ...config import Config
        Config.set_operation_mode(mode)

        # Emit signal for any listeners
        self.mode_changed.emit(mode)

        # Emit via event bus for app-wide notification
        from ...events.event_bus import get_event_bus
        get_event_bus().operation_mode_changed.emit(mode)


__all__ = ['StudioModeTab']
