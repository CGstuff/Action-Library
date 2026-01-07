"""
MainWindow - Main application window

Pattern: QMainWindow with splitter layout
Inspired by: Current animation_library structure
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QCloseEvent

from ..config import Config
from ..events.event_bus import get_event_bus
from ..services.database_service import get_database_service
from ..services.blender_service import get_blender_service
from ..services.archive_service import get_archive_service
from ..services.trash_service import get_trash_service
from ..themes.theme_manager import get_theme_manager
from ..models.animation_list_model import AnimationListModel
from ..models.animation_filter_proxy_model import AnimationFilterProxyModel
from ..views.animation_view import AnimationView
from .header_toolbar import HeaderToolbar
from .folder_tree import FolderTree
from .metadata_panel import MetadataPanel
from .apply_panel import ApplyPanel
from .bulk_edit_toolbar import BulkEditToolbar
from .settings.settings_dialog import SettingsDialog
from .controllers import ArchiveTrashController, BulkEditController, FilterController


class MainWindow(QMainWindow):
    """
    Main application window

    Features:
    - 3-panel layout (folder tree, animation grid, metadata panel)
    - Splitter with persistent state
    - Header toolbar with search and controls
    - Bulk edit toolbar (shown in edit mode)
    - Status bar
    - Window state persistence
    - Event bus integration

    Layout:
        +------------------------------------------+
        |  HeaderToolbar                           |
        +------------------------------------------+
        |  BulkEditToolbar (edit mode only)        |
        +------------------------------------------+
        | FolderTree | AnimationView | Metadata   |
        |            |               | Panel       |
        |            |               |             |
        +------------------------------------------+
        |  StatusBar                               |
        +------------------------------------------+
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Check if first run and show setup wizard
        if Config.is_first_run():
            from .dialogs.setup_wizard import SetupWizard
            wizard = SetupWizard()
            if wizard.exec() != QDialog.DialogCode.Accepted:
                # User cancelled setup
                sys.exit(0)

        # Services and event bus
        self._event_bus = get_event_bus()
        self._db_service = get_database_service()
        self._blender_service = get_blender_service()
        self._archive_service = get_archive_service()
        self._trash_service = get_trash_service()

        # Models
        self._animation_model = AnimationListModel()
        self._proxy_model = AnimationFilterProxyModel()
        self._proxy_model.setSourceModel(self._animation_model)

        # Setup window
        self._setup_window()
        self._create_widgets()
        self._create_layout()
        self._init_controllers()
        self._connect_signals()
        self._load_settings()
        self._load_animations()

    def _setup_window(self):
        """Configure window properties"""

        self.setWindowTitle(f"{Config.APP_NAME} {Config.APP_VERSION}")
        self.setGeometry(100, 100, Config.DEFAULT_WINDOW_WIDTH, Config.DEFAULT_WINDOW_HEIGHT)

    def _create_widgets(self):
        """Create UI widgets"""

        # Header toolbar
        self._header_toolbar = HeaderToolbar()

        # Bulk edit toolbar (hidden by default)
        self._bulk_edit_toolbar = BulkEditToolbar()
        self._bulk_edit_toolbar.hide()

        # Folder tree (left panel)
        self._folder_tree = FolderTree()

        # Animation view (center panel)
        self._animation_view = AnimationView()
        self._animation_view.setModel(self._proxy_model)

        # Metadata panel (right panel)
        self._metadata_panel = MetadataPanel()

        # Apply panel (below metadata)
        self._apply_panel = ApplyPanel()

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def _create_layout(self):
        """Create window layout"""

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Add header toolbar
        main_layout.addWidget(self._header_toolbar)

        # Add bulk edit toolbar
        main_layout.addWidget(self._bulk_edit_toolbar)

        # Create horizontal splitter for 3-panel layout
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Right panel container (metadata + apply panel stacked vertically)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._metadata_panel, 1)  # Stretchy
        right_layout.addWidget(self._apply_panel, 0)     # Fixed

        # Add panels to splitter
        self._splitter.addWidget(self._folder_tree)
        self._splitter.addWidget(self._animation_view)
        self._splitter.addWidget(right_panel)

        # Set initial splitter sizes (from config)
        self._splitter.setSizes(Config.DEFAULT_SPLITTER_SIZES)

        # Set stretch factors (center panel gets most space)
        self._splitter.setStretchFactor(0, 0)  # Folder tree: fixed-ish
        self._splitter.setStretchFactor(1, 1)  # Animation view: stretchy
        self._splitter.setStretchFactor(2, 0)  # Metadata: fixed-ish

        # Add splitter to layout
        main_layout.addWidget(self._splitter, 1)

    def _init_controllers(self):
        """Initialize controllers for delegated functionality"""

        # Filter controller - manages proxy model interactions
        self._filter_ctrl = FilterController(self._proxy_model, self._status_bar)

        # Archive/Trash controller - manages special views
        self._archive_trash_ctrl = ArchiveTrashController(
            parent=self,
            animation_model=self._animation_model,
            animation_view=self._animation_view,
            metadata_panel=self._metadata_panel,
            proxy_model=self._proxy_model,
            db_service=self._db_service,
            archive_service=self._archive_service,
            trash_service=self._trash_service,
            event_bus=self._event_bus,
            status_bar=self._status_bar,
            reload_animations_callback=self._reload_animations_from_db
        )

        # Bulk edit controller - manages bulk operations
        self._bulk_edit_ctrl = BulkEditController(
            parent=self,
            animation_view=self._animation_view,
            animation_model=self._animation_model,
            db_service=self._db_service,
            event_bus=self._event_bus,
            status_bar=self._status_bar,
            reload_animations_callback=self._reload_animations_from_db
        )

    def _reload_animations_from_db(self):
        """Reload all animations from database - used by controllers"""
        animations = self._db_service.get_all_animations()
        self._animation_model.set_animations(animations)

    def _connect_signals(self):
        """Connect signals and slots"""

        # Folder tree selection -> filter animations
        self._folder_tree.folder_selected.connect(self._on_folder_selected)

        # Folder tree archive/trash actions
        self._folder_tree.empty_archive_requested.connect(self._on_empty_archive)
        self._folder_tree.empty_trash_requested.connect(self._on_empty_trash)

        # Animation view selection -> update metadata panel
        self._animation_view.selectionModel().selectionChanged.connect(
            self._on_animation_selection_changed
        )

        # Animation view selection -> update event bus (for bulk toolbar)
        self._animation_view.selectionModel().selectionChanged.connect(
            self._animation_view._on_selection_changed
        )

        # Animation view double-click -> apply animation
        self._animation_view.animation_double_clicked.connect(self._on_animation_double_clicked)

        # Header toolbar search -> filter animations
        self._header_toolbar.search_text_changed.connect(self._on_search_text_changed)

        # Header toolbar view mode -> update view
        self._header_toolbar.view_mode_changed.connect(self._animation_view.set_view_mode)

        # Header toolbar card size -> update view
        self._header_toolbar.card_size_changed.connect(self._animation_view.set_card_size)

        # Header toolbar edit mode -> show/hide bulk toolbar
        self._header_toolbar.edit_mode_changed.connect(self._on_edit_mode_changed)

        # Header toolbar archive -> archive selected animations (soft delete)
        self._header_toolbar.delete_clicked.connect(self._on_archive_clicked)

        # Apply panel -> apply animation with options
        self._apply_panel.apply_clicked.connect(self._on_apply_with_options)

        # Header toolbar refresh -> sync library with database
        self._header_toolbar.refresh_library_clicked.connect(self._on_refresh_library)

        # Header toolbar new folder -> create folder dialog
        self._header_toolbar.new_folder_clicked.connect(self._on_create_folder)

        # Header toolbar settings -> show settings dialog
        self._header_toolbar.settings_clicked.connect(self._show_settings)

        # Header toolbar filters -> filter animations
        self._header_toolbar.rig_type_filter_changed.connect(
            lambda rig_types: self._proxy_model.set_rig_type_filter(set(rig_types))
        )
        self._header_toolbar.tags_filter_changed.connect(
            lambda tags: self._proxy_model.set_tag_filter(set(tags))
        )
        self._header_toolbar.sort_changed.connect(self._on_sort_changed)

        # Bulk edit toolbar signals
        self._bulk_edit_toolbar.remove_tags_clicked.connect(self._on_remove_tags)
        self._bulk_edit_toolbar.move_to_folder_clicked.connect(self._on_move_to_folder)
        self._bulk_edit_toolbar.gradient_preset_selected.connect(self._on_gradient_preset_selected)
        self._bulk_edit_toolbar.custom_gradient_clicked.connect(self._on_custom_gradient_clicked)
        self._bulk_edit_toolbar.restore_clicked.connect(self._on_restore_clicked)

        # Event bus signals
        self._event_bus.loading_started.connect(self._on_loading_started)
        self._event_bus.loading_finished.connect(self._on_loading_finished)
        self._event_bus.error_occurred.connect(self._on_error)
        self._event_bus.folder_changed.connect(self._on_folder_changed)

    def _load_settings(self):
        """Load window and splitter settings"""

        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)

        # Window geometry
        if settings.contains("window/geometry"):
            self.restoreGeometry(settings.value("window/geometry"))

        # Window state
        if settings.contains("window/state"):
            self.restoreState(settings.value("window/state"))

        # Splitter sizes
        if settings.contains("splitter/sizes"):
            sizes = settings.value("splitter/sizes")
            if sizes:
                # Convert to integers (QSettings may return strings)
                try:
                    sizes = [int(s) for s in sizes]
                    self._splitter.setSizes(sizes)
                except (ValueError, TypeError):
                    # If conversion fails, use defaults
                    self._splitter.setSizes(Config.DEFAULT_SPLITTER_SIZES)

    def _save_settings(self):
        """Save window and splitter settings"""

        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)

        # Window geometry
        settings.setValue("window/geometry", self.saveGeometry())

        # Window state
        settings.setValue("window/state", self.saveState())

        # Splitter sizes
        settings.setValue("splitter/sizes", self._splitter.sizes())

    def _load_animations(self):
        """Load animations from database, auto-sync if needed"""
        from ..services.backup_service import BackupService

        self._event_bus.start_loading("Loading animations")

        # Check if database is empty - if so, auto-sync with library folder
        if self._db_service.get_animation_count() == 0:
            self._status_bar.showMessage("Scanning library...")
            self._db_service.sync_library()

        # Apply any pending metadata from import
        if BackupService.has_pending_metadata():
            self._status_bar.showMessage("Restoring metadata...")
            BackupService.apply_pending_metadata()

        # Get all animations from database
        animations = self._db_service.get_all_animations()

        # Load into model
        self._animation_model.set_animations(animations)

        # Update status
        count = len(animations)
        self._status_bar.showMessage(f"Loaded {count} animations")

        self._event_bus.finish_loading("Loading animations")

    def _show_settings(self):
        """Show settings dialog"""
        theme_manager = get_theme_manager()
        dialog = SettingsDialog(theme_manager, self)
        dialog.exec()

    # ==================== SLOT HANDLERS ====================

    def _on_folder_selected(self, folder_id: int, folder_name: str, recursive: bool = True):
        """Handle folder selection with optional recursive filtering"""

        # Clear special filters first
        self._filter_ctrl.clear_special_filters()

        if folder_name == "Archive":
            self._archive_trash_ctrl.show_archive_view()
            self._bulk_edit_toolbar.set_special_view_mode(in_archive=True)
            return
        elif folder_name == "Trash":
            self._archive_trash_ctrl.show_trash_view()
            self._bulk_edit_toolbar.set_special_view_mode(in_trash=True)
            return

        # Exit special views if we were in archive/trash
        self._archive_trash_ctrl.exit_special_views()
        self._bulk_edit_toolbar.set_special_view_mode()  # Reset to normal mode

        if folder_name == "All Animations":
            self._filter_ctrl.clear_folder_filter()
        elif folder_name == "Favorites":
            self._filter_ctrl.clear_folder_filter()
            self._filter_ctrl.set_favorites_only(True)
        elif folder_name == "Recent":
            self._filter_ctrl.clear_folder_filter()
            self._filter_ctrl.set_recent_only(True)
        else:
            # Filter by folder name (tags-based)
            self._filter_ctrl.set_folder_filter(folder_id, folder_name, set())

        self._filter_ctrl.update_status(folder_name)

    def _on_animation_selection_changed(self, selected, deselected):
        """Handle animation selection change"""

        selected_indexes = self._animation_view.selectionModel().selectedIndexes()

        if selected_indexes:
            # Get first selected animation
            index = selected_indexes[0]
            source_index = self._proxy_model.mapToSource(index)
            animation = self._animation_model.get_animation_at_index(source_index.row())

            if animation:
                # Update metadata panel
                self._metadata_panel.set_animation(animation)

                # Update apply panel
                self._apply_panel.set_animation(animation)

                # Update status
                name = animation.get('name', 'Unknown')
                self._status_bar.showMessage(f"Selected: {name}")
        else:
            # Clear metadata panel
            self._metadata_panel.clear()

            # Clear apply panel
            self._apply_panel.clear()

            self._status_bar.showMessage("Ready")

    def _on_animation_double_clicked(self, uuid: str):
        """Handle animation double-click - Immediately apply to Blender with options"""

        animation = self._animation_model.get_animation_by_uuid(uuid)
        if not animation:
            return

        name = animation.get('name', 'Unknown')

        # Get options from apply panel
        options = self._apply_panel.get_options()

        # Queue animation for Blender with options
        success = self._blender_service.queue_apply_animation(uuid, name, options)

        if success:
            self._status_bar.showMessage(f"Applied '{name}' to Blender")
        else:
            self._status_bar.showMessage(f"Failed to apply '{name}'")
            self._event_bus.report_error("blender", f"Failed to apply animation '{name}'")

    def _on_search_text_changed(self, text: str):
        """Handle search text change"""
        self._filter_ctrl.set_search_text(text)

    def _on_sort_changed(self, sort_by: str, sort_order: str):
        """Handle sort option change from toolbar"""
        self._filter_ctrl.set_sort_config(sort_by, sort_order)

    def _on_edit_mode_changed(self, enabled: bool):
        """Handle edit mode toggle"""

        if enabled:
            self._bulk_edit_toolbar.show()
        else:
            self._bulk_edit_toolbar.hide()

    def _on_archive_clicked(self):
        """Handle archive button click - context-aware action based on current view"""
        self._archive_trash_ctrl.handle_delete_action()

    def _on_restore_clicked(self):
        """Handle restore button click in bulk edit toolbar"""
        if self._archive_trash_ctrl.in_archive_view:
            self._archive_trash_ctrl.restore_from_archive()
        elif self._archive_trash_ctrl.in_trash_view:
            self._archive_trash_ctrl.restore_to_archive()

    def _on_apply_with_options(self, options: dict):
        """Handle apply from apply panel button - Apply current animation with options"""

        animation = self._apply_panel.get_current_animation()
        if not animation:
            self._status_bar.showMessage("No animation selected")
            return

        uuid = animation.get('uuid')
        name = animation.get('name', 'Unknown')

        # Queue animation for Blender with options
        success = self._blender_service.queue_apply_animation(uuid, name, options)

        if success:
            self._status_bar.showMessage(f"Applied '{name}' to Blender")
        else:
            self._status_bar.showMessage(f"Failed to apply '{name}'")
            self._event_bus.report_error("blender", f"Failed to apply animation '{name}'")

    def _on_refresh_library(self):
        """Handle refresh library button click - sync database with library folder"""
        from ..services.backup_service import BackupService

        self._event_bus.start_loading("Scanning library")
        self._status_bar.showMessage("Scanning library folder...")

        # Sync library with database
        total_found, newly_imported = self._db_service.sync_library()

        # Apply any pending metadata from import
        metadata_applied = 0
        if BackupService.has_pending_metadata():
            self._status_bar.showMessage("Applying imported metadata...")
            stats = BackupService.apply_pending_metadata()
            metadata_applied = stats.get('updated', 0)

        # Reload animations from database
        animations = self._db_service.get_all_animations()
        self._animation_model.set_animations(animations)

        # Refresh filter dropdowns (rig types, tags)
        self._header_toolbar.refresh_filters()

        # Refresh folder tree to show any new folders
        self._folder_tree.refresh()

        # Update status
        status_parts = [f"{total_found} animations found"]
        if newly_imported > 0:
            status_parts.append(f"{newly_imported} newly imported")
        if metadata_applied > 0:
            status_parts.append(f"{metadata_applied} metadata restored")

        self._status_bar.showMessage(f"Library refresh complete: {', '.join(status_parts)}")

        self._event_bus.finish_loading("Scanning library")

    def _on_create_folder(self):
        """Handle create new folder request from header button"""
        # Delegate to folder tree widget
        self._folder_tree.create_folder_with_dialog()

    def _on_remove_tags(self):
        """Handle remove tags from selected animations"""
        self._bulk_edit_ctrl.remove_tags()

    def _on_gradient_preset_selected(self, name: str, top_color: tuple, bottom_color: tuple):
        """Handle gradient preset selection from dropdown"""
        self._bulk_edit_ctrl.apply_gradient_preset(name, top_color, bottom_color)

    def _on_custom_gradient_clicked(self):
        """Handle custom gradient selection - opens color picker dialog"""
        self._bulk_edit_ctrl.apply_custom_gradient()

    def _on_move_to_folder(self):
        """Handle move selected animations to folder"""
        self._bulk_edit_ctrl.move_to_folder()

    def _on_loading_started(self, operation: str):
        """Handle loading started"""
        self._status_bar.showMessage(f"{operation}...")

    def _on_loading_finished(self, operation: str):
        """Handle loading finished"""
        count = self._proxy_model.rowCount()
        self._status_bar.showMessage(f"{count} animations")

    def _on_error(self, error_type: str, error_message: str):
        """Handle error"""
        self._status_bar.showMessage(f"Error: {error_message}")

    def _on_folder_changed(self, folder_id: int):
        """Handle animations moved to different folder"""
        # Reload ALL animations from database to get updated tags
        self._reload_animations_from_db()

        # If the changed folder is currently selected, keep it selected
        selected_items = self._folder_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                folder_name = data.get('folder_name')
                # Reapply current filter
                if folder_name == "All Animations":
                    self._filter_ctrl.clear_folder_filter()
                else:
                    folder_item_id = data.get('folder_id')
                    if folder_item_id:
                        self._filter_ctrl.set_folder_filter(folder_item_id, folder_name, None)

    # ==================== ARCHIVE/TRASH OPERATIONS (delegated to controller) ====================

    def _on_empty_archive(self):
        """Handle empty archive action - delegate to controller"""
        self._archive_trash_ctrl.empty_archive()

    def _on_empty_trash(self):
        """Handle empty trash action - delegate to controller"""
        self._archive_trash_ctrl.empty_trash()

    # ==================== EVENTS ====================

    def closeEvent(self, event: QCloseEvent):
        """Handle window close"""

        # Save settings
        self._save_settings()

        # Accept close
        event.accept()


__all__ = ['MainWindow']
