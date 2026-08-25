# Phase 2: Drawover & Advanced Review System Design

## Overview

Phase 2 extends the review notes system with visual annotation capabilities, enabling frame-specific drawings (drawovers) similar to SyncSketch and Loom. This document covers architecture, data formats, storage, permissions, and UI design.

---

## 1. Overlay Canvas Architecture

### Technology Choice: QGraphicsView + QGraphicsScene

Using Qt's graphics framework provides:
- Hardware-accelerated rendering
- Built-in item management (undo/redo support)
- Vector-based drawing with rasterization option
- Smooth pan/zoom capabilities
- Event handling for drawing tools

### Component Stack

```
┌─────────────────────────────────────────────┐
│            DrawoverOverlay (QWidget)         │  ← Transparent overlay
├─────────────────────────────────────────────┤
│         QGraphicsView (viewport)             │  ← Renders scene
├─────────────────────────────────────────────┤
│         QGraphicsScene (canvas)              │  ← Contains items
├─────────────────────────────────────────────┤
│   QGraphicsPathItem, QGraphicsLineItem...   │  ← Drawing elements
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│           VideoPreviewWidget                 │  ← Video underneath
└─────────────────────────────────────────────┘
```

### Class Design

```python
class DrawoverCanvas(QGraphicsView):
    """
    Transparent overlay canvas for frame annotations.

    Features:
    - Freehand drawing (QPainterPath)
    - Straight lines (Shift+drag)
    - Arrows (directional indicators)
    - Text annotations
    - Shapes (rectangles, circles)
    - Eraser tool
    - Color picker
    - Brush size control
    - Undo/redo stack
    """

    # Signals
    drawing_started = pyqtSignal()
    drawing_finished = pyqtSignal()
    drawing_modified = pyqtSignal()

    # Tool modes
    class Tool(Enum):
        NONE = 0      # Passthrough mode (clicks go to video)
        PEN = 1       # Freehand drawing
        LINE = 2      # Straight line
        ARROW = 3     # Arrow with head
        RECT = 4      # Rectangle
        CIRCLE = 5    # Ellipse
        TEXT = 6      # Text annotation
        ERASER = 7    # Remove strokes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self._current_tool = Tool.NONE
        self._current_color = QColor('#FF5722')  # Default orange
        self._brush_size = 3
        self._undo_stack = QUndoStack()
        self._current_path = None
        self._frame_drawings: Dict[int, List[QGraphicsItem]] = {}

        self._setup_view()

    def _setup_view(self):
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background: transparent; border: none;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

    def set_frame(self, frame: int):
        """Switch to drawings for specific frame."""
        self._save_current_frame()
        self._current_frame = frame
        self._load_frame_drawings(frame)

    def enable_drawing(self, tool: Tool):
        """Enable drawing mode with specified tool."""
        self._current_tool = tool
        self.setCursor(self._get_tool_cursor(tool))
        self.setFocus()

    def disable_drawing(self):
        """Return to passthrough mode."""
        self._current_tool = Tool.NONE
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def export_to_png(self, path: Path, frame: int) -> bool:
        """Export frame's drawings to PNG with transparency."""
        ...

    def export_to_json(self, path: Path, frame: int) -> dict:
        """Export frame's drawings to vector JSON format."""
        ...

    def import_from_json(self, data: dict, frame: int):
        """Load drawings from vector JSON."""
        ...
```

### Drawing Tools Implementation

```python
class DrawingTool(ABC):
    """Base class for drawing tools."""

    @abstractmethod
    def on_press(self, pos: QPointF, canvas: DrawoverCanvas): ...

    @abstractmethod
    def on_move(self, pos: QPointF, canvas: DrawoverCanvas): ...

    @abstractmethod
    def on_release(self, pos: QPointF, canvas: DrawoverCanvas): ...


class PenTool(DrawingTool):
    """Freehand drawing tool."""

    def on_press(self, pos, canvas):
        self._path = QPainterPath()
        self._path.moveTo(pos)
        self._item = QGraphicsPathItem(self._path)
        self._item.setPen(QPen(canvas.color, canvas.brush_size,
                               Qt.PenStyle.SolidLine,
                               Qt.PenCapStyle.RoundCap,
                               Qt.PenJoinStyle.RoundJoin))
        canvas.scene().addItem(self._item)

    def on_move(self, pos, canvas):
        self._path.lineTo(pos)
        self._item.setPath(self._path)

    def on_release(self, pos, canvas):
        # Simplify path for storage efficiency
        self._path = self._simplify_path(self._path, tolerance=1.0)
        self._item.setPath(self._path)
        canvas.add_to_undo_stack(self._item)


class ArrowTool(DrawingTool):
    """Arrow with directional head."""

    def on_release(self, pos, canvas):
        # Create line with arrow head
        line = QLineF(self._start, pos)
        arrow_size = 12

        # Calculate arrow head points
        angle = math.atan2(-line.dy(), line.dx())
        p1 = pos + QPointF(
            math.cos(angle + math.pi * 0.8) * arrow_size,
            -math.sin(angle + math.pi * 0.8) * arrow_size
        )
        p2 = pos + QPointF(
            math.cos(angle - math.pi * 0.8) * arrow_size,
            -math.sin(angle - math.pi * 0.8) * arrow_size
        )

        # Create arrow as path
        path = QPainterPath()
        path.moveTo(self._start)
        path.lineTo(pos)
        path.moveTo(pos)
        path.lineTo(p1)
        path.moveTo(pos)
        path.lineTo(p2)

        item = QGraphicsPathItem(path)
        item.setPen(QPen(canvas.color, canvas.brush_size))
        canvas.scene().addItem(item)
```

---

## 2. Drawing Data Format

### Decision: Hybrid Approach (Vector JSON + PNG Cache)

**Primary Storage: Vector JSON**
- Editable, resolution-independent
- Small file size
- Supports undo/redo reconstruction
- Can re-render at any resolution

**Secondary: PNG Cache**
- Pre-rendered for fast display
- Generated on-demand
- Invalidated when JSON changes

### Vector JSON Schema

```json
{
    "version": "1.0",
    "frame": 125,
    "canvas_size": [1920, 1080],
    "created_at": "2024-01-15T10:30:00Z",
    "modified_at": "2024-01-15T11:45:00Z",
    "author": "john.smith",
    "strokes": [
        {
            "id": "stroke_001",
            "type": "path",
            "tool": "pen",
            "color": "#FF5722",
            "opacity": 1.0,
            "width": 3,
            "points": [
                [100.5, 200.3],
                [102.1, 201.5],
                [105.0, 203.2]
            ],
            "created_at": "2024-01-15T10:30:15Z",
            "author": "john.smith"
        },
        {
            "id": "stroke_002",
            "type": "arrow",
            "tool": "arrow",
            "color": "#4CAF50",
            "opacity": 1.0,
            "width": 2,
            "start": [300, 400],
            "end": [500, 350],
            "head_size": 12,
            "created_at": "2024-01-15T10:31:00Z",
            "author": "jane.doe"
        },
        {
            "id": "stroke_003",
            "type": "text",
            "tool": "text",
            "color": "#FFFFFF",
            "background": "#000000",
            "opacity": 0.8,
            "font_size": 14,
            "position": [600, 100],
            "text": "Fix this arc",
            "created_at": "2024-01-15T10:32:00Z",
            "author": "john.smith"
        },
        {
            "id": "stroke_004",
            "type": "rect",
            "tool": "rect",
            "color": "#F44336",
            "opacity": 0.5,
            "width": 2,
            "fill": false,
            "bounds": [200, 300, 150, 100],
            "created_at": "2024-01-15T10:33:00Z",
            "author": "john.smith"
        }
    ],
    "deleted_strokes": [
        {
            "id": "stroke_000",
            "deleted_at": "2024-01-15T10:35:00Z",
            "deleted_by": "jane.doe",
            "original_data": { ... }
        }
    ]
}
```

### Stroke Types

| Type | Fields | Description |
|------|--------|-------------|
| `path` | points[] | Freehand polyline |
| `line` | start, end | Straight line |
| `arrow` | start, end, head_size | Line with arrow head |
| `rect` | bounds, fill | Rectangle (x, y, w, h) |
| `ellipse` | bounds, fill | Ellipse in bounding box |
| `text` | position, text, font_size, background | Text annotation |

### Path Simplification

To reduce file size, paths are simplified using the Ramer-Douglas-Peucker algorithm:

```python
def simplify_path(points: List[Tuple[float, float]], epsilon: float = 1.0) -> List[Tuple[float, float]]:
    """Reduce points while preserving shape."""
    if len(points) < 3:
        return points

    # Find point with max distance from line between first and last
    start, end = points[0], points[-1]
    max_dist = 0
    max_idx = 0

    for i in range(1, len(points) - 1):
        dist = perpendicular_distance(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        # Recursively simplify
        left = simplify_path(points[:max_idx + 1], epsilon)
        right = simplify_path(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [start, end]
```

---

## 3. File Structure for Drawovers

### Directory Layout

```
storage/.actionlibrary/
├── database.db              # Main animation database
├── notes.db                 # Review notes database
└── drawovers/               # Drawover files
    └── {animation_uuid}/
        └── {version}/
            ├── f0125.json       # Frame 125 vector data
            ├── f0125.png        # Frame 125 PNG cache
            ├── f0200.json
            ├── f0200.png
            └── manifest.json    # Index of all drawovers for this version
```

### Manifest File

```json
{
    "version": "1.0",
    "animation_uuid": "abc123-...",
    "version_label": "v003",
    "frames": {
        "125": {
            "json": "f0125.json",
            "png": "f0125.png",
            "modified_at": "2024-01-15T11:45:00Z",
            "stroke_count": 5
        },
        "200": {
            "json": "f0200.json",
            "png": "f0200.png",
            "modified_at": "2024-01-15T11:50:00Z",
            "stroke_count": 3
        }
    },
    "total_frames": 2,
    "total_strokes": 8
}
```

### File Naming Convention

- Vector data: `f{frame:04d}.json` (e.g., `f0125.json`)
- PNG cache: `f{frame:04d}.png`
- Manifest: `manifest.json`

### Storage Class

```python
class DrawoverStorage:
    """Manages drawover file storage."""

    def __init__(self, base_path: Path):
        self._base = base_path / 'drawovers'

    def get_drawover_path(self, uuid: str, version: str, frame: int) -> Path:
        """Get path for a frame's drawover JSON."""
        return self._base / uuid / version / f'f{frame:04d}.json'

    def get_png_cache_path(self, uuid: str, version: str, frame: int) -> Path:
        """Get path for a frame's PNG cache."""
        return self._base / uuid / version / f'f{frame:04d}.png'

    def save_drawover(self, uuid: str, version: str, frame: int, data: dict) -> bool:
        """Save drawover JSON and invalidate PNG cache."""
        path = self.get_drawover_path(uuid, version, frame)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

        # Invalidate PNG cache
        png_path = self.get_png_cache_path(uuid, version, frame)
        if png_path.exists():
            png_path.unlink()

        self._update_manifest(uuid, version)
        return True

    def load_drawover(self, uuid: str, version: str, frame: int) -> Optional[dict]:
        """Load drawover JSON for a frame."""
        path = self.get_drawover_path(uuid, version, frame)
        if not path.exists():
            return None

        with open(path, 'r') as f:
            return json.load(f)

    def get_or_render_png(self, uuid: str, version: str, frame: int,
                          size: Tuple[int, int]) -> Optional[Path]:
        """Get PNG cache, rendering if needed."""
        png_path = self.get_png_cache_path(uuid, version, frame)
        json_path = self.get_drawover_path(uuid, version, frame)

        if not json_path.exists():
            return None

        # Check if cache is valid
        if png_path.exists():
            if png_path.stat().st_mtime >= json_path.stat().st_mtime:
                return png_path

        # Render PNG from JSON
        data = self.load_drawover(uuid, version, frame)
        if data:
            self._render_to_png(data, png_path, size)
            return png_path

        return None

    def list_frames_with_drawovers(self, uuid: str, version: str) -> List[int]:
        """Get list of frames that have drawovers."""
        manifest = self._load_manifest(uuid, version)
        if manifest:
            return [int(f) for f in manifest.get('frames', {}).keys()]
        return []

    def delete_drawover(self, uuid: str, version: str, frame: int) -> bool:
        """Delete a frame's drawover (hard delete for files)."""
        json_path = self.get_drawover_path(uuid, version, frame)
        png_path = self.get_png_cache_path(uuid, version, frame)

        if json_path.exists():
            json_path.unlink()
        if png_path.exists():
            png_path.unlink()

        self._update_manifest(uuid, version)
        return True
```

---

## 4. Database Schema Updates

### New Tables in notes.db

```sql
-- Drawover metadata (file references only)
CREATE TABLE drawovers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animation_uuid TEXT NOT NULL,
    version_label TEXT NOT NULL,
    frame INTEGER NOT NULL,
    file_path TEXT NOT NULL,           -- Relative path to JSON file
    stroke_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    last_modified_by TEXT,

    UNIQUE(animation_uuid, version_label, frame)
);

CREATE INDEX idx_drawovers_animation ON drawovers(animation_uuid, version_label);
CREATE INDEX idx_drawovers_frame ON drawovers(animation_uuid, version_label, frame);

-- Individual stroke metadata for fine-grained permissions
CREATE TABLE drawover_strokes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drawover_id INTEGER NOT NULL,
    stroke_id TEXT NOT NULL,           -- UUID within the JSON
    stroke_type TEXT NOT NULL,         -- path, arrow, text, etc.
    author TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0,
    deleted_by TEXT,
    deleted_at TIMESTAMP,

    FOREIGN KEY (drawover_id) REFERENCES drawovers(id) ON DELETE CASCADE
);

CREATE INDEX idx_strokes_drawover ON drawover_strokes(drawover_id);
CREATE INDEX idx_strokes_author ON drawover_strokes(author);

-- Drawover audit log
CREATE TABLE drawover_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drawover_id INTEGER,
    stroke_id TEXT,
    action TEXT NOT NULL,              -- created, modified, deleted, restored
    actor TEXT NOT NULL,
    actor_role TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT,                      -- JSON with change info

    FOREIGN KEY (drawover_id) REFERENCES drawovers(id) ON DELETE SET NULL
);

CREATE INDEX idx_drawover_audit_timestamp ON drawover_audit_log(timestamp);
```

### Schema Migration

```python
def _migrate_v2_to_v3(self):
    """Add drawover tables."""
    cursor = self._connection.cursor()

    # Create drawovers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drawovers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animation_uuid TEXT NOT NULL,
            version_label TEXT NOT NULL,
            frame INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            stroke_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            last_modified_by TEXT,
            UNIQUE(animation_uuid, version_label, frame)
        )
    ''')

    # Create strokes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drawover_strokes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drawover_id INTEGER NOT NULL,
            stroke_id TEXT NOT NULL,
            stroke_type TEXT NOT NULL,
            author TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted INTEGER DEFAULT 0,
            deleted_by TEXT,
            deleted_at TIMESTAMP,
            FOREIGN KEY (drawover_id) REFERENCES drawovers(id) ON DELETE CASCADE
        )
    ''')

    # Create audit log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drawover_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drawover_id INTEGER,
            stroke_id TEXT,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            actor_role TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            FOREIGN KEY (drawover_id) REFERENCES drawovers(id) ON DELETE SET NULL
        )
    ''')

    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_drawovers_animation ON drawovers(animation_uuid, version_label)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_drawovers_frame ON drawovers(animation_uuid, version_label, frame)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_strokes_drawover ON drawover_strokes(drawover_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_strokes_author ON drawover_strokes(author)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_drawover_audit_timestamp ON drawover_audit_log(timestamp)')

    # Update schema version
    cursor.execute('UPDATE schema_version SET version = 3')
    self._connection.commit()
```

---

## 5. Permission System

### Extended Permissions for Drawovers

```python
class DrawoverPermissions:
    """Permission checking for drawover operations."""

    @staticmethod
    def can_draw(is_studio_mode: bool, user_role: str) -> bool:
        """Everyone can add drawings."""
        return True

    @staticmethod
    def can_edit_stroke(
        is_studio_mode: bool,
        user_role: str,
        stroke_author: str,
        current_user: str
    ) -> bool:
        """
        Check if user can edit a stroke.

        Solo mode: Always allowed
        Studio mode: Users can only edit their own strokes
        """
        if not is_studio_mode:
            return True
        return stroke_author == current_user

    @staticmethod
    def can_delete_stroke(
        is_studio_mode: bool,
        user_role: str,
        stroke_author: str,
        current_user: str
    ) -> bool:
        """
        Check if user can delete a stroke.

        Solo mode: Always allowed
        Studio mode:
            - Artists: Cannot delete any strokes
            - Leads/Directors: Can delete their own strokes only
            - Supervisors/Admins: Can delete any stroke
        """
        if not is_studio_mode:
            return True

        level = NotePermissions.get_role_level(user_role)

        if level >= RoleLevel.SUPERVISOR:
            return True
        if level >= RoleLevel.LEAD:
            return stroke_author == current_user
        return False

    @staticmethod
    def can_clear_frame(is_studio_mode: bool, user_role: str) -> bool:
        """
        Check if user can clear all strokes on a frame.

        Solo mode: Always allowed
        Studio mode: Only Supervisors and Admins
        """
        if not is_studio_mode:
            return True
        return NotePermissions.get_role_level(user_role) >= RoleLevel.SUPERVISOR

    @staticmethod
    def can_restore_stroke(is_studio_mode: bool, user_role: str) -> bool:
        """
        Check if user can restore deleted strokes.

        Solo mode: Always allowed
        Studio mode: Only Supervisors and Admins
        """
        if not is_studio_mode:
            return True
        return NotePermissions.get_role_level(user_role) >= RoleLevel.SUPERVISOR
```

### Permission Matrix

| Permission | Artist | Lead/Director | Supervisor | Admin |
|------------|--------|---------------|------------|-------|
| Draw (add strokes) | ✓ | ✓ | ✓ | ✓ |
| Edit own strokes | ✓ | ✓ | ✓ | ✓ |
| Edit others' strokes | — | — | — | — |
| Delete own strokes | — | ✓ | ✓ | ✓ |
| Delete any stroke | — | — | ✓ | ✓ |
| Clear entire frame | — | — | ✓ | ✓ |
| Restore deleted strokes | — | — | ✓ | ✓ |
| View deleted strokes | — | ✓ | ✓ | ✓ |

---

## 6. UI Flow for Draw/Edit/Delete

### Drawing Mode Toggle

```
┌─────────────────────────────────────────────────────────────────────┐
│ Animation Lineage                                              [X]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │                                                                │   │
│ │                    Video Preview                               │   │
│ │                   + Drawover Overlay                           │   │
│ │                                                                │   │
│ └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ [▶] [🔁]  ══════════●══════════════════════  f125 / 300        │ │
│ │           [●][●]    [●]        [●]   ← Timeline markers        │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ ┌─ Drawing Tools ─────────────────────────────────────────────────┐ │
│ │ [✏️ Pen] [➡️ Arrow] [▢ Rect] [⭕ Circle] [T Text] [🧹 Eraser]  │ │
│ │                                                                  │ │
│ │ Color: [██████] ▼   Size: [━━━●━━━] 3px   [↩️ Undo] [↪️ Redo]  │ │
│ │                                                                  │ │
│ │ [✓ Done Drawing]                           [🗑️ Clear Frame]    │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Tool Activation Flow

```
1. User pauses video at frame 125
2. User clicks "Draw" button or presses 'D' key
3. Drawing toolbar appears below timeline
4. Video controls disabled (prevent accidental navigation)
5. Overlay canvas becomes active (accepts mouse input)
6. User draws with selected tool
7. Each stroke auto-saved on mouse release
8. User clicks "Done Drawing" or presses Escape
9. Toolbar hides, video controls re-enabled
10. Drawover thumbnail appears on timeline marker
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| D | Toggle draw mode |
| Escape | Exit draw mode |
| P | Select pen tool |
| A | Select arrow tool |
| R | Select rect tool |
| C | Select circle tool |
| T | Select text tool |
| E | Select eraser |
| [ | Decrease brush size |
| ] | Increase brush size |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Delete | Delete selected stroke |
| Ctrl+Shift+Delete | Clear frame (with confirmation) |

### Drawing Toolbar Widget

```python
class DrawingToolbar(QWidget):
    """Toolbar for drawing tools and settings."""

    tool_changed = pyqtSignal(DrawoverCanvas.Tool)
    color_changed = pyqtSignal(QColor)
    size_changed = pyqtSignal(int)
    done_clicked = pyqtSignal()
    clear_clicked = pyqtSignal()
    undo_clicked = pyqtSignal()
    redo_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Tool buttons row
        tools_row = QHBoxLayout()

        self._tool_group = QButtonGroup()
        tools = [
            ('Pen', DrawoverCanvas.Tool.PEN, 'pen.svg'),
            ('Arrow', DrawoverCanvas.Tool.ARROW, 'arrow.svg'),
            ('Rect', DrawoverCanvas.Tool.RECT, 'rect.svg'),
            ('Circle', DrawoverCanvas.Tool.CIRCLE, 'circle.svg'),
            ('Text', DrawoverCanvas.Tool.TEXT, 'text.svg'),
            ('Eraser', DrawoverCanvas.Tool.ERASER, 'eraser.svg'),
        ]

        for name, tool, icon in tools:
            btn = QToolButton()
            btn.setIcon(IconLoader.get_icon(icon))
            btn.setToolTip(name)
            btn.setCheckable(True)
            btn.setFixedSize(32, 32)
            self._tool_group.addButton(btn, tool.value)
            tools_row.addWidget(btn)

        tools_row.addStretch()
        layout.addLayout(tools_row)

        # Settings row
        settings_row = QHBoxLayout()

        # Color picker
        settings_row.addWidget(QLabel("Color:"))
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(28, 28)
        self._color_btn.clicked.connect(self._pick_color)
        self._set_color_preview(QColor('#FF5722'))
        settings_row.addWidget(self._color_btn)

        # Quick colors
        quick_colors = ['#FF5722', '#4CAF50', '#2196F3', '#FFEB3B', '#FFFFFF']
        for color in quick_colors:
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(f"background-color: {color}; border: 1px solid #555;")
            btn.clicked.connect(lambda c=color: self._set_color(QColor(c)))
            settings_row.addWidget(btn)

        settings_row.addSpacing(20)

        # Brush size
        settings_row.addWidget(QLabel("Size:"))
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(1, 20)
        self._size_slider.setValue(3)
        self._size_slider.setFixedWidth(100)
        self._size_slider.valueChanged.connect(self.size_changed.emit)
        settings_row.addWidget(self._size_slider)

        self._size_label = QLabel("3px")
        self._size_slider.valueChanged.connect(lambda v: self._size_label.setText(f"{v}px"))
        settings_row.addWidget(self._size_label)

        settings_row.addStretch()

        # Undo/Redo
        undo_btn = QPushButton("Undo")
        undo_btn.clicked.connect(self.undo_clicked.emit)
        settings_row.addWidget(undo_btn)

        redo_btn = QPushButton("Redo")
        redo_btn.clicked.connect(self.redo_clicked.emit)
        settings_row.addWidget(redo_btn)

        layout.addLayout(settings_row)

        # Action row
        action_row = QHBoxLayout()

        done_btn = QPushButton("Done Drawing")
        done_btn.setStyleSheet("background-color: #3a5a3a; color: #8BC34A;")
        done_btn.clicked.connect(self.done_clicked.emit)
        action_row.addWidget(done_btn)

        action_row.addStretch()

        clear_btn = QPushButton("Clear Frame")
        clear_btn.setStyleSheet("color: #ff6b6b;")
        clear_btn.clicked.connect(self.clear_clicked.emit)
        action_row.addWidget(clear_btn)

        layout.addLayout(action_row)
```

### Stroke Selection & Editing

```python
class StrokeSelector:
    """Handles stroke selection for editing/deletion."""

    def __init__(self, canvas: DrawoverCanvas):
        self._canvas = canvas
        self._selected_items: List[QGraphicsItem] = []
        self._selection_rect = None

    def on_click(self, pos: QPointF):
        """Select stroke at position."""
        item = self._canvas.scene().itemAt(pos, QTransform())

        if item:
            self._clear_selection()
            self._select_item(item)
        else:
            self._clear_selection()

    def _select_item(self, item: QGraphicsItem):
        """Highlight selected item."""
        self._selected_items = [item]

        # Add selection highlight
        bounds = item.boundingRect()
        self._selection_rect = QGraphicsRectItem(bounds)
        self._selection_rect.setPen(QPen(QColor('#3A8FB7'), 1, Qt.PenStyle.DashLine))
        self._selection_rect.setParentItem(item)

    def delete_selected(self) -> List[str]:
        """Delete selected strokes, return their IDs."""
        deleted_ids = []
        for item in self._selected_items:
            stroke_id = item.data(0)  # Stored on item
            if stroke_id:
                deleted_ids.append(stroke_id)
            self._canvas.scene().removeItem(item)

        self._clear_selection()
        return deleted_ids
```

---

## 7. Compare Mode Overlay Behavior

### Side-by-Side with Drawovers

```
┌─────────────────────────────────────────────────────────────────────┐
│ Compare: v002 vs v003                                          [X]  │
├─────────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────┐   ┌───────────────────────────┐      │
│ │                           │   │                           │      │
│ │  v002 + Drawovers         │   │  v003 + Drawovers         │      │
│ │  (read-only)              │   │  (read-only)              │      │
│ │                           │   │                           │      │
│ └───────────────────────────┘   └───────────────────────────┘      │
│                                                                      │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ [▶]  ════════════●══════════════════════════  f125 / 300       │ │
│ │      [●]         [●]              [●]                          │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ ☑ Show v002 Drawovers    ☑ Show v003 Drawovers                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Compare Mode Rules

1. **Drawovers are read-only in compare mode**
   - No drawing allowed
   - Only viewing existing annotations

2. **Toggle visibility per version**
   - Checkbox to show/hide each version's drawovers
   - Useful for seeing original vs annotated

3. **Synchronized frame**
   - Both videos on same frame
   - Drawovers load for current frame on both sides

4. **Timeline shows combined markers**
   - Markers from both versions visible
   - Different colors per version

### Implementation

```python
class CompareDrawoverManager:
    """Manages drawovers in compare mode."""

    def __init__(self, left_canvas: DrawoverCanvas, right_canvas: DrawoverCanvas):
        self._left = left_canvas
        self._right = right_canvas
        self._left_visible = True
        self._right_visible = True

    def set_frame(self, frame: int, left_data: dict, right_data: dict):
        """Load drawovers for both sides."""
        self._left.set_read_only(True)
        self._right.set_read_only(True)

        if self._left_visible and left_data:
            self._left.import_from_json(left_data, frame)
        else:
            self._left.clear()

        if self._right_visible and right_data:
            self._right.import_from_json(right_data, frame)
        else:
            self._right.clear()

    def toggle_left_visibility(self, visible: bool):
        self._left_visible = visible
        if not visible:
            self._left.clear()

    def toggle_right_visibility(self, visible: bool):
        self._right_visible = visible
        if not visible:
            self._right.clear()
```

---

## 8. Performance Considerations

### Lazy Loading

```python
class DrawoverCache:
    """LRU cache for drawover data."""

    def __init__(self, max_size: int = 50):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size

    def get(self, uuid: str, version: str, frame: int) -> Optional[dict]:
        key = f"{uuid}:{version}:{frame}"
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, uuid: str, version: str, frame: int, data: dict):
        key = f"{uuid}:{version}:{frame}"
        self._cache[key] = data
        self._cache.move_to_end(key)

        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate(self, uuid: str, version: str, frame: int):
        key = f"{uuid}:{version}:{frame}"
        self._cache.pop(key, None)
```

### Preloading Strategy

```python
class DrawoverPreloader(QObject):
    """Background preloader for nearby frames."""

    preload_complete = pyqtSignal(int, dict)  # frame, data

    def __init__(self, storage: DrawoverStorage, cache: DrawoverCache):
        super().__init__()
        self._storage = storage
        self._cache = cache
        self._thread_pool = QThreadPool.globalInstance()

    def preload_range(self, uuid: str, version: str, center_frame: int, radius: int = 5):
        """Preload frames around center."""
        for offset in range(-radius, radius + 1):
            frame = center_frame + offset
            if frame < 0:
                continue

            if self._cache.get(uuid, version, frame) is None:
                task = PreloadTask(self._storage, uuid, version, frame)
                task.signals.loaded.connect(self._on_loaded)
                self._thread_pool.start(task)

    def _on_loaded(self, frame: int, data: dict):
        self._cache.put(self._uuid, self._version, frame, data)
        self.preload_complete.emit(frame, data)
```

### Stroke Batching

```python
class StrokeBatcher:
    """Batches multiple stroke updates into single save."""

    def __init__(self, storage: DrawoverStorage, delay_ms: int = 500):
        self._storage = storage
        self._pending: Dict[str, dict] = {}
        self._timer = QTimer()
        self._timer.timeout.connect(self._flush)
        self._delay = delay_ms

    def queue_save(self, uuid: str, version: str, frame: int, data: dict):
        """Queue data for batched save."""
        key = f"{uuid}:{version}:{frame}"
        self._pending[key] = (uuid, version, frame, data)

        self._timer.stop()
        self._timer.start(self._delay)

    def _flush(self):
        """Save all pending data."""
        self._timer.stop()

        for uuid, version, frame, data in self._pending.values():
            self._storage.save_drawover(uuid, version, frame, data)

        self._pending.clear()

    def flush_now(self):
        """Force immediate save (e.g., on dialog close)."""
        self._flush()
```

### Rendering Optimization

```python
class OptimizedCanvas(DrawoverCanvas):
    """Canvas with rendering optimizations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._viewport_rect = QRectF()
        self._visible_items: List[QGraphicsItem] = []

    def update_visible_items(self):
        """Only render items in viewport."""
        self._viewport_rect = self.mapToScene(self.viewport().rect()).boundingRect()

        for item in self._scene.items():
            visible = item.boundingRect().intersects(self._viewport_rect)
            item.setVisible(visible)

    def paintEvent(self, event):
        """Optimized paint with culling."""
        self.update_visible_items()
        super().paintEvent(event)
```

---

## 9. Studio-Safe Workflows

### Soft Delete for Strokes

```python
def soft_delete_stroke(self, stroke_id: str, deleted_by: str, actor_role: str) -> bool:
    """Soft delete a stroke in Studio Mode."""
    cursor = self._connection.cursor()

    # Update database
    cursor.execute('''
        UPDATE drawover_strokes
        SET deleted = 1, deleted_by = ?, deleted_at = CURRENT_TIMESTAMP
        WHERE stroke_id = ?
    ''', (deleted_by, stroke_id))

    # Log action
    self._log_drawover_action(
        stroke_id=stroke_id,
        action='deleted',
        actor=deleted_by,
        actor_role=actor_role
    )

    self._connection.commit()

    # Update JSON file - move stroke to deleted_strokes array
    # (handled by DrawoverStorage)

    return cursor.rowcount > 0
```

### Restore Workflow

```python
def restore_stroke(self, stroke_id: str, restored_by: str, actor_role: str) -> bool:
    """Restore a soft-deleted stroke."""
    if not DrawoverPermissions.can_restore_stroke(self.is_studio_mode(), actor_role):
        return False

    cursor = self._connection.cursor()

    cursor.execute('''
        UPDATE drawover_strokes
        SET deleted = 0, deleted_by = NULL, deleted_at = NULL
        WHERE stroke_id = ?
    ''', (stroke_id,))

    self._log_drawover_action(
        stroke_id=stroke_id,
        action='restored',
        actor=restored_by,
        actor_role=actor_role
    )

    self._connection.commit()
    return cursor.rowcount > 0
```

### Audit Trail Queries

```python
def get_drawover_history(self, animation_uuid: str, version: str) -> List[Dict]:
    """Get full audit history for a version's drawovers."""
    cursor = self._connection.cursor()

    cursor.execute('''
        SELECT
            dal.action,
            dal.actor,
            dal.actor_role,
            dal.timestamp,
            dal.details,
            d.frame
        FROM drawover_audit_log dal
        LEFT JOIN drawovers d ON dal.drawover_id = d.id
        WHERE d.animation_uuid = ? AND d.version_label = ?
        ORDER BY dal.timestamp DESC
    ''', (animation_uuid, version))

    return [dict(row) for row in cursor.fetchall()]
```

### Version Freeze Protection

```python
class DrawoverGuard:
    """Prevents edits to finalized versions."""

    def __init__(self, db_service):
        self._db = db_service

    def can_edit_drawover(self, animation_uuid: str) -> bool:
        """Check if animation's drawovers can be edited."""
        animation = self._db.get_animation(animation_uuid)
        if not animation:
            return False

        status = animation.get('status', '')

        # Finalized versions are read-only
        if status == 'final':
            return False

        return True

    def validate_edit(self, animation_uuid: str) -> None:
        """Raise exception if edit not allowed."""
        if not self.can_edit_drawover(animation_uuid):
            raise PermissionError("Cannot edit drawovers on finalized versions")
```

---

## 10. Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `widgets/drawover_canvas.py` | Main drawing canvas widget |
| `widgets/drawing_toolbar.py` | Tool selection and settings |
| `widgets/drawing_tools.py` | Individual tool implementations |
| `services/drawover_storage.py` | File storage management |
| `services/drawover_database.py` | Database operations for drawovers |
| `services/drawover_permissions.py` | Permission checking (or extend permissions.py) |

### Modified Files

| File | Changes |
|------|---------|
| `widgets/dialogs/version_history_dialog.py` | Add drawover overlay to video preview |
| `widgets/video_preview_widget.py` | Support overlay integration |
| `services/notes_database.py` | Add schema v3 migration |
| `services/permissions.py` | Add drawover permissions |

---

## 11. Implementation Phases

### Phase 2.1: Core Drawing (Week 1-2)
- [ ] DrawoverCanvas with basic pen tool
- [ ] DrawoverStorage for file management
- [ ] Vector JSON format implementation
- [ ] Basic save/load functionality

### Phase 2.2: Tools & UI (Week 2-3)
- [ ] Full tool suite (arrow, rect, circle, text, eraser)
- [ ] DrawingToolbar widget
- [ ] Color picker and brush size
- [ ] Undo/redo stack

### Phase 2.3: Integration (Week 3-4)
- [ ] Overlay integration in VersionHistoryDialog
- [ ] Timeline markers for frames with drawovers
- [ ] Database schema v3 migration
- [ ] Permission system integration

### Phase 2.4: Studio Features (Week 4-5)
- [ ] Soft delete for strokes
- [ ] Restore workflow
- [ ] Audit trail
- [ ] Compare mode support

### Phase 2.5: Polish (Week 5-6)
- [ ] Performance optimization (caching, preloading)
- [ ] Keyboard shortcuts
- [ ] PNG cache generation
- [ ] Testing and bug fixes

---

## 12. Testing Checklist

### Core Functionality
- [ ] Draw with all tools (pen, arrow, rect, circle, text, eraser)
- [ ] Save drawover to JSON
- [ ] Load drawover from JSON
- [ ] Switch frames preserves drawings
- [ ] Undo/redo works correctly
- [ ] PNG cache generates correctly

### Permissions (Studio Mode)
- [ ] Artists can draw but not delete others' strokes
- [ ] Leads can delete their own strokes
- [ ] Supervisors can delete any stroke
- [ ] Supervisors can restore deleted strokes
- [ ] Finalized versions are read-only

### Performance
- [ ] Smooth drawing at 60fps
- [ ] Fast frame switching (<100ms)
- [ ] Reasonable memory usage with many drawovers
- [ ] Preloading works for nearby frames

### Edge Cases
- [ ] Empty drawover (no strokes)
- [ ] Very long strokes (thousands of points)
- [ ] Many strokes on one frame (100+)
- [ ] Concurrent access from multiple users
- [ ] Corrupt JSON file handling
- [ ] Missing PNG cache regeneration

---

## 13. Future Enhancements (Out of Scope)

- Video annotation playback (animated drawings)
- Voice notes attached to frames
- Real-time collaborative drawing
- Annotation templates/stamps
- Export to PDF/video with annotations burned in
- Integration with external review tools (Shotgrid, ftrack)
- Mobile/tablet touch drawing support
