"""
FolderMoveService - Validate and execute folder move operations

Pattern: Service layer for folder hierarchy management
Responsibilities:
- Validate folder move operations (prevent circular references)
- Execute folder-to-folder moves
- Execute folder-to-root moves
- Check descendant relationships
"""

from typing import Optional, Tuple
from .database_service import DatabaseService


class FolderMoveService:
    """
    Service for validating and executing folder moves

    This service handles all folder move logic including:
    - Moving folders into other folders (creating hierarchy)
    - Moving folders to root level
    - Preventing circular references (moving folder into its own child)
    - Validation of move operations

    Usage:
        move_service = FolderMoveService(db_service)

        # Validate move
        can_move, error_msg = move_service.can_move_to_folder(source_id, target_id)
        if not can_move:
            print(f"Cannot move: {error_msg}")
            return

        # Execute move
        success, message = move_service.move_folder_to_folder(source_id, target_id)
        if success:
            print(f"Success: {message}")
        else:
            print(f"Failed: {message}")
    """

    def __init__(self, db_service: DatabaseService):
        """
        Initialize folder move service

        Args:
            db_service: Database service for folder operations
        """
        self._db_service = db_service

    def can_move_to_folder(self, source_id: int, target_id: int) -> Tuple[bool, str]:
        """
        Validate if folder can be moved into another folder

        Args:
            source_id: ID of folder to move
            target_id: ID of target parent folder

        Returns:
            (is_valid, error_message) - error_message is empty string if valid
        """
        # Cannot drop onto self
        if source_id == target_id:
            return False, "Cannot move folder into itself"

        # Cannot drop into own descendant (check by parent_id chain)
        if self._is_descendant(target_id, source_id):
            return False, "Cannot move folder into its own subfolder (circular reference)"

        # Valid move
        return True, ""

    def can_move_to_root(self, source_id: int) -> Tuple[bool, str]:
        """
        Validate if folder can be moved to root level

        Args:
            source_id: ID of folder to move

        Returns:
            (is_valid, error_message) - error_message is empty string if valid
        """
        # Get root folder ID
        root_id = self._db_service.get_root_folder_id()
        if not root_id:
            return False, "Could not find root folder"

        # Check if already at root level
        folder = self._db_service.get_folder_by_id(source_id)
        if folder and folder.get('parent_id') == root_id:
            return False, "Folder is already at the root level"

        # Valid move
        return True, ""

    def move_folder_to_folder(self, source_id: int, target_id: int, source_name: str = "", target_name: str = "") -> Tuple[bool, str]:
        """
        Move folder into another folder (create hierarchy)

        Args:
            source_id: ID of folder to move
            target_id: ID of target parent folder
            source_name: Name of source folder (for message, optional)
            target_name: Name of target folder (for message, optional)

        Returns:
            (success, message) - message describes result
        """
        # Validate move first
        can_move, error = self.can_move_to_folder(source_id, target_id)
        if not can_move:
            return False, error

        # Update parent_id in database
        if self._db_service.update_folder_parent(source_id, target_id):
            if source_name and target_name:
                return True, f"Moved '{source_name}' into '{target_name}'"
            else:
                return True, "Folder moved successfully"
        else:
            return False, "Failed to move folder"

    def move_folder_to_root(self, source_id: int, source_name: str = "") -> Tuple[bool, str]:
        """
        Move folder to root level (make it a top-level folder)

        Args:
            source_id: ID of folder to move
            source_name: Name of source folder (for message, optional)

        Returns:
            (success, message) - message describes result
        """
        # Validate move first
        can_move, error = self.can_move_to_root(source_id)
        if not can_move:
            return False, error

        # Get root folder ID
        root_id = self._db_service.get_root_folder_id()
        if not root_id:
            return False, "Could not find root folder"

        # Update parent_id to root
        if self._db_service.update_folder_parent(source_id, root_id):
            if source_name:
                return True, f"Moved '{source_name}' to root level"
            else:
                return True, "Moved folder to root level"
        else:
            return False, "Failed to move folder to root"

    def _is_descendant(self, folder_id: int, ancestor_id: int) -> bool:
        """
        Check if folder_id is a descendant of ancestor_id

        This walks up the parent chain from folder_id to check if
        ancestor_id appears anywhere in the hierarchy.

        Args:
            folder_id: Folder to check
            ancestor_id: Potential ancestor folder

        Returns:
            True if folder_id is a child/grandchild/etc. of ancestor_id
        """
        # Get folder info
        folder = self._db_service.get_folder_by_id(folder_id)
        if not folder:
            return False

        # Walk up parent chain
        current_id = folder.get('parent_id')
        visited = set()

        while current_id:
            if current_id == ancestor_id:
                return True

            if current_id in visited:
                break  # Circular ref detected
            visited.add(current_id)

            parent = self._db_service.get_folder_by_id(current_id)
            if not parent:
                break

            current_id = parent.get('parent_id')

        return False


__all__ = ['FolderMoveService']
