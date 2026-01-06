"""
MainWindow - Main application window

Pattern: QMainWindow with splitter layout
Inspired by: Current animation_library structure
"""

import shutil
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
from ..themes.theme_manager import get_theme_manager
from ..models.animation_list_model import AnimationListModel
from ..models.animation_filter_proxy_model import AnimationFilterProxyModel
from ..views.animation_view import AnimationView
from .header_toolbar import HeaderToolbar
from .folder_tree import FolderTree
from .metadata_panel import MetadataPanel
from .bulk_edit_toolbar import BulkEditToolbar
from .settings.settings_dialog import SettingsDialog


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

        # Models
        self._animation_model = AnimationListModel()
        self._proxy_model = AnimationFilterProxyModel()
        self._proxy_model.setSourceModel(self._animation_model)

        # Setup window
        self._setup_window()
        self._create_widgets()
        self._create_layout()
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

        # Add panels to splitter
        self._splitter.addWidget(self._folder_tree)
        self._splitter.addWidget(self._animation_view)
        self._splitter.addWidget(self._metadata_panel)

        # Set initial splitter sizes (from config)
        self._splitter.setSizes(Config.DEFAULT_SPLITTER_SIZES)

        # Set stretch factors (center panel gets most space)
        self._splitter.setStretchFactor(0, 0)  # Folder tree: fixed-ish
        self._splitter.setStretchFactor(1, 1)  # Animation view: stretchy
        self._splitter.setStretchFactor(2, 0)  # Metadata: fixed-ish

        # Add splitter to layout
        main_layout.addWidget(self._splitter, 1)

    def _connect_signals(self):
        """Connect signals and slots"""

        # Folder tree selection -> filter animations
        self._folder_tree.folder_selected.connect(self._on_folder_selected)

        # Animation view selection -> update metadata panel
        self._animation_view.selectionModel().selectionChanged.connect(
            self._on_animation_selection_changed
        )

        # Animation view selection -> update event bus (for bulk toolbar)
        self._animation_view.selectionModel().selectionChanged.connect(
            self._animation_view._on_selection_changed
        )

        # Animation view double-click -> apply animation (TODO: Phase 6)
        self._animation_view.animation_double_clicked.connect(self._on_animation_double_clicked)

        # Header toolbar search -> filter animations
        self._header_toolbar.search_text_changed.connect(self._on_search_text_changed)

        # Header toolbar view mode -> update view
        self._header_toolbar.view_mode_changed.connect(self._animation_view.set_view_mode)

        # Header toolbar card size -> update view
        self._header_toolbar.card_size_changed.connect(self._animation_view.set_card_size)

        # Header toolbar edit mode -> show/hide bulk toolbar
        self._header_toolbar.edit_mode_changed.connect(self._on_edit_mode_changed)

        # Header toolbar delete -> delete selected animations
        self._header_toolbar.delete_clicked.connect(self._on_delete_clicked)

        # Header toolbar apply -> apply selected animation to Blender
        self._header_toolbar.apply_clicked.connect(self._on_apply_clicked)

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
        self._proxy_model.set_favorites_only(False)
        self._proxy_model.set_recent_only(False)

        if folder_name == "All Animations":
            # Show all animations
            self._proxy_model.set_folder_filter(None, None, None)
        elif folder_name == "Favorites":
            # Show only favorited animations
            self._proxy_model.set_folder_filter(None, None, None)
            self._proxy_model.set_favorites_only(True)
        elif folder_name == "Recent":
            # Show only recently viewed animations
            self._proxy_model.set_folder_filter(None, None, None)
            self._proxy_model.set_recent_only(True)
        else:
            # Filter by folder name (tags-based)
            # Pass folder_name for tag-based filtering
            self._proxy_model.set_folder_filter(folder_id, set(), folder_name)

        # Update status
        count = self._proxy_model.rowCount()
        self._status_bar.showMessage(f"{count} animations in {folder_name}")

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

                # Update status
                name = animation.get('name', 'Unknown')
                self._status_bar.showMessage(f"Selected: {name}")
        else:
            # Clear metadata panel
            self._metadata_panel.clear()
            self._status_bar.showMessage("Ready")

    def _on_animation_double_clicked(self, uuid: str):
        """Handle animation double-click - Queue animation for Blender"""

        animation = self._animation_model.get_animation_by_uuid(uuid)
        if not animation:
            return

        name = animation.get('name', 'Unknown')

        # Set animation for application in Blender
        success = self._blender_service.queue_apply_animation(uuid, name)

        if success:
            self._status_bar.showMessage(f"Ready to apply '{name}' in Blender")
        else:
            self._status_bar.showMessage(f"Failed to set '{name}'")
            self._event_bus.report_error("blender", f"Failed to set animation '{name}'")

    def _on_search_text_changed(self, text: str):
        """Handle search text change"""

        self._proxy_model.set_search_text(text)

        # Update status
        count = self._proxy_model.rowCount()
        if text:
            self._status_bar.showMessage(f"{count} animations match '{text}'")
        else:
            self._status_bar.showMessage(f"{count} animations")

    def _on_sort_changed(self, sort_by: str, sort_order: str):
        """Handle sort option change from toolbar"""
        self._proxy_model.set_sort_config(sort_by, sort_order)

    def _on_edit_mode_changed(self, enabled: bool):
        """Handle edit mode toggle"""

        if enabled:
            self._bulk_edit_toolbar.show()
        else:
            self._bulk_edit_toolbar.hide()

    def _on_delete_clicked(self):
        """Handle delete button click"""
        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            return

        # Confirmation dialog
        count = len(selected_uuids)
        msg = f"Delete {count} animation{'s' if count > 1 else ''}?\n\nThis will permanently remove the files."
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Delete from database and filesystem
        library_path = Config.load_library_path()
        deleted = 0
        for uuid in selected_uuids:
            self._db_service.delete_animation(uuid)
            self._animation_model.remove_animation(uuid)

            # Delete files from library folder
            if library_path:
                anim_folder = library_path / "library" / uuid
                if anim_folder.exists():
                    shutil.rmtree(anim_folder)
            deleted += 1

        self._status_bar.showMessage(f"Deleted {deleted} animation{'s' if deleted > 1 else ''}")

    def _on_apply_clicked(self):
        """Handle apply to Blender button click - Queue selected animation for Blender"""

        # Get selected animation UUID from EventBus
        uuid = self._event_bus.get_selected_animation()
        if not uuid:
            self._status_bar.showMessage("No animation selected")
            return

        animation = self._animation_model.get_animation_by_uuid(uuid)
        if not animation:
            self._status_bar.showMessage("Animation not found")
            return

        name = animation.get('name', 'Unknown')

        # Set animation for application in Blender
        success = self._blender_service.queue_apply_animation(uuid, name)

        if success:
            self._status_bar.showMessage(f"Ready to apply '{name}' in Blender")
        else:
            self._status_bar.showMessage(f"Failed to set '{name}'")
            self._event_bus.report_error("blender", f"Failed to set animation '{name}'")

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
        from PyQt6.QtWidgets import QMessageBox, QInputDialog

        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            QMessageBox.warning(self, "No Selection", "Please select animations first")
            return

        # Collect all unique tags from selected animations
        all_tags = set()
        for uuid in selected_uuids:
            animation = self._animation_model.get_animation_by_uuid(uuid)
            if animation:
                all_tags.update(animation.get('tags', []))

        if not all_tags:
            QMessageBox.information(self, "No Tags", "Selected animations have no tags")
            return

        # Show tag selection dialog
        tag_list = sorted(list(all_tags))
        tag, ok = QInputDialog.getItem(
            self,
            "Remove Tag",
            "Select tag to remove:",
            tag_list,
            0,
            False
        )

        if not ok or not tag:
            return

        # Confirm removal
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove tag '{tag}' from {len(selected_uuids)} animation(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Remove tag from each selected animation
        success_count = 0
        for uuid in selected_uuids:
            animation = self._animation_model.get_animation_by_uuid(uuid)
            if not animation:
                continue

            current_tags = animation.get('tags', [])
            if tag in current_tags:
                current_tags.remove(tag)

                if self._db_service.update_animation(uuid, {'tags': current_tags}):
                    success_count += 1

        # Reload animations
        if success_count > 0:
            animations = self._db_service.get_all_animations()
            self._animation_model.set_animations(animations)

            self._status_bar.showMessage(
                f"Removed tag '{tag}' from {success_count} animation(s)"
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to remove tags")

    def _on_gradient_preset_selected(self, name: str, top_color: tuple, bottom_color: tuple):
        """Handle gradient preset selection from dropdown"""
        self._apply_gradient_to_selected(top_color, bottom_color, name)

    def _on_custom_gradient_clicked(self):
        """Handle custom gradient selection - opens color picker dialog"""
        from .dialogs.gradient_picker_dialog import GradientPickerDialog

        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            return

        dialog = GradientPickerDialog(self)
        if not dialog.exec():
            return

        top_color, bottom_color = dialog.get_gradient()
        self._apply_gradient_to_selected(top_color, bottom_color, "Custom")

    def _apply_gradient_to_selected(self, top_color: tuple, bottom_color: tuple, preset_name: str):
        """Apply gradient colors to all selected animations"""
        import json
        from PyQt6.QtWidgets import QMessageBox

        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            QMessageBox.warning(self, "No Selection", "Please select animations first")
            return

        success_count = 0
        for uuid in selected_uuids:
            updates = {
                'use_custom_thumbnail_gradient': 1,
                'thumbnail_gradient_top': json.dumps(list(top_color)),
                'thumbnail_gradient_bottom': json.dumps(list(bottom_color))
            }

            if self._db_service.update_animation(uuid, updates):
                success_count += 1

        if success_count > 0:
            # Reload animations
            animations = self._db_service.get_all_animations()
            self._animation_model.set_animations(animations)

            # Clear thumbnail cache and refresh view
            from ..services.thumbnail_loader import get_thumbnail_loader
            thumbnail_loader = get_thumbnail_loader()
            thumbnail_loader.clear_cache()
            self._animation_view.viewport().update()

            self._status_bar.showMessage(
                f"Applied '{preset_name}' gradient to {success_count} animation(s)"
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to apply gradient")

    def _on_move_to_folder(self):
        """Handle move selected animations to folder"""
        from PyQt6.QtWidgets import QMessageBox, QInputDialog

        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            QMessageBox.warning(self, "No Selection", "Please select animations first")
            return

        # Get all folders
        folders = self._db_service.get_all_folders()
        user_folders = [f for f in folders if f.get('parent_id')]  # Exclude root

        if not user_folders:
            QMessageBox.information(self, "No Folders", "Please create a folder first")
            return

        # Build folder list for selection
        folder_names = [f['name'] for f in user_folders]
        folder_name, ok = QInputDialog.getItem(
            self,
            "Move to Folder",
            "Select destination folder:",
            folder_names,
            0,
            False
        )

        if not ok or not folder_name:
            return

        # Find folder ID
        folder_id = None
        for f in user_folders:
            if f['name'] == folder_name:
                folder_id = f['id']
                break

        if not folder_id:
            return

        # Move animations
        success_count = 0
        for uuid in selected_uuids:
            if self._db_service.move_animation_to_folder(uuid, folder_id):
                success_count += 1

        # Reload animations
        if success_count > 0:
            animations = self._db_service.get_all_animations()
            self._animation_model.set_animations(animations)

            self._status_bar.showMessage(
                f"Moved {success_count} animation(s) to '{folder_name}'"
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to move animations")

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
        animations = self._db_service.get_all_animations()
        self._animation_model.set_animations(animations)

        # If the changed folder is currently selected, keep it selected
        selected_items = self._folder_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                folder_name = data.get('folder_name')
                # Reapply current filter
                if folder_name == "All Animations":
                    self._proxy_model.set_folder_filter(None, None, None)
                else:
                    folder_item_id = data.get('folder_id')
                    if folder_item_id:
                        self._proxy_model.set_folder_filter(folder_item_id, None, folder_name)

    # ==================== EVENTS ====================

    def closeEvent(self, event: QCloseEvent):
        """Handle window close"""

        # Save settings
        self._save_settings()

        # Accept close
        event.accept()


__all__ = ['MainWindow']
