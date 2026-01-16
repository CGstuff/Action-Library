"""
CompactNotesPanel - Simple read-only notes list for compare mode.

Shows notes in a compact format: [f{frame}] {text}
Click on a note to seek to that frame.
"""

from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QHBoxLayout, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont


class CompactNoteItem(QFrame):
    """Single note item in compact format."""

    clicked = pyqtSignal(int)  # Frame number

    def __init__(self, note_data: Dict, parent: QWidget = None):
        super().__init__(parent)
        self._note_data = note_data
        self._frame = note_data.get('frame', 0)

        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self):
        """Build compact note UI."""
        self.setStyleSheet("""
            CompactNoteItem {
                background: #2a2a2a;
                border: none;
                border-radius: 3px;
                padding: 4px;
            }
            CompactNoteItem:hover {
                background: #3a3a3a;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        # Frame badge
        frame_label = QLabel(f"f{self._frame}")
        frame_label.setStyleSheet("""
            background: #404040;
            color: #FF9800;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: bold;
        """)
        frame_label.setFixedWidth(45)
        frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(frame_label)

        # Note text (truncated)
        text = self._note_data.get('note', '')
        if len(text) > 50:
            text = text[:47] + "..."

        text_label = QLabel(text)
        text_label.setStyleSheet("color: #ccc; font-size: 11px;")
        text_label.setWordWrap(False)
        layout.addWidget(text_label, 1)

        # Status indicator if resolved
        if self._note_data.get('resolved'):
            resolved_label = QLabel("✓")
            resolved_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
            resolved_label.setToolTip("Resolved")
            layout.addWidget(resolved_label)

    def mousePressEvent(self, event):
        """Handle click - emit frame number."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._frame)
        super().mousePressEvent(event)


class CompactNotesPanel(QWidget):
    """
    Compact read-only notes panel for compare mode.

    Shows notes for a specific version in a scrollable list.
    Clicking a note emits the frame number for seeking.

    Signals:
        note_clicked(int): Frame number when a note is clicked
    """

    note_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._notes: List[Dict] = []
        self._note_widgets: List[CompactNoteItem] = []

        self._setup_ui()

    def _setup_ui(self):
        """Build panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("Notes")
        header.setStyleSheet("""
            background: #252525;
            color: #888;
            font-size: 10px;
            font-weight: bold;
            padding: 4px 8px;
            text-transform: uppercase;
        """)
        layout.addWidget(header)

        # Scroll area for notes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: #1e1e1e;
                border: none;
            }
            QScrollBar:vertical {
                background: #1e1e1e;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Content widget
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._content_layout.setSpacing(4)
        self._content_layout.addStretch()

        scroll.setWidget(self._content)
        layout.addWidget(scroll, 1)

        # Set max height for compact display
        self.setMaximumHeight(200)
        self.setMinimumHeight(100)

    def set_notes(self, notes: List[Dict]):
        """
        Set the notes to display.

        Args:
            notes: List of note dicts with 'frame', 'note', 'resolved' keys
        """
        self._notes = notes
        self._rebuild_list()

    def _rebuild_list(self):
        """Rebuild the notes list UI."""
        # Clear existing
        for widget in self._note_widgets:
            widget.deleteLater()
        self._note_widgets.clear()

        # Remove stretch
        while self._content_layout.count() > 0:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add notes sorted by frame
        sorted_notes = sorted(
            [n for n in self._notes if not n.get('deleted_at')],
            key=lambda n: n.get('frame', 0)
        )

        for note_data in sorted_notes:
            item = CompactNoteItem(note_data)
            item.clicked.connect(self._on_note_clicked)
            self._content_layout.addWidget(item)
            self._note_widgets.append(item)

        # Add stretch at end
        self._content_layout.addStretch()

        # Show empty state if no notes
        if not sorted_notes:
            empty_label = QLabel("No notes")
            empty_label.setStyleSheet("color: #555; font-size: 11px; padding: 12px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.insertWidget(0, empty_label)

    def _on_note_clicked(self, frame: int):
        """Handle note click."""
        self.note_clicked.emit(frame)

    def clear(self):
        """Clear all notes."""
        self._notes = []
        self._rebuild_list()

    @property
    def note_count(self) -> int:
        """Get number of notes (excluding deleted)."""
        return len([n for n in self._notes if not n.get('deleted_at')])
