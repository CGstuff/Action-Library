"""
DrawoverCanvas - Transparent overlay canvas for frame annotations

Provides drawing tools for annotating video frames with:
- Freehand pen
- Straight lines
- Arrows
- Rectangles
- Circles/ellipses
- Text annotations
- Eraser
"""

import math
import uuid as uuid_lib
from enum import Enum
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsPathItem, QGraphicsLineItem, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsPolygonItem,
    QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QLineF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath,
    QPolygonF, QFont, QCursor, QPixmap, QTransform,
    QUndoStack, QUndoCommand
)


class DrawingTool(Enum):
    """Available drawing tools."""
    NONE = 0      # Passthrough mode
    PEN = 1       # Freehand drawing
    LINE = 2      # Straight line
    ARROW = 3     # Arrow with head
    RECT = 4      # Rectangle
    CIRCLE = 5    # Ellipse
    TEXT = 6      # Text annotation
    ERASER = 7    # Remove strokes
    SELECT = 8    # Select/move strokes


# ==================== Undo Commands ====================

class AddStrokeCommand(QUndoCommand):
    """Undo command for adding a stroke."""

    def __init__(self, canvas: 'DrawoverCanvas', item: QGraphicsItem, stroke_data: Dict):
        super().__init__("Add Stroke")
        self._canvas = canvas
        self._item = item
        self._stroke_data = stroke_data

    def redo(self):
        if self._item.scene() is None:
            self._canvas._scene.addItem(self._item)

    def undo(self):
        if self._item.scene() is not None:
            self._canvas._scene.removeItem(self._item)


class RemoveStrokeCommand(QUndoCommand):
    """Undo command for removing a stroke."""

    def __init__(self, canvas: 'DrawoverCanvas', item: QGraphicsItem, stroke_data: Dict):
        super().__init__("Remove Stroke")
        self._canvas = canvas
        self._item = item
        self._stroke_data = stroke_data

    def redo(self):
        if self._item.scene() is not None:
            self._canvas._scene.removeItem(self._item)

    def undo(self):
        if self._item.scene() is None:
            self._canvas._scene.addItem(self._item)


class ClearFrameCommand(QUndoCommand):
    """Undo command for clearing all strokes."""

    def __init__(self, canvas: 'DrawoverCanvas', items: List[Tuple[QGraphicsItem, Dict]]):
        super().__init__("Clear Frame")
        self._canvas = canvas
        self._items = items  # List of (item, stroke_data) tuples

    def redo(self):
        for item, _ in self._items:
            if item.scene() is not None:
                self._canvas._scene.removeItem(item)

    def undo(self):
        for item, _ in self._items:
            if item.scene() is None:
                self._canvas._scene.addItem(item)


# ==================== Canvas ====================

class DrawoverCanvas(QGraphicsView):
    """
    Transparent overlay canvas for frame annotations.

    Features:
    - Multiple drawing tools
    - Undo/redo support
    - Stroke-level data tracking
    - Export to JSON format
    - Import from JSON format
    """

    # Signals
    drawing_started = pyqtSignal()
    drawing_finished = pyqtSignal()
    drawing_modified = pyqtSignal()
    stroke_added = pyqtSignal(dict)  # stroke_data
    stroke_removed = pyqtSignal(str)  # stroke_id

    # Constants
    DEFAULT_COLOR = '#FF5722'
    DEFAULT_BRUSH_SIZE = 3
    MIN_BRUSH_SIZE = 1
    MAX_BRUSH_SIZE = 30

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._scene = QGraphicsScene()
        self._current_tool = DrawingTool.NONE
        self._current_color = QColor(self.DEFAULT_COLOR)
        self._brush_size = self.DEFAULT_BRUSH_SIZE
        self._undo_stack = QUndoStack()

        # Drawing state
        self._is_drawing = False
        self._current_item: Optional[QGraphicsItem] = None
        self._current_path: Optional[QPainterPath] = None
        self._current_points: List[List[float]] = []
        self._start_pos: Optional[QPointF] = None
        self._current_author = ''

        # Stroke tracking
        self._stroke_items: Dict[str, QGraphicsItem] = {}  # stroke_id -> item
        self._item_data: Dict[int, Dict] = {}  # item id -> stroke_data (UV coordinates)

        # Read-only mode (for compare view)
        self._read_only = False

        # Video content rect (for coordinate conversion)
        # This defines the actual video area within the canvas
        # Coordinates are stored as normalized UV (0-1) relative to this rect
        self._video_rect: Optional[QRectF] = None

        self._setup_view()

    def _setup_view(self):
        """Configure the graphics view."""
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # Disable scroll wheel zoom
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

    # ==================== Properties ====================

    @property
    def current_tool(self) -> DrawingTool:
        return self._current_tool

    @property
    def color(self) -> QColor:
        return self._current_color

    @color.setter
    def color(self, value: QColor):
        self._current_color = value

    @property
    def brush_size(self) -> int:
        return self._brush_size

    @brush_size.setter
    def brush_size(self, value: int):
        self._brush_size = max(self.MIN_BRUSH_SIZE, min(self.MAX_BRUSH_SIZE, value))

    @property
    def read_only(self) -> bool:
        return self._read_only

    @read_only.setter
    def read_only(self, value: bool):
        self._read_only = value
        if value:
            self.set_tool(DrawingTool.NONE)

    @property
    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    # ==================== Video Rect & Coordinate Conversion ====================

    def set_video_rect(self, rect: QRectF):
        """
        Set the video content rectangle within the canvas.

        All drawing coordinates are normalized relative to this rect.
        This should be called whenever the video display area changes.

        Args:
            rect: The video content area in canvas coordinates
        """
        self._video_rect = rect
        # Update scene rect to match video rect for proper coordinate mapping
        if rect:
            self._scene.setSceneRect(rect)

    def get_video_rect(self) -> Optional[QRectF]:
        """Get the current video content rectangle."""
        return self._video_rect

    def _get_effective_rect(self) -> QRectF:
        """Get the effective drawing area (video rect or full canvas)."""
        if self._video_rect and self._video_rect.isValid():
            return self._video_rect
        # Fallback to full canvas
        return QRectF(0, 0, self.width(), self.height())

    def _screen_to_uv(self, screen_pos: QPointF) -> List[float]:
        """
        Convert screen coordinates to normalized UV (0-1) coordinates.

        Args:
            screen_pos: Position in screen/scene coordinates

        Returns:
            [u, v] where u and v are in range 0-1
        """
        rect = self._get_effective_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return [0.0, 0.0]

        u = (screen_pos.x() - rect.x()) / rect.width()
        v = (screen_pos.y() - rect.y()) / rect.height()
        return [u, v]

    def _uv_to_screen(self, uv: List[float]) -> QPointF:
        """
        Convert normalized UV (0-1) coordinates to screen coordinates.

        Args:
            uv: [u, v] where u and v are in range 0-1

        Returns:
            Position in screen/scene coordinates
        """
        rect = self._get_effective_rect()
        x = rect.x() + uv[0] * rect.width()
        y = rect.y() + uv[1] * rect.height()
        return QPointF(x, y)

    def _is_inside_video_rect(self, pos: QPointF) -> bool:
        """Check if position is inside the video content area."""
        rect = self._get_effective_rect()
        return rect.contains(pos)

    def _clamp_to_video_rect(self, pos: QPointF) -> QPointF:
        """Clamp position to video content area boundaries."""
        rect = self._get_effective_rect()
        x = max(rect.left(), min(rect.right(), pos.x()))
        y = max(rect.top(), min(rect.bottom(), pos.y()))
        return QPointF(x, y)

    # ==================== Tool Management ====================

    def set_tool(self, tool: DrawingTool):
        """Set the current drawing tool."""
        if self._read_only and tool != DrawingTool.NONE:
            return

        self._current_tool = tool
        self.setCursor(self._get_tool_cursor(tool))

        if tool == DrawingTool.NONE:
            # Passthrough mode - let events go to parent
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.setFocus()

    def _get_tool_cursor(self, tool: DrawingTool) -> QCursor:
        """Get cursor for tool."""
        if tool == DrawingTool.NONE:
            return QCursor(Qt.CursorShape.ArrowCursor)
        elif tool == DrawingTool.PEN:
            return QCursor(Qt.CursorShape.CrossCursor)
        elif tool == DrawingTool.LINE:
            return QCursor(Qt.CursorShape.CrossCursor)
        elif tool == DrawingTool.ARROW:
            return QCursor(Qt.CursorShape.CrossCursor)
        elif tool == DrawingTool.RECT:
            return QCursor(Qt.CursorShape.CrossCursor)
        elif tool == DrawingTool.CIRCLE:
            return QCursor(Qt.CursorShape.CrossCursor)
        elif tool == DrawingTool.TEXT:
            return QCursor(Qt.CursorShape.IBeamCursor)
        elif tool == DrawingTool.ERASER:
            return QCursor(Qt.CursorShape.PointingHandCursor)
        elif tool == DrawingTool.SELECT:
            return QCursor(Qt.CursorShape.ArrowCursor)
        return QCursor(Qt.CursorShape.ArrowCursor)

    def set_author(self, author: str):
        """Set current author for new strokes."""
        self._current_author = author

    # ==================== Mouse Events ====================

    def mousePressEvent(self, event):
        if self._read_only or self._current_tool == DrawingTool.NONE:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            # Only start drawing if inside video rect
            if not self._is_inside_video_rect(pos):
                super().mousePressEvent(event)
                return
            pos = self._clamp_to_video_rect(pos)
            self._start_drawing(pos)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_drawing and self._current_tool != DrawingTool.NONE:
            pos = self.mapToScene(event.pos())
            # Clamp to video rect while drawing
            pos = self._clamp_to_video_rect(pos)
            self._continue_drawing(pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_drawing and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            pos = self._clamp_to_video_rect(pos)
            self._finish_drawing(pos)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # ==================== Drawing ====================

    def _start_drawing(self, pos: QPointF):
        """Start a new stroke."""
        self._is_drawing = True
        self._start_pos = pos
        self.drawing_started.emit()

        if self._current_tool == DrawingTool.PEN:
            self._start_pen(pos)
        elif self._current_tool == DrawingTool.LINE:
            self._start_line(pos)
        elif self._current_tool == DrawingTool.ARROW:
            self._start_arrow(pos)
        elif self._current_tool == DrawingTool.RECT:
            self._start_rect(pos)
        elif self._current_tool == DrawingTool.CIRCLE:
            self._start_circle(pos)
        elif self._current_tool == DrawingTool.TEXT:
            self._add_text(pos)
            self._is_drawing = False
        elif self._current_tool == DrawingTool.ERASER:
            self._erase_at(pos)

    def _continue_drawing(self, pos: QPointF):
        """Continue current stroke."""
        if self._current_tool == DrawingTool.PEN:
            self._continue_pen(pos)
        elif self._current_tool == DrawingTool.LINE:
            self._update_line(pos)
        elif self._current_tool == DrawingTool.ARROW:
            self._update_arrow(pos)
        elif self._current_tool == DrawingTool.RECT:
            self._update_rect(pos)
        elif self._current_tool == DrawingTool.CIRCLE:
            self._update_circle(pos)
        elif self._current_tool == DrawingTool.ERASER:
            self._erase_at(pos)

    def _finish_drawing(self, pos: QPointF):
        """Finish current stroke."""
        self._is_drawing = False

        if self._current_item:
            stroke_data = self._finalize_stroke()
            if stroke_data:
                cmd = AddStrokeCommand(self, self._current_item, stroke_data)
                self._undo_stack.push(cmd)
                self.stroke_added.emit(stroke_data)
                self.drawing_modified.emit()

        self._current_item = None
        self._current_path = None
        self._current_points = []
        self._start_pos = None
        self.drawing_finished.emit()

    # ==================== Pen Tool ====================

    def _start_pen(self, pos: QPointF):
        """Start freehand drawing."""
        self._current_path = QPainterPath()
        self._current_path.moveTo(pos)
        self._current_points = [[pos.x(), pos.y()]]

        self._current_item = QGraphicsPathItem(self._current_path)
        self._current_item.setPen(self._create_pen())
        self._scene.addItem(self._current_item)

    def _continue_pen(self, pos: QPointF):
        """Continue freehand drawing."""
        if self._current_path and self._current_item:
            self._current_path.lineTo(pos)
            self._current_points.append([pos.x(), pos.y()])
            self._current_item.setPath(self._current_path)

    # ==================== Line Tool ====================

    def _start_line(self, pos: QPointF):
        """Start line drawing."""
        self._current_item = QGraphicsLineItem(pos.x(), pos.y(), pos.x(), pos.y())
        self._current_item.setPen(self._create_pen())
        self._scene.addItem(self._current_item)

    def _update_line(self, pos: QPointF):
        """Update line endpoint."""
        if self._current_item and self._start_pos:
            self._current_item.setLine(
                self._start_pos.x(), self._start_pos.y(),
                pos.x(), pos.y()
            )

    # ==================== Arrow Tool ====================

    def _start_arrow(self, pos: QPointF):
        """Start arrow drawing."""
        # Use path item for arrow (line + head)
        self._current_path = QPainterPath()
        self._current_path.moveTo(pos)
        self._current_path.lineTo(pos)

        self._current_item = QGraphicsPathItem(self._current_path)
        self._current_item.setPen(self._create_pen())
        self._scene.addItem(self._current_item)

    def _update_arrow(self, pos: QPointF):
        """Update arrow with head."""
        if self._current_item and self._start_pos:
            path = QPainterPath()
            path.moveTo(self._start_pos)
            path.lineTo(pos)

            # Arrow head
            head_size = max(12, self._brush_size * 3)
            line = QLineF(self._start_pos, pos)
            if line.length() > 0:
                angle = math.atan2(-line.dy(), line.dx())

                p1 = pos + QPointF(
                    math.cos(angle + math.pi * 0.8) * head_size,
                    -math.sin(angle + math.pi * 0.8) * head_size
                )
                p2 = pos + QPointF(
                    math.cos(angle - math.pi * 0.8) * head_size,
                    -math.sin(angle - math.pi * 0.8) * head_size
                )

                path.moveTo(pos)
                path.lineTo(p1)
                path.moveTo(pos)
                path.lineTo(p2)

            self._current_item.setPath(path)

    # ==================== Rectangle Tool ====================

    def _start_rect(self, pos: QPointF):
        """Start rectangle drawing."""
        self._current_item = QGraphicsRectItem(pos.x(), pos.y(), 0, 0)
        self._current_item.setPen(self._create_pen())
        self._scene.addItem(self._current_item)

    def _update_rect(self, pos: QPointF):
        """Update rectangle size."""
        if self._current_item and self._start_pos:
            x = min(self._start_pos.x(), pos.x())
            y = min(self._start_pos.y(), pos.y())
            w = abs(pos.x() - self._start_pos.x())
            h = abs(pos.y() - self._start_pos.y())
            self._current_item.setRect(x, y, w, h)

    # ==================== Circle Tool ====================

    def _start_circle(self, pos: QPointF):
        """Start ellipse drawing."""
        self._current_item = QGraphicsEllipseItem(pos.x(), pos.y(), 0, 0)
        self._current_item.setPen(self._create_pen())
        self._scene.addItem(self._current_item)

    def _update_circle(self, pos: QPointF):
        """Update ellipse size."""
        if self._current_item and self._start_pos:
            x = min(self._start_pos.x(), pos.x())
            y = min(self._start_pos.y(), pos.y())
            w = abs(pos.x() - self._start_pos.x())
            h = abs(pos.y() - self._start_pos.y())
            self._current_item.setRect(x, y, w, h)

    # ==================== Text Tool ====================

    def _add_text(self, pos: QPointF):
        """Add text annotation at position."""
        from PyQt6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(
            self, "Add Text", "Enter annotation text:"
        )

        if ok and text:
            text_item = QGraphicsTextItem(text)
            text_item.setPos(pos)
            text_item.setDefaultTextColor(self._current_color)

            font = QFont('Arial', max(12, self._brush_size * 2))
            text_item.setFont(font)

            self._scene.addItem(text_item)
            self._current_item = text_item

            stroke_data = self._finalize_stroke(text=text)
            if stroke_data:
                cmd = AddStrokeCommand(self, text_item, stroke_data)
                self._undo_stack.push(cmd)
                self.stroke_added.emit(stroke_data)
                self.drawing_modified.emit()

            self._current_item = None

    # ==================== Eraser Tool ====================

    def _erase_at(self, pos: QPointF):
        """Erase strokes at position."""
        items = self._scene.items(pos)
        for item in items:
            if item in self._stroke_items.values():
                stroke_id = None
                for sid, sitem in self._stroke_items.items():
                    if sitem == item:
                        stroke_id = sid
                        break

                if stroke_id:
                    stroke_data = self._item_data.get(id(item), {})
                    cmd = RemoveStrokeCommand(self, item, stroke_data)
                    self._undo_stack.push(cmd)
                    del self._stroke_items[stroke_id]
                    self.stroke_removed.emit(stroke_id)
                    self.drawing_modified.emit()
                    break

    # ==================== Helpers ====================

    def _create_pen(self) -> QPen:
        """Create pen with current settings."""
        pen = QPen(self._current_color, self._brush_size)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def _finalize_stroke(self, text: str = '') -> Optional[Dict]:
        """
        Create stroke data from current item.

        All coordinates are stored as normalized UV (0-1) relative to video rect.
        """
        if not self._current_item:
            return None

        stroke_id = f"stroke_{uuid_lib.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat() + 'Z'

        # Get video rect for normalization
        rect = self._get_effective_rect()
        rect_size = min(rect.width(), rect.height()) if rect.width() > 0 else 1

        # Store width as normalized value (relative to smaller dimension)
        normalized_width = self._brush_size / rect_size if rect_size > 0 else 0.005

        stroke_data = {
            'id': stroke_id,
            'color': self._current_color.name(),
            'opacity': self._current_color.alphaF(),
            'width': normalized_width,  # Normalized stroke width
            'width_px': self._brush_size,  # Keep original for reference
            'created_at': now,
            'author': self._current_author,
            'format': 'uv'  # Mark as UV coordinates
        }

        if self._current_tool == DrawingTool.PEN:
            stroke_data['type'] = 'path'
            stroke_data['tool'] = 'pen'
            # Simplify and convert to UV
            simplified = self._simplify_points(self._current_points)
            stroke_data['points'] = [
                self._screen_to_uv(QPointF(p[0], p[1])) for p in simplified
            ]

        elif self._current_tool == DrawingTool.LINE:
            stroke_data['type'] = 'line'
            stroke_data['tool'] = 'line'
            line = self._current_item.line()
            stroke_data['start'] = self._screen_to_uv(QPointF(line.x1(), line.y1()))
            stroke_data['end'] = self._screen_to_uv(QPointF(line.x2(), line.y2()))

        elif self._current_tool == DrawingTool.ARROW:
            stroke_data['type'] = 'arrow'
            stroke_data['tool'] = 'arrow'
            stroke_data['start'] = self._screen_to_uv(self._start_pos)
            # Get end from last point in path
            path = self._current_item.path()
            end_pt = path.elementAt(1)
            stroke_data['end'] = self._screen_to_uv(QPointF(end_pt.x, end_pt.y))
            # Normalize head size
            stroke_data['head_size'] = max(12, self._brush_size * 3) / rect_size

        elif self._current_tool == DrawingTool.RECT:
            stroke_data['type'] = 'rect'
            stroke_data['tool'] = 'rect'
            item_rect = self._current_item.rect()
            # Convert bounds to UV: [u1, v1, width_uv, height_uv]
            top_left = self._screen_to_uv(QPointF(item_rect.x(), item_rect.y()))
            bottom_right = self._screen_to_uv(QPointF(item_rect.right(), item_rect.bottom()))
            stroke_data['bounds'] = [
                top_left[0], top_left[1],
                bottom_right[0] - top_left[0],
                bottom_right[1] - top_left[1]
            ]
            stroke_data['fill'] = False

        elif self._current_tool == DrawingTool.CIRCLE:
            stroke_data['type'] = 'ellipse'
            stroke_data['tool'] = 'circle'
            item_rect = self._current_item.rect()
            top_left = self._screen_to_uv(QPointF(item_rect.x(), item_rect.y()))
            bottom_right = self._screen_to_uv(QPointF(item_rect.right(), item_rect.bottom()))
            stroke_data['bounds'] = [
                top_left[0], top_left[1],
                bottom_right[0] - top_left[0],
                bottom_right[1] - top_left[1]
            ]
            stroke_data['fill'] = False

        elif self._current_tool == DrawingTool.TEXT:
            stroke_data['type'] = 'text'
            stroke_data['tool'] = 'text'
            stroke_data['position'] = self._screen_to_uv(self._current_item.pos())
            stroke_data['text'] = text
            stroke_data['font_size'] = max(12, self._brush_size * 2) / rect_size

        # Track the item
        self._stroke_items[stroke_id] = self._current_item
        self._item_data[id(self._current_item)] = stroke_data
        self._current_item.setData(0, stroke_id)

        return stroke_data

    def _simplify_points(self, points: List[List[float]], epsilon: float = 1.5) -> List[List[float]]:
        """Simplify path using Ramer-Douglas-Peucker algorithm."""
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
            left = self._simplify_points(points[:max_idx + 1], epsilon)
            right = self._simplify_points(points[max_idx:], epsilon)
            return left[:-1] + right
        else:
            return [start, end]

    # ==================== Data Import/Export ====================

    def clear(self):
        """Clear all strokes."""
        self._scene.clear()
        self._stroke_items.clear()
        self._item_data.clear()
        self._undo_stack.clear()

    def import_strokes(self, strokes: List[Dict], source_canvas_size: Tuple[int, int] = None):
        """
        Import strokes from data.

        Handles both UV-normalized strokes (new format) and legacy absolute pixel strokes.

        Args:
            strokes: List of stroke dictionaries
            source_canvas_size: Original canvas size for legacy strokes (ignored for UV format)
        """
        self.clear()

        for stroke in strokes:
            # Check if stroke uses UV format (new) or legacy pixel format
            if stroke.get('format') == 'uv':
                # Convert UV coordinates to current screen coordinates
                screen_stroke = self._uv_stroke_to_screen(stroke)
            else:
                # Legacy format - use old scaling logic for backward compatibility
                current_w = self.width()
                current_h = self.height()
                if source_canvas_size and source_canvas_size[0] > 0 and source_canvas_size[1] > 0:
                    scale_x = current_w / source_canvas_size[0]
                    scale_y = current_h / source_canvas_size[1]
                else:
                    scale_x = 1.0
                    scale_y = 1.0
                screen_stroke = self._scale_stroke(stroke, scale_x, scale_y)

            item = self._create_item_from_stroke(screen_stroke)
            if item:
                self._scene.addItem(item)
                stroke_id = stroke.get('id', '')
                self._stroke_items[stroke_id] = item
                # Store original UV data for export (not screen coordinates)
                self._item_data[id(item)] = stroke
                item.setData(0, stroke_id)

    def _uv_stroke_to_screen(self, stroke: Dict) -> Dict:
        """
        Convert UV-normalized stroke to screen coordinates for rendering.

        Args:
            stroke: Stroke data with UV coordinates

        Returns:
            Stroke data with screen coordinates
        """
        screen_stroke = stroke.copy()
        stroke_type = stroke.get('type', 'path')
        rect = self._get_effective_rect()
        rect_size = min(rect.width(), rect.height()) if rect.width() > 0 else 1

        # Convert normalized width to pixels
        normalized_width = stroke.get('width', 0.005)
        screen_stroke['width'] = normalized_width * rect_size

        if stroke_type == 'path':
            points = stroke.get('points', [])
            screen_stroke['points'] = [
                [self._uv_to_screen(p).x(), self._uv_to_screen(p).y()]
                for p in points
            ]

        elif stroke_type == 'line':
            start = stroke.get('start', [0.5, 0.5])
            end = stroke.get('end', [0.5, 0.5])
            start_pt = self._uv_to_screen(start)
            end_pt = self._uv_to_screen(end)
            screen_stroke['start'] = [start_pt.x(), start_pt.y()]
            screen_stroke['end'] = [end_pt.x(), end_pt.y()]

        elif stroke_type == 'arrow':
            start = stroke.get('start', [0.5, 0.5])
            end = stroke.get('end', [0.5, 0.5])
            start_pt = self._uv_to_screen(start)
            end_pt = self._uv_to_screen(end)
            screen_stroke['start'] = [start_pt.x(), start_pt.y()]
            screen_stroke['end'] = [end_pt.x(), end_pt.y()]
            screen_stroke['head_size'] = stroke.get('head_size', 0.02) * rect_size

        elif stroke_type == 'rect' or stroke_type == 'ellipse':
            bounds = stroke.get('bounds', [0.25, 0.25, 0.5, 0.5])
            top_left = self._uv_to_screen([bounds[0], bounds[1]])
            # bounds[2] and bounds[3] are width/height in UV space
            bottom_right = self._uv_to_screen([bounds[0] + bounds[2], bounds[1] + bounds[3]])
            screen_stroke['bounds'] = [
                top_left.x(), top_left.y(),
                bottom_right.x() - top_left.x(),
                bottom_right.y() - top_left.y()
            ]

        elif stroke_type == 'text':
            position = stroke.get('position', [0.5, 0.5])
            pos_pt = self._uv_to_screen(position)
            screen_stroke['position'] = [pos_pt.x(), pos_pt.y()]
            screen_stroke['font_size'] = int(stroke.get('font_size', 0.02) * rect_size)

        return screen_stroke

    def export_strokes(self) -> List[Dict]:
        """Export current strokes to data (UV format)."""
        return list(self._item_data.values())

    def get_canvas_size(self) -> Tuple[int, int]:
        """Get current canvas size."""
        return (self.width(), self.height())

    def refresh_strokes(self):
        """
        Redraw all strokes with current video rect.

        Call this when the video rect changes (resize, layout change, etc.)
        to ensure strokes are rendered at correct positions.
        """
        # Get current stroke data (UV format)
        strokes = list(self._item_data.values())
        if not strokes:
            return

        # Re-import to update screen positions
        # Save undo stack state
        can_undo = self._undo_stack.canUndo()

        self.import_strokes(strokes)

        # Undo stack is cleared by import, which is fine for redraw

    def _scale_stroke(self, stroke: Dict, scale_x: float, scale_y: float) -> Dict:
        """Scale stroke coordinates by given factors."""
        if scale_x == 1.0 and scale_y == 1.0:
            return stroke

        scaled = stroke.copy()
        stroke_type = stroke.get('type', 'path')

        if stroke_type == 'path':
            points = stroke.get('points', [])
            scaled['points'] = [[p[0] * scale_x, p[1] * scale_y] for p in points]

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

        elif stroke_type == 'rect' or stroke_type == 'ellipse':
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

    def _create_item_from_stroke(self, stroke: Dict) -> Optional[QGraphicsItem]:
        """Create graphics item from stroke data."""
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

            line = QLineF(start_pt, end_pt)
            if line.length() > 0:
                angle = math.atan2(-line.dy(), line.dx())
                p1 = end_pt + QPointF(
                    math.cos(angle + math.pi * 0.8) * head_size,
                    -math.sin(angle + math.pi * 0.8) * head_size
                )
                p2 = end_pt + QPointF(
                    math.cos(angle - math.pi * 0.8) * head_size,
                    -math.sin(angle - math.pi * 0.8) * head_size
                )
                path.moveTo(end_pt)
                path.lineTo(p1)
                path.moveTo(end_pt)
                path.lineTo(p2)

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

    # ==================== Resize ====================

    def resizeEvent(self, event):
        """Handle resize to fit content."""
        super().resizeEvent(event)
        self.setSceneRect(0, 0, self.width(), self.height())


__all__ = ['DrawoverCanvas', 'DrawingTool']
