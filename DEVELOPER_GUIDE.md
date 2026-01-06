# Developer Guide - Animation Library v2

Welcome to the Animation Library v2 development guide! This document will help you get started with developing and extending the application.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Adding New Features](#adding-new-features)
5. [Theme Customization](#theme-customization)
6. [Widget Development](#widget-development)
7. [Database Operations](#database-operations)
8. [Testing](#testing)
9. [Best Practices](#best-practices)
10. [Common Tasks](#common-tasks)

---

## Getting Started

### Prerequisites

- Python 3.10+
- PyQt6
- SQLite 3
- Basic understanding of Qt Model/View architecture
- Familiarity with Qt signals & slots

### First Steps

1. **Read the Architecture Overview**
   - Start with `ARCHITECTURE.md` to understand the system design
   - Review the component diagram and signal flow

2. **Explore Key Files** (in this order):
   ```python
   config.py                    # Configuration constants
   widgets/main_window.py       # Main window layout
   themes/theme_manager.py      # Theme system
   events/event_bus.py          # Event communication
   models/animation_list_model.py  # Data structures
   services/database_service.py    # Database operations
   ```

3. **Run the Application**
   ```bash
   cd animation_library_v2
   python -m animation_library
   ```

4. **Make a Small Change**
   - Try changing a color in `themes/dark_theme.py`
   - Restart the app and see the change
   - This confirms your environment is working

---

## Development Setup

### Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### IDE Configuration

**PyCharm**:
- Mark `animation_library` as Sources Root
- Enable Qt Designer integration
- Install PyQt6 stubs for autocomplete

**VS Code**:
- Install Python extension
- Install PyQt6 Intellisense extension
- Configure linter (pylint or flake8)

### Development Database

```bash
# Use a test database during development
export ANIMLIB_DB_PATH="test_library.db"  # Linux/macOS
set ANIMLIB_DB_PATH=test_library.db       # Windows
```

---

## Project Structure

```
animation_library/
├── __init__.py                 # Package initialization
├── __main__.py                 # Application entry point
├── config.py                   # Global configuration
│
├── events/                     # Event system
│   ├── __init__.py
│   └── event_bus.py           # Singleton event bus
│
├── models/                     # Data models (MVC)
│   ├── __init__.py
│   ├── animation_list_model.py        # Qt model for animations
│   └── animation_filter_proxy_model.py # Filtering/sorting
│
├── services/                   # Business logic
│   ├── __init__.py
│   ├── database_service.py    # Database operations
│   ├── thumbnail_loader.py    # Async thumbnail loading
│   ├── blender_service.py     # Blender integration
│   ├── backup_service.py      # Library export/import (.animlib)
│   └── folder_icon_service.py # Folder icon management
│
├── themes/                     # Theme system
│   ├── __init__.py
│   ├── theme_manager.py       # Theme management
│   ├── dark_theme.py          # Dark theme implementation
│   ├── light_theme.py         # Light theme implementation
│   ├── built_in/              # Pre-built themes
│   └── custom/                # User custom themes
│
├── utils/                      # Utility functions
│   ├── __init__.py
│   ├── color_utils.py         # Color conversions
│   ├── gradient_utils.py      # Gradient generation
│   ├── icon_loader.py         # Icon loading
│   ├── icon_utils.py          # SVG colorization
│   └── image_utils.py         # Image operations
│
├── views/                      # View components (MVC)
│   ├── __init__.py
│   ├── animation_view.py      # Main animation list view
│   ├── animation_card_delegate.py # Card rendering
│   └── hover_video_widget.py  # Video preview widget
│
└── widgets/                    # UI widgets
    ├── __init__.py
    ├── main_window.py         # Main application window
    ├── header_toolbar.py      # Top toolbar
    ├── metadata_panel.py      # Right panel with details
    ├── folder_tree.py         # Left folder tree
    ├── bulk_edit_toolbar.py   # Bulk operations toolbar
    ├── dialogs/               # Dialog windows
    └── settings/              # Settings dialog tabs
```

---

## Adding New Features

### Feature Development Workflow

1. **Plan the Feature**
   - Define requirements
   - Identify affected components
   - Consider database changes
   - Plan signal flow

2. **Update Database (if needed)**
   - Modify schema in `DatabaseService._create_schema()`
   - Increment `SCHEMA_VERSION`
   - Add migration function `_migrate_to_vX()`

3. **Add Service Methods**
   - Add business logic to appropriate service
   - Follow repository pattern
   - Add comprehensive docstrings

4. **Update Models**
   - Add new data roles if needed
   - Update `AnimationListModel.data()`
   - Add helper methods

5. **Update UI**
   - Create or modify widgets
   - Connect to event bus
   - Use theme colors (never hard-code)

6. **Test**
   - Manual testing with various scenarios
   - Test theme switching
   - Test with large datasets

### Example: Adding a "Rating" Feature

```python
# 1. Update database schema
def _create_schema(self, cursor):
    # ... existing schema ...
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS animations (
            -- ... existing columns ...
            rating INTEGER DEFAULT 0,  -- NEW: 0-5 stars
            -- ...
        )
    ''')

# 2. Add migration
def _migrate_to_v3(self, cursor):
    cursor.execute('ALTER TABLE animations ADD COLUMN rating INTEGER DEFAULT 0')
    cursor.execute('CREATE INDEX idx_animations_rating ON animations(rating)')

# 3. Add service methods
def set_rating(self, uuid: str, rating: int) -> bool:
    """Set animation rating (0-5 stars)"""
    if not 0 <= rating <= 5:
        return False

    with self.transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE animations SET rating = ? WHERE uuid = ?',
            (rating, uuid)
        )
        return cursor.rowcount > 0

def get_animations_by_rating(self, min_rating: int) -> List[Dict]:
    """Get animations with rating >= min_rating"""
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM animations WHERE rating >= ? ORDER BY rating DESC',
        (min_rating,)
    )
    return [dict(row) for row in cursor.fetchall()]

# 4. Add to model
class AnimationRole(IntEnum):
    # ... existing roles ...
    RatingRole = Qt.ItemDataRole.UserRole + 74

def data(self, index, role):
    # ... existing roles ...
    elif role == AnimationRole.RatingRole:
        return animation.get('rating', 0)

# 5. Update UI (add rating widget to metadata panel)
class MetadataPanel(QWidget):
    def _create_widgets(self):
        # ... existing widgets ...
        self._rating_widget = RatingWidget()  # Custom star rating widget
        self._rating_widget.rating_changed.connect(self._on_rating_changed)

    def _on_rating_changed(self, rating: int):
        if self._current_uuid:
            self._db_service.set_rating(self._current_uuid, rating)
```

---

## Theme Customization

### Creating a New Theme

```python
# themes/my_theme.py
from .theme_manager import Theme, ColorPalette

class MyTheme(Theme):
    def get_palette(self) -> ColorPalette:
        return ColorPalette(
            # Define all required colors
            background="#1E1E1E",
            background_secondary="#252525",
            text_primary="#FFFFFF",
            text_secondary="#CCCCCC",
            text_disabled="#666666",
            accent="#007ACC",
            accent_hover="#1E8AD6",
            accent_pressed="#005A9E",
            # ... all other colors ...
        )

    def get_stylesheet(self) -> str:
        palette = self.get_palette()
        return f"""
            QMainWindow {{
                background-color: {palette.background};
                color: {palette.text_primary};
            }}
            /* ... rest of stylesheet ... */
        """

# Register theme
from .my_theme import MyTheme
theme_manager.register_theme("My Theme", MyTheme())
```

### Modifying Existing Theme Colors

```python
# themes/dark_theme.py
class DarkTheme(Theme):
    def get_palette(self) -> ColorPalette:
        return ColorPalette(
            accent="#3B7DD6",  # Change from blue to custom color
            # ... rest of colors ...
        )
```

### Using Theme Colors in Widgets

```python
class MyWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Get current theme
        theme_manager = get_theme_manager()
        theme = theme_manager.get_current_theme()
        palette = theme.get_palette()

        # Use theme colors
        self.setStyleSheet(f"""
            MyWidget {{
                background-color: {palette.card_background};
                border: 1px solid {palette.card_border};
            }}
        """)

        # Listen for theme changes
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme_name: str):
        # Reload colors when theme changes
        theme = get_theme_manager().get_current_theme()
        palette = theme.get_palette()
        # Update widget styling...
```

---

## Widget Development

### Creating a New Widget

```python
# widgets/my_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal

from ..events.event_bus import get_event_bus
from ..themes.theme_manager import get_theme_manager

class MyWidget(QWidget):
    """
    Description of widget purpose

    Features:
    - Feature 1
    - Feature 2
    - Feature 3

    Signals:
    - some_event_happened(data: str)

    Usage:
        widget = MyWidget()
        widget.some_event_happened.connect(handler)
    """

    # Define signals
    some_event_happened = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Get services
        self._event_bus = get_event_bus()

        # Setup UI
        self._create_widgets()
        self._create_layout()
        self._connect_signals()

    def _create_widgets(self):
        """Create child widgets"""
        # Use theme colors
        theme = get_theme_manager().get_current_theme()
        palette = theme.get_palette()

        self._button = QPushButton("Click Me")
        self._button.setStyleSheet(f"""
            QPushButton {{
                background-color: {palette.accent};
                color: white;
            }}
        """)

    def _create_layout(self):
        """Create layout"""
        layout = QVBoxLayout(self)
        layout.addWidget(self._button)

    def _connect_signals(self):
        """Connect internal signals"""
        self._button.clicked.connect(self._on_button_clicked)

        # Connect to event bus
        self._event_bus.some_event.connect(self._on_some_event)

    def _on_button_clicked(self):
        """Handle button click"""
        self.some_event_happened.emit("Button clicked!")

    def _on_some_event(self, data):
        """Handle event from event bus"""
        print(f"Received: {data}")

# Export in widgets/__init__.py
from .my_widget import MyWidget
__all__ = ['MyWidget', ...]
```

### Widget Best Practices

1. **Comprehensive Docstrings**
   - Describe purpose and features
   - List signals and slots
   - Provide usage example
   - Include ASCII diagram for complex layouts

2. **Separation of Concerns**
   - `_create_widgets()` - Create child widgets
   - `_create_layout()` - Build layout
   - `_connect_signals()` - Wire up signals
   - Handler methods start with `_on_`

3. **Theme Colors**
   - Never hard-code colors
   - Always use `ThemeManager.get_current_theme().palette`
   - Listen to `theme_changed` signal

4. **Event Bus Usage**
   - Use for cross-widget communication
   - Keeps widgets loosely coupled
   - Makes testing easier

5. **Performance**
   - Debounce expensive operations
   - Use `blockSignals()` when updating multiple widgets
   - Virtual scrolling for lists

---

## Database Operations

### Adding a Service Method

```python
# services/database_service.py
def my_custom_query(self, param: str) -> List[Dict[str, Any]]:
    """
    Description of what this query does

    Args:
        param: Parameter description

    Returns:
        List of result dictionaries
    """
    try:
        conn = self._get_connection()
        cursor = conn.cursor()

        # Use parameterized queries (prevents SQL injection)
        cursor.execute('''
            SELECT * FROM animations
            WHERE name LIKE ?
            ORDER BY created_date DESC
        ''', (f'%{param}%',))

        results = []
        for row in cursor.fetchall():
            data = dict(row)
            # Deserialize JSON fields
            if data.get('tags'):
                data['tags'] = json.loads(data['tags'])
            results.append(data)

        return results
    except Exception as e:
        print(f"Error in my_custom_query: {e}")
        return []
```

### Database Migrations

```python
# Increment schema version
SCHEMA_VERSION = 3

def initialize(self):
    # ... existing code ...
    if current_version < 3:
        self._migrate_to_v3(cursor)

def _migrate_to_v3(self, cursor: sqlite3.Cursor):
    """Migrate database from v2 to v3"""
    print("[DatabaseService] Migrating database to v3...")

    try:
        # Add new columns
        cursor.execute('ALTER TABLE animations ADD COLUMN new_field TEXT')

        # Create new tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_table (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
        ''')

        # Migrate existing data if needed
        cursor.execute('UPDATE animations SET new_field = "default"')

        # Create indexes
        cursor.execute('CREATE INDEX idx_new_field ON animations(new_field)')

        print("[DatabaseService] Migration to v3 complete")
    except Exception as e:
        print(f"[DatabaseService] Migration error: {e}")
        raise
```

### Working with Nested Folders

**Creating Folder Hierarchy:**
```python
from animation_library.services.database_service import get_database_service

db = get_database_service()

# Get root folder ID
root_id = db.get_root_folder_id()

# Create top-level folder
body_id = db.create_folder("Body Mechanics", parent_id=root_id)

# Create nested folder (child of Body Mechanics)
walk_id = db.create_folder("Walk Cycles", parent_id=body_id)

# Create deeply nested folder
realistic_id = db.create_folder("Realistic", parent_id=walk_id)
```

**Moving Folders in Hierarchy:**
```python
# Move folder to different parent (creates new hierarchy)
success = db.update_folder_parent(walk_id, locomotion_id)

# Move folder to root level
success = db.update_folder_parent(combat_id, root_id)
```

**Getting Folder Descendants (Recursive):**
```python
# Get all nested folder IDs under "Body Mechanics"
descendant_ids = db.get_folder_descendants(body_id)
# Returns: [body_id, walk_id, run_id, realistic_id, stylized_id, ...]

# Use for recursive filtering
animations = []
for folder_id in descendant_ids:
    folder_anims = db.get_animations_by_folder(folder_id)
    animations.extend(folder_anims)
```

**Preventing Circular References:**
```python
# Check if target is descendant of source (prevents circular refs)
from animation_library.widgets.folder_tree import FolderTree

tree = FolderTree()
is_circular = tree._is_descendant(target_id, source_id)

if is_circular:
    print("Cannot move folder into its own subfolder!")
```

**Folder Drag & Drop Integration:**
```python
# FolderTree automatically handles drag-drop via Qt events

# dragEnterEvent: Accepts both MIME types
if (mime_data.hasFormat('application/x-animation-uuid') or
    mime_data.hasFormat('application/x-qabstractitemmodeldatalist')):
    event.acceptProposedAction()

# dropEvent: Handles folder-to-folder moves
if self._move_folder_to_folder(source_item, target_item):
    # Database updated, tree reloaded automatically
    pass
```

**Important: Extract Data Before Tree Reload!**
```python
# ❌ WRONG - Crashes after tree reload
if db.update_folder_parent(source_id, target_id):
    self._load_folders()  # Deletes all QTreeWidgetItems
    name = source_item.text(0)  # CRASH! Item already deleted

# ✅ CORRECT - Extract first, then reload
name = source_item.text(0)  # Extract BEFORE reload
if db.update_folder_parent(source_id, target_id):
    self._load_folders()  # Safe - name already extracted
    print(f"Moved {name}")
```

---

## Testing

### Manual Testing Checklist

**Theme Testing**:
- [ ] Switch between all themes
- [ ] Verify all colors update correctly
- [ ] Check icon colorization
- [ ] Test hover/pressed states

**Database Testing**:
- [ ] Test with empty database
- [ ] Test with 1000+ animations
- [ ] Test database migration
- [ ] Test concurrent access

**UI Testing**:
- [ ] Grid mode rendering
- [ ] List mode rendering
- [ ] Multi-selection
- [ ] Drag & drop
- [ ] Folder navigation
- [ ] Search filtering
- [ ] Sorting

**Performance Testing**:
- [ ] Scrolling with 1000+ items
- [ ] Thumbnail loading time
- [ ] Theme switch performance
- [ ] Search response time

### Unit Test Example (Future)

```python
# tests/test_database_service.py
import unittest
from animation_library.services.database_service import DatabaseService

class TestDatabaseService(unittest.TestCase):
    def setUp(self):
        """Create test database"""
        self.db = DatabaseService()
        self.db.initialize(":memory:")  # In-memory DB for testing

    def test_toggle_favorite(self):
        """Test favorite toggle"""
        # Create test animation
        anim_id = self.db.create_animation({
            'uuid': 'test-uuid',
            'name': 'Test Animation',
            'is_favorite': 0
        })

        # Toggle favorite
        result = self.db.toggle_favorite('test-uuid')
        self.assertTrue(result)

        # Verify favorite status
        anim = self.db.get_animation_by_uuid('test-uuid')
        self.assertEqual(anim['is_favorite'], 1)

        # Toggle again
        self.db.toggle_favorite('test-uuid')
        anim = self.db.get_animation_by_uuid('test-uuid')
        self.assertEqual(anim['is_favorite'], 0)
```

---

## Best Practices

### Code Style

1. **Follow PEP 8**
   - 4 spaces for indentation
   - Max line length: 100 characters
   - Use type hints
   - Docstrings for all public methods

2. **Naming Conventions**
   - Classes: `PascalCase`
   - Functions/methods: `snake_case`
   - Private methods: `_snake_case`
   - Constants: `UPPER_SNAKE_CASE`
   - Qt signals: `snake_case`

3. **Import Organization**
   ```python
   # Standard library
   import json
   from pathlib import Path

   # Third-party
   from PyQt6.QtWidgets import QWidget
   from PyQt6.QtCore import pyqtSignal

   # Local application
   from ..services.database_service import get_database_service
   from ..themes.theme_manager import get_theme_manager
   ```

### Performance Guidelines

1. **Use Virtual Scrolling**
   - For lists with 100+ items
   - Set uniform item sizes
   - Implement custom delegates

2. **Debounce Expensive Operations**
   ```python
   from PyQt6.QtCore import QTimer

   class MyWidget(QWidget):
       def __init__(self):
           super().__init__()
           self._debounce_timer = QTimer()
           self._debounce_timer.setSingleShot(True)
           self._debounce_timer.timeout.connect(self._do_expensive_operation)

       def on_user_input(self, text):
           # Restart timer on each input
           self._debounce_timer.stop()
           self._debounce_timer.start(300)  # 300ms delay

       def _do_expensive_operation(self):
           # This only runs after user stops typing for 300ms
           pass
   ```

3. **Cache Expensive Computations**
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=128)
   def expensive_calculation(param):
       # Result is cached for repeated calls with same param
       return complex_computation(param)
   ```

### Security Guidelines

1. **SQL Injection Prevention**
   ```python
   # GOOD: Parameterized query
   cursor.execute('SELECT * FROM animations WHERE name = ?', (name,))

   # BAD: String concatenation
   cursor.execute(f'SELECT * FROM animations WHERE name = "{name}"')
   ```

2. **Path Validation**
   ```python
   from pathlib import Path

   def safe_path(user_input: str) -> Path:
       path = Path(user_input).resolve()
       # Verify path is within allowed directory
       if not path.is_relative_to(Config.get_library_path()):
           raise ValueError("Invalid path")
       return path
   ```

---

## Common Tasks

### Task: Add a New Filter Option

```python
# 1. Add filter state to proxy model
class AnimationFilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self._my_filter = None

    def set_my_filter(self, value):
        if self._my_filter != value:
            self._my_filter = value
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        # ... existing filters ...

        # Add new filter logic
        if self._my_filter is not None:
            my_value = source_model.data(index, MyRole)
            if my_value != self._my_filter:
                return False

        return True

# 2. Add UI control
class HeaderToolbar(QWidget):
    my_filter_changed = pyqtSignal(str)

    def _create_widgets(self):
        self._my_filter_combo = QComboBox()
        self._my_filter_combo.addItems(["All", "Option1", "Option2"])
        self._my_filter_combo.currentTextChanged.connect(
            self.my_filter_changed.emit
        )

# 3. Wire up in main window
class MainWindow(QMainWindow):
    def __init__(self):
        # ... existing code ...
        self._header_toolbar.my_filter_changed.connect(
            self._on_my_filter_changed
        )

    def _on_my_filter_changed(self, value):
        if value == "All":
            self._proxy_model.set_my_filter(None)
        else:
            self._proxy_model.set_my_filter(value)
```

### Task: Add a New Metadata Field

```python
# 1. Update database
def _create_schema(self, cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS animations (
            -- ... existing fields ...
            my_field TEXT,  -- NEW
        )
    ''')

# 2. Add migration
def _migrate_to_vX(self, cursor):
    cursor.execute('ALTER TABLE animations ADD COLUMN my_field TEXT')

# 3. Add to model roles
class AnimationRole(IntEnum):
    MyFieldRole = Qt.ItemDataRole.UserRole + 75

def data(self, index, role):
    elif role == AnimationRole.MyFieldRole:
        return animation.get('my_field', '')

# 4. Display in metadata panel
class MetadataPanel(QWidget):
    def _update_metadata_display(self, animation_data):
        # ... existing fields ...
        my_field = animation_data.get('my_field', 'N/A')
        self._my_field_label.setText(f"My Field: {my_field}")
```

### Task: Organize Folders with Drag & Drop

**Programmatically Move Folders:**
```python
from animation_library.services.database_service import get_database_service

db = get_database_service()

# Move "Walk Cycles" into "Locomotion" folder
walk_id = 42
locomotion_id = 15
success = db.update_folder_parent(walk_id, locomotion_id)

# Move folder to root level
root_id = db.get_root_folder_id()
success = db.update_folder_parent(combat_id, root_id)

# Rebuild tree to show changes
from animation_library.widgets.folder_tree import FolderTree
tree = FolderTree()
tree.refresh()
```

**UI Drag & Drop (Automatic):**
```python
# Users can drag folders in the UI:
# 1. Click and hold on folder
# 2. Drag to target folder (or empty space for root)
# 3. Release to drop
# FolderTree handles all validation and database updates automatically
```

**Check Folder Hierarchy:**
```python
# Get all folders under "Body Mechanics" (recursive)
body_id = 10
descendants = db.get_folder_descendants(body_id)
print(f"Body Mechanics has {len(descendants)-1} nested folders")

# Check if folder can be moved (prevent circular refs)
from animation_library.widgets.folder_tree import FolderTree
tree = FolderTree()
if tree._is_descendant(target_id, source_id):
    print("Cannot move! Would create circular reference")
```

### Task: Add a Keyboard Shortcut

```python
# widgets/main_window.py
from PyQt6.QtGui import QKeySequence, QAction

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Refresh library
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self._load_animations)
        self.addAction(refresh_action)

        # Toggle favorites filter
        favorites_action = QAction("Favorites", self)
        favorites_action.setShortcut(QKeySequence("Ctrl+F"))
        favorites_action.triggered.connect(self._show_favorites)
        self.addAction(favorites_action)
```

---

## Debugging Tips

### Enable Debug Logging

```python
# config.py
class Config:
    ENABLE_PERFORMANCE_LOGGING = True  # Enable performance logs
    ENABLE_DEBUG_MODE = True           # Enable debug output
```

### Qt Inspector

```python
# Add to main.py for debugging UI
from PyQt6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
app.setStyleSheet("*{ border: 1px solid red; }")  # Show all widget borders
```

### Database Inspection

```bash
# Use DB Browser for SQLite
# Download: https://sqlitebrowser.org/
# Open: data/animation_library_v2.db
```

### Common Issues

**Issue**: Theme not applying
- **Solution**: Call `style().polish(widget)` after setting property

**Issue**: Signal not firing
- **Solution**: Check signal is connected before emitting

**Issue**: Database locked
- **Solution**: Close all connections, use `with self.transaction()`

**Issue**: Pixmap not displaying
- **Solution**: Check pixmap is not null, verify file path exists

---

## Resources

### Official Documentation
- **PyQt6**: https://www.riverbankcomputing.com/static/Docs/PyQt6/
- **Qt 6**: https://doc.qt.io/qt-6/
- **SQLite**: https://www.sqlite.org/docs.html
- **Python**: https://docs.python.org/3/

### Tutorials
- Qt Model/View: https://doc.qt.io/qt-6/model-view-programming.html
- Qt Stylesheets: https://doc.qt.io/qt-6/stylesheet.html
- Qt Signals & Slots: https://doc.qt.io/qt-6/signalsandslots.html

### Tools
- **Qt Designer**: UI prototyping
- **DB Browser for SQLite**: Database inspection
- **Black**: Python code formatter
- **Pylint**: Code linter

---

## Getting Help

1. **Check Documentation**
   - Read `ARCHITECTURE.md`
   - Check widget docstrings
   - Review `WIDGET_REFERENCE.md`

2. **Search Codebase**
   - Look for similar implementations
   - Check how existing features work
   - Follow the patterns

3. **Ask Questions**
   - Open GitHub issue
   - Include error messages
   - Provide code samples
   - Describe expected vs actual behavior

---

## Contributing

When contributing new features:

1. Follow existing code style
2. Add comprehensive docstrings
3. Use type hints
4. Update documentation
5. Test with multiple themes
6. Test with large datasets
7. Verify performance

Happy coding! 🚀
