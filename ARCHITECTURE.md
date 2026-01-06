# Animation Library v2 - Architecture Overview

## Introduction

Animation Library v2 is a professional desktop application for managing Blender animation assets. Built with PyQt6, it provides a modern, theme-able interface with advanced features like favorites, tagging, filtering, and seamless Blender integration.

---

## Directory Structure

```
animation_library_v2/
├── animation_library/          # Main application package
│   ├── config.py              # Centralized configuration
│   ├── events/                # Event bus for component communication
│   ├── icons/                 # SVG icon assets
│   ├── models/                # Data models (MVC pattern)
│   ├── services/              # Business logic (database, backup, thumbnails)
│   ├── themes/                # Theme system and styling
│   ├── utils/                 # Utility functions
│   ├── views/                 # View components (MVC pattern)
│   └── widgets/               # UI widgets and dialogs
├── blender_plugin/            # Blender addon for integration
├── data/                      # User data (databases, cache)
└── storage/                   # Animation library storage
```

---

## Architectural Patterns

### 1. Model-View-Controller (MVC)

**Models** (`models/`):
- `AnimationListModel` - Qt model for animation data
- `AnimationFilterProxyModel` - Filtering and sorting logic
- Uses Qt's Model/View architecture for performance

**Views** (`views/`):
- `AnimationView` - QListView with grid/list modes
- `AnimationCardDelegate` - Custom rendering for animation cards
- Delegates handle all drawing logic

**Controllers** (`widgets/`):
- `MainWindow` - Main application controller
- Widgets handle user interactions and update models

### 2. Singleton Pattern

Global service access via getter functions:
```python
from animation_library.services.database_service import get_database_service
from animation_library.themes.theme_manager import get_theme_manager
from animation_library.events.event_bus import get_event_bus

db = get_database_service()      # Database operations
theme = get_theme_manager()       # Theme management
bus = get_event_bus()            # Event communication
```

**Why Singletons?**
- Single source of truth for application state
- Easy access from any component
- Lazy initialization
- Thread-safe (for services that need it)

### 3. Repository Pattern

`DatabaseService` abstracts all database operations:
```python
# Clean API for data access
animations = db_service.get_all_animations()
favorites = db_service.get_favorite_animations()
db_service.toggle_favorite(uuid)
db_service.update_last_viewed(uuid)
```

Benefits:
- Single point of database access
- Easy to test (can mock the service)
- Database implementation can change without affecting UI

### 4. Observer Pattern (Event Bus)

Component communication via Qt signals:
```python
# Publish event
event_bus.set_folder("Favorites")
event_bus.view_mode_changed.emit("grid")

# Subscribe to event
event_bus.folder_selected.connect(self._on_folder_selected)
event_bus.view_mode_changed.connect(self.set_view_mode)
```

**Benefits**:
- Loose coupling between components
- Easy to add new listeners
- Testable (can verify signals emitted)

### 5. Strategy Pattern (Themes)

Theme base class with concrete implementations:
```python
class Theme(ABC):
    @abstractmethod
    def get_palette(self) -> ColorPalette:
        pass

    @abstractmethod
    def get_stylesheet(self) -> str:
        pass

class DarkTheme(Theme):
    # Dark color scheme implementation

class LightTheme(Theme):
    # Light color scheme implementation
```

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        MainWindow                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              HeaderToolbar                           │  │
│  │  [Search] [Filters] [Sort] [View Mode] [Settings]   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         BulkEditToolbar (conditional)                │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌────────┬──────────────────────┬─────────────────────┐  │
│  │Folder  │   AnimationView      │  MetadataPanel      │  │
│  │Tree    │   (Grid/List)        │  ┌───────────────┐  │  │
│  │        │  ┌────────────────┐  │  │ Video Preview │  │  │
│  │Virtual:│  │AnimationCard   │  │  └───────────────┘  │  │
│  │ All    │  │Delegate        │  │  Name: Walk Cycle   │  │
│  │ Recent │  │┌─────┬─────┐   │  │  Tags: [locomotion] │  │
│  │ Favs   │  ││Card │Card │   │  │  Duration: 2.5s     │  │
│  │        │  │└─────┴─────┘   │  │  FPS: 30            │  │
│  │User:   │  └────────────────┘  │  Rig: Humanoid      │  │
│  │ Combat │                      │  [Edit] [Apply]     │  │
│  │ Idle   │                      │                     │  │
│  └────────┴──────────────────────┴─────────────────────┘  │
│  Status Bar: "Loaded 47 animations"                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Signal Flow

### Example: Folder Selection Flow

```
User clicks "Favorites" folder
         ↓
FolderTree._on_selection_changed()
         ↓
FolderTree.folder_selected.emit(folder_id, "Favorites", recursive)
         ↓
MainWindow._on_folder_selected()
         ↓
AnimationFilterProxyModel.set_favorites_only(True)
         ↓
ProxyModel.invalidateFilter()
         ↓
AnimationView refreshes (automatic via Qt)
         ↓
Only favorited animations visible
```

### Example: Theme Change Flow

```
User selects "Light Theme" in settings
         ↓
ThemeTab._on_theme_selected()
         ↓
ThemeManager.set_theme("Light Theme")
         ↓
ThemeManager.theme_changed.emit("Light Theme")
         ↓
┌────────────────────────────────────────┐
│ All widgets listening to this signal:  │
│ - HeaderToolbar (recolor icons)        │
│ - MainWindow (apply new stylesheet)    │
│ - AnimationView (repaint with new colors)│
└────────────────────────────────────────┘
         ↓
UI updates to light theme
```

---

## Theme System

### Color Palette Structure

All colors defined in `ColorPalette` dataclass:
```python
@dataclass
class ColorPalette:
    # Backgrounds
    background: str              # Main window
    background_secondary: str    # Panels

    # Text
    text_primary: str
    text_secondary: str
    text_disabled: str

    # Interactive
    accent: str                  # Primary color
    accent_hover: str
    accent_pressed: str

    # Cards
    card_background: str
    card_border: str
    card_selected: str

    # Special
    gold_primary: str            # Favorites star
    header_gradient_top: str     # Orange header
    header_gradient_bottom: str
```

### QSS Generation

Themes dynamically generate Qt StyleSheets:
```python
def get_stylesheet(self) -> str:
    palette = self.get_palette()
    return f"""
        QMainWindow {{
            background-color: {palette.background};
            color: {palette.text_primary};
        }}

        QPushButton {{
            background-color: {palette.accent};
            color: #FFFFFF;
        }}

        QPushButton:hover {{
            background-color: {palette.accent_hover};
        }}

        /* ... hundreds more lines ... */
    """
```

### Property-Based Styling

Widgets can set custom properties for special styling:
```python
# In widget code
self.setProperty("header", "true")

# In QSS
HeaderToolbar[header="true"] {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #FF8C00,
        stop:1 #FF6600
    );
}
```

---

## Data Flow

### Animation Loading Flow

```
Application Start
        ↓
MainWindow.__init__()
        ↓
DatabaseService.initialize()
        ↓
DatabaseService.get_all_animations()
        ↓
AnimationListModel.set_animations(animations)
        ↓
AnimationFilterProxyModel.setSourceModel(model)
        ↓
AnimationView.setModel(proxy_model)
        ↓
AnimationCardDelegate.paint() for each visible card
        ↓
ThumbnailLoader.load_thumbnail() (async)
        ↓
Cards display with thumbnails
```

### Thumbnail Loading (Async)

```
AnimationCardDelegate.paint()
        ↓
ThumbnailLoader.load_thumbnail(uuid, path, gradient)
        ↓
Check cache → Found? Return immediately
        ↓ Not found
Queue thumbnail loading task
        ↓
QThreadPool executes in background
        ↓
Load PNG + composite with gradient
        ↓
ThumbnailLoader.thumbnail_loaded.emit(uuid, pixmap)
        ↓
AnimationCardDelegate._on_thumbnail_loaded()
        ↓
AnimationView.viewport().update()
        ↓
Card repaints with loaded thumbnail
```

### Favorite Toggle Flow

```
User clicks star on animation card
        ↓
AnimationCardDelegate.editorEvent()
        ↓
DatabaseService.toggle_favorite(uuid)
        ↓
Update database (is_favorite = 1)
        ↓
AnimationListModel.refresh_animation(uuid)
        ↓
Re-fetch animation data from DB
        ↓
Model.dataChanged.emit(index)
        ↓
View repaints with filled star
```

---

## Performance Optimizations

### 1. Virtual Scrolling
- Only visible items rendered
- Uniform item sizes for fast layout
- Reduces memory for large libraries (1000+ animations)

### 2. Async Thumbnail Loading
- Background thread pool (QThreadPool)
- Non-blocking UI
- Progressive loading as user scrolls

### 3. Pixmap Cache
- 512MB LRU cache for thumbnails
- Prevents redundant file I/O
- Key: `{uuid}_{gradient_hash}`

### 4. Debounced Operations
- Theme preview: 100ms debounce
- Hover detection: 300ms delay
- Prevents excessive repaints

### 5. Database Indexing
```sql
CREATE INDEX idx_animations_uuid ON animations(uuid);
CREATE INDEX idx_animations_folder ON animations(folder_id);
CREATE INDEX idx_animations_rig_type ON animations(rig_type);
CREATE INDEX idx_animations_favorite ON animations(is_favorite);
CREATE INDEX idx_animations_last_viewed ON animations(last_viewed_date);
```

---

## Configuration System

### Centralized Config (`config.py`)

All constants in one place:
```python
class Config:
    # App metadata
    APP_NAME = "Animation Library v2"
    APP_VERSION = "2.0.0"

    # Performance
    PIXMAP_CACHE_SIZE_KB = 512 * 1024  # 512 MB
    THUMBNAIL_THREAD_COUNT = 4
    BATCH_SIZE = 100

    # UI defaults
    DEFAULT_CARD_SIZE = 160
    MIN_CARD_SIZE = 80
    MAX_CARD_SIZE = 300
    DEFAULT_VIEW_MODE = "grid"

    # Feature flags
    ENABLE_HOVER_VIDEO = False
    ENABLE_DRAG_DROP = True
    ENABLE_MULTI_SELECT = True
```

**Benefits**:
- Easy to customize without code changes
- Single source of truth
- Feature flags for experimental features
- Performance tuning in one place

---

## Database Schema

### Tables

**animations** - Main animation data
```sql
CREATE TABLE animations (
    id INTEGER PRIMARY KEY,
    uuid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    folder_id INTEGER,

    -- Rig info
    rig_type TEXT,
    armature_name TEXT,
    bone_count INTEGER,

    -- Timing
    frame_start INTEGER,
    frame_end INTEGER,
    frame_count INTEGER,
    duration_seconds REAL,
    fps INTEGER,

    -- Files
    blend_file_path TEXT,
    json_file_path TEXT,
    preview_path TEXT,
    thumbnail_path TEXT,

    -- Metadata
    description TEXT,
    tags TEXT,  -- JSON array
    author TEXT,

    -- Custom thumbnail
    use_custom_thumbnail_gradient INTEGER DEFAULT 0,
    thumbnail_gradient_top TEXT,
    thumbnail_gradient_bottom TEXT,

    -- User features (v2)
    is_favorite INTEGER DEFAULT 0,
    last_viewed_date TIMESTAMP,
    custom_order INTEGER,
    is_locked INTEGER DEFAULT 0,

    -- Timestamps
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE
);
```

**folders** - User-created folder hierarchy with unlimited nesting
```sql
CREATE TABLE folders (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id INTEGER,         -- NULL for root folder, otherwise parent folder ID
    path TEXT,                 -- Full path for quick lookups
    created_date TIMESTAMP,
    modified_date TIMESTAMP,

    FOREIGN KEY (parent_id) REFERENCES folders (id) ON DELETE CASCADE
);
```

**Folder Hierarchy:**
- **Root folder**: `parent_id = NULL` (hidden, acts as container)
- **Top-level folders**: `parent_id = root_folder_id`
- **Nested folders**: `parent_id = any_user_folder_id`
- **Unlimited depth**: Folders can be nested infinitely (e.g., `Body/Walk/Realistic/Forward`)

**Folder Operations:**
- `get_folder_descendants(folder_id)` - Returns all nested folder IDs recursively
- `update_folder_parent(folder_id, new_parent_id)` - Moves folder in hierarchy
- Circular reference protection prevents moving folder into its own subfolder

**folder_icons** - Folder icon customization
```sql
CREATE TABLE folder_icons (
    folder_id INTEGER PRIMARY KEY,
    icon_id TEXT NOT NULL,    -- Preset: 'body', 'face', 'hand', 'locomotion', etc.

    FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE
);
```

---

## Folder Management System

### Nested Folder Hierarchy

**Visual Structure:**
```
Root (hidden)
├─ Body Mechanics          (top-level)
│  ├─ Walk Cycles          (nested)
│  │  ├─ Realistic         (deeply nested)
│  │  └─ Stylized          (deeply nested)
│  └─ Run Cycles           (nested)
├─ Locomotion              (top-level)
└─ Combat                  (top-level)
```

**Tree Widget Features:**
1. **Expand/Collapse Arrows**:
   - Right arrow (▶️) when folder is collapsed
   - Down arrow (▼) when folder is expanded
   - Only shown on folders with children
   - Styled via QTreeView QSS

2. **Dynamic Icons**:
   - **Custom preset icons**: Don't change on expand/collapse (body, face, hand, etc.)
   - **Default icons**: Change between `folder_closed` and `folder_open`
   - Icons colorized based on current theme

3. **Drag & Drop System**:
   - **MIME Types**:
     - `application/x-animation-uuid` - Animation cards from grid
     - `application/x-qabstractitemmodeldatalist` - Internal folder moves
   - **Drop Targets**:
     - User folder → Creates nested hierarchy
     - Empty space → Moves to root level
     - Virtual folder ("All Animations") → Moves to root level
   - **Safety Checks**:
     - Circular reference prevention (can't drag into own subfolder)
     - "Cannot move into itself" validation
     - "Already at root" detection

4. **Recursive Filtering**:
   - When folder selected, shows animations in that folder AND all subfolders
   - Example: Selecting "Body Mechanics" shows animations from "Walk Cycles", "Run Cycles", etc.
   - Database method `get_folder_descendants()` returns all nested folder IDs
   - Proxy model filters by set of folder IDs instead of single ID

### Drag & Drop Flow

```
User drags folder "Walk Cycles"
    ↓
startDrag() - Stores dragged item
    ↓
dragEnterEvent() - Accepts folder MIME type
    ↓
dragMoveEvent() - Highlights target folder (visual feedback)
    ↓
dropEvent() - Validates move, checks circular refs
    ↓
_move_folder_to_folder() or _move_folder_to_root()
    ↓
Extract folder names (BEFORE tree reload!)
    ↓
update_folder_parent() - Updates database
    ↓
_load_folders() - Rebuilds tree with new hierarchy
    ↓
Show success message
```

**Critical Implementation Detail:**
Folder names must be extracted BEFORE calling `_load_folders()` because the tree reload deletes all `QTreeWidgetItem` objects, causing `RuntimeError: wrapped C/C++ object has been deleted` if accessed after.

---

## Blender Integration

### Communication Method

File-based queue system (no network required):

```
Desktop App                         Blender Plugin
     ↓                                    ↓
queue_apply_animation(uuid, name)   Poll queue directory
     ↓                                    ↓
Create JSON in temp queue           Find apply_*.json files
     ↓                                    ↓
{                                   Read JSON, extract UUID
  "status": "pending",                   ↓
  "animation_id": "uuid",           Load .blend from library
  "animation_name": "Walk",              ↓
  "timestamp": "..."                Apply to active armature
}                                        ↓
                                    Delete queue file
```

**Queue Directory**: `%TEMP%/animation_library_queue/`

**File Format**: `apply_{uuid}_{timestamp}.json`

**Benefits**:
- No network configuration needed
- Works on network paths
- Simple, robust, debuggable
- Survives app crashes (queue persists)

---

## Testing Strategy

### Unit Tests (Planned)
```
tests/
├── test_database_service.py    # Database operations
├── test_theme_manager.py       # Theme switching
├── test_color_utils.py         # Color conversions
└── test_icon_loader.py         # Icon loading
```

### UI Tests (Planned)
```
tests/ui/
├── test_main_window.py         # Window layout
├── test_header_toolbar.py      # Toolbar interactions
├── test_folder_tree.py         # Folder selection
└── test_animation_view.py      # Grid/list switching
```

### Integration Tests (Planned)
```
tests/integration/
├── test_blender_queue.py       # Queue communication
├── test_thumbnail_loading.py   # Async loading
└── test_database_migration.py  # Schema upgrades
```

---

## Extension Points

### Adding a New Widget

1. Create file in `animation_library/widgets/`
2. Inherit from appropriate Qt base class
3. Add comprehensive docstring with ASCII diagram
4. Connect to event bus if needed
5. Use theme colors: `ThemeManager.get_current_theme().palette`
6. Export in `widgets/__init__.py`

### Adding a New Theme

1. Create Theme subclass in `themes/`
2. Implement `get_palette()` and `get_stylesheet()`
3. Register in ThemeManager
4. Test all widget states (hover, pressed, disabled)
5. Verify icon colorization looks good

### Adding a New Service

1. Create service class in `services/`
2. Implement as singleton with getter function
3. Follow repository pattern for data access
4. Add comprehensive docstrings
5. Export in `services/__init__.py`

### Adding a New Database Feature

1. Update schema in `DatabaseService._create_schema()`
2. Increment `SCHEMA_VERSION`
3. Add migration in `_migrate_to_vX()`
4. Add service methods for new feature
5. Update models to include new data
6. Update views to display new data

---

## Security Considerations

### SQL Injection Prevention
- All queries use parameterized statements
- Never string concatenation for SQL
- Example: `cursor.execute('SELECT * FROM animations WHERE uuid = ?', (uuid,))`

### File Path Validation
- All paths validated before file operations
- UNC paths supported for network storage
- Path traversal attacks prevented

### User Input Sanitization
- Tag input validated and sanitized
- File names cleaned of special characters
- Description length limits enforced

---

## Common Workflows

### User Favorites an Animation

1. User clicks star icon on animation card
2. `AnimationCardDelegate.editorEvent()` detects click
3. `DatabaseService.toggle_favorite(uuid)` updates DB
4. `AnimationListModel.refresh_animation(uuid)` reloads data
5. View repaints with filled star
6. If "Favorites" folder selected, animation appears/disappears

### User Changes Theme

1. User selects theme in Settings > Appearance
2. `ThemeTab._on_theme_selected()` called
3. `ThemeManager.set_theme(theme_name)` loads theme
4. `ThemeManager.theme_changed.emit()` notifies widgets
5. All widgets reload icons with new colors
6. MainWindow applies new QSS stylesheet
7. UI updates to new theme

### User Applies Animation in Blender

1. User double-clicks animation in library
2. `AnimationView.animation_double_clicked.emit(uuid)`
3. `BlenderService.queue_apply_animation(uuid, name)`
4. JSON file created in temp queue directory
5. Blender plugin polls queue (500ms interval)
6. Plugin finds file, reads UUID
7. Plugin loads .blend file from library
8. Animation applied to active armature
9. Plugin deletes queue file

---

## Troubleshooting

### Thumbnails Not Loading
- Check cache size limit in Config
- Verify thumbnail files exist at paths
- Check ThumbnailLoader thread pool status
- Verify gradient values are valid RGB tuples

### Theme Not Applying
- Verify theme registered in ThemeManager
- Check QSS syntax for errors
- Verify palette has all required colors
- Force style refresh: `widget.style().polish(widget)`

### Database Errors
- Check schema version matches code version
- Run migration if needed
- Verify database file permissions
- Check for locked database (close other connections)

### Blender Integration Not Working
- Verify queue directory exists: `%TEMP%/animation_library_queue/`
- Check Blender addon is installed and enabled
- Verify library path matches in both apps
- Check JSON queue files being created

---

## Future Enhancements

### Completed Features
- [x] **Drag & drop folder reorganization** - Fully implemented with nested hierarchy support
  - Drag folders into other folders (create hierarchy)
  - Drag folders to empty space (move to root)
  - Expand/collapse arrows for folders with children
  - Recursive folder filtering
  - Circular reference protection

### Planned Features
- [ ] Animation preview on double-click (in-app playback)
- [ ] Batch thumbnail regeneration
- [ ] Cloud sync support
- [ ] Animation versioning
- [ ] Custom metadata fields
- [ ] Advanced search with AND/OR queries
- [ ] Animation collections (playlists)

### Performance Improvements
- [ ] Database connection pooling
- [ ] Thumbnail pre-loading for visible items
- [ ] GPU-accelerated gradient compositing
- [ ] Lazy loading for large folders (1000+ items)

---

## Resources

### Key Documentation
- Qt Model/View: https://doc.qt.io/qt-6/model-view-programming.html
- PyQt6 Signals & Slots: https://www.riverbankcomputing.com/static/Docs/PyQt6/
- SQLite Best Practices: https://www.sqlite.org/lang.html

### Development Tools
- Qt Designer: UI prototyping
- DB Browser for SQLite: Database inspection
- PyCharm: Python IDE with Qt support
- Black: Python code formatter

---

## Contributors

Animation Library v2 is developed by CGstuff and open source contributors.

**Architecture**: Model-View-Controller with event-driven communication
**UI Framework**: PyQt6
**Database**: SQLite 3
**Theme System**: Dynamic QSS generation from color palettes
**Performance**: Virtual scrolling, async loading, caching

For questions or contributions, see the main README.md.
