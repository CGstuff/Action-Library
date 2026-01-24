"""
DatabaseService - SQLite database management facade

Pattern: Facade pattern with backwards-compatible API
Delegates to focused repository modules in services/database/
"""

import logging
import json
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager

from ..config import Config

logger = logging.getLogger(__name__)


def _atomic_json_write(file_path: Path, data: dict) -> bool:
    """
    Write JSON data atomically using temp file + rename pattern.

    This prevents data corruption if the process crashes mid-write.
    The rename operation is atomic on most filesystems.

    Args:
        file_path: Path to the JSON file
        data: Dictionary to write as JSON

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create temp file in same directory (for same filesystem atomic rename)
        dir_path = file_path.parent
        fd, temp_path = tempfile.mkstemp(suffix='.tmp', dir=str(dir_path))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Atomic rename (same filesystem)
            os.replace(temp_path, str(file_path))
            return True
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.warning(f"Atomic JSON write failed for {file_path}: {e}")
        return False

# Import from modular database package
from .database import (
    DatabaseConnection,
    SchemaManager,
    SCHEMA_VERSION,
    VERSION_FEATURES,
    backup_database,
    get_backups,
    delete_backup,
    AnimationRepository,
    FolderRepository,
    ArchiveRepository,
    TrashRepository,
    ReviewNotesRepository,
    LibraryScanner,
)


class DatabaseService:
    """
    Database service facade for animation metadata storage.

    This class provides a unified API while delegating to focused repositories.
    Maintains backwards compatibility with existing code.

    Features:
    - Thread-local connections for thread safety
    - WAL mode for better concurrency
    - Transaction support
    - Automatic schema initialization and migrations

    Usage:
        db = DatabaseService()
        animation_id = db.add_animation({...})
        animations = db.get_all_animations()

    Direct repository access (optional):
        db.animations.get_by_uuid(uuid)
        db.folders.get_all()
        db.archive.get_count()
        db.review_notes.get_notes_for_animation(uuid)
    """

    # Schema version (re-exported for compatibility)
    SCHEMA_VERSION = 4

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database service.

        Args:
            db_path: Path to database file (defaults to Config.get_database_path())
        """
        self.db_path = db_path or Config.get_database_path()

        # Initialize connection manager
        self._connection = DatabaseConnection(self.db_path)

        # Initialize schema
        self._schema = SchemaManager(self._connection)
        self._schema.init_database()

        # Initialize repositories
        self.animations = AnimationRepository(self._connection)
        self.folders = FolderRepository(self._connection)
        self.archive = ArchiveRepository(self._connection)
        self.trash = TrashRepository(self._connection)
        self.review_notes = ReviewNotesRepository(self._connection)

        # Initialize library scanner
        self._scanner = LibraryScanner(self._connection, self.animations, self.folders)

        # Legacy attribute for backwards compatibility
        self.local = self._connection._local

    # ==================== CONNECTION METHODS ====================

    def _get_connection(self):
        """Get thread-local database connection (backwards compatible)."""
        return self._connection.get_connection()

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        with self._connection.transaction() as conn:
            yield conn

    def close(self):
        """Close database connection for current thread."""
        self._connection.close()

    # ==================== FOLDER OPERATIONS (delegated) ====================

    def get_root_folder_id(self) -> int:
        """Get the ID of the root folder."""
        return self.folders.get_root_id()

    def create_folder(self, name: str, parent_id: Optional[int] = None,
                     description: str = "") -> Optional[int]:
        """Create new folder."""
        return self.folders.create(name, parent_id, description)

    def get_folder_by_id(self, folder_id: int) -> Optional[Dict[str, Any]]:
        """Get folder by ID."""
        return self.folders.get_by_id(folder_id)

    def get_folder_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get folder by its path string."""
        return self.folders.get_by_path(path)

    def get_all_folders(self) -> List[Dict[str, Any]]:
        """Get all folders."""
        return self.folders.get_all()

    def get_folder_descendants(self, folder_id: int) -> List[int]:
        """Get all descendant folder IDs (recursive)."""
        return self.folders.get_descendants(folder_id)

    def delete_folder(self, folder_id: int) -> bool:
        """Delete folder (and all contained animations via CASCADE)."""
        return self.folders.delete(folder_id)

    def update_folder_parent(self, folder_id: int, new_parent_id: int) -> bool:
        """Update folder's parent to create hierarchy."""
        return self.folders.update_parent(folder_id, new_parent_id)

    def ensure_folder_exists(self, path: str, description: str = None) -> Optional[int]:
        """Ensure folder hierarchy exists, creating missing folders."""
        return self.folders.ensure_exists(path, description)

    def get_all_folders_with_paths(self) -> List[Dict[str, Any]]:
        """Get all folders with their full paths."""
        return self.folders.get_all_with_paths()

    # ==================== ANIMATION OPERATIONS (delegated) ====================

    def add_animation(self, animation_data: Dict[str, Any]) -> Optional[int]:
        """Add animation to database."""
        return self.animations.add(animation_data)

    def get_animation_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get animation by UUID."""
        return self.animations.get_by_uuid(uuid)

    def get_animation_by_id(self, animation_id: int) -> Optional[Dict[str, Any]]:
        """Get animation by database ID."""
        return self.animations.get_by_id(animation_id)

    def get_all_animations(self, folder_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all animations, optionally filtered by folder."""
        return self.animations.get_all(folder_id)

    def update_animation(self, uuid: str, updates: Dict[str, Any]) -> bool:
        """Update animation metadata.

        Also syncs tags to JSON file if tags are being updated,
        which is important for version inheritance in Blender.
        """
        success = self.animations.update(uuid, updates)
        if success and 'tags' in updates:
            # Sync tags to JSON file
            self._update_animation_json_tags(uuid, updates['tags'])
        return success

    def _update_animation_json_tags(self, animation_uuid: str, tags) -> bool:
        """Update animation's JSON file with current tags.

        This keeps the JSON file in sync with the database, which is important
        for version inheritance when creating new versions in Blender.

        Uses atomic write (temp file + rename) to prevent corruption.
        """
        try:
            # Get animation to find JSON file path
            animation = self.animations.get_by_uuid(animation_uuid)
            if not animation:
                return False

            json_path = animation.get('json_file_path')
            if not json_path:
                return False

            json_file = Path(json_path)
            if not json_file.exists():
                return False

            # Read existing JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Update tags
            if isinstance(tags, list):
                data['tags'] = tags
            elif isinstance(tags, str):
                try:
                    data['tags'] = json.loads(tags)
                except json.JSONDecodeError:
                    data['tags'] = [t.strip() for t in tags.split(',') if t.strip()]

            # Write back atomically
            return _atomic_json_write(json_file, data)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {json_path}: {e}")
            return False
        except IOError as e:
            logger.warning(f"Could not update tags in {json_path}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Failed to sync tags to JSON: {e}")
            return False

    def rename_animation(self, uuid: str, new_name: str,
                         naming_fields: dict = None,
                         naming_template: str = None) -> bool:
        """
        Rename animation - updates folder, files, and database atomically.

        This method:
        1. Renames the folder on disk (if base name changes)
        2. Renames all files inside (.blend, .json, .webm, .png)
        3. Updates database with new name and file paths
        4. Rolls back file changes if database update fails

        Args:
            uuid: Animation UUID
            new_name: New animation name
            naming_fields: Optional naming fields dict
            naming_template: Optional naming template string

        Returns:
            True if successful
        """
        import re
        import json
        import time

        animation = self.get_animation_by_uuid(uuid)
        if not animation:
            return False

        old_name = animation['name']
        is_pose = animation.get('is_pose', 0)

        # Get current folder from blend_file_path
        old_blend_path = animation.get('blend_file_path', '')
        old_blend = Path(old_blend_path) if old_blend_path else None

        if not old_blend or not old_blend.exists():
            # Files don't exist - just update DB name and fields
            updates = {'name': new_name}
            if naming_fields:
                updates['naming_fields'] = json.dumps(naming_fields)
            if naming_template:
                updates['naming_template'] = naming_template
            return self.animations.update(uuid, updates)

        old_folder = old_blend.parent

        # Calculate new folder path based on base names
        old_base = Config.get_base_name(old_name)
        new_base = Config.get_base_name(new_name)

        # Determine parent folder (actions or poses)
        if is_pose:
            parent = Config.get_poses_folder()
        else:
            parent = Config.get_actions_folder()

        new_folder = parent / new_base

        # Sanitize filenames
        def sanitize(name: str) -> str:
            safe = re.sub(r'[<>:"/\\|?*]', '_', name)
            safe = safe.strip(' .') or 'unnamed'
            return re.sub(r'_+', '_', safe)

        safe_old = sanitize(old_name)
        safe_new = sanitize(new_name)

        # Helper to rename with retry (handles file lock delays)
        def rename_with_retry(src: Path, dst: Path, max_retries: int = 3, delay: float = 0.2):
            for attempt in range(max_retries):
                try:
                    src.rename(dst)
                    return True
                except PermissionError:
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        raise
            return False

        # Track completed operations for rollback
        completed_renames = []  # List of (new_path, old_path) tuples for rollback
        folder_renamed = False
        original_folder = old_folder

        try:
            # Handle folder rename if base name changed
            if old_base != new_base:
                if new_folder.exists():
                    # Conflict - append number to avoid overwrite
                    counter = 2
                    while (parent / f"{new_base}_{counter}").exists():
                        counter += 1
                    new_folder = parent / f"{new_base}_{counter}"

                # Rename folder with retry
                rename_with_retry(old_folder, new_folder)
                folder_renamed = True
            else:
                # Base name same, folder stays the same
                new_folder = old_folder

            # Rename files inside the folder
            new_paths = {}
            for ext, key in [('.blend', 'blend_file_path'), ('.json', 'json_file_path'),
                             ('.webm', 'preview_path'), ('.png', 'thumbnail_path')]:
                old_file = new_folder / f"{safe_old}{ext}"
                new_file = new_folder / f"{safe_new}{ext}"
                if old_file.exists() and old_file != new_file:
                    rename_with_retry(old_file, new_file)
                    completed_renames.append((new_file, old_file))
                new_paths[key] = str(new_file)

            # Update JSON file content with new name (atomic write)
            json_path = Path(new_paths.get('json_file_path', ''))
            original_json_content = None
            if json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        original_json_content = f.read()
                        json_data = json.loads(original_json_content)
                    json_data['name'] = new_name
                    if naming_fields:
                        json_data['naming_fields'] = naming_fields
                    if naming_template:
                        json_data['naming_template'] = naming_template
                    # Use atomic write to prevent corruption
                    _atomic_json_write(json_path, json_data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in {json_path}: {e}")
                except IOError as e:
                    logger.warning(f"Could not update JSON content in {json_path}: {e}")

            # Update database with new name and paths
            updates = {'name': new_name, **new_paths}
            if naming_fields:
                updates['naming_fields'] = json.dumps(naming_fields)
            if naming_template:
                updates['naming_template'] = naming_template

            db_success = self.animations.update(uuid, updates)

            if not db_success:
                # Database update failed - rollback file operations
                logger.error("Database update failed, rolling back file renames")
                self._rollback_renames(
                    completed_renames, folder_renamed, new_folder, original_folder,
                    json_path, original_json_content
                )
                return False

            return True

        except PermissionError as e:
            logger.error(f"Permission denied during rename: {e}")
            self._rollback_renames(
                completed_renames, folder_renamed, new_folder, original_folder,
                None, None
            )
            return False
        except OSError as e:
            logger.error(f"File operation failed during rename: {e}")
            self._rollback_renames(
                completed_renames, folder_renamed, new_folder, original_folder,
                None, None
            )
            return False
        except Exception as e:
            logger.error(f"Rename animation failed: {e}")
            self._rollback_renames(
                completed_renames, folder_renamed, new_folder, original_folder,
                None, None
            )
            return False

    def _rollback_renames(self, completed_renames: list, folder_renamed: bool,
                          new_folder: Path, original_folder: Path,
                          json_path: Optional[Path], original_json_content: Optional[str]):
        """
        Rollback file rename operations after a failure.

        Args:
            completed_renames: List of (new_path, old_path) tuples to reverse
            folder_renamed: Whether the folder was renamed
            new_folder: The new folder path (to rename back)
            original_folder: The original folder path
            json_path: Path to JSON file if content was modified
            original_json_content: Original JSON content to restore
        """
        # Restore JSON content first (before file renames)
        if json_path and original_json_content:
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    f.write(original_json_content)
            except Exception as e:
                logger.warning(f"Failed to restore JSON content: {e}")

        # Reverse file renames (in reverse order)
        for new_path, old_path in reversed(completed_renames):
            try:
                if new_path.exists():
                    new_path.rename(old_path)
            except Exception as e:
                logger.warning(f"Failed to rollback rename {new_path} -> {old_path}: {e}")

        # Reverse folder rename
        if folder_renamed and new_folder.exists():
            try:
                new_folder.rename(original_folder)
            except Exception as e:
                logger.warning(f"Failed to rollback folder rename: {e}")

    def delete_animation(self, uuid: str) -> bool:
        """Delete animation by UUID."""
        return self.animations.delete(uuid)

    def clear_all_animations(self) -> int:
        """Clear all animations from database for rebuild.

        Returns:
            Number of animations cleared
        """
        return self.animations.clear_all()

    def search_animations(self, query: str) -> List[Dict[str, Any]]:
        """Search animations by name or description."""
        return self.animations.search(query)

    def get_animation_count(self, folder_id: Optional[int] = None) -> int:
        """Get count of animations, optionally filtered by folder."""
        return self.animations.get_count(folder_id)

    def move_animation_to_folder(self, animation_uuid: str, folder_id: int) -> bool:
        """Move animation to a different folder and add folder name to tags.

        Also updates the JSON file to keep it in sync with the database,
        which is important for version inheritance in the Blender plugin.
        """
        # Update database
        success = self.animations.move_to_folder(animation_uuid, folder_id)
        if not success:
            return False

        # Update JSON file to keep it in sync
        self._update_animation_json_folder(animation_uuid, folder_id)
        return True

    def _update_animation_json_folder(self, animation_uuid: str, folder_id: int) -> bool:
        """Update animation's JSON file with current folder information.

        This keeps the JSON file in sync with the database, which is important
        for version inheritance when creating new versions in Blender.

        Uses atomic write (temp file + rename) to prevent corruption.
        """
        try:
            # Get animation to find JSON file path
            animation = self.animations.get_by_uuid(animation_uuid)
            if not animation:
                return False

            json_path = animation.get('json_file_path')
            if not json_path:
                return False

            json_file = Path(json_path)
            if not json_file.exists():
                return False

            # Get folder info for path
            folder = self.folders.get_by_id(folder_id)
            folder_path = folder.get('path', '') if folder else ''

            # Read existing JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Update folder fields
            data['folder_id'] = folder_id
            data['folder_path'] = folder_path

            # Also update tags to include folder name (matches database behavior)
            if folder and folder.get('name'):
                folder_name = folder['name']
                tags = data.get('tags', [])
                if isinstance(tags, list) and folder_name not in tags:
                    tags.append(folder_name)
                    data['tags'] = tags

            # Write back atomically
            return _atomic_json_write(json_file, data)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {json_path}: {e}")
            return False
        except IOError as e:
            logger.warning(f"Could not update folder in {json_path}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Failed to sync folder to JSON: {e}")
            return False

    # ==================== USER FEATURES (delegated) ====================

    def toggle_favorite(self, uuid: str) -> bool:
        """Toggle favorite status for an animation."""
        return self.animations.toggle_favorite(uuid)

    def set_favorite(self, uuid: str, is_favorite: bool) -> bool:
        """Set favorite status for an animation."""
        return self.animations.set_favorite(uuid, is_favorite)

    def get_favorite_animations(self) -> List[Dict[str, Any]]:
        """Get all favorite animations."""
        return self.animations.get_favorites()

    def update_last_viewed(self, uuid: str) -> bool:
        """Update last viewed timestamp for an animation."""
        return self.animations.update_last_viewed(uuid)

    def get_recent_animations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recently viewed animations."""
        return self.animations.get_recent(limit)

    def get_animations_filtered(
        self,
        folder_id: Optional[int] = None,
        rig_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        favorites_only: bool = False,
        sort_by: str = "name",
        sort_order: str = "ASC"
    ) -> List[Dict[str, Any]]:
        """Get animations with advanced filtering and sorting."""
        return self.animations.get_filtered(
            folder_id, rig_types, tags, favorites_only, sort_by, sort_order
        )

    def get_all_tags(self) -> List[str]:
        """Get all unique tags used across all animations."""
        return self.animations.get_all_tags()

    def get_all_rig_types(self) -> List[str]:
        """Get all unique rig types used across all animations."""
        return self.animations.get_all_rig_types()

    # ==================== VERSION OPERATIONS (delegated) ====================

    def get_version_history(self, version_group_id: str) -> List[Dict[str, Any]]:
        """Get all versions of an animation by version group ID."""
        return self.animations.get_version_history(version_group_id)

    def get_version_count(self, version_group_id: str) -> int:
        """Get count of versions in a version group."""
        return self.animations.get_version_count(version_group_id)

    def get_latest_version(self, version_group_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest version in a version group."""
        return self.animations.get_latest_version(version_group_id)

    def create_new_version(self, source_uuid: str, new_uuid: str,
                           file_updates: Dict[str, Any]) -> Optional[str]:
        """Create a new version of an animation."""
        return self.animations.create_new_version(source_uuid, new_uuid, file_updates)

    def set_version_as_latest(self, uuid: str) -> bool:
        """Set a specific version as the latest in its version group."""
        return self.animations.set_as_latest(uuid)

    def initialize_version_group(self, uuid: str) -> bool:
        """Initialize version tracking for an animation."""
        return self.animations.initialize_version_group(uuid)

    # ==================== STATUS OPERATIONS (delegated) ====================

    def set_status(self, uuid: str, status: str) -> bool:
        """Set lifecycle status for an animation."""
        return self.animations.set_status(uuid, status)

    def get_status(self, uuid: str) -> Optional[str]:
        """Get lifecycle status for an animation."""
        return self.animations.get_status(uuid)

    # ==================== REVIEW NOTES OPERATIONS (delegated) ====================

    def get_review_notes(self, animation_uuid: str) -> List[Dict[str, Any]]:
        """Get all review notes for an animation, ordered by frame."""
        return self.review_notes.get_notes_for_animation(animation_uuid)

    def add_review_note(
        self,
        animation_uuid: str,
        frame: int,
        note: str,
        author: str = ''
    ) -> Optional[int]:
        """Add a new review note to an animation."""
        return self.review_notes.add_note(animation_uuid, frame, note, author)

    def update_review_note(self, note_id: int, note: str) -> bool:
        """Update a review note's text content."""
        return self.review_notes.update_note(note_id, note)

    def update_review_note_frame(self, note_id: int, frame: int) -> bool:
        """Update a review note's frame number."""
        return self.review_notes.update_note_frame(note_id, frame)

    def delete_review_note(self, note_id: int) -> bool:
        """Delete a review note."""
        return self.review_notes.delete_note(note_id)

    def toggle_review_note_resolved(self, note_id: int) -> Optional[bool]:
        """Toggle a review note's resolved status. Returns new status."""
        return self.review_notes.toggle_resolved(note_id)

    def set_review_note_resolved(self, note_id: int, resolved: bool) -> bool:
        """Set a review note's resolved status."""
        return self.review_notes.set_resolved(note_id, resolved)

    def get_review_note_count(self, animation_uuid: str) -> int:
        """Get count of review notes for an animation."""
        return self.review_notes.get_note_count(animation_uuid)

    def get_unresolved_review_note_count(self, animation_uuid: str) -> int:
        """Get count of unresolved review notes for an animation."""
        return self.review_notes.get_unresolved_count(animation_uuid)

    # ==================== ARCHIVE OPERATIONS (delegated) ====================

    def add_to_archive(self, archive_data: Dict[str, Any]) -> Optional[int]:
        """Add animation to archive table (soft delete)."""
        return self.archive.add(archive_data)

    def get_archive_item(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get archive item by UUID."""
        return self.archive.get_by_uuid(uuid)

    def get_all_archive_items(self) -> List[Dict[str, Any]]:
        """Get all items in archive."""
        return self.archive.get_all()

    def delete_from_archive(self, uuid: str) -> bool:
        """Remove item from archive table."""
        return self.archive.delete(uuid)

    def get_archive_count(self) -> int:
        """Get number of items in archive."""
        return self.archive.get_count()

    def get_archive_total_size(self) -> float:
        """Get total size of all items in archive."""
        return self.archive.get_total_size()

    def is_uuid_in_archive(self, uuid: str) -> bool:
        """Check if a UUID exists in archive."""
        return self.archive.exists(uuid)

    # ==================== TRASH OPERATIONS (delegated) ====================

    def add_to_trash(self, trash_data: Dict[str, Any]) -> Optional[int]:
        """Add animation to trash table (staging for hard delete)."""
        return self.trash.add(trash_data)

    def get_trash_item(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get trash item by UUID."""
        return self.trash.get_by_uuid(uuid)

    def get_all_trash_items(self) -> List[Dict[str, Any]]:
        """Get all items in trash."""
        return self.trash.get_all()

    def delete_from_trash(self, uuid: str) -> bool:
        """Remove item from trash table."""
        return self.trash.delete(uuid)

    def get_trash_count(self) -> int:
        """Get number of items in trash."""
        return self.trash.get_count()

    def is_uuid_in_trash(self, uuid: str) -> bool:
        """Check if a UUID exists in trash."""
        return self.trash.exists(uuid)

    # ==================== LIBRARY SCANNING (delegated) ====================

    def import_animation_from_json(self, json_file_path: Path) -> bool:
        """Import animation from JSON file into database."""
        return self._scanner.import_from_json(json_file_path)

    def scan_library_folder(self, library_path: Path) -> Tuple[int, int]:
        """Scan library folder for animations and import them."""
        return self._scanner.scan_folder(library_path)

    def sync_library(self) -> Tuple[int, int]:
        """Sync library with database (scan configured library path)."""
        library_path = Config.load_library_path()
        if not library_path:
            return (0, 0)
        result = self._scanner.sync_library(library_path)

        # Fix pose flags for existing animations (in case they were imported before is_pose was added)
        self.fix_pose_flags()

        # Migrate existing animations to actions/poses folder structure
        self._migrate_to_actions_poses_folders()

        return result

    def fix_pose_flags(self) -> int:
        """Fix is_pose flag for animations that should be poses (frame_count = 1)."""
        return self.animations.fix_pose_flags()

    # ==================== METADATA EXPORT/IMPORT (delegated) ====================

    def get_all_animation_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all animations, keyed by UUID."""
        return self._scanner.get_all_metadata()

    def update_animation_metadata_by_uuid(self, uuid: str, metadata: Dict[str, Any]) -> bool:
        """Update metadata fields for an animation by UUID."""
        return self._scanner.update_metadata_by_uuid(uuid, metadata)

    # ==================== DATABASE MAINTENANCE ====================

    def _migrate_to_actions_poses_folders(self) -> int:
        """
        Migrate existing animations from library/ root to library/actions/ or library/poses/.

        This method:
        1. Finds animations stored directly in library/{name}/ (old structure)
        2. Moves them to library/actions/{name}/ or library/poses/{name}/
        3. Updates database paths

        Returns:
            Number of animations migrated
        """
        import shutil

        migrated_count = 0

        try:
            library_folder = Config.get_library_folder()
            actions_folder = Config.get_actions_folder()
            poses_folder = Config.get_poses_folder()
        except ValueError:
            # Library not configured
            return 0

        # Get all animations (latest versions only)
        animations = self.animations.get_all(include_all_versions=False)

        for anim in animations:
            blend_path_str = anim.get('blend_file_path', '')
            if not blend_path_str:
                continue

            blend_path = Path(blend_path_str)
            if not blend_path.exists():
                continue

            current_folder = blend_path.parent

            # Skip if already in actions/ or poses/
            try:
                if current_folder.parent == actions_folder:
                    continue
                if current_folder.parent == poses_folder:
                    continue
                # Also check if parent's parent is actions/poses (nested structure)
                if current_folder.parent.parent == actions_folder:
                    continue
                if current_folder.parent.parent == poses_folder:
                    continue
            except (AttributeError, TypeError):
                # Path doesn't have expected parent structure
                pass

            # Only migrate if directly in library/ folder
            if current_folder.parent != library_folder:
                continue

            # Determine target based on is_pose flag
            is_pose = anim.get('is_pose', 0)
            target_parent = poses_folder if is_pose else actions_folder
            target_folder = target_parent / current_folder.name

            # Skip if target already exists
            if target_folder.exists():
                continue

            try:
                # Move the folder
                shutil.move(str(current_folder), str(target_folder))

                # Update database paths
                self._update_animation_paths_after_move(anim['uuid'], target_folder)
                migrated_count += 1
                logger.info(f"Moved {current_folder.name} to {'poses' if is_pose else 'actions'}/")

            except PermissionError as e:
                logger.warning(f"Permission denied migrating {current_folder.name}: {e}")
                continue
            except OSError as e:
                logger.warning(f"Failed to migrate {current_folder.name}: {e}")
                continue

        if migrated_count > 0:
            logger.info(f"Migrated {migrated_count} animations to new folder structure")

        return migrated_count

    def _update_animation_paths_after_move(self, uuid: str, new_folder: Path) -> bool:
        """
        Update database paths after moving an animation folder.

        Args:
            uuid: Animation UUID
            new_folder: New folder path

        Returns:
            True if successful
        """
        animation = self.get_animation_by_uuid(uuid)
        if not animation:
            return False

        name = animation.get('name', '')
        import re
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        safe_name = safe_name.strip(' .') or 'unnamed'
        safe_name = re.sub(r'_+', '_', safe_name)

        # Build new paths
        new_paths = {
            'blend_file_path': str(new_folder / f"{safe_name}.blend"),
            'json_file_path': str(new_folder / f"{safe_name}.json"),
            'preview_path': str(new_folder / f"{safe_name}.webm"),
            'thumbnail_path': str(new_folder / f"{safe_name}.png"),
        }

        return self.animations.update(uuid, new_paths)

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics for status display.

        Returns:
            Dict containing schema version, record counts, file size, pending features, etc.
        """
        return self._schema.get_database_stats()

    def run_integrity_check(self) -> Tuple[bool, str]:
        """
        Run database integrity check.

        Returns:
            Tuple of (is_ok, message)
        """
        return self._schema.run_integrity_check()

    def optimize_database(self) -> Tuple[int, int]:
        """
        Optimize database by running VACUUM.

        Returns:
            Tuple of (size_before, size_after) in bytes
        """
        return self._schema.optimize_database()

    def get_current_schema_version(self) -> int:
        """Get current schema version."""
        return self._schema.get_current_version()

    def create_backup(self) -> Path:
        """
        Create a backup of the database.

        Returns:
            Path to the backup file
        """
        return backup_database(self.db_path)

    def get_backups(self) -> List[Dict[str, Any]]:
        """
        Get list of existing backups.

        Returns:
            List of backup info dicts with 'path', 'size', 'date'
        """
        return get_backups(self.db_path)

    def delete_backup(self, backup_path: Path) -> bool:
        """
        Delete a backup file.

        Args:
            backup_path: Path to the backup file

        Returns:
            True if deleted successfully
        """
        return delete_backup(backup_path)

    def run_schema_upgrade(self) -> Tuple[bool, str]:
        """
        Run schema upgrade (migrations).

        Creates a backup first, then runs init_database() to apply migrations.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get current version before upgrade
            before_version = self._schema.get_current_version()

            # Create backup before migration
            backup_path = self.create_backup()

            # Run migrations
            self._schema.init_database()

            # Get version after upgrade
            after_version = self._schema.get_current_version()

            if after_version > before_version:
                return True, f"Upgraded from v{before_version} to v{after_version}. Backup created at: {backup_path}"
            else:
                return True, f"Already at latest version (v{after_version}). Backup created at: {backup_path}"

        except Exception as e:
            return False, f"Upgrade failed: {str(e)}"


# Singleton instance
_database_service_instance: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """
    Get global DatabaseService singleton instance.

    Returns:
        Global DatabaseService instance
    """
    global _database_service_instance
    if _database_service_instance is None:
        _database_service_instance = DatabaseService()
    return _database_service_instance


__all__ = ['DatabaseService', 'get_database_service']
