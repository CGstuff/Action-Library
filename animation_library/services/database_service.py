"""
DatabaseService - SQLite database management

Pattern: Repository pattern with thread-local connections
Inspired by: Current animation_library with improvements
"""

import sqlite3
import json
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager

from ..config import Config


class DatabaseService:
    """
    Database service for animation metadata storage

    Features:
    - Thread-local connections for thread safety
    - WAL mode for better concurrency
    - Transaction support
    - Automatic schema initialization and migrations
    - Comprehensive indexing for fast queries

    Usage:
        db = DatabaseService()
        animation_id = db.add_animation({...})
        animations = db.get_all_animations()
    """

    # Schema version for migrations
    SCHEMA_VERSION = 2

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database service

        Args:
            db_path: Path to database file (defaults to Config.get_database_path())
        """
        # Check for legacy database migration first
        if db_path is None:
            self._migrate_legacy_database()

        self.db_path = db_path or Config.get_database_path()
        self.local = threading.local()
        self._init_database()

    def _migrate_legacy_database(self):
        """
        Migrate legacy database from old location to new hidden folder.

        Checks for 'animation_library_v2.db' in library root and moves it
        to '.actionlibrary/database.db' if the new database doesn't exist.
        """
        new_db_path = Config.get_database_path()
        legacy_db_path = Config.get_legacy_database_path()

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

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local database connection

        Returns:
            SQLite connection for current thread
        """
        if not hasattr(self.local, 'connection') or self.local.connection is None:
            self.local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            # Enable foreign keys
            self.local.connection.execute("PRAGMA foreign_keys = ON")
            # Use WAL mode for better concurrency
            self.local.connection.execute("PRAGMA journal_mode = WAL")
            # Row factory for dict-like access
            self.local.connection.row_factory = sqlite3.Row

        return self.local.connection

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions

        Usage:
            with db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(...)

        Automatically commits on success, rolls back on exception
        """
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

    def _init_database(self):
        """Initialize database schema and check for migrations"""
        with self.transaction() as conn:
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
                    (self.SCHEMA_VERSION,)
                )
            elif current_version < self.SCHEMA_VERSION:
                # Incremental migrations
                if current_version < 2:
                    self._migrate_to_v2(cursor)
                cursor.execute(
                    'INSERT OR REPLACE INTO schema_version (version) VALUES (?)',
                    (self.SCHEMA_VERSION,)
                )

    def _create_schema(self, cursor: sqlite3.Cursor):
        """Create database schema"""

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

        # Create root folder if it doesn't exist
        cursor.execute('SELECT id FROM folders WHERE parent_id IS NULL LIMIT 1')
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO folders (name, parent_id, path, created_date, modified_date)
                VALUES (?, ?, ?, ?, ?)
            ''', ("Root", None, "", datetime.now(), datetime.now()))

    def _migrate_to_v2(self, cursor: sqlite3.Cursor):
        """Migrate database from v1 to v2 - add user feature columns"""
        # Add new columns to animations table
        try:
            cursor.execute('ALTER TABLE animations ADD COLUMN is_favorite INTEGER DEFAULT 0')
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            cursor.execute('ALTER TABLE animations ADD COLUMN last_viewed_date TIMESTAMP')
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            cursor.execute('ALTER TABLE animations ADD COLUMN custom_order INTEGER')
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            cursor.execute('ALTER TABLE animations ADD COLUMN is_locked INTEGER DEFAULT 0')
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Create new indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_favorite ON animations(is_favorite)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_last_viewed ON animations(last_viewed_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_animations_custom_order ON animations(custom_order)')

    # ==================== FOLDER OPERATIONS ====================

    def get_root_folder_id(self) -> int:
        """
        Get the ID of the root folder

        Returns:
            Root folder ID
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM folders WHERE parent_id IS NULL LIMIT 1')
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                # Create root folder if it doesn't exist
                with self.transaction() as trans_conn:
                    trans_cursor = trans_conn.cursor()
                    now = datetime.now()
                    trans_cursor.execute('''
                        INSERT INTO folders (name, parent_id, path, created_date, modified_date)
                        VALUES (?, ?, ?, ?, ?)
                    ''', ("Root", None, "", now, now))
                    return trans_cursor.lastrowid
        except Exception:
            return 1  # Fallback to ID 1

    def create_folder(self, name: str, parent_id: Optional[int] = None,
                     description: str = "") -> Optional[int]:
        """
        Create new folder

        Args:
            name: Folder name
            parent_id: Parent folder ID (None for root level)
            description: Folder description

        Returns:
            Folder ID or None on error
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()

                # Get parent path
                if parent_id:
                    cursor.execute('SELECT path FROM folders WHERE id = ?', (parent_id,))
                    result = cursor.fetchone()
                    if not result:
                        return None
                    parent_path = result['path']
                    full_path = f"{parent_path}/{name}" if parent_path else name
                else:
                    full_path = name

                now = datetime.now()
                cursor.execute('''
                    INSERT INTO folders (name, parent_id, path, description, created_date, modified_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, parent_id, full_path, description, now, now))

                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        except Exception:
            return None

    def get_folder_by_id(self, folder_id: int) -> Optional[Dict[str, Any]]:
        """
        Get folder by ID

        Args:
            folder_id: Folder ID

        Returns:
            Folder data dict or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM folders WHERE id = ?', (folder_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception:
            return None

    def get_all_folders(self) -> List[Dict[str, Any]]:
        """
        Get all folders

        Returns:
            List of folder dicts
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM folders ORDER BY path')
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_folder_descendants(self, folder_id: int) -> List[int]:
        """
        Get all descendant folder IDs (recursive)

        Args:
            folder_id: Parent folder ID

        Returns:
            List of descendant folder IDs (including the folder itself)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get all folders to build hierarchy
            cursor.execute('SELECT id, parent_id FROM folders')
            all_folders = cursor.fetchall()

            # Build parent -> children map
            children_map = {}
            for row in all_folders:
                fid = row['id']
                parent = row['parent_id']
                if parent not in children_map:
                    children_map[parent] = []
                children_map[parent].append(fid)

            # Recursively collect descendants
            def collect_descendants(current_id: int) -> List[int]:
                result = [current_id]
                if current_id in children_map:
                    for child_id in children_map[current_id]:
                        result.extend(collect_descendants(child_id))
                return result

            return collect_descendants(folder_id)

        except Exception:
            return [folder_id]  # At least return the folder itself

    def delete_folder(self, folder_id: int) -> bool:
        """
        Delete folder (and all contained animations via CASCADE)

        Args:
            folder_id: Folder ID to delete

        Returns:
            True if deleted, False on error
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
                return cursor.rowcount > 0
        except Exception:
            return False

    def move_animation_to_folder(self, animation_uuid: str, folder_id: int) -> bool:
        """
        Move animation to a different folder and add folder name to tags

        Args:
            animation_uuid: Animation UUID
            folder_id: Target folder ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()

                # Get folder name
                cursor.execute('SELECT name FROM folders WHERE id = ?', (folder_id,))
                folder = cursor.fetchone()
                if not folder:
                    return False

                folder_name = folder['name']

                # Get current animation data
                cursor.execute('SELECT tags FROM animations WHERE uuid = ?', (animation_uuid,))
                animation = cursor.fetchone()
                if not animation:
                    return False

                # Parse current tags
                import json
                tags = []
                if animation['tags']:
                    try:
                        tags = json.loads(animation['tags'])
                    except:
                        tags = []

                # Add folder name to tags if not already present
                if folder_name not in tags:
                    tags.append(folder_name)

                # Serialize tags back to JSON
                tags_json = json.dumps(tags)

                # Update both folder_id and tags
                cursor.execute(
                    """
                    UPDATE animations
                    SET folder_id = ?, tags = ?, modified_date = CURRENT_TIMESTAMP
                    WHERE uuid = ?
                    """,
                    (folder_id, tags_json, animation_uuid)
                )

                return cursor.rowcount > 0

        except Exception:
            return False

    def update_folder_parent(self, folder_id: int, new_parent_id: int) -> bool:
        """
        Update folder's parent to create hierarchy

        Args:
            folder_id: Folder to move
            new_parent_id: New parent folder ID

        Returns:
            True if successful
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()

                # Get folder info to update path (including old path for descendants)
                cursor.execute('SELECT name, parent_id, path FROM folders WHERE id = ?', (folder_id,))
                folder = cursor.fetchone()
                if not folder:
                    return False

                folder_name = folder['name']
                old_path = folder['path']  # Store old path before update

                # Get new parent path
                cursor.execute('SELECT path FROM folders WHERE id = ?', (new_parent_id,))
                parent = cursor.fetchone()
                if not parent:
                    return False

                parent_path = parent['path']
                new_path = f"{parent_path}/{folder_name}" if parent_path else folder_name

                # Update folder
                cursor.execute(
                    '''
                    UPDATE folders
                    SET parent_id = ?, path = ?, modified_date = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''',
                    (new_parent_id, new_path, folder_id)
                )

                # Store result before updating descendants
                parent_updated = cursor.rowcount > 0

                # Update paths of all descendant folders recursively
                try:
                    self._update_descendant_paths(cursor, old_path, new_path)
                except Exception:
                    pass  # Continue anyway - parent folder was updated

                return parent_updated
        except Exception:
            return False

    def _update_descendant_paths(self, cursor, old_path_prefix: str, new_path_prefix: str):
        """
        Recursively update paths of all descendant folders

        Args:
            cursor: Database cursor
            old_path_prefix: Old path prefix (e.g., "Folder1")
            new_path_prefix: New path prefix (e.g., "Folder2/Folder1")
        """
        # Get all descendant folders (folders whose path starts with old_path_prefix/)
        cursor.execute("""
            SELECT id, path FROM folders
            WHERE path LIKE ?
            ORDER BY path
        """, (f"{old_path_prefix}/%",))

        descendants = cursor.fetchall()

        # Update each descendant's path
        for row in descendants:
            folder_id = row['id']
            old_path = row['path']

            # Replace old prefix with new prefix
            # Example: "Folder1/Subfolder1" → "Folder2/Folder1/Subfolder1"
            new_path = old_path.replace(old_path_prefix, new_path_prefix, 1)

            cursor.execute("""
                UPDATE folders
                SET path = ?, modified_date = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_path, folder_id))

    # ==================== ANIMATION OPERATIONS ====================

    def add_animation(self, animation_data: Dict[str, Any]) -> Optional[int]:
        """
        Add animation to database

        Args:
            animation_data: Animation metadata dict with keys:
                - uuid (required)
                - name (required)
                - folder_id (required)
                - rig_type (required)
                - ... other optional fields

        Returns:
            Animation database ID or None on error
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()

                # Serialize tags list to JSON
                tags = animation_data.get('tags', [])
                tags_json = json.dumps(tags) if isinstance(tags, list) else tags

                now = datetime.now()

                cursor.execute('''
                    INSERT INTO animations (
                        uuid, name, description, folder_id, rig_type, armature_name,
                        bone_count, frame_start, frame_end, frame_count, duration_seconds,
                        fps, blend_file_path, json_file_path, preview_path, thumbnail_path,
                        file_size_mb, tags, author, use_custom_thumbnail_gradient,
                        thumbnail_gradient_top, thumbnail_gradient_bottom,
                        created_date, modified_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    animation_data.get('uuid'),
                    animation_data.get('name'),
                    animation_data.get('description', ''),
                    animation_data.get('folder_id'),
                    animation_data.get('rig_type'),
                    animation_data.get('armature_name'),
                    animation_data.get('bone_count'),
                    animation_data.get('frame_start'),
                    animation_data.get('frame_end'),
                    animation_data.get('frame_count'),
                    animation_data.get('duration_seconds'),
                    animation_data.get('fps'),
                    animation_data.get('blend_file_path'),
                    animation_data.get('json_file_path'),
                    animation_data.get('preview_path'),
                    animation_data.get('thumbnail_path'),
                    animation_data.get('file_size_mb'),
                    tags_json,
                    animation_data.get('author', ''),
                    animation_data.get('use_custom_thumbnail_gradient', 0),
                    animation_data.get('thumbnail_gradient_top'),
                    animation_data.get('thumbnail_gradient_bottom'),
                    now,
                    now
                ))

                return cursor.lastrowid
        except Exception:
            return None

    def get_animation_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get animation by UUID

        Args:
            uuid: Animation UUID

        Returns:
            Animation data dict or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM animations WHERE uuid = ?', (uuid,))
            result = cursor.fetchone()

            if result:
                data = dict(result)
                # Deserialize tags
                if data.get('tags'):
                    try:
                        data['tags'] = json.loads(data['tags'])
                    except:
                        data['tags'] = []
                return data
            return None
        except Exception:
            return None

    def get_animation_by_id(self, animation_id: int) -> Optional[Dict[str, Any]]:
        """
        Get animation by database ID

        Args:
            animation_id: Animation database ID

        Returns:
            Animation data dict or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM animations WHERE id = ?', (animation_id,))
            result = cursor.fetchone()

            if result:
                data = dict(result)
                # Deserialize tags
                if data.get('tags'):
                    try:
                        data['tags'] = json.loads(data['tags'])
                    except:
                        data['tags'] = []
                return data
            return None
        except Exception:
            return None

    def get_all_animations(self, folder_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all animations, optionally filtered by folder

        Args:
            folder_id: Optional folder ID to filter by

        Returns:
            List of animation dicts
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if folder_id is not None:
                cursor.execute('SELECT * FROM animations WHERE folder_id = ? ORDER BY name', (folder_id,))
            else:
                cursor.execute('SELECT * FROM animations ORDER BY name')

            results = []
            for row in cursor.fetchall():
                data = dict(row)
                # Deserialize tags
                if data.get('tags'):
                    try:
                        data['tags'] = json.loads(data['tags'])
                    except:
                        data['tags'] = []
                results.append(data)

            return results
        except Exception:
            return []

    def update_animation(self, uuid: str, updates: Dict[str, Any]) -> bool:
        """
        Update animation metadata

        Args:
            uuid: Animation UUID
            updates: Dict of fields to update

        Returns:
            True if updated, False on error
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()

                # Serialize tags if present
                if 'tags' in updates and isinstance(updates['tags'], list):
                    updates['tags'] = json.dumps(updates['tags'])

                # Build dynamic UPDATE query
                updates['modified_date'] = datetime.now()
                set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
                values = list(updates.values())
                values.append(uuid)

                cursor.execute(
                    f'UPDATE animations SET {set_clause} WHERE uuid = ?',
                    values
                )

                return cursor.rowcount > 0
        except Exception:
            return False

    def delete_animation(self, uuid: str) -> bool:
        """
        Delete animation by UUID

        Args:
            uuid: Animation UUID

        Returns:
            True if deleted, False on error
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM animations WHERE uuid = ?', (uuid,))
                return cursor.rowcount > 0
        except Exception:
            return False

    def search_animations(self, query: str) -> List[Dict[str, Any]]:
        """
        Search animations by name or description

        Args:
            query: Search query

        Returns:
            List of matching animation dicts
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            search_pattern = f"%{query}%"
            cursor.execute('''
                SELECT * FROM animations
                WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
                ORDER BY name
            ''', (search_pattern, search_pattern, search_pattern))

            results = []
            for row in cursor.fetchall():
                data = dict(row)
                if data.get('tags'):
                    try:
                        data['tags'] = json.loads(data['tags'])
                    except:
                        data['tags'] = []
                results.append(data)

            return results
        except Exception:
            return []

    def get_animation_count(self, folder_id: Optional[int] = None) -> int:
        """
        Get count of animations, optionally filtered by folder

        Args:
            folder_id: Optional folder ID

        Returns:
            Animation count
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if folder_id is not None:
                cursor.execute('SELECT COUNT(*) FROM animations WHERE folder_id = ?', (folder_id,))
            else:
                cursor.execute('SELECT COUNT(*) FROM animations')

            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    # ==================== USER FEATURES (v2) ====================

    def toggle_favorite(self, uuid: str) -> bool:
        """
        Toggle favorite status for an animation

        Args:
            uuid: Animation UUID

        Returns:
            True if toggled successfully
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()

                # Get current favorite status
                cursor.execute('SELECT is_favorite FROM animations WHERE uuid = ?', (uuid,))
                result = cursor.fetchone()
                if not result:
                    return False

                new_status = 0 if result[0] == 1 else 1

                # Update favorite status
                cursor.execute(
                    'UPDATE animations SET is_favorite = ?, modified_date = CURRENT_TIMESTAMP WHERE uuid = ?',
                    (new_status, uuid)
                )

                return cursor.rowcount > 0
        except Exception:
            return False

    def set_favorite(self, uuid: str, is_favorite: bool) -> bool:
        """
        Set favorite status for an animation

        Args:
            uuid: Animation UUID
            is_favorite: True to mark as favorite, False to unmark

        Returns:
            True if updated successfully
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE animations SET is_favorite = ?, modified_date = CURRENT_TIMESTAMP WHERE uuid = ?',
                    (1 if is_favorite else 0, uuid)
                )
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_favorite_animations(self) -> List[Dict[str, Any]]:
        """
        Get all favorite animations

        Returns:
            List of favorite animation dicts
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM animations WHERE is_favorite = 1 ORDER BY name')

            results = []
            for row in cursor.fetchall():
                data = dict(row)
                # Deserialize tags
                if data.get('tags'):
                    try:
                        data['tags'] = json.loads(data['tags'])
                    except:
                        data['tags'] = []
                results.append(data)

            return results
        except Exception:
            return []

    def update_last_viewed(self, uuid: str) -> bool:
        """
        Update last viewed timestamp for an animation

        Args:
            uuid: Animation UUID

        Returns:
            True if updated successfully
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE animations SET last_viewed_date = CURRENT_TIMESTAMP WHERE uuid = ?',
                    (uuid,)
                )
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_recent_animations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recently viewed animations

        Args:
            limit: Maximum number of animations to return (default 20)

        Returns:
            List of recent animation dicts, ordered by last viewed date
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM animations
                WHERE last_viewed_date IS NOT NULL
                ORDER BY last_viewed_date DESC
                LIMIT ?
            ''', (limit,))

            results = []
            for row in cursor.fetchall():
                data = dict(row)
                # Deserialize tags
                if data.get('tags'):
                    try:
                        data['tags'] = json.loads(data['tags'])
                    except:
                        data['tags'] = []
                results.append(data)

            return results
        except Exception:
            return []

    def get_animations_filtered(
        self,
        folder_id: Optional[int] = None,
        rig_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        favorites_only: bool = False,
        sort_by: str = "name",
        sort_order: str = "ASC"
    ) -> List[Dict[str, Any]]:
        """
        Get animations with advanced filtering and sorting

        Args:
            folder_id: Optional folder ID to filter by
            rig_types: Optional list of rig types to filter by
            tags: Optional list of tags to filter by (OR logic)
            favorites_only: If True, only return favorites
            sort_by: Column to sort by (name, created_date, duration_seconds, rig_type, last_viewed_date)
            sort_order: Sort order (ASC or DESC)

        Returns:
            List of animation dicts
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build query
            query = "SELECT * FROM animations WHERE 1=1"
            params = []

            if folder_id is not None:
                query += " AND folder_id = ?"
                params.append(folder_id)

            if rig_types:
                placeholders = ','.join(['?'] * len(rig_types))
                query += f" AND rig_type IN ({placeholders})"
                params.extend(rig_types)

            if tags:
                # OR logic for tags (animation has ANY of the specified tags)
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("tags LIKE ?")
                    params.append(f'%"{tag}"%')  # JSON array contains this tag
                query += f" AND ({' OR '.join(tag_conditions)})"

            if favorites_only:
                query += " AND is_favorite = 1"

            # Add sorting
            valid_sort_columns = ["name", "created_date", "duration_seconds", "rig_type", "last_viewed_date", "custom_order"]
            if sort_by in valid_sort_columns:
                query += f" ORDER BY {sort_by} {sort_order}"
            else:
                query += " ORDER BY name ASC"

            cursor.execute(query, params)

            results = []
            for row in cursor.fetchall():
                data = dict(row)
                # Deserialize tags
                if data.get('tags'):
                    try:
                        data['tags'] = json.loads(data['tags'])
                    except:
                        data['tags'] = []
                results.append(data)

            return results
        except Exception:
            return []

    def get_all_tags(self) -> List[str]:
        """
        Get all unique tags used across all animations

        Returns:
            List of unique tag strings
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT DISTINCT tags FROM animations WHERE tags IS NOT NULL AND tags != ""')

            all_tags = set()
            for row in cursor.fetchall():
                tags_json = row[0]
                if tags_json:
                    try:
                        tags = json.loads(tags_json)
                        if isinstance(tags, list):
                            all_tags.update(tags)
                    except:
                        pass

            return sorted(list(all_tags))
        except Exception:
            return []

    def get_all_rig_types(self) -> List[str]:
        """
        Get all unique rig types used across all animations

        Returns:
            List of unique rig type strings
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT DISTINCT rig_type FROM animations WHERE rig_type IS NOT NULL ORDER BY rig_type')

            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []

    # ==================== LIBRARY SCANNING ====================

    def _is_uuid_folder(self, folder_name: str) -> bool:
        """
        Check if folder name is a valid UUID

        Args:
            folder_name: Folder name to check

        Returns:
            True if valid UUID format
        """
        import re
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        return bool(re.match(uuid_pattern, folder_name.lower()))

    def import_animation_from_json(self, json_file_path: Path) -> bool:
        """
        Import animation from JSON file into database

        Args:
            json_file_path: Path to animation JSON file

        Returns:
            True if imported successfully, False otherwise
        """
        try:
            # Load JSON data
            with open(json_file_path, 'r', encoding='utf-8') as f:
                animation_data = json.load(f)

            # Normalize: handle both 'uuid' and 'id' fields
            uuid = animation_data.get('uuid') or animation_data.get('id')
            if not uuid:
                return False

            # Ensure 'uuid' key exists (Blender plugin uses 'id')
            if 'uuid' not in animation_data:
                animation_data['uuid'] = uuid

            existing = self.get_animation_by_uuid(uuid)
            if existing:
                # Animation already in database - skip
                return False

            # Ensure folder_id is set (default to root folder for uncategorized animations)
            if 'folder_id' not in animation_data or animation_data['folder_id'] is None:
                animation_data['folder_id'] = self.get_root_folder_id()

            # Add to database
            result = self.add_animation(animation_data)
            return result is not None

        except Exception:
            return False

    def scan_library_folder(self, library_path: Path) -> Tuple[int, int]:
        """
        Scan library folder for animations and import them into database

        Args:
            library_path: Path to animation library root

        Returns:
            Tuple of (total_found, newly_imported)
        """
        if not library_path or not library_path.exists():
            return (0, 0)

        total_found = 0
        newly_imported = 0

        try:
            # Scan library folder (supports nested subfolders)
            library_dir = library_path / "library"
            if library_dir.exists():
                import os
                for root, dirs, files in os.walk(library_dir):
                    root_path = Path(root)
                    for dirname in dirs:
                        if self._is_uuid_folder(dirname):
                            folder_path = root_path / dirname
                            total_found += 1
                            json_file = folder_path / f"{dirname}.json"
                            if json_file.exists():
                                if self.import_animation_from_json(json_file):
                                    newly_imported += 1

            return (total_found, newly_imported)

        except Exception:
            return (total_found, newly_imported)

    def sync_library(self) -> Tuple[int, int]:
        """
        Sync library with database (scan configured library path)

        Returns:
            Tuple of (total_found, newly_imported)
        """
        library_path = Config.load_library_path()
        if not library_path:
            return (0, 0)

        return self.scan_library_folder(library_path)

    # ==================== METADATA EXPORT/IMPORT ====================

    def get_all_animation_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for all animations, keyed by UUID.
        Used for library export.

        Returns:
            Dict mapping UUID to metadata (tags, favorite, locked, gradient, folder_path)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.uuid, a.tags, a.is_favorite, a.is_locked,
                       a.use_custom_thumbnail_gradient,
                       a.thumbnail_gradient_top, a.thumbnail_gradient_bottom,
                       f.path as folder_path
                FROM animations a
                LEFT JOIN folders f ON a.folder_id = f.id
            ''')

            result = {}
            for row in cursor.fetchall():
                uuid = row['uuid']
                if not uuid:
                    continue

                metadata = {}

                # Tags (stored as JSON string)
                if row['tags']:
                    try:
                        import json
                        metadata['tags'] = json.loads(row['tags'])
                    except (json.JSONDecodeError, TypeError):
                        metadata['tags'] = []

                # Booleans
                if row['is_favorite']:
                    metadata['is_favorite'] = True
                if row['is_locked']:
                    metadata['is_locked'] = True

                # Custom gradient
                if row['use_custom_thumbnail_gradient']:
                    metadata['custom_gradient'] = {
                        'enabled': True,
                        'top': row['thumbnail_gradient_top'] or '',
                        'bottom': row['thumbnail_gradient_bottom'] or ''
                    }

                # Folder path
                if row['folder_path']:
                    metadata['folder_path'] = row['folder_path']

                # Only include if there's actual metadata
                if metadata:
                    result[uuid] = metadata

            return result
        except Exception:
            return {}

    def update_animation_metadata_by_uuid(self, uuid: str, metadata: Dict[str, Any]) -> bool:
        """
        Update metadata fields for an animation by UUID.
        Used for library import.

        Args:
            uuid: Animation UUID
            metadata: Dict with optional keys: tags, is_favorite, is_locked,
                     custom_gradient, folder_path

        Returns:
            True if updated, False on error
        """
        try:
            # Build dynamic update query
            updates = []
            params = []

            # Tags - merge with existing
            if 'tags' in metadata:
                import json
                new_tags = metadata['tags']
                if isinstance(new_tags, list):
                    # Get existing tags
                    existing = self.get_animation_by_uuid(uuid)
                    if existing and existing.get('tags'):
                        try:
                            existing_tags = json.loads(existing['tags'])
                            if isinstance(existing_tags, list):
                                # Union of both tag sets
                                new_tags = list(set(existing_tags) | set(new_tags))
                        except (json.JSONDecodeError, TypeError):
                            pass
                    updates.append('tags = ?')
                    params.append(json.dumps(new_tags))

            # Booleans - import wins if true
            if metadata.get('is_favorite'):
                updates.append('is_favorite = ?')
                params.append(1)

            if metadata.get('is_locked'):
                updates.append('is_locked = ?')
                params.append(1)

            # Custom gradient
            if 'custom_gradient' in metadata:
                gradient = metadata['custom_gradient']
                if gradient.get('enabled'):
                    updates.append('use_custom_thumbnail_gradient = ?')
                    params.append(1)
                    updates.append('thumbnail_gradient_top = ?')
                    params.append(gradient.get('top', ''))
                    updates.append('thumbnail_gradient_bottom = ?')
                    params.append(gradient.get('bottom', ''))

            # Folder path - move animation to specified folder
            if 'folder_path' in metadata:
                folder = self.get_folder_by_path(metadata['folder_path'])
                if folder:
                    updates.append('folder_id = ?')
                    params.append(folder['id'])

            if not updates:
                return True  # Nothing to update

            params.append(uuid)
            query = f"UPDATE animations SET {', '.join(updates)} WHERE uuid = ?"

            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.rowcount > 0

        except Exception:
            return False

    def get_folder_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get folder by its path string.

        Args:
            path: Folder path (e.g., "Body/Combat")

        Returns:
            Folder dict or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM folders WHERE path = ?', (path,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception:
            return None

    def ensure_folder_exists(self, path: str, description: str = None) -> Optional[int]:
        """
        Ensure folder hierarchy exists, creating missing folders.
        Used for library import.

        Args:
            path: Full folder path (e.g., "Body/Combat")
            description: Optional folder description

        Returns:
            Folder ID if exists/created, None on error
        """
        if not path:
            return self.get_root_folder_id()

        try:
            # Check if folder already exists
            existing = self.get_folder_by_path(path)
            if existing:
                # Update description if provided
                if description and description != existing.get('description'):
                    with self.transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            'UPDATE folders SET description = ? WHERE id = ?',
                            (description, existing['id'])
                        )
                return existing['id']

            # Need to create folder - ensure parent exists first
            parts = path.split('/')
            parent_id = self.get_root_folder_id()

            for i, part in enumerate(parts):
                current_path = '/'.join(parts[:i + 1])
                folder = self.get_folder_by_path(current_path)

                if folder:
                    parent_id = folder['id']
                else:
                    # Create this folder
                    is_last = (i == len(parts) - 1)
                    folder_id = self.create_folder(
                        name=part,
                        parent_id=parent_id,
                        description=description if is_last else None
                    )
                    if folder_id:
                        parent_id = folder_id
                    else:
                        return None

            return parent_id

        except Exception:
            return None

    def get_all_folders_with_paths(self) -> List[Dict[str, Any]]:
        """
        Get all folders with their full paths.
        Used for library export.

        Returns:
            List of folder dicts with path, description
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # Exclude root folder (path is empty or just the name)
            cursor.execute('''
                SELECT path, description FROM folders
                WHERE parent_id IS NOT NULL
                ORDER BY path
            ''')
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def close(self):
        """Close database connection for current thread"""
        if hasattr(self.local, 'connection') and self.local.connection:
            self.local.connection.close()
            self.local.connection = None


# Singleton instance
_database_service_instance: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """
    Get global DatabaseService singleton instance

    Returns:
        Global DatabaseService instance
    """
    global _database_service_instance
    if _database_service_instance is None:
        _database_service_instance = DatabaseService()
    return _database_service_instance


__all__ = ['DatabaseService', 'get_database_service']
