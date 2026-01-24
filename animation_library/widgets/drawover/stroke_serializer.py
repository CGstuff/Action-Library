"""
Stroke serializer for data conversion and persistence.

Provides functions for:
- Converting strokes between UV and screen coordinates
- Simplifying point paths
- Scaling legacy stroke data
"""

import math
from typing import List, Dict, Callable
from PyQt6.QtCore import QPointF


def simplify_points(points: List[List[float]], epsilon: float = 1.5) -> List[List[float]]:
    """
    Simplify path using Ramer-Douglas-Peucker algorithm.

    Args:
        points: List of [x, y] points
        epsilon: Simplification threshold (higher = more simplified)

    Returns:
        Simplified list of points
    """
    if len(points) < 3:
        return points

    def perpendicular_distance(point, start, end):
        if start == end:
            return math.sqrt((point[0] - start[0])**2 + (point[1] - start[1])**2)

        n = abs((end[1] - start[1]) * point[0] - (end[0] - start[0]) * point[1] +
               end[0] * start[1] - end[1] * start[0])
        d = math.sqrt((end[1] - start[1])**2 + (end[0] - start[0])**2)
        return n / d if d > 0 else 0

    start, end = points[0], points[-1]
    max_dist = 0
    max_idx = 0

    for i in range(1, len(points) - 1):
        dist = perpendicular_distance(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        left = simplify_points(points[:max_idx + 1], epsilon)
        right = simplify_points(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [start, end]


def scale_stroke(stroke: Dict, scale_x: float, scale_y: float) -> Dict:
    """
    Scale stroke coordinates by given factors (for legacy stroke format).

    Args:
        stroke: Stroke dictionary with pixel coordinates
        scale_x: Horizontal scale factor
        scale_y: Vertical scale factor

    Returns:
        New stroke dictionary with scaled coordinates
    """
    if scale_x == 1.0 and scale_y == 1.0:
        return stroke

    scaled = stroke.copy()
    stroke_type = stroke.get('type', 'path')

    if stroke_type == 'path':
        points = stroke.get('points', [])
        scaled['points'] = [[p[0] * scale_x, p[1] * scale_y] for p in points]

    elif stroke_type == 'brush_path':
        points = stroke.get('points', [])
        scaled['points'] = [[p[0] * scale_x, p[1] * scale_y] for p in points]
        # Scale points_with_pressure
        points_with_pressure = stroke.get('points_with_pressure', [])
        scaled['points_with_pressure'] = [
            [p[0] * scale_x, p[1] * scale_y, p[2] if len(p) > 2 else 1.0]
            for p in points_with_pressure
        ]

    elif stroke_type == 'line':
        start = stroke.get('start', [0, 0])
        end = stroke.get('end', [0, 0])
        scaled['start'] = [start[0] * scale_x, start[1] * scale_y]
        scaled['end'] = [end[0] * scale_x, end[1] * scale_y]

    elif stroke_type == 'arrow':
        start = stroke.get('start', [0, 0])
        end = stroke.get('end', [0, 0])
        scaled['start'] = [start[0] * scale_x, start[1] * scale_y]
        scaled['end'] = [end[0] * scale_x, end[1] * scale_y]
        scaled['head_size'] = stroke.get('head_size', 12) * min(scale_x, scale_y)

    elif stroke_type in ('rect', 'ellipse'):
        bounds = stroke.get('bounds', [0, 0, 100, 100])
        scaled['bounds'] = [
            bounds[0] * scale_x,
            bounds[1] * scale_y,
            bounds[2] * scale_x,
            bounds[3] * scale_y
        ]

    elif stroke_type == 'text':
        position = stroke.get('position', [0, 0])
        scaled['position'] = [position[0] * scale_x, position[1] * scale_y]
        scaled['font_size'] = int(stroke.get('font_size', 14) * min(scale_x, scale_y))

    # Scale stroke width
    scaled['width'] = stroke.get('width', 3) * min(scale_x, scale_y)

    return scaled


def uv_stroke_to_screen(
    stroke: Dict,
    uv_to_screen: Callable[[List[float]], QPointF],
    rect_size: float
) -> Dict:
    """
    Convert UV-normalized stroke to screen coordinates for rendering.

    Args:
        stroke: Stroke data with UV coordinates
        uv_to_screen: Function to convert UV to screen coordinates
        rect_size: Size of the effective rect (for width conversion)

    Returns:
        Stroke data with screen coordinates
    """
    screen_stroke = stroke.copy()
    stroke_type = stroke.get('type', 'path')

    # Convert normalized width to pixels
    normalized_width = stroke.get('width', 0.005)
    screen_stroke['width'] = normalized_width * rect_size

    if stroke_type == 'path':
        points = stroke.get('points', [])
        screen_stroke['points'] = [
            [uv_to_screen(p).x(), uv_to_screen(p).y()]
            for p in points
        ]

    elif stroke_type == 'brush_path':
        # Convert points and points_with_pressure
        points = stroke.get('points', [])
        screen_stroke['points'] = [
            [uv_to_screen(p).x(), uv_to_screen(p).y()]
            for p in points
        ]
        # Convert points_with_pressure (preserve pressure as 3rd element)
        points_with_pressure = stroke.get('points_with_pressure', [])
        screen_stroke['points_with_pressure'] = [
            [uv_to_screen([p[0], p[1]]).x(),
             uv_to_screen([p[0], p[1]]).y(),
             p[2] if len(p) > 2 else 1.0]
            for p in points_with_pressure
        ]

    elif stroke_type == 'line':
        start = stroke.get('start', [0.5, 0.5])
        end = stroke.get('end', [0.5, 0.5])
        start_pt = uv_to_screen(start)
        end_pt = uv_to_screen(end)
        screen_stroke['start'] = [start_pt.x(), start_pt.y()]
        screen_stroke['end'] = [end_pt.x(), end_pt.y()]

    elif stroke_type == 'arrow':
        start = stroke.get('start', [0.5, 0.5])
        end = stroke.get('end', [0.5, 0.5])
        start_pt = uv_to_screen(start)
        end_pt = uv_to_screen(end)
        screen_stroke['start'] = [start_pt.x(), start_pt.y()]
        screen_stroke['end'] = [end_pt.x(), end_pt.y()]
        screen_stroke['head_size'] = stroke.get('head_size', 0.02) * rect_size

    elif stroke_type in ('rect', 'ellipse'):
        bounds = stroke.get('bounds', [0.25, 0.25, 0.5, 0.5])
        top_left = uv_to_screen([bounds[0], bounds[1]])
        # bounds[2] and bounds[3] are width/height in UV space
        bottom_right = uv_to_screen([bounds[0] + bounds[2], bounds[1] + bounds[3]])
        screen_stroke['bounds'] = [
            top_left.x(), top_left.y(),
            bottom_right.x() - top_left.x(),
            bottom_right.y() - top_left.y()
        ]

    elif stroke_type == 'text':
        position = stroke.get('position', [0.5, 0.5])
        pos_pt = uv_to_screen(position)
        screen_stroke['position'] = [pos_pt.x(), pos_pt.y()]
        screen_stroke['font_size'] = int(stroke.get('font_size', 0.02) * rect_size)

    return screen_stroke


__all__ = [
    'simplify_points',
    'scale_stroke',
    'uv_stroke_to_screen'
]
