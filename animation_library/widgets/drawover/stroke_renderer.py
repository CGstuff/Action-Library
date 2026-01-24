"""
Stroke renderer for creating graphics items from stroke data.

Provides functions to convert stroke dictionaries to QGraphicsItem objects.
"""

import math
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsPathItem, QGraphicsLineItem,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem,
    QGraphicsItemGroup
)
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath, QFont


def add_arrow_head_to_path(
    path: QPainterPath,
    start: QPointF,
    end: QPointF,
    head_size: float
):
    """
    Add arrow head lines to a path.

    Args:
        path: The QPainterPath to add arrow head to
        start: Start point of the arrow line
        end: End point (where arrow head is drawn)
        head_size: Size of the arrow head in pixels
    """
    line = QLineF(start, end)
    if line.length() > 0:
        angle = math.atan2(-line.dy(), line.dx())
        p1 = end + QPointF(
            math.cos(angle + math.pi * 0.8) * head_size,
            -math.sin(angle + math.pi * 0.8) * head_size
        )
        p2 = end + QPointF(
            math.cos(angle - math.pi * 0.8) * head_size,
            -math.sin(angle - math.pi * 0.8) * head_size
        )
        path.moveTo(end)
        path.lineTo(p1)
        path.moveTo(end)
        path.lineTo(p2)


def render_brush_stroke_to_group(
    points_with_pressure: List,
    brush_size: float,
    color: QColor,
    base_opacity: float,
    group: QGraphicsItemGroup
):
    """
    Render pressure-sensitive brush stroke using circle stamping.

    Both size and opacity are pressure-sensitive.

    Args:
        points_with_pressure: List of [x, y, pressure] points
        brush_size: Base brush size in pixels
        color: Stroke color
        base_opacity: Base opacity (0-1)
        group: QGraphicsItemGroup to add circles to
    """
    no_pen = QPen(Qt.PenStyle.NoPen)
    last_point = None
    last_pressure = 1.0

    for point_data in points_with_pressure:
        x, y = point_data[0], point_data[1]
        pressure = point_data[2] if len(point_data) > 2 else 1.0
        current_point = QPointF(x, y)

        if last_point is not None:
            # Interpolate between points
            dx = x - last_point.x()
            dy = y - last_point.y()
            distance = math.sqrt(dx * dx + dy * dy)

            avg_pressure = (last_pressure + pressure) / 2.0
            avg_diameter = max(1.0, brush_size * avg_pressure)
            spacing = max(1.0, avg_diameter * 0.25)

            if distance > 0.1:
                num_stamps = max(1, int(distance / spacing))
                for i in range(1, num_stamps + 1):
                    t = i / num_stamps
                    ix = last_point.x() + dx * t
                    iy = last_point.y() + dy * t
                    ip = last_pressure + (pressure - last_pressure) * t
                    diameter = max(1.0, brush_size * ip)
                    radius = diameter / 2.0
                    ellipse = QGraphicsEllipseItem(
                        ix - radius, iy - radius, diameter, diameter
                    )
                    stamp_color = QColor(color)
                    stamp_color.setAlphaF(max(0.05, base_opacity * ip))
                    ellipse.setBrush(QBrush(stamp_color))
                    ellipse.setPen(no_pen)
                    group.addToGroup(ellipse)
        else:
            # First point - stamp a circle
            diameter = max(1.0, brush_size * pressure)
            radius = diameter / 2.0
            ellipse = QGraphicsEllipseItem(
                x - radius, y - radius, diameter, diameter
            )
            stamp_color = QColor(color)
            stamp_color.setAlphaF(max(0.05, base_opacity * pressure))
            ellipse.setBrush(QBrush(stamp_color))
            ellipse.setPen(no_pen)
            group.addToGroup(ellipse)

        last_point = current_point
        last_pressure = pressure


def create_item_from_stroke(stroke: Dict) -> Optional[QGraphicsItem]:
    """
    Create graphics item from stroke data.

    Args:
        stroke: Stroke dictionary with type, color, width, and geometry data

    Returns:
        QGraphicsItem or None if stroke type is invalid
    """
    stroke_type = stroke.get('type', 'path')
    color = QColor(stroke.get('color', '#FF5722'))
    opacity = stroke.get('opacity', 1.0)
    color.setAlphaF(opacity)
    width = stroke.get('width', 3)

    pen = QPen(color, width)
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
        # Pressure-sensitive brush stroke - render with circle stamping
        points_with_pressure = stroke.get('points_with_pressure', [])
        if len(points_with_pressure) >= 1:
            group = QGraphicsItemGroup()
            # Use original color (without opacity applied) for pressure-based opacity
            base_color = QColor(stroke.get('color', '#FF5722'))
            render_brush_stroke_to_group(
                points_with_pressure, width, base_color, opacity, group
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
        if stroke.get('fill', False):
            item.setBrush(QBrush(color))
        return item

    elif stroke_type == 'ellipse':
        bounds = stroke.get('bounds', [0, 0, 100, 100])
        item = QGraphicsEllipseItem(bounds[0], bounds[1], bounds[2], bounds[3])
        item.setPen(pen)
        if stroke.get('fill', False):
            item.setBrush(QBrush(color))
        return item

    elif stroke_type == 'text':
        position = stroke.get('position', [0, 0])
        text = stroke.get('text', '')
        font_size = stroke.get('font_size', 14)

        item = QGraphicsTextItem(text)
        item.setPos(position[0], position[1])
        item.setDefaultTextColor(color)
        item.setFont(QFont('Arial', font_size))
        return item

    return None


__all__ = [
    'add_arrow_head_to_path',
    'render_brush_stroke_to_group',
    'create_item_from_stroke'
]
