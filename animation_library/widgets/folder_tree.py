"""
FolderTree - Folder navigation tree

Pattern: QTreeWidget for folder hierarchy
Inspired by: Current animation_library folder structure
"""

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu, QAbstractItemView, QCheckBox, QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QSize
from PyQt6.QtGui import QIcon, QAction, QFont

from ..config import Config
from ..services.database_service import get_database_service
from ..services.folder_icon_service import get_folder_icon_service
from ..services.folder_move_service import FolderMoveService
from ..events.event_bus import get_event_bus
from ..utils.icon_loader import IconLoader
from ..themes.theme_manager import get_theme_manager


class FolderTree(QTreeWidget):
    """
    Tree widget for folder navigation

    Features:
    - Virtual folders (All Animations, Recent, Favorites)
    - User folders from database
    - Context menus (create, rename, delete)
    - Drag & drop support (TODO: Phase 5+)
    - Selection handling

    Layout:
        All Animations
        Recent
        Favorites
        ───────────────
        User Folder 1
        User Folder 2
          └─ Subfolder
    """

    # Signals
    folder_selected = pyqtSignal(int, str, bool)  # folder_id, folder_name, recursive
    recursive_search_changed = pyqtSignal(bool)  # recursive state

    def __init__(self, parent=None):
        super().__init__(parent)

        # Services
        self._db_service = get_database_service()
        self._event_bus = get_event_bus()
        self._icon_service = get_folder_icon_service(self._db_service)
        self._move_service = FolderMoveService(self._db_service)

        # Load folder icons
        self._folder_icons = self._load_folder_icons()

        # Track dragged folder for folder-to-folder dragging
        self._dragged_folder_item = None

        # Recursive search setting (search subfolders)
        self._recursive_search = True  # Default to recursive

        # Setup tree
        self._setup_tree()
        self._load_folders()
        self._connect_signals()

    def _setup_tree(self):
        """Configure tree widget"""

        # Hide header
        self.setHeaderHidden(True)

        # Selection
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)

        # Enable drag drop for folder management
        self.setDragEnabled(True)  # Enable folder dragging
        self.setAcceptDrops(True)   # Can receive animation cards
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Alternating colors
        self.setAlternatingRowColors(True)

        # Set minimum width
        self.setMinimumWidth(200)

        # Setup custom branch indicators (expand/collapse arrows)
        self._setup_branch_indicators()

        # Apply initial folder text/icon size from theme
        theme_manager = get_theme_manager()
        self._update_folder_style(theme_manager.get_folder_text_size())

    def _setup_branch_indicators(self):
        """Setup custom expand/collapse arrow indicators for tree branches"""
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.text_primary if theme else "#e0e0e0"

        # Get arrow icon paths
        arrow_right_path = IconLoader.get("arrow_right")
        arrow_down_path = IconLoader.get("arrow_down")

        # Convert paths to Windows format for QSS
        arrow_right_path = arrow_right_path.replace('\\', '/')
        arrow_down_path = arrow_down_path.replace('\\', '/')

        # Apply QSS for custom branch indicators
        # Note: Since we can't colorize SVG directly in QSS, we use the default icons
        # The theme's text color will be applied via the palette
        branch_style = f"""
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                image: url({arrow_right_path});
                padding: 2px;
            }}

            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {{
                image: url({arrow_down_path});
                padding: 2px;
            }}

            QTreeView::branch:has-children:!has-siblings:closed:hover,
            QTreeView::branch:closed:has-children:has-siblings:hover,
            QTreeView::branch:open:has-children:!has-siblings:hover,
            QTreeView::branch:open:has-children:has-siblings:hover {{
                background-color: rgba(255, 255, 255, 30);
            }}
        """

        current_style = self.styleSheet()
        self.setStyleSheet(current_style + branch_style)

    def _connect_signals(self):
        """Connect internal signals"""

        # Selection changed
        self.itemSelectionChanged.connect(self._on_selection_changed)

        # Context menu
        self.customContextMenuRequested.connect(self._on_context_menu)

        # Expand/collapse events for icon changes
        self.itemExpanded.connect(self._on_item_expanded)
        self.itemCollapsed.connect(self._on_item_collapsed)

        # Event bus - folder selected
        self._event_bus.folder_selected.connect(self._on_folder_selected_external)

        # Theme changes - reload branch indicators and icons
        theme_manager = get_theme_manager()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        theme_manager.folder_text_size_changed.connect(self._update_folder_style)

    def _load_folders(self):
        """Load folders from database and create tree"""
        self.clear()

        # Create virtual folders
        self._create_virtual_folders()

        # Add separator
        separator = QTreeWidgetItem(self)
        separator.setText(0, "─" * 20)
        separator.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable

        # Load user folders from database
        self._load_user_folders()

        # Select "All Animations" by default
        if self.topLevelItemCount() > 0:
            first_item = self.topLevelItem(0)
            self.setCurrentItem(first_item)

    def _create_virtual_folders(self):
        """Create virtual folders with icons"""
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.folder_icon_color if theme else "#D4AF37"

        # Map folder names to icon keys
        virtual_folder_icons = {
            "All Animations": "root_icon",
            "Favorites": "favorite_icon",
            "Recent": "recent_icon",
        }

        for folder_name in Config.VIRTUAL_FOLDERS:
            item = QTreeWidgetItem(self)
            item.setText(0, folder_name)

            # Set icon if available
            icon_key = virtual_folder_icons.get(folder_name)
            if icon_key:
                icon_path = IconLoader.get(icon_key)
                icon = IconLoader.colorize_icon(icon_path, icon_color)
                item.setIcon(0, icon)

            # Store metadata
            item.setData(0, Qt.ItemDataRole.UserRole, {
                'type': 'virtual',
                'folder_id': None,
                'folder_name': folder_name
            })

            # Make bold
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)

    def _load_folder_icons(self):
        """Load folder preset icons"""
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.folder_icon_color if theme else "#D4AF37"

        icons = {}
        for preset in self._icon_service.get_all_presets():
            icon_path = IconLoader.get(preset['icon_key'])
            icons[preset['id']] = IconLoader.colorize_icon(icon_path, icon_color)

        return icons

    def _load_user_folders(self):
        """Load user folders from database and build tree hierarchy"""

        folders = self._db_service.get_all_folders()

        # Build folder lookup dictionary
        folder_dict = {folder['id']: folder for folder in folders}

        # Find root folder ID
        root_folder_id = None
        for folder in folders:
            if folder.get('parent_id') is None:
                root_folder_id = folder['id']
                break

        # Build tree recursively starting from root's children
        if root_folder_id:
            self._build_folder_tree(root_folder_id, folder_dict, None)

    def _build_folder_tree(self, parent_id: int, folder_dict: dict, parent_item: QTreeWidgetItem = None):
        """
        Recursively build folder tree

        Args:
            parent_id: Parent folder ID to find children for
            folder_dict: Dictionary of all folders {id: folder_data}
            parent_item: Parent QTreeWidgetItem (None for top-level)
        """
        # Find all children of this parent
        children = [f for f in folder_dict.values() if f.get('parent_id') == parent_id]

        # Sort children by name
        children.sort(key=lambda f: f['name'].lower())

        for folder in children:
            # Create tree item
            if parent_item is None:
                # Top-level item (child of root folder)
                item = QTreeWidgetItem(self)
            else:
                # Child of another folder
                item = QTreeWidgetItem(parent_item)

            item.setText(0, folder['name'])

            # Store metadata
            item.setData(0, Qt.ItemDataRole.UserRole, {
                'type': 'user',
                'folder_id': folder['id'],
                'folder_name': folder['name'],
                'folder_path': folder.get('path', '')
            })

            # Store folder ID and path for drag-drop and icon operations
            item.folder_id = folder['id']
            item.folder_path = folder.get('path', '')

            # Set folder icon (will be updated on expand/collapse)
            self._update_folder_icon(item, is_expanded=False)

            # Recursively build children
            self._build_folder_tree(folder['id'], folder_dict, item)

    def _update_folder_icon(self, item: QTreeWidgetItem, is_expanded: bool):
        """
        Update folder icon based on expand state and custom icon

        Args:
            item: Tree item to update
            is_expanded: True if folder is expanded, False if collapsed
        """
        if not hasattr(item, 'folder_path'):
            return

        folder_path = item.folder_path
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.folder_icon_color if theme else "#D4AF37"

        # Check if folder has a custom preset icon (using path for portability)
        icon_id = self._icon_service.get_folder_icon(folder_path)
        if icon_id and icon_id in self._folder_icons:
            # Use custom preset icon (doesn't change with expand/collapse)
            item.setIcon(0, self._folder_icons[icon_id])
        else:
            # Use default folder icon with open/closed state
            if is_expanded:
                icon_path = IconLoader.get("folder_open")
            else:
                icon_path = IconLoader.get("folder_closed")

            icon = IconLoader.colorize_icon(icon_path, icon_color)
            item.setIcon(0, icon)

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Handle folder expansion - update to open folder icon"""
        self._update_folder_icon(item, is_expanded=True)

    def _on_item_collapsed(self, item: QTreeWidgetItem):
        """Handle folder collapse - update to closed folder icon"""
        self._update_folder_icon(item, is_expanded=False)

    def _on_theme_changed(self, theme_name: str):
        """Handle theme change - reload branch indicators and all folder icons"""
        # Get new theme color for folder icons
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.folder_icon_color if theme else "#D4AF37"

        # Reload folder icons with new theme color
        self._folder_icons = self._load_folder_icons()

        # Refresh branch indicators
        self._setup_branch_indicators()

        # Map of virtual folder names to icon keys
        virtual_folder_icons = {
            "All Animations": "root_icon",
            "Favorites": "favorite_icon",
            "Recent": "recent_icon",
        }

        # Update all folder icons in the tree
        def update_item_icons(item: QTreeWidgetItem):
            # Check if it's a virtual folder
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get('type') == 'virtual':
                folder_name = data.get('folder_name')
                icon_key = virtual_folder_icons.get(folder_name)
                if icon_key:
                    icon_path = IconLoader.get(icon_key)
                    icon = IconLoader.colorize_icon(icon_path, icon_color)
                    item.setIcon(0, icon)
            elif hasattr(item, 'folder_id'):
                is_expanded = item.isExpanded()
                self._update_folder_icon(item, is_expanded)

            # Recursively update children
            for i in range(item.childCount()):
                update_item_icons(item.child(i))

        # Update all top-level items and their children
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item:
                update_item_icons(item)

        # Also update folder style (font/icon size)
        self._update_folder_style(get_theme_manager().get_folder_text_size())

    def _update_folder_style(self, size: int):
        """
        Update folder tree font and icon sizes

        Args:
            size: Font size in points (8-20)
        """
        # Update font
        font = self.font()
        font.setPointSize(size)
        self.setFont(font)

        # Update icon size (font size + 4)
        icon_size = size + 4
        self.setIconSize(QSize(icon_size, icon_size))

    def _on_selection_changed(self):
        """Handle selection change"""

        selected_items = self.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if not data:
            return

        folder_id = data.get('folder_id')
        folder_name = data.get('folder_name')

        # Emit signal with recursive flag
        self.folder_selected.emit(folder_id if folder_id else -1, folder_name, self._recursive_search)

        # Update event bus
        self._event_bus.set_folder(folder_name)

    def _on_folder_selected_external(self, folder_name: str):
        """Handle folder selection from event bus"""

        # Find item with this name
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)

            if data and data.get('folder_name') == folder_name:
                self.setCurrentItem(item)
                break

    def _on_context_menu(self, position: QPoint):
        """Handle context menu request"""

        item = self.itemAt(position)

        menu = QMenu(self)

        if item:
            data = item.data(0, Qt.ItemDataRole.UserRole)

            if data and data.get('type') == 'user':
                # User folder context menu
                icon_action = menu.addAction("Change Icon...")
                menu.addSeparator()
                rename_action = menu.addAction("Rename Folder")
                delete_action = menu.addAction("Delete Folder")

                action = menu.exec(self.viewport().mapToGlobal(position))

                if action == icon_action:
                    self._change_folder_icon(item)
                elif action == rename_action:
                    self._rename_folder(item)
                elif action == delete_action:
                    self._delete_folder(item)
        else:
            # Empty space - create new folder
            create_action = menu.addAction("Create Folder")

            action = menu.exec(self.viewport().mapToGlobal(position))

            if action == create_action:
                self.create_folder_with_dialog()

    def create_folder_with_dialog(self):
        """Show dialog and create new folder (called from header button)"""
        from PyQt6.QtWidgets import QInputDialog, QMessageBox

        # Get parent folder from selection, or default to Root folder
        parent_id = None
        selected_items = self.selectedItems()
        if selected_items:
            item = selected_items[0]
            # Only use as parent if it's a user folder (not virtual)
            if hasattr(item, 'folder_id'):
                parent_id = item.folder_id

        # If no folder selected, use Root folder as parent
        if parent_id is None:
            parent_id = self._db_service.get_root_folder_id()

        # Show input dialog
        folder_name, ok = QInputDialog.getText(
            self,
            "Create New Folder",
            "Folder name:",
            text="New Folder"
        )

        if not ok or not folder_name.strip():
            return  # User cancelled or empty name

        folder_name = folder_name.strip()

        # Create folder in database
        folder_id = self._db_service.create_folder(
            name=folder_name,
            parent_id=parent_id
        )

        if folder_id:
            # Reload tree to show new folder
            self._load_folders()

            # Show success message
            parent_path = ""
            if parent_id:
                parent_folder = self._db_service.get_folder_by_id(parent_id)
                if parent_folder:
                    parent_path = f" under '{parent_folder['name']}'"

            QMessageBox.information(
                self,
                "Folder Created",
                f"Created folder '{folder_name}'{parent_path}"
            )
        else:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to create folder '{folder_name}'.\n\nA folder with this name may already exist at this location."
            )

    def _rename_folder(self, item: QTreeWidgetItem):
        """Rename folder"""
        # TODO: Show input dialog
        pass

    def _delete_folder(self, item: QTreeWidgetItem):
        """Delete folder"""

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        folder_id = data.get('folder_id')
        if not folder_id:
            return

        # TODO: Show confirmation dialog

        if self._db_service.delete_folder(folder_id):
            # Reload tree
            self._load_folders()

    def _change_folder_icon(self, item: QTreeWidgetItem):
        """Show icon picker and change folder icon"""
        from .dialogs.icon_picker_dialog import IconPickerDialog

        if not hasattr(item, 'folder_path'):
            return

        folder_path = item.folder_path
        current_icon = self._icon_service.get_folder_icon(folder_path)
        presets = self._icon_service.get_all_presets()

        dialog = IconPickerDialog(presets, current_icon, self)
        if dialog.exec():
            selected_icon = dialog.get_selected_icon()
            if selected_icon:
                self._icon_service.set_folder_icon(folder_path, selected_icon)
                self._load_folders()  # Reload to show new icon

    def refresh(self):
        """Refresh folder tree"""
        self._load_folders()

    def startDrag(self, supportedActions):
        """Store dragged folder item before drag starts"""
        selected = self.selectedItems()
        if selected:
            self._dragged_folder_item = selected[0]
        super().startDrag(supportedActions)

    def dragEnterEvent(self, event):
        """Accept animation card OR folder drops"""
        mime_data = event.mimeData()

        # Accept both animation UUID drops AND internal folder drags
        if (mime_data.hasFormat('application/x-animation-uuid') or
            mime_data.hasFormat('application/x-qabstractitemmodeldatalist')):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Highlight target folder during drag"""
        mime_data = event.mimeData()
        item = self.itemAt(event.position().toPoint())

        if not item:
            event.ignore()
            return

        # Accept both animation cards and folder drags
        if (mime_data.hasFormat('application/x-animation-uuid') or
            mime_data.hasFormat('application/x-qabstractitemmodeldatalist')):
            # Highlight drop target
            self.setCurrentItem(item)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle animation card OR folder drop"""
        mime_data = event.mimeData()

        # Check if this is a folder drag (internal tree drag)
        if mime_data.hasFormat('application/x-qabstractitemmodeldatalist'):
            # Folder-to-folder drag
            target_item = self.itemAt(event.position().toPoint())

            if self._dragged_folder_item:
                # Handle different drop targets
                if target_item is None:
                    # Dropped on empty space → move to root level
                    if self._move_folder_to_root(self._dragged_folder_item):
                        event.setDropAction(Qt.DropAction.MoveAction)
                        event.accept()
                        self._dragged_folder_item = None
                        return
                elif not hasattr(target_item, 'folder_id'):
                    # Dropped on virtual folder (All Animations, etc.) → move to root level
                    if self._move_folder_to_root(self._dragged_folder_item):
                        event.setDropAction(Qt.DropAction.MoveAction)
                        event.accept()
                        self._dragged_folder_item = None
                        return
                else:
                    # Dropped on user folder → create hierarchy
                    if self._move_folder_to_folder(self._dragged_folder_item, target_item):
                        event.setDropAction(Qt.DropAction.MoveAction)
                        event.accept()
                        self._dragged_folder_item = None
                        return

            event.ignore()
            return

        # Handle animation UUID drops (existing code)
        if not mime_data.hasFormat('application/x-animation-uuid'):
            event.ignore()
            return

        # Get target folder item
        target_item = self.itemAt(event.position().toPoint())
        if not target_item:
            event.ignore()
            return

        # Extract animation UUID(s) from MIME data
        try:
            uuid_data = bytes(mime_data.data('application/x-animation-uuid')).decode('utf-8')
            animation_uuids = [u.strip() for u in uuid_data.strip().split('\n') if u.strip()]

            if not animation_uuids:
                event.ignore()
                return
        except (UnicodeDecodeError, AttributeError) as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Drag Error", f"Failed to decode animation data: {e}")
            event.ignore()
            return

        # Get target folder ID
        # Virtual folders (All, Recent, Favorites) have no folder_id attribute
        if not hasattr(target_item, 'folder_id'):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Cannot Move",
                "Cannot move animations to virtual folders"
            )
            event.ignore()
            return

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
            # Refresh displays
            event.acceptProposedAction()

            # Emit signal to refresh animation list
            from ..events.event_bus import get_event_bus
            event_bus = get_event_bus()
            event_bus.folder_changed.emit(target_folder_id)

            # Show success message
            folder_name = target_item.text(0).split(' (')[0]  # Remove count
            from PyQt6.QtWidgets import QMessageBox

            if failed_count > 0:
                QMessageBox.warning(
                    self,
                    "Partially Moved",
                    f"Moved {success_count} animation(s) to '{folder_name}'.\n\n{failed_count} failed."
                )
            else:
                QMessageBox.information(
                    self,
                    "Moved",
                    f"Moved {success_count} animation(s) to '{folder_name}'"
                )
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Move Failed",
                f"Failed to move any animations. They may not exist or be inaccessible."
            )
            event.ignore()

    def _move_folder_to_root(self, source_item: QTreeWidgetItem) -> bool:
        """
        Move folder to root level (make it a top-level folder)

        Args:
            source_item: Folder to move to root

        Returns:
            True if successful
        """
        from PyQt6.QtWidgets import QMessageBox

        # Validate source
        if not hasattr(source_item, 'folder_id'):
            return False

        source_id = source_item.folder_id

        # Extract name BEFORE reloading tree (item will be deleted)
        source_name = source_item.text(0).split(' (')[0]

        # Use move service to execute move
        success, message = self._move_service.move_folder_to_root(source_id, source_name)

        if success:
            # Defer reload to after drag operation completes to prevent Qt rendering bug
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._reload_after_move(message))
            return True
        else:
            # Show appropriate message based on error
            if "already at the root level" in message.lower():
                QMessageBox.information(self, "Already at Root", message)
            else:
                QMessageBox.warning(self, "Move Failed", message)
            return False

    def _move_folder_to_folder(self, source_item: QTreeWidgetItem, target_item: QTreeWidgetItem) -> bool:
        """Move folder into another folder (create hierarchy)"""
        from PyQt6.QtWidgets import QMessageBox

        # Validate source and target
        if not hasattr(source_item, 'folder_id') or not hasattr(target_item, 'folder_id'):
            return False

        source_id = source_item.folder_id
        target_id = target_item.folder_id

        # Extract names BEFORE reloading tree (items will be deleted)
        source_name = source_item.text(0).split(' (')[0]
        target_name = target_item.text(0).split(' (')[0]

        # Use move service to execute move
        success, message = self._move_service.move_folder_to_folder(source_id, target_id, source_name, target_name)

        if success:
            # Defer reload to after drag operation completes to prevent Qt rendering bug
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._reload_after_move(message))
            return True
        else:
            QMessageBox.warning(self, "Invalid Move", message)
            return False

    def _reload_after_move(self, message: str):
        """Reload tree after folder move with proper UI refresh"""
        from PyQt6.QtWidgets import QMessageBox

        self._load_folders()
        # Force viewport repaint to prevent Qt rendering bug
        self.viewport().update()

        QMessageBox.information(self, "Folder Moved", message)

    # ==================== RECURSIVE SEARCH ====================

    def get_recursive_search(self) -> bool:
        """
        Get recursive search state

        Returns:
            bool: True if searching subfolders, False for current folder only
        """
        return self._recursive_search

    def set_recursive_search(self, recursive: bool):
        """
        Set recursive search state

        Args:
            recursive: True to search subfolders, False for current folder only
        """
        if self._recursive_search != recursive:
            self._recursive_search = recursive
            self.recursive_search_changed.emit(recursive)

            # Re-emit current folder selection with new recursive state
            selected_items = self.selectedItems()
            if selected_items:
                item = selected_items[0]
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data:
                    folder_id = data.get('folder_id')
                    folder_name = data.get('folder_name')
                    self.folder_selected.emit(folder_id if folder_id else -1, folder_name, self._recursive_search)


__all__ = ['FolderTree']
