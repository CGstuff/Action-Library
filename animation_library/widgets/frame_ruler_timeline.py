"""
FrameRulerTimeline - SyncSketch-style frame-by-frame timeline

Shows a ruler with frame numbers that can be clicked to seek.
Displays note markers at their frame positions.
"""

from typing import List, Dict, Optional
from PyQt6.QtWidgets import QWidget, QToolTip, QHBoxLayout, QPushButton, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt, QRect, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
    QMouseEvent, QWheelEvent
)


class FrameRulerTimeline(QWidget):
    """
    Frame-by-frame timeline ruler with click-to-seek.

    Features:
    - Click any position to seek to that frame
    - Drag to scrub through frames
    - Frame number labels at intervals
    - Note markers shown as large clickable markers
    - Current frame indicator

    Signals:
        frame_clicked(int): Frame number clicked
        frame_dragged(int): Frame number during drag
        marker_clicked(int, int): Frame and note_id when clicking a marker
    """

    frame_clicked = pyqtSignal(int)
    frame_dragged = pyqtSignal(int)
    marker_clicked = pyqtSignal(int, int)  # frame, note_id

    # Visual settings
    RULER_HEIGHT = 50  # Taller for bigger markers
    TICK_HEIGHT_MAJOR = 10
    TICK_HEIGHT_MINOR = 5
    MARKER_SIZE = 24  # Much bigger markers
    PLAYHEAD_WIDTH = 2

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self._total_frames: int = 100
        self._current_frame: int = 0
        self._notes: List[Dict] = []
        self._is_dragging: bool = False
        self._marker_rects: List[tuple] = []  # (QRect, note_data) for click detection

        # Margins for the ruler area
        self._left_margin = 45  # Space for frame number on left
        self._right_margin = 10

        self.setMinimumHeight(self.RULER_HEIGHT)
        self.setMaximumHeight(self.RULER_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        # Styling
        self.setStyleSheet("background-color: #1a1a1a;")

    def set_total_frames(self, total: int):
        """Set total frame count."""
        self._total_frames = max(1, total)
        self.update()

    def set_current_frame(self, frame: int):
        """Set current playhead position."""
        self._current_frame = max(0, min(frame, self._total_frames - 1))
        self.update()

    def set_notes(self, notes: List[Dict]):
        """Set note markers to display."""
        self._notes = notes
        self.update()

    def get_frame_at_x(self, x: int) -> int:
        """Convert X coordinate to frame number."""
        ruler_width = self.width() - self._left_margin - self._right_margin
        if ruler_width <= 0:
            return 0

        # Clamp X to ruler area
        x = max(self._left_margin, min(x, self.width() - self._right_margin))
        rel_x = x - self._left_margin

        # Calculate frame
        frame = int((rel_x / ruler_width) * self._total_frames)
        return max(0, min(frame, self._total_frames - 1))

    def get_x_for_frame(self, frame: int) -> int:
        """Convert frame number to X coordinate."""
        ruler_width = self.width() - self._left_margin - self._right_margin
        if ruler_width <= 0 or self._total_frames <= 0:
            return self._left_margin

        ratio = frame / max(1, self._total_frames - 1)
        return self._left_margin + int(ratio * ruler_width)

    def paintEvent(self, event):
        """Draw the timeline ruler."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        ruler_width = width - self._left_margin - self._right_margin

        if ruler_width <= 0:
            return

        # Background
        painter.fillRect(0, 0, width, height, QColor("#1a1a1a"))

        # Draw ruler track
        track_y = height - 8
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#333333")))
        painter.drawRect(self._left_margin, track_y, ruler_width, 4)

        # Calculate tick interval based on total frames and width
        self._draw_ticks(painter, ruler_width, track_y)

        # Draw note markers
        self._draw_note_markers(painter, ruler_width, track_y)

        # Draw playhead (current frame indicator)
        self._draw_playhead(painter, track_y)

        # Draw current frame number on left
        self._draw_frame_counter(painter)

        painter.end()

    def _draw_ticks(self, painter: QPainter, ruler_width: int, track_y: int):
        """Draw frame tick marks and labels."""
        # Determine tick interval based on zoom level
        # Show major ticks every N frames where N gives us ~10-20 major ticks
        frames_per_pixel = self._total_frames / ruler_width if ruler_width > 0 else 1

        # Calculate good interval
        if self._total_frames <= 30:
            major_interval = 5
            minor_interval = 1
        elif self._total_frames <= 100:
            major_interval = 10
            minor_interval = 5
        elif self._total_frames <= 300:
            major_interval = 25
            minor_interval = 5
        elif self._total_frames <= 1000:
            major_interval = 50
            minor_interval = 10
        else:
            major_interval = 100
            minor_interval = 25

        # Font for labels
        font = QFont("Consolas", 8)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Draw ticks
        tick_color = QColor("#666666")
        label_color = QColor("#888888")

        for frame in range(0, self._total_frames, minor_interval):
            x = self.get_x_for_frame(frame)

            is_major = (frame % major_interval == 0)
            tick_height = self.TICK_HEIGHT_MAJOR if is_major else self.TICK_HEIGHT_MINOR

            # Draw tick
            painter.setPen(QPen(tick_color, 1))
            painter.drawLine(x, track_y - tick_height, x, track_y)

            # Draw label for major ticks
            if is_major:
                label = str(frame)
                label_width = fm.horizontalAdvance(label)
                label_x = x - label_width // 2

                # Don't draw if too close to edges
                if label_x > self._left_margin - 10 and label_x + label_width < self.width() - 5:
                    painter.setPen(label_color)
                    painter.drawText(label_x, track_y - tick_height - 3, label)

        # Always draw last frame tick
        x = self.get_x_for_frame(self._total_frames - 1)
        painter.setPen(QPen(tick_color, 1))
        painter.drawLine(x, track_y - self.TICK_HEIGHT_MAJOR, x, track_y)

    def _draw_note_markers(self, painter: QPainter, ruler_width: int, track_y: int):
        """Draw large, clickable markers for notes at their frame positions."""
        self._marker_rects.clear()  # Reset marker hit areas

        marker_y = 4  # Position at top of widget
        half_size = self.MARKER_SIZE // 2

        for i, note in enumerate(self._notes):
            frame = note.get('frame', 0)
            resolved = note.get('resolved', False)

            x = self.get_x_for_frame(frame)

            # Color based on resolved status
            if resolved:
                bg_color = QColor("#4CAF50")  # Green
                border_color = QColor("#66BB6A")
            else:
                bg_color = QColor("#FF9800")  # Orange
                border_color = QColor("#FFB74D")

            # Draw large circular marker
            marker_rect = QRect(
                x - half_size,
                marker_y,
                self.MARKER_SIZE,
                self.MARKER_SIZE
            )

            # Store rect for click detection
            self._marker_rects.append((marker_rect, note))

            # Draw marker background
            painter.setPen(QPen(border_color, 2))
            painter.setBrush(QBrush(bg_color))
            painter.drawEllipse(marker_rect)

            # Draw marker number (1-indexed)
            painter.setPen(QColor("#ffffff"))
            font = QFont("Arial", 9, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(marker_rect, Qt.AlignmentFlag.AlignCenter, str(i + 1))

    def _draw_playhead(self, painter: QPainter, track_y: int):
        """Draw the current frame playhead."""
        x = self.get_x_for_frame(self._current_frame)

        # Playhead line - from below markers to track
        painter.setPen(QPen(QColor("#3A8FB7"), self.PLAYHEAD_WIDTH))
        painter.drawLine(x, self.MARKER_SIZE + 8, x, track_y + 4)

        # Playhead triangle at bottom pointing up
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#3A8FB7")))
        points = [
            QPoint(x - 6, track_y + 6),
            QPoint(x + 6, track_y + 6),
            QPoint(x, track_y - 2)
        ]
        painter.drawPolygon(points)

    def _draw_frame_counter(self, painter: QPainter):
        """Draw current frame number on left side."""
        font = QFont("Consolas", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#e0e0e0"))

        text = f"f{self._current_frame}"
        # Position in the lower portion of the widget
        painter.drawText(4, self.height() - 8, text)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press - check for marker click first, then seek."""
        if event.button() == Qt.MouseButton.LeftButton:
            click_pos = event.position().toPoint()

            # Check if clicking on a marker
            for marker_rect, note_data in self._marker_rects:
                if marker_rect.contains(click_pos):
                    frame = note_data.get('frame', 0)
                    note_id = note_data.get('id', -1)
                    self._current_frame = frame
                    self.update()
                    self.marker_clicked.emit(frame, note_id)
                    self.frame_clicked.emit(frame)
                    return

            # Regular timeline click - start seeking
            self._is_dragging = True
            frame = self.get_frame_at_x(int(event.position().x()))
            self._current_frame = frame
            self.update()
            self.frame_clicked.emit(frame)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move - drag scrubbing."""
        if self._is_dragging:
            frame = self.get_frame_at_x(int(event.position().x()))
            if frame != self._current_frame:
                self._current_frame = frame
                self.update()
                self.frame_dragged.emit(frame)
        else:
            # Show tooltip with frame number on hover
            frame = self.get_frame_at_x(int(event.position().x()))

            # Check if hovering over a note marker
            note_at_frame = None
            for note in self._notes:
                if note.get('frame') == frame:
                    note_at_frame = note
                    break

            if note_at_frame:
                note_text = note_at_frame.get('note', '')[:50]
                if len(note_at_frame.get('note', '')) > 50:
                    note_text += '...'
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"f{frame}: {note_text}"
                )
            else:
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"Frame {frame}"
                )

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release - stop dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False

    def leaveEvent(self, event):
        """Hide tooltip when leaving."""
        QToolTip.hideText()


__all__ = ['FrameRulerTimeline']
