"""
Video Preview Panel Widget

Composite widget that encapsulates:
- VideoPreviewWidget (video display)
- DrawoverCanvas (annotation overlay)
- AnnotationToolbar (tools)
- Playback controls
- Canvas positioning logic

Handles annotation mode toggle, frame synchronization, and drawover data.
"""

from typing import Optional, List, Dict, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor

from .video_preview_widget import VideoPreviewWidget
from .drawover_canvas import DrawoverCanvas, DrawingTool
from .annotation_toolbar import AnnotationToolbar
from ..utils.icon_loader import IconLoader
from ..utils.icon_utils import colorize_white_svg
from ..themes.theme_manager import get_theme_manager


class VideoPreviewPanel(QWidget):
    """
    Composite video preview with annotation support.

    Signals:
        frame_changed(int): Emitted when video frame changes
        annotation_mode_changed(bool): Emitted when annotation mode toggles
        drawover_modified(): Emitted when annotations are modified
    """

    frame_changed = pyqtSignal(int)
    annotation_mode_changed = pyqtSignal(bool)
    drawover_modified = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._annotation_mode = False
        self._current_author = ""

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with annotate toggle and toolbar
        header = QHBoxLayout()
        header.setContentsMargins(4, 4, 4, 4)
        header.setSpacing(8)

        # Annotate toggle button
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#e0e0e0"

        self._annotate_btn = QPushButton("Annotate")
        self._annotate_btn.setCheckable(True)
        self._annotate_btn.setFixedHeight(28)
        self._annotate_btn.setStyleSheet("""
            QPushButton {
                background: #2d2d2d; border: 1px solid #444;
                color: #aaa; padding: 4px 12px; border-radius: 3px;
            }
            QPushButton:hover { background: #3a3a3a; }
            QPushButton:checked { background: #FF5722; border-color: #FF5722; color: white; }
        """)
        self._annotate_btn.clicked.connect(self._on_annotate_toggled)
        header.addWidget(self._annotate_btn)

        # Annotation toolbar (hidden by default)
        self._annotation_toolbar = AnnotationToolbar()
        self._annotation_toolbar.hide()
        header.addWidget(self._annotation_toolbar)

        header.addStretch()
        layout.addLayout(header)

        # Video container
        self._video_container = QFrame()
        self._video_container.setStyleSheet("background: #1e1e1e;")
        container_layout = QVBoxLayout(self._video_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Video preview
        self._video_preview = VideoPreviewWidget()
        self._video_preview.hide_controls()
        container_layout.addWidget(self._video_preview, 1)

        layout.addWidget(self._video_container, 1)

        # Drawover canvas (overlay - positioned over video)
        self._canvas = DrawoverCanvas()
        self._canvas.hide()
        self._canvas.read_only = True

        # Playback controls
        self._controls = self._create_playback_controls()
        layout.addWidget(self._controls)

    def _create_playback_controls(self) -> QWidget:
        """Create video playback controls."""
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 4, 8, 4)
        controls_layout.setSpacing(8)

        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#e0e0e0"

        btn_style = """
            QPushButton { background: transparent; border: none; }
            QPushButton:hover { background: #3a3a3a; border-radius: 4px; }
            QPushButton:checked { background: #FF5722; border-radius: 4px; }
        """

        # Play/Pause button
        self._play_btn = QPushButton()
        self._play_btn.setFixedSize(32, 32)
        self._play_btn.setStyleSheet(btn_style)
        play_icon = IconLoader.get("play")
        self._play_btn.setIcon(colorize_white_svg(play_icon, icon_color))
        self._play_btn.clicked.connect(self._on_play_clicked)
        controls_layout.addWidget(self._play_btn)

        # Loop button
        self._loop_btn = QPushButton()
        self._loop_btn.setFixedSize(32, 32)
        self._loop_btn.setCheckable(True)
        self._loop_btn.setStyleSheet(btn_style + """
            QPushButton:checked { background: #2196F3; }
        """)
        loop_icon = IconLoader.get("loop")
        self._loop_btn.setIcon(colorize_white_svg(loop_icon, icon_color))
        self._loop_btn.setToolTip("Loop playback")
        controls_layout.addWidget(self._loop_btn)

        # Progress slider (use the video preview's internal slider)
        controls_layout.addWidget(self._video_preview._progress_slider, 1)

        # Frame counter
        self._frame_label = QLabel("0 / 0")
        self._frame_label.setStyleSheet("color: #888; font-size: 11px;")
        controls_layout.addWidget(self._frame_label)

        return controls

    def _connect_signals(self):
        """Connect internal signals."""
        # Video preview signals
        self._video_preview.frame_changed.connect(self._on_frame_changed)

        # Annotation toolbar signals
        self._annotation_toolbar.tool_changed.connect(self._on_tool_changed)
        self._annotation_toolbar.color_changed.connect(self._on_color_changed)
        self._annotation_toolbar.undo_clicked.connect(self._on_undo)
        self._annotation_toolbar.redo_clicked.connect(self._on_redo)
        self._annotation_toolbar.clear_clicked.connect(self._on_clear)

        # Canvas signals
        self._canvas.drawing_finished.connect(self._on_drawing_finished)

        # Loop button sync
        self._loop_btn.toggled.connect(self._video_preview._loop_button.setChecked)

    def _on_annotate_toggled(self, checked: bool):
        """Handle annotate button toggle."""
        if checked:
            self._enter_annotation_mode()
        else:
            self._exit_annotation_mode()
        self.annotation_mode_changed.emit(checked)

    def _enter_annotation_mode(self):
        """Enable annotation mode."""
        self._annotation_mode = True
        self._annotation_toolbar.show()

        # Pause video
        if self._video_preview.is_playing:
            self._video_preview.toggle_playback()
            self._update_play_icon()

        # Position and show canvas
        self._position_canvas()
        self._canvas.show()
        self._canvas.read_only = False
        self._canvas.set_tool(DrawingTool.PEN)
        self._canvas.color = self._annotation_toolbar.current_color
        self._annotation_toolbar.set_tool(DrawingTool.PEN)

    def _exit_annotation_mode(self):
        """Disable annotation mode."""
        self._annotation_mode = False
        self._annotation_toolbar.hide()

        # Keep canvas visible but read-only for viewing annotations
        self._canvas.read_only = True
        self._canvas.set_tool(DrawingTool.NONE)

    def _position_canvas(self):
        """
        Position canvas over video content area only.

        This ensures:
        - Canvas is parented to video label
        - Canvas covers only the actual video content (not letterbox bars)
        - Canvas video rect is set for coordinate conversion
        - Strokes are refreshed if video rect changed
        """
        video_label = self._video_preview.video_label
        self._canvas.setParent(video_label)

        # Get actual video content rect (excluding letterbox)
        video_rect = self._video_preview.get_video_display_rect()

        if video_rect and video_rect.isValid():
            # Position canvas at video content area
            self._canvas.setGeometry(video_rect)
            # Set video rect for UV coordinate conversion (in canvas-local coords)
            from PyQt6.QtCore import QRectF
            local_rect = QRectF(0, 0, video_rect.width(), video_rect.height())
            self._canvas.set_video_rect(local_rect)
        else:
            # Fallback: cover entire label
            self._canvas.setGeometry(0, 0, video_label.width(), video_label.height())
            from PyQt6.QtCore import QRectF
            self._canvas.set_video_rect(QRectF(0, 0, video_label.width(), video_label.height()))

        self._canvas.raise_()

    def _on_frame_changed(self, frame: int):
        """Handle video frame change."""
        # Update frame label
        total = self._video_preview.total_frames
        self._frame_label.setText(f"{frame} / {total}")

        # Reposition canvas if visible (annotation mode or viewing annotations)
        if self._annotation_mode or self._canvas.isVisible():
            QTimer.singleShot(10, self._position_canvas)

        self.frame_changed.emit(frame)

    def resizeEvent(self, event):
        """Handle resize - reposition canvas over video."""
        super().resizeEvent(event)
        if self._canvas.isVisible():
            # Delay to allow layout to update
            QTimer.singleShot(50, self._on_resize_complete)

    def _on_resize_complete(self):
        """Called after resize to update canvas position."""
        self._position_canvas()
        # Refresh strokes to recalculate screen positions from UV
        self._canvas.refresh_strokes()

    def _on_tool_changed(self, tool: DrawingTool):
        """Handle tool selection."""
        self._canvas.set_tool(tool)

    def _on_color_changed(self, color: QColor):
        """Handle color change."""
        self._canvas.color = color

    def _on_undo(self):
        """Undo last stroke."""
        self._canvas.undo_stack.undo()
        self._update_undo_redo_buttons()
        self.drawover_modified.emit()

    def _on_redo(self):
        """Redo last undone stroke."""
        self._canvas.undo_stack.redo()
        self._update_undo_redo_buttons()
        self.drawover_modified.emit()

    def _on_clear(self):
        """Clear all annotations on current frame."""
        self._canvas.clear()
        self._update_undo_redo_buttons()
        self.drawover_modified.emit()

    def _on_drawing_finished(self):
        """Handle drawing completion."""
        self._update_undo_redo_buttons()
        self.drawover_modified.emit()

    def _on_play_clicked(self):
        """Handle play button click."""
        self._video_preview.toggle_playback()
        self._update_play_icon()

    def _update_play_icon(self):
        """Update play/pause icon based on state."""
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#e0e0e0"

        if self._video_preview.is_playing:
            icon = IconLoader.get("pause")
        else:
            icon = IconLoader.get("play")
        self._play_btn.setIcon(colorize_white_svg(icon, icon_color))

    def _update_undo_redo_buttons(self):
        """Update undo/redo button states."""
        self._annotation_toolbar.set_undo_enabled(self._canvas.undo_stack.canUndo())
        self._annotation_toolbar.set_redo_enabled(self._canvas.undo_stack.canRedo())

    # ==================== PUBLIC API ====================

    def load_video(self, path: str) -> bool:
        """Load a video file."""
        result = self._video_preview.load_video(path)
        if result:
            self._on_frame_changed(0)
        return result

    def clear(self):
        """Clear video and canvas."""
        self._video_preview.clear()
        self._canvas.clear()

    @property
    def annotation_mode(self) -> bool:
        """Check if annotation mode is active."""
        return self._annotation_mode

    @property
    def current_frame(self) -> int:
        """Get current video frame."""
        return self._video_preview.current_frame

    @property
    def total_frames(self) -> int:
        """Get total video frames."""
        return self._video_preview.total_frames

    @property
    def is_playing(self) -> bool:
        """Check if video is playing."""
        return self._video_preview.is_playing

    def seek_to_frame(self, frame: int):
        """Seek video to specific frame."""
        self._video_preview.seek_to_frame(frame)

    def set_author(self, author: str):
        """Set the annotation author."""
        self._current_author = author
        self._canvas.set_author(author)

    def load_drawover(self, strokes: List[Dict], canvas_size: Tuple[int, int] = None):
        """Load drawover strokes for current frame."""
        self._canvas.clear()
        if strokes:
            self._canvas.import_strokes(strokes, canvas_size)
        self._update_undo_redo_buttons()

    def export_drawover(self) -> List[Dict]:
        """Export current drawover strokes."""
        return self._canvas.export_strokes()

    def get_canvas_size(self) -> Tuple[int, int]:
        """Get current canvas size."""
        return (self._canvas.width(), self._canvas.height())

    @property
    def video_label(self):
        """Access to video label for canvas positioning."""
        return self._video_preview.video_label

    def toggle_playback(self):
        """Toggle video playback."""
        self._video_preview.toggle_playback()
        self._update_play_icon()

    def set_loop(self, enabled: bool):
        """Set loop mode."""
        self._loop_btn.setChecked(enabled)
