"""
Version History Dialog - View and manage animation versions

Features:
- Version table with thumbnails
- Video preview with playback controls
- SyncSketch-style frame ruler timeline
- Review notes panel on right side
- Compare two versions side-by-side
"""

from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QApplication, QSizePolicy, QSplitter, QWidget,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QObject, QRunnable, QThreadPool
from PyQt6.QtGui import QColor, QPixmap, QImage, QIcon

from ...config import Config
from ...services.database_service import get_database_service
from ...services.notes_database import get_notes_database
from ...services.permissions import DrawoverPermissions
from ...services.drawover_storage import get_drawover_storage, get_drawover_cache
from ...utils.icon_loader import IconLoader
from ...utils.icon_utils import colorize_white_svg
from ...themes.theme_manager import get_theme_manager
from ..video_preview_widget import VideoPreviewWidget
from ..frame_ruler_timeline import FrameRulerTimeline
from ..drawover_canvas import DrawoverCanvas, DrawingTool
from ..review_notes_panel import ReviewNotesPanel
from .comparison_widget import ComparisonWidget


# ==================== Async Thumbnail Loading ====================

class ThumbnailSignals(QObject):
    loaded = pyqtSignal(str, QPixmap)
    failed = pyqtSignal(str)


class ThumbnailTask(QRunnable):
    def __init__(self, uuid: str, thumbnail_path: str, size: int):
        super().__init__()
        self.uuid = uuid
        self.thumbnail_path = thumbnail_path
        self.size = size
        self.signals = ThumbnailSignals()

    def run(self):
        try:
            path = Path(self.thumbnail_path)
            if not path.exists():
                self.signals.failed.emit(self.uuid)
                return

            image = QImage(str(path))
            if image.isNull():
                self.signals.failed.emit(self.uuid)
                return

            scaled = image.scaled(
                self.size, self.size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            pixmap = QPixmap.fromImage(scaled)
            self.signals.loaded.emit(self.uuid, pixmap)
        except Exception:
            self.signals.failed.emit(self.uuid)


# ==================== Version History Dialog ====================


class VersionHistoryDialog(QDialog):
    """
    Dialog for viewing animation version history with review notes.

    Layout: [Version Table] | [Video + Timeline] | [Notes Panel]
    """

    version_selected = pyqtSignal(str)
    version_set_as_latest = pyqtSignal(str)

    THUMBNAIL_SIZE = 60
    TABLE_WIDTH_NORMAL = 280
    TABLE_WIDTH_COMPARE = 180

    def __init__(self, version_group_id: str, parent=None, theme_manager=None):
        super().__init__(parent)

        self._version_group_id = version_group_id
        self._theme_manager = theme_manager
        self._db_service = get_database_service()
        self._notes_db = get_notes_database()
        self._versions: List[Dict[str, Any]] = []
        self._selected_uuid: Optional[str] = None
        self._selected_version_label: Optional[str] = None

        # Compare mode
        self._compare_mode = False
        self._compare_selections: List[str] = []

        # Thumbnails
        self._thread_pool = QThreadPool.globalInstance()
        self._thumbnail_cache: Dict[str, QPixmap] = {}
        self._pending_thumbnails: Dict[str, int] = {}

        # Video/notes state
        self._current_fps: int = 24
        self._total_frames: int = 0
        self._review_notes: List[Dict] = []

        # Drawover state
        self._drawover_storage = get_drawover_storage()
        self._drawover_cache = get_drawover_cache()
        self._drawover_enabled = False
        self._current_drawover_frame: int = -1

        # Studio Mode state
        self._is_studio_mode: bool = self._notes_db.is_studio_mode()
        self._current_user: str = self._notes_db.get_current_user()
        self._current_user_role: str = self._get_current_user_role()
        self._show_deleted: bool = False  # Toggle state

        self._configure_window()
        self._apply_theme_styles()
        self._build_ui()
        self._load_versions()

    def _get_current_user_role(self) -> str:
        """Get role of current user."""
        if not self._current_user:
            return 'artist'
        user = self._notes_db.get_user(self._current_user)
        return user.get('role', 'artist') if user else 'artist'

    def _configure_window(self):
        self.setWindowTitle("Animation Lineage")
        self.setModal(True)
        # Make it a normal window with min/max/close buttons for proper Windows behavior
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )

    def showEvent(self, event):
        """Maximize window when shown for full screen workspace."""
        super().showEvent(event)
        if not self.isMaximized():
            self.showMaximized()

    def _apply_theme_styles(self):
        if not self._theme_manager:
            self.setStyleSheet("""
                QDialog { background-color: #1e1e1e; }
                QLabel { color: #e0e0e0; background-color: transparent; }
                QPushButton {
                    background-color: #3a3a3a;
                    color: #e0e0e0;
                    border: 1px solid #404040;
                    border-radius: 3px;
                    padding: 8px 16px;
                }
                QPushButton:hover { background-color: #4a4a4a; }
                QPushButton:pressed { background-color: #2a2a2a; }
                QPushButton:disabled { background-color: #252525; color: #606060; }
                QTableWidget {
                    background-color: #2a2a2a;
                    color: #e0e0e0;
                    border: 1px solid #404040;
                    gridline-color: #404040;
                    selection-background-color: #3A8FB7;
                }
                QTableWidget::item {
                    padding: 8px;
                    background-color: #2a2a2a;
                    color: #e0e0e0;
                }
                QTableWidget::item:selected {
                    background-color: #3A8FB7;
                    color: #ffffff;
                }
                QTableWidget::item:selected:!active {
                    background-color: #3A8FB7;
                    color: #ffffff;
                }
                QTableWidget::item:hover:!selected { background-color: #3a3a3a; }
                QHeaderView::section {
                    background-color: #505050;
                    color: #ffffff;
                    padding: 8px;
                    border: none;
                    border-right: 1px solid #606060;
                    border-bottom: 1px solid #606060;
                    font-weight: bold;
                }
                QScrollBar:vertical {
                    background-color: #2d2d2d;
                    width: 10px;
                }
                QScrollBar::handle:vertical {
                    background-color: #4a4a4a;
                    border-radius: 5px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #5a5a5a;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QSplitter::handle { background-color: #404040; }
                QFrame { background-color: transparent; }
            """)

    def _center_over_parent(self):
        if self.parent():
            pg = self.parent().geometry()
            x = pg.x() + (pg.width() - self.width()) // 2
            y = pg.y() + (pg.height() - self.height()) // 2
            screen = QApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                x = max(sg.x(), min(x, sg.x() + sg.width() - self.width()))
                y = max(sg.y() + 30, min(y, sg.y() + sg.height() - self.height()))
            self.move(x, y)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("Animation Lineage")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)

        self._name_label = QLabel("")
        self._name_label.setStyleSheet("font-size: 13px; color: #888;")
        layout.addWidget(self._name_label)

        # Main splitter: Table | Video | Notes (fixed, not draggable)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(1)  # Minimal handle, just a line

        # ===== LEFT: Version table =====
        self._table_container = QWidget()
        self._table_container.setFixedWidth(self.TABLE_WIDTH_NORMAL)
        table_layout = QVBoxLayout(self._table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "", "Version", "Latest", "Status", "Frames"
        ])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setIconSize(QSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE))

        # Apply table-specific styles to override theme
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #404040;
                gridline-color: #404040;
            }
            QTableWidget::item {
                background-color: #2D2D2D;
                color: #FFFFFF;
            }
            QTableWidget::item:selected {
                background-color: #3A8FB7;
                color: #FFFFFF;
            }
            QTableWidget::item:hover:!selected {
                background-color: #4A4A4A;
            }
            QHeaderView::section {
                background-color: #4A4A4A;
                color: #FFFFFF;
                padding: 8px;
                border: none;
                border-right: 1px solid #505050;
                border-bottom: 1px solid #505050;
                font-weight: bold;
            }
        """)

        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, self.THUMBNAIL_SIZE + 8)
        self._table.setColumnWidth(1, 60)
        self._table.setColumnWidth(2, 50)
        self._table.setColumnWidth(4, 60)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(self._on_double_click)

        table_layout.addWidget(self._table)
        self._splitter.addWidget(self._table_container)

        # ===== CENTER: Video preview + timeline =====
        self._center_widget = QWidget()
        center_layout = QVBoxLayout(self._center_widget)
        center_layout.setContentsMargins(8, 0, 8, 0)
        center_layout.setSpacing(4)

        # Preview header
        preview_header = QHBoxLayout()
        self._preview_info_label = QLabel("Select a version to preview")
        self._preview_info_label.setStyleSheet("font-size: 12px; color: #888;")
        preview_header.addWidget(self._preview_info_label)
        preview_header.addStretch()

        # Done annotating button (shown only when in annotate mode)
        self._done_annotate_btn = QPushButton("Done Annotating")
        self._done_annotate_btn.setFixedHeight(24)
        self._done_annotate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._done_annotate_btn.setToolTip("Exit annotation mode")
        self._done_annotate_btn.clicked.connect(self._exit_drawover_mode)
        self._done_annotate_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                border: 1px solid #FF5722;
                border-radius: 0px;
                padding: 2px 10px;
                color: white;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #E64A19; border-color: #E64A19; }
        """)
        self._done_annotate_btn.hide()  # Hidden by default, shown in annotate mode
        preview_header.addWidget(self._done_annotate_btn)

        # Annotation toolbar (hidden until annotate mode)
        from ..annotation_toolbar import AnnotationToolbar
        self._annotation_toolbar = AnnotationToolbar()
        self._annotation_toolbar.tool_changed.connect(self._on_tool_selected)
        self._annotation_toolbar.color_changed.connect(self._on_draw_color_changed)
        self._annotation_toolbar.undo_clicked.connect(self._on_drawover_undo)
        self._annotation_toolbar.redo_clicked.connect(self._on_drawover_redo)
        self._annotation_toolbar.clear_clicked.connect(self._on_drawover_clear)
        self._annotation_toolbar.hide()
        preview_header.addWidget(self._annotation_toolbar)

        center_layout.addLayout(preview_header)

        # Video preview with drawover overlay (using stacked widget approach)
        from PyQt6.QtWidgets import QStackedLayout
        video_container = QWidget()
        video_container.setMinimumWidth(400)

        # Use a stacked layout with all widgets visible
        self._video_stack = QVBoxLayout(video_container)
        self._video_stack.setContentsMargins(0, 0, 0, 0)
        self._video_stack.setSpacing(0)

        # Create a frame to hold video and drawover
        preview_frame = QFrame()
        preview_frame.setStyleSheet("background: #1e1e1e;")  # Match dialog background
        preview_frame_layout = QVBoxLayout(preview_frame)
        preview_frame_layout.setContentsMargins(0, 0, 0, 0)
        preview_frame_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Video preview
        self._video_preview = VideoPreviewWidget()
        self._video_preview.hide_controls()  # Use our own controls below
        preview_frame_layout.addWidget(self._video_preview, 1)

        self._video_stack.addWidget(preview_frame, 1)

        # Drawover canvas (overlay - will be positioned over video)
        self._drawover_canvas = DrawoverCanvas()
        self._drawover_canvas.set_author(self._current_user)
        self._drawover_canvas.drawing_modified.connect(self._on_drawover_modified)
        self._drawover_canvas.read_only = True
        self._drawover_canvas.set_tool(DrawingTool.NONE)
        self._drawover_canvas.hide()  # Hidden until version selected

        center_layout.addWidget(video_container, 1)

        # Timeline controls row: Play | Loop | Frame Ruler
        timeline_row = QHBoxLayout()
        timeline_row.setSpacing(4)
        timeline_row.setContentsMargins(0, 0, 0, 0)

        # Load icons (same as video preview widget)
        self._load_playback_icons()

        # Play/pause button (matches video preview widget style)
        self._play_btn = QPushButton()
        self._play_btn.setIcon(self._play_icon)
        self._play_btn.setIconSize(QSize(24, 24))
        self._play_btn.setFixedSize(36, 36)
        self._play_btn.setProperty("media", "true")
        self._play_btn.setToolTip("Play/Pause")
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.clicked.connect(self._on_play_clicked)
        timeline_row.addWidget(self._play_btn)

        # Loop button (matches video preview widget style)
        self._loop_btn = QPushButton()
        self._loop_btn.setIcon(self._loop_icon)
        self._loop_btn.setIconSize(QSize(24, 24))
        self._loop_btn.setFixedSize(36, 36)
        self._loop_btn.setProperty("media", "true")
        self._loop_btn.setCheckable(True)
        self._loop_btn.setChecked(True)
        self._loop_btn.setToolTip("Toggle Loop")
        self._loop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._loop_btn.setStyleSheet("""
            QPushButton:checked {
                background-color: rgba(255, 255, 255, 0.35);
            }
        """)
        self._loop_btn.clicked.connect(self._on_loop_clicked)
        timeline_row.addWidget(self._loop_btn)

        # Frame ruler timeline
        self._frame_timeline = FrameRulerTimeline()
        self._frame_timeline.frame_clicked.connect(self._on_timeline_frame_clicked)
        self._frame_timeline.frame_dragged.connect(self._on_timeline_frame_clicked)
        self._frame_timeline.marker_clicked.connect(self._on_marker_clicked)
        timeline_row.addWidget(self._frame_timeline, 1)

        center_layout.addLayout(timeline_row)

        # Connect video frame changes to timeline
        self._video_preview.frame_changed.connect(self._on_video_frame_changed)

        self._splitter.addWidget(self._center_widget)

        # ===== RIGHT: Notes panel =====
        self._notes_panel = ReviewNotesPanel(
            fps=self._current_fps,
            is_studio_mode=self._is_studio_mode,
            current_user=self._current_user,
            current_user_role=self._current_user_role
        )
        self._notes_panel.setFixedWidth(320)

        # Connect notes panel signals
        self._notes_panel.note_clicked.connect(self._on_note_clicked)
        self._notes_panel.annotate_requested.connect(self._on_annotate_requested)
        self._notes_panel.note_added.connect(self._on_note_added)
        self._notes_panel.note_resolved.connect(self._on_note_resolve_toggled)
        self._notes_panel.note_deleted.connect(self._on_note_delete_requested)
        self._notes_panel.note_restored.connect(self._on_note_restore_requested)
        self._notes_panel.note_edited.connect(self._on_note_edit_saved)

        self._splitter.addWidget(self._notes_panel)

        # Comparison widget (hidden)
        self._comparison_widget = ComparisonWidget()
        self._comparison_widget.hide()
        self._splitter.addWidget(self._comparison_widget)

        # Disable splitter handles (no dragging - fixed layout)
        for i in range(self._splitter.count()):
            handle = self._splitter.handle(i)
            if handle:
                handle.setEnabled(False)
        layout.addWidget(self._splitter, 1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._set_latest_btn = QPushButton("Set as Latest")
        self._set_latest_btn.setEnabled(False)
        self._set_latest_btn.clicked.connect(self._on_set_as_latest)
        btn_layout.addWidget(self._set_latest_btn)

        self._apply_btn = QPushButton("Apply This Version")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply_version)
        btn_layout.addWidget(self._apply_btn)

        self._compare_btn = QPushButton("Compare")
        self._compare_btn.clicked.connect(self._toggle_compare_mode)
        btn_layout.addWidget(self._compare_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    # ==================== Thumbnails ====================

    def _load_thumbnail_async(self, uuid: str, thumbnail_path: str, row: int):
        if not thumbnail_path:
            return
        if uuid in self._thumbnail_cache:
            self._set_thumbnail_for_row(row, self._thumbnail_cache[uuid])
            return

        self._pending_thumbnails[uuid] = row
        task = ThumbnailTask(uuid, thumbnail_path, self.THUMBNAIL_SIZE)
        task.signals.loaded.connect(self._on_thumbnail_loaded)
        task.signals.failed.connect(self._on_thumbnail_failed)
        self._thread_pool.start(task)

    def _on_thumbnail_loaded(self, uuid: str, pixmap: QPixmap):
        self._thumbnail_cache[uuid] = pixmap
        if uuid in self._pending_thumbnails:
            row = self._pending_thumbnails.pop(uuid)
            self._set_thumbnail_for_row(row, pixmap)

    def _on_thumbnail_failed(self, uuid: str):
        self._pending_thumbnails.pop(uuid, None)

    def _set_thumbnail_for_row(self, row: int, pixmap: QPixmap):
        if 0 <= row < self._table.rowCount():
            item = self._table.item(row, 0)
            if item:
                item.setIcon(QIcon(pixmap))

    # ==================== Version Loading ====================

    def _load_versions(self):
        self._versions = self._db_service.get_version_history(self._version_group_id)

        if not self._versions:
            self._name_label.setText("No versions found")
            return

        # Resolve actual paths for each version (checks hot + cold storage)
        for version in self._versions:
            # Resolve thumbnail path
            resolved_thumb = self._db_service.animations.resolve_thumbnail_file(version)
            if resolved_thumb:
                version['thumbnail_path'] = str(resolved_thumb)

            # Resolve preview path
            resolved_preview = self._db_service.animations.resolve_preview_file(version)
            if resolved_preview:
                version['preview_path'] = str(resolved_preview)

        self._name_label.setText(f"Animation: {self._versions[0].get('name', 'Unknown')}")
        self._table.setRowCount(len(self._versions))

        for row, version in enumerate(self._versions):
            uuid = version.get('uuid', '')
            self._table.setRowHeight(row, self.THUMBNAIL_SIZE + 8)

            thumb_item = QTableWidgetItem()
            thumb_item.setData(Qt.ItemDataRole.UserRole, uuid)
            self._table.setItem(row, 0, thumb_item)

            self._load_thumbnail_async(uuid, version.get('thumbnail_path', ''), row)

            version_label = version.get('version_label', 'v001')
            version_item = QTableWidgetItem(version_label)
            version_item.setData(Qt.ItemDataRole.UserRole, uuid)
            self._table.setItem(row, 1, version_item)

            is_latest = version.get('is_latest', 0)
            latest_item = QTableWidgetItem("●" if is_latest else "")
            if is_latest:
                latest_item.setForeground(QColor("#4CAF50"))
            self._table.setItem(row, 2, latest_item)

            status = version.get('status', 'none')
            status_info = Config.LIFECYCLE_STATUSES.get(status, {'label': status.upper(), 'color': '#888'})
            status_item = QTableWidgetItem(status_info['label'])
            color = status_info.get('color') or '#888'
            status_item.setForeground(QColor(color))
            self._table.setItem(row, 3, status_item)

            frames = version.get('frame_count')
            self._table.setItem(row, 4, QTableWidgetItem(str(frames) if frames else '-'))

        # Select latest
        for row, version in enumerate(self._versions):
            if version.get('is_latest', 0):
                self._table.selectRow(row)
                break

    # ==================== Selection ====================

    def _on_selection_changed(self):
        if self._compare_mode:
            self._on_compare_selection_changed()
            return

        selected = self._table.selectedItems()
        if selected:
            row = selected[0].row()
            self._selected_uuid = self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self._selected_version_label = self._versions[row].get('version_label', 'v001')

            is_latest = self._versions[row].get('is_latest', 0)
            self._set_latest_btn.setEnabled(not is_latest)
            self._apply_btn.setEnabled(True)

            self._update_preview(row)
        else:
            self._selected_uuid = None
            self._selected_version_label = None
            self._set_latest_btn.setEnabled(False)
            self._apply_btn.setEnabled(False)
            self._video_preview.clear()
            self._preview_info_label.setText("Select a version to preview")
            self._frame_timeline.set_total_frames(1)
            self._clear_notes()
            # Clear drawover
            self._drawover_canvas.clear()
            self._drawover_canvas.hide()
            self._current_drawover_frame = -1

    def _update_preview(self, row: int):
        if row < 0 or row >= len(self._versions):
            return

        version = self._versions[row]
        version_label = version.get('version_label', 'v001')
        status = version.get('status', 'none')
        status_info = Config.LIFECYCLE_STATUSES.get(status, {'label': status})

        # Info label
        is_latest = "Latest" if version.get('is_latest', 0) else ""
        info_parts = [version_label]
        if is_latest:
            info_parts.append(is_latest)
        if status != 'none':
            info_parts.append(status_info.get('label', status))
        self._preview_info_label.setText(" | ".join(info_parts))

        # Load video
        preview_path = version.get('preview_path', '')
        if preview_path and Path(preview_path).exists():
            self._video_preview.load_video(preview_path)
        else:
            self._video_preview.clear()

        # Store video info
        self._current_fps = version.get('fps', 24) or 24
        self._total_frames = version.get('frame_count', 0) or 0

        # Update timeline
        self._frame_timeline.set_total_frames(max(1, self._total_frames))
        self._frame_timeline.set_current_frame(0)

        # Reset annotate mode when switching versions
        self._drawover_enabled = False
        self._done_annotate_btn.hide()
        self._annotation_toolbar.hide()

        # Setup drawover canvas for this version (view-only mode for existing annotations)
        self._current_drawover_frame = -1  # Reset to force load
        self._drawover_canvas.read_only = True
        self._drawover_canvas.set_tool(DrawingTool.NONE)
        self._position_drawover_canvas()
        self._drawover_canvas.show()
        self._load_drawover_for_frame(0)

        # Load review notes
        self._load_review_notes()

    def _load_playback_icons(self):
        """Load media control icons matching video preview widget."""
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#1a1a1a"

        self._play_icon = colorize_white_svg(IconLoader.get("play"), icon_color)
        self._pause_icon = colorize_white_svg(IconLoader.get("pause"), icon_color)
        self._loop_icon = colorize_white_svg(IconLoader.get("loop"), icon_color)

    def _on_video_frame_changed(self, frame: int):
        """Sync timeline with video playback."""
        self._frame_timeline.set_current_frame(frame)
        # Update play button icon based on playing state
        self._update_play_button_icon()

        # Update notes panel current frame
        self._notes_panel.set_current_frame(frame)

        # Load drawover for new frame (show annotations even when not editing)
        if frame != self._current_drawover_frame:
            self._load_drawover_for_frame(frame)

    def _update_play_button_icon(self):
        """Update play button icon based on playback state."""
        if self._video_preview.is_playing:
            self._play_btn.setIcon(self._pause_icon)
        else:
            self._play_btn.setIcon(self._play_icon)

    def _on_play_clicked(self):
        """Toggle video playback."""
        self._video_preview.toggle_playback()
        self._update_play_button_icon()

    def _on_loop_clicked(self):
        """Toggle loop mode."""
        self._video_preview.set_loop(self._loop_btn.isChecked())

    def _on_timeline_frame_clicked(self, frame: int):
        """Seek video when timeline is clicked."""
        if hasattr(self._video_preview, 'seek_to_frame'):
            self._video_preview.seek_to_frame(frame)
        # Ensure timeline playhead is synced
        self._frame_timeline.set_current_frame(frame)

    def _on_marker_clicked(self, frame: int, note_id: int):
        """Handle click on a timeline marker - seek to frame."""
        # Seek video and update timeline
        if hasattr(self._video_preview, 'seek_to_frame'):
            self._video_preview.seek_to_frame(frame)
        self._frame_timeline.set_current_frame(frame)

    # ==================== Review Notes ====================

    def _on_show_deleted_toggled(self, checked: bool):
        """Handle show deleted checkbox toggle."""
        self._show_deleted = checked
        self._load_review_notes()

    def _load_review_notes(self):
        """Load review notes for the selected version."""
        if not self._selected_uuid or not self._selected_version_label:
            self._review_notes = []
            self._notes_panel.set_notes([])
            return

        self._review_notes = self._notes_db.get_notes_for_version(
            self._selected_uuid,
            self._selected_version_label,
            include_deleted=self._show_deleted
        )

        # Update timeline markers (only show non-deleted notes on timeline)
        active_notes = [n for n in self._review_notes if not n.get('deleted', 0)]
        self._frame_timeline.set_notes(active_notes)

        # Update notes panel
        self._notes_panel.set_notes(self._review_notes)

    def _clear_notes(self):
        """Clear all notes."""
        self._review_notes = []
        self._notes_panel.clear()

    def _on_note_added(self, frame: int, text: str):
        """Add a new note at the given frame."""
        if not text:
            return

        if not self._selected_uuid or not self._selected_version_label:
            QMessageBox.warning(self, "Error", "No version selected.")
            return

        # Include author info in Studio Mode
        note_id = self._notes_db.add_note(
            self._selected_uuid,
            self._selected_version_label,
            frame,
            text,
            author=self._current_user if self._is_studio_mode else '',
            author_role=self._current_user_role if self._is_studio_mode else 'artist'
        )

        if note_id:
            self._load_review_notes()
        else:
            QMessageBox.warning(self, "Error", "Failed to add note.")

    def _on_note_clicked(self, frame: int):
        """Seek to note's frame and update timeline."""
        if hasattr(self._video_preview, 'seek_to_frame'):
            self._video_preview.seek_to_frame(frame)
        # Update timeline playhead
        self._frame_timeline.set_current_frame(frame)

    def _on_annotate_requested(self, frame: int, note_id: int):
        """
        Handle request to annotate a specific frame.

        Jumps to the frame and enters annotate mode.
        """
        # Seek to frame
        if hasattr(self._video_preview, 'seek_to_frame'):
            self._video_preview.seek_to_frame(frame)
        self._frame_timeline.set_current_frame(frame)

        # Enter annotation mode for this frame
        self._enter_drawover_mode_for_frame(frame)

    def _enter_drawover_mode_for_frame(self, frame: int):
        """Enter annotation/drawover mode for a specific frame."""
        # Pause video
        if self._video_preview.is_playing:
            self._video_preview.toggle_playback()
            self._update_play_button_icon()

        # Enable drawover mode
        self._drawover_enabled = True
        self._done_annotate_btn.show()
        self._annotation_toolbar.show()

        # Position canvas and show it
        self._position_drawover_canvas()
        self._drawover_canvas.show()
        self._drawover_canvas.read_only = False
        self._drawover_canvas.set_tool(DrawingTool.PEN)

        # Load existing drawover for this frame if any
        self._load_drawover_for_frame(frame)

    def _on_note_resolve_toggled(self, note_id: int, new_resolved: bool):
        """Toggle note resolved status."""
        if self._notes_db.set_note_resolved(note_id, new_resolved):
            self._load_review_notes()
        else:
            QMessageBox.warning(self, "Error", "Failed to update note.")

    def _on_note_delete_requested(self, note_id: int):
        """Delete a note (soft delete with audit trail)."""
        reply = QMessageBox.question(
            self, "Delete Note", "Delete this review note?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Use soft delete with actor info
            success = self._notes_db.soft_delete_note(
                note_id,
                deleted_by=self._current_user if self._is_studio_mode else 'user',
                actor_role=self._current_user_role if self._is_studio_mode else ''
            )
            if success:
                self._load_review_notes()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete note.")

    def _on_note_restore_requested(self, note_id: int):
        """Restore a soft-deleted note."""
        success = self._notes_db.restore_note(
            note_id,
            restored_by=self._current_user if self._is_studio_mode else 'user',
            actor_role=self._current_user_role if self._is_studio_mode else ''
        )
        if success:
            self._load_review_notes()
        else:
            QMessageBox.warning(self, "Error", "Failed to restore note.")

    def _on_note_edit_saved(self, note_id: int, new_text: str):
        """Save edited note with audit trail."""
        success = self._notes_db.update_note(
            note_id,
            new_text,
            actor=self._current_user if self._is_studio_mode else '',
            actor_role=self._current_user_role if self._is_studio_mode else ''
        )
        if success:
            self._load_review_notes()
        else:
            QMessageBox.warning(self, "Error", "Failed to update note.")

    # ==================== Actions ====================

    def _on_double_click(self, item):
        self._on_apply_version()

    def _on_set_as_latest(self):
        if not self._selected_uuid:
            return
        reply = QMessageBox.question(
            self, "Set as Latest",
            "Set this version as the latest?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._db_service.set_version_as_latest(self._selected_uuid):
                self.version_set_as_latest.emit(self._selected_uuid)
                self._load_versions()
            else:
                QMessageBox.warning(self, "Error", "Failed to set version as latest.")

    def _on_apply_version(self):
        if self._selected_uuid:
            self.version_selected.emit(self._selected_uuid)
            self.accept()

    def get_selected_uuid(self) -> Optional[str]:
        return self._selected_uuid

    # ==================== Compare Mode ====================

    def _toggle_compare_mode(self):
        if self._compare_mode:
            self._exit_compare_mode()
        else:
            self._enter_compare_mode()

    def _enter_compare_mode(self):
        # Exit drawover mode if active
        if self._drawover_enabled:
            self._exit_drawover_mode()

        # Hide drawover canvas in compare mode
        self._drawover_canvas.hide()

        self._compare_mode = True
        self._compare_selections = []

        self._compare_btn.setText("Exit Compare")
        self._compare_btn.setStyleSheet("background-color: #3A8FB7;")

        self._table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._table.clearSelection()

        self._set_latest_btn.setEnabled(False)
        self._apply_btn.setEnabled(False)

        self._preview_info_label.setText("Select 2 versions to compare")

        # Hide notes panel and shrink table
        self._notes_panel.hide()
        self._table_container.setFixedWidth(self.TABLE_WIDTH_COMPARE)

    def _exit_compare_mode(self):
        self._compare_mode = False
        self._compare_selections = []

        self._compare_btn.setText("Compare")
        self._compare_btn.setStyleSheet("")

        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.clearSelection()

        self._comparison_widget.hide()
        self._comparison_widget.clear()
        self._center_widget.show()
        self._notes_panel.show()

        # Restore table width
        self._table_container.setFixedWidth(self.TABLE_WIDTH_NORMAL)

    def _on_compare_selection_changed(self):
        try:
            selected_items = self._table.selectedItems()
            selected_rows = []
            seen = set()
            for item in selected_items:
                row = item.row()
                if row not in seen:
                    seen.add(row)
                    uuid = self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                    if uuid:
                        selected_rows.append((row, uuid))

            if len(selected_rows) > 2:
                self._table.blockSignals(True)
                self._table.clearSelection()
                for row, uuid in selected_rows[:2]:
                    for col in range(self._table.columnCount()):
                        item = self._table.item(row, col)
                        if item:
                            item.setSelected(True)
                self._table.blockSignals(False)
                self._compare_selections = [uuid for _, uuid in selected_rows[:2]]
            else:
                self._compare_selections = [uuid for _, uuid in selected_rows]

            if len(self._compare_selections) == 2:
                self._show_comparison()
            else:
                self._comparison_widget.hide()
                self._center_widget.show()
                count_needed = 2 - len(self._compare_selections)
                self._preview_info_label.setText(f"Select {count_needed} more version(s)")
        except Exception as e:
            print(f"Compare error: {e}")

    def _show_comparison(self):
        if len(self._compare_selections) != 2:
            return

        version_a = next((v for v in self._versions if v.get('uuid') == self._compare_selections[0]), None)
        version_b = next((v for v in self._versions if v.get('uuid') == self._compare_selections[1]), None)

        if version_a and version_b:
            # Load notes for each version
            notes_a = []
            notes_b = []

            if self._notes_db:
                label_a = version_a.get('version_label', '')
                label_b = version_b.get('version_label', '')
                uuid_a = version_a.get('uuid', '')
                uuid_b = version_b.get('uuid', '')

                if uuid_a and label_a:
                    notes_a = self._notes_db.get_notes_for_version(uuid_a, label_a)
                if uuid_b and label_b:
                    notes_b = self._notes_db.get_notes_for_version(uuid_b, label_b)

            self._center_widget.hide()
            self._comparison_widget.show()
            self._comparison_widget.set_versions(version_a, version_b, notes_a, notes_b)

    # ==================== Drawover Mode ====================

    def _enter_drawover_mode(self):
        """Enable drawover annotation mode."""
        self._drawover_enabled = True
        self._done_annotate_btn.show()
        self._annotation_toolbar.show()

        # Position drawover canvas over video
        self._position_drawover_canvas()

        # Show canvas and set default tool (enable editing)
        self._drawover_canvas.show()
        self._drawover_canvas.read_only = False
        self._drawover_canvas.set_tool(DrawingTool.PEN)
        self._drawover_canvas.color = self._annotation_toolbar.current_color
        self._annotation_toolbar.set_tool(DrawingTool.PEN)

        # Pause video while annotating
        if self._video_preview.is_playing:
            self._video_preview.toggle_playback()
            self._update_play_button_icon()

        # Load drawover for current frame
        self._load_drawover_for_frame(self._video_preview.current_frame)

    def _exit_drawover_mode(self):
        """Disable drawover annotation mode."""
        # Save current frame's drawover before exiting
        self._save_current_drawover()

        self._drawover_enabled = False
        self._done_annotate_btn.hide()
        self._annotation_toolbar.hide()

        # Reload frame to update canvas visibility (only show if has saved annotations)
        current_frame = self._video_preview.current_frame
        self._load_drawover_for_frame(current_frame)

    def _position_drawover_canvas(self):
        """
        Position drawover canvas over video content area only.

        This ensures:
        - Canvas covers only actual video content (not letterbox bars)
        - Canvas video rect is set for UV coordinate conversion
        """
        video_label = self._video_preview.video_label
        self._drawover_canvas.setParent(video_label)

        # Get actual video content rect (excluding letterbox)
        video_rect = self._video_preview.get_video_display_rect()

        if video_rect and video_rect.isValid():
            # Position canvas at video content area
            self._drawover_canvas.setGeometry(video_rect)
            # Set video rect for UV coordinate conversion (in canvas-local coords)
            from PyQt6.QtCore import QRectF
            local_rect = QRectF(0, 0, video_rect.width(), video_rect.height())
            self._drawover_canvas.set_video_rect(local_rect)
        else:
            # Fallback: cover entire label
            self._drawover_canvas.setGeometry(0, 0, video_label.width(), video_label.height())
            from PyQt6.QtCore import QRectF
            self._drawover_canvas.set_video_rect(QRectF(0, 0, video_label.width(), video_label.height()))

        self._drawover_canvas.raise_()

    def resizeEvent(self, event):
        """Handle resize - reposition canvas and refresh strokes."""
        super().resizeEvent(event)
        if hasattr(self, '_drawover_canvas') and self._drawover_canvas.isVisible():
            # Delay to allow layout to update
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self._on_resize_complete)

    def _on_resize_complete(self):
        """Called after resize to update canvas position."""
        self._position_drawover_canvas()
        # Refresh strokes to recalculate screen positions from UV
        self._drawover_canvas.refresh_strokes()

    def _load_drawover_for_frame(self, frame: int):
        """Load drawover data for a specific frame."""
        if not self._selected_uuid or not self._selected_version_label:
            return

        # Save previous frame's drawover first (only if in edit mode)
        if self._drawover_enabled and self._current_drawover_frame >= 0 and self._current_drawover_frame != frame:
            self._save_current_drawover()

        self._current_drawover_frame = frame

        # Check cache first
        cached = self._drawover_cache.get(
            self._selected_uuid,
            self._selected_version_label,
            frame
        )

        if cached:
            strokes = cached.get('strokes', [])
            canvas_size = cached.get('canvas_size')
        else:
            # Load from storage
            data = self._drawover_storage.load_drawover(
                self._selected_uuid,
                self._selected_version_label,
                frame
            )
            if data:
                strokes = data.get('strokes', [])
                canvas_size = data.get('canvas_size')
                self._drawover_cache.put(
                    self._selected_uuid,
                    self._selected_version_label,
                    frame,
                    data
                )
            else:
                strokes = []
                canvas_size = None

        # Reposition canvas to match current video rect
        self._position_drawover_canvas()

        # Import strokes to canvas
        source_size = tuple(canvas_size) if canvas_size else None
        self._drawover_canvas.import_strokes(strokes, source_size)

        # Control canvas visibility based on mode and data
        if self._drawover_enabled:
            # In annotate mode - always show canvas (editable)
            self._drawover_canvas.show()
            self._drawover_canvas.read_only = False
        elif strokes:
            # Not in annotate mode but has saved annotations - show read-only
            self._drawover_canvas.show()
            self._drawover_canvas.read_only = True
            self._drawover_canvas.set_tool(DrawingTool.NONE)
        else:
            # No annotations and not in annotate mode - hide canvas
            self._drawover_canvas.hide()

        # Update undo/redo button states
        self._update_drawover_buttons()

    def _save_current_drawover(self):
        """Save current frame's drawover to storage."""
        if self._current_drawover_frame < 0 or not self._selected_uuid or not self._selected_version_label:
            return

        strokes = self._drawover_canvas.export_strokes()

        if strokes:
            # Get canvas size from video label (which matches video content exactly)
            video_label = self._video_preview.video_label
            canvas_size = (
                video_label.width(),
                video_label.height()
            )

            success = self._drawover_storage.save_drawover(
                self._selected_uuid,
                self._selected_version_label,
                self._current_drawover_frame,
                strokes,
                author=self._current_user,
                canvas_size=canvas_size
            )

            if success:
                # Update cache
                self._drawover_cache.invalidate(
                    self._selected_uuid,
                    self._selected_version_label,
                    self._current_drawover_frame
                )

                # Log action if in studio mode
                if self._is_studio_mode:
                    self._notes_db.log_drawover_action(
                        self._selected_uuid,
                        self._selected_version_label,
                        self._current_drawover_frame,
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
                    self._current_drawover_frame,
                    len(strokes),
                    ','.join(authors)
                )

    def _on_drawover_modified(self):
        """Handle drawover canvas modification."""
        self._update_drawover_buttons()

    def _on_tool_selected(self, tool: DrawingTool):
        """Handle tool selection from compact toolbar."""
        self._drawover_canvas.set_tool(tool)

    def _on_draw_color_changed(self, color: QColor):
        """Handle color change from ColorPicker widget."""
        self._drawover_canvas.color = color

    def _on_drawover_undo(self):
        """Undo last stroke."""
        self._drawover_canvas.undo_stack.undo()
        self._update_drawover_buttons()

    def _on_drawover_redo(self):
        """Redo last undone stroke."""
        self._drawover_canvas.undo_stack.redo()
        self._update_drawover_buttons()

    def _on_drawover_clear(self):
        """Clear all strokes on current frame."""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Clear Annotations",
            "Clear all annotations on this frame?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Check permissions for clearing in studio mode
            if self._is_studio_mode:
                strokes = self._drawover_canvas.export_strokes()
                has_others = any(
                    s.get('author', '') and s.get('author') != self._current_user
                    for s in strokes
                )
                if not DrawoverPermissions.can_clear_frame(
                    self._is_studio_mode,
                    self._current_user_role,
                    has_others
                ):
                    QMessageBox.warning(
                        self,
                        "Permission Denied",
                        "You don't have permission to clear annotations from other users."
                    )
                    return

            self._drawover_canvas.clear()
            self._update_drawover_buttons()

            # Clear from storage
            if self._selected_uuid and self._selected_version_label:
                soft_delete = DrawoverPermissions.use_soft_delete(self._is_studio_mode)
                self._drawover_storage.clear_frame(
                    self._selected_uuid,
                    self._selected_version_label,
                    self._current_drawover_frame,
                    soft_delete=soft_delete,
                    deleted_by=self._current_user
                )

                # Invalidate cache for this frame
                self._drawover_cache.invalidate(
                    self._selected_uuid,
                    self._selected_version_label,
                    self._current_drawover_frame
                )

                # Log action
                if self._is_studio_mode:
                    self._notes_db.log_drawover_action(
                        self._selected_uuid,
                        self._selected_version_label,
                        self._current_drawover_frame,
                        'cleared',
                        self._current_user,
                        self._current_user_role
                    )

    def _update_drawover_buttons(self):
        """Update undo/redo button enabled states."""
        if hasattr(self, '_annotation_toolbar'):
            self._annotation_toolbar.set_undo_enabled(self._drawover_canvas.undo_stack.canUndo())
            self._annotation_toolbar.set_redo_enabled(self._drawover_canvas.undo_stack.canRedo())

    def closeEvent(self, event):
        # Save any pending drawover changes
        if self._drawover_enabled:
            self._save_current_drawover()

        self._video_preview.clear()
        self._comparison_widget.clear()
        super().closeEvent(event)


__all__ = ['VersionHistoryDialog']
