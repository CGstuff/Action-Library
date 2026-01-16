"""
Database Module - Modular database operations

This module provides focused database repositories:
- connection: Thread-safe connection management
- schema: Schema initialization and migrations
- helpers: Shared utility functions
- animations: Animation CRUD operations
- folders: Folder hierarchy management
- archive: Archive (soft delete) operations
- trash: Trash (hard delete staging) operations
- review_notes: Frame-specific review notes for dailies
- library_scanner: Library scanning and metadata
"""

from .connection import DatabaseConnection
from .schema import (
    SchemaManager,
    SCHEMA_VERSION,
    VERSION_FEATURES,
    migrate_legacy_database,
    backup_database,
    get_backups,
    delete_backup,
)
from .helpers import (
    deserialize_animation,
    serialize_tags,
    row_to_dict,
    rows_to_list,
    is_valid_uuid,
    parse_json_field
)
from .animations import AnimationRepository
from .folders import FolderRepository
from .archive import ArchiveRepository
from .trash import TrashRepository
from .review_notes import ReviewNotesRepository
from .library_scanner import LibraryScanner

__all__ = [
    # Connection
    'DatabaseConnection',
    # Schema
    'SchemaManager',
    'SCHEMA_VERSION',
    'VERSION_FEATURES',
    'migrate_legacy_database',
    'backup_database',
    'get_backups',
    'delete_backup',
    # Helpers
    'deserialize_animation',
    'serialize_tags',
    'row_to_dict',
    'rows_to_list',
    'is_valid_uuid',
    'parse_json_field',
    # Repositories
    'AnimationRepository',
    'FolderRepository',
    'ArchiveRepository',
    'TrashRepository',
    'ReviewNotesRepository',
    'LibraryScanner',
]
