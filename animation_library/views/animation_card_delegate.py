"""
AnimationCardDelegate - Custom rendering for animation items

Pattern: QStyledItemDelegate for Model/View
Inspired by: Hybrid plan + Maya Studio Library
"""

from typing import Optional
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt6.QtCore import QSize, QRect, Qt, QPoint, QEvent, QItemSelectionModel
from PyQt6.QtGui import QPainter, QPixmap, QFont, QPen, QColor, QFontMetrics

from ..models.animation_list_model import AnimationRole
from ..services.thumbnail_loader import get_thumbnail_loader
from ..services.database_service import get_database_service
from ..themes.theme_manager import get_theme_manager
from ..utils.icon_loader import IconLoader
from ..config import Config


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

    Usage:
        delegate = AnimationCardDelegate(view_mode="grid")
        list_view.setItemDelegate(delegate)
    """

    def __init__(self, parent=None, view_mode: str = "grid"):
        super().__init__(parent)
        self._view_mode = view_mode
        self._card_size = Config.DEFAULT_CARD_SIZE
        self._thumbnail_loader = get_thumbnail_loader()
        self._theme_manager = get_theme_manager()
        self._db_service = get_database_service()
        self._edit_mode = False

        # Cache type badge pixmaps
        self._action_badge_pixmap = None
        self._pose_badge_pixmap = None
        self._load_type_badges()

        # Connect thumbnail loader signals
        self._thumbnail_loader.thumbnail_loaded.connect(self._on_thumbnail_loaded)

    def _load_type_badges(self):
        """Load and cache type badge pixmaps"""
        try:
            # Load action badge
            action_path = IconLoader.get("action_badge")
            self._action_badge_pixmap = QPixmap(action_path)

            # Load pose badge
            pose_path = IconLoader.get("pose_badge")
            self._pose_badge_pixmap = QPixmap(pose_path)
        except Exception as e:
            print(f"Warning: Could not load type badges: {e}")

    def set_view_mode(self, mode: str):
        """
        Set view mode

        Args:
            mode: "grid" or "list"
        """
        if mode in ("grid", "list"):
            self._view_mode = mode

    def set_card_size(self, size: int):
        """
        Set card size for grid mode

        Args:
            size: Size in pixels
        """
        self._card_size = max(Config.MIN_CARD_SIZE, min(size, Config.MAX_CARD_SIZE))

    def set_edit_mode(self, enabled: bool):
        """
        Enable/disable edit mode

        Args:
            enabled: True to show checkboxes
        """
        self._edit_mode = enabled

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        """
        Return size hint for item

        Args:
            option: Style options
            index: Model index

        Returns:
            QSize for item
        """
        if self._view_mode == "grid":
            # Square + name below (like old repo: 160px square + 28px name = 188px total)
            name_height = 28
            return QSize(self._card_size, self._card_size + name_height)
        else:
            # List mode: fixed row height
            return QSize(option.rect.width(), Config.LIST_ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """
        Paint item

        Args:
            painter: QPainter instance
            option: Style options
            index: Model index
        """
        painter.save()

        if self._view_mode == "grid":
            self._paint_grid_mode(painter, option, index)
        else:
            self._paint_list_mode(painter, option, index)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """
        Handle mouse events for checkbox (edit mode) and favorite star

        Args:
            event: QEvent instance
            model: Model instance
            option: Style options
            index: Model index

        Returns:
            bool: True if event was handled
        """
        # Only handle mouse button release
        if event.type() != QEvent.Type.MouseButtonRelease:
            return super().editorEvent(event, model, option, index)

        rect = option.rect
        click_pos = event.position().toPoint()

        # Calculate positions based on view mode
        if self._view_mode == "grid":
            # Grid mode: star in top-right of thumbnail
            star_size = 24
            star_padding = 5
            star_rect = QRect(
                rect.x() + self._card_size - star_size - star_padding,
                rect.y() + star_padding,
                star_size,
                star_size
            )
            # Grid mode: checkbox in top-left (below type badge)
            checkbox_size = 20
            badge_size = 24
            checkbox_rect = QRect(
                rect.x() + 5,
                rect.y() + 5 + badge_size + 3,  # Below type badge
                checkbox_size,
                checkbox_size
            )
        else:
            # List mode: star at right edge, vertically centered
            star_size = 20
            star_padding = 8
            star_rect = QRect(
                rect.right() - star_size - star_padding,
                rect.y() + (rect.height() - star_size) // 2,
                star_size,
                star_size
            )
            # List mode: checkbox at left edge, vertically centered
            checkbox_size = 20
            padding = 4
            checkbox_rect = QRect(
                rect.x() + padding,
                rect.y() + (rect.height() - checkbox_size) // 2,
                checkbox_size,
                checkbox_size
            )

        # Check favorite star click (always active)
        if star_rect.contains(click_pos):
            # Toggle favorite
            uuid = index.data(AnimationRole.UUIDRole)
            if uuid:
                success = self._db_service.toggle_favorite(uuid)
                if success:
                    # Get the source model (might be a proxy model)
                    source_model = model
                    if hasattr(model, 'sourceModel'):
                        source_model = model.sourceModel()

                    # Refresh animation data from database
                    if hasattr(source_model, 'refresh_animation'):
                        source_model.refresh_animation(uuid)

                    # Force view repaint
                    if self.parent() and hasattr(self.parent(), 'viewport'):
                        self.parent().viewport().update()
                return True

        # Check checkbox click (only in edit mode)
        if self._edit_mode:
            if checkbox_rect.contains(click_pos):
                # Toggle selection
                is_selected = option.state & QStyle.StateFlag.State_Selected

                # Get the view to toggle selection
                if self.parent() and hasattr(self.parent(), 'selectionModel'):
                    selection_model = self.parent().selectionModel()
                    if is_selected:
                        selection_model.select(index, QItemSelectionModel.SelectionFlag.Deselect)
                    else:
                        selection_model.select(index, QItemSelectionModel.SelectionFlag.Select)

                return True  # Event handled

        return super().editorEvent(event, model, option, index)

    def _paint_grid_mode(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint item in grid mode"""

        rect = option.rect
        is_selected = option.state & QStyle.StateFlag.State_Selected
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver

        # Get theme colors
        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        palette = theme.palette

        # Draw full card selection background (Studio Library style)
        if is_selected:
            # Fill entire card (thumbnail + name label) with accent color
            painter.fillRect(rect, QColor(palette.accent))

        # Draw thumbnail as square (fills card_size x card_size at top)
        thumbnail_rect = QRect(
            rect.x(),
            rect.y(),
            self._card_size,
            self._card_size
        )
        self._draw_thumbnail(painter, thumbnail_rect, index)

        # Draw type badge (action/pose) in upper left corner
        is_pose = index.data(AnimationRole.IsPoseRole)
        self._draw_type_badge(painter, thumbnail_rect, bool(is_pose), badge_size=24)

        # Draw edit mode checkbox (overlaid on top-left of thumbnail, below type badge)
        if self._edit_mode:
            checkbox_size = 20
            badge_size = 24
            checkbox_rect = QRect(
                rect.x() + 5,
                rect.y() + 5 + badge_size + 3,  # Position below the type badge
                checkbox_size,
                checkbox_size
            )
            self._draw_checkbox(painter, checkbox_rect, is_selected)

        # Draw favorite star (overlaid on top-right of thumbnail)
        is_favorite = index.data(AnimationRole.IsFavoriteRole)
        star_size = 24
        star_padding = 5
        star_rect = QRect(
            rect.x() + self._card_size - star_size - star_padding,
            rect.y() + star_padding,
            star_size,
            star_size
        )
        self._draw_favorite_star(painter, star_rect, is_favorite, is_hovered)

        # Draw version badge (bottom-left of thumbnail) - skip for poses (they don't use versioning)
        if not is_pose:
            version_label = index.data(AnimationRole.VersionLabelRole)
            if version_label:
                badge_padding = 5
                badge_rect = QRect(
                    rect.x() + badge_padding,
                    rect.y() + self._card_size - 20 - badge_padding,
                    40,
                    20
                )
                self._draw_version_badge(painter, badge_rect, version_label)

        # Draw status badge (bottom-right of thumbnail) - skip for poses (no lifecycle tracking)
        if not is_pose:
            status = index.data(AnimationRole.StatusRole)
            if status and status != 'none':
                badge_padding = 5
                # Calculate width based on status label length
                status_info = Config.LIFECYCLE_STATUSES.get(status, {'label': status.upper()})
                label_width = max(50, len(status_info['label']) * 7 + 10)
                status_rect = QRect(
                    rect.x() + self._card_size - label_width - badge_padding,
                    rect.y() + self._card_size - 20 - badge_padding,
                    label_width,
                    20
                )
                self._draw_status_badge(painter, status_rect, status)
        else:
            # For poses: draw partial indicator if this is a partial pose (selected bones only)
            is_partial = index.data(AnimationRole.IsPartialRole)
            if is_partial:
                # Small circle in bottom-right corner
                indicator_size = 12
                padding = 6
                self._draw_partial_indicator(
                    painter,
                    rect.x() + self._card_size - indicator_size - padding,
                    rect.y() + self._card_size - indicator_size - padding,
                    indicator_size
                )

        # Draw text BELOW thumbnail (28px height)
        name_height = 28
        text_rect = QRect(
            rect.x(),
            rect.y() + self._card_size,  # Below the thumbnail
            self._card_size,
            name_height
        )
        self._draw_grid_text(painter, text_rect, index, palette, is_selected)

    def _paint_list_mode(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint item in list mode"""

        rect = option.rect
        is_selected = option.state & QStyle.StateFlag.State_Selected
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver

        # Get theme colors
        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        palette = theme.palette

        # Draw background (Studio Library style - use accent for selection)
        if is_selected:
            painter.fillRect(rect, QColor(palette.accent))
        elif is_hovered:
            hover_color = QColor(palette.accent)
            hover_color.setAlpha(20)
            painter.fillRect(rect, hover_color)

        # Calculate layout
        padding = 4
        thumbnail_size = Config.LIST_ROW_HEIGHT - (padding * 2)

        # Calculate checkbox offset (shift content right when edit mode is on)
        checkbox_size = 20
        checkbox_offset = (checkbox_size + padding * 2) if self._edit_mode else 0

        # Draw edit mode checkbox (to the left of thumbnail)
        if self._edit_mode:
            checkbox_rect = QRect(
                rect.x() + padding,
                rect.y() + (rect.height() - checkbox_size) // 2,
                checkbox_size,
                checkbox_size
            )
            self._draw_checkbox(painter, checkbox_rect, is_selected)

        # Thumbnail rect (shifted right if checkbox is shown)
        thumbnail_rect = QRect(
            rect.x() + padding + checkbox_offset,
            rect.y() + padding,
            thumbnail_size,
            thumbnail_size
        )

        # Draw thumbnail
        self._draw_thumbnail(painter, thumbnail_rect, index)

        # Draw type badge (action/pose) in upper left of thumbnail
        is_pose = index.data(AnimationRole.IsPoseRole)
        self._draw_type_badge(painter, thumbnail_rect, bool(is_pose), badge_size=16)

        # Draw selection indicator
        if is_selected:
            pen = QPen(QColor(palette.accent), 2)
            painter.setPen(pen)
            painter.drawRect(thumbnail_rect.adjusted(-1, -1, 1, 1))

        # Draw favorite star (at right edge)
        is_favorite = index.data(AnimationRole.IsFavoriteRole)
        star_size = 20
        star_padding = 8
        star_rect = QRect(
            rect.right() - star_size - star_padding,
            rect.y() + (rect.height() - star_size) // 2,
            star_size,
            star_size
        )
        self._draw_favorite_star(painter, star_rect, is_favorite, is_hovered)

        # Draw version badge on thumbnail (bottom-left) - skip for poses (they don't use versioning)
        if not is_pose:
            version_label = index.data(AnimationRole.VersionLabelRole)
            if version_label:
                badge_rect = QRect(
                    thumbnail_rect.x() + 2,
                    thumbnail_rect.bottom() - 14,
                    30,
                    12
                )
                self._draw_version_badge(painter, badge_rect, version_label)

        # Get status for list mode (skip for poses - no lifecycle tracking)
        status = index.data(AnimationRole.StatusRole)
        show_status = status and status != 'none' and not is_pose

        # Check for partial pose badge
        is_partial = index.data(AnimationRole.IsPartialRole) if is_pose else False
        show_partial = is_pose and is_partial

        # Draw text next to thumbnail (account for checkbox offset, star space, and status/partial badge)
        badge_width = 60 if show_status else (20 if show_partial else 0)
        text_x = rect.x() + thumbnail_size + (padding * 3) + checkbox_offset
        text_rect = QRect(
            text_x,
            rect.y() + padding,
            rect.width() - text_x - star_size - star_padding - padding - badge_width - 8,
            thumbnail_size
        )
        self._draw_list_text(painter, text_rect, index, palette, is_selected)

        # Draw status badge (between text and star) - skip for poses
        if show_status:
            status_info = Config.LIFECYCLE_STATUSES.get(status, {'label': status.upper()})
            label_width = max(50, len(status_info['label']) * 7 + 6)
            status_rect = QRect(
                rect.right() - star_size - star_padding - label_width - 8,
                rect.y() + (rect.height() - 18) // 2,
                label_width,
                18
            )
            self._draw_status_badge(painter, status_rect, status)
        elif show_partial:
            # Draw partial indicator circle for poses with selected bones only
            indicator_size = 10
            self._draw_partial_indicator(
                painter,
                rect.right() - star_size - star_padding - indicator_size - 12,
                rect.y() + (rect.height() - indicator_size) // 2,
                indicator_size
            )

    def _draw_thumbnail(self, painter: QPainter, rect: QRect, index):
        """Draw thumbnail image"""

        uuid = index.data(AnimationRole.UUIDRole)
        thumbnail_path_str = index.data(AnimationRole.ThumbnailPathRole)

        if not thumbnail_path_str:
            # No thumbnail - draw placeholder
            self._draw_placeholder(painter, rect)
            return

        # Get gradient colors
        use_custom = index.data(AnimationRole.UseCustomGradientRole)

        if use_custom:
            gradient_top_str = index.data(AnimationRole.GradientTopRole)
            gradient_bottom_str = index.data(AnimationRole.GradientBottomRole)
            # Parse stored gradient colors (stored as strings)
            try:
                import json
                gradient_top = tuple(json.loads(gradient_top_str)) if gradient_top_str else None
                gradient_bottom = tuple(json.loads(gradient_bottom_str)) if gradient_bottom_str else None
            except Exception:
                gradient_top = None
                gradient_bottom = None
        else:
            gradient_top = None
            gradient_bottom = None

        # Use theme gradient if no custom
        if not gradient_top or not gradient_bottom:
            gradient_top, gradient_bottom = self._theme_manager.get_gradient_colors()

        # Try to load thumbnail
        from pathlib import Path
        thumbnail_path = Path(thumbnail_path_str)

        pixmap = self._thumbnail_loader.load_thumbnail(
            uuid,
            thumbnail_path,
            gradient_top,
            gradient_bottom,
            use_custom
        )

        if pixmap:
            # Scale to rect dimensions (works for both grid and list modes)
            target_width = rect.width()
            target_height = rect.height()

            scaled = pixmap.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,  # Stretch to fill
                Qt.TransformationMode.SmoothTransformation
            )

            # Draw at rect dimensions
            painter.drawPixmap(
                rect.x(),
                rect.y(),
                target_width,
                target_height,
                scaled
            )
        else:
            # Loading in background - draw placeholder
            self._draw_loading_placeholder(painter, rect)

    def _draw_placeholder(self, painter: QPainter, rect: QRect):
        """Draw placeholder when no thumbnail"""

        theme = self._theme_manager.get_current_theme()
        if theme:
            painter.fillRect(rect, QColor(theme.palette.background_secondary))

        painter.setPen(QColor("#808080"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Image")

    def _draw_loading_placeholder(self, painter: QPainter, rect: QRect):
        """Draw placeholder while loading"""

        theme = self._theme_manager.get_current_theme()
        if theme:
            painter.fillRect(rect, QColor(theme.palette.background_secondary))

        painter.setPen(QColor("#A0A0A0"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Loading...")

    def _draw_checkbox(self, painter: QPainter, rect: QRect, is_checked: bool):
        """Draw edit mode checkbox"""

        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        palette = theme.palette

        # Draw checkbox background
        bg_color = QColor(palette.accent) if is_checked else QColor(palette.background_secondary)
        painter.fillRect(rect, bg_color)

        # Draw border
        pen = QPen(QColor(palette.border), 2)
        painter.setPen(pen)
        painter.drawRect(rect)

        # Draw checkmark if checked
        if is_checked:
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            # Draw checkmark
            painter.drawLine(
                rect.x() + 4, rect.y() + rect.height() // 2,
                rect.x() + rect.width() // 3, rect.y() + rect.height() - 4
            )
            painter.drawLine(
                rect.x() + rect.width() // 3, rect.y() + rect.height() - 4,
                rect.x() + rect.width() - 4, rect.y() + 4
            )

    def _draw_favorite_star(self, painter: QPainter, rect: QRect, is_favorite: bool, is_hovered: bool):
        """Draw favorite star icon"""

        from PyQt6.QtGui import QPolygonF, QBrush
        from PyQt6.QtCore import QPointF

        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        palette = theme.palette

        # Calculate star points (5-pointed star)
        cx, cy = rect.center().x(), rect.center().y()
        outer_radius = rect.width() / 2.0 - 2
        inner_radius = outer_radius * 0.4

        import math
        points = []
        for i in range(10):
            angle = (i * 36 - 90) * math.pi / 180
            radius = outer_radius if i % 2 == 0 else inner_radius
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            points.append(QPointF(x, y))

        star_polygon = QPolygonF(points)

        # Draw star
        if is_favorite:
            # Filled gold star for favorited animations
            painter.setBrush(QBrush(QColor(palette.gold_primary)))
            painter.setPen(QPen(QColor(palette.gold_primary), 1))
        else:
            # Outline star for non-favorited (show on hover or semi-transparent)
            if is_hovered:
                # White outline on hover
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#FFFFFF"), 2))
            else:
                # Very subtle outline when not hovered
                color = QColor("#FFFFFF")
                color.setAlpha(80)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(color, 1))

        painter.drawPolygon(star_polygon)

    def _draw_version_badge(self, painter: QPainter, rect: QRect, version_label: str):
        """Draw version badge (e.g., v001) on thumbnail"""

        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        # Disable antialiasing for sharp edges
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Draw semi-transparent background (sharp rectangle)
        bg_color = QColor("#000000")
        bg_color.setAlpha(160)
        painter.fillRect(rect, bg_color)

        # Draw text
        font = QFont("Roboto", 8, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, version_label)

    def _draw_status_badge(self, painter: QPainter, rect: QRect, status: str):
        """Draw lifecycle status badge on thumbnail"""

        # Disable antialiasing for sharp edges
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Get status info from config
        status_info = Config.LIFECYCLE_STATUSES.get(status, {'label': status.upper(), 'color': '#9E9E9E'})
        color = status_info['color']
        label = status_info['label']

        # Draw colored background (sharp rectangle)
        painter.fillRect(rect, QColor(color))

        # Draw text
        font = QFont("Roboto", 7, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_partial_indicator(self, painter: QPainter, x: int, y: int, size: int = 10):
        """Draw partial pose indicator (small circle for poses captured with selected bones only)"""
        from PyQt6.QtGui import QBrush

        # Teal circle to indicate partial pose
        painter.setBrush(QBrush(QColor("#00ACC1")))  # Cyan/teal
        painter.setPen(QPen(QColor("#FFFFFF"), 1))  # White border
        painter.drawEllipse(x, y, size, size)

    def _draw_type_badge(self, painter: QPainter, rect: QRect, is_pose: bool, badge_size: int = 24):
        """
        Draw type badge (action or pose) in upper left corner of thumbnail.

        Args:
            painter: QPainter instance
            rect: Rectangle for positioning (typically thumbnail rect)
            is_pose: True for pose badge, False for action badge
            badge_size: Size of the badge icon
        """
        # Select the appropriate badge pixmap
        badge_pixmap = self._pose_badge_pixmap if is_pose else self._action_badge_pixmap

        if not badge_pixmap or badge_pixmap.isNull():
            return

        # Position in upper left corner with small padding
        padding = 5
        badge_rect = QRect(
            rect.x() + padding,
            rect.y() + padding,
            badge_size,
            badge_size
        )

        # Scale pixmap to badge size
        scaled_badge = badge_pixmap.scaled(
            badge_size,
            badge_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Draw the badge
        painter.drawPixmap(badge_rect.x(), badge_rect.y(), scaled_badge)

    def _draw_grid_text(self, painter: QPainter, rect: QRect, index, palette, is_selected: bool = False):
        """Draw text for grid mode (below thumbnail)"""

        name = index.data(AnimationRole.NameRole)
        if not name:
            return

        # Draw subtle gray background for non-selected cards
        if not is_selected:
            bg_color = QColor(palette.background_secondary)
            bg_color.setAlpha(30)  # Very subtle transparency
            painter.fillRect(rect, bg_color)

        # Set up font (match old repo: Roboto 9pt DemiBold)
        font = QFont("Roboto", 9, QFont.Weight.DemiBold)
        painter.setFont(font)

        # White text on selection (Studio Library style)
        if is_selected:
            painter.setPen(QColor(palette.selection_text))
        else:
            painter.setPen(QColor(palette.text_primary))

        # Draw name centered (elided if too long, with ellipsis like old repo)
        fm = QFontMetrics(font)
        if fm.horizontalAdvance(name) > rect.width():
            # Truncate and add "..." like old repo (14 chars + "...")
            name = name[:14] + "..."

        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)

    def _draw_grid_text_overlay(self, painter: QPainter, rect: QRect, index, palette):
        """Draw text overlaid on thumbnail with semi-transparent background"""

        name = index.data(AnimationRole.NameRole)
        if not name:
            return

        # Draw semi-transparent background for text readability
        bg_color = QColor(palette.background)
        bg_color.setAlpha(180)  # 70% opacity
        painter.fillRect(rect, bg_color)

        # Set up font
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor(palette.text_primary))

        # Draw name (elided if too long)
        fm = QFontMetrics(font)
        elided_name = fm.elidedText(name, Qt.TextElideMode.ElideRight, rect.width() - 8)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, elided_name)

    def _draw_list_text(self, painter: QPainter, rect: QRect, index, palette, is_selected: bool = False):
        """Draw text for list mode"""

        name = index.data(AnimationRole.NameRole)
        rig_type = index.data(AnimationRole.RigTypeRole)
        frame_count = index.data(AnimationRole.FrameCountRole)
        fps = index.data(AnimationRole.FPSRole)

        # Name (bold)
        font_bold = QFont()
        font_bold.setPointSize(10)
        font_bold.setBold(True)
        painter.setFont(font_bold)

        # White text on selection (Studio Library style)
        if is_selected:
            painter.setPen(QColor(palette.selection_text))
        else:
            painter.setPen(QColor(palette.text_primary))

        name_rect = QRect(rect.x(), rect.y(), rect.width(), 20)
        fm = QFontMetrics(font_bold)
        elided_name = fm.elidedText(name or "Unknown", Qt.TextElideMode.ElideRight, name_rect.width())
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_name)

        # Metadata (smaller)
        font_small = QFont()
        font_small.setPointSize(8)
        painter.setFont(font_small)

        # White text for metadata too when selected
        if is_selected:
            painter.setPen(QColor(palette.selection_text))
        else:
            painter.setPen(QColor(palette.text_secondary))

        metadata_parts = []
        if rig_type:
            metadata_parts.append(f"Rig: {rig_type}")
        if frame_count:
            metadata_parts.append(f"{frame_count} frames")
        if fps:
            metadata_parts.append(f"{fps} FPS")

        metadata_text = " | ".join(metadata_parts)
        metadata_rect = QRect(rect.x(), rect.y() + 22, rect.width(), 18)
        painter.drawText(metadata_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, metadata_text)

    def _on_thumbnail_loaded(self, uuid: str, pixmap: QPixmap):
        """Handle thumbnail loaded signal"""

        # Request repaint for this item
        # The view will handle the repaint when data changes
        if self.parent():
            # Trigger view update
            parent_view = self.parent()
            if hasattr(parent_view, 'viewport'):
                parent_view.viewport().update()


__all__ = ['AnimationCardDelegate']
