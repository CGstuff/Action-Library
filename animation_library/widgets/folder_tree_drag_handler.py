"""
FolderTreeDragHandler - Handles drag-drop operations for folder tree

Extracts drag-drop logic from FolderTree for better separation of concerns.
"""

from typing import Optional, Tuple
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMessageBox
from PyQt6.QtCore import Qt, QTimer


class FolderTreeDragHandler:
    """
    Handles drag-drop operations for folder tree.

    Supports:
    - Animation card drops onto folders
    - Folder-to-folder drag (hierarchy management)
    - Folder to root level drag
    """

    def __init__(
        self,
        tree_widget: QTreeWidget,
        db_service,
        move_service,
        event_bus,
        reload_callback
    ):
        """
        Initialize drag handler.

        Args:
            tree_widget: The folder tree widget
            db_service: Database service
            move_service: Folder move service
            event_bus: Event bus for signals
            reload_callback: Callback to reload folder tree
        """
        self._tree = tree_widget
        self._db_service = db_service
        self._move_service = move_service
        self._event_bus = event_bus
        self._reload_folders = reload_callback

        # Track dragged folder for folder-to-folder dragging
        self._dragged_folder_item: Optional[QTreeWidgetItem] = None

    def start_drag(self, selected_items):
        """Store dragged folder item before drag starts."""
        if selected_items:
            self._dragged_folder_item = selected_items[0]

    def clear_dragged_item(self):
        """Clear the dragged folder item reference."""
        self._dragged_folder_item = None

    def handle_drag_enter(self, event) -> bool:
        """
        Handle drag enter event.

        Args:
            event: QDragEnterEvent

        Returns:
            True if event should be accepted
        """
        mime_data = event.mimeData()

        # Accept both animation UUID drops AND internal folder drags
        if (mime_data.hasFormat('application/x-animation-uuid') or
            mime_data.hasFormat('application/x-qabstractitemmodeldatalist')):
            event.acceptProposedAction()
            return True
        else:
            event.ignore()
            return False

    def handle_drag_move(self, event) -> bool:
        """
        Handle drag move event - highlight target folder.

        Args:
            event: QDragMoveEvent

        Returns:
            True if event should be accepted
        """
        mime_data = event.mimeData()
        item = self._tree.itemAt(event.position().toPoint())

        if not item:
            event.ignore()
            return False

        # Accept both animation cards and folder drags
        if (mime_data.hasFormat('application/x-animation-uuid') or
            mime_data.hasFormat('application/x-qabstractitemmodeldatalist')):
            # Highlight drop target
            self._tree.setCurrentItem(item)
            event.acceptProposedAction()
            return True
        else:
            event.ignore()
            return False

    def handle_drop(self, event) -> bool:
        """
        Handle drop event for animations or folders.

        Args:
            event: QDropEvent

        Returns:
            True if event was handled
        """
        mime_data = event.mimeData()

        # Check if this is a folder drag (internal tree drag)
        if mime_data.hasFormat('application/x-qabstractitemmodeldatalist'):
            return self._handle_folder_drop(event)

        # Handle animation UUID drops
        if mime_data.hasFormat('application/x-animation-uuid'):
            return self._handle_animation_drop(event)

        event.ignore()
        return False

    def _handle_folder_drop(self, event) -> bool:
        """Handle folder-to-folder or folder-to-root drop."""
        target_item = self._tree.itemAt(event.position().toPoint())

        if not self._dragged_folder_item:
            event.ignore()
            return False

        # Handle different drop targets
        if target_item is None:
            # Dropped on empty space -> move to root level
            if self._move_folder_to_root(self._dragged_folder_item):
                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
                self._dragged_folder_item = None
                return True
        elif not hasattr(target_item, 'folder_id'):
            # Dropped on virtual folder -> move to root level
            if self._move_folder_to_root(self._dragged_folder_item):
                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
                self._dragged_folder_item = None
                return True
        else:
            # Dropped on user folder -> create hierarchy
            if self._move_folder_to_folder(self._dragged_folder_item, target_item):
                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
                self._dragged_folder_item = None
                return True

        event.ignore()
        return False

    def _handle_animation_drop(self, event) -> bool:
        """Handle animation card drop onto folder."""
        mime_data = event.mimeData()

        # Get target folder item
        target_item = self._tree.itemAt(event.position().toPoint())
        if not target_item:
            event.ignore()
            return False

        # Extract animation UUID(s) from MIME data
        try:
            uuid_data = bytes(mime_data.data('application/x-animation-uuid')).decode('utf-8')
            animation_uuids = [u.strip() for u in uuid_data.strip().split('\n') if u.strip()]

            if not animation_uuids:
                event.ignore()
                return False
        except (UnicodeDecodeError, AttributeError) as e:
            QMessageBox.warning(
                self._tree, "Drag Error", f"Failed to decode animation data: {e}"
            )
            event.ignore()
            return False

        # Check if target is a valid user folder
        if not hasattr(target_item, 'folder_id'):
            QMessageBox.warning(
                self._tree,
                "Cannot Move",
                "Cannot move animations to virtual folders"
            )
            event.ignore()
            return False

        target_folder_id = target_item.folder_id

        # Move animations to target folder
        success_count = 0
        failed_count = 0
        for uuid in animation_uuids:
            if self._db_service.move_animation_to_folder(uuid, target_folder_id):
                success_count += 1
            else:
                failed_count += 1

        if success_count > 0:
            event.acceptProposedAction()

            # Emit signal to refresh animation list
            self._event_bus.folder_changed.emit(target_folder_id)

            # Show result message
            folder_name = target_item.text(0).split(' (')[0]  # Remove count

            if failed_count > 0:
                QMessageBox.warning(
                    self._tree,
                    "Partially Moved",
                    f"Moved {success_count} animation(s) to '{folder_name}'.\n\n"
                    f"{failed_count} failed."
                )
            else:
                QMessageBox.information(
                    self._tree,
                    "Moved",
                    f"Moved {success_count} animation(s) to '{folder_name}'"
                )
            return True
        else:
            QMessageBox.warning(
                self._tree,
                "Move Failed",
                "Failed to move any animations. They may not exist or be inaccessible."
            )
            event.ignore()
            return False

    def _move_folder_to_root(self, source_item: QTreeWidgetItem) -> bool:
        """
        Move folder to root level (make it a top-level folder).

        Args:
            source_item: Folder to move to root

        Returns:
            True if successful
        """
        # Validate source
        if not hasattr(source_item, 'folder_id'):
            return False

        source_id = source_item.folder_id

        # Extract name BEFORE reloading tree (item will be deleted)
        source_name = source_item.text(0).split(' (')[0]

        # Use move service to execute move
        success, message = self._move_service.move_folder_to_root(source_id, source_name)

        if success:
            # Defer reload to after drag operation completes
            QTimer.singleShot(0, lambda: self._reload_after_move(message))
            return True
        else:
            if "already at the root level" in message.lower():
                QMessageBox.information(self._tree, "Already at Root", message)
            else:
                QMessageBox.warning(self._tree, "Move Failed", message)
            return False

    def _move_folder_to_folder(
        self,
        source_item: QTreeWidgetItem,
        target_item: QTreeWidgetItem
    ) -> bool:
        """
        Move folder into another folder (create hierarchy).

        Args:
            source_item: Folder to move
            target_item: Target parent folder

        Returns:
            True if successful
        """
        # Validate source and target
        if not hasattr(source_item, 'folder_id') or not hasattr(target_item, 'folder_id'):
            return False

        source_id = source_item.folder_id
        target_id = target_item.folder_id

        # Extract names BEFORE reloading tree (items will be deleted)
        source_name = source_item.text(0).split(' (')[0]
        target_name = target_item.text(0).split(' (')[0]

        # Use move service to execute move
        success, message = self._move_service.move_folder_to_folder(
            source_id, target_id, source_name, target_name
        )

        if success:
            # Defer reload to after drag operation completes
            QTimer.singleShot(0, lambda: self._reload_after_move(message))
            return True
        else:
            QMessageBox.warning(self._tree, "Invalid Move", message)
            return False

    def _reload_after_move(self, message: str):
        """Reload tree after folder move with proper UI refresh."""
        self._reload_folders()
        # Force viewport repaint
        self._tree.viewport().update()
        QMessageBox.information(self._tree, "Folder Moved", message)


__all__ = ['FolderTreeDragHandler']
