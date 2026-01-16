"""
AnimationView - QListView for animations

Pattern: QListView with Model/View architecture
Inspired by: Hybrid plan + Maya Studio Library
"""

import os
from typing import Optional
from PyQt6.QtWidgets import QListView, QAbstractItemView
from PyQt6.QtCore import Qt, QTimer, QModelIndex, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent, QPainter, QColor, QFont

from .animation_card_delegate import AnimationCardDelegate
from ..models.animation_list_model import AnimationRole
from ..services.database_service import get_database_service
from ..services.socket_client import get_socket_client
from ..events.event_bus import get_event_bus
from ..widgets.hover_video_popup import HoverVideoPopup
from ..config import Config


class AnimationView(QListView):
    """
    View for displaying animations in grid or list mode

    Features:
    - Grid/list mode switching
    - Virtual scrolling (only renders visible items)
    - Hover detection
    - Selection handling (single/multi)
    - Drag & drop support
    - Async thumbnail loading via delegate
    - Event bus integration
    - Pose blending via right-click drag

    Usage:
        view = AnimationView()
        view.setModel(animation_filter_proxy_model)
        view.set_view_mode("grid")
    """

    # Signals
    # animation_uuid, mirror, use_slots, insert_at_playhead
    animation_double_clicked = pyqtSignal(str, bool, bool, bool)
    animation_context_menu = pyqtSignal(str, QPoint)  # animation_uuid, position
    hover_started = pyqtSignal(str, QPoint)  # animation_uuid, position
    hover_ended = pyqtSignal()

    def __init__(self, parent=None, db_service=None, event_bus=None,
                 thumbnail_loader=None, theme_manager=None):
        super().__init__(parent)

        # Services (injectable for testing)
        self._event_bus = event_bus or get_event_bus()
        self._db_service = db_service or get_database_service()

        # View mode
        self._view_mode = Config.DEFAULT_VIEW_MODE
        self._card_size = Config.DEFAULT_CARD_SIZE

        # Delegate (pass through DI services)
        self._delegate = AnimationCardDelegate(
            self, view_mode=self._view_mode,
            db_service=self._db_service,
            thumbnail_loader=thumbnail_loader,
            theme_manager=theme_manager
        )
        self.setItemDelegate(self._delegate)

        # Hover tracking
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._on_hover_timeout)
        self._hover_index: Optional[QModelIndex] = None
        self._last_hover_pos = QPoint()

        # Hover video popup (lazy loading - only create when first needed)
        self._hover_popup: Optional[HoverVideoPopup] = None

        # Pose blending state
        self._blend_active = False
        self._blend_just_ended = False  # Prevents context menu after blend
        self._blend_start_x = 0
        self._blend_factor = 0.0
        self._blend_mirror = False
        self._blend_pose_name = ""
        self._blend_sensitivity = Config.BLEND_SENSITIVITY_PIXELS

        # Setup view
        self._setup_view()
        self._connect_signals()

    def _setup_view(self):
        """Configure view settings"""

        # Remove default margins for tight-packed grid
        self.setContentsMargins(0, 0, 0, 0)
        self.setViewportMargins(0, 0, 0, 0)

        # Virtual scrolling for performance
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        # Uniform item sizes for better performance
        self.setUniformItemSizes(True)

        # Selection
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)

        # Drag & drop
        if Config.ENABLE_DRAG_DROP:
            self.setDragEnabled(True)
            self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

        # Mouse tracking for hover
        self.setMouseTracking(True)

        # Performance: No alternating colors, we handle in delegate
        self.setAlternatingRowColors(False)

        # Apply view mode
        self._apply_view_mode()

    def _connect_signals(self):
        """Connect internal signals"""

        # Double click
        self.doubleClicked.connect(self._on_double_clicked)

        # Event bus signals
        self._event_bus.view_mode_changed.connect(self.set_view_mode)
        self._event_bus.card_size_changed.connect(self.set_card_size)
        self._event_bus.edit_mode_changed.connect(self._delegate.set_edit_mode)

    def setModel(self, model):
        """Override setModel to connect selection signal"""
        # Disconnect from old model's selection
        old_selection_model = self.selectionModel()
        if old_selection_model:
            try:
                old_selection_model.selectionChanged.disconnect(self._on_selection_changed)
            except:
                pass

        # Set new model
        super().setModel(model)

        # Connect to new selection model
        new_selection_model = self.selectionModel()
        if new_selection_model:
            new_selection_model.selectionChanged.connect(self._on_selection_changed)

    def set_view_mode(self, mode: str):
        """
        Set view mode

        Args:
            mode: "grid" or "list"
        """
        if mode == self._view_mode:
            return

        if mode not in ("grid", "list"):
            return

        self._view_mode = mode
        self._delegate.set_view_mode(mode)
        self._apply_view_mode()

        # Trigger repaint
        self.viewport().update()

    def set_card_size(self, size: int):
        """
        Set card size for grid mode

        Args:
            size: Size in pixels
        """
        self._card_size = size
        self._delegate.set_card_size(size)

        if self._view_mode == "grid":
            self._apply_view_mode()
            self.viewport().update()

    def _apply_view_mode(self):
        """Apply view mode configuration"""

        if self._view_mode == "grid":
            # Grid mode: IconMode with flow, wrapping
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setFlow(QListView.Flow.LeftToRight)
            self.setWrapping(True)
            self.setResizeMode(QListView.ResizeMode.Adjust)
            self.setSpacing(0)  # Tight grid: cards touching for sleek minimalistic look
            self.setGridSize(self._delegate.sizeHint(None, QModelIndex()))
            # IconMode uses Snap movement by default
            self.setMovement(QListView.Movement.Snap)

        else:
            # List mode: ListMode, no wrapping
            self.setViewMode(QListView.ViewMode.ListMode)
            self.setFlow(QListView.Flow.TopToBottom)
            self.setWrapping(False)
            self.setSpacing(0)  # No spacing - rows touch (like grid mode)
            # Reset grid size to use delegate's sizeHint for list mode
            self.setGridSize(QSize(-1, -1))  # -1 = use sizeHint
            # ListMode defaults to Static, but we need Snap for drag to work
            self.setMovement(QListView.Movement.Snap)

        # Re-enable drag after mode change (setViewMode can reset settings)
        if Config.ENABLE_DRAG_DROP:
            self.setDragEnabled(True)
            self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

        # Force layout recalculation after mode change
        self.scheduleDelayedItemsLayout()

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for pose blending"""

        # Left-click cancels active blend
        if event.button() == Qt.MouseButton.LeftButton and self._blend_active:
            self._cancel_pose_blend()
            event.accept()
            return

        # Check for right-click on a pose to start blend
        if event.button() == Qt.MouseButton.RightButton:
            index = self.indexAt(event.pos())
            if index.isValid():
                # Check if this is a pose (not an animation)
                is_pose = index.data(AnimationRole.IsPoseRole)
                if is_pose:
                    # Start pose blend
                    if self._start_pose_blend(index, event.pos()):
                        event.accept()
                        return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for hover detection and pose blending"""

        # Handle pose blending
        if self._blend_active:
            self._update_pose_blend(event.pos())
            event.accept()
            return

        super().mouseMoveEvent(event)

        if not Config.ENABLE_HOVER_VIDEO:
            return

        # Get index under mouse
        index = self.indexAt(event.pos())

        if index.isValid():
            if index != self._hover_index:
                # New item hovered
                self._hover_index = index
                self._last_hover_pos = event.pos()
                self._hover_timer.start(Config.HOVER_VIDEO_DELAY_MS)
        else:
            # No item under mouse
            if self._hover_index:
                self._hover_index = None
                self._hover_timer.stop()
                self.hover_ended.emit()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release for pose blending"""

        if event.button() == Qt.MouseButton.RightButton and self._blend_active:
            self._end_pose_blend()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press for pose blending cancel"""

        if event.key() == Qt.Key.Key_Escape and self._blend_active:
            self._cancel_pose_blend()
            event.accept()
            return

        super().keyPressEvent(event)

    def paintEvent(self, event):
        """Override paint event to draw blend overlay"""
        super().paintEvent(event)

        if self._blend_active:
            self._draw_blend_overlay()

    def _start_pose_blend(self, index: QModelIndex, pos: QPoint) -> bool:
        """
        Start pose blend session

        Args:
            index: Model index of the pose
            pos: Mouse position

        Returns:
            True if blend started successfully
        """
        uuid = index.data(AnimationRole.UUIDRole)
        name = index.data(AnimationRole.NameRole)
        blend_path = index.data(AnimationRole.BlendFilePathRole)

        if not uuid or not blend_path:
            return False

        # Send blend start to Maya
        client = get_socket_client()
        response = client.blend_pose_start(uuid, name, blend_path)

        if response.get('status') != 'success':
            print(f"[AnimationView] Failed to start blend: {response.get('message')}")
            return False

        # Initialize blend state
        self._blend_active = True
        self._blend_start_x = pos.x()
        self._blend_factor = 0.0
        self._blend_mirror = False
        self._blend_pose_name = name or "Pose"

        # Grab focus for keyboard (Escape key)
        self.setFocus()

        print(f"[AnimationView] Blend started: {name}, start_x={pos.x()}")

        # Force repaint to show overlay
        self.viewport().update()

        return True

    def _update_pose_blend(self, pos: QPoint):
        """
        Update pose blend based on mouse position

        Args:
            pos: Current mouse position
        """
        # Calculate blend factor from horizontal mouse movement
        delta_x = pos.x() - self._blend_start_x
        self._blend_factor = max(0.0, min(1.0, delta_x / self._blend_sensitivity))
        print(f"[AnimationView] Blend update: pos.x={pos.x()}, start_x={self._blend_start_x}, delta={delta_x}, factor={self._blend_factor:.2f}")

        # Check for Ctrl modifier for mirror
        modifiers = self.cursor().pos()  # Dummy call to get modifiers working
        from PyQt6.QtWidgets import QApplication
        self._blend_mirror = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)

        # Send blend update to Maya
        client = get_socket_client()
        client.blend_pose(self._blend_factor, self._blend_mirror)

        # Force repaint to update overlay
        self.viewport().update()

    def _end_pose_blend(self):
        """End pose blend session"""

        if not self._blend_active:
            return

        # Send blend end to Blender
        client = get_socket_client()
        client.blend_pose_end()

        # Reset blend state
        self._blend_active = False
        self._blend_just_ended = True  # Prevent context menu
        self._blend_start_x = 0
        self._blend_factor = 0.0
        self._blend_mirror = False
        self._blend_pose_name = ""

        print(f"[AnimationView] Blend ended")

        # Force repaint to remove overlay
        self.viewport().update()

    def _cancel_pose_blend(self):
        """Cancel pose blend and restore original pose"""
        if not self._blend_active:
            return

        print(f"[AnimationView] Blend cancelled")

        # Send cancel to Blender (cancelled=True restores original)
        client = get_socket_client()
        client.blend_pose_end(cancelled=True)

        # Reset blend state
        self._blend_active = False
        self._blend_just_ended = True  # Prevent context menu
        self._blend_start_x = 0
        self._blend_factor = 0.0
        self._blend_mirror = False
        self._blend_pose_name = ""

        # Force repaint to remove overlay
        self.viewport().update()

    def _draw_blend_overlay(self):
        """Draw sharp blend progress overlay at top center"""
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QPen

        painter = QPainter(self.viewport())

        viewport_rect = self.viewport().rect()
        percentage = int(self._blend_factor * 100)

        # Box dimensions
        box_width = 240
        box_height = 52
        box_x = (viewport_rect.width() - box_width) // 2
        box_y = 16

        box_rect = QRectF(box_x, box_y, box_width, box_height)

        # Sharp background
        painter.fillRect(box_rect, QColor(25, 25, 30, 245))

        # Thin progress bar at bottom
        progress_height = 3
        progress_y = box_y + box_height - progress_height
        progress_bg = QRectF(box_x, progress_y, box_width, progress_height)
        painter.fillRect(progress_bg, QColor(50, 50, 60))

        # Progress fill
        if self._blend_factor > 0:
            fill_width = box_width * self._blend_factor
            progress_fill = QRectF(box_x, progress_y, fill_width, progress_height)
            fill_color = QColor(100, 160, 255) if self._blend_mirror else QColor(80, 200, 120)
            painter.fillRect(progress_fill, fill_color)

        # Percentage text (large)
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)

        pct_rect = QRectF(box_x, box_y + 6, box_width, 24)
        painter.drawText(pct_rect, Qt.AlignmentFlag.AlignCenter, f"{percentage}%")

        # Pose name
        name_font = QFont()
        name_font.setPointSize(9)
        painter.setFont(name_font)
        painter.setPen(QColor(140, 140, 150))

        mirror_text = " [M]" if self._blend_mirror else ""
        name_rect = QRectF(box_x, box_y + 26, box_width, 16)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter, f"{self._blend_pose_name}{mirror_text}")

        # Border
        painter.setPen(QPen(QColor(60, 60, 70), 1))
        painter.drawRect(box_rect)

        painter.end()

    def leaveEvent(self, event):
        """Handle mouse leaving view"""

        super().leaveEvent(event)

        if self._hover_index:
            self._hover_index = None
            self._hover_timer.stop()
            self.hover_ended.emit()

            # Hide hover video popup
            if Config.ENABLE_HOVER_VIDEO and self._hover_popup:
                self._hover_popup.hide_preview()

    def _on_hover_timeout(self):
        """Handle hover timer timeout"""

        if not self._hover_index or not self._hover_index.isValid():
            return

        uuid = self._hover_index.data(AnimationRole.UUIDRole)
        if uuid:
            # Get global position
            global_pos = self.viewport().mapToGlobal(self._last_hover_pos)
            self.hover_started.emit(uuid, global_pos)

            # Show hover video popup if enabled
            if Config.ENABLE_HOVER_VIDEO:
                self._show_hover_video_popup()

    def _on_double_clicked(self, index: QModelIndex):
        """Handle double click and track last viewed

        Modifier keys:
        - Ctrl = mirror animation/pose
        - Shift = use action slots (actions only)
        - Alt = insert at playhead instead of new action (actions only)
        """
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt

        if not index.isValid():
            return

        uuid = index.data(AnimationRole.UUIDRole)
        if uuid:
            # Update last viewed (double-click is a strong viewing signal)
            self._db_service.update_last_viewed(uuid)

            # Check modifiers
            modifiers = QApplication.keyboardModifiers()
            mirror = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
            use_slots = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
            insert_at_playhead = bool(modifiers & Qt.KeyboardModifier.AltModifier)

            self.animation_double_clicked.emit(uuid, mirror, use_slots, insert_at_playhead)

            # Update event bus
            self._event_bus.set_selected_animation(uuid)

    def _on_selection_changed(self, selected, deselected):
        """Handle selection changes and track last viewed"""

        # Get all selected UUIDs
        selected_indexes = self.selectionModel().selectedIndexes()
        selected_uuids = set()

        for index in selected_indexes:
            uuid = index.data(AnimationRole.UUIDRole)
            if uuid:
                selected_uuids.add(uuid)

        # Update last_viewed_date for newly selected items
        for index in selected.indexes():
            uuid = index.data(AnimationRole.UUIDRole)
            if uuid:
                self._db_service.update_last_viewed(uuid)

        # Update event bus
        if Config.ENABLE_MULTI_SELECT:
            self._event_bus.set_selected_animations(selected_uuids)

        # Update single selection (last selected)
        if selected_uuids:
            last_uuid = list(selected_uuids)[-1]
            self._event_bus.set_selected_animation(last_uuid)
        else:
            self._event_bus.set_selected_animation(None)

    def contextMenuEvent(self, event):
        """Handle context menu"""

        # Don't show context menu while blending or right after blend ended
        if self._blend_active:
            event.accept()
            return

        if self._blend_just_ended:
            self._blend_just_ended = False  # Reset flag
            event.accept()
            return

        index = self.indexAt(event.pos())
        if index.isValid():
            uuid = index.data(AnimationRole.UUIDRole)
            if uuid:
                self.animation_context_menu.emit(uuid, event.globalPos())

    def resizeEvent(self, event: QResizeEvent):
        """Handle resize to adjust grid layout"""

        super().resizeEvent(event)

        if self._view_mode == "grid":
            # Recalculate grid size
            self.setGridSize(self._delegate.sizeHint(None, QModelIndex()))

    def select_animation(self, uuid: str):
        """
        Select animation by UUID

        Args:
            uuid: Animation UUID
        """
        model = self.model()
        if not model:
            return

        # Find item with this UUID
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            item_uuid = index.data(AnimationRole.UUIDRole)
            if item_uuid == uuid:
                self.selectionModel().select(
                    index,
                    self.selectionModel().SelectionFlag.ClearAndSelect
                )
                self.scrollTo(index)
                break

    def clear_selection(self):
        """Clear all selections"""
        self.selectionModel().clearSelection()

    def get_selected_uuids(self) -> list[str]:
        """
        Get list of selected animation UUIDs

        Returns:
            List of UUIDs (deduplicated)
        """
        selected_indexes = self.selectionModel().selectedIndexes()
        uuids = []
        seen = set()

        for index in selected_indexes:
            uuid = index.data(AnimationRole.UUIDRole)
            if uuid and uuid not in seen:
                uuids.append(uuid)
                seen.add(uuid)

        return uuids

    # Hover video popup methods

    def _ensure_hover_popup(self):
        """Create popup on demand (lazy loading)"""
        if not self._hover_popup:
            self._hover_popup = HoverVideoPopup(self)
            self._hover_popup.set_size(Config.HOVER_VIDEO_SIZE)

    def _show_hover_video_popup(self):
        """Show hover video popup with animation preview"""
        if not self._hover_index or not self._hover_index.isValid():
            return

        # Get video path
        video_path = self._hover_index.data(AnimationRole.PreviewPathRole)

        if not video_path or not os.path.exists(video_path):
            return

        # Ensure popup exists
        self._ensure_hover_popup()

        # Get gradient colors
        gradient_top, gradient_bottom = self._get_gradient_colors(self._hover_index)

        # Calculate popup position
        position = self._calculate_popup_position(self._last_hover_pos)

        # Show popup
        self._hover_popup.show_preview(video_path, gradient_top, gradient_bottom, position)

    def _get_gradient_colors(self, index: QModelIndex) -> tuple:
        """
        Get gradient colors for animation

        Args:
            index: Model index

        Returns:
            Tuple of (gradient_top, gradient_bottom) as RGB tuples (0-255)
        """
        # Check if using custom gradient
        use_custom = index.data(AnimationRole.UseCustomGradientRole)

        if use_custom:
            # Get custom gradient colors (stored as normalized 0-1 floats)
            top_normalized = index.data(AnimationRole.GradientTopRole)
            bottom_normalized = index.data(AnimationRole.GradientBottomRole)

            if top_normalized and bottom_normalized:
                # Convert to 0-255 RGB
                gradient_top = tuple(int(c * 255) for c in top_normalized)
                gradient_bottom = tuple(int(c * 255) for c in bottom_normalized)
                return gradient_top, gradient_bottom

        # Use default gradient colors
        top_normalized = Config.DEFAULT_GRADIENT_TOP
        bottom_normalized = Config.DEFAULT_GRADIENT_BOTTOM
        gradient_top = tuple(int(c * 255) for c in top_normalized)
        gradient_bottom = tuple(int(c * 255) for c in bottom_normalized)

        return gradient_top, gradient_bottom

    def _calculate_popup_position(self, cursor_pos: QPoint) -> QPoint:
        """
        Calculate popup position based on config

        Args:
            cursor_pos: Cursor position in viewport coordinates

        Returns:
            Global screen position for popup
        """
        position_mode = Config.HOVER_VIDEO_POSITION
        popup_size = Config.HOVER_VIDEO_SIZE

        # Convert to global coordinates
        global_cursor_pos = self.viewport().mapToGlobal(cursor_pos)

        if position_mode == "cursor":
            # Position near cursor with offset
            offset = 20
            return QPoint(
                global_cursor_pos.x() + offset,
                global_cursor_pos.y() + offset
            )

        # Get card rect for other positioning modes
        if not self._hover_index or not self._hover_index.isValid():
            return global_cursor_pos

        card_rect = self.visualRect(self._hover_index)
        global_card_top_left = self.viewport().mapToGlobal(card_rect.topLeft())

        if position_mode == "right":
            # Position to the right of card
            return QPoint(
                global_card_top_left.x() + card_rect.width() + 10,
                global_card_top_left.y()
            )
        elif position_mode == "left":
            # Position to the left of card
            return QPoint(
                global_card_top_left.x() - popup_size - 10,
                global_card_top_left.y()
            )
        elif position_mode == "above":
            # Position above card
            return QPoint(
                global_card_top_left.x(),
                global_card_top_left.y() - popup_size - 10
            )
        elif position_mode == "below":
            # Position below card
            return QPoint(
                global_card_top_left.x(),
                global_card_top_left.y() + card_rect.height() + 10
            )

        # Default: cursor position
        return global_cursor_pos

    def startDrag(self, supportedActions):
        """
        Override startDrag to force viewport cleanup after drag completes

        This fixes visual artifacts when cards are dragged and dropped in empty space.
        The default QListView drag implementation can leave pixmap artifacts on screen
        when the drag is cancelled (ESC) or dropped on invalid targets.

        Args:
            supportedActions: Qt.DropActions supported by this view
        """
        # Call parent's drag implementation (blocks until drag completes)
        super().startDrag(supportedActions)

        # Force immediate viewport repaint to clear drag visual artifacts
        # Use repaint() for immediate update instead of update() which schedules it
        self.viewport().repaint()

        # Also force layout recalculation to ensure proper redraw
        self.scheduleDelayedItemsLayout()

        # Update the view itself as well
        self.update()


__all__ = ['AnimationView']
