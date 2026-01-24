"""
Review Notes Panel Widget

Panel for displaying and managing frame-specific review notes (text comments).

Features:
- Note list with NoteItemWidget items
- Add note input
- Show/hide deleted notes toggle
- Note count display
- Permission-based features

Signals:
- note_clicked(int): frame number clicked
- note_added(int, str): frame, note text
- note_resolved(int, bool): note_id, resolved
- note_deleted(int): note_id
- note_restored(int): note_id
- note_edited(int, str): note_id, new_text
"""

from typing import Optional, List, Dict
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame,
    QLabel, QLineEdit, QScrollArea, QCheckBox, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QKeyEvent

from ..config import Config
from ..services.permissions import NotePermissions
from ..utils.icon_loader import IconLoader
from ..utils.icon_utils import colorize_white_svg


class NoteItemWidget(QFrame):
    """
    Single note item in the notes panel.

    Supports:
    - Author/role badges in Studio Mode
    - Permission-based button visibility
    - Deleted note display with restore button
    """

    clicked = pyqtSignal(int)  # frame
    resolve_toggled = pyqtSignal(int, bool)  # note_id, new_resolved
    delete_requested = pyqtSignal(int)  # note_id
    restore_requested = pyqtSignal(int)  # note_id
    edit_saved = pyqtSignal(int, str)  # note_id, new_text

    def __init__(
        self,
        note_data: Dict,
        fps: int = 24,
        is_studio_mode: bool = False,
        current_user: str = '',
        current_user_role: str = 'artist',
        marker_index: int = 0,
        parent=None
    ):
        super().__init__(parent)
        self._note_data = note_data
        self._fps = fps
        self._is_studio_mode = is_studio_mode
        self._current_user = current_user
        self._current_user_role = current_user_role
        self._marker_index = marker_index
        self._editing = False
        self._is_deleted = note_data.get('deleted', 0) == 1
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header row with timestamp
        header = QHBoxLayout()
        header.setSpacing(8)

        frame = self._note_data.get('frame', 0)
        resolved = self._note_data.get('resolved', False)
        author = self._note_data.get('author', '')
        author_role = self._note_data.get('author_role', 'artist')

        # Timestamp button
        timestamp = Config.format_frame_timestamp(frame, self._fps)
        self._timestamp_btn = QPushButton(timestamp)
        self._timestamp_btn.setFixedHeight(24)
        self._timestamp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timestamp_btn.clicked.connect(lambda: self.clicked.emit(frame))

        # Style based on state
        if self._is_deleted:
            self._timestamp_btn.setStyleSheet(self._get_deleted_timestamp_style())
        elif resolved:
            self._timestamp_btn.setStyleSheet(self._get_resolved_timestamp_style())
        else:
            self._timestamp_btn.setStyleSheet(self._get_active_timestamp_style())
        header.addWidget(self._timestamp_btn)

        # Marker index badge (matches timeline markers)
        if self._marker_index > 0:
            marker_badge = QLabel(str(self._marker_index))
            marker_badge.setFixedSize(20, 20)
            marker_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            marker_badge.setStyleSheet("""
                QLabel {
                    background-color: #FF9800;
                    color: white;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 10px;
                }
            """)
            marker_badge.setToolTip(f"Timeline marker {self._marker_index}")
            header.addWidget(marker_badge)

        # Author role badge (Studio Mode only, elevated roles)
        if self._is_studio_mode and author_role and NotePermissions.is_elevated_role(author_role):
            role_label = NotePermissions.get_role_label(author_role)
            role_color = NotePermissions.get_role_color(author_role)
            role_badge = QLabel(role_label.upper())
            role_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {role_color};
                    color: white;
                    font-size: 9px;
                    font-weight: bold;
                    padding: 2px 6px;
                    border-radius: 0px;
                }}
            """)
            header.addWidget(role_badge)

        # Author name (Studio Mode only)
        if self._is_studio_mode and author:
            author_label = QLabel(author)
            author_label.setStyleSheet("color: #888; font-size: 11px;")
            header.addWidget(author_label)

        header.addStretch()

        # Action buttons
        self._add_action_buttons(header, resolved, author)

        layout.addLayout(header)

        # Note text
        note_text = self._note_data.get('note', '')
        self._note_label = QLabel(note_text)
        self._note_label.setWordWrap(True)
        self._note_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._note_label.setMinimumWidth(50)

        if self._is_deleted:
            self._note_label.setStyleSheet("""
                QLabel { color: #555; font-size: 12px; padding: 4px 0; text-decoration: line-through; }
            """)
        else:
            self._note_label.setStyleSheet("""
                QLabel { color: #e0e0e0; font-size: 12px; padding: 4px 0; }
            """)
        layout.addWidget(self._note_label)

        # Deleted info
        if self._is_deleted:
            deleted_by = self._note_data.get('deleted_by', 'Unknown')
            deleted_at = self._note_data.get('deleted_at', '')
            if deleted_at:
                try:
                    dt = datetime.fromisoformat(deleted_at.replace('Z', '+00:00'))
                    deleted_at = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    pass

            deleted_info = QLabel(f"Deleted by {deleted_by}" + (f" on {deleted_at}" if deleted_at else ""))
            deleted_info.setStyleSheet("color: #555; font-size: 10px; font-style: italic;")
            layout.addWidget(deleted_info)

        # Edit container (hidden by default)
        if not self._is_deleted:
            self._edit_container = QWidget()
            edit_layout = QVBoxLayout(self._edit_container)
            edit_layout.setContentsMargins(0, 0, 0, 0)
            edit_layout.setSpacing(4)

            self._edit_input = QTextEdit()
            self._edit_input.setFixedHeight(60)
            self._edit_input.setStyleSheet("""
                QTextEdit {
                    background-color: #2a2a2a;
                    border: 1px solid #3A8FB7;
                    border-radius: 0px;
                    padding: 6px 8px;
                    color: #e0e0e0;
                    font-size: 12px;
                }
            """)
            edit_layout.addWidget(self._edit_input)

            # Edit buttons row
            edit_btn_row = QHBoxLayout()
            edit_btn_row.setSpacing(4)
            edit_btn_row.addStretch()

            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedHeight(24)
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    border: 1px solid #555;
                    border-radius: 0px;
                    color: #aaa;
                    padding: 4px 12px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #4a4a4a; }
            """)
            cancel_btn.clicked.connect(self._on_cancel_edit)
            edit_btn_row.addWidget(cancel_btn)

            save_btn = QPushButton("Save")
            save_btn.setFixedHeight(24)
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3A8FB7;
                    border: none;
                    border-radius: 0px;
                    color: white;
                    padding: 4px 12px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #4A9FC7; }
            """)
            save_btn.clicked.connect(self._on_save_edit)
            edit_btn_row.addWidget(save_btn)

            edit_layout.addLayout(edit_btn_row)
            self._edit_container.hide()
            layout.addWidget(self._edit_container)

            # Double-click to edit
            can_edit = NotePermissions.can_edit_note(
                self._is_studio_mode,
                self._current_user_role,
                self._note_data.get('author', ''),
                self._current_user
            )
            if can_edit:
                self._note_label.mouseDoubleClickEvent = self._start_edit
        else:
            self._edit_container = None
            self._edit_input = None

        # Frame styling
        if self._is_deleted:
            self.setStyleSheet("""
                NoteItemWidget { background-color: #1e1e1e; border: 1px dashed #333; border-radius: 0px; }
            """)
        else:
            self.setStyleSheet("""
                NoteItemWidget { background-color: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 0px; }
                NoteItemWidget:hover { background-color: #303030; border-color: #4a4a4a; }
            """)

    def _add_action_buttons(self, header, resolved: bool, author: str):
        """Add resolve/delete/restore buttons based on permissions."""
        btn_style = """
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 0px;
                color: #888;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #4a4a4a; color: #aaa; }
        """

        # Resolve button (not for deleted notes)
        if not self._is_deleted:
            self._resolve_btn = QPushButton()
            self._resolve_btn.setFixedSize(24, 24)
            self._resolve_btn.setToolTip("Mark as resolved" if not resolved else "Mark as unresolved")
            self._resolve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._resolve_btn.clicked.connect(self._on_resolve_toggle)

            # Use approve icon
            approve_icon = IconLoader.get("approve")
            if resolved:
                self._resolve_btn.setIcon(colorize_white_svg(approve_icon, "#8BC34A"))
                self._resolve_btn.setIconSize(QSize(14, 14))
                self._resolve_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4a6a4a; border: 1px solid #5a7a5a;
                        border-radius: 0px;
                    }
                    QPushButton:hover { background-color: #5a7a5a; }
                """)
            else:
                self._resolve_btn.setIcon(colorize_white_svg(approve_icon, "#888"))
                self._resolve_btn.setIconSize(QSize(14, 14))
                self._resolve_btn.setStyleSheet(btn_style)
            header.addWidget(self._resolve_btn)

        # Delete button
        if not self._is_deleted:
            can_delete = NotePermissions.can_delete_note(
                self._is_studio_mode,
                self._current_user_role,
                author,
                self._current_user
            )
            if can_delete:
                self._delete_btn = QPushButton()
                self._delete_btn.setFixedSize(24, 24)
                self._delete_btn.setToolTip("Delete note")
                self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self._delete_btn.clicked.connect(self._on_delete)
                # Use delete icon
                delete_icon = IconLoader.get("delete")
                self._delete_btn.setIcon(colorize_white_svg(delete_icon, "#888"))
                self._delete_btn.setIconSize(QSize(14, 14))
                self._delete_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3a3a3a; border: 1px solid #555;
                        border-radius: 0px;
                    }
                    QPushButton:hover { background-color: #4a3535; border-color: #aa5555; }
                """)
                header.addWidget(self._delete_btn)

        # Restore button (deleted notes only)
        if self._is_deleted:
            can_restore = NotePermissions.can_restore_note(
                self._is_studio_mode,
                self._current_user_role
            )
            if can_restore:
                restore_btn = QPushButton("Restore")
                restore_btn.setFixedHeight(24)
                restore_btn.setToolTip("Restore this deleted note")
                restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                restore_btn.clicked.connect(self._on_restore)
                restore_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3a4a3a; border: 1px solid #4a6a4a;
                        border-radius: 0px; color: #8BC34A; font-size: 11px; padding: 2px 12px;
                    }
                    QPushButton:hover { background-color: #4a5a4a; }
                """)
                header.addWidget(restore_btn)

    def _get_deleted_timestamp_style(self) -> str:
        return """
            QPushButton {
                background-color: #2a2a2a; border: 1px solid #404040; border-radius: 0px;
                padding: 2px 10px; font-size: 11px; font-family: monospace; font-weight: bold; color: #666;
            }
            QPushButton:hover { background-color: #333; }
        """

    def _get_resolved_timestamp_style(self) -> str:
        return """
            QPushButton {
                background-color: #2d3d2d; border: 1px solid #4a6a4a; border-radius: 0px;
                padding: 2px 10px; font-size: 11px; font-family: monospace; font-weight: bold; color: #8BC34A;
            }
            QPushButton:hover { background-color: #3a4a3a; }
        """

    def _get_active_timestamp_style(self) -> str:
        return """
            QPushButton {
                background-color: #3d3528; border: 1px solid #5a4a30; border-radius: 0px;
                padding: 2px 10px; font-size: 11px; font-family: monospace; font-weight: bold; color: #FFB74D;
            }
            QPushButton:hover { background-color: #4a4030; }
        """

    def _on_resolve_toggle(self):
        note_id = self._note_data.get('id', -1)
        current = self._note_data.get('resolved', False)
        self.resolve_toggled.emit(note_id, not current)

    def _on_delete(self):
        note_id = self._note_data.get('id', -1)
        self.delete_requested.emit(note_id)

    def _on_restore(self):
        note_id = self._note_data.get('id', -1)
        self.restore_requested.emit(note_id)

    def _start_edit(self, event):
        if self._edit_container is None:
            return
        self._editing = True
        self._edit_input.setPlainText(self._note_data.get('note', ''))
        self._note_label.hide()
        self._edit_container.show()
        self._edit_input.setFocus()
        # Select all text
        cursor = self._edit_input.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self._edit_input.setTextCursor(cursor)

    def _on_save_edit(self):
        if self._edit_container is None:
            return
        new_text = self._edit_input.toPlainText().strip()
        if new_text and new_text != self._note_data.get('note', ''):
            note_id = self._note_data.get('id', -1)
            self.edit_saved.emit(note_id, new_text)

        self._editing = False
        self._edit_container.hide()
        self._note_label.show()

    def _on_cancel_edit(self):
        if self._edit_container is None:
            return
        self._editing = False
        self._edit_container.hide()
        self._note_label.show()

    def get_note_id(self) -> int:
        return self._note_data.get('id', -1)

    def get_frame(self) -> int:
        return self._note_data.get('frame', 0)

    def is_deleted(self) -> bool:
        return self._is_deleted


class ReviewNotesPanel(QWidget):
    """
    Panel for displaying and managing review notes.

    Signals:
        note_clicked(int): frame number
        note_added(int, str): frame, text
        note_resolved(int, bool): note_id, resolved
        note_deleted(int): note_id
        note_restored(int): note_id
        note_edited(int, str): note_id, new_text
    """

    note_clicked = pyqtSignal(int)
    note_added = pyqtSignal(int, str)
    note_resolved = pyqtSignal(int, bool)
    note_deleted = pyqtSignal(int)
    note_restored = pyqtSignal(int)
    note_edited = pyqtSignal(int, str)

    def __init__(
        self,
        fps: int = 24,
        is_studio_mode: bool = False,
        current_user: str = '',
        current_user_role: str = 'artist',
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._fps = fps
        self._is_studio_mode = is_studio_mode
        self._current_user = current_user
        self._current_user_role = current_user_role
        self._current_frame = 0
        self._notes: List[Dict] = []
        self._note_widgets: List[NoteItemWidget] = []

        self._setup_ui()

    def _setup_ui(self):
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background: #252525;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Review Notes")
        title.setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: bold;")
        header_layout.addWidget(title)

        self._count_label = QLabel("(0)")
        self._count_label.setStyleSheet("color: #888; font-size: 12px;")
        header_layout.addWidget(self._count_label)

        header_layout.addStretch()

        # Show deleted checkbox (elevated roles in Studio Mode)
        if self._is_studio_mode and NotePermissions.can_view_deleted(
            self._is_studio_mode, self._current_user_role
        ):
            self._show_deleted_cb = QCheckBox("Show deleted")
            self._show_deleted_cb.setStyleSheet("color: #888; font-size: 11px;")
            self._show_deleted_cb.toggled.connect(self._on_show_deleted_toggled)
            header_layout.addWidget(self._show_deleted_cb)
        else:
            self._show_deleted_cb = None

        layout.addWidget(header)

        # Notes scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: #1e1e1e; }
            QScrollBar:vertical {
                background: #252525; width: 8px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #3a3a3a; min-height: 20px; border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._notes_container = QWidget()
        self._notes_layout = QVBoxLayout(self._notes_container)
        self._notes_layout.setContentsMargins(8, 8, 8, 8)
        self._notes_layout.setSpacing(8)
        self._notes_layout.addStretch()

        scroll.setWidget(self._notes_container)
        layout.addWidget(scroll, 1)

        # Add note section
        add_section = QWidget()
        add_section.setStyleSheet("background: #252525;")
        add_layout = QHBoxLayout(add_section)
        add_layout.setContentsMargins(8, 8, 8, 8)
        add_layout.setSpacing(8)

        self._note_input = QTextEdit()
        self._note_input.setPlaceholderText("Add note at current frame... (Enter for new line)")
        self._note_input.setFixedHeight(60)
        self._note_input.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 0px;
                padding: 8px;
                color: #e0e0e0;
                font-size: 12px;
            }
            QTextEdit:focus { border-color: #FF5722; }
        """)
        add_layout.addWidget(self._note_input)

        # Add button with confirm icon
        add_btn = QPushButton()
        add_btn.setFixedSize(36, 60)
        add_btn.setToolTip("Add note (Ctrl+Enter)")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                border: none;
                border-radius: 0px;
            }
            QPushButton:hover { background-color: #FF7043; }
        """)
        # Add confirm/checkmark icon
        confirm_icon = IconLoader.get("approve")
        add_btn.setIcon(colorize_white_svg(confirm_icon, "#ffffff"))
        add_btn.setIconSize(QSize(20, 20))
        add_btn.clicked.connect(self._on_add_note)
        add_layout.addWidget(add_btn)

        layout.addWidget(add_section)

    def _on_add_note(self):
        """Handle add note button."""
        text = self._note_input.toPlainText().strip()
        if text:
            self.note_added.emit(self._current_frame, text)
            self._note_input.clear()

    def _on_show_deleted_toggled(self, checked: bool):
        """Handle show deleted checkbox toggle."""
        self._rebuild_notes_list()

    def _rebuild_notes_list(self):
        """Rebuild the notes list UI."""
        # Clear existing widgets
        for widget in self._note_widgets:
            widget.deleteLater()
        self._note_widgets.clear()

        # Remove stretch
        while self._notes_layout.count() > 0:
            item = self._notes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Filter notes
        show_deleted = self._show_deleted_cb and self._show_deleted_cb.isChecked()
        visible_notes = [
            n for n in self._notes
            if show_deleted or n.get('deleted', 0) != 1
        ]

        # Sort by frame
        visible_notes.sort(key=lambda n: n.get('frame', 0))

        # Build frame-to-marker-index mapping (1-based, only for non-deleted notes)
        active_frames = sorted(set(
            n.get('frame', 0) for n in visible_notes if n.get('deleted', 0) != 1
        ))
        frame_to_marker = {frame: idx + 1 for idx, frame in enumerate(active_frames)}

        # Create widgets
        for note_data in visible_notes:
            # Get marker index (0 if deleted, otherwise 1-based index)
            frame = note_data.get('frame', 0)
            is_deleted = note_data.get('deleted', 0) == 1
            marker_index = 0 if is_deleted else frame_to_marker.get(frame, 0)

            widget = NoteItemWidget(
                note_data,
                fps=self._fps,
                is_studio_mode=self._is_studio_mode,
                current_user=self._current_user,
                current_user_role=self._current_user_role,
                marker_index=marker_index
            )
            widget.clicked.connect(self.note_clicked.emit)
            widget.resolve_toggled.connect(self.note_resolved.emit)
            widget.delete_requested.connect(self.note_deleted.emit)
            widget.restore_requested.connect(self.note_restored.emit)
            widget.edit_saved.connect(self.note_edited.emit)

            self._notes_layout.addWidget(widget)
            self._note_widgets.append(widget)

        self._notes_layout.addStretch()

        # Update count
        active_count = len([n for n in self._notes if n.get('deleted', 0) != 1])
        self._count_label.setText(f"({active_count})")

    # ==================== PUBLIC API ====================

    def set_notes(self, notes: List[Dict]):
        """Set the list of notes to display."""
        self._notes = notes
        self._rebuild_notes_list()

    def clear(self):
        """Clear all notes."""
        self._notes = []
        self._rebuild_notes_list()

    def set_current_frame(self, frame: int):
        """Set the current frame for new notes."""
        self._current_frame = frame

    def set_fps(self, fps: int):
        """Set frames per second for timestamp display."""
        self._fps = fps

    def set_studio_mode(self, enabled: bool, user: str = '', role: str = 'artist'):
        """Update studio mode settings."""
        self._is_studio_mode = enabled
        self._current_user = user
        self._current_user_role = role
        self._rebuild_notes_list()

    def get_note_count(self) -> int:
        """Get count of active (non-deleted) notes."""
        return len([n for n in self._notes if n.get('deleted', 0) != 1])
