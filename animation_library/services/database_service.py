"""
DatabaseService - SQLite database management facade

Pattern: Facade pattern with backwards-compatible API
Delegates to focused repository modules in services/database/
"""

from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager

from ..config import Config

# Import from modular database package
from .database import (
    DatabaseConnection,
    SchemaManager,
    migrate_legacy_database,
    AnimationRepository,
    FolderRepository,
    ArchiveRepository,
    TrashRepository,
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
    """

    # Schema version (re-exported for compatibility)
    SCHEMA_VERSION = 4

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database service.

        Args:
            db_path: Path to database file (defaults to Config.get_database_path())
        """
        # Check for legacy database migration first
        if db_path is None:
            migrate_legacy_database(
                Config.get_database_path(),
                Config.get_legacy_database_path()
            )

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
        """Update animation metadata."""
        return self.animations.update(uuid, updates)

    def delete_animation(self, uuid: str) -> bool:
        """Delete animation by UUID."""
        return self.animations.delete(uuid)

    def search_animations(self, query: str) -> List[Dict[str, Any]]:
        """Search animations by name or description."""
        return self.animations.search(query)

    def get_animation_count(self, folder_id: Optional[int] = None) -> int:
        """Get count of animations, optionally filtered by folder."""
        return self.animations.get_count(folder_id)

    def move_animation_to_folder(self, animation_uuid: str, folder_id: int) -> bool:
        """Move animation to a different folder and add folder name to tags."""
        return self.animations.move_to_folder(animation_uuid, folder_id)

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
        return self._scanner.sync_library(library_path)

    # ==================== METADATA EXPORT/IMPORT (delegated) ====================

    def get_all_animation_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all animations, keyed by UUID."""
        return self._scanner.get_all_metadata()

    def update_animation_metadata_by_uuid(self, uuid: str, metadata: Dict[str, Any]) -> bool:
        """Update metadata fields for an animation by UUID."""
        return self._scanner.update_metadata_by_uuid(uuid, metadata)


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
