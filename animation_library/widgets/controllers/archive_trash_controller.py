"""
ArchiveTrashController - Handles archive and trash view operations

Extracts archive/trash logic from MainWindow for better separation of concerns.
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from PyQt6.QtWidgets import QMessageBox, QWidget

logger = logging.getLogger(__name__)


class ArchiveTrashController:
    """
    Manages archive and trash views and operations.

    Handles:
    - Switching between normal, archive, and trash views
    - Archive operations (soft delete, restore)
    - Trash operations (move from archive, restore to archive, permanent delete)
    - Converting archive/trash items to animation format for display
    """

    def __init__(
        self,
        parent: QWidget,
        animation_model,
        animation_view,
        metadata_panel,
        proxy_model,
        db_service,
        archive_service,
        trash_service,
        event_bus,
        status_bar,
        reload_animations_callback: Callable[[], None]
    ):
        """
        Initialize archive/trash controller.

        Args:
            parent: Parent widget for dialogs
            animation_model: Animation list model
            animation_view: Animation view widget
            metadata_panel: Metadata panel widget
            proxy_model: Animation filter proxy model
            db_service: Database service
            archive_service: Archive service
            trash_service: Trash service
            event_bus: Event bus for signals
            status_bar: Status bar for messages
            reload_animations_callback: Callback to reload normal animations
        """
        self._parent = parent
        self._animation_model = animation_model
        self._animation_view = animation_view
        self._metadata_panel = metadata_panel
        self._proxy_model = proxy_model
        self._db_service = db_service
        self._archive_service = archive_service
        self._trash_service = trash_service
        self._event_bus = event_bus
        self._status_bar = status_bar
        self._reload_animations = reload_animations_callback

        # View state flags
        self._in_archive_view = False
        self._in_trash_view = False

    @property
    def in_archive_view(self) -> bool:
        """Check if currently in archive view."""
        return self._in_archive_view

    @property
    def in_trash_view(self) -> bool:
        """Check if currently in trash view."""
        return self._in_trash_view

    @property
    def in_special_view(self) -> bool:
        """Check if in any special view (archive or trash)."""
        return self._in_archive_view or self._in_trash_view

    def exit_special_views(self) -> None:
        """Exit archive and trash views and restore normal animations."""
        if self._in_archive_view or self._in_trash_view:
            self._in_archive_view = False
            self._in_trash_view = False
            self._reload_animations()

    # ==================== ARCHIVE VIEW ====================

    def show_archive_view(self) -> None:
        """Show archived items in the animation view."""
        self._in_archive_view = True
        self._in_trash_view = False

        # Get archive items and convert to animation-like format
        archive_items = self._archive_service.get_archive_items()
        animations = self._convert_archive_items(archive_items)

        # Load archive items into model
        self._animation_model.set_animations(animations)

        # Clear any active filters
        self._proxy_model.set_folder_filter(None, None, None)

        # Update status
        count = len(animations)
        total_size = self._archive_service.get_archive_size()
        self._status_bar.showMessage(
            f"Archive: {count} item{'s' if count != 1 else ''} ({total_size:.1f} MB)"
        )

        # Clear metadata panel
        self._metadata_panel.clear()

    def _convert_archive_items(self, archive_items: List[Dict]) -> List[Dict[str, Any]]:
        """Convert archive items to animation format for display."""
        animations = []
        for item in archive_items:
            anim = {
                'uuid': item['uuid'],
                'name': item['name'],
                'rig_type': item.get('rig_type', 'unknown'),
                'frame_count': item.get('frame_count', 0),
                'duration_seconds': item.get('duration_seconds', 0),
                'file_size_mb': item.get('file_size_mb', 0),
                'thumbnail_path': item.get('thumbnail_path', ''),
                'folder_id': -998,  # Special ID for archive items
                'tags': [],
                'is_favorite': False,
                '_is_archive_item': True,
                '_archived_date': item.get('archived_date'),
                '_original_folder_path': item.get('original_folder_path', ''),
            }
            animations.append(anim)
        return animations

    def archive_selected(self) -> None:
        """Archive selected animations from normal view (soft delete)."""
        if self.in_special_view:
            return

        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            return

        # Confirmation dialog
        count = len(selected_uuids)
        msg = (
            f"Move {count} animation{'s' if count > 1 else ''} to Archive?\n\n"
            "Items can be restored from the Archive folder."
        )
        reply = QMessageBox.question(
            self._parent,
            "Move to Archive",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Clear metadata panel to release video file handles
        self._metadata_panel.clear()

        # Move to archive
        archived = 0
        errors = []
        for uuid in selected_uuids:
            success, message = self._archive_service.move_to_archive(uuid)
            if success:
                self._animation_model.remove_animation(uuid)
                self._event_bus.animation_archived.emit(uuid)
                archived += 1
            else:
                errors.append(message)

        # Update archive count
        archive_count = self._archive_service.get_archive_count()
        self._event_bus.archive_count_changed.emit(archive_count)

        # Show result
        if archived > 0:
            self._status_bar.showMessage(
                f"Moved {archived} animation{'s' if archived > 1 else ''} to Archive"
            )
        if errors:
            self._event_bus.report_error("archive", f"Some items failed: {errors[0]}")

    def restore_from_archive(self) -> None:
        """Restore selected items from archive back to library."""
        if not self._in_archive_view:
            return

        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            return

        logger.info(f"Restoring {len(selected_uuids)} items from archive: {selected_uuids}")

        restored = 0
        errors = []
        for uuid in selected_uuids:
            logger.debug(f"Restoring UUID: {uuid}")
            success, message = self._archive_service.restore_from_archive(uuid)
            if success:
                restored += 1
                logger.info(f"Restored {uuid}")
                self._event_bus.animation_restored_from_archive.emit(uuid)
            else:
                logger.warning(f"Failed to restore {uuid}: {message}")
                errors.append(f"{uuid}: {message}")

        # Update archive count
        archive_count = self._archive_service.get_archive_count()
        self._event_bus.archive_count_changed.emit(archive_count)

        # Refresh archive view
        self.show_archive_view()

        if restored > 0:
            self._status_bar.showMessage(
                f"Restored {restored} animation{'s' if restored > 1 else ''} to library"
            )
        if errors:
            logger.error(f"Restore errors: {errors}")
            self._event_bus.report_error("archive", f"Failed to restore {len(errors)} item(s)")

    def move_to_trash_from_archive(self) -> None:
        """Move selected archive items to trash."""
        if not self._in_archive_view:
            return

        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            return

        # Confirmation dialog
        count = len(selected_uuids)
        msg = (
            f"Move {count} item{'s' if count > 1 else ''} to Trash?\n\n"
            "From Trash, items can be permanently deleted."
        )
        reply = QMessageBox.question(
            self._parent,
            "Move to Trash",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        moved = 0
        errors = []
        for uuid in selected_uuids:
            success, message = self._archive_service.move_to_trash(uuid)
            if success:
                moved += 1
                self._event_bus.animation_moved_to_trash.emit(uuid)
            else:
                errors.append(message)

        # Update counts
        archive_count = self._archive_service.get_archive_count()
        trash_count = self._trash_service.get_trash_count()
        self._event_bus.archive_count_changed.emit(archive_count)
        self._event_bus.trash_count_changed.emit(trash_count)

        # Refresh archive view
        self.show_archive_view()

        if moved > 0:
            self._status_bar.showMessage(
                f"Moved {moved} item{'s' if moved > 1 else ''} to Trash"
            )
        if errors:
            self._event_bus.report_error("archive", f"Some items failed: {errors[0]}")

    def empty_archive(self) -> None:
        """Move all archive items to trash."""
        archive_count = self._archive_service.get_archive_count()
        if archive_count == 0:
            QMessageBox.information(
                self._parent, "Archive Empty", "Archive is already empty."
            )
            return

        archive_size = self._archive_service.get_archive_size()

        # Confirmation dialog
        msg = (
            f"Move all {archive_count} item{'s' if archive_count > 1 else ''} "
            f"from Archive to Trash?\n\n"
            f"This affects {archive_size:.1f} MB of data."
        )
        reply = QMessageBox.question(
            self._parent,
            "Move All to Trash",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Move all archive items to trash
        archive_items = self._archive_service.get_archive_items()
        moved = 0
        for item in archive_items:
            success, _ = self._archive_service.move_to_trash(item['uuid'])
            if success:
                moved += 1

        # Update counts
        self._event_bus.archive_count_changed.emit(0)
        trash_count = self._trash_service.get_trash_count()
        self._event_bus.trash_count_changed.emit(trash_count)

        # Refresh archive view if active
        if self._in_archive_view:
            self.show_archive_view()

        self._status_bar.showMessage(
            f"Moved {moved} item{'s' if moved > 1 else ''} from Archive to Trash"
        )

    # ==================== TRASH VIEW ====================

    def show_trash_view(self) -> None:
        """Show trash items in the animation view."""
        self._in_trash_view = True
        self._in_archive_view = False

        # Get trash items and convert to animation-like format
        trash_items = self._trash_service.get_trash_items()
        animations = self._convert_trash_items(trash_items)

        # Load trash items into model
        self._animation_model.set_animations(animations)

        # Clear any active filters
        self._proxy_model.set_folder_filter(None, None, None)

        # Update status
        count = len(animations)
        self._status_bar.showMessage(
            f"Trash: {count} item{'s' if count != 1 else ''} (pending deletion)"
        )

        # Clear metadata panel
        self._metadata_panel.clear()

    def _convert_trash_items(self, trash_items: List[Dict]) -> List[Dict[str, Any]]:
        """Convert trash items to animation format for display."""
        animations = []
        for item in trash_items:
            anim = {
                'uuid': item['uuid'],
                'name': item['name'],
                'rig_type': 'unknown',  # Trash items don't store full metadata
                'frame_count': 0,
                'duration_seconds': 0,
                'file_size_mb': 0,
                'thumbnail_path': item.get('thumbnail_path', ''),
                'folder_id': -999,  # Special ID for trash items
                'tags': [],
                'is_favorite': False,
                '_is_trash_item': True,
                '_trashed_date': item.get('trashed_date'),
                '_archived_date': item.get('archived_date'),
            }
            animations.append(anim)
        return animations

    def restore_to_archive(self) -> None:
        """Restore selected items from trash back to archive."""
        if not self._in_trash_view:
            return

        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            return

        restored = 0
        errors = []
        for uuid in selected_uuids:
            success, message = self._trash_service.restore_to_archive(uuid)
            if success:
                restored += 1
                self._event_bus.animation_restored_to_archive.emit(uuid)
            else:
                errors.append(message)

        # Update counts
        trash_count = self._trash_service.get_trash_count()
        archive_count = self._archive_service.get_archive_count()
        self._event_bus.trash_count_changed.emit(trash_count)
        self._event_bus.archive_count_changed.emit(archive_count)

        # Refresh trash view
        self.show_trash_view()

        if restored > 0:
            self._status_bar.showMessage(
                f"Restored {restored} item{'s' if restored > 1 else ''} to Archive"
            )
        if errors:
            self._event_bus.report_error("trash", f"Some restores failed: {errors[0]}")

    def permanent_delete(self) -> None:
        """Permanently delete selected trash items."""
        if not self._in_trash_view:
            return

        # Check if hard delete is allowed
        if not self._trash_service.is_hard_delete_allowed():
            QMessageBox.warning(
                self._parent,
                "Hard Delete Disabled",
                "Permanent deletion is disabled.\n\n"
                "Enable 'Allow permanent deletion' in Settings to delete items."
            )
            return

        selected_uuids = self._animation_view.get_selected_uuids()
        if not selected_uuids:
            return

        # Confirmation dialog
        count = len(selected_uuids)
        msg = (
            f"Permanently delete {count} item{'s' if count > 1 else ''}?\n\n"
            "This cannot be undone!"
        )
        reply = QMessageBox.warning(
            self._parent,
            "Permanent Delete",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        for uuid in selected_uuids:
            success, _ = self._trash_service.permanently_delete(uuid)
            if success:
                deleted += 1
                self._event_bus.trash_item_deleted.emit(uuid)

        # Update trash count
        trash_count = self._trash_service.get_trash_count()
        self._event_bus.trash_count_changed.emit(trash_count)

        # Refresh trash view
        self.show_trash_view()

        if deleted > 0:
            self._status_bar.showMessage(
                f"Permanently deleted {deleted} item{'s' if deleted > 1 else ''}"
            )

    def empty_trash(self) -> None:
        """Empty all items from trash."""
        # Check if hard delete is allowed
        if not self._trash_service.is_hard_delete_allowed():
            QMessageBox.warning(
                self._parent,
                "Hard Delete Disabled",
                "Permanent deletion is disabled.\n\n"
                "Enable 'Allow permanent deletion' in Settings to empty trash."
            )
            return

        trash_count = self._trash_service.get_trash_count()
        if trash_count == 0:
            QMessageBox.information(
                self._parent, "Trash Empty", "Trash is already empty."
            )
            return

        # Confirmation dialog
        msg = (
            f"Permanently delete all {trash_count} item{'s' if trash_count > 1 else ''} "
            f"in trash?\n\n"
            "This cannot be undone!"
        )
        reply = QMessageBox.warning(
            self._parent,
            "Empty Trash",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted, errors, message = self._trash_service.empty_trash()

        # Update trash count
        self._event_bus.trash_count_changed.emit(0)
        self._event_bus.trash_emptied.emit()

        # Refresh trash view if active
        if self._in_trash_view:
            self.show_trash_view()

        self._status_bar.showMessage(message)

    # ==================== CONTEXT-AWARE DELETE HANDLER ====================

    def handle_delete_action(self) -> None:
        """
        Handle delete/archive action based on current view context.

        - Normal view: Archive selected items (soft delete)
        - Archive view: Move to trash
        - Trash view: Show message (use context menu)
        """
        if self._in_archive_view:
            self.move_to_trash_from_archive()
        elif self._in_trash_view:
            self._status_bar.showMessage("Use right-click menu for trash actions")
        else:
            self.archive_selected()


__all__ = ['ArchiveTrashController']
