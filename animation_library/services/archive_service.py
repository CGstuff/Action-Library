"""
ArchiveService - Soft delete and recovery for animations (First Stage)

Provides archive functionality:
- Move animations to .archive folder instead of permanent delete
- Restore animations from archive back to library
- Move archived animations to trash (second stage before hard delete)
"""

import shutil
import logging
import gc
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .database_service import get_database_service, DatabaseService
from .utils.path_utils import (
    get_library_path,
    get_library_folder,
    get_archive_folder,
    get_trash_folder,
)
from .utils.file_operations import (
    safe_copy_folder_contents,
    safe_delete_folder_contents,
)


logger = logging.getLogger(__name__)


class ArchiveService:
    """
    Service for managing archive operations (first stage of deletion)

    Features:
    - Soft delete: Move files to .archive folder, remove from animations table
    - Restore: Move files back to library, re-add to animations table
    - Move to trash: Stage archived items for permanent deletion
    """

    def __init__(self, db_service: Optional[DatabaseService] = None):
        """
        Initialize archive service

        Args:
            db_service: Database service instance (uses singleton if not provided)
        """
        self._db = db_service or get_database_service()

    def move_to_archive(self, uuid: str) -> Tuple[bool, str]:
        """
        Move animation to archive (soft delete)

        Args:
            uuid: Animation UUID to archive

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get animation data
            animation = self._db.get_animation_by_uuid(uuid)
            if not animation:
                return False, "Animation not found"

            # Get paths
            archive_folder = get_archive_folder()
            if not archive_folder:
                return False, "Library path not configured"

            # Source folder - derive from stored file paths
            blend_path = animation.get('blend_file_path')
            json_path = animation.get('json_file_path')
            source_path = blend_path or json_path
            if not source_path:
                self._db.delete_animation(uuid)
                return True, "Animation removed (no file paths stored)"

            source_folder = Path(source_path).parent
            if not source_folder.exists():
                # Files already gone - just remove from database
                self._db.delete_animation(uuid)
                return True, "Animation removed (files were already missing)"

            # Destination folder (.deleted/{uuid}/)
            dest_folder = archive_folder / uuid

            # Handle existing archive item with same UUID
            if dest_folder.exists():
                try:
                    shutil.rmtree(dest_folder)
                except PermissionError as e:
                    logger.warning(f"Permission denied removing existing archive folder {dest_folder}: {e}")
                except OSError as e:
                    logger.warning(f"Could not remove existing archive folder {dest_folder}: {e}")

            # Get folder info for restoration
            folder_id = animation.get('folder_id')
            folder_path = ""
            if folder_id:
                folder = self._db.get_folder_by_id(folder_id)
                if folder:
                    folder_path = folder.get('path', '')

            # Copy files to archive (more reliable than move on Windows)
            gc.collect()  # Release any Python file handles
            all_copied, failed_files = safe_copy_folder_contents(source_folder, dest_folder)

            if not all_copied:
                logger.warning(f"Some files couldn't be copied to archive: {failed_files}")
                # Continue anyway - we'll archive what we can

            # Update thumbnail path to new location
            thumbnail_path = None
            new_thumb = dest_folder / "thumbnail.png"
            if new_thumb.exists():
                thumbnail_path = str(new_thumb)

            # Add to archive table
            archive_data = {
                'uuid': uuid,
                'name': animation.get('name', 'Unknown'),
                'original_folder_id': folder_id,
                'original_folder_path': folder_path,
                'rig_type': animation.get('rig_type'),
                'frame_count': animation.get('frame_count'),
                'duration_seconds': animation.get('duration_seconds'),
                'file_size_mb': animation.get('file_size_mb'),
                'archive_folder_path': str(dest_folder),
                'thumbnail_path': thumbnail_path,
                'original_created_date': animation.get('created_date')
            }

            result = self._db.add_to_archive(archive_data)
            if not result:
                # Rollback - remove copied files
                try:
                    shutil.rmtree(dest_folder)
                except PermissionError as e:
                    logger.warning(f"Rollback failed - permission denied removing {dest_folder}: {e}")
                except OSError as e:
                    logger.warning(f"Rollback failed - could not remove {dest_folder}: {e}")
                return False, "Failed to add to archive database"

            # Remove from animations table first (so it's gone from UI)
            self._db.delete_animation(uuid)

            # Try to delete original files
            still_locked = safe_delete_folder_contents(source_folder, skip_files=failed_files)

            if still_locked:
                logger.info(f"Some files still locked, will be cleaned up later: {still_locked}")
                # Files will be orphaned but that's OK - they'll be cleaned up on next scan

            logger.info(f"Moved animation '{animation.get('name')}' to archive")
            return True, "Moved to archive"

        except Exception as e:
            logger.error(f"Failed to move animation to archive: {e}")
            return False, f"Error: {str(e)}"

    def restore_from_archive(self, uuid: str, target_folder_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Restore animation from archive back to library

        Args:
            uuid: Animation UUID to restore
            target_folder_id: Optional folder ID to restore to (uses original if not specified)

        Returns:
            Tuple of (success, message)
        """
        try:
            import re

            # Get archive item
            archive_item = self._db.get_archive_item(uuid)
            if not archive_item:
                return False, "Item not found in archive"

            # Get paths
            library_folder = get_library_folder()
            if not library_folder:
                return False, "Library path not configured"

            # Source folder (.deleted/{uuid}/)
            source_folder = Path(archive_item['archive_folder_path'])
            if not source_folder.exists():
                # Files gone - just clean up database
                self._db.delete_from_archive(uuid)
                return False, "Archive files not found (already deleted?)"

            # Destination folder - use animation base name (human-readable)
            animation_name = archive_item.get('name', 'unnamed')

            # Get base name (strip version suffix) for folder
            base_name = re.sub(r'_v\d{2,4}$', '', animation_name)
            safe_base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
            safe_base_name = safe_base_name.strip(' .') or 'unnamed'
            safe_base_name = re.sub(r'_+', '_', safe_base_name)

            # Folder name: {base_name}/ (human-readable, no UUID)
            dest_folder = library_folder / safe_base_name

            if dest_folder.exists():
                # Check if it's already in the database
                existing = self._db.get_animation_by_uuid(uuid)
                if existing:
                    # Already restored - just clean up archive record
                    self._db.delete_from_archive(uuid)
                    logger.info(f"Animation {uuid} already in library, cleaned up archive record")
                    return True, "Animation already restored"
                else:
                    # Folder exists but not in DB - remove orphan folder and continue
                    shutil.rmtree(str(dest_folder))
                    logger.warning(f"Removed orphan folder for {uuid}")

            # Determine target folder
            folder_id = target_folder_id
            if folder_id is None:
                folder_id = archive_item.get('original_folder_id')

            # Validate folder exists (or use root)
            if folder_id:
                folder = self._db.get_folder_by_id(folder_id)
                if not folder:
                    # Original folder deleted - use root
                    folder_id = self._db.get_root_folder_id()
            else:
                folder_id = self._db.get_root_folder_id()

            # Move files back to library
            shutil.move(str(source_folder), str(dest_folder))

            # Sanitize full animation name (with version) for filenames
            safe_anim_name = re.sub(r'[<>:"/\\|?*]', '_', animation_name)
            safe_anim_name = safe_anim_name.strip(' .') or 'unnamed'
            safe_anim_name = re.sub(r'_+', '_', safe_anim_name)

            # Load animation data from JSON if available
            # Try name-based file first, then any .json file in folder
            json_file = dest_folder / f"{safe_anim_name}.json"
            if not json_file.exists():
                json_files = list(dest_folder.glob("*.json"))
                json_file = json_files[0] if json_files else None

            animation_data = None
            if json_file and json_file.exists():
                import json
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        animation_data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in {json_file}: {e}")
                except IOError as e:
                    logger.warning(f"Could not read {json_file}: {e}")

            if not animation_data:
                # Reconstruct minimal data from archive record
                animation_data = {
                    'uuid': uuid,
                    'name': archive_item.get('name', 'Restored Animation'),
                    'rig_type': archive_item.get('rig_type', 'unknown'),
                    'frame_count': archive_item.get('frame_count'),
                    'duration_seconds': archive_item.get('duration_seconds'),
                    'file_size_mb': archive_item.get('file_size_mb'),
                    'created_date': archive_item.get('original_created_date')
                }

            # Ensure uuid is set
            animation_data['uuid'] = uuid
            animation_data['folder_id'] = folder_id

            # Update file paths - files use animation name with version: walk_cycle_v001.blend
            animation_data['blend_file_path'] = str(dest_folder / f"{safe_anim_name}.blend")
            animation_data['json_file_path'] = str(json_file) if json_file and json_file.exists() else None
            animation_data['thumbnail_path'] = str(dest_folder / f"{safe_anim_name}.png")
            animation_data['preview_path'] = str(dest_folder / f"{safe_anim_name}.webm")

            # Add back to animations table
            result = self._db.add_animation(animation_data)
            if not result:
                # Rollback - move files back to archive
                shutil.move(str(dest_folder), str(source_folder))
                return False, "Failed to restore to database"

            # Remove from archive table
            self._db.delete_from_archive(uuid)

            logger.info(f"Restored animation '{archive_item.get('name')}' from archive")
            return True, "Animation restored successfully"

        except Exception as e:
            logger.error(f"Failed to restore animation from archive: {e}")
            return False, f"Error: {str(e)}"

    def move_to_trash(self, uuid: str) -> Tuple[bool, str]:
        """
        Move archived animation to trash (second stage before hard delete)

        Args:
            uuid: Animation UUID to move to trash

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get archive item
            archive_item = self._db.get_archive_item(uuid)
            if not archive_item:
                return False, "Item not found in archive"

            # Get paths
            trash_folder = get_trash_folder()
            if not trash_folder:
                return False, "Library path not configured"

            # Source folder (.deleted/{uuid}/)
            source_folder = Path(archive_item['archive_folder_path'])
            if not source_folder.exists():
                # Files gone - just clean up database
                self._db.delete_from_archive(uuid)
                return False, "Archive files not found"

            # Destination folder (.trash/{uuid}/)
            dest_folder = trash_folder / uuid

            # Handle existing trash item with same UUID
            if dest_folder.exists():
                try:
                    shutil.rmtree(dest_folder)
                except PermissionError as e:
                    logger.warning(f"Permission denied removing existing trash folder {dest_folder}: {e}")
                except OSError as e:
                    logger.warning(f"Could not remove existing trash folder {dest_folder}: {e}")

            # Move files to trash
            shutil.move(str(source_folder), str(dest_folder))

            # Update thumbnail path to new location
            thumbnail_path = None
            new_thumb = dest_folder / "thumbnail.png"
            if new_thumb.exists():
                thumbnail_path = str(new_thumb)

            # Add to trash table
            trash_data = {
                'uuid': uuid,
                'name': archive_item.get('name', 'Unknown'),
                'trash_folder_path': str(dest_folder),
                'thumbnail_path': thumbnail_path,
                'archived_date': archive_item.get('archived_date')
            }

            result = self._db.add_to_trash(trash_data)
            if not result:
                # Rollback - move files back to archive
                shutil.move(str(dest_folder), str(source_folder))
                return False, "Failed to add to trash database"

            # Remove from archive table
            self._db.delete_from_archive(uuid)

            logger.info(f"Moved '{archive_item.get('name')}' from archive to trash")
            return True, "Moved to trash"

        except Exception as e:
            logger.error(f"Failed to move to trash: {e}")
            return False, f"Error: {str(e)}"

    def get_archive_items(self) -> List[Dict[str, Any]]:
        """
        Get all items in archive

        Returns:
            List of archive item dicts
        """
        return self._db.get_all_archive_items()

    def get_archive_count(self) -> int:
        """Get number of items in archive"""
        return self._db.get_archive_count()

    def get_archive_size(self) -> float:
        """Get total size of archive in MB"""
        return self._db.get_archive_total_size()

    def is_in_archive(self, uuid: str) -> bool:
        """Check if UUID is in archive"""
        return self._db.is_uuid_in_archive(uuid)


# Singleton instance
_archive_service_instance: Optional[ArchiveService] = None


def get_archive_service() -> ArchiveService:
    """
    Get global ArchiveService singleton instance

    Returns:
        Global ArchiveService instance
    """
    global _archive_service_instance
    if _archive_service_instance is None:
        _archive_service_instance = ArchiveService()
    return _archive_service_instance


__all__ = ['ArchiveService', 'get_archive_service']
