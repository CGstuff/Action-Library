"""
FolderTreeContextMenu - Builds context menus for folder tree items

Extracts context menu logic from FolderTree for better separation of concerns.
"""

from typing import Dict, Callable, Optional
from PyQt6.QtWidgets import QMenu, QWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt


class FolderTreeContextMenu:
    """
    Builds context menus for folder tree items.

    Handles:
    - User folder menus (rename, delete, change icon)
    - Archive folder menu (empty archive)
    - Trash folder menu (empty trash)
    - Empty space menu (create folder)
    """

    def __init__(self, parent: QWidget, callbacks: Dict[str, Callable]):
        """
        Initialize context menu builder.

        Args:
            parent: Parent widget for menus
            callbacks: Dict of callback functions:
                - 'change_icon': fn(item) - Change folder icon
                - 'rename': fn(item) - Rename folder
                - 'delete': fn(item) - Delete folder
                - 'create': fn() - Create new folder
                - 'empty_archive': fn() - Empty archive
                - 'empty_trash': fn() - Empty trash
        """
        self._parent = parent
        self._callbacks = callbacks

    def show_context_menu(self, item: Optional[QTreeWidgetItem], global_pos) -> None:
        """
        Show appropriate context menu for item at position.

        Args:
            item: Tree item at click position (None for empty space)
            global_pos: Global position for menu
        """
        if item:
            data = item.data(0, Qt.ItemDataRole.UserRole)

            if data and data.get('type') == 'user':
                self._show_user_folder_menu(item, global_pos)
            elif data and data.get('folder_name') == 'Archive':
                self._show_archive_menu(global_pos)
            elif data and data.get('folder_name') == 'Trash':
                self._show_trash_menu(global_pos)
            # Virtual folders (All Animations, etc.) have no context menu
        else:
            self._show_empty_space_menu(global_pos)

    def _show_user_folder_menu(self, item: QTreeWidgetItem, global_pos) -> None:
        """Show context menu for user folder."""
        menu = QMenu(self._parent)

        icon_action = menu.addAction("Change Icon...")
        menu.addSeparator()
        rename_action = menu.addAction("Rename Folder")
        delete_action = menu.addAction("Delete Folder")

        action = menu.exec(global_pos)

        if action == icon_action:
            self._invoke_callback('change_icon', item)
        elif action == rename_action:
            self._invoke_callback('rename', item)
        elif action == delete_action:
            self._invoke_callback('delete', item)

    def _show_archive_menu(self, global_pos) -> None:
        """Show context menu for Archive folder."""
        menu = QMenu(self._parent)

        empty_action = menu.addAction("Move All to Trash...")

        action = menu.exec(global_pos)

        if action == empty_action:
            self._invoke_callback('empty_archive')

    def _show_trash_menu(self, global_pos) -> None:
        """Show context menu for Trash folder."""
        menu = QMenu(self._parent)

        empty_action = menu.addAction("Empty Trash...")

        action = menu.exec(global_pos)

        if action == empty_action:
            self._invoke_callback('empty_trash')

    def _show_empty_space_menu(self, global_pos) -> None:
        """Show context menu for empty space (create folder)."""
        menu = QMenu(self._parent)

        create_action = menu.addAction("Create Folder")

        action = menu.exec(global_pos)

        if action == create_action:
            self._invoke_callback('create')

    def _invoke_callback(self, name: str, *args) -> None:
        """Safely invoke a callback by name."""
        callback = self._callbacks.get(name)
        if callback:
            callback(*args)


__all__ = ['FolderTreeContextMenu']
