"""
Canvas manager for VersionHistoryDialog.

Handles annotation canvas positioning, loading, and saving.
"""

from typing import TYPE_CHECKING, Optional, List, Dict, Any, Tuple, Callable

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox

from ...drawover_canvas import DrawingTool

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget, QLabel
    from ...drawover_canvas import DrawoverCanvas
    from ....services.drawover_storage import DrawoverStorage, DrawoverCache
    from ....services.notes_database import NotesDatabase


class AnnotationCanvasManager:
    """
    Manages the annotation canvas for version history.

    Handles:
    - Canvas positioning over video
    - Loading strokes for frames
    - Saving strokes to storage
    - Hold mode (persist annotations forward)
    - Ghost mode (onion skin from neighboring frames)
    """

    def __init__(
        self,
        parent_widget: 'QWidget',
        canvas: 'DrawoverCanvas',
        storage: 'DrawoverStorage',
        cache: 'DrawoverCache',
        notes_db: 'NotesDatabase',
        is_studio_mode: bool,
        current_user: str,
        current_user_role: str,
        on_annotation_markers_changed: Callable[[], None]
    ):
        """
        Initialize canvas manager.

        Args:
            parent_widget: Parent widget for dialogs
            canvas: Drawover canvas widget
            storage: Drawover storage service
            cache: Drawover cache service
            notes_db: Notes database for logging
            is_studio_mode: Whether studio mode is active
            current_user: Current user name
            current_user_role: Current user role
            on_annotation_markers_changed: Callback when annotation markers change
        """
        self._parent = parent_widget
        self._canvas = canvas
        self._storage = storage
        self._cache = cache
        self._notes_db = notes_db
        self._is_studio_mode = is_studio_mode
        self._current_user = current_user
        self._current_user_role = current_user_role
        self._on_markers_changed = on_annotation_markers_changed

        # State
        self._selected_uuid: Optional[str] = None
        self._selected_version_label: Optional[str] = None
        self._current_frame: int = -1
        self._annotation_frames: List[int] = []
        self._strokes_from_hold: bool = False
        self._total_frames: int = 0

        # Mode settings
        self._hide_annotations = False
        self._hold_enabled = False
        self._ghost_enabled = False
        self._ghost_settings = {
            'before_frames': 2,
            'after_frames': 2,
            'before_color': QColor("#FF5555"),
            'after_color': QColor("#55FF55"),
            'sketches_only': True
        }

    @property
    def current_frame(self) -> int:
        """Get current frame number."""
        return self._current_frame

    @property
    def strokes_from_hold(self) -> bool:
        """Check if current strokes came from hold mode."""
        return self._strokes_from_hold

    def on_drawing_started(self):
        """
        Handle drawing start - clears held strokes if drawing on held frame.

        Call this when user starts drawing a stroke. If drawing on a held frame,
        this clears the canvas so the user starts fresh with a new annotation
        instead of including the held strokes.

        Returns:
            True if canvas was cleared (was a held frame), False otherwise.
        """
        if self._strokes_from_hold:
            self._canvas.clear()
            self._strokes_from_hold = False
            return True
        return False

    @property
    def annotation_frames(self) -> List[int]:
        """Get list of frames with annotations."""
        return self._annotation_frames

    @property
    def hide_annotations(self) -> bool:
        """Get hide annotations state."""
        return self._hide_annotations

    @hide_annotations.setter
    def hide_annotations(self, value: bool):
        """Set hide annotations state."""
        self._hide_annotations = value

    @property
    def hold_enabled(self) -> bool:
        """Get hold mode state."""
        return self._hold_enabled

    @hold_enabled.setter
    def hold_enabled(self, value: bool):
        """Set hold mode state."""
        self._hold_enabled = value

    @property
    def ghost_enabled(self) -> bool:
        """Get ghost mode state."""
        return self._ghost_enabled

    @ghost_enabled.setter
    def ghost_enabled(self, value: bool):
        """Set ghost mode state."""
        self._ghost_enabled = value

    @property
    def ghost_settings(self) -> Dict:
        """Get ghost settings."""
        return self._ghost_settings

    @ghost_settings.setter
    def ghost_settings(self, value: Dict):
        """Set ghost settings."""
        self._ghost_settings = value

    def set_version(
        self,
        animation_uuid: str,
        version_label: str,
        total_frames: int
    ):
        """
        Set current version for annotations.

        Args:
            animation_uuid: Animation UUID
            version_label: Version label
            total_frames: Total frame count
        """
        self._selected_uuid = animation_uuid
        self._selected_version_label = version_label
        self._total_frames = total_frames
        self._current_frame = -1
        self._strokes_from_hold = False
        self._load_annotation_markers()

    def clear_version(self):
        """Clear version selection."""
        self._selected_uuid = None
        self._selected_version_label = None
        self._current_frame = -1
        self._annotation_frames = []
        self._strokes_from_hold = False
        self._canvas.clear()

    def position_canvas(self, video_label: 'QLabel', video_rect: Optional[QRectF]):
        """
        Position canvas over video content area.

        Args:
            video_label: Video label widget (parent for canvas)
            video_rect: Video content rectangle, or None for full label
        """
        self._canvas.setParent(video_label)

        if video_rect and video_rect.isValid():
            self._canvas.setGeometry(video_rect.toRect())
            local_rect = QRectF(0, 0, video_rect.width(), video_rect.height())
            self._canvas.set_video_rect(local_rect)
        else:
            self._canvas.setGeometry(0, 0, video_label.width(), video_label.height())
            self._canvas.set_video_rect(QRectF(0, 0, video_label.width(), video_label.height()))

        self._canvas.raise_()

    def load_frame(self, frame: int, video_label: 'QLabel', video_rect: Optional[QRectF]):
        """
        Load annotations for a frame.

        Args:
            frame: Frame number
            video_label: Video label widget
            video_rect: Video content rectangle
        """
        if not self._selected_uuid or not self._selected_version_label:
            return

        # Save previous frame's annotations (only if not from Hold)
        if self._current_frame >= 0 and self._current_frame != frame:
            if not self._strokes_from_hold:
                self.save_current_frame(video_label)

        self._current_frame = frame
        self._strokes_from_hold = False

        # Handle Hide mode
        if self._hide_annotations:
            self._canvas.hide()
            return

        # Position canvas
        self.position_canvas(video_label, video_rect)

        # Clear ghost strokes first
        self._canvas.clear_ghost_strokes()

        # Load strokes for current frame (or held frame if Hold enabled)
        strokes, canvas_size, from_hold = self._get_strokes_for_frame(frame)
        self._strokes_from_hold = from_hold

        # Import strokes
        source_size = tuple(canvas_size) if canvas_size else None
        self._canvas.import_strokes(strokes, source_size)

        # Handle Ghost mode
        if self._ghost_enabled:
            self._add_ghost_strokes(frame)

        # Show canvas
        self._canvas.show()
        # Always allow drawing - drawing on held frames creates new annotation frames
        self._canvas.read_only = False
        self._canvas.set_tool(DrawingTool.PEN)

    def save_current_frame(self, video_label: 'QLabel'):
        """
        Save current frame's annotations to storage.

        Args:
            video_label: Video label widget for canvas size
        """
        if self._current_frame < 0 or not self._selected_uuid or not self._selected_version_label:
            return

        # Never save strokes from Hold mode
        if self._strokes_from_hold:
            return

        strokes = self._canvas.export_strokes()

        if strokes:
            canvas_size = (video_label.width(), video_label.height())

            success = self._storage.save_drawover(
                self._selected_uuid,
                self._selected_version_label,
                self._current_frame,
                strokes,
                author=self._current_user,
                canvas_size=canvas_size
            )

            if success:
                # Invalidate cache
                self._cache.invalidate(
                    self._selected_uuid,
                    self._selected_version_label,
                    self._current_frame
                )

                # Log action in studio mode
                if self._is_studio_mode:
                    self._notes_db.log_drawover_action(
                        self._selected_uuid,
                        self._selected_version_label,
                        self._current_frame,
                        'saved',
                        self._current_user,
                        self._current_user_role,
                        details={'stroke_count': len(strokes)}
                    )

                # Update metadata
                authors = set(s.get('author', '') for s in strokes if s.get('author'))
                self._notes_db.update_drawover_metadata(
                    self._selected_uuid,
                    self._selected_version_label,
                    self._current_frame,
                    len(strokes),
                    ','.join(authors)
                )

                # Update annotation markers
                self._load_annotation_markers()

    def _get_strokes_for_frame(self, frame: int) -> Tuple[List[Dict], Any, bool]:
        """
        Get strokes for a frame, with Hold mode support.

        Returns:
            (strokes, canvas_size, from_hold) tuple
        """
        # Check cache first
        cached = self._cache.get(
            self._selected_uuid,
            self._selected_version_label,
            frame
        )

        if cached:
            strokes = cached.get('strokes', [])
            canvas_size = cached.get('canvas_size')
            if strokes:
                return strokes, canvas_size, False

        # Load from storage
        data = self._storage.load_drawover(
            self._selected_uuid,
            self._selected_version_label,
            frame
        )

        if data:
            strokes = data.get('strokes', [])
            canvas_size = data.get('canvas_size')
            self._cache.put(
                self._selected_uuid,
                self._selected_version_label,
                frame,
                data
            )
            if strokes:
                return strokes, canvas_size, False

        # If Hold enabled and no strokes, search backwards
        if self._hold_enabled and self._annotation_frames:
            prev_frames = [f for f in self._annotation_frames if f < frame]
            if prev_frames:
                held_frame = max(prev_frames)
                cached = self._cache.get(
                    self._selected_uuid,
                    self._selected_version_label,
                    held_frame
                )
                if cached:
                    return cached.get('strokes', []), cached.get('canvas_size'), True

                data = self._storage.load_drawover(
                    self._selected_uuid,
                    self._selected_version_label,
                    held_frame
                )
                if data:
                    strokes = data.get('strokes', [])
                    canvas_size = data.get('canvas_size')
                    self._cache.put(
                        self._selected_uuid,
                        self._selected_version_label,
                        held_frame,
                        data
                    )
                    return strokes, canvas_size, True

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
            strokes, canvas_size = self._load_strokes_from_storage(ghost_frame)
            if strokes:
                distance = idx + 1
                opacity = 0.5 / distance
                self._canvas.add_ghost_strokes(
                    strokes, before_color, opacity,
                    tuple(canvas_size) if canvas_size else None
                )

        # Add ghost strokes for "after" frames
        for idx, ghost_frame in enumerate(after_frames):
            strokes, canvas_size = self._load_strokes_from_storage(ghost_frame)
            if strokes:
                distance = idx + 1
                opacity = 0.5 / distance
                self._canvas.add_ghost_strokes(
                    strokes, after_color, opacity,
                    tuple(canvas_size) if canvas_size else None
                )

    def _load_strokes_from_storage(self, frame: int) -> Tuple[List[Dict], Any]:
        """Load strokes from storage (with caching)."""
        cached = self._cache.get(
            self._selected_uuid,
            self._selected_version_label,
            frame
        )
        if cached:
            return cached.get('strokes', []), cached.get('canvas_size')

        data = self._storage.load_drawover(
            self._selected_uuid,
            self._selected_version_label,
            frame
        )
        if data:
            self._cache.put(
                self._selected_uuid,
                self._selected_version_label,
                frame,
                data
            )
            return data.get('strokes', []), data.get('canvas_size')

        return [], None

    def _load_annotation_markers(self):
        """Load frames with annotations for timeline display."""
        if not self._selected_uuid or not self._selected_version_label:
            self._annotation_frames = []
            self._on_markers_changed()
            return

        self._annotation_frames = self._storage.list_frames_with_drawovers(
            self._selected_uuid, self._selected_version_label
        )
        self._on_markers_changed()

    def refresh_annotation_markers(self):
        """Refresh annotation markers (public interface)."""
        self._load_annotation_markers()


__all__ = ['AnnotationCanvasManager']
