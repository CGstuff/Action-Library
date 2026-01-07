"""
ArchiveService - Soft delete and recovery for animations (First Stage)

Provides archive functionality:
- Move animations to .archive folder instead of permanent delete
- Restore animations from archive back to library
- Move archived animations to trash (second stage before hard delete)
"""

import shutil
import logging
import time
import gc
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from ..config import Config
from .database_service import get_database_service, DatabaseService


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

    def _get_library_path(self) -> Optional[Path]:
        """Get configured library path"""
        return Config.load_library_path()

    def _get_archive_folder(self) -> Optional[Path]:
        """
        Get .archive folder path, creating if needed

        Returns:
            Path to .archive folder or None if library not configured
        """
        library_path = self._get_library_path()
        if not library_path:
            return None

        archive_folder = library_path / Config.ARCHIVE_FOLDER_NAME
        archive_folder.mkdir(parents=True, exist_ok=True)
        return archive_folder

    def _get_trash_folder(self) -> Optional[Path]:
        """
        Get .trash folder path, creating if needed

        Returns:
            Path to .trash folder or None if library not configured
        """
        library_path = self._get_library_path()
        if not library_path:
            return None

        trash_folder = library_path / Config.TRASH_FOLDER_NAME
        trash_folder.mkdir(parents=True, exist_ok=True)
        return trash_folder

    def _get_library_folder(self) -> Optional[Path]:
        """Get library/animations folder path"""
        library_path = self._get_library_path()
        if not library_path:
            return None
        return library_path / "library"

    def _copy_folder_contents(self, source_folder: Path, dest_folder: Path) -> Tuple[bool, List[str]]:
        """
        Copy folder contents file by file, handling locked files gracefully

        Args:
            source_folder: Source folder path
            dest_folder: Destination folder path

        Returns:
            Tuple of (all_success, list of failed files)
        """
        dest_folder.mkdir(parents=True, exist_ok=True)
        failed_files = []

        for file_path in source_folder.iterdir():
            dest_path = dest_folder / file_path.name
            try:
                if file_path.is_file():
                    # Try to copy with retry
                    for attempt in range(3):
                        try:
                            gc.collect()
                            shutil.copy2(str(file_path), str(dest_path))
                            break
                        except PermissionError:
                            if attempt < 2:
                                time.sleep(0.3)
                            else:
                                failed_files.append(file_path.name)
            except Exception as e:
                logger.warning(f"Failed to copy {file_path.name}: {e}")
                failed_files.append(file_path.name)

        return len(failed_files) == 0, failed_files

    def _delete_folder_contents(self, folder: Path, skip_files: List[str] = None) -> List[str]:
        """
        Delete folder contents, skipping specified files

        Args:
            folder: Folder to clean
            skip_files: Files to skip (still locked)

        Returns:
            List of files that couldn't be deleted
        """
        skip_files = skip_files or []
        still_locked = []

        for file_path in folder.iterdir():
            if file_path.name in skip_files:
                still_locked.append(file_path.name)
                continue

            try:
                gc.collect()
                if file_path.is_file():
                    file_path.unlink()
            except PermissionError:
                still_locked.append(file_path.name)
            except Exception as e:
                logger.warning(f"Failed to delete {file_path.name}: {e}")
                still_locked.append(file_path.name)

        # Try to remove folder if empty
        if not still_locked:
            try:
                folder.rmdir()
            except OSError:
                pass  # Not empty or locked

        return still_locked

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
            archive_folder = self._get_archive_folder()
            library_folder = self._get_library_folder()
            if not archive_folder or not library_folder:
                return False, "Library path not configured"

            # Source folder (library/{uuid}/)
            source_folder = library_folder / uuid
            if not source_folder.exists():
                # Files already gone - just remove from database
                self._db.delete_animation(uuid)
                return True, "Animation removed (files were already missing)"

            # Destination folder (.archive/{uuid}/)
            dest_folder = archive_folder / uuid

            # Handle existing archive item with same UUID
            if dest_folder.exists():
                try:
                    shutil.rmtree(dest_folder)
                except Exception:
                    pass  # Will be overwritten

            # Get folder info for restoration
            folder_id = animation.get('folder_id')
            folder_path = ""
            if folder_id:
                folder = self._db.get_folder_by_id(folder_id)
                if folder:
                    folder_path = folder.get('path', '')

            # Copy files to archive (more reliable than move on Windows)
            gc.collect()  # Release any Python file handles
            all_copied, failed_files = self._copy_folder_contents(source_folder, dest_folder)

            if not all_copied:
                logger.warning(f"Some files couldn't be copied to archive: {failed_files}")
                # Continue anyway - we'll archive what we can

            # Update thumbnail path to new location
            thumbnail_path = None
            new_thumb = dest_folder / f"{uuid}.png"
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
                except Exception:
                    pass
                return False, "Failed to add to archive database"

            # Remove from animations table first (so it's gone from UI)
            self._db.delete_animation(uuid)

            # Try to delete original files
            still_locked = self._delete_folder_contents(source_folder, failed_files)

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
            # Get archive item
            archive_item = self._db.get_archive_item(uuid)
            if not archive_item:
                return False, "Item not found in archive"

            # Get paths
            library_folder = self._get_library_folder()
            if not library_folder:
                return False, "Library path not configured"

            # Source folder (.archive/{uuid}/)
            source_folder = Path(archive_item['archive_folder_path'])
            if not source_folder.exists():
                # Files gone - just clean up database
                self._db.delete_from_archive(uuid)
                return False, "Archive files not found (already deleted?)"

            # Destination folder (library/{uuid}/)
            dest_folder = library_folder / uuid
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

            # Load animation data from JSON if available
            json_file = dest_folder / f"{uuid}.json"
            animation_data = None

            if json_file.exists():
                import json
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        animation_data = json.load(f)
                except Exception:
                    pass

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

            # Update file paths
            animation_data['blend_file_path'] = str(dest_folder / f"{uuid}.blend")
            animation_data['json_file_path'] = str(json_file) if json_file.exists() else None
            animation_data['thumbnail_path'] = str(dest_folder / f"{uuid}.png")
            animation_data['preview_path'] = str(dest_folder / f"{uuid}.webm")

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
            trash_folder = self._get_trash_folder()
            if not trash_folder:
                return False, "Library path not configured"

            # Source folder (.archive/{uuid}/)
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
                except Exception:
                    pass

            # Move files to trash
            shutil.move(str(source_folder), str(dest_folder))

            # Update thumbnail path to new location
            thumbnail_path = None
            new_thumb = dest_folder / f"{uuid}.png"
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
