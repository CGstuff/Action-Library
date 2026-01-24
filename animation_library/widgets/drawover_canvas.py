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
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsPathItem, QGraphicsLineItem, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsTextItem,
    QGraphicsItemGroup, QGraphicsPolygonItem, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QEvent
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath,
    QFont, QCursor, QUndoStack, QTabletEvent, QPolygonF
)

# Import from extracted modules
from ..utils.coordinate_utils import CoordinateConverter
from .drawover.undo_commands import AddStrokeCommand, RemoveStrokeCommand
from .drawover.stroke_renderer import (
    add_arrow_head_to_path,
    render_brush_stroke_to_group,
    create_item_from_stroke
)
from .drawover.stroke_serializer import simplify_points, scale_stroke, uv_stroke_to_screen
from .drawover.ghost_renderer import GhostRenderer


class DrawingTool(Enum):
    """Available drawing tools."""
    NONE = 0      # Passthrough mode
    PEN = 1       # Freehand drawing (thin, fixed-width strokes)
    BRUSH = 2     # Variable thickness with pressure sensitivity
    LINE = 3      # Straight line
    ARROW = 4     # Arrow with head
    RECT = 5      # Rectangle
    CIRCLE = 6    # Ellipse
    TEXT = 7      # Text annotation
    ERASER = 8    # Remove strokes
    DIAMOND = 9   # Diamond/keyframe marker (single-click stamp)


class DrawoverCanvas(QGraphicsView):
    """
    Transparent overlay canvas for frame annotations.

    Features:
    - Multiple drawing tools
    - Undo/redo support
    - Stroke-level data tracking
    - Export to JSON format
    - Import from JSON format
    - Ghost/onion skin rendering for neighboring frames
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
    GHOST_OPACITY = 0.4

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._scene = QGraphicsScene()
        self._current_tool = DrawingTool.NONE
        self._current_color = QColor(self.DEFAULT_COLOR)
        self._brush_size = self.DEFAULT_BRUSH_SIZE
        self._opacity = 1.0
        self._undo_stack = QUndoStack()

        # Pressure sensitivity (for tablet/stylus support)
        self._current_pressure = 1.0
        self._tablet_device_down = False
        self._using_tablet = False

        # Drawing state
        self._is_drawing = False
        self._current_item: Optional[QGraphicsItem] = None
        self._current_path: Optional[QPainterPath] = None
        self._current_points: List[List[float]] = []
        self._start_pos: Optional[QPointF] = None
        self._current_author = ''

        # Brush tool state (for circle stamping)
        self._last_brush_point: Optional[QPointF] = None
        self._last_brush_pressure: float = 1.0

        # Stroke tracking
        self._stroke_items: Dict[str, QGraphicsItem] = {}  # stroke_id -> item
        self._item_data: Dict[int, Dict] = {}  # item id -> stroke_data (UV coordinates)

        # Read-only mode (for compare view)
        self._read_only = False

        # Preview cursor for brush/diamond tools
        self._preview_item: Optional[QGraphicsItem] = None

        # Use composition for coordinate conversion and ghost rendering
        self._coord = CoordinateConverter()
        self._ghost = GhostRenderer(self._scene)

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

        # Enable tablet tracking for pressure sensitivity
        self.setAttribute(Qt.WidgetAttribute.WA_TabletTracking, True)

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
        # Refresh preview if brush or diamond tool is active
        if self._preview_item:
            bounds = self._preview_item.boundingRect()
            if not bounds.isEmpty():
                center = bounds.center()
                if self._current_tool == DrawingTool.DIAMOND:
                    self._update_diamond_preview(center)
                elif self._current_tool == DrawingTool.BRUSH:
                    self._update_brush_preview(center)

    @property
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float):
        self._opacity = max(0.0, min(1.0, value))

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
        """Set the video content rectangle within the canvas."""
        self._coord.set_video_rect(rect)
        if rect:
            self._scene.setSceneRect(rect)

    def get_video_rect(self) -> Optional[QRectF]:
        """Get the current video content rectangle."""
        return self._coord.get_video_rect()

    def _get_effective_rect(self) -> QRectF:
        """Get the effective drawing area (video rect or full canvas)."""
        return self._coord.get_effective_rect(self.width(), self.height())

    def _screen_to_uv(self, screen_pos: QPointF) -> List[float]:
        """Convert screen coordinates to normalized UV (0-1) coordinates."""
        return self._coord.screen_to_uv(screen_pos, self.width(), self.height())

    def _uv_to_screen(self, uv: List[float]) -> QPointF:
        """Convert normalized UV (0-1) coordinates to screen coordinates."""
        return self._coord.uv_to_screen(uv, self.width(), self.height())

    def _is_inside_video_rect(self, pos: QPointF) -> bool:
        """Check if position is inside the video content area."""
        return self._coord.is_inside_rect(pos, self.width(), self.height())

    def _clamp_to_video_rect(self, pos: QPointF) -> QPointF:
        """Clamp position to video content area boundaries."""
        return self._coord.clamp_to_rect(pos, self.width(), self.height())

    # ==================== Tool Management ====================

    def set_tool(self, tool: DrawingTool):
        """Set the current drawing tool."""
        if self._read_only and tool != DrawingTool.NONE:
            return

        # Skip if tool hasn't changed (avoids unnecessary focus grab)
        if tool == self._current_tool:
            return

        # Clear any preview when switching tools
        self._clear_preview()

        self._current_tool = tool
        self.setCursor(self._get_tool_cursor(tool))

        if tool == DrawingTool.NONE:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.setFocus()

    def _get_tool_cursor(self, tool: DrawingTool) -> QCursor:
        """Get cursor for tool."""
        if tool == DrawingTool.NONE:
            return QCursor(Qt.CursorShape.ArrowCursor)
        elif tool in (DrawingTool.PEN, DrawingTool.BRUSH, DrawingTool.LINE,
                      DrawingTool.ARROW, DrawingTool.RECT, DrawingTool.CIRCLE,
                      DrawingTool.DIAMOND):
            return QCursor(Qt.CursorShape.CrossCursor)
        elif tool == DrawingTool.TEXT:
            return QCursor(Qt.CursorShape.IBeamCursor)
        elif tool == DrawingTool.ERASER:
            return QCursor(Qt.CursorShape.PointingHandCursor)
        return QCursor(Qt.CursorShape.ArrowCursor)

    def set_author(self, author: str):
        """Set current author for new strokes."""
        self._current_author = author

    # ==================== Event Interception (for Tablet Support) ====================

    def event(self, event):
        """Intercept events at QEvent level to properly handle tablet input."""
        event_type = event.type()

        if event_type in (QEvent.Type.TabletPress, QEvent.Type.TabletMove,
                          QEvent.Type.TabletRelease, QEvent.Type.TabletEnterProximity,
                          QEvent.Type.TabletLeaveProximity):
            self._handle_tablet_event(event)
            return True

        return super().event(event)

    # ==================== Tablet Events (Pressure Sensitivity) ====================

    def _handle_tablet_event(self, event: QTabletEvent):
        """Handle tablet/stylus input with pressure sensitivity."""
        event_type = event.type()

        if event_type == QEvent.Type.TabletEnterProximity:
            self._using_tablet = True
            return
        elif event_type == QEvent.Type.TabletLeaveProximity:
            self._using_tablet = False
            self._tablet_device_down = False
            return

        self._current_pressure = event.pressure()

        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
        pos = self.mapToScene(local_pos)

        if event_type == QEvent.Type.TabletPress:
            self._using_tablet = True
            self._tablet_device_down = True

            if self._read_only or self._current_tool == DrawingTool.NONE:
                return
            if not self._is_inside_video_rect(pos):
                return
            pos = self._clamp_to_video_rect(pos)
            self._start_drawing(pos)

        elif event_type == QEvent.Type.TabletMove:
            if self._tablet_device_down and self._is_drawing and self._current_tool != DrawingTool.NONE:
                pos = self._clamp_to_video_rect(pos)
                self._continue_drawing(pos)

        elif event_type == QEvent.Type.TabletRelease:
            self._tablet_device_down = False
            if self._is_drawing:
                pos = self._clamp_to_video_rect(pos)
                self._finish_drawing(pos)
            self._current_pressure = 1.0

    # ==================== Mouse Events ====================

    def mousePressEvent(self, event):
        if self._tablet_device_down:
            event.ignore()
            return

        self._current_pressure = 1.0
        if self._read_only or self._current_tool == DrawingTool.NONE:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            if not self._is_inside_video_rect(pos):
                super().mousePressEvent(event)
                return
            pos = self._clamp_to_video_rect(pos)
            self._start_drawing(pos)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._tablet_device_down:
            event.ignore()
            return

        self._current_pressure = 1.0
        if self._is_drawing and self._current_tool != DrawingTool.NONE:
            pos = self.mapToScene(event.pos())
            pos = self._clamp_to_video_rect(pos)
            self._continue_drawing(pos)
            event.accept()
        elif self._current_tool in (DrawingTool.DIAMOND, DrawingTool.BRUSH):
            # Show preview cursor for diamond/brush tool
            pos = self.mapToScene(event.pos())
            if self._is_inside_video_rect(pos):
                if self._current_tool == DrawingTool.DIAMOND:
                    self._update_diamond_preview(pos)
                else:
                    self._update_brush_preview(pos)
            else:
                self._clear_preview()
            event.accept()
        else:
            self._clear_preview()
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._tablet_device_down:
            event.ignore()
            return

        if self._is_drawing and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            pos = self._clamp_to_video_rect(pos)
            self._finish_drawing(pos)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        """Clear preview when mouse leaves canvas."""
        self._clear_preview()
        super().leaveEvent(event)

    # ==================== Drawing ====================

    def _start_drawing(self, pos: QPointF):
        """Start a new stroke."""
        self._clear_preview()  # Hide preview when drawing starts
        self._is_drawing = True
        self._start_pos = pos
        self.drawing_started.emit()

        if self._current_tool == DrawingTool.PEN:
            self._start_pen(pos)
        elif self._current_tool == DrawingTool.BRUSH:
            self._start_brush(pos)
        elif self._current_tool == DrawingTool.LINE:
            self._start_line(pos)
        elif self._current_tool == DrawingTool.ARROW:
            self._start_arrow(pos)
        elif self._current_tool == DrawingTool.RECT:
            self._start_rect(pos)
        elif self._current_tool == DrawingTool.CIRCLE:
            self._start_circle(pos)
        elif self._current_tool == DrawingTool.DIAMOND:
            self._start_diamond(pos)
            self._is_drawing = False  # Diamond is single-click stamp
        elif self._current_tool == DrawingTool.TEXT:
            self._add_text(pos)
            self._is_drawing = False
        elif self._current_tool == DrawingTool.ERASER:
            self._erase_at(pos)

    def _continue_drawing(self, pos: QPointF):
        """Continue current stroke."""
        if self._current_tool == DrawingTool.PEN:
            self._continue_pen(pos)
        elif self._current_tool == DrawingTool.BRUSH:
            self._continue_brush(pos)
        elif self._current_tool == DrawingTool.LINE:
            self._update_line(pos)
        elif self._current_tool == DrawingTool.ARROW:
            self._update_arrow(pos)
        elif self._current_tool == DrawingTool.RECT:
            self._update_shape_bounds(pos)
        elif self._current_tool == DrawingTool.CIRCLE:
            self._update_shape_bounds(pos)
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
        self._last_brush_point = None
        self._last_brush_pressure = 1.0

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

    # ==================== Brush Tool (Pressure Sensitive) ====================

    def _start_brush(self, pos: QPointF):
        """Start pressure-sensitive brush drawing using circle stamping."""
        self._current_item = QGraphicsItemGroup()
        self._scene.addItem(self._current_item)

        self._current_points = [[pos.x(), pos.y(), self._current_pressure]]
        self._last_brush_point = pos
        self._last_brush_pressure = self._current_pressure

        self._stamp_brush_circle(pos, self._current_pressure)

    def _continue_brush(self, pos: QPointF):
        """Continue pressure-sensitive brush drawing with circle stamping."""
        if not self._current_item or not self._last_brush_point:
            return

        self._current_points.append([pos.x(), pos.y(), self._current_pressure])

        self._interpolate_brush_stamps(
            self._last_brush_point, self._last_brush_pressure,
            pos, self._current_pressure
        )

        self._last_brush_point = pos
        self._last_brush_pressure = self._current_pressure

    def _stamp_brush_circle(self, pos: QPointF, pressure: float):
        """Stamp a single filled circle at the given position."""
        diameter = max(1.0, self._brush_size * pressure)
        radius = diameter / 2.0

        ellipse = QGraphicsEllipseItem(
            pos.x() - radius,
            pos.y() - radius,
            diameter,
            diameter
        )

        color = QColor(self._current_color)
        pressure_opacity = self._opacity * pressure
        color.setAlphaF(max(0.05, pressure_opacity))
        ellipse.setBrush(QBrush(color))
        ellipse.setPen(QPen(Qt.PenStyle.NoPen))

        self._current_item.addToGroup(ellipse)

    def _interpolate_brush_stamps(self, p1: QPointF, pressure1: float,
                                   p2: QPointF, pressure2: float):
        """Interpolate circles between two points to create smooth strokes."""
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 0.1:
            self._stamp_brush_circle(p2, pressure2)
            return

        avg_pressure = (pressure1 + pressure2) / 2.0
        avg_diameter = max(1.0, self._brush_size * avg_pressure)
        spacing = max(1.0, avg_diameter * 0.25)

        num_stamps = max(1, int(distance / spacing))

        for i in range(1, num_stamps + 1):
            t = i / num_stamps
            x = p1.x() + dx * t
            y = p1.y() + dy * t
            pressure = pressure1 + (pressure2 - pressure1) * t
            self._stamp_brush_circle(QPointF(x, y), pressure)

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

            head_size = max(12, self._brush_size * 3)
            add_arrow_head_to_path(path, self._start_pos, pos, head_size)

            self._current_item.setPath(path)

    # ==================== Rectangle Tool ====================

    def _start_rect(self, pos: QPointF):
        """Start rectangle drawing."""
        self._current_item = QGraphicsRectItem(pos.x(), pos.y(), 0, 0)
        self._current_item.setPen(self._create_pen())
        self._scene.addItem(self._current_item)

    # ==================== Circle Tool ====================

    def _start_circle(self, pos: QPointF):
        """Start ellipse drawing."""
        self._current_item = QGraphicsEllipseItem(pos.x(), pos.y(), 0, 0)
        self._current_item.setPen(self._create_pen())
        self._scene.addItem(self._current_item)

    def _update_shape_bounds(self, pos: QPointF):
        """Update rect/ellipse bounds from start_pos to pos."""
        if self._current_item and self._start_pos:
            x = min(self._start_pos.x(), pos.x())
            y = min(self._start_pos.y(), pos.y())
            w = abs(pos.x() - self._start_pos.x())
            h = abs(pos.y() - self._start_pos.y())
            self._current_item.setRect(x, y, w, h)

    # ==================== Diamond Tool (Single-Click Stamp) ====================

    def _start_diamond(self, pos: QPointF):
        """Create a diamond shape at the clicked position (single-click stamp).

        Diamond size scales with brush_size (size = brush_size * 3).
        This is a keyframe/marker stamp, not a drag-to-draw shape.
        """
        # Size scales with brush_size slider
        size = self._brush_size * 3
        half = size / 2.0

        # Create diamond points (top, right, bottom, left)
        top = QPointF(pos.x(), pos.y() - half)
        right = QPointF(pos.x() + half, pos.y())
        bottom = QPointF(pos.x(), pos.y() + half)
        left = QPointF(pos.x() - half, pos.y())

        polygon = QPolygonF([top, right, bottom, left])

        self._current_item = QGraphicsPolygonItem(polygon)

        # Filled diamond with current color and opacity
        color = QColor(self._current_color)
        color.setAlphaF(self._opacity)
        self._current_item.setPen(QPen(Qt.PenStyle.NoPen))  # No outline
        self._current_item.setBrush(QBrush(color))

        self._scene.addItem(self._current_item)

        # Store position and size for serialization
        self._diamond_center = pos
        self._diamond_size = size

        # Immediately finalize as this is a single-click stamp
        stroke_data = self._finalize_diamond_stroke()
        if stroke_data:
            cmd = AddStrokeCommand(self, self._current_item, stroke_data)
            self._undo_stack.push(cmd)
            self.stroke_added.emit(stroke_data)
            self.drawing_modified.emit()

        self._current_item = None
        self.drawing_finished.emit()

    def _finalize_diamond_stroke(self) -> Optional[Dict]:
        """Create stroke data for diamond shape in UV coordinates."""
        if not self._current_item or not hasattr(self, '_diamond_center'):
            return None

        rect = self._get_effective_rect()
        if rect.isEmpty():
            return None

        # Convert center position to UV coordinates
        center_uv = self._screen_to_uv(self._diamond_center)

        # Normalize size relative to rect size
        size_normalized = self._diamond_size / max(rect.width(), rect.height())

        stroke_id = str(uuid_lib.uuid4())

        stroke_data = {
            'id': stroke_id,
            'type': 'diamond',
            'tool': 'diamond',
            'color': self._current_color.name(),
            'opacity': self._opacity,
            'position': center_uv,
            'size': size_normalized,
            'size_px': self._diamond_size,
            'fill': True,
            'format': 'uv',
            'created_at': datetime.now().isoformat(),
            'author': self._current_author
        }

        self._stroke_items[stroke_id] = self._current_item
        self._item_data[id(self._current_item)] = stroke_data

        return stroke_data

    # ==================== Preview Cursors (Brush/Diamond) ====================

    def _update_diamond_preview(self, pos: QPointF):
        """Show/update diamond preview cursor at position."""
        size = self._brush_size * 3
        half = size / 2

        # Diamond points centered on position
        top = QPointF(pos.x(), pos.y() - half)
        right = QPointF(pos.x() + half, pos.y())
        bottom = QPointF(pos.x(), pos.y() + half)
        left = QPointF(pos.x() - half, pos.y())

        polygon = QPolygonF([top, right, bottom, left])

        # Check if we need to recreate the preview item (wrong type)
        if self._preview_item is not None and not isinstance(self._preview_item, QGraphicsPolygonItem):
            self._clear_preview()

        if self._preview_item is None:
            self._preview_item = QGraphicsPolygonItem(polygon)
            # Preview: semi-transparent fill with dashed outline
            color = QColor(self._current_color)
            color.setAlphaF(self._opacity * 0.5)
            self._preview_item.setBrush(QBrush(color))
            outline = QColor(self._current_color)
            outline.setAlphaF(self._opacity)
            self._preview_item.setPen(QPen(outline, 1, Qt.PenStyle.DashLine))
            self._preview_item.setZValue(1000)  # On top
            self._scene.addItem(self._preview_item)
        else:
            self._preview_item.setPolygon(polygon)
            # Update colors in case they changed
            color = QColor(self._current_color)
            color.setAlphaF(self._opacity * 0.5)
            self._preview_item.setBrush(QBrush(color))
            outline = QColor(self._current_color)
            outline.setAlphaF(self._opacity)
            self._preview_item.setPen(QPen(outline, 1, Qt.PenStyle.DashLine))

    def _update_brush_preview(self, pos: QPointF):
        """Show/update brush size preview cursor at position."""
        diameter = self._brush_size
        radius = diameter / 2

        # Check if we need to recreate the preview item (wrong type)
        if self._preview_item is not None and not isinstance(self._preview_item, QGraphicsEllipseItem):
            self._clear_preview()

        if self._preview_item is None:
            self._preview_item = QGraphicsEllipseItem(
                pos.x() - radius, pos.y() - radius, diameter, diameter
            )
            # Preview: semi-transparent fill with dashed outline
            color = QColor(self._current_color)
            color.setAlphaF(self._opacity * 0.3)
            self._preview_item.setBrush(QBrush(color))
            outline = QColor(self._current_color)
            outline.setAlphaF(self._opacity)
            self._preview_item.setPen(QPen(outline, 1, Qt.PenStyle.DashLine))
            self._preview_item.setZValue(1000)  # On top
            self._scene.addItem(self._preview_item)
        else:
            self._preview_item.setRect(pos.x() - radius, pos.y() - radius, diameter, diameter)
            # Update colors in case they changed
            color = QColor(self._current_color)
            color.setAlphaF(self._opacity * 0.3)
            self._preview_item.setBrush(QBrush(color))
            outline = QColor(self._current_color)
            outline.setAlphaF(self._opacity)
            self._preview_item.setPen(QPen(outline, 1, Qt.PenStyle.DashLine))

    def _clear_preview(self):
        """Remove preview cursor from scene."""
        if self._preview_item is not None:
            if self._preview_item.scene() is not None:
                self._scene.removeItem(self._preview_item)
            self._preview_item = None

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

    def _get_current_width(self) -> int:
        """Get stroke width based on tool and pressure.

        Only BRUSH uses brush_size slider. Other tools use fixed widths:
        - PEN: fixed 2px
        - BRUSH: brush_size * pressure
        - LINE, ARROW, RECT, CIRCLE: fixed 3px
        """
        if self._current_tool == DrawingTool.PEN:
            return 2  # Fixed thin width for pen
        elif self._current_tool == DrawingTool.BRUSH:
            return max(1, int(self._brush_size * self._current_pressure))
        else:
            # LINE, ARROW, RECT, CIRCLE use fixed width (not affected by brush size slider)
            return 3

    def _create_pen(self) -> QPen:
        """Create pen with current settings including opacity and tool-specific width."""
        color = QColor(self._current_color)
        color.setAlphaF(self._opacity)

        width = self._get_current_width()

        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def _finalize_stroke(self, text: str = '') -> Optional[Dict]:
        """Create stroke data from current item (UV coordinates)."""
        if not self._current_item:
            return None

        stroke_id = f"stroke_{uuid_lib.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat() + 'Z'

        rect = self._get_effective_rect()
        rect_size = min(rect.width(), rect.height()) if rect.width() > 0 else 1

        # Use actual drawing width (respects tool-specific fixed widths)
        # This ensures PEN=2px, LINE/ARROW/RECT/CIRCLE=3px, BRUSH=brush_size*pressure
        actual_width = self._get_current_width()
        normalized_width = actual_width / rect_size if rect_size > 0 else 0.005

        stroke_data = {
            'id': stroke_id,
            'color': self._current_color.name(),
            'opacity': self._opacity,
            'width': normalized_width,
            'width_px': actual_width,
            'created_at': now,
            'author': self._current_author,
            'format': 'uv'
        }

        if self._current_tool == DrawingTool.PEN:
            stroke_data['type'] = 'path'
            stroke_data['tool'] = 'pen'
            simplified = simplify_points(self._current_points)
            stroke_data['points'] = [
                self._screen_to_uv(QPointF(p[0], p[1])) for p in simplified
            ]

        elif self._current_tool == DrawingTool.BRUSH:
            stroke_data['type'] = 'brush_path'
            stroke_data['tool'] = 'brush'
            stroke_data['points_with_pressure'] = [
                [*self._screen_to_uv(QPointF(p[0], p[1])), p[2] if len(p) > 2 else 1.0]
                for p in self._current_points
            ]
            points_2d = [[p[0], p[1]] for p in self._current_points]
            simplified = simplify_points(points_2d)
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
            path = self._current_item.path()
            end_pt = path.elementAt(1)
            stroke_data['end'] = self._screen_to_uv(QPointF(end_pt.x, end_pt.y))
            stroke_data['head_size'] = max(12, self._brush_size * 3) / rect_size

        elif self._current_tool == DrawingTool.RECT:
            stroke_data['type'] = 'rect'
            stroke_data['tool'] = 'rect'
            item_rect = self._current_item.rect()
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

        self._stroke_items[stroke_id] = self._current_item
        self._item_data[id(self._current_item)] = stroke_data
        self._current_item.setData(0, stroke_id)

        return stroke_data

    # ==================== Ghost/Onion Skin ====================

    def clear_ghost_strokes(self):
        """Remove all ghost strokes from the canvas."""
        self._ghost.clear()

    def has_ghost_strokes(self) -> bool:
        """Check if there are any ghost strokes rendered."""
        return len(self._ghost._ghost_items) > 0

    def add_ghost_strokes(
        self,
        strokes: List[Dict],
        tint_color: QColor,
        opacity: float = 0.4,
        source_canvas_size: Tuple[int, int] = None
    ):
        """Add ghost strokes from another frame with tinting."""
        rect_size = self._coord.get_rect_size(self.width(), self.height())
        self._ghost.add_strokes(
            strokes=strokes,
            tint_color=tint_color,
            opacity=opacity,
            canvas_width=self.width(),
            canvas_height=self.height(),
            source_canvas_size=source_canvas_size,
            uv_to_screen=self._uv_to_screen,
            rect_size=rect_size
        )

    # ==================== Data Import/Export ====================

    def clear(self):
        """Clear all strokes (including ghost strokes)."""
        self.clear_ghost_strokes()
        self._scene.clear()
        self._stroke_items.clear()
        self._item_data.clear()
        self._undo_stack.clear()

    def import_strokes(self, strokes: List[Dict], source_canvas_size: Tuple[int, int] = None):
        """Import strokes from data."""
        self.clear()

        rect_size = self._coord.get_rect_size(self.width(), self.height())

        for stroke in strokes:
            if stroke.get('format') == 'uv':
                screen_stroke = uv_stroke_to_screen(stroke, self._uv_to_screen, rect_size)
            else:
                current_w = self.width()
                current_h = self.height()
                if source_canvas_size and source_canvas_size[0] > 0 and source_canvas_size[1] > 0:
                    scale_x = current_w / source_canvas_size[0]
                    scale_y = current_h / source_canvas_size[1]
                else:
                    scale_x = 1.0
                    scale_y = 1.0
                screen_stroke = scale_stroke(stroke, scale_x, scale_y)

            item = create_item_from_stroke(screen_stroke)
            if item:
                self._scene.addItem(item)
                stroke_id = stroke.get('id', '')
                self._stroke_items[stroke_id] = item
                self._item_data[id(item)] = stroke
                item.setData(0, stroke_id)

    def export_strokes(self) -> List[Dict]:
        """Export current strokes to data (UV format)."""
        return list(self._item_data.values())

    def get_canvas_size(self) -> Tuple[int, int]:
        """Get current canvas size."""
        return (self.width(), self.height())

    def refresh_strokes(self):
        """Redraw all strokes with current video rect."""
        strokes = list(self._item_data.values())
        if not strokes:
            return
        self.import_strokes(strokes)

    # ==================== Resize ====================

    def resizeEvent(self, event):
        """Handle resize to fit content."""
        super().resizeEvent(event)
        self.setSceneRect(0, 0, self.width(), self.height())


__all__ = ['DrawoverCanvas', 'DrawingTool']
