"""
ThumbnailRenderer - Drawing utilities for thumbnails on animation cards

Handles drawing of:
- Thumbnail images (with gradient backgrounds)
- Loading placeholders
- Missing image placeholders
"""

from pathlib import Path
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QPainter, QPixmap, QColor


class ThumbnailRenderer:
    """Static methods for drawing thumbnails on animation cards"""

    @staticmethod
    def draw_thumbnail(painter: QPainter, rect: QRect, uuid: str,
                       thumbnail_path_str: str, use_custom_gradient: bool,
                       gradient_top_str: str, gradient_bottom_str: str,
                       thumbnail_loader, theme_manager) -> None:
        """
        Draw thumbnail image with gradient background.

        Args:
            painter: QPainter instance
            rect: Rectangle for thumbnail
            uuid: Animation UUID for cache lookup
            thumbnail_path_str: Path to thumbnail file
            use_custom_gradient: Whether to use custom gradient colors
            gradient_top_str: JSON string of top gradient color
            gradient_bottom_str: JSON string of bottom gradient color
            thumbnail_loader: ThumbnailLoader service instance
            theme_manager: ThemeManager service instance
        """
        if not thumbnail_path_str:
            ThumbnailRenderer.draw_placeholder(painter, rect, theme_manager)
            return

        # Get gradient colors
        gradient_top = None
        gradient_bottom = None

        if use_custom_gradient:
            try:
                import json
                gradient_top = tuple(json.loads(gradient_top_str)) if gradient_top_str else None
                gradient_bottom = tuple(json.loads(gradient_bottom_str)) if gradient_bottom_str else None
            except Exception:
                gradient_top = None
                gradient_bottom = None

        # Use theme gradient if no custom
        if not gradient_top or not gradient_bottom:
            gradient_top, gradient_bottom = theme_manager.get_gradient_colors()

        # Animated preview, if this card has one playing. Sprite frames are
        # keyed to transparent like the thumbnails are, so they composite onto
        # the same gradient and a card looks identical playing or still.
        try:
            from ...services.sprite_playback import get_sprite_playback
            frame = get_sprite_playback().get_frame(uuid)
        except Exception:
            frame = None

        if frame is not None:
            sheet, src = frame
            ThumbnailRenderer._fill_gradient(painter, rect, gradient_top, gradient_bottom)
            painter.drawPixmap(rect, sheet, src)
            return

        # Try to load thumbnail
        thumbnail_path = Path(thumbnail_path_str)

        pixmap = thumbnail_loader.load_thumbnail(
            uuid,
            thumbnail_path,
            gradient_top,
            gradient_bottom,
            use_custom_gradient
        )

        if pixmap:
            target_width = rect.width()
            target_height = rect.height()

            scaled = pixmap.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            painter.drawPixmap(
                rect.x(),
                rect.y(),
                target_width,
                target_height,
                scaled
            )
        else:
            ThumbnailRenderer.draw_loading_placeholder(painter, rect, theme_manager)

    @staticmethod
    def _fill_gradient(painter: QPainter, rect: QRect, top, bottom) -> None:
        """Paint the card's gradient behind a transparent sprite frame.

        Thumbnails get composited onto this gradient when they're loaded; sprite
        frames keep their alpha and are drawn over it here instead, so both
        routes end up looking the same.
        """
        from PyQt6.QtGui import QLinearGradient, QBrush
        grad = QLinearGradient(rect.x(), rect.y(), rect.x(), rect.y() + rect.height())
        grad.setColorAt(0.0, QColor(int(top[0] * 255), int(top[1] * 255), int(top[2] * 255)))
        grad.setColorAt(1.0, QColor(int(bottom[0] * 255), int(bottom[1] * 255), int(bottom[2] * 255)))
        painter.fillRect(rect, QBrush(grad))

    @staticmethod 
    def draw_placeholder(painter: QPainter, rect: QRect, theme_manager) -> None:
        """
        Draw placeholder when no thumbnail exists.

        Args:
            painter: QPainter instance
            rect: Rectangle for placeholder
            theme_manager: ThemeManager service instance
        """
        theme = theme_manager.get_current_theme()
        if theme:
            painter.fillRect(rect, QColor(theme.palette.background_secondary))

        painter.setPen(QColor("#808080"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Image")

    @staticmethod
    def draw_loading_placeholder(painter: QPainter, rect: QRect, theme_manager) -> None:
        """
        Draw placeholder while thumbnail is loading.

        Args:
            painter: QPainter instance
            rect: Rectangle for placeholder
            theme_manager: ThemeManager service instance
        """
        theme = theme_manager.get_current_theme()
        if theme:
            painter.fillRect(rect, QColor(theme.palette.background_secondary))

        painter.setPen(QColor("#A0A0A0"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Loading...")
