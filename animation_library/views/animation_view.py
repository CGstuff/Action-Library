"""
AnimationView - QListView for animations

Pattern: QListView with Model/View architecture
Inspired by: Hybrid plan + Maya Studio Library
"""

import os
from typing import Optional
from PyQt6.QtWidgets import QListView, QAbstractItemView
from PyQt6.QtCore import Qt, QTimer, QModelIndex, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QResizeEvent, QMouseEvent

from .animation_card_delegate import AnimationCardDelegate
from ..models.animation_list_model import AnimationRole
from ..services.database_service import get_database_service
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

    Usage:
        view = AnimationView()
        view.setModel(animation_filter_proxy_model)
        view.set_view_mode("grid")
    """

    # Signals
    animation_double_clicked = pyqtSignal(str)  # animation_uuid
    animation_context_menu = pyqtSignal(str, QPoint)  # animation_uuid, position
    hover_started = pyqtSignal(str, QPoint)  # animation_uuid, position
    hover_ended = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Event bus
        self._event_bus = get_event_bus()

        # Database service
        self._db_service = get_database_service()

        # View mode
        self._view_mode = Config.DEFAULT_VIEW_MODE
        self._card_size = Config.DEFAULT_CARD_SIZE

        # Delegate
        self._delegate = AnimationCardDelegate(self, view_mode=self._view_mode)
        self.setItemDelegate(self._delegate)

        # Hover tracking
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._on_hover_timeout)
        self._hover_index: Optional[QModelIndex] = None
        self._last_hover_pos = QPoint()

        # Hover video popup (lazy loading - only create when first needed)
        self._hover_popup: Optional[HoverVideoPopup] = None

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

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for hover detection"""

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
        """Handle double click and track last viewed"""

        if not index.isValid():
            return

        uuid = index.data(AnimationRole.UUIDRole)
        if uuid:
            # Update last viewed (double-click is a strong viewing signal)
            self._db_service.update_last_viewed(uuid)

            self.animation_double_clicked.emit(uuid)

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
