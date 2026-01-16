"""
TimelineMarkers - Loom-style numbered markers on video timeline

Shows small numbered badges at note positions.
Clicking a marker emits a signal with frame and note_id.
"""

from typing import List, Dict, Optional
from PyQt6.QtWidgets import QWidget, QToolTip, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics

from ..config import Config


class TimelineMarkerBadge(QPushButton):
    """Small numbered badge for a single marker."""

    clicked_with_data = pyqtSignal(int, int)  # frame, note_id

    def __init__(self, index: int, note_data: Dict, parent=None):
        super().__init__(parent)

        self._index = index
        self._note_data = note_data
        self._frame = note_data.get('frame', 0)
        self._note_id = note_data.get('id', -1)
        self._resolved = note_data.get('resolved', False)

        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(str(index + 1))

        # Tooltip with note preview
        note_text = note_data.get('note', '')[:60]
        if len(note_data.get('note', '')) > 60:
            note_text += '...'
        self.setToolTip(f"f{self._frame}: {note_text}")

        self._apply_style()
        self.clicked.connect(self._on_click)

    def _apply_style(self):
        """Apply styling based on resolved status."""
        if self._resolved:
            # Green for resolved
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
                }
            """)
        else:
            # Orange for unresolved
            self.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #FFA726;
                }
            """)

    def _on_click(self):
        """Emit click with frame and note_id."""
        self.clicked_with_data.emit(self._frame, self._note_id)

    def get_frame(self) -> int:
        return self._frame

    def get_note_id(self) -> int:
        return self._note_id


class TimelineMarkers(QWidget):
    """
    Container widget that positions numbered marker badges on the timeline.

    Markers are positioned based on their frame relative to total frames.

    Signals:
        marker_clicked(int, int): frame, note_id when marker is clicked
    """

    marker_clicked = pyqtSignal(int, int)  # frame, note_id

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self._markers: List[Dict] = []
        self._total_frames: int = 1
        self._badges: List[TimelineMarkerBadge] = []

        # Layout for absolute positioning
        self.setMinimumHeight(24)
        self.setMaximumHeight(24)

    def set_markers(self, notes: List[Dict]):
        """
        Set the review notes to display as markers.

        Args:
            notes: List of note dicts with 'frame', 'note', 'resolved', 'id' keys
        """
        self._markers = notes
        self._rebuild_badges()

    def set_total_frames(self, total: int):
        """
        Set the total frame count for position calculation.

        Args:
            total: Total number of frames in the video
        """
        self._total_frames = max(1, total)
        self._position_badges()

    def clear_markers(self):
        """Remove all markers."""
        self._markers = []
        self._clear_badges()

    def _clear_badges(self):
        """Remove all badge widgets."""
        for badge in self._badges:
            badge.deleteLater()
        self._badges.clear()

    def _rebuild_badges(self):
        """Rebuild all badge widgets."""
        self._clear_badges()

        for i, note_data in enumerate(self._markers):
            badge = TimelineMarkerBadge(i, note_data, self)
            badge.clicked_with_data.connect(self._on_badge_clicked)
            self._badges.append(badge)
            badge.show()

        self._position_badges()

    def _position_badges(self):
        """Position badges based on frame positions."""
        if not self._badges:
            return

        # Calculate usable width (leave margin for badge width)
        badge_width = 20
        margin = 10
        usable_width = self.width() - badge_width - (margin * 2)

        if usable_width <= 0:
            return

        for badge in self._badges:
            frame = badge.get_frame()

            # Calculate X position based on frame ratio
            if self._total_frames > 1:
                ratio = frame / (self._total_frames - 1)
            else:
                ratio = 0

            x = margin + int(ratio * usable_width)

            # Center badge on position
            badge.move(x, 2)

    def _on_badge_clicked(self, frame: int, note_id: int):
        """Handle badge click."""
        self.marker_clicked.emit(frame, note_id)

    def resizeEvent(self, event):
        """Reposition badges on resize."""
        super().resizeEvent(event)
        self._position_badges()

    def paintEvent(self, event):
        """Draw the timeline track."""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw timeline track
        track_height = 4
        track_y = (self.height() - track_height) // 2 + 6

        # Track background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#3a3a3a")))
        painter.drawRoundedRect(
            10, track_y,
            self.width() - 20, track_height,
            2, 2
        )

        painter.end()


__all__ = ['TimelineMarkers', 'TimelineMarkerBadge']
