"""
Database Schema - Schema initialization and migrations

Manages database schema versions and migration logic.
"""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from .connection import DatabaseConnection


# Current schema version
SCHEMA_VERSION = 11

# Feature descriptions for each version upgrade
VERSION_FEATURES: Dict[int, List[str]] = {
    2: ["Favorites", "Recently Viewed", "Custom Order", "Lock animations"],
    3: ["Trash system"],
    4: ["Two-stage deletion (Archive + Trash)"],
    5: ["Version history", "Version labels"],
    6: ["Lifecycle status (WIP, Review, Approved)"],
    7: ["Pose detection and badges"],
    8: ["Partial pose support"],
    9: ["Studio naming engine (naming_fields, naming_template)"],
    10: ["Frame-specific review notes for dailies"],
    11: ["Human-readable folder structure"],
}


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
                if current_version < 5:
                    self._migrate_to_v5(cursor)
                if current_version < 6:
                    self._migrate_to_v6(cursor)
                if current_version < 7:
                    self._migrate_to_v7(cursor)
                if current_version < 8:
                    self._migrate_to_v8(cursor)
                if current_version < 9:
                    self._migrate_to_v9(cursor)
                if current_version < 10:
                    self._migrate_to_v10(cursor)
                if current_version < 11:
                    self._migrate_to_v11(cursor)
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

                -- Versioning (v5)
                version INTEGER DEFAULT 1,
                version_label TEXT DEFAULT 'v001',
                version_group_id TEXT,
                is_latest INTEGER DEFAULT 1,

                -- Lifecycle Status (v6)
                status TEXT DEFAULT 'none',

                -- Pose flag (v7) - 0 for actions, 1 for poses
                is_pose INTEGER DEFAULT 0,

                -- Partial pose flag (v8) - 1 if pose was captured with selected bones only
                is_partial INTEGER DEFAULT 0,

                -- Studio Naming Engine (v9)
                naming_fields TEXT,       -- JSON: {"show":"PROJ","shot":"010",...}
                naming_template TEXT,     -- Template used: "{show}_{asset}_v{version:03}"

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

        # v5 indexes (versioning)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_version_group ON animations(version_group_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_is_latest ON animations(is_latest)')

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

        # Review notes table (v10) - frame-specific notes for dailies review
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animation_uuid TEXT NOT NULL,
                frame INTEGER NOT NULL,
                note TEXT NOT NULL,
                author TEXT DEFAULT '',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved INTEGER DEFAULT 0,
                FOREIGN KEY (animation_uuid) REFERENCES animations(uuid) ON DELETE CASCADE
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_review_notes_animation ON review_notes(animation_uuid)')

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

    def _migrate_to_v5(self, cursor: sqlite3.Cursor):
        """Migrate database from v4 to v5 - add versioning columns."""
        columns_to_add = [
            ('version', 'INTEGER DEFAULT 1'),
            ('version_label', "TEXT DEFAULT 'v001'"),
            ('version_group_id', 'TEXT'),
            ('is_latest', 'INTEGER DEFAULT 1')
        ]

        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f'ALTER TABLE animations ADD COLUMN {column_name} {column_type}')
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise

        # Create indexes for versioning
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_version_group ON animations(version_group_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_is_latest ON animations(is_latest)')

        # Initialize version_group_id for existing animations (each animation is its own group initially)
        cursor.execute('UPDATE animations SET version_group_id = uuid WHERE version_group_id IS NULL')

    def _migrate_to_v6(self, cursor: sqlite3.Cursor):
        """Migrate database from v5 to v6 - add lifecycle status column."""
        try:
            cursor.execute("ALTER TABLE animations ADD COLUMN status TEXT DEFAULT 'none'")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

    def _migrate_to_v7(self, cursor: sqlite3.Cursor):
        """Migrate database from v6 to v7 - add is_pose flag for pose support."""
        try:
            cursor.execute("ALTER TABLE animations ADD COLUMN is_pose INTEGER DEFAULT 0")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Create index for pose filtering
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_is_pose ON animations(is_pose)')

        # Identify and update existing poses based on frame_count
        # Poses have frame_count = 1 (single-frame snapshots)
        cursor.execute('''
            UPDATE animations
            SET is_pose = 1
            WHERE frame_count = 1 AND is_pose = 0
        ''')

    def _migrate_to_v8(self, cursor: sqlite3.Cursor):
        """Migrate database from v7 to v8 - add is_partial flag for partial poses."""
        try:
            cursor.execute("ALTER TABLE animations ADD COLUMN is_partial INTEGER DEFAULT 0")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

    def _migrate_to_v9(self, cursor: sqlite3.Cursor):
        """Migrate database from v8 to v9 - add studio naming engine columns."""
        columns_to_add = [
            ('naming_fields', 'TEXT'),       # JSON: {"show":"PROJ","shot":"010",...}
            ('naming_template', 'TEXT'),     # Template used: "{show}_{asset}_v{version:03}"
        ]

        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f'ALTER TABLE animations ADD COLUMN {column_name} {column_type}')
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise

    def _migrate_to_v10(self, cursor: sqlite3.Cursor):
        """Migrate database from v9 to v10 - add review_notes table for dailies."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animation_uuid TEXT NOT NULL,
                frame INTEGER NOT NULL,
                note TEXT NOT NULL,
                author TEXT DEFAULT '',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved INTEGER DEFAULT 0,
                FOREIGN KEY (animation_uuid) REFERENCES animations(uuid) ON DELETE CASCADE
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_review_notes_animation ON review_notes(animation_uuid)')

    def _migrate_to_v11(self, cursor: sqlite3.Cursor):
        """Migrate database from v10 to v11 - human-readable folder structure.

        Note: This is a breaking change. Users with old UUID-based libraries
        need to export their animations before upgrading.
        """
        # No schema changes needed - just version bump
        pass

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics for status display.

        Returns:
            Dict containing schema version, record counts, file size, etc.
        """
        conn = self._conn.get_connection()
        cursor = conn.cursor()

        # Schema version
        cursor.execute('SELECT MAX(version) FROM schema_version')
        result = cursor.fetchone()
        schema_version = result[0] if result and result[0] is not None else 0

        # Record counts - handle tables that may not exist in old schemas
        animation_count = 0
        folder_count = 0
        archive_count = 0
        trash_count = 0

        try:
            cursor.execute('SELECT COUNT(*) FROM animations')
            animation_count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute('SELECT COUNT(*) FROM folders')
            folder_count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute('SELECT COUNT(*) FROM archive')
            archive_count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute('SELECT COUNT(*) FROM trash')
            trash_count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            pass

        # Database file size
        db_path = self._conn.db_path
        db_size_bytes = db_path.stat().st_size if db_path.exists() else 0

        # Get pending features (what will be added by upgrade)
        pending_features = []
        for version in range(schema_version + 1, SCHEMA_VERSION + 1):
            if version in VERSION_FEATURES:
                pending_features.extend(VERSION_FEATURES[version])

        return {
            'schema_version': schema_version,
            'latest_version': SCHEMA_VERSION,
            'is_up_to_date': schema_version >= SCHEMA_VERSION,
            'needs_upgrade': schema_version < SCHEMA_VERSION,
            'animation_count': animation_count,
            'folder_count': folder_count,
            'archive_count': archive_count,
            'trash_count': trash_count,
            'db_size_bytes': db_size_bytes,
            'db_size_mb': round(db_size_bytes / (1024 * 1024), 2),
            'db_path': str(db_path),
            'pending_features': pending_features,
        }

    def run_integrity_check(self) -> Tuple[bool, str]:
        """
        Run database integrity check.

        Returns:
            Tuple of (is_ok, message)
        """
        conn = self._conn.get_connection()
        cursor = conn.cursor()

        results = []

        # Run PRAGMA integrity_check
        cursor.execute('PRAGMA integrity_check')
        integrity_result = cursor.fetchall()
        integrity_ok = len(integrity_result) == 1 and integrity_result[0][0] == 'ok'

        if integrity_ok:
            results.append("Integrity check: OK")
        else:
            results.append(f"Integrity check: FAILED - {integrity_result}")

        # Run PRAGMA foreign_key_check
        cursor.execute('PRAGMA foreign_key_check')
        fk_result = cursor.fetchall()
        fk_ok = len(fk_result) == 0

        if fk_ok:
            results.append("Foreign key check: OK")
        else:
            results.append(f"Foreign key check: FAILED - {len(fk_result)} violations")

        is_ok = integrity_ok and fk_ok
        message = "\n".join(results)

        return is_ok, message

    def optimize_database(self) -> Tuple[int, int]:
        """
        Optimize database by running VACUUM.

        Returns:
            Tuple of (size_before, size_after) in bytes
        """
        db_path = self._conn.db_path
        size_before = db_path.stat().st_size if db_path.exists() else 0

        # Close all connections and run VACUUM
        conn = self._conn.get_connection()
        conn.execute('VACUUM')

        size_after = db_path.stat().st_size if db_path.exists() else 0

        return size_before, size_after

    def get_current_version(self) -> int:
        """Get current schema version."""
        conn = self._conn.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT MAX(version) FROM schema_version')
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0
        except sqlite3.OperationalError:
            return 0


def backup_database(db_path: Path, backup_dir: Optional[Path] = None) -> Path:
    """
    Create a backup of the database using SQLite backup API.

    Args:
        db_path: Path to the database file
        backup_dir: Directory for backups (defaults to db_path.parent / 'backups')

    Returns:
        Path to the backup file
    """
    if backup_dir is None:
        backup_dir = db_path.parent / 'backups'

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"database_backup_{timestamp}.db"

    # Checkpoint WAL to ensure all data is in main file
    source = sqlite3.connect(str(db_path))
    source.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    # Use SQLite backup API for atomic, consistent snapshot
    dest = sqlite3.connect(str(backup_path))
    source.backup(dest)

    source.close()
    dest.close()

    return backup_path


def get_backups(db_path: Path) -> List[Dict[str, Any]]:
    """
    Get list of existing backups.

    Args:
        db_path: Path to the database file

    Returns:
        List of backup info dicts with 'path', 'size', 'date'
    """
    backup_dir = db_path.parent / 'backups'
    if not backup_dir.exists():
        return []

    backups = []
    for backup_file in sorted(backup_dir.glob("database_backup_*.db"), reverse=True):
        stat = backup_file.stat()
        backups.append({
            'path': str(backup_file),
            'filename': backup_file.name,
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'date': datetime.fromtimestamp(stat.st_mtime),
        })

    return backups


def delete_backup(backup_path: Path) -> bool:
    """
    Delete a backup file.

    Args:
        backup_path: Path to the backup file

    Returns:
        True if deleted successfully
    """
    try:
        if backup_path.exists():
            backup_path.unlink()
            return True
        return False
    except Exception:
        return False


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


__all__ = [
    'SchemaManager',
    'SCHEMA_VERSION',
    'VERSION_FEATURES',
    'migrate_legacy_database',
    'backup_database',
    'get_backups',
    'delete_backup',
]
