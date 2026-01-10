"""
TrashService - Hard deletion staging for animations (Second Stage)

Provides trash functionality:
- Staging area before permanent deletion
- Restore to archive (move back to .archive folder)
- Permanent delete (hard delete with setting check)
- Empty trash (delete all)
"""

import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from ..config import Config
from .database_service import get_database_service, DatabaseService
from .utils.path_utils import get_archive_folder, get_trash_folder


logger = logging.getLogger(__name__)


class TrashService:
    """
    Service for managing trash operations (second stage - hard delete staging)

    Features:
    - Restore to archive: Move files back to .archive folder
    - Permanent delete: Hard delete (if setting enabled)
    - Empty trash: Delete all items (if setting enabled)
    """

    def __init__(self, db_service: Optional[DatabaseService] = None):
        """
        Initialize trash service

        Args:
            db_service: Database service instance (uses singleton if not provided)
        """
        self._db = db_service or get_database_service()

    def _is_hard_delete_allowed(self) -> bool:
        """Check if hard delete is allowed based on settings"""
        return Config.load_allow_hard_delete()

    def restore_to_archive(self, uuid: str) -> Tuple[bool, str]:
        """
        Restore animation from trash back to archive

        Args:
            uuid: Animation UUID to restore

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get trash item
            trash_item = self._db.get_trash_item(uuid)
            if not trash_item:
                return False, "Item not found in trash"

            # Get paths
            archive_folder = get_archive_folder()
            if not archive_folder:
                return False, "Library path not configured"

            # Source folder (.trash/{uuid}/)
            source_folder = Path(trash_item['trash_folder_path'])
            if not source_folder.exists():
                # Files gone - just clean up database
                self._db.delete_from_trash(uuid)
                return False, "Trash files not found"

            # Destination folder (.archive/{uuid}/)
            dest_folder = archive_folder / uuid

            # Handle existing archive item with same UUID
            if dest_folder.exists():
                return False, "Item already exists in archive"

            # Move files back to archive
            shutil.move(str(source_folder), str(dest_folder))

            # Update thumbnail path to new location
            thumbnail_path = None
            new_thumb = dest_folder / f"{uuid}.png"
            if new_thumb.exists():
                thumbnail_path = str(new_thumb)

            # Add to archive table
            # Note: We only have minimal data from trash, so we reconstruct what we can
            archive_data = {
                'uuid': uuid,
                'name': trash_item.get('name', 'Unknown'),
                'archive_folder_path': str(dest_folder),
                'thumbnail_path': thumbnail_path,
                # Preserve original archived_date if available
                'original_created_date': trash_item.get('archived_date')
            }

            result = self._db.add_to_archive(archive_data)
            if not result:
                # Rollback - move files back to trash
                shutil.move(str(dest_folder), str(source_folder))
                return False, "Failed to add to archive database"

            # Remove from trash table
            self._db.delete_from_trash(uuid)

            logger.info(f"Restored '{trash_item.get('name')}' from trash to archive")
            return True, "Restored to archive"

        except Exception as e:
            logger.error(f"Failed to restore to archive: {e}")
            return False, f"Error: {str(e)}"

    def permanently_delete(self, uuid: str, force: bool = False) -> Tuple[bool, str]:
        """
        Permanently delete animation from trash (hard delete)

        Args:
            uuid: Animation UUID to permanently delete
            force: If True, skip the ALLOW_HARD_DELETE check

        Returns:
            Tuple of (success, message)
        """
        # Check if hard delete is allowed
        if not force and not self._is_hard_delete_allowed():
            return False, "Hard delete is disabled. Enable it in Settings to permanently delete."

        try:
            # Get trash item
            trash_item = self._db.get_trash_item(uuid)
            if not trash_item:
                return False, "Item not found in trash"

            # Delete files
            trash_folder = Path(trash_item['trash_folder_path'])
            if trash_folder.exists():
                shutil.rmtree(trash_folder)

            # Remove from trash table
            self._db.delete_from_trash(uuid)

            logger.info(f"Permanently deleted animation '{trash_item.get('name')}'")
            return True, "Permanently deleted"

        except Exception as e:
            logger.error(f"Failed to permanently delete: {e}")
            return False, f"Error: {str(e)}"

    def empty_trash(self, force: bool = False) -> Tuple[int, int, str]:
        """
        Delete all items in trash permanently

        Args:
            force: If True, skip the ALLOW_HARD_DELETE check

        Returns:
            Tuple of (deleted_count, error_count, message)
        """
        # Check if hard delete is allowed
        if not force and not self._is_hard_delete_allowed():
            return 0, 0, "Hard delete is disabled. Enable it in Settings to empty trash."

        deleted = 0
        errors = 0

        trash_items = self._db.get_all_trash_items()
        for item in trash_items:
            success, _ = self.permanently_delete(item['uuid'], force=True)
            if success:
                deleted += 1
            else:
                errors += 1

        logger.info(f"Emptied trash: {deleted} deleted, {errors} errors")
        return deleted, errors, f"Deleted {deleted} item(s)" if deleted > 0 else "Trash is empty"

    def get_trash_items(self) -> List[Dict[str, Any]]:
        """
        Get all items in trash

        Returns:
            List of trash item dicts
        """
        return self._db.get_all_trash_items()

    def get_trash_count(self) -> int:
        """Get number of items in trash"""
        return self._db.get_trash_count()

    def is_in_trash(self, uuid: str) -> bool:
        """Check if UUID is in trash"""
        return self._db.is_uuid_in_trash(uuid)

    def is_hard_delete_allowed(self) -> bool:
        """Check if hard delete is allowed in settings"""
        return self._is_hard_delete_allowed()


# Singleton instance
_trash_service_instance: Optional[TrashService] = None


def get_trash_service() -> TrashService:
    """
    Get global TrashService singleton instance

    Returns:
        Global TrashService instance
    """
    global _trash_service_instance
    if _trash_service_instance is None:
        _trash_service_instance = TrashService()
    return _trash_service_instance


__all__ = ['TrashService', 'get_trash_service']
