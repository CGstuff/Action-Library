"""
TextRenderer - Drawing utilities for text on animation cards

Handles drawing of:
- Grid mode text (name below thumbnail)
- List mode text (name and metadata)
"""

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QPainter, QFont, QColor, QFontMetrics

from ...themes.fonts import Fonts


class TextRenderer:
    """Static methods for drawing text on animation cards"""

    @staticmethod
    def draw_grid_text(painter: QPainter, rect: QRect, name: str,
                       palette, is_selected: bool = False) -> None:
        """
        Draw text for grid mode (below thumbnail).

        Args:
            painter: QPainter instance
            rect: Rectangle for text
            name: Animation name to display
            palette: Theme palette with colors
            is_selected: Whether item is selected
        """
        if not name:
            return

        # Draw subtle gray background for non-selected cards
        if not is_selected:
            bg_color = QColor(palette.background_secondary)
            bg_color.setAlpha(30)
            painter.fillRect(rect, bg_color)

        # Set up font
        font = QFont(Fonts.SHOT_CARD_NAME.family, Fonts.SHOT_CARD_NAME.size, QFont.Weight.DemiBold)
        painter.setFont(font)

        # White text on selection
        if is_selected:
            painter.setPen(QColor(palette.selection_text))
        else:
            painter.setPen(QColor(palette.text_primary))

        # Draw name centered (truncate with ellipsis if too long)
        fm = QFontMetrics(font)
        if fm.horizontalAdvance(name) > rect.width():
            name = name[:14] + "..."

        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)

    @staticmethod
    def draw_grid_text_overlay(painter: QPainter, rect: QRect, name: str,
                               palette) -> None:
        """
        Draw text overlaid on thumbnail with semi-transparent background.

        Args:
            painter: QPainter instance
            rect: Rectangle for text overlay
            name: Animation name to display
            palette: Theme palette with colors
        """
        if not name:
            return

        # Draw semi-transparent background for text readability
        bg_color = QColor(palette.background)
        bg_color.setAlpha(180)
        painter.fillRect(rect, bg_color)

        # Set up font
        font = QFont(Fonts.SHOT_CARD_NAME.family, Fonts.SHOT_CARD_NAME.size)
        painter.setFont(font)
        painter.setPen(QColor(palette.text_primary))

        # Draw name (elided if too long)
        fm = QFontMetrics(font)
        elided_name = fm.elidedText(name, Qt.TextElideMode.ElideRight, rect.width() - 8)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, elided_name)

    @staticmethod
    def draw_list_text(painter: QPainter, rect: QRect, name: str,
                       rig_type: str, frame_count: int, fps: int,
                       palette, is_selected: bool = False) -> None:
        """
        Draw text for list mode.

        Args:
            painter: QPainter instance
            rect: Rectangle for text
            name: Animation name
            rig_type: Rig type string
            frame_count: Number of frames
            fps: Frames per second
            palette: Theme palette with colors
            is_selected: Whether item is selected
        """
        # Name (bold)
        font_bold = QFont(Fonts.SHOT_CARD_NAME.family, Fonts.SHOT_CARD_NAME.size + 1)
        font_bold.setBold(True)
        painter.setFont(font_bold)

        # White text on selection
        if is_selected:
            painter.setPen(QColor(palette.selection_text))
        else:
            painter.setPen(QColor(palette.text_primary))

        name_rect = QRect(rect.x(), rect.y(), rect.width(), 20)
        fm = QFontMetrics(font_bold)
        elided_name = fm.elidedText(name or "Unknown", Qt.TextElideMode.ElideRight, name_rect.width())
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_name)

        # Metadata (smaller)
        font_small = QFont(Fonts.SHOT_CARD_DURATION.family, Fonts.SHOT_CARD_DURATION.size)
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
