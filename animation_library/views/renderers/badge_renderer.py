"""
BadgeRenderer - Drawing utilities for badges on animation cards

Handles drawing of:
- Type badges (action/pose)
- Version badges
- Status badges
- Favorite star
- Comment count badges
- Edit mode checkboxes
- Partial pose indicator
"""

import math
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QPainter, QPixmap, QFont, QPen, QColor, QFontMetrics, QPolygonF, QBrush
from PyQt6.QtCore import QPointF

from ...config import Config


class BadgeRenderer:
    """Static methods for drawing badges on animation cards"""

    @staticmethod
    def draw_checkbox(painter: QPainter, rect: QRect, is_checked: bool, palette) -> None:
        """
        Draw edit mode checkbox.

        Args:
            painter: QPainter instance
            rect: Rectangle for checkbox
            is_checked: Whether checkbox is checked
            palette: Theme palette with colors
        """
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
            painter.drawLine(
                rect.x() + 4, rect.y() + rect.height() // 2,
                rect.x() + rect.width() // 3, rect.y() + rect.height() - 4
            )
            painter.drawLine(
                rect.x() + rect.width() // 3, rect.y() + rect.height() - 4,
                rect.x() + rect.width() - 4, rect.y() + 4
            )

    @staticmethod
    def draw_favorite_star(painter: QPainter, rect: QRect, is_favorite: bool,
                           is_hovered: bool, palette) -> None:
        """
        Draw favorite star icon.

        Args:
            painter: QPainter instance
            rect: Rectangle for star
            is_favorite: Whether item is favorited
            is_hovered: Whether item is being hovered
            palette: Theme palette with colors
        """
        # Calculate star points (5-pointed star)
        cx, cy = rect.center().x(), rect.center().y()
        outer_radius = rect.width() / 2.0 - 2
        inner_radius = outer_radius * 0.4

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
            painter.setBrush(QBrush(QColor(palette.gold_primary)))
            painter.setPen(QPen(QColor(palette.gold_primary), 1))
        else:
            if is_hovered:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#FFFFFF"), 2))
            else:
                color = QColor("#FFFFFF")
                color.setAlpha(80)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(color, 1))

        painter.drawPolygon(star_polygon)

    @staticmethod
    def draw_version_badge(painter: QPainter, rect: QRect, version_label: str) -> None:
        """
        Draw version badge (e.g., v001) on thumbnail.

        Args:
            painter: QPainter instance
            rect: Rectangle for badge
            version_label: Version string to display
        """
        # Disable antialiasing for sharp edges
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Draw semi-transparent background
        bg_color = QColor("#000000")
        bg_color.setAlpha(160)
        painter.fillRect(rect, bg_color)

        # Draw text
        font = QFont("Roboto", 8, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, version_label)

    @staticmethod
    def draw_status_badge(painter: QPainter, rect: QRect, status: str) -> None:
        """
        Draw lifecycle status badge on thumbnail.

        Args:
            painter: QPainter instance
            rect: Rectangle for badge
            status: Status key from Config.LIFECYCLE_STATUSES
        """
        # Disable antialiasing for sharp edges
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Get status info from config
        status_info = Config.LIFECYCLE_STATUSES.get(status, {'label': status.upper(), 'color': '#9E9E9E'})
        color = status_info['color']
        label = status_info['label']

        # Draw colored background
        painter.fillRect(rect, QColor(color))

        # Draw text
        font = QFont("Roboto", 7, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    @staticmethod
    def draw_partial_indicator(painter: QPainter, x: int, y: int, size: int = 10) -> None:
        """
        Draw partial pose indicator (for poses captured with selected bones only).

        Args:
            painter: QPainter instance
            x: X position
            y: Y position
            size: Size of indicator circle
        """
        painter.setBrush(QBrush(QColor("#00ACC1")))  # Cyan/teal
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.drawEllipse(x, y, size, size)

    @staticmethod
    def draw_type_badge(painter: QPainter, rect: QRect, is_pose: bool,
                        action_pixmap: QPixmap, pose_pixmap: QPixmap,
                        badge_size: int = 24) -> None:
        """
        Draw type badge (action or pose) in upper left corner.

        Args:
            painter: QPainter instance
            rect: Rectangle for positioning (typically thumbnail rect)
            is_pose: True for pose badge, False for action badge
            action_pixmap: Cached action badge pixmap
            pose_pixmap: Cached pose badge pixmap
            badge_size: Size of the badge icon
        """
        badge_pixmap = pose_pixmap if is_pose else action_pixmap

        if not badge_pixmap or badge_pixmap.isNull():
            return

        padding = 5
        badge_rect = QRect(
            rect.x() + padding,
            rect.y() + padding,
            badge_size,
            badge_size
        )

        scaled_badge = badge_pixmap.scaled(
            badge_size,
            badge_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        painter.drawPixmap(badge_rect.x(), badge_rect.y(), scaled_badge)

    @staticmethod
    def draw_comment_badge_grid(painter: QPainter, card_rect: QRect, count: int,
                                info_pixmap: QPixmap, card_size: int,
                                star_padding: int, star_size: int) -> None:
        """
        Draw unresolved comment count indicator (grid mode).

        Args:
            painter: QPainter instance
            card_rect: Card rectangle for positioning
            count: Number of unresolved comments
            info_pixmap: Info icon pixmap
            card_size: Size of the card
            star_padding: Padding used for star
            star_size: Size of star icon
        """
        if count <= 0:
            return

        icon_size = 16
        font = QFont("Roboto", 9, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)

        count_text = str(count)
        text_width = fm.horizontalAdvance(count_text)

        x_pos = card_rect.x() + card_size - icon_size - star_padding
        y_pos = card_rect.y() + star_padding + star_size + 3

        if info_pixmap and not info_pixmap.isNull():
            scaled_icon = info_pixmap.scaled(
                icon_size, icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(x_pos, y_pos, scaled_icon)

        text_x = x_pos - text_width - 2
        text_y = y_pos + (icon_size + fm.ascent()) // 2 - 2

        # Shadow
        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(int(text_x + 1), int(text_y + 1), count_text)

        # Main text
        painter.setPen(QColor("#E91E63"))
        painter.drawText(int(text_x), int(text_y), count_text)

    @staticmethod
    def draw_comment_badge_list(painter: QPainter, row_rect: QRect, count: int,
                                info_pixmap: QPixmap,
                                star_size: int, star_padding: int) -> None:
        """
        Draw unresolved comment count indicator (list mode).

        Args:
            painter: QPainter instance
            row_rect: Row rectangle for positioning
            count: Number of unresolved comments
            info_pixmap: Info icon pixmap
            star_size: Size of star icon
            star_padding: Padding used for star
        """
        if count <= 0:
            return

        icon_size = 14
        font = QFont("Roboto", 9, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)

        count_text = str(count)
        text_width = fm.horizontalAdvance(count_text)
        total_width = icon_size + 2 + text_width

        x_pos = row_rect.right() - star_size - star_padding - total_width - 8
        y_pos = row_rect.y() + (row_rect.height() - icon_size) // 2

        if info_pixmap and not info_pixmap.isNull():
            scaled_icon = info_pixmap.scaled(
                icon_size, icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(x_pos, y_pos, scaled_icon)

        text_x = x_pos + icon_size + 2
        text_y = y_pos + (icon_size + fm.ascent()) // 2 - 2

        # Shadow
        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(int(text_x + 1), int(text_y + 1), count_text)

        # Main text
        painter.setPen(QColor("#E91E63"))
        painter.drawText(int(text_x), int(text_y), count_text)
