"""
Ghost/onion skin renderer for drawover canvas.

Provides rendering of neighboring frame strokes with tinting for animation reference.
"""

from typing import Optional, List, Dict, Tuple, Callable

from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QGraphicsPathItem, QGraphicsLineItem,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem,
    QGraphicsItemGroup
)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QColor, QPainterPath, QFont

from .stroke_renderer import add_arrow_head_to_path, render_brush_stroke_to_group
from .stroke_serializer import scale_stroke, uv_stroke_to_screen


class GhostRenderer:
    """
    Manages ghost/onion skin stroke rendering.

    Ghost strokes are semi-transparent versions of strokes from neighboring
    frames, used for animation reference.
    """

    def __init__(self, scene: QGraphicsScene):
        """
        Initialize ghost renderer.

        Args:
            scene: QGraphicsScene to add ghost items to
        """
        self._scene = scene
        self._ghost_items: List[QGraphicsItem] = []

    def clear(self):
        """Remove all ghost strokes from the canvas."""
        for item in self._ghost_items:
            if item.scene() is not None:
                self._scene.removeItem(item)
        self._ghost_items.clear()

    def add_strokes(
        self,
        strokes: List[Dict],
        tint_color: QColor,
        opacity: float,
        canvas_width: int,
        canvas_height: int,
        source_canvas_size: Optional[Tuple[int, int]],
        uv_to_screen: Callable[[List[float]], QPointF],
        rect_size: float
    ):
        """
        Add ghost strokes from another frame with tinting.

        Args:
            strokes: List of stroke dictionaries
            tint_color: Color to tint the ghost strokes
            opacity: Opacity for ghost strokes (0-1)
            canvas_width: Current canvas width
            canvas_height: Current canvas height
            source_canvas_size: Original canvas size for legacy strokes
            uv_to_screen: Function to convert UV to screen coordinates
            rect_size: Size of effective rect for scaling
        """
        for stroke in strokes:
            # Check if stroke uses UV format or legacy
            if stroke.get('format') == 'uv':
                screen_stroke = uv_stroke_to_screen(stroke, uv_to_screen, rect_size)
            else:
                if source_canvas_size and source_canvas_size[0] > 0 and source_canvas_size[1] > 0:
                    scale_x = canvas_width / source_canvas_size[0]
                    scale_y = canvas_height / source_canvas_size[1]
                else:
                    scale_x = 1.0
                    scale_y = 1.0
                screen_stroke = scale_stroke(stroke, scale_x, scale_y)

            # Create ghost item with tint
            item = self._create_ghost_item(screen_stroke, tint_color, opacity)
            if item:
                # Set z-value to render behind normal strokes
                item.setZValue(-1)
                self._scene.addItem(item)
                self._ghost_items.append(item)

    def _create_ghost_item(
        self,
        stroke: Dict,
        tint_color: QColor,
        opacity: float
    ) -> Optional[QGraphicsItem]:
        """
        Create a ghost graphics item with tinting.

        Args:
            stroke: Stroke data in screen coordinates
            tint_color: Color to tint the stroke
            opacity: Opacity value (0-1)

        Returns:
            QGraphicsItem or None
        """
        stroke_type = stroke.get('type', 'path')

        # Apply tint color with opacity
        ghost_color = QColor(tint_color)
        ghost_color.setAlphaF(opacity)

        width = stroke.get('width', 3)
        pen = QPen(ghost_color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        if stroke_type == 'path':
            points = stroke.get('points', [])
            if len(points) >= 2:
                path = QPainterPath()
                path.moveTo(points[0][0], points[0][1])
                for point in points[1:]:
                    path.lineTo(point[0], point[1])
                item = QGraphicsPathItem(path)
                item.setPen(pen)
                return item

        elif stroke_type == 'brush_path':
            # Ghost rendering for pressure-sensitive brush strokes
            points_with_pressure = stroke.get('points_with_pressure', [])
            if len(points_with_pressure) >= 1:
                group = QGraphicsItemGroup()
                render_brush_stroke_to_group(
                    points_with_pressure, width, tint_color, opacity, group
                )
                return group

        elif stroke_type == 'line':
            start = stroke.get('start', [0, 0])
            end = stroke.get('end', [0, 0])
            item = QGraphicsLineItem(start[0], start[1], end[0], end[1])
            item.setPen(pen)
            return item

        elif stroke_type == 'arrow':
            start = stroke.get('start', [0, 0])
            end = stroke.get('end', [0, 0])
            head_size = stroke.get('head_size', 12)

            path = QPainterPath()
            start_pt = QPointF(start[0], start[1])
            end_pt = QPointF(end[0], end[1])

            path.moveTo(start_pt)
            path.lineTo(end_pt)
            add_arrow_head_to_path(path, start_pt, end_pt, head_size)

            item = QGraphicsPathItem(path)
            item.setPen(pen)
            return item

        elif stroke_type == 'rect':
            bounds = stroke.get('bounds', [0, 0, 100, 100])
            item = QGraphicsRectItem(bounds[0], bounds[1], bounds[2], bounds[3])
            item.setPen(pen)
            return item

        elif stroke_type == 'ellipse':
            bounds = stroke.get('bounds', [0, 0, 100, 100])
            item = QGraphicsEllipseItem(bounds[0], bounds[1], bounds[2], bounds[3])
            item.setPen(pen)
            return item

        elif stroke_type == 'text':
            position = stroke.get('position', [0, 0])
            text = stroke.get('text', '')
            font_size = stroke.get('font_size', 14)

            item = QGraphicsTextItem(text)
            item.setPos(position[0], position[1])
            item.setDefaultTextColor(ghost_color)
            item.setFont(QFont('Arial', font_size))
            return item

        return None


__all__ = ['GhostRenderer']
