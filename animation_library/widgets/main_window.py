"""
MainWindow - Main application window

Pattern: QMainWindow with splitter layout
Inspired by: Current animation_library structure
"""

import logging
import os
import sys
from pathlib import Path
from typing import List, Tuple
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QDialog, QFileDialog, QMessageBox, QMenu,
    QApplication
)
from PyQt6.QtCore import Qt, QSettings, QTimer, QFileSystemWatcher, QThreadPool, QRunnable, QObject, pyqtSignal
from PyQt6.QtGui import QCloseEvent
import json

from ..config import Config
from ..events.event_bus import get_event_bus
from ..services.database_service import get_database_service
from ..services.blender_service import get_blender_service, APPLY_QUEUED
from ..services.archive_service import get_archive_service
from ..services.trash_service import get_trash_service
from ..services.thumbnail_loader import get_thumbnail_loader
from ..services.library_switch import reset_library_services, switch_library
from ..services.service_refs import service_ref
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

logger = logging.getLogger(__name__)


class _ApplyWorkerSignals(QObject):
    """Signal carrier for the background apply worker (QRunnable can't hold signals)."""
    done = pyqtSignal(object, dict)  # (apply_result, context)


class _ApplyWorker(QRunnable):
    """Runs a blocking apply (socket round-trip) off the Qt UI thread.

    The socket send/recv can block up to ~30s on a slow/large apply over the
    network; doing it on the UI thread froze the app. This runs it on a pool
    thread and reports the result back via a queued signal (delivered on the UI
    thread), so the window stays responsive.
    """
    def __init__(self, fn, context: dict):
        super().__init__()
        self._fn = fn
        self._context = context
        self.signals = _ApplyWorkerSignals()

    def run(self):
        try:
            result = self._fn()
        except Exception:
            result = None
        self.signals.done.emit(result, self._context)


class MainWindow(QMainWindow):
    # Resolved on every access, never cached: the library can be switched at
    # runtime, which resets these singletons, and this window is built once at
    # startup. A cached handle would silently keep reading the old library.
    # See services/service_refs.py.
    _db_service = service_ref(get_database_service, '_injected_db_service')
    _blender_service = service_ref(get_blender_service, '_injected_blender_service')
    _archive_service = service_ref(get_archive_service, '_injected_archive_service')
    _trash_service = service_ref(get_trash_service, '_injected_trash_service')

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

        # First-run identity wizard (Option B per-machine identity).
        # Forced — there's no "anonymous" mode. Runs after the library setup
        # wizard so the app already knows where the library lives.
        if not Config.has_identity():
            from .dialogs.identity_wizard import IdentityWizard
            identity_wizard = IdentityWizard()
            if identity_wizard.exec() != QDialog.DialogCode.Accepted:
                # User cancelled — same exit path as the setup wizard.
                # (sys.exit cleanup risk is tracked separately as bug_fix_spec #3.)
                sys.exit(0)
            Config.save_identity(identity_wizard.get_identity())

        # Services and event bus (injectable for testing; None in production, in
        # which case the properties above resolve the current singleton on every
        # access - see services/service_refs.py).
        self._event_bus = event_bus or get_event_bus()
        self._injected_db_service = db_service
        self._injected_blender_service = blender_service
        self._injected_archive_service = archive_service
        self._injected_trash_service = trash_service
        self._theme_manager = theme_manager or get_theme_manager()

        # The thumbnail loader is NOT library-bound (paths are passed per
        # request) and views connect to its signals, so it stays a plain cached
        # reference. Only its caches are library-specific, and
        # reset_thumbnail_loader() clears those in place.
        self._thumbnail_loader = thumbnail_loader or get_thumbnail_loader()

        # Models. Pass the INJECTED value, not self._db_service: handing over the
        # resolved service would freeze it inside the model and undo the deferral.
        self._animation_model = AnimationListModel(db_service=self._injected_db_service)
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
        # Startup is just "bind to the configured library" - the exact same path
        # a switch takes, so the switch path is exercised on every launch.
        self._load_library(initial=True)

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

        # Update banner - above everything, because the previous home for this
        # (a button inside the About dialog) meant nobody ever found it.
        # Hidden unless a newer release actually exists.
        from .update_banner import UpdateBanner
        self._update_banner = UpdateBanner()
        self._update_banner.update_requested.connect(self._on_update_requested)
        main_layout.addWidget(self._update_banner)

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
            # Injected values, not resolved ones - see the note in __init__.
            db_service=self._injected_db_service,
            archive_service=self._injected_archive_service,
            trash_service=self._injected_trash_service,
            event_bus=self._event_bus,
            status_bar=self._status_bar,
            reload_animations_callback=self._reload_animations_from_db
        )

        # Bulk edit controller - manages bulk operations
        self._bulk_edit_ctrl = BulkEditController(
            parent=self,
            animation_view=self._animation_view,
            animation_model=self._animation_model,
            db_service=self._injected_db_service,
            event_bus=self._event_bus,
            status_bar=self._status_bar,
            reload_animations_callback=self._reload_animations_from_db
        )

    def _reload_animations_from_db(self):
        """Reload all animations from database - used by controllers"""
        animations = self._db_service.get_all_animations()
        self._animation_model.set_animations(animations)
        self._refresh_folder_membership()
        self._animation_view.refresh_animated_previews()

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
        self._track_connection(self._header_toolbar.library_switch_requested,
                               self._on_library_switch_requested)
        self._track_connection(self._header_toolbar.library_browse_requested,
                               self._on_library_browse_requested)
        self._track_connection(self._header_toolbar.library_forget_requested,
                               self._on_library_forget_requested)
        self._track_connection(self._header_toolbar.docs_clicked,
                               self._open_documentation)

        # A folder rename/delete rewrites tags on its animations - reload the
        # model so the change shows immediately instead of at the next refresh.
        self._track_connection(self._folder_tree.animations_changed,
                               self._on_folder_animations_changed)

        self._track_connection(self._header_toolbar.search_text_changed, self._on_search_text_changed)

        # Header toolbar view mode -> update view
        self._track_connection(self._header_toolbar.view_mode_changed, self._animation_view.set_view_mode)

        # Header toolbar card size -> update view
        self._track_connection(self._header_toolbar.card_size_changed, self._animation_view.set_card_size)

        # Header toolbar edit mode -> show/hide bulk toolbar
        self._track_connection(self._header_toolbar.edit_mode_changed, self._on_edit_mode_changed)
        self._track_connection(self._header_toolbar.animated_previews_toggled,
                               self._on_animated_previews_toggled)

        # Pause animated previews when the app goes to the background.
        app = QApplication.instance()
        if app is not None:
            self._track_connection(app.applicationStateChanged, self._on_app_state_changed)

        # Header toolbar archive -> archive selected animations (soft delete)
        self._track_connection(self._header_toolbar.delete_clicked, self._on_archive_clicked)

        # Apply panel -> apply animation with options
        self._track_connection(self._apply_panel.apply_clicked, self._on_apply_with_options)

        # Metadata panel notes changed -> refresh notes badges
        self._track_connection(self._metadata_panel.notes_changed, self._on_notes_changed)

        # Tags changed anywhere -> rebuild the tag dropdown. This signal existed
        # with no subscribers, which is why removing a tag left it in the filter
        # dropdown until the next library refresh.
        self._track_connection(self._event_bus.tags_updated, self._on_tags_updated)

        # Header toolbar refresh -> sync library with database
        self._track_connection(self._header_toolbar.refresh_library_clicked, self._on_refresh_library)

        # Header toolbar new folder -> create folder dialog
        self._track_connection(self._header_toolbar.new_folder_clicked, self._on_create_folder)

        # Header toolbar settings -> show settings dialog
        self._track_connection(self._header_toolbar.settings_clicked, self._show_settings)

        # Header identity pill -> open Settings → Identity directly
        self._track_connection(self._header_toolbar.identity_pill_clicked, self._show_identity_settings)

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
        self._track_connection(self._bulk_edit_toolbar.add_tags_clicked, self._on_add_tags)
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

        # Animated previews. On by default; anyone who has explicitly turned
        # them off keeps that, since their setting is already stored.
        from ..services.sprite_playback import DEFAULT_ANIMATED_PREVIEWS
        animated = settings.value(
            "view/animated_previews", DEFAULT_ANIMATED_PREVIEWS, type=bool)
        self._header_toolbar.set_animated_previews(animated)
        if animated:
            self._on_animated_previews_toggled(True)

        # Look for a newer release. Runs off the UI thread a couple of seconds
        # in, and shows nothing at all unless there's genuinely an update.
        self._update_banner.start_check()

        # Card size - previously reset to the default on every launch.
        if settings.contains("view/card_size"):
            try:
                self._header_toolbar.set_card_size(int(settings.value("view/card_size")))
            except (ValueError, TypeError):
                pass

    def _save_settings(self):
        """Save window and splitter settings"""

        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)

        # Window geometry
        settings.setValue("window/geometry", self.saveGeometry())

        # Window state
        settings.setValue("window/state", self.saveState())

        # Splitter sizes
        settings.setValue("splitter/sizes", self._splitter.sizes())

        # Card size
        settings.setValue("view/card_size", self._header_toolbar.get_card_size())

    def _load_animations(self):
        """Load animations from database, auto-sync if needed"""
        from ..services.backup_service import BackupService

        self._event_bus.start_loading("Loading animations")

        # Check if database is empty - if so, auto-sync with library folder
        if self._db_service.get_animation_count() == 0:
            self._status_bar.showMessage("Scanning library...")
            self._db_service.sync_library()

            # Legacy repair, only for a freshly-populated database: mark
            # single-frame animations imported before is_pose existed as poses.
            # This used to run on EVERY launch of EVERY client, taking a write
            # lock on the shared network database for a repair that is a no-op
            # on any healthy library. It belongs with a fresh import (or an
            # explicit maintenance run), not on every startup.
            self._db_service.fix_pose_flags()
            self._db_service.migrate_to_actions_poses_folders()

        # Apply any pending metadata from import
        if BackupService.has_pending_metadata():
            self._status_bar.showMessage("Restoring metadata...")
            BackupService.apply_pending_metadata()

        # Get all animations from database
        animations = self._db_service.get_all_animations()

        # Load into model
        self._animation_model.set_animations(animations)
        self._refresh_folder_membership()

        # Update status
        count = len(animations)
        self._status_bar.showMessage(f"Loaded {count} animations")

        self._event_bus.finish_loading("Loading animations")

    # ==================== LIBRARY BINDING ====================

    def _load_library(self, initial: bool = False):
        """Bind the window to whatever library is currently configured.

        This is the ONE path that binds the UI to a library, and it runs BOTH at
        startup and on every switch. That's deliberate: a separate switch-only
        path would only run on the rare occasions someone switches, so it would
        rot unnoticed. This way, if it breaks, the app doesn't start.

        Args:
            initial: True on the startup call, where there is no previous library
                     to unbind from and the widgets were just built empty.
        """
        if not initial:
            self._teardown_library_bindings()
            reset_library_services()
            self._reset_library_ui_state()

        # Write the protocol schema into the (possibly brand new) library. At
        # startup main() does this before the window exists; on a switch nothing
        # else would, and the Blender addon needs it to be there.
        try:
            from ..main import sync_protocol_to_library
            sync_protocol_to_library()
        except Exception as e:
            logger.warning(f"Could not sync protocol to library: {e}")

        # Stamp the app's version into the library so the Blender addon can warn
        # when it's older than the app (the two are versioned together, so an old
        # addon on a new library is the source of most odd behaviour).
        self._write_app_version_marker()

        self._load_animations()

        if not initial:
            # Rebuilt from the new library's database. At startup these widgets
            # load themselves as they're constructed.
            self._folder_tree.refresh()
            self._header_toolbar.refresh_filters()

        self._setup_queue_watcher()
        self._setup_library_watcher()

    def _write_app_version_marker(self):
        """Write the app version to {library}/.meta/app_version.txt.

        The Blender addon reads this and compares it to its own version, so it
        can tell the user to reinstall when it's out of date. Best-effort - a
        read-only or offline library must not stop the app loading.
        """
        try:
            marker = Config.get_database_folder() / 'app_version.txt'
            tmp = marker.with_suffix('.tmp')
            tmp.write_text(Config.APP_VERSION, encoding='utf-8')
            os.replace(tmp, marker)
        except OSError as e:
            logger.warning(f"Could not write app version marker: {e}")

    def _teardown_library_bindings(self):
        """Stop watching/polling the current library and release its open files.

        Shared by the library switch and closeEvent - both need exactly this.
        """
        # Stop polling before anything else, so a timer can't fire mid-teardown
        # and repopulate what we're about to clear.
        if hasattr(self, '_queue_check_timer') and self._queue_check_timer.isActive():
            self._queue_check_timer.stop()
        if hasattr(self, '_library_refresh_timer') and self._library_refresh_timer.isActive():
            self._library_refresh_timer.stop()

        for attr in ('_queue_watcher', '_library_watcher'):
            watcher = getattr(self, attr, None)
            if watcher is not None:
                self._unwatch_all(watcher)

        # Release open file handles pointing INTO the library. The video preview
        # and the hover popup both hold a video file open; on Windows those pin
        # the folder, so a switch would leave the old library undeletable and the
        # handles leaked.
        try:
            self._metadata_panel.clear()
        except Exception as e:
            logger.warning(f"Error clearing metadata panel: {e}")
        try:
            self._apply_panel.clear()
        except Exception as e:
            logger.warning(f"Error clearing apply panel: {e}")
        try:
            if getattr(self._animation_view, '_hover_popup', None):
                self._animation_view._hover_popup.hide_preview()
        except Exception as e:
            logger.warning(f"Error releasing hover preview: {e}")

    def _reset_library_ui_state(self):
        """Clear view state that refers to the previous library's rows.

        Every uuid, folder id and tag belongs to the library we just left, so
        anything holding one has to go. Deliberately does NOT touch window
        geometry, splitter sizes, theme, view mode, card size or sort order -
        those are user preferences, not library data.
        """
        # Leave Archive/Trash view if we're in it: the model would otherwise hold
        # converted archive rows from the old library. Set the flags directly -
        # exit_special_views() early-returns when both are already False, so it
        # can't be used as an unconditional reset.
        self._archive_trash_ctrl._in_archive_view = False
        self._archive_trash_ctrl._in_trash_view = False
        self._bulk_edit_toolbar.set_special_view_mode()

        # Filters reference old folder ids, tags and rig types. Use the proxy's
        # own method: FilterController.clear_all_filters() misses poses_only and
        # animations_only.
        self._proxy_model.clear_all_filters()
        self._filter_ctrl._current_context = None

        # Clear the search box itself, not just the proxy - otherwise the box
        # still shows a query that is no longer being applied.
        self._header_toolbar._search_box.clear()

        # Selection is old uuids.
        self._animation_view.clearSelection()
        self._event_bus.clear_selection()
        self._event_bus._search_text = ""
        # Assign directly rather than via set_folder("Home"): set_folder is
        # guarded by an inequality check, so if the current folder is already
        # "Home" it emits nothing and listeners never re-drive.
        self._event_bus._current_folder = "Home"

    def _on_library_switch_requested(self, path: str):
        """User picked a library from the header picker."""
        from ..services.known_libraries import get_known_libraries_store

        label = path
        for lib in get_known_libraries_store().list_libraries():
            if lib['path'] == path:
                label = lib['label']
                break

        reply = QMessageBox.question(
            self,
            "Switch Library",
            f"Switch to '{label}'?\n\n{path}\n\n"
            "Blender follows automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            ok, message = self.switch_to_library(path)
            if not ok:
                QMessageBox.warning(
                    self, "Switch Failed",
                    f"Could not switch library:\n\n{message}"
                )

        # Always resync the picker from what's actually loaded - that's the whole
        # revert-on-cancel story. The combo already moved to the clicked entry, so
        # without this a declined or failed switch would leave it pointing at a
        # library we are not using.
        self._header_toolbar.refresh_libraries()

    def _on_library_forget_requested(self, path: str):
        """User asked to drop a library from the picker's list."""
        from ..services.known_libraries import get_known_libraries_store

        store = get_known_libraries_store()

        label = path
        for lib in store.list_libraries():
            if lib['path'] == path:
                label = lib['label']
                break

        reply = QMessageBox.question(
            self,
            "Forget Library",
            f"Remove '{label}' from the library list?\n\n{path}\n\n"
            "This only removes it from this menu. Nothing is deleted - the "
            "folder and every animation in it stay exactly as they are, and you "
            "can add it back with 'Browse for another folder...'.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            store.forget(path)
            self._header_toolbar.refresh_libraries()
            self._status_bar.showMessage(f"Removed '{label}' from the library list")

    def _on_library_browse_requested(self):
        """User picked 'Browse for another folder...' in the header picker."""
        current = Config.load_library_path() or Path.home()

        new_path = QFileDialog.getExistingDirectory(
            self,
            "Select Animation Library Folder",
            str(current),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if new_path:
            reply = QMessageBox.question(
                self,
                "Switch Library",
                f"Use this folder as the animation library?\n\n{new_path}\n\n"
                "An empty folder becomes a new, empty library. Existing "
                "animations are NOT moved.\n\n"
                "Blender follows automatically.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                ok, message = self.switch_to_library(new_path)
                if not ok:
                    QMessageBox.warning(
                        self, "Switch Failed",
                        f"Could not switch library:\n\n{message}"
                    )

        # Resync regardless: the combo is currently showing "Browse...".
        self._header_toolbar.refresh_libraries()

    def switch_to_library(self, new_path) -> Tuple[bool, str]:
        """Switch the app to a different library, in place, without restarting.

        Returns:
            (success, message) - message is the resolved path, or the reason.
        """
        # reset_services=False: _load_library() owns the teardown ordering (stop
        # timers and release files BEFORE the services go away).
        ok, message = switch_library(new_path, reset_services=False)
        if not ok:
            return False, message

        self._load_library()
        self._header_toolbar.refresh_libraries()
        self._status_bar.showMessage(f"Switched library: {message}")
        logger.info(f"Switched library in place: {message}")
        return True, message

    def _setup_queue_watcher(self):
        """Point the queue watcher at the CURRENT library's .queue folder.

        Idempotent - safe to call again after a library switch. The watcher, the
        timer and their signal connections are created once and then reused; only
        the watched paths change. Creating fresh ones per call would leave the
        previous watcher alive and still firing for the old library, and would
        stack a second timer on top of the first.
        """
        if not hasattr(self, '_queue_watcher'):
            self._queue_watcher = QFileSystemWatcher(self)
            self._queue_watcher.directoryChanged.connect(self._on_queue_directory_changed)
            self._queue_check_timer = QTimer(self)
            self._queue_check_timer.timeout.connect(self._check_queue_notifications)

        self._unwatch_all(self._queue_watcher)
        self._queue_check_timer.stop()

        library_path = Config.load_library_path()
        if not library_path:
            return

        queue_dir = Path(library_path) / ".queue"
        queue_dir.mkdir(parents=True, exist_ok=True)

        self._queue_watcher.addPath(str(queue_dir))

        # Periodic check as a backup in case the watcher misses events (it does,
        # over SMB).
        self._queue_check_timer.start(Config.QUEUE_CHECK_INTERVAL_MS)

    @staticmethod
    def _unwatch_all(watcher: QFileSystemWatcher):
        """Drop every path a watcher is watching.

        QFileSystemWatcher.addPath is additive and has no 'replace' - so without
        this, re-pointing at a new library would keep watching the old one's
        folders forever, on top of the new ones.
        """
        directories = watcher.directories()
        if directories:
            watcher.removePaths(directories)
        files = watcher.files()
        if files:
            watcher.removePaths(files)

    def _setup_library_watcher(self):
        """Point the library watcher at the CURRENT library's folders.

        Idempotent - see _setup_queue_watcher for why that matters.
        """
        if not hasattr(self, '_library_watcher'):
            self._library_watcher = QFileSystemWatcher(self)
            self._library_watcher.directoryChanged.connect(self._on_library_folder_changed)
            self._library_refresh_timer = QTimer(self)
            self._library_refresh_timer.setSingleShot(True)
            self._library_refresh_timer.timeout.connect(self._on_library_auto_refresh)

        self._unwatch_all(self._library_watcher)
        self._library_refresh_timer.stop()

        library_path = Config.load_library_path()
        if not library_path:
            return

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
            self._refresh_folder_membership()

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
                animation_id = data.get('animation_id')

                # Trigger full library refresh to import the new animation
                self._on_library_auto_refresh()

                # Only CONSUME the notification once the animation actually landed
                # in the database. The scan can legitimately miss it on the first
                # try - on a network share the directory listing is briefly cached
                # by the SMB client, or the files are still being flushed. Deleting
                # the notification anyway threw the trigger away forever, and the
                # capture then only showed up when the user refreshed by hand
                # (the "sometimes I have to hit refresh" symptom). Leave it in
                # place and let the next queue poll retry instead.
                if animation_id and not self._db_service.get_animation_by_uuid(animation_id):
                    attempts = int(data.get('_refresh_attempts', 0)) + 1
                    if attempts < 6:  # ~30s at the 5s queue-poll interval
                        data['_refresh_attempts'] = attempts
                        try:
                            with open(notification_file, 'w', encoding='utf-8') as f:
                                json.dump(data, f)
                        except OSError:
                            pass
                        continue  # not imported yet - retry on the next poll
                    # Out of attempts: fall through and clean the notification up
                    # so it can't linger forever.

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

    def _show_identity_settings(self):
        """Show settings dialog opened directly to the Identity tab."""
        dialog = SettingsDialog(self._theme_manager, self)
        dialog.open_identity_tab()
        dialog.exec()

    # ==================== SLOT HANDLERS ====================

    def _on_folder_selected(self, folder_id: int, folder_name: str, recursive: bool = True):
        """Handle folder selection with optional recursive filtering.

        Dispatches on WHAT the item is, not what it's called. The built-in
        folders (Home / Actions / Poses / Favorites / Recent / Archive / Trash)
        carry no folder_id and the tree emits -1 for them; anything with a real
        id is one of the user's own folders.

        This used to switch on the folder's NAME, which silently made those seven
        names reserved: a user folder called "Poses" never reached the folder
        branch, so it showed every pose in the library instead of its own
        contents - no error, no clue. Same disease as folder membership being a
        name-matched tag: identity by name instead of by id.
        """
        is_virtual = folder_id is None or folder_id < 0

        # Clear special filters first
        self._filter_ctrl.clear_special_filters()

        if is_virtual and folder_name == "Archive":
            self._archive_trash_ctrl.show_archive_view()
            self._bulk_edit_toolbar.set_special_view_mode(in_archive=True)
            return
        elif is_virtual and folder_name == "Trash":
            self._archive_trash_ctrl.show_trash_view()
            self._bulk_edit_toolbar.set_special_view_mode(in_trash=True)
            return

        # Exit special views if we were in archive/trash
        self._archive_trash_ctrl.exit_special_views()
        self._bulk_edit_toolbar.set_special_view_mode()  # Reset to normal mode

        if is_virtual:
            # Built-in views. Name-matching is safe here precisely because we
            # know these have no folder_id - they're ours, not the user's.
            self._filter_ctrl.clear_folder_filter()
            if folder_name == "Actions":
                self._filter_ctrl.set_animations_only(True)
            elif folder_name == "Poses":
                self._filter_ctrl.set_poses_only(True)
            elif folder_name == "Favorites":
                self._filter_ctrl.set_favorites_only(True)
            elif folder_name == "Recent":
                self._filter_ctrl.set_recent_only(True)
            # "Home" (and anything unrecognised) = no filter at all.
        else:
            # Filter by real folder membership, by id.
            #
            # This used to pass an empty set here and let the proxy match the
            # folder's NAME against each animation's tags - which is why folders
            # could never be renamed. `recursive` (the tree's toggle) decides
            # whether subfolders' contents are included.
            if recursive:
                folder_ids = set(self._db_service.get_folder_descendants(folder_id))
            else:
                folder_ids = {folder_id}
            self._filter_ctrl.set_folder_filter(folder_id, folder_name, folder_ids)

        self._filter_ctrl.update_status(folder_name)

    def _refresh_folder_membership(self):
        """Reload which animations are in which folders, and hand it to the proxy.

        Called whenever membership could have changed (load, drag-drop, folder
        delete/rename). One query for the whole map, because the filter needs it
        per row.
        """
        membership = {
            uuid: set(folder_ids)
            for uuid, folder_ids in self._db_service.get_folder_membership_map().items()
        }
        self._proxy_model.set_membership(membership)

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

        item_type = "pose" if is_pose else "animation"
        if is_pose:
            # Pose: apply instantly with optional mirror (other modifiers don't apply to poses)
            blend_file_path = animation.get('blend_file_path', '')
            fn = lambda: self._blender_service.queue_apply_pose(uuid, name, blend_file_path, mirror=mirror)
        else:
            # Animation: read options from the apply panel ON THE UI THREAD, then
            # run the blocking apply off-thread.
            apply_mode = "INSERT" if insert_at_playhead else "NEW"
            options = self._apply_panel.get_options(apply_mode=apply_mode)
            if mirror:
                options['mirror'] = True
            if use_slots:
                options['use_slots'] = True
            fn = lambda: self._blender_service.queue_apply_animation(uuid, name, options)

        # Run the (potentially 30s) socket round-trip off the UI thread so a slow
        # apply can't freeze the window; the result is reported by _on_apply_result.
        self._status_bar.showMessage(f"Applying {item_type} '{name}'...")
        self._apply_async(fn, {
            'name': name, 'item_type': item_type, 'mirror': mirror,
            'use_slots': use_slots, 'insert_at_playhead': insert_at_playhead,
        })

    def _apply_async(self, fn, context: dict):
        """Run a blocking apply (socket round-trip) on a pool thread; the result
        is delivered to _on_apply_result on the UI thread via a queued signal."""
        worker = _ApplyWorker(fn, context)
        worker.signals.done.connect(self._on_apply_result)
        QThreadPool.globalInstance().start(worker)

    def _on_apply_result(self, result, context: dict):
        """UI-thread slot: show the apply result message."""
        name = context.get('name', 'Unknown')
        item_type = context.get('item_type', 'animation')
        if result == APPLY_QUEUED:
            port_clash = self._blender_service.get_port_clash()
            if port_clash:
                # Another program answers on our port - queued to file, which
                # still reaches Blender, just slower. Explain once per session;
                # the status bar keeps saying it.
                self._status_bar.showMessage(
                    f"Queued {item_type} '{name}' - another program is using the Blender port (see Settings > Blender Integration)"
                )
                if not getattr(self, '_port_clash_shown', False):
                    self._port_clash_shown = True
                    QMessageBox.warning(self, "Blender port is in use by another program", port_clash)
                return
            # Blender isn't connected; queued to file - do NOT claim it applied.
            self._status_bar.showMessage(
                f"Queued {item_type} '{name}' - Blender not connected; it will apply when Blender is running"
            )
        elif result:
            mirror_text = " (mirrored)" if context.get('mirror') else ""
            slots_text = " (as slot)" if context.get('use_slots') and item_type != 'pose' else ""
            playhead_text = " at playhead" if context.get('insert_at_playhead') and item_type != 'pose' else ""
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

        # Add tags
        tag_action = menu.addAction("Add Tags...")
        tag_action.triggered.connect(lambda: self._add_tags_to_animations([uuid]))

        # Remove from the folder we're currently looking at. Only offered when a
        # real folder is selected, because "remove from folder" is meaningless in
        # Home or a virtual folder - and it says WHICH folder, since an animation
        # is usually in several.
        current_folder_id = self._filter_ctrl.get_current_folder_id()
        if current_folder_id and current_folder_id in set(
            self._db_service.get_folders_for_animation(uuid)
        ):
            folder = self._db_service.get_folder_by_id(current_folder_id)
            folder_name = folder.get('name') if folder else None
            if folder_name:
                remove_action = menu.addAction(f"Remove from '{folder_name}'")
                remove_action.triggered.connect(
                    lambda: self._remove_from_folder([uuid], current_folder_id)
                )

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

    def _add_tags_to_animations(self, uuids: List[str]):
        """Ask for tags and add them to the given animations.

        Adding a tag wasn't possible from the app at all before this: the dialog
        existed but nothing ever opened it, so a tag typed wrongly at capture
        could never be corrected here.
        """
        from .dialogs.tag_input_dialog import TagInputDialog

        if not uuids:
            return

        dialog = TagInputDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_tags = dialog.get_tags()
        if not new_tags:
            return

        # add_tags_to_animation() owns the normalization: trims, and steers to the
        # spelling the library already uses so `combat` can't become a second
        # `Combat`. See services/tag_utils.py.
        updated = sum(
            1 for uuid in uuids
            if self._db_service.add_tags_to_animation(uuid, new_tags)
        )

        if updated:
            self._reload_animations_from_db()
            # The tag dropdown is built from the tags in use, so it has to be
            # rebuilt or the new tag won't be filterable until a refresh.
            self._header_toolbar.refresh_filters()

        self._status_bar.showMessage(
            f"Added {', '.join(new_tags)} to {updated} animation(s)"
            if updated else "No tags added (already present)"
        )

    def _remove_from_folder(self, uuids: List[str], folder_id: int):
        """Take animations out of one folder, leaving them in any others."""
        folder = self._db_service.get_folder_by_id(folder_id)
        folder_name = folder.get('name', 'folder') if folder else 'folder'

        removed = sum(
            1 for uuid in uuids
            if self._db_service.remove_animation_from_folder(uuid, folder_id)
        )

        if removed:
            self._reload_animations_from_db()
            self._header_toolbar.refresh_filters()
            self._status_bar.showMessage(
                f"Removed {removed} animation(s) from '{folder_name}'"
            )

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

        item_type = "pose" if is_pose else "animation"
        if is_pose:
            # Pose: Apply instantly without options
            blend_file_path = animation.get('blend_file_path', '')
            fn = lambda: self._blender_service.queue_apply_pose(uuid, name, blend_file_path)
        else:
            # Animation: Queue with options
            fn = lambda: self._blender_service.queue_apply_animation(uuid, name, options)

        # Off-thread apply (see _on_animation_double_clicked) so the UI stays responsive.
        self._status_bar.showMessage(f"Applying {item_type} '{name}'...")
        self._apply_async(fn, {'name': name, 'item_type': item_type})

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
        self._refresh_folder_membership()
        self._animation_view.refresh_animated_previews()

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

    def _on_update_requested(self, info):
        """Banner clicked - show what's new and offer to install it."""
        from .dialogs.update_dialog import UpdateDialog
        dialog = UpdateDialog(info, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_banner.hide()

    def _on_animated_previews_toggled(self, enabled: bool):
        """Play/stop the previews on the cards."""
        from ..services.sprite_playback import get_sprite_playback
        playback = get_sprite_playback()
        playback.set_frame_size(self._header_toolbar.get_card_size())
        playback.set_enabled(enabled)
        if enabled:
            # Tell it what's on screen right now, or nothing plays until you scroll.
            self._animation_view.refresh_animated_previews()
        QSettings(Config.APP_AUTHOR, Config.APP_NAME).setValue(
            "view/animated_previews", enabled)

    def _on_app_state_changed(self, state):
        """Stop animating while the app is in the background.

        Repainting a grid 15 times a second is wasted work - and battery - when
        nobody is looking at it.
        """
        from PyQt6.QtCore import Qt as _Qt
        from ..services.sprite_playback import get_sprite_playback
        playback = get_sprite_playback()
        if state == _Qt.ApplicationState.ApplicationActive:
            playback.resume()
        else:
            playback.pause()

    def _on_tags_updated(self, uuid: str, tags: list):
        """A tag changed - the filter dropdown is built from tags in use."""
        self._header_toolbar.refresh_filters()

    def _on_folder_animations_changed(self):
        """A folder operation changed the animations themselves.

        Renaming or deleting a folder rewrites its tag on every animation in it,
        and deleting moves them to Home. The folder tree rebuilds itself, but the
        animation model is still holding the rows it loaded earlier - so the old
        tag stays on the card and in the metadata panel until something reloads
        them. That something is this.
        """
        self._reload_animations_from_db()   # also refreshes folder membership
        self._header_toolbar.refresh_filters()

        # The metadata panel keeps its own copy of the selected animation, so it
        # needs re-pointing at the fresh row rather than just repainting.
        selected = self._event_bus.get_selected_animation()
        if selected:
            fresh = self._db_service.get_animation_by_uuid(selected)
            if fresh:
                self._metadata_panel.set_animation(fresh)
            else:
                self._metadata_panel.clear()

    def _on_add_tags(self):
        """Handle add tags to selected animations"""
        self._add_tags_to_animations(self._animation_view.get_selected_uuids())

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
        # Adding to a folder mirrors the folder's name onto the animation's tags,
        # and the dropdown is built from the tags in use.
        self._header_toolbar.refresh_filters()

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

        # F1 opens the documentation. No text-field guard: F1 isn't a character,
        # so it can't collide with typing.
        if event.key() == Qt.Key.Key_F1:
            self._open_documentation()
            event.accept()
            return

        # 'H' toggles help overlay
        if event.key() == Qt.Key.Key_H:
            # Don't trigger if typing in a text input field
            focus = self.focusWidget()
            if not isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit)):
                self._help_overlay.toggle()
                event.accept()
                return

        super().keyPressEvent(event)

    def _open_documentation(self, page: str = None):
        """Open the local documentation in the user's default browser.

        Args:
            page: Optional page to deep-link, e.g. 'installation.html'.
        """
        from ..utils.docs import get_expected_docs_location, open_documentation

        if open_documentation(page):
            return

        # Not installed. Say where they were expected rather than just failing -
        # a missing docs folder is a packaging problem, and the path is the clue.
        QMessageBox.information(
            self,
            "Documentation",
            "The documentation files weren't found.\n\n"
            f"They're expected at:\n{get_expected_docs_location()}\n\n"
            "The docs ship with Action Library, so this usually means the "
            "install is incomplete."
        )

    def resizeEvent(self, event):
        """Handle window resize - update help overlay size"""
        super().resizeEvent(event)
        if hasattr(self, '_help_overlay') and self._help_overlay.isVisible():
            central = self.centralWidget()
            if central:
                self._help_overlay.setGeometry(0, 0, central.width(), central.height())

    def closeEvent(self, event: QCloseEvent):
        """Handle window close"""

        # Stop the timers/watchers and release the library's open video handles.
        # Same teardown a library switch performs.
        self._teardown_library_bindings()

        # Disconnect all tracked signal connections to prevent memory leaks
        self._disconnect_all_signals()

        # Save settings
        self._save_settings()

        # Accept close
        event.accept()


__all__ = ['MainWindow']
