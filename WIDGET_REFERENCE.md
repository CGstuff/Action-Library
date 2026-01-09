# Widget Reference
## Animation Library v2 - Complete Widget Documentation

**Date:** 2026-01-05
**Target Audience:** Frontend Developers
**Purpose:** Comprehensive reference for all UI widgets, their features, and usage patterns

---

## Table of Contents

1. [Main Window](#main-window)
2. [Header Toolbar](#header-toolbar)
3. [Folder Tree](#folder-tree)
4. [Animation View](#animation-view)
5. [Animation Card Delegate](#animation-card-delegate)
6. [Metadata Panel](#metadata-panel)
7. [Bulk Edit Toolbar](#bulk-edit-toolbar)
8. [Dialog Widgets](#dialog-widgets)
9. [Settings Dialog](#settings-dialog)
10. [Common Patterns](#common-patterns)

---

## Main Window

**File:** `animation_library/widgets/main_window.py` (742 lines)

### Description

The top-level application window orchestrating all major UI components. Implements a 3-panel layout with persistent window state and event bus integration.

### Layout

```
┌─────────────────────────────────────────────┐
│ Header Toolbar                              │
├─────────────────────────────────────────────┤
│ Bulk Edit Toolbar (conditional)             │
├──────────┬───────────────┬──────────────────┤
│          │               │                  │
│  Folder  │   Animation   │    Metadata      │
│   Tree   │     View      │     Panel        │
│          │   (Grid/List) │  (Details+Video) │
│          │               │                  │
└──────────┴───────────────┴──────────────────┘
│ Status Bar                                  │
└─────────────────────────────────────────────┘
```

### Key Features

- **3-Panel Layout**: Folder tree (left), animation grid/list (center), metadata (right)
- **Persistent State**: Saves/restores window size, position, and splitter positions
- **Event Bus Integration**: Listens to and emits events for cross-widget communication
- **Keyboard Shortcuts**: F5 (refresh), Del (delete), Ctrl+N (new folder), Ctrl+, (settings)
- **Multi-Selection**: Bulk operations on multiple animations
- **Drag & Drop**: Animations to folders, folders to folders

### Usage Example

```python
from animation_library.widgets.main_window import MainWindow

# Create and show main window
window = MainWindow()
window.show()

# The window automatically:
# - Loads last window state
# - Connects to event bus
# - Initializes all child widgets
# - Loads animation library
```

### Important Methods

```python
def _on_folder_selected(folder_id: int, folder_name: str, recursive: bool):
    """Handle folder selection from tree"""
    # Applies filtering to animation view

def _on_animation_selected(uuid: str):
    """Handle animation selection from view"""
    # Updates metadata panel with animation details

def _refresh_library():
    """Reload animations from database"""
    # Refreshes all models and views
```

### Signals Used

| Signal | Direction | Purpose |
|--------|-----------|---------|
| `folder_selected` | From FolderTree | Filter animations by folder |
| `animation_selected` | From AnimationView | Show metadata |
| `search_text_changed` | From HeaderToolbar | Filter by search text |
| `view_mode_changed` | From HeaderToolbar | Switch grid/list mode |
| `edit_mode_changed` | From HeaderToolbar | Enable bulk operations |

---

## Header Toolbar

**File:** `animation_library/widgets/header_toolbar.py` (398 lines)

### Description

Main toolbar with search, view controls, filtering, and sorting. Features theme-aware icon colorization and orange gradient background.

### Layout

```
[New Folder] [Grid/List] [Search] [Rig Type ▼] [Tags ▼] [Sort ▼] [Grid Icon: ----] [Edit] [Refresh] [Delete] ... [Settings]
```

### Key Features

- **Search Box**: Live text filtering (200px wide, clear button)
- **View Mode Toggle**: Switch between grid/list (icon-only button)
- **Card Size Slider**: Adjust grid card size (120px slider)
- **Rig Type Filter**: Dropdown with all available rig types
- **Tags Filter**: Dropdown with all tags
- **Sort Options**: Name, Date, Duration, Recent (ascending/descending)
- **Edit Mode**: Toggle multi-selection and bulk operations
- **Refresh Library**: Reload from database (F5 shortcut)
- **Settings**: Open settings dialog (Ctrl+, shortcut)
- **Theme-Aware Icons**: Icons recolor based on theme's `header_icon_color`

### Visual Properties

```python
# Fixed height
self.setFixedHeight(50)

# Orange gradient background (via theme property)
self.setProperty("header", "true")

# Icon size: 24x24 for most buttons
# Button size: 40x40 for icon buttons, 32x32 for view mode
```

### Usage Example

```python
from animation_library.widgets.header_toolbar import HeaderToolbar

toolbar = HeaderToolbar()

# Connect signals
toolbar.search_text_changed.connect(on_search)
toolbar.view_mode_changed.connect(on_view_mode)
toolbar.card_size_changed.connect(on_card_size)
toolbar.rig_type_filter_changed.connect(on_rig_filter)
toolbar.tags_filter_changed.connect(on_tags_filter)
toolbar.sort_changed.connect(on_sort)
toolbar.edit_mode_changed.connect(on_edit_mode)
toolbar.delete_clicked.connect(on_delete)
toolbar.refresh_library_clicked.connect(on_refresh)
toolbar.settings_clicked.connect(on_settings)
toolbar.new_folder_clicked.connect(on_new_folder)

# Refresh filter data after library changes
toolbar.refresh_filters()
```

### Signals

```python
search_text_changed = pyqtSignal(str)
view_mode_changed = pyqtSignal(str)  # "grid" or "list"
card_size_changed = pyqtSignal(int)
edit_mode_changed = pyqtSignal(bool)
delete_clicked = pyqtSignal()
refresh_library_clicked = pyqtSignal()
settings_clicked = pyqtSignal()
new_folder_clicked = pyqtSignal()
rig_type_filter_changed = pyqtSignal(list)  # List of selected rig types
tags_filter_changed = pyqtSignal(list)  # List of selected tags
sort_changed = pyqtSignal(str, str)  # (sort_by, sort_order)
```

### Filter Data Updates

```python
# After adding new animations or tags
toolbar.refresh_filters()  # Reloads rig types and tags from database
```

---

## Folder Tree

**File:** `animation_library/widgets/folder_tree.py` (594 lines)

### Description

Tree widget for folder navigation with virtual folders, user folders, drag & drop support, and context menus.

### Layout

```
📁 All Animations
📁 Recent
⭐ Favorites
───────────────
▼ Body Mechanics              (expanded, has children)
  ▶️ Walk Cycles              (collapsed, has children)
  📁 Idles                    (no children - no arrow)
▶️ Locomotion                 (collapsed, has children)
📁 Facial                     (no children)
📁 Combat                     (no children)
```

### Key Features

- **Virtual Folders**: "All Animations", "Recent", "Favorites" (bold, no folder ID)
- **Nested Hierarchy**: Unlimited depth parent/child folder structure
- **Expand/Collapse Arrows**:
  - Right arrow (▶️) when collapsed
  - Down arrow (▼) when expanded
  - Only shown on folders with children
- **Dynamic Folder Icons**:
  - Custom preset icons (body, face, hand, locomotion, combat, idle)
  - Default icons change: folder_closed (📁) ↔ folder_open (📂) on expand/collapse
- **Context Menus**: Create, rename, delete, change icon
- **Advanced Drag & Drop**:
  - Drag animations from view to folders
  - Drag folders into other folders (create nested hierarchy)
  - Drag folders to empty space (move to root level)
  - Drag folders to "All Animations" (move to root level)
  - Visual feedback: target folder highlights during drag
- **Recursive Folder Filtering**: Shows animations in selected folder and all subfolders
- **Safety Features**:
  - Circular reference protection (can't drag folder into its own subfolder)
  - "Already at root" detection
  - Drag onto self prevention

### Visual Properties

```python
# Minimum width
self.setMinimumWidth(200)

# Single selection
self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)

# Drag & drop enabled
self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
```

### Usage Example

```python
from animation_library.widgets.folder_tree import FolderTree

tree = FolderTree()

# Connect signals
tree.folder_selected.connect(on_folder_selected)  # (folder_id, folder_name, recursive)
tree.recursive_search_changed.connect(on_recursive_changed)

# Refresh after database changes
tree.refresh()

# Programmatically create folder
tree.create_folder_with_dialog()

# Get/set recursive search
is_recursive = tree.get_recursive_search()
tree.set_recursive_search(True)
```

### Signals

```python
folder_selected = pyqtSignal(int, str, bool)  # folder_id, folder_name, recursive
recursive_search_changed = pyqtSignal(bool)  # recursive state
```

### Drag & Drop MIME Types

```python
# Animation UUID (from AnimationView)
'application/x-animation-uuid'  # UTF-8 encoded UUID(s), newline-separated

# Folder hierarchy (internal)
'application/x-qabstractitemmodeldatalist'  # Qt internal format
```

### Folder Item Data

```python
# Virtual folders
item.setData(0, Qt.ItemDataRole.UserRole, {
    'type': 'virtual',
    'folder_id': None,
    'folder_name': 'All Animations'
})

# User folders
item.setData(0, Qt.ItemDataRole.UserRole, {
    'type': 'user',
    'folder_id': 42,
    'folder_name': 'Body Mechanics'
})
item.folder_id = 42  # For drag-drop
```

### Drag & Drop Behavior Details

**Folder-to-Folder Drag:**
```python
# Scenario 1: Drag folder into another folder
Source: "Walk Cycles"
Target: "Body Mechanics" (user folder)
Result: Creates hierarchy - Walk Cycles becomes child of Body Mechanics

# Scenario 2: Drag folder to empty space
Source: "Walk Cycles" (currently nested)
Target: Empty area in tree
Result: Moves to root level (top-level folder)

# Scenario 3: Drag folder to virtual folder
Source: "Walk Cycles" (currently nested)
Target: "All Animations" virtual folder
Result: Moves to root level (same as empty space)

# Scenario 4: Invalid moves (prevented with error messages)
- Drag folder onto itself → "Cannot move folder into itself"
- Drag folder into its own subfolder → Circular reference error
- Drag already-root folder to root → "Already at root level"
```

**Event Sequence:**
1. `dragEnterEvent()` - Accepts both animation and folder MIME types
2. `dragMoveEvent()` - Highlights target, provides visual feedback
3. `dropEvent()` - Validates move, updates database, reloads tree
4. Success message shown after tree reload

**Backend Methods:**
- `_move_folder_to_folder(source, target)` - Creates hierarchy
- `_move_folder_to_root(source)` - Moves to root level
- `_is_descendant(folder_id, ancestor_id)` - Prevents circular refs

---

## Animation View

**File:** `animation_library/views/animation_view.py` (337 lines)

### Description

QListView displaying animations in grid or list mode with virtual scrolling, hover detection, and drag & drop. Uses AnimationCardDelegate for custom rendering.

### Features

- **Grid Mode**: IconMode with card flow and wrapping
- **List Mode**: ListMode with horizontal entries
- **Virtual Scrolling**: Only renders visible items (performance optimization)
- **Hover Detection**: Shows video preview after configurable delay
- **Multi-Selection**: Extended selection for bulk operations
- **Drag & Drop**: Drag animations to folders
- **Last Viewed Tracking**: Updates on selection and double-click
- **Uniform Item Sizes**: Performance optimization

### Usage Example

```python
from animation_library.views.animation_view import AnimationView
from animation_library.models.animation_filter_proxy_model import AnimationFilterProxyModel

view = AnimationView()

# Set model (usually a proxy model for filtering)
proxy_model = AnimationFilterProxyModel()
proxy_model.setSourceModel(animation_list_model)
view.setModel(proxy_model)

# Connect signals
view.animation_double_clicked.connect(on_double_click)  # UUID
view.animation_context_menu.connect(on_context_menu)  # UUID, position
view.hover_started.connect(on_hover_start)  # UUID, position
view.hover_ended.connect(on_hover_end)

# Change view mode
view.set_view_mode("grid")  # or "list"

# Change card size (grid mode only)
view.set_card_size(200)  # pixels

# Selection
view.select_animation(uuid)
view.clear_selection()
selected_uuids = view.get_selected_uuids()
```

### Signals

```python
animation_double_clicked = pyqtSignal(str)  # animation_uuid
animation_context_menu = pyqtSignal(str, QPoint)  # animation_uuid, position
hover_started = pyqtSignal(str, QPoint)  # animation_uuid, position
hover_ended = pyqtSignal()
```

### View Modes

| Mode | Description | Layout |
|------|-------------|--------|
| `grid` | Cards in wrapping grid | IconMode, LeftToRight flow, spacing=0 |
| `list` | Horizontal list entries | ListMode, TopToBottom flow, spacing=2 |

### Performance Optimizations

```python
# Virtual scrolling
self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

# Uniform item sizes
self.setUniformItemSizes(True)

# No alternating colors (delegate handles painting)
self.setAlternatingRowColors(False)
```

---

## Animation Card Delegate

**File:** `animation_library/views/animation_card_delegate.py` (565 lines)

### Description

Custom QStyledItemDelegate for rendering animation cards with thumbnails, metadata, star icons (favorites), and visual states. Handles grid and list modes with different layouts.

### Grid Mode Layout

```
┌────────────────────┐
│                    │
│     Thumbnail      │
│      (150x150)     │
│                    │
├────────────────────┤
│ Animation Name     │
│ Duration: 2.5s     │
│ [tag1] [tag2] ⭐   │
└────────────────────┘
```

### List Mode Layout

```
┌──────┬────────────────────────────────────┐
│ Thb  │ Animation Name                  ⭐ │
│ 60px │ Body Mechanics | Humanoid          │
│      │ Duration: 2.5s  [tag1] [tag2]      │
└──────┴────────────────────────────────────┘
```

### Key Features

- **Async Thumbnail Loading**: Uses QThreadPool for non-blocking image loading
- **Pixmap Caching**: 512MB LRU cache for loaded thumbnails
- **Star Icon**: Click to toggle favorite (immediate UI update)
- **Visual States**: Hover, selected, gold border for favorited
- **Edit Mode**: Shows selection indicators for bulk operations
- **Gradient Background**: Supports header gradient for premium cards
- **Tag Badges**: Rounded blue badges for tags
- **Theme-Aware**: Uses theme colors for all UI elements

### Usage

```python
from animation_library.views.animation_card_delegate import AnimationCardDelegate

# Automatically set by AnimationView
delegate = AnimationCardDelegate(parent_view, view_mode="grid")
view.setItemDelegate(delegate)

# Switch modes
delegate.set_view_mode("list")

# Change card size (grid only)
delegate.set_card_size(250)

# Toggle edit mode
delegate.set_edit_mode(True)
```

### Interactive Elements

```python
# Star icon click (favorite toggle)
# - Detects click in star icon bounds
# - Calls database_service.toggle_favorite(uuid)
# - Refreshes animation data from source model
# - Forces viewport repaint

# Returns True if click handled, False otherwise
```

### Visual Properties

| Property | Grid Mode | List Mode |
|----------|-----------|-----------|
| Card Width | `card_size` (150-500px) | Full width |
| Card Height | `card_size + text_height` | 80px |
| Thumbnail Size | `card_size × card_size` | 60×60px |
| Spacing | 0px (tight grid) | 2px |
| Border | 1px on selected/hover | None |
| Gold Border | Favorited items | Favorited items |

### Thumbnail Loading

```python
# Async loading workflow:
1. paint() checks if thumbnail exists in cache
2. If not, starts QRunnable task in QThreadPool
3. Task loads image from disk
4. Emits signal when complete
5. Caches pixmap (512MB LRU)
6. Triggers viewport repaint
```

---

## Metadata Panel

**File:** `animation_library/widgets/metadata_panel.py` (751 lines)

### Description

Right panel displaying selected animation's details and video preview with playback controls. Supports tag management in edit mode.

### Layout

```
┌─────────────────┐
│                 │
│  Video Preview  │
│    (350px)      │
│                 │
├─────────────────┤
│ [▶] [Loop] ──── │ ← Playback controls
├─────────────────┤
│ Animation Name  │
│ Description     │
├─────────────────┤
│ Technical Info  │
│ - Frames        │
│ - FPS           │
│ - Duration      │
├─────────────────┤
│ Rig Info        │
│ - Type          │
│ - Armature      │
│ - Bone Count    │
├─────────────────┤
│ Files           │
│ - File Size     │
│ - Author        │
│ - Created       │
├─────────────────┤
│ Tags            │
│ [tag1] [tag2×]  │ ← Red with × in edit mode
└─────────────────┘
```

### Key Features

- **Video Preview**: 350px height, OpenCV-based playback
- **Playback Controls**: Play/pause toggle, loop button, seek slider
- **Metadata Sections**: Technical, Rig, Files, Tags
- **Tag Badges**: Blue badges, red with × button in edit mode
- **Tag Removal**: Click × to remove tag (with confirmation)
- **Auto-pause**: Pauses on new animation load
- **First Frame Display**: Shows thumbnail when paused
- **Theme-Aware Icons**: Play/pause/loop icons recolor with theme

### Usage Example

```python
from animation_library.widgets.metadata_panel import MetadataPanel

panel = MetadataPanel()

# Set animation data
animation = {
    'uuid': '...',
    'name': 'Walk Cycle',
    'description': 'Basic walk animation',
    'preview_path': '/path/to/video.mp4',
    'frame_start': 1,
    'frame_end': 24,
    'fps': 24,
    'duration_seconds': 1.0,
    'rig_type': 'humanoid',
    'armature_name': 'rig',
    'bone_count': 42,
    'file_size_mb': 2.5,
    'author': 'John Doe',
    'created_date': '2025-01-05',
    'tags': ['walk', 'locomotion'],
    # Lineage fields (v1.1)
    'version': 1,
    'version_label': 'v001',
    'version_group_id': 'abc-123-def',
    'is_latest': 1,
    # Status field (v1.1)
    'status': 'none'  # none, wip, review, approved, needs_work, final
}

panel.set_animation(animation)

# Clear panel
panel.clear()
```

### Video Player API

```python
def _load_video(video_path: str) -> bool:
    """Load video file for preview"""
    # Returns True on success, False on error

def _toggle_playback():
    """Toggle play/pause state"""
    # Updates icon (play ↔ pause)

def _on_slider_released():
    """Handle seek slider release"""
    # Jumps to frame based on slider position
```

### Tag Badge States

```python
# Normal mode (read-only)
badge_style = """
    QFrame {
        background-color: #4a90e2;  /* Blue */
        border-radius: 3px;
        padding: 2px 6px;
    }
"""

# Edit mode (removable)
badge_style = """
    QFrame {
        background-color: #dc3545;  /* Red */
        border-radius: 3px;
        padding: 2px 6px;
    }
"""
# + Remove button (× symbol)
```

### Lineage Section (v1.1)

Displays version info and provides access to version history:
- **Version Label**: Shows current version (e.g., "v001", "v002")
- **LATEST Badge**: Green badge shown if `is_latest == 1`
- **Version Count**: Shows "(X versions)" if multiple versions exist
- **View Lineage Button**: Opens `VersionHistoryDialog`

### Status Badge (v1.1)

Clickable badge showing lifecycle status:

```python
# Status colors from Config.LIFECYCLE_STATUSES
LIFECYCLE_STATUSES = {
    'none': {'color': None, 'label': 'None'},        # Gray, muted
    'wip': {'color': '#FF9800', 'label': 'WIP'},     # Orange
    'review': {'color': '#2196F3', 'label': 'In Review'},  # Blue
    'approved': {'color': '#4CAF50', 'label': 'Approved'}, # Green
    'needs_work': {'color': '#F44336', 'label': 'Needs Work'}, # Red
    'final': {'color': '#9C27B0', 'label': 'Final'}, # Purple
}

# Clicking badge shows QMenu dropdown to change status
```

### Video Formats Supported

OpenCV supports: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`

Default frame rate if not detected: 24 FPS

---

## Bulk Edit Toolbar

**File:** `animation_library/widgets/bulk_edit_toolbar.py` (146 lines)

### Description

Conditional toolbar shown when edit mode is enabled. Displays selection count and bulk operation buttons.

### Layout

```
┌────────────────────────────────────────────┐
│ 3 animations selected  [Add Tags] [Remove]│
└────────────────────────────────────────────┘
```

### Key Features

- **Selection Counter**: Shows number of selected animations
- **Visibility**: Only shown when `edit_mode=True`
- **Add Tags**: Add tags to all selected animations
- **Remove**: Delete all selected animations (with confirmation)

### Usage Example

```python
from animation_library.widgets.bulk_edit_toolbar import BulkEditToolbar

toolbar = BulkEditToolbar()

# Show/hide based on edit mode
toolbar.setVisible(edit_mode_enabled)

# Connect signals
toolbar.add_tags_clicked.connect(on_add_tags)
toolbar.remove_clicked.connect(on_remove_animations)

# Update selection count
toolbar.update_selection_count(5)
```

---

## Dialog Widgets

### Icon Picker Dialog

**File:** `animation_library/widgets/dialogs/icon_picker_dialog.py`

Displays grid of folder preset icons for user selection.

```python
from animation_library.widgets.dialogs.icon_picker_dialog import IconPickerDialog

presets = icon_service.get_all_presets()
current_icon = icon_service.get_folder_icon(folder_id)

dialog = IconPickerDialog(presets, current_icon, parent)
if dialog.exec():
    selected_icon = dialog.get_selected_icon()
    icon_service.set_folder_icon(folder_id, selected_icon)
```

### Tag Input Dialog

**File:** `animation_library/widgets/dialogs/tag_input_dialog.py`

Input dialog for adding tags to animations.

```python
from animation_library.widgets.dialogs.tag_input_dialog import TagInputDialog

dialog = TagInputDialog(parent)
if dialog.exec():
    new_tags = dialog.get_tags()  # List[str]
    # Add tags to selected animations
```

### Gradient Picker Dialog

**File:** `animation_library/widgets/dialogs/gradient_picker_dialog.py`

Color gradient selector for theme customization.

```python
from animation_library.widgets.dialogs.gradient_picker_dialog import GradientPickerDialog

dialog = GradientPickerDialog(initial_gradient, parent)
if dialog.exec():
    selected_gradient = dialog.get_gradient()
    # Apply gradient to theme
```

---

## Settings Dialog

**File:** `animation_library/widgets/settings/settings_dialog.py`

### Description

Tabbed settings dialog with theme, Blender integration, and storage location configuration.

### Tabs

1. **Theme Tab** (`theme_tab.py`)
   - Theme selector (dark, light, built-in themes)
   - Custom theme creator
   - Live preview
   - Import/export themes

2. **Blender Integration Tab** (`blender_integration_tab.py`)
   - Blender executable path
   - Auto-detect Blender version
   - Test connection
   - Enable/disable integration

3. **Storage Locations Tab** (`storage_locations_tab.py`)
   - Animation files directory
   - Preview videos directory
   - Database location
   - Backup settings

### Usage Example

```python
from animation_library.widgets.settings.settings_dialog import SettingsDialog

dialog = SettingsDialog(parent)
dialog.exec()

# Settings automatically saved via QSettings
```

### Theme Editor Dialog

**File:** `animation_library/widgets/settings/theme_editor_dialog.py`

Advanced theme creation with color picker for each palette property.

```python
from animation_library.widgets.settings.theme_editor_dialog import ThemeEditorDialog

dialog = ThemeEditorDialog(parent)
if dialog.exec():
    custom_theme = dialog.get_theme()
    theme_manager.add_custom_theme(custom_theme)
```

---

## Common Patterns

### Event Bus Communication

All widgets communicate via centralized event bus (singleton):

```python
from animation_library.events.event_bus import get_event_bus

event_bus = get_event_bus()

# Listen to events
event_bus.folder_selected.connect(on_folder_selected)
event_bus.search_text_changed.connect(on_search_changed)
event_bus.view_mode_changed.connect(on_view_mode_changed)

# Emit events
event_bus.set_folder("Favorites")
event_bus.set_search_text("walk")
event_bus.set_view_mode("grid")
```

### Theme Integration

All widgets use centralized theme manager:

```python
from animation_library.themes.theme_manager import get_theme_manager

theme_manager = get_theme_manager()

# Get current theme
theme = theme_manager.get_current_theme()
color = theme.palette.accent

# Listen for theme changes
theme_manager.theme_changed.connect(on_theme_changed)

def on_theme_changed(theme_name: str):
    # Reload icons with new colors
    # Update custom stylesheets
    # Repaint widgets
```

### Icon Colorization

All icons use theme-based colorization:

```python
from animation_library.utils.icon_loader import IconLoader
from animation_library.utils.icon_utils import colorize_white_svg
from animation_library.themes.theme_manager import get_theme_manager

theme = get_theme_manager().get_current_theme()
icon_color = theme.palette.header_icon_color

# Get white SVG icon
icon_path = IconLoader.get("play")

# Colorize with theme color
colored_icon = colorize_white_svg(icon_path, icon_color)

# Use in button
button.setIcon(colored_icon)
button.setIconSize(QSize(24, 24))
```

### Database Service Access

All widgets access database via singleton service:

```python
from animation_library.services.database_service import get_database_service

db_service = get_database_service()

# Query animations
animations = db_service.get_all_animations()
animation = db_service.get_animation_by_uuid(uuid)

# Update animation
db_service.update_animation(uuid, {'name': 'New Name'})

# Folder operations
folders = db_service.get_all_folders()
folder_id = db_service.create_folder('New Folder', parent_id)
```

### Custom Properties for Styling

Widgets use Qt properties for dynamic QSS styling:

```python
# Set property
widget.setProperty("header", "true")
widget.setProperty("media", "true")

# Force stylesheet reapply
widget.style().unpolish(widget)
widget.style().polish(widget)

# QSS example (in theme)
QWidget[header="true"] {
    background: qlineargradient(...);
}

QPushButton[media="true"] {
    background-color: #2a2a2a;
    border-radius: 4px;
}
```

### Signal Connection Pattern

Standard pattern for connecting widget signals:

```python
def __init__(self, parent=None):
    super().__init__(parent)

    # Create widgets
    self._create_widgets()

    # Create layout
    self._create_layout()

    # Connect signals AFTER widgets exist
    self._connect_signals()

def _connect_signals(self):
    """Connect internal signals"""
    self._button.clicked.connect(self._on_button_clicked)
    self._slider.valueChanged.connect(self._on_value_changed)

    # Event bus connections
    event_bus = get_event_bus()
    event_bus.some_signal.connect(self._on_external_event)
```

### Persistent Window State

Main window and dialogs save/restore state:

```python
from PyQt6.QtCore import QSettings

def closeEvent(self, event):
    """Save window state before closing"""
    settings = QSettings("AnimationLibrary", "MainWindow")
    settings.setValue("geometry", self.saveGeometry())
    settings.setValue("windowState", self.saveState())
    settings.setValue("splitterSizes", self._splitter.saveState())
    super().closeEvent(event)

def _restore_window_state(self):
    """Restore window state"""
    settings = QSettings("AnimationLibrary", "MainWindow")
    geometry = settings.value("geometry")
    if geometry:
        self.restoreGeometry(geometry)

    state = settings.value("windowState")
    if state:
        self.restoreState(state)

    splitter_state = settings.value("splitterSizes")
    if splitter_state:
        self._splitter.restoreState(splitter_state)
```

---

## Widget Interaction Diagram

```
                        Event Bus (Singleton)
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
  HeaderToolbar          FolderTree           AnimationView
        │                      │                      │
        │ search_text          │ folder_selected      │ selection_changed
        │ view_mode            │                      │ double_click
        │ card_size            │                      │
        ▼                      ▼                      ▼
    MainWindow ◄───────────────────────────────► MetadataPanel
        │                                             │
        │ applies filters to                          │
        ▼                                             │
  AnimationFilterProxyModel                           │
        │                                             │
        │ filters                                     │
        ▼                                             │
  AnimationListModel                                  │
        │                                             │
        │ data                                        │
        ▼                                             │
  DatabaseService ◄───────────────────────────────────┘
```

---

## Best Practices

### Adding a New Widget

1. **Create in appropriate directory**
   - Main widgets → `widgets/`
   - Dialogs → `widgets/dialogs/`
   - Settings tabs → `widgets/settings/`
   - Views → `views/`

2. **Follow naming convention**
   - File: `my_widget.py`
   - Class: `MyWidget`
   - Export in `__init__.py`

3. **Add comprehensive docstring**
   ```python
   """
   MyWidget - Brief description

   Pattern: Design pattern used
   Inspired by: Reference if applicable

   Features:
   - Feature 1
   - Feature 2

   Layout:
       [ASCII diagram]
   """
   ```

4. **Use theme colors**
   ```python
   theme = get_theme_manager().get_current_theme()
   color = theme.palette.accent
   # Never hard-code colors
   ```

5. **Connect to event bus if needed**
   ```python
   self._event_bus = get_event_bus()
   self._event_bus.some_signal.connect(self._on_signal)
   ```

6. **Export in `__all__`**
   ```python
   __all__ = ['MyWidget']
   ```

### Modifying Existing Widgets

1. **Read the docstring first** - Understand purpose and design
2. **Preserve existing patterns** - Don't introduce new architectural patterns
3. **Update docstring if behavior changes**
4. **Test with both themes** - Dark and light
5. **Check all view modes** - Grid and list (if applicable)
6. **Verify event bus signals** - Ensure no broken connections

### Performance Considerations

1. **Use virtual scrolling** - For large lists/grids
2. **Cache pixmaps** - Don't reload images repeatedly
3. **Debounce expensive operations** - Use QTimer for search, filters
4. **Batch database queries** - Don't query in loops
5. **Async for I/O** - Use QThreadPool for file loading
6. **Uniform item sizes** - Enable `setUniformItemSizes(True)` for lists

---

## Troubleshooting

### Widget Not Updating

**Check:** Is it connected to the event bus?
```python
# Add connection
self._event_bus.relevant_signal.connect(self._on_update)
```

### Icons Not Showing

**Check:** Are icons being colorized with theme color?
```python
theme = get_theme_manager().get_current_theme()
icon_color = theme.palette.header_icon_color
icon = colorize_white_svg(IconLoader.get("icon_name"), icon_color)
```

### Theme Not Applying

**Check:** Is the widget property set?
```python
self.setProperty("custom_property", "value")
self.style().unpolish(self)
self.style().polish(self)
```

### Slow Rendering

**Check:** Performance optimizations
```python
# Enable uniform item sizes
self.setUniformItemSizes(True)

# Use virtual scrolling
self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

# Cache frequently accessed data
```

---

## Additional Resources

- **ARCHITECTURE.md** - Overall system architecture and design patterns
- **DEVELOPER_GUIDE.md** - Getting started, adding features, testing
- **Source Code Docstrings** - Every widget has detailed inline documentation
- **config.py** - All configurable constants and feature flags

For questions or contributions, refer to the main repository documentation.
