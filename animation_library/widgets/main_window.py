"""
MainWindow - Main application window

Pattern: QMainWindow with splitter layout
Inspired by: Current animation_library structure
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QDialog, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, QSettings, QTimer, QFileSystemWatcher
from PyQt6.QtGui import QCloseEvent
import json

from ..config import Config
from ..events.event_bus import get_event_bus
from ..services.database_service import get_database_service
from ..services.blender_service import get_blender_service
from ..services.archive_service import get_archive_service
from ..services.trash_service import get_trash_service
from ..services.thumbnail_loader import get_thumbnail_loader
from ..services.update_service import UpdateService
from ..themes.theme_manager import get_theme_manager
from ..models.animation_list_model import AnimationListModel
import threading
from ..models.animation_filter_proxy_model import AnimationFilterProxyModel
from ..views.animation_view import AnimationView
from .header_toolbar import HeaderToolbar
from .folder_tree import FolderTree
from .metadata_panel import MetadataPanel
from .apply_panel import ApplyPanel
from .bulk_edit_toolbar import BulkEditToolbar
from .settings.settings_dialog import SettingsDialog
from .help_overlay import HelpOverlay
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

    # Max number of watched directories to prevent resource exhaustion
    MAX_WATCHED_DIRECTORIES = 500

    def __init__(self, parent=None, db_service=None, blender_service=None,
                 archive_service=None, trash_service=None, event_bus=None,
                 thumbnail_loader=None, theme_manager=None):
        super().__init__(parent)

        # Check if first run and show setup wizard
        if Config.is_first_run():
            from .dialogs.setup_wizard import SetupWizard
            wizard = SetupWizard()
            if wizard.exec() != QDialog.DialogCode.Accepted:
                # User cancelled setup
                sys.exit(0)

        # Services and event bus (injectable for testing)
        self._event_bus = event_bus or get_event_bus()
        self._db_service = db_service or get_database_service()
        self._blender_service = blender_service or get_blender_service()
        self._archive_service = archive_service or get_archive_service()
        self._trash_service = trash_service or get_trash_service()
        self._thumbnail_loader = thumbnail_loader or get_thumbnail_loader()
        self._theme_manager = theme_manager or get_theme_manager()

        # Models (pass db_service for DI)
        self._animation_model = AnimationListModel(db_service=self._db_service)
        self._proxy_model = AnimationFilterProxyModel()
        self._proxy_model.setSourceModel(self._animation_model)

        # Track signal connections for cleanup
        self._signal_connections = []

        # Setup window
        self._setup_window()
        self._create_widgets()
        self._create_layout()
        self._init_controllers()
        self._connect_signals()
        self._load_settings()
        self._load_animations()
        self._setup_queue_watcher()
        self._setup_library_watcher()

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

        # Help overlay (hidden by default, toggle with 'H')
        # Created after layout so it overlays correctly
        self._help_overlay = HelpOverlay(central_widget)

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

    def _track_connection(self, signal, slot):
        """Connect signal to slot and track for cleanup on close"""
        signal.connect(slot)
        self._signal_connections.append((signal, slot))

    def _disconnect_all_signals(self):
        """Disconnect all tracked signal connections"""
        for signal, slot in self._signal_connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                # Signal already disconnected or object deleted
                pass
        self._signal_connections.clear()

    def _connect_signals(self):
        """Connect signals and slots"""

        # Folder tree selection -> filter animations
        self._track_connection(self._folder_tree.folder_selected, self._on_folder_selected)

        # Folder tree archive/trash actions
        self._track_connection(self._folder_tree.empty_archive_requested, self._on_empty_archive)
        self._track_connection(self._folder_tree.empty_trash_requested, self._on_empty_trash)

        # Animation view selection -> update metadata panel
        self._track_connection(
            self._animation_view.selectionModel().selectionChanged,
            self._on_animation_selection_changed
        )

        # Animation view selection -> update event bus (for bulk toolbar)
        self._track_connection(
            self._animation_view.selectionModel().selectionChanged,
            self._animation_view._on_selection_changed
        )

        # Animation view double-click -> apply animation
        self._track_connection(self._animation_view.animation_double_clicked, self._on_animation_double_clicked)

        # Animation view context menu -> show options
        self._track_connection(self._animation_view.animation_context_menu, self._on_animation_context_menu)

        # Header toolbar search -> filter animations
        self._track_connection(self._header_toolbar.search_text_changed, self._on_search_text_changed)

        # Header toolbar view mode -> update view
        self._track_connection(self._header_toolbar.view_mode_changed, self._animation_view.set_view_mode)

        # Header toolbar card size -> update view
        self._track_connection(self._header_toolbar.card_size_changed, self._animation_view.set_card_size)

        # Header toolbar edit mode -> show/hide bulk toolbar
        self._track_connection(self._header_toolbar.edit_mode_changed, self._on_edit_mode_changed)

        # Header toolbar archive -> archive selected animations (soft delete)
        self._track_connection(self._header_toolbar.delete_clicked, self._on_archive_clicked)

        # Apply panel -> apply animation with options
        self._track_connection(self._apply_panel.apply_clicked, self._on_apply_with_options)

        # Metadata panel notes changed -> refresh notes badges
        self._track_connection(self._metadata_panel.notes_changed, self._on_notes_changed)

        # Header toolbar refresh -> sync library with database
        self._track_connection(self._header_toolbar.refresh_library_clicked, self._on_refresh_library)

        # Header toolbar new folder -> create folder dialog
        self._track_connection(self._header_toolbar.new_folder_clicked, self._on_create_folder)

        # Header toolbar settings -> show settings dialog
        self._track_connection(self._header_toolbar.settings_clicked, self._show_settings)

        # Header toolbar help -> show keyboard shortcuts overlay
        self._track_connection(self._header_toolbar.help_clicked, self._help_overlay.toggle)

        # Header toolbar filters -> filter animations
        # Store lambda references to enable proper disconnection
        self._rig_type_filter_slot = lambda rig_types: self._proxy_model.set_rig_type_filter(set(rig_types))
        self._tags_filter_slot = lambda tags: self._proxy_model.set_tag_filter(set(tags))
        self._track_connection(self._header_toolbar.rig_type_filter_changed, self._rig_type_filter_slot)
        self._track_connection(self._header_toolbar.tags_filter_changed, self._tags_filter_slot)
        self._track_connection(self._header_toolbar.sort_changed, self._on_sort_changed)

        # Bulk edit toolbar signals
        self._track_connection(self._bulk_edit_toolbar.remove_tags_clicked, self._on_remove_tags)
        self._track_connection(self._bulk_edit_toolbar.move_to_folder_clicked, self._on_move_to_folder)
        self._track_connection(self._bulk_edit_toolbar.gradient_preset_selected, self._on_gradient_preset_selected)
        self._track_connection(self._bulk_edit_toolbar.custom_gradient_clicked, self._on_custom_gradient_clicked)
        self._track_connection(self._bulk_edit_toolbar.restore_clicked, self._on_restore_clicked)

        # Event bus signals
        self._track_connection(self._event_bus.loading_started, self._on_loading_started)
        self._track_connection(self._event_bus.loading_finished, self._on_loading_finished)
        self._track_connection(self._event_bus.error_occurred, self._on_error)
        self._track_connection(self._event_bus.folder_changed, self._on_folder_changed)
        self._track_connection(self._event_bus.settings_changed, self._on_settings_changed)
        self._track_connection(self._event_bus.animation_updated, self._on_animation_updated)
        self._track_connection(self._event_bus.operation_mode_changed, self._on_operation_mode_changed)

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

        # Fix pose flags for any animations with frame_count=1 that aren't marked as poses
        self._db_service.fix_pose_flags()

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

    def _setup_queue_watcher(self):
        """Setup file system watcher for queue directory to detect Blender notifications"""
        self._queue_watcher = QFileSystemWatcher(self)
        self._queue_check_timer = QTimer(self)
        self._queue_check_timer.timeout.connect(self._check_queue_notifications)

        # Get queue directory path
        library_path = Config.load_library_path()
        if library_path:
            queue_dir = Path(library_path) / ".queue"
            queue_dir.mkdir(parents=True, exist_ok=True)

            # Watch the queue directory for changes
            self._queue_watcher.addPath(str(queue_dir))
            self._queue_watcher.directoryChanged.connect(self._on_queue_directory_changed)

            # Also start periodic check (backup in case watcher misses events)
            self._queue_check_timer.start(Config.QUEUE_CHECK_INTERVAL_MS)

    def _setup_library_watcher(self):
        """Setup file system watcher for library folders to auto-refresh on new captures"""
        self._library_watcher = QFileSystemWatcher(self)
        self._library_refresh_timer = QTimer(self)
        self._library_refresh_timer.setSingleShot(True)
        self._library_refresh_timer.timeout.connect(self._on_library_auto_refresh)

        # Get library path
        library_path = Config.load_library_path()
        if library_path:
            library_dir = Path(library_path) / "library"

            # Watch actions and poses folders
            actions_dir = library_dir / "actions"
            poses_dir = library_dir / "poses"

            watch_count = 0
            for folder in [actions_dir, poses_dir]:
                if folder.exists() and watch_count < self.MAX_WATCHED_DIRECTORIES:
                    self._library_watcher.addPath(str(folder))
                    watch_count += 1
                    # Also watch immediate subfolders (animation folders)
                    for subfolder in folder.iterdir():
                        if watch_count >= self.MAX_WATCHED_DIRECTORIES:
                            break
                        if subfolder.is_dir():
                            self._library_watcher.addPath(str(subfolder))
                            watch_count += 1

            self._library_watcher.directoryChanged.connect(self._on_library_folder_changed)

    def _on_library_folder_changed(self, path: str):
        """Handle changes in library folders - debounce and auto-refresh"""
        # Debounce: wait 500ms after last change before refreshing
        # This prevents multiple refreshes when Blender writes multiple files
        self._library_refresh_timer.start(500)

        # Check if we've reached the max watched directories limit
        current_count = len(self._library_watcher.directories())
        if current_count >= self.MAX_WATCHED_DIRECTORIES:
            # At limit - don't add more watchers (auto-refresh timer will still work)
            return

        # Also add the changed path to watcher if it's a new directory
        path_obj = Path(path)
        if path_obj.is_dir() and path not in self._library_watcher.directories():
            if current_count < self.MAX_WATCHED_DIRECTORIES:
                self._library_watcher.addPath(path)
                current_count += 1

            # Watch new subfolders too (with limit check)
            for subfolder in path_obj.iterdir():
                if current_count >= self.MAX_WATCHED_DIRECTORIES:
                    break
                if subfolder.is_dir() and str(subfolder) not in self._library_watcher.directories():
                    self._library_watcher.addPath(str(subfolder))
                    current_count += 1

    def _on_library_auto_refresh(self):
        """Auto-refresh library after file changes detected"""
        # Sync library with database (lightweight - only imports new/changed)
        total_found, newly_imported = self._db_service.sync_library()

        if newly_imported > 0:
            # Reload animations from database
            animations = self._db_service.get_all_animations()
            self._animation_model.set_animations(animations)

            # Refresh filter dropdowns
            self._header_toolbar.refresh_filters()

            # Update status
            self._status_bar.showMessage(f"Auto-imported {newly_imported} new animation(s)")

    def _on_queue_directory_changed(self, path: str):
        """Handle changes in queue directory"""
        # Use a short delay to let file writes complete
        QTimer.singleShot(Config.QUEUE_NOTIFICATION_DELAY_MS, self._check_queue_notifications)

    def _check_queue_notifications(self):
        """Check for and process preview update notifications from Blender"""
        library_path = Config.load_library_path()
        if not library_path:
            return

        queue_dir = Path(library_path) / ".queue"
        if not queue_dir.exists():
            return

        # First, handle preview_updating_*.json files (release file locks before Blender renders)
        for notification_file in queue_dir.glob("preview_updating_*.json"):
            try:
                with open(notification_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                animation_id = data.get('animation_id')
                preview_path = data.get('preview_path', '')

                if animation_id:
                    # Release the video file if it's currently loaded
                    self._release_preview_file(animation_id, preview_path)

                # Delete notification file after processing
                notification_file.unlink()

            except Exception as e:
                print(f"Error processing preview_updating notification: {e}")
                try:
                    notification_file.unlink()
                except:
                    pass

        # Handle animation_captured_*.json files (new animation captured from Blender)
        for notification_file in queue_dir.glob("animation_captured_*.json"):
            try:
                with open(notification_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                animation_name = data.get('animation_name', 'Unknown')
                
                # Trigger full library refresh to import the new animation
                self._on_library_auto_refresh()
                
                # Update status bar
                self._status_bar.showMessage(f"New animation captured: {animation_name}")

                # Delete notification file after processing
                notification_file.unlink()

            except Exception as e:
                print(f"Error processing animation_captured notification: {e}")
                try:
                    notification_file.unlink()
                except:
                    pass

        # Find preview_updated_*.json files
        for notification_file in queue_dir.glob("preview_updated_*.json"):
            try:
                with open(notification_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                animation_id = data.get('animation_id')
                animation_name = data.get('animation_name', 'Unknown')

                if animation_id:
                    # Emit animation updated event to refresh the preview
                    self._event_bus.animation_updated.emit(animation_id)

                    # Update status bar
                    self._status_bar.showMessage(f"Preview updated: {animation_name}")

                    # Refresh the currently selected animation if it matches
                    self._refresh_animation_preview(animation_id)

                # Delete notification file after processing
                notification_file.unlink()

            except Exception as e:
                print(f"Error processing queue notification: {e}")
                # Still try to delete the file to avoid infinite loop
                try:
                    notification_file.unlink()
                except:
                    pass

    def _release_preview_file(self, animation_id: str, preview_path: str = ''):
        """Release video file lock so Blender can update it"""
        # Release from metadata panel if this animation is currently loaded
        if hasattr(self._metadata_panel, '_animation'):
            current = self._metadata_panel._animation
            if current and current.get('uuid') == animation_id:
                # Clear the video preview to release the file handle
                if hasattr(self._metadata_panel, '_video_preview'):
                    self._metadata_panel._video_preview.clear()
                    print(f"[Animation Library] Released video file for animation: {animation_id}")

        # Also stop any hover preview that might have this file
        if hasattr(self._animation_view, '_hover_popup') and self._animation_view._hover_popup:
            self._animation_view._hover_popup.hide_preview()

    def _refresh_animation_preview(self, animation_id: str):
        """Refresh preview for a specific animation if it's currently displayed"""
        # Invalidate thumbnail cache for this animation so it reloads from disk
        self._thumbnail_loader.invalidate_animation(animation_id)

        # Refresh animation data in the model (triggers dataChanged)
        self._animation_model.refresh_animation(animation_id)

        # Check if this animation is currently selected in metadata panel
        if hasattr(self._metadata_panel, '_animation'):
            current = self._metadata_panel._animation
            if current and current.get('uuid') == animation_id:
                # Reload animation data from database
                animation = self._db_service.get_animation_by_uuid(animation_id)
                if animation:
                    self._metadata_panel.set_animation(animation)

        # Force animation view to repaint with fresh thumbnails
        self._animation_view.viewport().update()

    def _show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self._theme_manager, self)
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

        if folder_name == "Home":
            self._filter_ctrl.clear_folder_filter()
        elif folder_name == "Actions":
            self._filter_ctrl.clear_folder_filter()
            self._filter_ctrl.set_animations_only(True)
        elif folder_name == "Poses":
            self._filter_ctrl.clear_folder_filter()
            self._filter_ctrl.set_poses_only(True)
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

    def _on_notes_changed(self):
        """Handle notes changed (e.g., lineage dialog closed) - refresh badges"""
        self._animation_model.refresh_notes_cache(emit_change=True)

    def _on_animation_double_clicked(
        self,
        uuid: str,
        mirror: bool = False,
        use_slots: bool = False,
        insert_at_playhead: bool = False
    ):
        """Handle animation double-click - Immediately apply to Blender with options

        Args:
            uuid: Animation/pose UUID
            mirror: If True, apply mirrored (Ctrl+double-click)
            use_slots: If True, add as slot instead of replacing (Shift+double-click, actions only)
            insert_at_playhead: If True, insert at playhead instead of new action (Alt+double-click, actions only)
        """

        animation = self._animation_model.get_animation_by_uuid(uuid)
        if not animation:
            return

        name = animation.get('name', 'Unknown')
        is_pose = animation.get('is_pose', 0)

        if is_pose:
            # Pose: Apply instantly with optional mirror (other modifiers don't apply to poses)
            blend_file_path = animation.get('blend_file_path', '')
            success = self._blender_service.queue_apply_pose(uuid, name, blend_file_path, mirror=mirror)
        else:
            # Animation: Apply with options from apply panel, override based on modifiers
            # Determine apply mode: Alt = INSERT, otherwise NEW
            apply_mode = "INSERT" if insert_at_playhead else "NEW"
            options = self._apply_panel.get_options(apply_mode=apply_mode)

            # Override mirror/slots if modifiers held
            if mirror:
                options['mirror'] = True
            if use_slots:
                options['use_slots'] = True

            success = self._blender_service.queue_apply_animation(uuid, name, options)

        if success:
            item_type = "pose" if is_pose else "animation"
            mirror_text = " (mirrored)" if mirror else ""
            slots_text = " (as slot)" if use_slots and not is_pose else ""
            playhead_text = " at playhead" if insert_at_playhead and not is_pose else ""
            self._status_bar.showMessage(f"Applied {item_type} '{name}'{mirror_text}{slots_text}{playhead_text} to Blender")
        else:
            self._status_bar.showMessage(f"Failed to apply '{name}'")
            self._event_bus.report_error("blender", f"Failed to apply animation '{name}'")

    def _on_animation_context_menu(self, uuid: str, position):
        """Handle animation right-click context menu"""

        animation = self._animation_model.get_animation_by_uuid(uuid)
        if not animation:
            return

        name = animation.get('name', 'Unknown')
        version_group_id = animation.get('version_group_id', uuid)

        # Create context menu
        menu = QMenu(self)

        # Apply action
        apply_action = menu.addAction("Apply to Blender")
        apply_action.triggered.connect(lambda: self._on_animation_double_clicked(uuid))

        menu.addSeparator()

        # View Lineage action
        version_count = self._db_service.get_version_count(version_group_id)
        if version_count > 1:
            history_action = menu.addAction(f"View Lineage ({version_count} versions)")
            history_action.triggered.connect(
                lambda: self._show_version_history(version_group_id)
            )

        menu.addSeparator()

        # Toggle Favorite
        is_favorite = animation.get('is_favorite', 0)
        fav_text = "Remove from Favorites" if is_favorite else "Add to Favorites"
        fav_action = menu.addAction(fav_text)
        fav_action.triggered.connect(lambda: self._toggle_favorite(uuid))

        menu.addSeparator()

        # Delete/Archive action based on mode
        from ..config import Config
        if Config.is_solo_mode():
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self._instant_delete_animation(uuid))
        else:
            archive_action = menu.addAction("Move to Archive")
            archive_action.triggered.connect(lambda: self._archive_animation(uuid))

        # Show menu at cursor position
        menu.exec(position)

    def _show_version_history(self, version_group_id: str):
        """Show version history dialog"""
        from .dialogs import VersionHistoryDialog

        dialog = VersionHistoryDialog(
            version_group_id,
            parent=self,
            theme_manager=self._theme_manager
        )

        # Connect signals
        dialog.version_selected.connect(self._on_version_selected)

        dialog.exec()

    def _on_version_selected(self, uuid: str):
        """Handle version selection from history dialog - apply it"""
        self._on_animation_double_clicked(uuid)

    def _toggle_favorite(self, uuid: str):
        """Toggle favorite status for animation"""
        success = self._db_service.toggle_favorite(uuid)
        if success:
            self._animation_model.refresh_animation(uuid)
            self._animation_view.viewport().update()

    def _archive_animation(self, uuid: str):
        """Archive a single animation via context menu"""
        # Use the archive trash controller
        self._archive_trash_ctrl.archive_animations([uuid])

    def _instant_delete_animation(self, uuid: str):
        """Instantly delete a single animation via context menu (Solo Mode)"""
        animation = self._animation_model.get_animation_by_uuid(uuid)
        name = animation.get('name', 'Unknown') if animation else 'Unknown'
        
        # Confirmation dialog
        reply = QMessageBox.warning(
            self,
            "Delete Animation",
            f"Permanently delete '{name}'?\n\nThis cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Clear metadata panel to release video file handles
        self._metadata_panel.clear()

        # Delete
        success, message = self._archive_service.instant_delete(uuid)
        if success:
            self._animation_model.remove_animation(uuid)
            self._status_bar.showMessage(f"Deleted '{name}'")
        else:
            self._event_bus.report_error("delete", message)

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
        """Handle delete/archive button click - mode and context aware"""
        from ..config import Config
        
        if Config.is_solo_mode():
            # Solo mode: instant delete
            self._instant_delete_selected()
        else:
            # Studio/Pipeline mode: archive (soft delete)
            self._archive_trash_ctrl.handle_delete_action()

    def _instant_delete_selected(self):
        """Instantly delete selected animations (Solo Mode)"""
        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            return

        # Confirmation dialog
        count = len(selected_uuids)
        msg = (
            f"Permanently delete {count} animation{'s' if count > 1 else ''}?\n\n"
            "This cannot be undone!"
        )
        reply = QMessageBox.warning(
            self,
            "Delete Animation",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Clear metadata panel to release video file handles
        self._metadata_panel.clear()

        # Delete each animation
        deleted = 0
        errors = []
        for uuid in selected_uuids:
            success, message = self._archive_service.instant_delete(uuid)
            if success:
                self._animation_model.remove_animation(uuid)
                deleted += 1
            else:
                errors.append(message)

        # Show result
        if deleted > 0:
            self._status_bar.showMessage(
                f"Deleted {deleted} animation{'s' if deleted > 1 else ''}"
            )
        if errors:
            self._event_bus.report_error("delete", f"Some items failed: {errors[0]}")

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
        is_pose = animation.get('is_pose', 0)

        if is_pose:
            # Pose: Apply instantly without options
            blend_file_path = animation.get('blend_file_path', '')
            success = self._blender_service.queue_apply_pose(uuid, name, blend_file_path)
        else:
            # Animation: Queue with options
            success = self._blender_service.queue_apply_animation(uuid, name, options)

        if success:
            item_type = "pose" if is_pose else "animation"
            self._status_bar.showMessage(f"Applied {item_type} '{name}' to Blender")
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

    def _on_settings_changed(self, setting_name: str, value):
        """Handle settings changes from settings dialog"""
        if setting_name == "hide_shortcut_toggles":
            # Update apply panel toggles visibility
            self._apply_panel.set_shortcut_toggles_visible(not value)

    def _on_operation_mode_changed(self, mode: str):
        """Handle operation mode change (solo/studio/pipeline)"""
        # Refresh header toolbar button appearance
        self._header_toolbar.refresh_mode()
        
        # Refresh folder tree to show/hide Archive and Trash virtual folders
        self._folder_tree.refresh()

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
                if folder_name == "Home":
                    self._filter_ctrl.clear_folder_filter()
                else:
                    folder_item_id = data.get('folder_id')
                    if folder_item_id:
                        self._filter_ctrl.set_folder_filter(folder_item_id, folder_name, None)

    def _on_animation_updated(self, uuid: str):
        """Handle animation updated event - refresh the card in the view"""
        if uuid:
            # Refresh the animation in the model to update the card
            self._animation_model.refresh_animation(uuid)

    # ==================== ARCHIVE/TRASH OPERATIONS (delegated to controller) ====================

    def _on_empty_archive(self):
        """Handle empty archive action - delegate to controller"""
        self._archive_trash_ctrl.empty_archive()

    def _on_empty_trash(self):
        """Handle empty trash action - delegate to controller"""
        self._archive_trash_ctrl.empty_trash()

    # ==================== EVENTS ====================

    def keyPressEvent(self, event):
        """Handle global key presses"""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit

        # 'H' toggles help overlay
        if event.key() == Qt.Key.Key_H:
            # Don't trigger if typing in a text input field
            focus = self.focusWidget()
            if not isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit)):
                self._help_overlay.toggle()
                event.accept()
                return

        super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Handle window resize - update help overlay size"""
        super().resizeEvent(event)
        if hasattr(self, '_help_overlay') and self._help_overlay.isVisible():
            central = self.centralWidget()
            if central:
                self._help_overlay.setGeometry(0, 0, central.width(), central.height())

    def closeEvent(self, event: QCloseEvent):
        """Handle window close"""

        # Stop queue check timer
        if hasattr(self, '_queue_check_timer') and self._queue_check_timer.isActive():
            self._queue_check_timer.stop()

        # Stop library refresh timer
        if hasattr(self, '_library_refresh_timer') and self._library_refresh_timer.isActive():
            self._library_refresh_timer.stop()

        # Disconnect all tracked signal connections to prevent memory leaks
        self._disconnect_all_signals()

        # Save settings
        self._save_settings()

        # Accept close
        event.accept()


__all__ = ['MainWindow']
