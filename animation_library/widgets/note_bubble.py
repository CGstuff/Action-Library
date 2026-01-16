"""
NoteBubble - Speech bubble overlay for review notes

Appears on the video preview when clicking a note marker.
Positioned at the bottom of the video with a pointer.
"""

from typing import Dict, Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPolygon

from ..config import Config


class NoteBubble(QFrame):
    """
    Speech bubble overlay that appears on the video preview.

    Shows note content with action buttons.
    Has a pointer at the bottom pointing to the timeline.

    Signals:
        resolve_clicked(int): Note ID
        edit_clicked(int): Note ID
        delete_clicked(int): Note ID
        closed(): Bubble was closed
    """

    resolve_clicked = pyqtSignal(int)
    edit_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)
    closed = pyqtSignal()

    POINTER_HEIGHT = 10
    POINTER_WIDTH = 16
    BORDER_RADIUS = 8

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self._note_data: Optional[Dict] = None
        self._note_id: int = -1
        self._fps: int = 24

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        """Build the bubble UI."""
        self.setFixedWidth(320)
        self.setStyleSheet("""
            NoteBubble {
                background-color: #2a2a2a;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
            }
        """)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 14)
        layout.setSpacing(8)

        # Header row with timestamp and close button
        header = QHBoxLayout()
        header.setSpacing(8)

        self._timestamp_label = QLabel("f0")
        self._timestamp_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                font-family: monospace;
                color: #FFB74D;
                background: transparent;
            }
        """)
        header.addWidget(self._timestamp_label)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #888;
                background: transparent;
            }
        """)
        header.addWidget(self._status_label)

        header.addStretch()

        close_btn = QPushButton("x")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #888;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #fff;
            }
        """)
        close_btn.clicked.connect(self._on_close)
        header.addWidget(close_btn)

        layout.addLayout(header)

        # Note text
        self._note_label = QLabel("")
        self._note_label.setWordWrap(True)
        self._note_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #e0e0e0;
                line-height: 1.4;
                background: transparent;
            }
        """)
        layout.addWidget(self._note_label)

        # Action buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(6)

        self._resolve_btn = QPushButton("Resolve")
        self._resolve_btn.setFixedHeight(26)
        self._resolve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._resolve_btn.clicked.connect(self._on_resolve)
        buttons.addWidget(self._resolve_btn)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setFixedHeight(26)
        self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_btn.clicked.connect(self._on_edit)
        buttons.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setFixedHeight(26)
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete)
        buttons.addWidget(self._delete_btn)

        buttons.addStretch()

        layout.addLayout(buttons)

        # Style buttons
        btn_style = """
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #505050;
                border-radius: 4px;
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
        self._delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a3535;
                color: #e0e0e0;
                border: 1px solid #5a4545;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a4545;
            }
        """)

    def show_note(self, note_data: Dict, fps: int = 24, anchor_x: int = 0, parent_widget: QWidget = None):
        """
        Show the bubble with note content.

        Args:
            note_data: Note dictionary with id, frame, note, resolved
            fps: FPS for timestamp formatting
            anchor_x: X position to anchor the pointer
            parent_widget: Widget to position relative to
        """
        self._note_data = note_data
        self._note_id = note_data.get('id', -1)
        self._fps = fps

        # Update content
        frame = note_data.get('frame', 0)
        timestamp = Config.format_frame_timestamp(frame, fps)
        self._timestamp_label.setText(timestamp)

        resolved = note_data.get('resolved', False)
        if resolved:
            self._status_label.setText("Resolved")
            self._status_label.setStyleSheet("font-size: 10px; color: #4CAF50; background: transparent;")
            self._resolve_btn.setText("Unresolve")
        else:
            self._status_label.setText("")
            self._resolve_btn.setText("Resolve")

        note_text = note_data.get('note', '')
        self._note_label.setText(note_text)

        # Adjust size
        self.adjustSize()

        # Position the bubble
        if parent_widget:
            # Position at bottom of parent, centered on anchor_x
            parent_rect = parent_widget.rect()
            bubble_x = anchor_x - self.width() // 2

            # Keep within parent bounds
            bubble_x = max(5, min(bubble_x, parent_rect.width() - self.width() - 5))

            # Position near bottom of video area
            bubble_y = parent_rect.height() - self.height() - 60

            self.move(bubble_x, max(10, bubble_y))

        self.show()
        self.raise_()

    def hide_bubble(self):
        """Hide the bubble."""
        self.hide()
        self.closed.emit()

    def get_note_id(self) -> int:
        """Get current note ID."""
        return self._note_id

    def _on_close(self):
        """Handle close button."""
        self.hide_bubble()

    def _on_resolve(self):
        """Handle resolve button."""
        if self._note_id >= 0:
            self.resolve_clicked.emit(self._note_id)

    def _on_edit(self):
        """Handle edit button."""
        if self._note_id >= 0:
            self.edit_clicked.emit(self._note_id)

    def _on_delete(self):
        """Handle delete button."""
        if self._note_id >= 0:
            self.delete_clicked.emit(self._note_id)

    def update_note_data(self, note_data: Dict):
        """Update the displayed note data."""
        if self.isVisible() and note_data.get('id') == self._note_id:
            self.show_note(note_data, self._fps)


__all__ = ['NoteBubble']
