"""
AnimationCardDelegate - Custom rendering for animation items

Pattern: QStyledItemDelegate for Model/View
Inspired by: Hybrid plan + Maya Studio Library

Rendering is delegated to specialized renderer classes:
- BadgeRenderer: Type badges, version badges, status badges, etc.
- ThumbnailRenderer: Thumbnail images and placeholders
- TextRenderer: Name and metadata text
"""

from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt6.QtCore import QSize, QRect, Qt, QEvent, QItemSelectionModel
from PyQt6.QtGui import QPainter, QPixmap, QColor, QPen

from ..models.animation_list_model import AnimationRole
from ..services.thumbnail_loader import get_thumbnail_loader
from ..services.database_service import get_database_service
from ..themes.theme_manager import get_theme_manager
from ..utils.icon_loader import IconLoader
from ..config import Config

from .renderers import BadgeRenderer, ThumbnailRenderer, TextRenderer


class AnimationCardDelegate(QStyledItemDelegate):
    """
    Custom delegate for rendering animation cards in grid and list modes

    Features:
    - Grid mode: Card layout with thumbnail, name, metadata
    - List mode: Row layout with smaller thumbnail
    - Async thumbnail loading
    - Selection highlighting
    - Edit mode checkboxes
    - Hover effects
    """

    def __init__(self, parent=None, view_mode: str = "grid",
                 db_service=None, thumbnail_loader=None, theme_manager=None):
        super().__init__(parent)
        self._view_mode = view_mode
        self._card_size = Config.DEFAULT_CARD_SIZE
        self._thumbnail_loader = thumbnail_loader or get_thumbnail_loader()
        self._theme_manager = theme_manager or get_theme_manager()
        self._db_service = db_service or get_database_service()
        self._edit_mode = False

        # Cache type badge pixmaps
        self._action_badge_pixmap = None
        self._pose_badge_pixmap = None
        self._info_badge_pixmap = None
        self._load_type_badges()

        # Connect thumbnail loader signals
        self._thumbnail_loader.thumbnail_loaded.connect(self._on_thumbnail_loaded)

    def _load_type_badges(self):
        """Load and cache type badge pixmaps"""
        try:
            self._action_badge_pixmap = QPixmap(IconLoader.get("action_badge"))
            self._pose_badge_pixmap = QPixmap(IconLoader.get("pose_badge"))
            self._info_badge_pixmap = QPixmap(IconLoader.get("info"))
        except Exception as e:
            print(f"Warning: Could not load type badges: {e}")

    # ==================== PUBLIC API ====================

    def set_view_mode(self, mode: str):
        """Set view mode ("grid" or "list")"""
        if mode in ("grid", "list"):
            self._view_mode = mode

    def set_card_size(self, size: int):
        """Set card size for grid mode"""
        self._card_size = max(Config.MIN_CARD_SIZE, min(size, Config.MAX_CARD_SIZE))

    def set_edit_mode(self, enabled: bool):
        """Enable/disable edit mode (shows checkboxes)"""
        self._edit_mode = enabled

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        """Return size hint for item"""
        if self._view_mode == "grid":
            name_height = 28
            return QSize(self._card_size, self._card_size + name_height)
        else:
            return QSize(option.rect.width(), Config.LIST_ROW_HEIGHT)

    # ==================== MAIN PAINT METHOD ====================

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint item"""
        painter.save()

        if self._view_mode == "grid":
            self._paint_grid_mode(painter, option, index)
        else:
            self._paint_list_mode(painter, option, index)

        painter.restore()

    # ==================== EVENT HANDLING ====================

    def editorEvent(self, event, model, option, index):
        """Handle mouse events for checkbox and favorite star"""
        if event.type() != QEvent.Type.MouseButtonRelease:
            return super().editorEvent(event, model, option, index)

        rect = option.rect
        click_pos = event.position().toPoint()

        # Calculate positions based on view mode
        if self._view_mode == "grid":
            star_size, star_padding = 24, 5
            star_rect = QRect(
                rect.x() + self._card_size - star_size - star_padding,
                rect.y() + star_padding,
                star_size, star_size
            )
            checkbox_size, badge_size = 20, 24
            checkbox_rect = QRect(
                rect.x() + 5,
                rect.y() + 5 + badge_size + 3,
                checkbox_size, checkbox_size
            )
        else:
            star_size, star_padding = 20, 8
            star_rect = QRect(
                rect.right() - star_size - star_padding,
                rect.y() + (rect.height() - star_size) // 2,
                star_size, star_size
            )
            checkbox_size, padding = 20, 4
            checkbox_rect = QRect(
                rect.x() + padding,
                rect.y() + (rect.height() - checkbox_size) // 2,
                checkbox_size, checkbox_size
            )

        # Check favorite star click
        if star_rect.contains(click_pos):
            uuid = index.data(AnimationRole.UUIDRole)
            if uuid:
                success = self._db_service.toggle_favorite(uuid)
                if success:
                    source_model = model
                    if hasattr(model, 'sourceModel'):
                        source_model = model.sourceModel()
                    if hasattr(source_model, 'refresh_animation'):
                        source_model.refresh_animation(uuid)
                    if self.parent() and hasattr(self.parent(), 'viewport'):
                        self.parent().viewport().update()
                return True

        # Check checkbox click (edit mode only)
        if self._edit_mode and checkbox_rect.contains(click_pos):
            is_selected = option.state & QStyle.StateFlag.State_Selected
            if self.parent() and hasattr(self.parent(), 'selectionModel'):
                selection_model = self.parent().selectionModel()
                flag = QItemSelectionModel.SelectionFlag.Deselect if is_selected else QItemSelectionModel.SelectionFlag.Select
                selection_model.select(index, flag)
            return True

        return super().editorEvent(event, model, option, index)

    # ==================== GRID MODE PAINTING ====================

    def _paint_grid_mode(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint item in grid mode"""
        rect = option.rect
        is_selected = option.state & QStyle.StateFlag.State_Selected
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver

        theme = self._theme_manager.get_current_theme()
        if not theme:
            return
        palette = theme.palette

        # Draw selection background
        if is_selected:
            painter.fillRect(rect, QColor(palette.accent))

        # Draw thumbnail
        thumbnail_rect = QRect(rect.x(), rect.y(), self._card_size, self._card_size)
        self._draw_thumbnail(painter, thumbnail_rect, index)

        # Draw type badge (action/pose)
        is_pose = index.data(AnimationRole.IsPoseRole)
        BadgeRenderer.draw_type_badge(
            painter, thumbnail_rect, bool(is_pose),
            self._action_badge_pixmap, self._pose_badge_pixmap, badge_size=24
        )

        # Draw edit mode checkbox
        if self._edit_mode:
            checkbox_rect = QRect(rect.x() + 5, rect.y() + 5 + 24 + 3, 20, 20)
            BadgeRenderer.draw_checkbox(painter, checkbox_rect, is_selected, palette)

        # Draw favorite star
        is_favorite = index.data(AnimationRole.IsFavoriteRole)
        star_size, star_padding = 24, 5
        star_rect = QRect(
            rect.x() + self._card_size - star_size - star_padding,
            rect.y() + star_padding, star_size, star_size
        )
        BadgeRenderer.draw_favorite_star(painter, star_rect, is_favorite, is_hovered, palette)

        # Draw unresolved comments badge
        unresolved_count = index.data(AnimationRole.UnresolvedCommentCountRole) or 0
        if unresolved_count > 0:
            BadgeRenderer.draw_comment_badge_grid(
                painter, rect, unresolved_count, self._info_badge_pixmap,
                self._card_size, star_padding, star_size
            )

        # Draw version badge (skip for poses)
        if not is_pose:
            version_label = index.data(AnimationRole.VersionLabelRole)
            if version_label:
                badge_rect = QRect(
                    rect.x() + 5, rect.y() + self._card_size - 25, 40, 20
                )
                BadgeRenderer.draw_version_badge(painter, badge_rect, version_label)

        # Draw status badge or partial indicator
        if not is_pose:
            status = index.data(AnimationRole.StatusRole)
            if status and status != 'none':
                status_info = Config.LIFECYCLE_STATUSES.get(status, {'label': status.upper()})
                label_width = max(50, len(status_info['label']) * 7 + 10)
                status_rect = QRect(
                    rect.x() + self._card_size - label_width - 5,
                    rect.y() + self._card_size - 25, label_width, 20
                )
                BadgeRenderer.draw_status_badge(painter, status_rect, status)
        else:
            is_partial = index.data(AnimationRole.IsPartialRole)
            if is_partial:
                BadgeRenderer.draw_partial_indicator(
                    painter,
                    rect.x() + self._card_size - 18,
                    rect.y() + self._card_size - 18, 12
                )

        # Draw text below thumbnail
        text_rect = QRect(rect.x(), rect.y() + self._card_size, self._card_size, 28)
        name = index.data(AnimationRole.NameRole)
        TextRenderer.draw_grid_text(painter, text_rect, name, palette, is_selected)

    # ==================== LIST MODE PAINTING ====================

    def _paint_list_mode(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint item in list mode"""
        rect = option.rect
        is_selected = option.state & QStyle.StateFlag.State_Selected
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver

        theme = self._theme_manager.get_current_theme()
        if not theme:
            return
        palette = theme.palette

        # Draw background
        if is_selected:
            painter.fillRect(rect, QColor(palette.accent))
        elif is_hovered:
            hover_color = QColor(palette.accent)
            hover_color.setAlpha(20)
            painter.fillRect(rect, hover_color)

        # Layout calculations
        padding = 4
        thumbnail_size = Config.LIST_ROW_HEIGHT - (padding * 2)
        checkbox_size = 20
        checkbox_offset = (checkbox_size + padding * 2) if self._edit_mode else 0

        # Draw checkbox (edit mode)
        if self._edit_mode:
            checkbox_rect = QRect(
                rect.x() + padding,
                rect.y() + (rect.height() - checkbox_size) // 2,
                checkbox_size, checkbox_size
            )
            BadgeRenderer.draw_checkbox(painter, checkbox_rect, is_selected, palette)

        # Draw thumbnail
        thumbnail_rect = QRect(
            rect.x() + padding + checkbox_offset, rect.y() + padding,
            thumbnail_size, thumbnail_size
        )
        self._draw_thumbnail(painter, thumbnail_rect, index)

        # Draw type badge
        is_pose = index.data(AnimationRole.IsPoseRole)
        BadgeRenderer.draw_type_badge(
            painter, thumbnail_rect, bool(is_pose),
            self._action_badge_pixmap, self._pose_badge_pixmap, badge_size=16
        )

        # Draw selection indicator
        if is_selected:
            pen = QPen(QColor(palette.accent), 2)
            painter.setPen(pen)
            painter.drawRect(thumbnail_rect.adjusted(-1, -1, 1, 1))

        # Draw favorite star
        is_favorite = index.data(AnimationRole.IsFavoriteRole)
        star_size, star_padding = 20, 8
        star_rect = QRect(
            rect.right() - star_size - star_padding,
            rect.y() + (rect.height() - star_size) // 2,
            star_size, star_size
        )
        BadgeRenderer.draw_favorite_star(painter, star_rect, is_favorite, is_hovered, palette)

        # Draw comment badge
        unresolved_count = index.data(AnimationRole.UnresolvedCommentCountRole) or 0
        if unresolved_count > 0:
            BadgeRenderer.draw_comment_badge_list(
                painter, rect, unresolved_count, self._info_badge_pixmap,
                star_size, star_padding
            )

        # Draw version badge (skip for poses)
        if not is_pose:
            version_label = index.data(AnimationRole.VersionLabelRole)
            if version_label:
                badge_rect = QRect(thumbnail_rect.x() + 2, thumbnail_rect.bottom() - 14, 30, 12)
                BadgeRenderer.draw_version_badge(painter, badge_rect, version_label)

        # Calculate text area
        status = index.data(AnimationRole.StatusRole)
        show_status = status and status != 'none' and not is_pose
        is_partial = index.data(AnimationRole.IsPartialRole) if is_pose else False
        show_partial = is_pose and is_partial
        comment_badge_width = 30 if unresolved_count > 0 else 0
        badge_width = 60 if show_status else (20 if show_partial else 0)

        text_x = rect.x() + thumbnail_size + (padding * 3) + checkbox_offset
        text_rect = QRect(
            text_x, rect.y() + padding,
            rect.width() - text_x - star_size - star_padding - padding - badge_width - comment_badge_width - 8,
            thumbnail_size
        )

        # Draw text
        name = index.data(AnimationRole.NameRole)
        rig_type = index.data(AnimationRole.RigTypeRole)
        frame_count = index.data(AnimationRole.FrameCountRole)
        fps = index.data(AnimationRole.FPSRole)
        TextRenderer.draw_list_text(painter, text_rect, name, rig_type, frame_count, fps, palette, is_selected)

        # Draw status badge or partial indicator
        if show_status:
            status_info = Config.LIFECYCLE_STATUSES.get(status, {'label': status.upper()})
            label_width = max(50, len(status_info['label']) * 7 + 6)
            status_rect = QRect(
                rect.right() - star_size - star_padding - label_width - 8,
                rect.y() + (rect.height() - 18) // 2,
                label_width, 18
            )
            BadgeRenderer.draw_status_badge(painter, status_rect, status)
        elif show_partial:
            BadgeRenderer.draw_partial_indicator(
                painter,
                rect.right() - star_size - star_padding - 22,
                rect.y() + (rect.height() - 10) // 2, 10
            )

    # ==================== THUMBNAIL DRAWING ====================

    def _draw_thumbnail(self, painter: QPainter, rect: QRect, index):
        """Draw thumbnail image"""
        uuid = index.data(AnimationRole.UUIDRole)
        thumbnail_path = index.data(AnimationRole.ThumbnailPathRole)
        use_custom = index.data(AnimationRole.UseCustomGradientRole)
        gradient_top = index.data(AnimationRole.GradientTopRole)
        gradient_bottom = index.data(AnimationRole.GradientBottomRole)

        ThumbnailRenderer.draw_thumbnail(
            painter, rect, uuid, thumbnail_path, use_custom,
            gradient_top, gradient_bottom,
            self._thumbnail_loader, self._theme_manager
        )

    # ==================== SIGNAL HANDLERS ====================

    def _on_thumbnail_loaded(self, uuid: str, pixmap: QPixmap):
        """Handle thumbnail loaded signal"""
        if self.parent() and hasattr(self.parent(), 'viewport'):
            self.parent().viewport().update()


__all__ = ['AnimationCardDelegate']
