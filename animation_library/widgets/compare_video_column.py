"""
CompareVideoColumn - Composite widget for a single version in compare mode.

Contains:
- VideoPreviewWidget with DrawoverCanvas overlay
- Version label showing version number and status
- FrameRulerTimeline with note markers
- CompactNotesPanel for notes

Used by ComparisonWidget to show two versions side-by-side.
"""

from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor

from .video_preview_widget import VideoPreviewWidget
from .drawover_canvas import DrawoverCanvas, DrawingTool
from .frame_ruler_timeline import FrameRulerTimeline
from .compact_notes_panel import CompactNotesPanel
from ..services.drawover_storage import DrawoverStorage


class CompareVideoColumn(QWidget):
    """
    Single version column for compare mode.

    Displays video with read-only annotations, timeline with markers,
    and compact notes panel.

    Signals:
        frame_clicked(int): When timeline or note is clicked (for sync)
    """

    frame_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self._version_uuid: Optional[str] = None
        self._version_label_text: Optional[str] = None
        self._version_status: Optional[str] = None
        self._total_frames: int = 0
        self._current_frame: int = 0
        self._notes: List[Dict] = []
        self._annotation_frames: List[int] = []  # Frames with annotations
        self._annotations_hidden: bool = False  # Hide annotations flag
        self._hold_enabled: bool = False  # Hold mode flag
        self._ghost_enabled: bool = False  # Ghost mode flag
        self._ghost_settings: Dict = {
            'before_frames': 2,
            'after_frames': 2,
            'before_color': QColor("#FF5555"),
            'after_color': QColor("#55FF55"),
            'sketches_only': True
        }

        # Drawover storage for loading annotations
        self._drawover_storage = DrawoverStorage()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Build the column UI with notes on the right side."""
        # Main horizontal layout: [Video+Timeline | Notes]
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Left side: Video + label + timeline (vertical)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # Video container with canvas overlay
        video_container = QFrame()
        video_container.setStyleSheet("background: #1a1a1a;")
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Video preview (controls hidden - managed by parent)
        self._video = VideoPreviewWidget()
        self._video.hide_controls()
        self._video.setMinimumSize(400, 280)
        video_layout.addWidget(self._video, 1)

        left_layout.addWidget(video_container, 1)

        # Drawover canvas (overlay - positioned over video label)
        self._canvas = DrawoverCanvas()
        self._canvas.hide()
        self._canvas.read_only = True
        self._canvas.set_tool(DrawingTool.NONE)

        # Version label
        self._version_label = QLabel("Select a version")
        self._version_label.setStyleSheet("""
            color: #888;
            font-size: 11px;
            padding: 4px 8px;
            background: #252525;
        """)
        self._version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self._version_label)

        # Frame ruler timeline (compact height)
        self._timeline = FrameRulerTimeline()
        self._timeline.setFixedHeight(50)
        left_layout.addWidget(self._timeline)

        main_layout.addWidget(left_widget, 1)

        # Right side: Compact notes panel
        self._notes_panel = CompactNotesPanel()
        self._notes_panel.setFixedWidth(200)
        main_layout.addWidget(self._notes_panel)

    def _connect_signals(self):
        """Connect internal signals."""
        # Timeline clicks
        self._timeline.frame_clicked.connect(self._on_timeline_clicked)
        self._timeline.frame_dragged.connect(self._on_timeline_clicked)
        self._timeline.marker_clicked.connect(self._on_marker_clicked)

        # Notes panel clicks
        self._notes_panel.note_clicked.connect(self._on_note_clicked)

    def set_version(self, version_data: Dict, notes: List[Dict] = None):
        """
        Set version data for this column.

        Args:
            version_data: Dict with 'uuid', 'version_label', 'status', 'preview_path'
            notes: Optional list of note dicts for this version
        """
        self._version_uuid = version_data.get('uuid')
        self._version_label_text = version_data.get('version_label', 'v???')
        self._version_status = version_data.get('status', '')
        self._notes = notes or []

        # Update version label display
        status_text = self._version_status.upper() if self._version_status else ''
        label_text = f"{self._version_label_text}"
        if status_text:
            label_text += f" | {status_text}"
        self._version_label.setText(label_text)

        # Style based on status
        status_colors = {
            'approved': '#4CAF50',
            'pending': '#FF9800',
            'revision_requested': '#f44336',
            'in_progress': '#2196F3',
        }
        status_color = status_colors.get(self._version_status, '#888')
        self._version_label.setStyleSheet(f"""
            color: {status_color};
            font-size: 12px;
            font-weight: bold;
            padding: 6px 8px;
            background: #252525;
        """)

        # Load video
        preview_path = version_data.get('preview_path', '')
        if preview_path:
            from pathlib import Path
            if Path(preview_path).exists():
                self._video.load_video(preview_path)
                self._total_frames = self._video.total_frames

        # Update timeline
        self._timeline.set_total_frames(max(1, self._total_frames))
        self._timeline.set_notes(self._notes)

        # Update notes panel
        self._notes_panel.set_notes(self._notes)

        # Load annotation frames for this version
        self._load_annotation_frames()

        # Position canvas after video loads
        QTimer.singleShot(100, self._position_canvas)

    def _load_annotation_frames(self):
        """Load frames with annotations for timeline display."""
        if not self._version_uuid or not self._version_label_text:
            self._annotation_frames = []
            self._timeline.set_annotation_frames([])
            return

        self._annotation_frames = self._drawover_storage.list_frames_with_drawovers(
            self._version_uuid, self._version_label_text
        )
        self._timeline.set_annotation_frames(self._annotation_frames)

    def _position_canvas(self):
        """Position drawover canvas over video content."""
        video_label = self._video.video_label
        self._canvas.setParent(video_label)

        # Get video content rect
        video_rect = self._video.get_video_display_rect()
        if video_rect and video_rect.isValid():
            self._canvas.setGeometry(video_rect)
            from PyQt6.QtCore import QRectF
            local_rect = QRectF(0, 0, video_rect.width(), video_rect.height())
            self._canvas.set_video_rect(local_rect)
        else:
            self._canvas.setGeometry(0, 0, video_label.width(), video_label.height())

        self._canvas.raise_()

    def set_current_frame(self, frame: int, load_drawover: bool = False):
        """
        Set current frame (called by parent for sync).

        Args:
            frame: Frame number to display
            load_drawover: If True, load annotations (skip during playback for performance)
        """
        self._current_frame = frame
        self._timeline.set_current_frame(frame)

        # Only load annotations when explicitly requested (not during continuous playback)
        if load_drawover:
            self._load_drawover_for_frame(frame)

    def _load_drawover_for_frame(self, frame: int):
        """Load and display annotations for a frame with hold/ghost support."""
        if not self._version_uuid or not self._version_label_text:
            self._canvas.hide()
            return

        # If annotations are hidden, don't show canvas
        if self._annotations_hidden:
            self._canvas.hide()
            return

        # Position canvas first
        self._position_canvas()

        # Clear ghost strokes
        self._canvas.clear_ghost_strokes()

        # Get strokes for current frame (with hold mode support)
        strokes, canvas_size, from_hold = self._get_strokes_for_frame(frame)

        if strokes:
            # Import strokes
            source_size = tuple(canvas_size) if canvas_size else None
            self._canvas.import_strokes(strokes, source_size)

            # Add ghost strokes if enabled
            if self._ghost_enabled:
                self._add_ghost_strokes(frame)

            self._canvas.show()
        else:
            self._canvas.clear()
            # Add ghost strokes even if no current strokes
            if self._ghost_enabled:
                self._add_ghost_strokes(frame)
                if self._canvas.has_ghost_strokes():
                    self._canvas.show()
                else:
                    self._canvas.hide()
            else:
                self._canvas.hide()

    def _get_strokes_for_frame(self, frame: int):
        """Get strokes for a frame with hold mode support.

        Returns:
            (strokes, canvas_size, from_hold) tuple
        """
        # Load from storage
        data = self._drawover_storage.load_drawover(
            self._version_uuid,
            self._version_label_text,
            frame
        )

        if data and data.get('strokes'):
            return data.get('strokes', []), data.get('canvas_size'), False

        # If hold enabled and no strokes, search backwards
        if self._hold_enabled and self._annotation_frames:
            prev_frames = [f for f in self._annotation_frames if f < frame]
            if prev_frames:
                held_frame = max(prev_frames)
                data = self._drawover_storage.load_drawover(
                    self._version_uuid,
                    self._version_label_text,
                    held_frame
                )
                if data and data.get('strokes'):
                    return data.get('strokes', []), data.get('canvas_size'), True

        return [], None, False

    def _add_ghost_strokes(self, frame: int):
        """Add ghost/onion skin strokes from neighboring frames."""
        before_count = self._ghost_settings.get('before_frames', 2)
        after_count = self._ghost_settings.get('after_frames', 2)
        before_color = self._ghost_settings.get('before_color', QColor("#FF5555"))
        after_color = self._ghost_settings.get('after_color', QColor("#55FF55"))
        sketches_only = self._ghost_settings.get('sketches_only', True)

        if sketches_only:
            if not self._annotation_frames:
                return
            before_frames = sorted([f for f in self._annotation_frames if f < frame], reverse=True)
            before_frames = before_frames[:before_count]
            after_frames = sorted([f for f in self._annotation_frames if f > frame])
            after_frames = after_frames[:after_count]
        else:
            before_frames = [frame - i for i in range(1, before_count + 1) if frame - i >= 0]
            after_frames = [frame + i for i in range(1, after_count + 1) if frame + i < self._total_frames]

        # Add ghost strokes for "before" frames
        for idx, ghost_frame in enumerate(before_frames):
            data = self._drawover_storage.load_drawover(
                self._version_uuid,
                self._version_label_text,
                ghost_frame
            )
            if data and data.get('strokes'):
                distance = idx + 1
                opacity = 0.5 / distance
                canvas_size = data.get('canvas_size')
                self._canvas.add_ghost_strokes(
                    data['strokes'], before_color, opacity,
                    tuple(canvas_size) if canvas_size else None
                )

        # Add ghost strokes for "after" frames
        for idx, ghost_frame in enumerate(after_frames):
            data = self._drawover_storage.load_drawover(
                self._version_uuid,
                self._version_label_text,
                ghost_frame
            )
            if data and data.get('strokes'):
                distance = idx + 1
                opacity = 0.5 / distance
                canvas_size = data.get('canvas_size')
                self._canvas.add_ghost_strokes(
                    data['strokes'], after_color, opacity,
                    tuple(canvas_size) if canvas_size else None
                )

    def _on_timeline_clicked(self, frame: int):
        """Handle timeline click - emit for sync."""
        self.frame_clicked.emit(frame)

    def _on_marker_clicked(self, frame: int, note_id: int):
        """Handle marker click - emit frame for sync."""
        self.frame_clicked.emit(frame)

    def _on_note_clicked(self, frame: int):
        """Handle note click - emit frame for sync."""
        self.frame_clicked.emit(frame)

    def seek_to_frame(self, frame: int):
        """Seek video to specific frame (loads annotations)."""
        clamped = min(frame, self._total_frames - 1) if self._total_frames > 0 else 0
        self._video.seek_to_frame(clamped)
        self.set_current_frame(clamped, load_drawover=True)

    def clear(self):
        """Clear this column."""
        self._video.clear()
        self._canvas.clear()
        self._canvas.hide()
        self._timeline.set_total_frames(1)
        self._timeline.set_notes([])
        self._notes_panel.clear()
        self._version_label.setText("Select a version")
        self._version_uuid = None
        self._version_label_text = None
        self._total_frames = 0

    @property
    def video_widget(self) -> VideoPreviewWidget:
        """Access to video widget for playback control."""
        return self._video

    @property
    def total_frames(self) -> int:
        """Get total frame count."""
        return self._total_frames

    @property
    def fps(self) -> float:
        """Get video FPS."""
        return self._video.fps if self._video else 24

    @property
    def annotation_frames(self) -> List[int]:
        """Get list of frames with annotations."""
        return self._annotation_frames

    def set_canvas_visible(self, visible: bool):
        """Show or hide the annotation canvas."""
        self._annotations_hidden = not visible
        if visible:
            # Reload annotations for current frame
            self._load_drawover_for_frame(self._current_frame)
        else:
            self._canvas.hide()

    def set_hold_enabled(self, enabled: bool):
        """Enable or disable hold mode."""
        self._hold_enabled = enabled
        # Reload annotations to apply hold mode
        self._load_drawover_for_frame(self._current_frame)

    def set_ghost_enabled(self, enabled: bool):
        """Enable or disable ghost mode."""
        self._ghost_enabled = enabled
        # Reload annotations to apply ghost mode
        self._load_drawover_for_frame(self._current_frame)

    def set_ghost_settings(self, settings: Dict):
        """Set ghost mode settings."""
        self._ghost_settings = settings
        if self._ghost_enabled:
            # Reload annotations to apply new settings
            self._load_drawover_for_frame(self._current_frame)

    def resizeEvent(self, event):
        """Handle resize - reposition canvas."""
        super().resizeEvent(event)
        if self._canvas.isVisible():
            QTimer.singleShot(50, self._position_canvas)
