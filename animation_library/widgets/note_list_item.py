"""
NoteListItem - Inline collapsible note widget for review panel

Features:
- Collapsed: Shows frame badge + truncated note
- Expanded: Full note + action buttons
- Click to expand/collapse
- Click timestamp to seek video
- Visual indicator for resolved status
"""

from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QWidget, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from ..config import Config


class NoteListItem(QFrame):
    """
    Inline collapsible note widget for the review notes panel.

    Signals:
        timestamp_clicked(int): Frame number clicked - seek video
        resolve_toggled(int, bool): Note ID, new resolved state
        edit_requested(int, str): Note ID, current text - open edit
        delete_requested(int): Note ID - confirm delete
        expanded_changed(int, bool): Note ID, is expanded
    """

    # Signals
    timestamp_clicked = pyqtSignal(int)  # frame
    resolve_toggled = pyqtSignal(int, bool)  # note_id, new_resolved
    edit_requested = pyqtSignal(int, str)  # note_id, current_text
    delete_requested = pyqtSignal(int)  # note_id
    expanded_changed = pyqtSignal(int, bool)  # note_id, is_expanded

    def __init__(self, note_data: Dict, fps: int = 24, parent: QWidget = None):
        super().__init__(parent)

        self._note_data = note_data
        self._fps = fps
        self._expanded = False
        self._editing = False

        self._setup_ui()
        self._apply_styling()
        self._update_display()

    def _setup_ui(self):
        """Build the widget UI."""
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Main layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Header row (always visible) - clickable to expand
        self._header = QWidget()
        self._header.setFixedHeight(32)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        # Status indicator (dot)
        self._status_dot = QLabel()
        self._status_dot.setFixedSize(8, 8)
        header_layout.addWidget(self._status_dot)

        # Frame badge
        self._frame_badge = QPushButton()
        self._frame_badge.setFixedHeight(22)
        self._frame_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._frame_badge.clicked.connect(self._on_timestamp_click)
        header_layout.addWidget(self._frame_badge)

        # Note preview (truncated)
        self._preview_label = QLabel()
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )
        header_layout.addWidget(self._preview_label)

        self._main_layout.addWidget(self._header)

        # Expanded content (hidden by default)
        self._expanded_content = QWidget()
        expanded_layout = QVBoxLayout(self._expanded_content)
        expanded_layout.setContentsMargins(24, 8, 8, 12)
        expanded_layout.setSpacing(8)

        # Full note text (read mode)
        self._note_label = QLabel()
        self._note_label.setWordWrap(True)
        self._note_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        expanded_layout.addWidget(self._note_label)

        # Edit text area (edit mode)
        self._edit_area = QTextEdit()
        self._edit_area.setMaximumHeight(80)
        self._edit_area.setPlaceholderText("Enter note...")
        self._edit_area.hide()
        expanded_layout.addWidget(self._edit_area)

        # Action buttons row
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 4, 0, 0)
        buttons_layout.setSpacing(6)

        # Resolve button
        self._resolve_btn = QPushButton("Resolve")
        self._resolve_btn.setFixedHeight(26)
        self._resolve_btn.clicked.connect(self._on_resolve_click)
        buttons_layout.addWidget(self._resolve_btn)

        # Edit button
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setFixedHeight(26)
        self._edit_btn.clicked.connect(self._on_edit_click)
        buttons_layout.addWidget(self._edit_btn)

        # Save button (edit mode)
        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedHeight(26)
        self._save_btn.clicked.connect(self._on_save_click)
        self._save_btn.hide()
        buttons_layout.addWidget(self._save_btn)

        # Cancel button (edit mode)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedHeight(26)
        self._cancel_btn.clicked.connect(self._on_cancel_click)
        self._cancel_btn.hide()
        buttons_layout.addWidget(self._cancel_btn)

        # Delete button
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setFixedHeight(26)
        self._delete_btn.clicked.connect(self._on_delete_click)
        buttons_layout.addWidget(self._delete_btn)

        buttons_layout.addStretch()

        expanded_layout.addWidget(buttons_widget)

        self._expanded_content.hide()
        self._main_layout.addWidget(self._expanded_content)

    def _apply_styling(self):
        """Apply visual styling based on state."""
        resolved = self._note_data.get('resolved', False)

        # Status dot color
        if resolved:
            dot_color = "#4CAF50"  # Green
            self._status_dot.setStyleSheet(f"""
                QLabel {{
                    background-color: {dot_color};
                    border-radius: 4px;
                    opacity: 0.6;
                }}
            """)
        else:
            dot_color = "#FF9800"  # Orange
            self._status_dot.setStyleSheet(f"""
                QLabel {{
                    background-color: {dot_color};
                    border-radius: 4px;
                }}
            """)

        # Frame badge styling
        if resolved:
            self._frame_badge.setStyleSheet("""
                QPushButton {
                    background-color: rgba(76, 175, 80, 0.2);
                    border: 1px solid rgba(76, 175, 80, 0.4);
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-family: monospace;
                    font-weight: bold;
                    color: #8BC34A;
                }
                QPushButton:hover {
                    background-color: rgba(76, 175, 80, 0.4);
                    border: 1px solid rgba(76, 175, 80, 0.6);
                }
            """)
        else:
            self._frame_badge.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 152, 0, 0.2);
                    border: 1px solid rgba(255, 152, 0, 0.4);
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-family: monospace;
                    font-weight: bold;
                    color: #FFB74D;
                }
                QPushButton:hover {
                    background-color: rgba(255, 152, 0, 0.4);
                    border: 1px solid rgba(255, 152, 0, 0.6);
                }
            """)

        # Preview label styling
        preview_color = "#888" if resolved else "#ccc"
        self._preview_label.setStyleSheet(f"""
            QLabel {{
                color: {preview_color};
                font-size: 12px;
            }}
        """)

        # Note label styling
        self._note_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
                line-height: 1.4;
            }
        """)

        # Button styling
        btn_style = """
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #505050;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """
        self._resolve_btn.setStyleSheet(btn_style)
        self._edit_btn.setStyleSheet(btn_style)
        self._save_btn.setStyleSheet(btn_style)
        self._cancel_btn.setStyleSheet(btn_style)

        # Delete button - slightly red
        self._delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a3a3a;
                color: #e0e0e0;
                border: 1px solid #5a4a4a;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a4a4a;
            }
        """)

        # Update resolve button text
        if resolved:
            self._resolve_btn.setText("Unresolve")
        else:
            self._resolve_btn.setText("Resolve")

        # Frame styling for expanded state
        if self._expanded:
            self.setStyleSheet("""
                NoteListItem {
                    background-color: rgba(255, 255, 255, 0.03);
                    border-left: 2px solid #3A8FB7;
                }
            """)
        else:
            self.setStyleSheet("""
                NoteListItem {
                    background-color: transparent;
                    border-left: 2px solid transparent;
                }
                NoteListItem:hover {
                    background-color: rgba(255, 255, 255, 0.02);
                }
            """)

    def _update_display(self):
        """Update displayed content."""
        frame = self._note_data.get('frame', 0)
        note = self._note_data.get('note', '')

        # Update frame badge
        timestamp_str = Config.format_frame_timestamp(frame, self._fps)
        self._frame_badge.setText(timestamp_str)

        # Update preview (truncated)
        max_preview = 50
        if len(note) > max_preview:
            preview = note[:max_preview].replace('\n', ' ') + "..."
        else:
            preview = note.replace('\n', ' ')
        self._preview_label.setText(preview)

        # Update full note
        self._note_label.setText(note)

        # Show/hide expanded content
        self._expanded_content.setVisible(self._expanded)
        self._preview_label.setVisible(not self._expanded)

    def mousePressEvent(self, event):
        """Handle click to expand/collapse."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Don't toggle if clicking on buttons
            if not self._is_click_on_buttons(event.pos()):
                self.toggle_expanded()
        super().mousePressEvent(event)

    def _is_click_on_buttons(self, pos) -> bool:
        """Check if click is on interactive elements."""
        # Check if click is within the frame badge
        badge_rect = self._frame_badge.geometry()
        header_rect = self._header.geometry()

        # Adjust for header offset
        adjusted_pos = pos - header_rect.topLeft()

        if badge_rect.contains(adjusted_pos):
            return True

        # Check if click is in expanded content area
        if self._expanded and self._expanded_content.geometry().contains(pos):
            return True

        return False

    def toggle_expanded(self):
        """Toggle expanded/collapsed state."""
        self._expanded = not self._expanded
        self._apply_styling()
        self._update_display()
        self.expanded_changed.emit(self.get_note_id(), self._expanded)

    def set_expanded(self, expanded: bool):
        """Set expanded state."""
        if self._expanded != expanded:
            self._expanded = expanded
            self._apply_styling()
            self._update_display()

    def is_expanded(self) -> bool:
        """Check if currently expanded."""
        return self._expanded

    def get_note_id(self) -> int:
        """Get the note ID."""
        return self._note_data.get('id', -1)

    def get_frame(self) -> int:
        """Get the frame number."""
        return self._note_data.get('frame', 0)

    def update_note_data(self, note_data: Dict):
        """Update note data and refresh display."""
        self._note_data = note_data
        self._apply_styling()
        self._update_display()

    def _on_timestamp_click(self):
        """Handle timestamp badge click."""
        self.timestamp_clicked.emit(self.get_frame())

    def _on_resolve_click(self):
        """Handle resolve button click."""
        current = self._note_data.get('resolved', False)
        self.resolve_toggled.emit(self.get_note_id(), not current)

    def _on_edit_click(self):
        """Enter edit mode."""
        self._editing = True
        self._edit_area.setText(self._note_data.get('note', ''))
        self._note_label.hide()
        self._edit_area.show()
        self._resolve_btn.hide()
        self._edit_btn.hide()
        self._delete_btn.hide()
        self._save_btn.show()
        self._cancel_btn.show()
        self._edit_area.setFocus()

    def _on_save_click(self):
        """Save edited note."""
        new_text = self._edit_area.toPlainText().strip()
        if new_text:
            self.edit_requested.emit(self.get_note_id(), new_text)
        self._exit_edit_mode()

    def _on_cancel_click(self):
        """Cancel editing."""
        self._exit_edit_mode()

    def _exit_edit_mode(self):
        """Exit edit mode."""
        self._editing = False
        self._edit_area.hide()
        self._note_label.show()
        self._save_btn.hide()
        self._cancel_btn.hide()
        self._resolve_btn.show()
        self._edit_btn.show()
        self._delete_btn.show()

    def _on_delete_click(self):
        """Handle delete button click."""
        self.delete_requested.emit(self.get_note_id())


__all__ = ['NoteListItem']
