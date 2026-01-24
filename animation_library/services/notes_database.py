"""
NotesDatabase - Separate database for review notes

Design principles:
- Notes live separately from asset data (assets are immutable)
- Version-scoped: each animation version has its own review session
- Soft delete with audit trail (Studio Mode)
- Role-based permissions support
- Studio-safe: can sync notes DB separately from assets
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..config import Config


class NotesDatabase:
    """
    Manages the separate notes.db database for review notes and drawover metadata.

    Features:
    - Review sessions per animation version
    - Soft delete with restore capability
    - Audit logging for all actions
    - User management for Studio Mode
    - App settings storage
    - Drawover metadata tracking (v3)
    """

    SCHEMA_VERSION = 3
    DB_NAME = "notes.db"

    def __init__(self):
        self._connection: Optional[sqlite3.Connection] = None
        self._db_path: Optional[Path] = None

    def initialize(self) -> bool:
        """
        Initialize the notes database.

        Returns:
            True if successful
        """
        try:
            # Get database folder (same as main DB)
            db_folder = Config.get_database_folder()
            self._db_path = db_folder / self.DB_NAME

            # Connect and create schema
            self._connection = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row

            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys = ON")

            # Create/migrate schema
            self._create_schema()
            self._migrate_if_needed()

            return True

        except Exception as e:
            print(f"Notes database initialization failed: {e}")
            return False

    def _create_schema(self):
        """Create database schema if not exists."""
        cursor = self._connection.cursor()

        # Review sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animation_uuid TEXT NOT NULL,
                version_label TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP,
                status TEXT DEFAULT 'active',
                UNIQUE(animation_uuid, version_label)
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sessions_uuid
            ON review_sessions(animation_uuid)
        ''')

        # Review notes table (with soft delete fields)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                frame INTEGER NOT NULL,
                note TEXT NOT NULL,
                author TEXT DEFAULT '',
                author_role TEXT DEFAULT 'artist',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_date TIMESTAMP,
                resolved INTEGER DEFAULT 0,
                resolved_by TEXT,
                resolved_date TIMESTAMP,
                deleted INTEGER DEFAULT 0,
                deleted_by TEXT,
                deleted_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES review_sessions(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notes_session ON review_notes(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notes_frame ON review_notes(frame)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notes_deleted ON review_notes(deleted)')

        # Audit log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS note_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                actor_role TEXT DEFAULT '',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY (note_id) REFERENCES review_notes(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_note ON note_audit_log(note_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON note_audit_log(timestamp)')

        # Studio users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS studio_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT DEFAULT 'artist',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # App settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Drawover metadata table (tracks drawover files on disk)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drawover_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animation_uuid TEXT NOT NULL,
                version_label TEXT NOT NULL,
                frame INTEGER NOT NULL,
                stroke_count INTEGER DEFAULT 0,
                authors TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_at TIMESTAMP,
                file_path TEXT,
                UNIQUE(animation_uuid, version_label, frame)
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drawover_uuid
            ON drawover_metadata(animation_uuid)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drawover_version
            ON drawover_metadata(animation_uuid, version_label)
        ''')

        # Drawover audit log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drawover_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animation_uuid TEXT NOT NULL,
                version_label TEXT NOT NULL,
                frame INTEGER NOT NULL,
                stroke_id TEXT,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                actor_role TEXT DEFAULT '',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drawover_audit_uuid
            ON drawover_audit_log(animation_uuid, version_label)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drawover_audit_timestamp
            ON drawover_audit_log(timestamp)
        ''')

        # Schema version table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        ''')

        # Initialize defaults
        cursor.execute('SELECT version FROM schema_version')
        if cursor.fetchone() is None:
            cursor.execute('INSERT INTO schema_version (version) VALUES (?)', (self.SCHEMA_VERSION,))

        # Default settings
        cursor.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)', ('app_mode', 'solo'))
        cursor.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)', ('current_user', ''))
        cursor.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)', ('show_deleted_notes', 'false'))

        # Default admin user
        cursor.execute('''
            INSERT OR IGNORE INTO studio_users (username, display_name, role)
            VALUES (?, ?, ?)
        ''', ('admin', 'Administrator', 'admin'))

        self._connection.commit()

    def _migrate_if_needed(self):
        """Run migrations if schema version is outdated."""
        cursor = self._connection.cursor()

        # Check if schema_version table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_version'
        """)
        if cursor.fetchone() is None:
            # Old database without version tracking - assume v1
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                )
            ''')
            cursor.execute('INSERT INTO schema_version (version) VALUES (1)')
            self._connection.commit()

        cursor.execute('SELECT version FROM schema_version')
        row = cursor.fetchone()
        current_version = row[0] if row else 1

        if current_version < 2:
            self._migrate_v1_to_v2()
            current_version = 2

        if current_version < 3:
            self._migrate_v2_to_v3()

    def _migrate_v1_to_v2(self):
        """Migrate from schema v1 to v2 (add soft delete, audit, users)."""
        cursor = self._connection.cursor()

        # Add soft delete columns if they don't exist
        try:
            cursor.execute('ALTER TABLE review_notes ADD COLUMN author_role TEXT DEFAULT "artist"')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE review_notes ADD COLUMN deleted INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute('ALTER TABLE review_notes ADD COLUMN deleted_by TEXT')
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute('ALTER TABLE review_notes ADD COLUMN deleted_at TIMESTAMP')
        except sqlite3.OperationalError:
            pass

        # Create index for deleted column
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notes_deleted ON review_notes(deleted)')

        # Create audit log table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS note_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                actor_role TEXT DEFAULT '',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY (note_id) REFERENCES review_notes(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_note ON note_audit_log(note_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON note_audit_log(timestamp)')

        # Create studio users table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS studio_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT DEFAULT 'artist',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # Create app settings table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Insert default settings
        cursor.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)', ('app_mode', 'solo'))
        cursor.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)', ('current_user', ''))
        cursor.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)', ('show_deleted_notes', 'false'))

        # Insert default admin user
        cursor.execute('''
            INSERT OR IGNORE INTO studio_users (username, display_name, role)
            VALUES (?, ?, ?)
        ''', ('admin', 'Administrator', 'admin'))

        # Update schema version
        cursor.execute('UPDATE schema_version SET version = 2')
        self._connection.commit()

    def _migrate_v2_to_v3(self):
        """Migrate from schema v2 to v3 (add drawover metadata tables)."""
        cursor = self._connection.cursor()

        # Create drawover metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drawover_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animation_uuid TEXT NOT NULL,
                version_label TEXT NOT NULL,
                frame INTEGER NOT NULL,
                stroke_count INTEGER DEFAULT 0,
                authors TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_at TIMESTAMP,
                file_path TEXT,
                UNIQUE(animation_uuid, version_label, frame)
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drawover_uuid
            ON drawover_metadata(animation_uuid)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drawover_version
            ON drawover_metadata(animation_uuid, version_label)
        ''')

        # Create drawover audit log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drawover_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animation_uuid TEXT NOT NULL,
                version_label TEXT NOT NULL,
                frame INTEGER NOT NULL,
                stroke_id TEXT,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                actor_role TEXT DEFAULT '',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drawover_audit_uuid
            ON drawover_audit_log(animation_uuid, version_label)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drawover_audit_timestamp
            ON drawover_audit_log(timestamp)
        ''')

        # Update schema version
        cursor.execute('UPDATE schema_version SET version = 3')
        self._connection.commit()

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    # ==================== App Settings ====================

    def get_setting(self, key: str, default: str = '') -> str:
        """Get an app setting value."""
        cursor = self._connection.cursor()
        cursor.execute('SELECT value FROM app_settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> bool:
        """Set an app setting value."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)
            ''', (key, value))
            self._connection.commit()
            return True
        except Exception as e:
            print(f"Failed to set setting: {e}")
            return False

    def is_studio_mode(self) -> bool:
        """Check if app is in studio mode."""
        return self.get_setting('app_mode', 'solo') == 'studio'

    def is_pipeline_mode(self) -> bool:
        """Check if app is in pipeline mode (controlled by Pipeline Control)."""
        return self.get_setting('app_mode', 'solo') == 'pipeline'

    def get_operation_mode(self) -> str:
        """
        Get current operation mode.
        
        Returns:
            'solo', 'studio', or 'pipeline'
        """
        mode = self.get_setting('app_mode', 'solo')
        if mode not in ('solo', 'studio', 'pipeline'):
            return 'solo'
        return mode

    def set_operation_mode(self, mode: str) -> bool:
        """
        Set operation mode.
        
        Args:
            mode: 'solo', 'studio', or 'pipeline'
            
        Returns:
            True if successful
        """
        if mode not in ('solo', 'studio', 'pipeline'):
            return False
        return self.set_setting('app_mode', mode)

    def get_current_user(self) -> str:
        """Get current username."""
        return self.get_setting('current_user', '')

    def get_show_deleted(self) -> bool:
        """Check if deleted notes should be shown."""
        return self.get_setting('show_deleted_notes', 'false') == 'true'

    # ==================== User Management ====================

    def get_all_users(self, include_inactive: bool = False) -> List[Dict]:
        """Get all studio users."""
        cursor = self._connection.cursor()
        if include_inactive:
            cursor.execute('SELECT * FROM studio_users ORDER BY role, display_name')
        else:
            cursor.execute('SELECT * FROM studio_users WHERE is_active = 1 ORDER BY role, display_name')
        return [dict(row) for row in cursor.fetchall()]

    def get_user(self, username: str) -> Optional[Dict]:
        """Get a user by username."""
        cursor = self._connection.cursor()
        cursor.execute('SELECT * FROM studio_users WHERE username = ?', (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def add_user(self, username: str, display_name: str, role: str = 'artist') -> bool:
        """Add a new user."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                INSERT INTO studio_users (username, display_name, role)
                VALUES (?, ?, ?)
            ''', (username, display_name, role))
            self._connection.commit()
            return True
        except Exception as e:
            print(f"Failed to add user: {e}")
            return False

    def update_user(self, username: str, display_name: str = None, role: str = None) -> bool:
        """Update user details."""
        try:
            cursor = self._connection.cursor()
            updates = []
            params = []

            if display_name is not None:
                updates.append('display_name = ?')
                params.append(display_name)
            if role is not None:
                updates.append('role = ?')
                params.append(role)

            if not updates:
                return True

            params.append(username)
            cursor.execute(f'''
                UPDATE studio_users SET {', '.join(updates)} WHERE username = ?
            ''', params)
            self._connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Failed to update user: {e}")
            return False

    def deactivate_user(self, username: str) -> bool:
        """Deactivate a user (soft delete)."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('UPDATE studio_users SET is_active = 0 WHERE username = ?', (username,))
            self._connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Failed to deactivate user: {e}")
            return False

    def reactivate_user(self, username: str) -> bool:
        """Reactivate a user."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('UPDATE studio_users SET is_active = 1 WHERE username = ?', (username,))
            self._connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Failed to reactivate user: {e}")
            return False

    # ==================== Session Methods ====================

    def get_or_create_session(self, animation_uuid: str, version_label: str) -> int:
        """Get existing session or create new one."""
        cursor = self._connection.cursor()

        cursor.execute('''
            SELECT id FROM review_sessions
            WHERE animation_uuid = ? AND version_label = ?
        ''', (animation_uuid, version_label))

        row = cursor.fetchone()
        if row:
            cursor.execute('''
                UPDATE review_sessions SET last_activity = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (row['id'],))
            self._connection.commit()
            return row['id']

        cursor.execute('''
            INSERT INTO review_sessions (animation_uuid, version_label, last_activity)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (animation_uuid, version_label))

        self._connection.commit()
        return cursor.lastrowid

    def get_session(self, animation_uuid: str, version_label: str) -> Optional[Dict]:
        """Get session info if exists."""
        cursor = self._connection.cursor()
        cursor.execute('''
            SELECT * FROM review_sessions
            WHERE animation_uuid = ? AND version_label = ?
        ''', (animation_uuid, version_label))

        row = cursor.fetchone()
        return dict(row) if row else None

    # ==================== Note Methods ====================

    def get_notes_for_version(
        self,
        animation_uuid: str,
        version_label: str,
        include_deleted: bool = False
    ) -> List[Dict]:
        """
        Get all notes for a specific animation version.

        Args:
            animation_uuid: UUID of the animation
            version_label: Version label (v001, v002, etc.)
            include_deleted: Include soft-deleted notes

        Returns:
            List of note dictionaries sorted by frame
        """
        cursor = self._connection.cursor()

        if include_deleted:
            cursor.execute('''
                SELECT n.* FROM review_notes n
                JOIN review_sessions s ON n.session_id = s.id
                WHERE s.animation_uuid = ? AND s.version_label = ?
                ORDER BY n.frame ASC, n.created_date ASC
            ''', (animation_uuid, version_label))
        else:
            cursor.execute('''
                SELECT n.* FROM review_notes n
                JOIN review_sessions s ON n.session_id = s.id
                WHERE s.animation_uuid = ? AND s.version_label = ?
                AND n.deleted = 0
                ORDER BY n.frame ASC, n.created_date ASC
            ''', (animation_uuid, version_label))

        return [dict(row) for row in cursor.fetchall()]

    def add_note(
        self,
        animation_uuid: str,
        version_label: str,
        frame: int,
        note: str,
        author: str = '',
        author_role: str = 'artist'
    ) -> Optional[int]:
        """Add a new review note with audit logging."""
        try:
            session_id = self.get_or_create_session(animation_uuid, version_label)

            cursor = self._connection.cursor()
            cursor.execute('''
                INSERT INTO review_notes (session_id, frame, note, author, author_role)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, frame, note, author, author_role))

            note_id = cursor.lastrowid

            # Update session activity
            cursor.execute('''
                UPDATE review_sessions SET last_activity = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (session_id,))

            # Audit log
            self._log_action(note_id, 'created', author, author_role, {
                'frame': frame,
                'note_preview': note[:100]
            })

            self._connection.commit()
            return note_id

        except Exception as e:
            print(f"Failed to add note: {e}")
            return None

    def update_note(
        self,
        note_id: int,
        note_text: str,
        actor: str = '',
        actor_role: str = ''
    ) -> bool:
        """Update note text with audit logging."""
        try:
            # Get old value for audit
            old_note = self.get_note_by_id(note_id)
            old_text = old_note.get('note', '') if old_note else ''

            cursor = self._connection.cursor()
            cursor.execute('''
                UPDATE review_notes
                SET note = ?, modified_date = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (note_text, note_id))

            # Audit log
            if cursor.rowcount > 0:
                self._log_action(note_id, 'edited', actor, actor_role, {
                    'old': old_text[:100],
                    'new': note_text[:100]
                })

            self._connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            print(f"Failed to update note: {e}")
            return False

    def soft_delete_note(
        self,
        note_id: int,
        deleted_by: str = '',
        actor_role: str = ''
    ) -> bool:
        """Soft delete a note (mark as deleted, don't remove)."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                UPDATE review_notes
                SET deleted = 1, deleted_by = ?, deleted_at = CURRENT_TIMESTAMP
                WHERE id = ? AND deleted = 0
            ''', (deleted_by, note_id))

            # Audit log
            if cursor.rowcount > 0:
                self._log_action(note_id, 'deleted', deleted_by, actor_role, {})

            self._connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            print(f"Failed to soft delete note: {e}")
            return False

    def restore_note(
        self,
        note_id: int,
        restored_by: str = '',
        actor_role: str = ''
    ) -> bool:
        """Restore a soft-deleted note."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                UPDATE review_notes
                SET deleted = 0, deleted_by = NULL, deleted_at = NULL
                WHERE id = ? AND deleted = 1
            ''', (note_id,))

            # Audit log
            if cursor.rowcount > 0:
                self._log_action(note_id, 'restored', restored_by, actor_role, {})

            self._connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            print(f"Failed to restore note: {e}")
            return False

    def delete_note(self, note_id: int) -> bool:
        """
        Delete a note - uses soft delete in studio mode, hard delete in solo mode.
        For backward compatibility, this calls soft_delete_note.
        """
        return self.soft_delete_note(note_id, '', '')

    def hard_delete_note(self, note_id: int) -> bool:
        """Permanently delete a note (use with caution)."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('DELETE FROM review_notes WHERE id = ?', (note_id,))
            self._connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Failed to hard delete note: {e}")
            return False

    def set_note_resolved(
        self,
        note_id: int,
        resolved: bool,
        resolved_by: str = '',
        actor_role: str = ''
    ) -> bool:
        """Set note resolved status with audit logging."""
        try:
            cursor = self._connection.cursor()

            if resolved:
                cursor.execute('''
                    UPDATE review_notes
                    SET resolved = 1, resolved_by = ?, resolved_date = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (resolved_by, note_id))
            else:
                cursor.execute('''
                    UPDATE review_notes
                    SET resolved = 0, resolved_by = NULL, resolved_date = NULL
                    WHERE id = ?
                ''', (note_id,))

            # Audit log
            if cursor.rowcount > 0:
                action = 'resolved' if resolved else 'unresolved'
                self._log_action(note_id, action, resolved_by, actor_role, {})

            self._connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            print(f"Failed to update note status: {e}")
            return False

    def get_note_by_id(self, note_id: int) -> Optional[Dict]:
        """Get a single note by ID."""
        cursor = self._connection.cursor()
        cursor.execute('SELECT * FROM review_notes WHERE id = ?', (note_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    # ==================== Audit Log ====================

    def _log_action(
        self,
        note_id: int,
        action: str,
        actor: str,
        actor_role: str,
        details: Dict
    ):
        """Log an action to the audit trail."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                INSERT INTO note_audit_log (note_id, action, actor, actor_role, details)
                VALUES (?, ?, ?, ?, ?)
            ''', (note_id, action, actor, actor_role, json.dumps(details)))
        except Exception as e:
            print(f"Failed to log action: {e}")

    def get_audit_log(self, note_id: int) -> List[Dict]:
        """Get audit log for a specific note."""
        cursor = self._connection.cursor()
        cursor.execute('''
            SELECT * FROM note_audit_log
            WHERE note_id = ?
            ORDER BY timestamp DESC
        ''', (note_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_activity(self, limit: int = 50) -> List[Dict]:
        """Get recent audit activity across all notes."""
        cursor = self._connection.cursor()
        cursor.execute('''
            SELECT a.*, n.frame, n.note as note_preview
            FROM note_audit_log a
            JOIN review_notes n ON a.note_id = n.id
            ORDER BY a.timestamp DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # ==================== Cleanup Methods ====================

    def cleanup_orphaned_sessions(self, valid_uuids: List[str]) -> int:
        """Archive sessions whose animations no longer exist."""
        if not valid_uuids:
            return 0

        try:
            cursor = self._connection.cursor()
            placeholders = ','.join('?' * len(valid_uuids))

            cursor.execute(f'''
                UPDATE review_sessions
                SET status = 'archived'
                WHERE animation_uuid NOT IN ({placeholders})
                AND status = 'active'
            ''', valid_uuids)

            self._connection.commit()
            return cursor.rowcount

        except Exception as e:
            print(f"Cleanup failed: {e}")
            return 0

    def archive_inactive_sessions(self, days_inactive: int = 30) -> int:
        """Archive sessions with no activity for X days."""
        try:
            cursor = self._connection.cursor()
            cursor.execute(f'''
                UPDATE review_sessions
                SET status = 'archived'
                WHERE last_activity < datetime('now', '-{days_inactive} days')
                AND status = 'active'
            ''')

            self._connection.commit()
            return cursor.rowcount

        except Exception as e:
            print(f"Archive failed: {e}")
            return 0

    def delete_archived_sessions(self) -> int:
        """Permanently delete archived sessions and their notes."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('DELETE FROM review_sessions WHERE status = "archived"')
            self._connection.commit()
            return cursor.rowcount

        except Exception as e:
            print(f"Delete failed: {e}")
            return 0

    def purge_deleted_notes(self, days_old: int = 30) -> int:
        """Permanently delete soft-deleted notes older than X days."""
        try:
            cursor = self._connection.cursor()
            cursor.execute(f'''
                DELETE FROM review_notes
                WHERE deleted = 1
                AND deleted_at < datetime('now', '-{days_old} days')
            ''')
            self._connection.commit()
            return cursor.rowcount

        except Exception as e:
            print(f"Purge failed: {e}")
            return 0

    def get_animations_with_notes(self) -> set:
        """
        Get set of animation UUIDs that have notes or drawovers.

        Returns:
            Set of animation UUIDs
        """
        uuids = set()
        try:
            cursor = self._connection.cursor()

            # Get UUIDs with notes
            cursor.execute('''
                SELECT DISTINCT s.animation_uuid
                FROM review_sessions s
                JOIN review_notes n ON n.session_id = s.id
                WHERE n.deleted = 0
            ''')
            for row in cursor.fetchall():
                uuids.add(row[0])

            # Get UUIDs with drawovers
            cursor.execute('''
                SELECT DISTINCT animation_uuid
                FROM drawover_metadata
                WHERE stroke_count > 0
            ''')
            for row in cursor.fetchall():
                uuids.add(row[0])

        except Exception as e:
            print(f"Failed to get animations with notes: {e}")

        return uuids

    def get_unresolved_counts(self) -> Dict[str, int]:
        """
        Get unresolved comment counts for all animations.

        Returns:
            Dict mapping animation UUID to unresolved comment count
        """
        counts = {}
        try:
            cursor = self._connection.cursor()

            # Count unresolved notes per animation (across all versions)
            cursor.execute('''
                SELECT s.animation_uuid, COUNT(*) as count
                FROM review_sessions s
                JOIN review_notes n ON n.session_id = s.id
                WHERE n.deleted = 0 AND n.resolved = 0
                GROUP BY s.animation_uuid
            ''')
            for row in cursor.fetchall():
                counts[row[0]] = row[1]

        except Exception as e:
            print(f"Failed to get unresolved counts: {e}")

        return counts

    def get_unresolved_count(self, animation_uuid: str) -> int:
        """
        Get unresolved comment count for a specific animation.

        Args:
            animation_uuid: UUID of the animation

        Returns:
            Number of unresolved comments
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM review_sessions s
                JOIN review_notes n ON n.session_id = s.id
                WHERE s.animation_uuid = ? AND n.deleted = 0 AND n.resolved = 0
            ''', (animation_uuid,))
            row = cursor.fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    def animation_has_notes(self, animation_uuid: str) -> bool:
        """
        Check if an animation has any notes or drawovers.

        Args:
            animation_uuid: UUID of the animation

        Returns:
            True if animation has notes or drawovers
        """
        try:
            cursor = self._connection.cursor()

            # Check for notes
            cursor.execute('''
                SELECT 1 FROM review_sessions s
                JOIN review_notes n ON n.session_id = s.id
                WHERE s.animation_uuid = ? AND n.deleted = 0
                LIMIT 1
            ''', (animation_uuid,))
            if cursor.fetchone():
                return True

            # Check for drawovers
            cursor.execute('''
                SELECT 1 FROM drawover_metadata
                WHERE animation_uuid = ? AND stroke_count > 0
                LIMIT 1
            ''', (animation_uuid,))
            if cursor.fetchone():
                return True

            return False

        except Exception:
            return False

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        cursor = self._connection.cursor()

        cursor.execute('SELECT COUNT(*) FROM review_sessions WHERE status = "active"')
        active_sessions = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM review_sessions WHERE status = "archived"')
        archived_sessions = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM review_notes WHERE deleted = 0')
        active_notes = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM review_notes WHERE deleted = 1')
        deleted_notes = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM review_notes WHERE resolved = 0 AND deleted = 0')
        unresolved_notes = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM studio_users WHERE is_active = 1')
        active_users = cursor.fetchone()[0]

        # Drawover stats
        try:
            cursor.execute('SELECT COUNT(*) FROM drawover_metadata')
            total_drawovers = cursor.fetchone()[0]

            cursor.execute('SELECT SUM(stroke_count) FROM drawover_metadata')
            total_strokes = cursor.fetchone()[0] or 0
        except sqlite3.OperationalError:
            total_drawovers = 0
            total_strokes = 0

        return {
            'active_sessions': active_sessions,
            'archived_sessions': archived_sessions,
            'active_notes': active_notes,
            'deleted_notes': deleted_notes,
            'unresolved_notes': unresolved_notes,
            'active_users': active_users,
            'total_drawovers': total_drawovers,
            'total_strokes': total_strokes
        }

    # ==================== Drawover Metadata ====================

    def update_drawover_metadata(
        self,
        animation_uuid: str,
        version_label: str,
        frame: int,
        stroke_count: int,
        authors: str = '',
        file_path: str = ''
    ) -> bool:
        """Update or create drawover metadata entry."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                INSERT INTO drawover_metadata
                    (animation_uuid, version_label, frame, stroke_count, authors, file_path, modified_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(animation_uuid, version_label, frame)
                DO UPDATE SET
                    stroke_count = excluded.stroke_count,
                    authors = excluded.authors,
                    file_path = excluded.file_path,
                    modified_at = CURRENT_TIMESTAMP
            ''', (animation_uuid, version_label, frame, stroke_count, authors, file_path))
            self._connection.commit()
            return True
        except Exception as e:
            print(f"Failed to update drawover metadata: {e}")
            return False

    def get_drawover_metadata(
        self,
        animation_uuid: str,
        version_label: str,
        frame: int
    ) -> Optional[Dict]:
        """Get drawover metadata for a specific frame."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                SELECT * FROM drawover_metadata
                WHERE animation_uuid = ? AND version_label = ? AND frame = ?
            ''', (animation_uuid, version_label, frame))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def get_version_drawovers(
        self,
        animation_uuid: str,
        version_label: str
    ) -> List[Dict]:
        """Get all drawover metadata for a version."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                SELECT * FROM drawover_metadata
                WHERE animation_uuid = ? AND version_label = ?
                ORDER BY frame ASC
            ''', (animation_uuid, version_label))
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def delete_drawover_metadata(
        self,
        animation_uuid: str,
        version_label: str,
        frame: int
    ) -> bool:
        """Delete drawover metadata entry."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                DELETE FROM drawover_metadata
                WHERE animation_uuid = ? AND version_label = ? AND frame = ?
            ''', (animation_uuid, version_label, frame))
            self._connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Failed to delete drawover metadata: {e}")
            return False

    def log_drawover_action(
        self,
        animation_uuid: str,
        version_label: str,
        frame: int,
        action: str,
        actor: str,
        actor_role: str = '',
        stroke_id: str = '',
        details: Dict = None
    ):
        """Log a drawover action to the audit trail."""
        try:
            cursor = self._connection.cursor()
            cursor.execute('''
                INSERT INTO drawover_audit_log
                    (animation_uuid, version_label, frame, stroke_id, action, actor, actor_role, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                animation_uuid, version_label, frame, stroke_id,
                action, actor, actor_role,
                json.dumps(details) if details else ''
            ))
            self._connection.commit()
        except Exception as e:
            print(f"Failed to log drawover action: {e}")

    def get_drawover_audit_log(
        self,
        animation_uuid: str,
        version_label: str,
        frame: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get drawover audit log entries."""
        try:
            cursor = self._connection.cursor()
            if frame is not None:
                cursor.execute('''
                    SELECT * FROM drawover_audit_log
                    WHERE animation_uuid = ? AND version_label = ? AND frame = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (animation_uuid, version_label, frame, limit))
            else:
                cursor.execute('''
                    SELECT * FROM drawover_audit_log
                    WHERE animation_uuid = ? AND version_label = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (animation_uuid, version_label, limit))
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []


# Singleton instance
_notes_db_instance: Optional[NotesDatabase] = None


def get_notes_database() -> NotesDatabase:
    """Get global NotesDatabase singleton instance."""
    global _notes_db_instance
    if _notes_db_instance is None:
        _notes_db_instance = NotesDatabase()
        _notes_db_instance.initialize()
    return _notes_db_instance


__all__ = ['NotesDatabase', 'get_notes_database']
