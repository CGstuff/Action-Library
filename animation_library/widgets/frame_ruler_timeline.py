"""
FrameRulerTimeline - SyncSketch-style frame-by-frame timeline

Shows a ruler with frame numbers that can be clicked to seek.
Displays two rows of compact markers:
- Row 1 (top): Note markers - thin orange/green bars with number badges
- Row 2: Annotation markers - thin blue bars
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
    - Note markers shown as compact bars with number badges (row 1 - orange/green)
    - Annotation markers shown as compact blue bars (row 2)
    - Current frame indicator

    Signals:
        frame_clicked(int): Frame number clicked
        frame_dragged(int): Frame number during drag
        marker_clicked(int, int): Frame and note_id when clicking a note marker
        annotation_marker_clicked(int): Frame when clicking an annotation marker
    """

    frame_clicked = pyqtSignal(int)
    frame_dragged = pyqtSignal(int)
    marker_clicked = pyqtSignal(int, int)  # frame, note_id
    annotation_marker_clicked = pyqtSignal(int)  # frame

    # Visual settings - compact markers
    RULER_HEIGHT = 50  # Reduced from 70 for compact layout
    TICK_HEIGHT_MAJOR = 8
    TICK_HEIGHT_MINOR = 4

    # Compact bar markers
    MARKER_WIDTH = 4  # Thin vertical bar width
    NOTE_MARKER_HEIGHT = 14  # Height of note marker bar
    ANNOTATION_MARKER_HEIGHT = 12  # Height of annotation marker bar
    NOTE_MARKER_Y = 2  # Notes at top row
    ANNOTATION_MARKER_Y = 18  # Annotations below notes
    NOTE_BADGE_SIZE = 10  # Small number badge size

    PLAYHEAD_WIDTH = 2

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self._total_frames: int = 100
        self._current_frame: int = 0
        self._notes: List[Dict] = []
        self._annotation_frames: List[int] = []  # Frames with annotations (separate from notes)
        self._is_dragging: bool = False
        self._marker_rects: List[tuple] = []  # (QRect, note_data) for click detection
        self._annotation_marker_rects: List[tuple] = []  # (QRect, frame) for annotation click detection

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

    def set_annotation_frames(self, frames: List[int]):
        """Set frames with annotations to display as blue markers."""
        self._annotation_frames = frames
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
        track_y = height - 6
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#333333")))
        painter.drawRect(self._left_margin, track_y, ruler_width, 3)

        # Calculate tick interval based on total frames and width
        self._draw_ticks(painter, ruler_width, track_y)

        # Draw annotation markers (row 2 - blue) - draw first so notes overlap if needed
        self._draw_annotation_markers(painter, ruler_width, track_y)

        # Draw note markers (row 1 - orange/green with badges)
        self._draw_note_markers(painter, ruler_width, track_y)

        # Draw playhead (current frame indicator)
        self._draw_playhead(painter, track_y)

        # Draw current frame number on left
        self._draw_frame_counter(painter)

        painter.end()

    def _draw_ticks(self, painter: QPainter, ruler_width: int, track_y: int):
        """Draw frame tick marks and labels."""
        # Determine tick interval based on zoom level
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
        font = QFont("Consolas", 7)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Draw ticks
        tick_color = QColor("#555555")
        label_color = QColor("#777777")

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
                    painter.drawText(label_x, track_y - tick_height - 2, label)

        # Always draw last frame tick
        x = self.get_x_for_frame(self._total_frames - 1)
        painter.setPen(QPen(tick_color, 1))
        painter.drawLine(x, track_y - self.TICK_HEIGHT_MAJOR, x, track_y)

    def _draw_note_markers(self, painter: QPainter, ruler_width: int, track_y: int):
        """Draw compact bar markers for notes with number badges (row 1)."""
        self._marker_rects.clear()  # Reset marker hit areas

        half_width = self.MARKER_WIDTH // 2

        for i, note in enumerate(self._notes):
            frame = note.get('frame', 0)
            resolved = note.get('resolved', False)

            x = self.get_x_for_frame(frame)

            # Color based on resolved status
            if resolved:
                bar_color = QColor("#4CAF50")  # Green
                badge_color = QColor("#2E7D32")  # Darker green for badge
            else:
                bar_color = QColor("#FF9800")  # Orange
                badge_color = QColor("#E65100")  # Darker orange for badge

            # Draw thin vertical bar
            bar_rect = QRect(
                x - half_width,
                self.NOTE_MARKER_Y,
                self.MARKER_WIDTH,
                self.NOTE_MARKER_HEIGHT
            )

            # Store rect for click detection (slightly wider for easier clicking)
            click_rect = QRect(
                x - half_width - 3,
                self.NOTE_MARKER_Y,
                self.MARKER_WIDTH + 6,
                self.NOTE_MARKER_HEIGHT + 2
            )
            self._marker_rects.append((click_rect, note))

            # Draw the bar with rounded ends
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bar_color))
            painter.drawRoundedRect(bar_rect, 2, 2)

            # Draw small number badge on top of bar
            badge_rect = QRect(
                x - self.NOTE_BADGE_SIZE // 2,
                self.NOTE_MARKER_Y - 2,
                self.NOTE_BADGE_SIZE,
                self.NOTE_BADGE_SIZE
            )

            # Badge background (circle)
            painter.setBrush(QBrush(badge_color))
            painter.drawEllipse(badge_rect)

            # Badge number
            painter.setPen(QColor("#ffffff"))
            font = QFont("Arial", 6, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, str(i + 1))

    def _draw_annotation_markers(self, painter: QPainter, ruler_width: int, track_y: int):
        """Draw compact blue bar markers for frames with annotations (row 2)."""
        self._annotation_marker_rects.clear()  # Reset marker hit areas

        half_width = self.MARKER_WIDTH // 2

        # Blue color for annotation markers
        bar_color = QColor("#2196F3")

        for frame in self._annotation_frames:
            x = self.get_x_for_frame(frame)

            # Draw thin vertical bar
            bar_rect = QRect(
                x - half_width,
                self.ANNOTATION_MARKER_Y,
                self.MARKER_WIDTH,
                self.ANNOTATION_MARKER_HEIGHT
            )

            # Store rect for click detection (slightly wider for easier clicking)
            click_rect = QRect(
                x - half_width - 3,
                self.ANNOTATION_MARKER_Y,
                self.MARKER_WIDTH + 6,
                self.ANNOTATION_MARKER_HEIGHT
            )
            self._annotation_marker_rects.append((click_rect, frame))

            # Draw the bar with rounded ends
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bar_color))
            painter.drawRoundedRect(bar_rect, 2, 2)

    def _draw_playhead(self, painter: QPainter, track_y: int):
        """Draw the current frame playhead."""
        x = self.get_x_for_frame(self._current_frame)

        # Playhead line - from below annotation markers to track
        playhead_start_y = self.ANNOTATION_MARKER_Y + self.ANNOTATION_MARKER_HEIGHT + 2
        painter.setPen(QPen(QColor("#3A8FB7"), self.PLAYHEAD_WIDTH))
        painter.drawLine(x, playhead_start_y, x, track_y + 2)

        # Playhead triangle at bottom pointing up
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#3A8FB7")))
        points = [
            QPoint(x - 5, track_y + 4),
            QPoint(x + 5, track_y + 4),
            QPoint(x, track_y - 1)
        ]
        painter.drawPolygon(points)

    def _draw_frame_counter(self, painter: QPainter):
        """Draw current frame number on left side."""
        font = QFont("Consolas", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#e0e0e0"))

        text = f"f{self._current_frame}"
        # Position in the lower portion of the widget
        painter.drawText(4, self.height() - 6, text)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press - check for marker click first, then seek."""
        if event.button() == Qt.MouseButton.LeftButton:
            click_pos = event.position().toPoint()

            # Check if clicking on a note marker (row 1)
            for marker_rect, note_data in self._marker_rects:
                if marker_rect.contains(click_pos):
                    frame = note_data.get('frame', 0)
                    note_id = note_data.get('id', -1)
                    self._current_frame = frame
                    self.update()
                    self.marker_clicked.emit(frame, note_id)
                    self.frame_clicked.emit(frame)
                    return

            # Check if clicking on an annotation marker (row 2)
            for marker_rect, frame in self._annotation_marker_rects:
                if marker_rect.contains(click_pos):
                    self._current_frame = frame
                    self.update()
                    self.annotation_marker_clicked.emit(frame)
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
            click_pos = event.position().toPoint()

            # Check if hovering over a note marker
            for marker_rect, note_data in self._marker_rects:
                if marker_rect.contains(click_pos):
                    note_text = note_data.get('note', '')[:50]
                    if len(note_data.get('note', '')) > 50:
                        note_text += '...'
                    frame = note_data.get('frame', 0)
                    QToolTip.showText(
                        event.globalPosition().toPoint(),
                        f"Note #{self._notes.index(note_data) + 1} (f{frame}): {note_text}"
                    )
                    return

            # Check if hovering over an annotation marker
            for marker_rect, frame in self._annotation_marker_rects:
                if marker_rect.contains(click_pos):
                    QToolTip.showText(
                        event.globalPosition().toPoint(),
                        f"Annotation at frame {frame}"
                    )
                    return

            # Regular frame tooltip
            frame = self.get_frame_at_x(int(event.position().x()))
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
