"""
Database Schema - Schema initialization and migrations

Manages database schema versions and migration logic.
"""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from .connection import DatabaseConnection


# Current schema version
SCHEMA_VERSION = 4


class SchemaManager:
    """
    Database schema management.

    Handles:
    - Initial schema creation
    - Version tracking
    - Incremental migrations
    - Legacy database migration
    """

    def __init__(self, connection: DatabaseConnection):
        """
        Initialize schema manager.

        Args:
            connection: Database connection manager
        """
        self._conn = connection

    def init_database(self):
        """Initialize database schema and check for migrations."""
        with self._conn.transaction() as conn:
            cursor = conn.cursor()

            # Schema version table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Check current version
            cursor.execute('SELECT MAX(version) FROM schema_version')
            result = cursor.fetchone()
            current_version = result[0] if result[0] is not None else 0

            # Apply migrations if needed
            if current_version == 0:
                # Fresh install - create full schema
                self._create_schema(cursor)
                cursor.execute(
                    'INSERT OR REPLACE INTO schema_version (version) VALUES (?)',
                    (SCHEMA_VERSION,)
                )
            elif current_version < SCHEMA_VERSION:
                # Incremental migrations
                if current_version < 2:
                    self._migrate_to_v2(cursor)
                if current_version < 3:
                    self._migrate_to_v3(cursor)
                if current_version < 4:
                    self._migrate_to_v4(cursor)
                cursor.execute(
                    'INSERT OR REPLACE INTO schema_version (version) VALUES (?)',
                    (SCHEMA_VERSION,)
                )

    def _create_schema(self, cursor: sqlite3.Cursor):
        """Create database schema."""

        # Folders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                path TEXT UNIQUE,
                description TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES folders (id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folders_path ON folders(path)')

        # Animations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS animations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                folder_id INTEGER NOT NULL,

                -- Rig Information
                rig_type TEXT NOT NULL,
                armature_name TEXT,
                bone_count INTEGER,

                -- Animation Timing
                frame_start INTEGER,
                frame_end INTEGER,
                frame_count INTEGER,
                duration_seconds REAL,
                fps INTEGER,

                -- File Information
                blend_file_path TEXT,
                json_file_path TEXT,
                preview_path TEXT,
                thumbnail_path TEXT,
                file_size_mb REAL,

                -- Organization
                tags TEXT,
                author TEXT,

                -- Custom Thumbnail Gradient
                use_custom_thumbnail_gradient INTEGER DEFAULT 0,
                thumbnail_gradient_top TEXT,
                thumbnail_gradient_bottom TEXT,

                -- User Features (v2)
                is_favorite INTEGER DEFAULT 0,
                last_viewed_date TIMESTAMP,
                custom_order INTEGER,
                is_locked INTEGER DEFAULT 0,

                -- Timestamps
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE
            )
        ''')

        # Create indexes for fast queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_uuid ON animations(uuid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_folder ON animations(folder_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_rig_type ON animations(rig_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_name ON animations(name)')

        # v2 indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_favorite ON animations(is_favorite)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_last_viewed ON animations(last_viewed_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_custom_order ON animations(custom_order)')

        # Archive table (v4) - for soft-deleted animations (indefinite retention)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,

                -- Original location info for restoration
                original_folder_id INTEGER,
                original_folder_path TEXT,

                -- Animation metadata (for display in archive view)
                rig_type TEXT,
                frame_count INTEGER,
                duration_seconds REAL,
                file_size_mb REAL,

                -- File paths
                archive_folder_path TEXT NOT NULL,
                thumbnail_path TEXT,

                -- Timestamps
                archived_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                original_created_date TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_archive_uuid ON archive(uuid)')

        # Trash table (v4) - staging area for permanent deletion
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trash (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,

                -- File paths
                trash_folder_path TEXT NOT NULL,
                thumbnail_path TEXT,

                -- Timestamps
                trashed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                archived_date TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_uuid ON trash(uuid)')

        # Create root folder if it doesn't exist
        cursor.execute('SELECT id FROM folders WHERE parent_id IS NULL LIMIT 1')
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO folders (name, parent_id, path, created_date, modified_date)
                VALUES (?, ?, ?, ?, ?)
            ''', ("Root", None, "", datetime.now(), datetime.now()))

    def _migrate_to_v2(self, cursor: sqlite3.Cursor):
        """Migrate database from v1 to v2 - add user feature columns."""
        columns_to_add = [
            ('is_favorite', 'INTEGER DEFAULT 0'),
            ('last_viewed_date', 'TIMESTAMP'),
            ('custom_order', 'INTEGER'),
            ('is_locked', 'INTEGER DEFAULT 0')
        ]

        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f'ALTER TABLE animations ADD COLUMN {column_name} {column_type}')
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise

        # Create new indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_favorite ON animations(is_favorite)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_last_viewed ON animations(last_viewed_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_custom_order ON animations(custom_order)')

    def _migrate_to_v3(self, cursor: sqlite3.Cursor):
        """Migrate database from v2 to v3 - add trash table (legacy, renamed to archive in v4)."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trash (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                original_folder_id INTEGER,
                original_folder_path TEXT,
                rig_type TEXT,
                frame_count INTEGER,
                duration_seconds REAL,
                file_size_mb REAL,
                trash_folder_path TEXT NOT NULL,
                thumbnail_path TEXT,
                deleted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_date TIMESTAMP,
                original_created_date TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_uuid ON trash(uuid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_expires_date ON trash(expires_date)')

    def _migrate_to_v4(self, cursor: sqlite3.Cursor):
        """Migrate database from v3 to v4 - rename trash to archive, add new trash table."""
        # Check if old trash table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trash'")
        old_trash_exists = cursor.fetchone() is not None

        if old_trash_exists:
            # Rename old trash table to archive
            cursor.execute('ALTER TABLE trash RENAME TO archive')

            # Create new table with renamed columns
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS archive_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    original_folder_id INTEGER,
                    original_folder_path TEXT,
                    rig_type TEXT,
                    frame_count INTEGER,
                    duration_seconds REAL,
                    file_size_mb REAL,
                    archive_folder_path TEXT NOT NULL,
                    thumbnail_path TEXT,
                    archived_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    original_created_date TIMESTAMP
                )
            ''')

            # Copy data from old archive to new archive
            cursor.execute('''
                INSERT INTO archive_new (id, uuid, name, original_folder_id, original_folder_path,
                    rig_type, frame_count, duration_seconds, file_size_mb, archive_folder_path,
                    thumbnail_path, archived_date, original_created_date)
                SELECT id, uuid, name, original_folder_id, original_folder_path,
                    rig_type, frame_count, duration_seconds, file_size_mb, trash_folder_path,
                    thumbnail_path, deleted_date, original_created_date
                FROM archive
            ''')

            # Drop old archive and rename new
            cursor.execute('DROP TABLE archive')
            cursor.execute('ALTER TABLE archive_new RENAME TO archive')
        else:
            # Create archive table fresh
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    original_folder_id INTEGER,
                    original_folder_path TEXT,
                    rig_type TEXT,
                    frame_count INTEGER,
                    duration_seconds REAL,
                    file_size_mb REAL,
                    archive_folder_path TEXT NOT NULL,
                    thumbnail_path TEXT,
                    archived_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    original_created_date TIMESTAMP
                )
            ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_archive_uuid ON archive(uuid)')

        # Create new trash table for second-stage deletion
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trash (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                trash_folder_path TEXT NOT NULL,
                thumbnail_path TEXT,
                trashed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                archived_date TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_uuid ON trash(uuid)')


def migrate_legacy_database(new_db_path: Path, legacy_db_path: Optional[Path]):
    """
    Migrate legacy database from old location to new hidden folder.

    Args:
        new_db_path: New database path
        legacy_db_path: Legacy database path (or None)
    """
    # If new database already exists, no migration needed
    if new_db_path.exists():
        return

    # If legacy database exists, migrate it
    if legacy_db_path and legacy_db_path.exists():
        try:
            # Ensure target directory exists
            new_db_path.parent.mkdir(parents=True, exist_ok=True)

            # Move the database file
            shutil.move(str(legacy_db_path), str(new_db_path))

            # Also move WAL and SHM files if they exist
            for suffix in ['-wal', '-shm']:
                legacy_wal = legacy_db_path.parent / (legacy_db_path.name + suffix)
                if legacy_wal.exists():
                    new_wal = new_db_path.parent / (new_db_path.name + suffix)
                    shutil.move(str(legacy_wal), str(new_wal))

        except Exception:
            # If migration fails, we'll create a fresh database
            pass


__all__ = ['SchemaManager', 'SCHEMA_VERSION', 'migrate_legacy_database']
