"""
Coordinate conversion utilities for drawover canvas.

Provides UV/screen coordinate conversion for resolution-independent stroke storage.
"""

from typing import Optional, List
from PyQt6.QtCore import QPointF, QRectF


class CoordinateConverter:
    """
    Handles conversion between screen coordinates and normalized UV coordinates.

    UV coordinates are in the range 0-1 and are resolution-independent.
    This allows strokes to be scaled properly when the canvas size changes.
    """

    def __init__(self):
        self._video_rect: Optional[QRectF] = None

    def set_video_rect(self, rect: QRectF):
        """
        Set the video content rectangle.

        All drawing coordinates are normalized relative to this rect.
        This should be called whenever the video display area changes.

        Args:
            rect: The video content area in canvas coordinates
        """
        self._video_rect = rect

    def get_video_rect(self) -> Optional[QRectF]:
        """Get the current video content rectangle."""
        return self._video_rect

    def get_effective_rect(self, canvas_width: int, canvas_height: int) -> QRectF:
        """
        Get the effective drawing area (video rect or full canvas).

        Args:
            canvas_width: Current canvas width
            canvas_height: Current canvas height

        Returns:
            QRectF representing the effective drawing area
        """
        if self._video_rect and self._video_rect.isValid():
            return self._video_rect
        return QRectF(0, 0, canvas_width, canvas_height)

    def screen_to_uv(self, screen_pos: QPointF, canvas_width: int, canvas_height: int) -> List[float]:
        """
        Convert screen coordinates to normalized UV (0-1) coordinates.

        Args:
            screen_pos: Position in screen/scene coordinates
            canvas_width: Current canvas width
            canvas_height: Current canvas height

        Returns:
            [u, v] where u and v are in range 0-1
        """
        rect = self.get_effective_rect(canvas_width, canvas_height)
        if rect.width() <= 0 or rect.height() <= 0:
            return [0.0, 0.0]

        u = (screen_pos.x() - rect.x()) / rect.width()
        v = (screen_pos.y() - rect.y()) / rect.height()
        return [u, v]

    def uv_to_screen(self, uv: List[float], canvas_width: int, canvas_height: int) -> QPointF:
        """
        Convert normalized UV (0-1) coordinates to screen coordinates.

        Args:
            uv: [u, v] where u and v are in range 0-1
            canvas_width: Current canvas width
            canvas_height: Current canvas height

        Returns:
            Position in screen/scene coordinates
        """
        rect = self.get_effective_rect(canvas_width, canvas_height)
        x = rect.x() + uv[0] * rect.width()
        y = rect.y() + uv[1] * rect.height()
        return QPointF(x, y)

    def is_inside_rect(self, pos: QPointF, canvas_width: int, canvas_height: int) -> bool:
        """
        Check if position is inside the video content area.

        Args:
            pos: Position to check
            canvas_width: Current canvas width
            canvas_height: Current canvas height

        Returns:
            True if position is inside the effective rect
        """
        rect = self.get_effective_rect(canvas_width, canvas_height)
        return rect.contains(pos)

    def clamp_to_rect(self, pos: QPointF, canvas_width: int, canvas_height: int) -> QPointF:
        """
        Clamp position to video content area boundaries.

        Args:
            pos: Position to clamp
            canvas_width: Current canvas width
            canvas_height: Current canvas height

        Returns:
            Clamped position
        """
        rect = self.get_effective_rect(canvas_width, canvas_height)
        x = max(rect.left(), min(rect.right(), pos.x()))
        y = max(rect.top(), min(rect.bottom(), pos.y()))
        return QPointF(x, y)

    def get_rect_size(self, canvas_width: int, canvas_height: int) -> float:
        """
        Get the smaller dimension of the effective rect.

        Useful for normalizing stroke widths.

        Args:
            canvas_width: Current canvas width
            canvas_height: Current canvas height

        Returns:
            Minimum of width and height
        """
        rect = self.get_effective_rect(canvas_width, canvas_height)
        return min(rect.width(), rect.height()) if rect.width() > 0 else 1


__all__ = ['CoordinateConverter']
