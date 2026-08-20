"""
Folder Repository - Database operations for folders

Handles folder CRUD and hierarchy management.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .connection import DatabaseConnection
from .helpers import row_to_dict, rows_to_list

logger = logging.getLogger(__name__)


class FolderRepository:
    """
    Repository for folder database operations.

    Handles:
    - Folder CRUD operations
    - Hierarchy management
    - Path resolution
    """

    def __init__(self, connection: DatabaseConnection):
        """
        Initialize folder repository.

        Args:
            connection: Database connection manager
        """
        self._conn = connection

    def get_root_id(self) -> int:
        """
        Get the ID of the root folder.

        Returns:
            Root folder ID
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM folders WHERE parent_id IS NULL LIMIT 1')
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                # Create root folder if it doesn't exist
                with self._conn.transaction() as trans_conn:
                    trans_cursor = trans_conn.cursor()
                    now = datetime.now()
                    trans_cursor.execute('''
                        INSERT INTO folders (name, parent_id, path, created_date, modified_date)
                        VALUES (?, ?, ?, ?, ?)
                    ''', ("Root", None, "", now, now))
                    return trans_cursor.lastrowid
        except Exception:
            return 1  # Fallback to ID 1

    def sibling_name_taken(self, parent_id: Optional[int], name: str,
                           ignore_id: Optional[int] = None) -> bool:
        """Is a sibling already using this name, ignoring case?

        The `path` UNIQUE constraint blocks exact duplicates, but SQLite compares
        TEXT with a binary collation - so `Combat` and `combat` sail past it and
        you end up with two folders that look identical in the tree. This is the
        guard; it's enforced in code rather than as a COLLATE NOCASE index so no
        migration can fail on a library that already contains such a pair.

        Args:
            ignore_id: Folder to skip - a rename shouldn't collide with itself.
        """
        from ..tag_utils import tag_key   # same fold rule as tags

        target = tag_key(name)
        if not target:
            return False
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            if parent_id is None:
                cursor.execute('SELECT id, name FROM folders WHERE parent_id IS NULL')
            else:
                cursor.execute('SELECT id, name FROM folders WHERE parent_id = ?', (parent_id,))
            for row in cursor.fetchall():
                if ignore_id is not None and row['id'] == ignore_id:
                    continue
                if tag_key(row['name']) == target:
                    return True
            return False
        except Exception:
            return False

    def create(self, name: str, parent_id: Optional[int] = None,
               description: str = "") -> Optional[int]:
        """
        Create new folder.

        Args:
            name: Folder name
            parent_id: Parent folder ID (None for root level)
            description: Folder description

        Returns:
            Folder ID or None on error (including a name a sibling already uses,
            ignoring case)
        """
        name = (name or '').strip()
        if not name:
            return None
        if '/' in name:
            # `path` is a '/'-joined cache of names; a separator in a name would
            # corrupt every descendant path derived from it.
            logger.warning(f"Refusing folder name containing '/': {name!r}")
            return None
        if self.sibling_name_taken(parent_id, name):
            logger.warning(f"Folder name already in use at this level: {name!r}")
            return None

        try:
            with self._conn.transaction() as conn:
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

    def get_by_id(self, folder_id: int) -> Optional[Dict[str, Any]]:
        """
        Get folder by ID.

        Args:
            folder_id: Folder ID

        Returns:
            Folder data dict or None
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM folders WHERE id = ?', (folder_id,))
            return row_to_dict(cursor.fetchone())
        except Exception:
            return None

    def get_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get folder by its path string.

        Args:
            path: Folder path (e.g., "Body/Combat")

        Returns:
            Folder dict or None
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM folders WHERE path = ?', (path,))
            return row_to_dict(cursor.fetchone())
        except Exception:
            return None

    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all folders.

        Returns:
            List of folder dicts
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM folders ORDER BY path')
            return rows_to_list(cursor.fetchall())
        except Exception:
            return []

    def get_descendants(self, folder_id: int) -> List[int]:
        """
        Get all descendant folder IDs (recursive).

        Args:
            folder_id: Parent folder ID

        Returns:
            List of descendant folder IDs (including the folder itself)
        """
        try:
            conn = self._conn.get_connection()
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

    def count_contents(self, folder_id: int) -> Tuple[int, int]:
        """How much is in a folder, counting its subfolders too.

        Returns:
            (animation_count, subfolder_count) - for telling the user what
            they're about to affect BEFORE they confirm.
        """
        try:
            folder_ids = self.get_descendants(folder_id)
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(folder_ids))
            cursor.execute(
                f'SELECT COUNT(*) FROM animations WHERE folder_id IN ({placeholders})',
                tuple(folder_ids),
            )
            animation_count = cursor.fetchone()[0]
            # get_descendants includes the folder itself
            return animation_count, len(folder_ids) - 1
        except Exception:
            return 0, 0

    def delete(self, folder_id: int) -> bool:
        """Delete a folder and its subfolders. Animations inside are KEPT.

        Animations in this folder (and any descendant) are reassigned to the root
        folder FIRST. That step is not optional:

        `animations.folder_id` is declared `ON DELETE CASCADE` and foreign keys
        are enabled, so deleting a folder row would delete the animation ROWS in
        it - taking is_favorite, status and gradients with them. Those live only
        in the database unless the asset has been archived (sync_metadata_to_json
        is called from archive_service, nowhere else). The .blend files would
        survive on disk, so the next scan would re-import the animations looking
        untouched, with that metadata silently gone for good.

        A folder here is a LABEL, not a container - the files live in
        library/actions|poses regardless of which folder they're filed under. So
        deleting the label must never delete the work.

        Args:
            folder_id: Folder ID to delete

        Returns:
            True if deleted, False on error (or if asked to delete the root)
        """
        try:
            root_id = self.get_root_id()
            if folder_id == root_id:
                logger.warning("Refusing to delete the root folder")
                return False

            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                # Rescue the animations before the cascade can reach them.
                folder_ids = self.get_descendants(folder_id)
                placeholders = ','.join('?' * len(folder_ids))
                cursor.execute(
                    f'UPDATE animations SET folder_id = ? WHERE folder_id IN ({placeholders})',
                    (root_id, *folder_ids),
                )
                rescued = cursor.rowcount

                cursor.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
                deleted = cursor.rowcount > 0

                if deleted and rescued:
                    logger.info(
                        f"Deleted folder {folder_id}; moved {rescued} animation(s) to the root folder"
                    )
                return deleted
        except Exception as e:
            logger.error(f"Error deleting folder {folder_id}: {e}")
            return False

    # ==================== MEMBERSHIP ====================
    #
    # An animation is in a folder when a row exists in folder_animations. That's
    # the truth the folder tree filters on. The folder's NAME is also mirrored
    # onto the animation's tags as a convenience (so search finds it, and so the
    # JSON sidecar carries it between machines) - but nothing READS the tag to
    # decide membership. That distinction is the whole point: it's what makes
    # rename possible.

    def add_animation(self, folder_id: int, animation_uuid: str) -> bool:
        """Put an animation in a folder. Additive - it stays in any others."""
        try:
            with self._conn.transaction() as conn:
                conn.cursor().execute(
                    'INSERT OR IGNORE INTO folder_animations (folder_id, animation_uuid) '
                    'VALUES (?, ?)',
                    (folder_id, animation_uuid),
                )
            return True
        except Exception as e:
            logger.error(f"Error adding {animation_uuid} to folder {folder_id}: {e}")
            return False

    def remove_animation(self, folder_id: int, animation_uuid: str) -> bool:
        """Take an animation out of ONE folder, leaving it in any others.

        Not expressible at all before v12: membership was a tag, and moving an
        animation only ever appended tags, so it accumulated one per folder it
        had ever visited and could never leave any of them.
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM folder_animations WHERE folder_id = ? AND animation_uuid = ?',
                    (folder_id, animation_uuid),
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing {animation_uuid} from folder {folder_id}: {e}")
            return False

    def get_animation_uuids(self, folder_id: int) -> List[str]:
        """UUIDs of the animations in this folder (not including subfolders)."""
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT animation_uuid FROM folder_animations WHERE folder_id = ?',
                (folder_id,),
            )
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []

    def get_folders_for_animation(self, animation_uuid: str) -> List[int]:
        """Folder ids this animation belongs to."""
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT folder_id FROM folder_animations WHERE animation_uuid = ?',
                (animation_uuid,),
            )
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []

    def get_membership_map(self) -> Dict[str, List[int]]:
        """Every membership at once, as {animation_uuid: [folder_id, ...]}.

        The filter needs this for every visible row, so it's fetched in one query
        rather than one per animation.
        """
        result: Dict[str, List[int]] = {}
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT animation_uuid, folder_id FROM folder_animations')
            for uuid, folder_id in cursor.fetchall():
                result.setdefault(uuid, []).append(folder_id)
        except Exception as e:
            logger.error(f"Error loading folder membership: {e}")
        return result

    def rename(self, folder_id: int, new_name: str) -> Optional[Dict[str, str]]:
        """Rename a folder.

        Membership is by id, so renaming can't orphan anything - which is exactly
        why this is now possible. It updates the folder's own `path` and every
        descendant's, since `path` is a denormalized cache of the names above it.

        Returns:
            {'old_name', 'new_name', 'old_path', 'new_path'} on success, so the
            caller can sync the name mirrored onto tags and re-key folder icons.
            None on failure.
        """
        new_name = (new_name or '').strip()
        if not new_name:
            return None
        if '/' in new_name:
            # `path` is a '/'-joined cache of names; a name containing the
            # separator would corrupt every descendant path built from it.
            logger.warning(f"Refusing folder name containing '/': {new_name!r}")
            return None

        try:
            folder = self.get_by_id(folder_id)
            if not folder:
                return None
            if folder.get('parent_id') is None:
                logger.warning("Refusing to rename the root folder")
                return None

            old_name = folder['name']
            old_path = folder.get('path') or ''
            if new_name == old_name:
                return {'old_name': old_name, 'new_name': new_name,
                        'old_path': old_path, 'new_path': old_path}

            # Case-insensitive sibling guard. ignore_id so re-casing a folder
            # ('combat' -> 'Combat') isn't blocked by the folder itself.
            if self.sibling_name_taken(folder['parent_id'], new_name, ignore_id=folder_id):
                logger.warning(f"Folder name already in use at this level: {new_name!r}")
                return None

            parent = self.get_by_id(folder['parent_id'])
            parent_path = (parent.get('path') or '') if parent else ''
            new_path = f"{parent_path}/{new_name}" if parent_path else new_name

            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE folders SET name = ?, path = ?, modified_date = ? WHERE id = ?',
                    (new_name, new_path, datetime.now(), folder_id),
                )
                if old_path:
                    self._update_descendant_paths(cursor, old_path, new_path)

            return {'old_name': old_name, 'new_name': new_name,
                    'old_path': old_path, 'new_path': new_path}

        except sqlite3.IntegrityError:
            # `path` is UNIQUE - a sibling already has this name.
            logger.warning(f"Folder name already in use at this level: {new_name!r}")
            return None
        except Exception as e:
            logger.error(f"Error renaming folder {folder_id}: {e}")
            return None

    def update_parent(self, folder_id: int, new_parent_id: int) -> bool:
        """
        Update folder's parent to create hierarchy.

        Args:
            folder_id: Folder to move
            new_parent_id: New parent folder ID

        Returns:
            True if successful
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                # Get folder info
                cursor.execute('SELECT name, parent_id, path FROM folders WHERE id = ?', (folder_id,))
                folder = cursor.fetchone()
                if not folder:
                    return False

                folder_name = folder['name']
                old_path = folder['path']

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

                parent_updated = cursor.rowcount > 0

                # Update paths of all descendant folders
                try:
                    self._update_descendant_paths(cursor, old_path, new_path)
                except Exception:
                    pass  # Continue anyway - parent folder was updated

                return parent_updated
        except Exception:
            return False

    def _update_descendant_paths(self, cursor, old_path_prefix: str, new_path_prefix: str):
        """
        Recursively update paths of all descendant folders.

        Args:
            cursor: Database cursor
            old_path_prefix: Old path prefix
            new_path_prefix: New path prefix
        """
        cursor.execute("""
            SELECT id, path FROM folders
            WHERE path LIKE ?
            ORDER BY path
        """, (f"{old_path_prefix}/%",))

        descendants = cursor.fetchall()

        for row in descendants:
            folder_id = row['id']
            old_path = row['path']
            new_path = old_path.replace(old_path_prefix, new_path_prefix, 1)

            cursor.execute("""
                UPDATE folders
                SET path = ?, modified_date = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_path, folder_id))

    def ensure_exists(self, path: str, description: str = None) -> Optional[int]:
        """
        Ensure folder hierarchy exists, creating missing folders.

        Args:
            path: Full folder path (e.g., "Body/Combat")
            description: Optional folder description

        Returns:
            Folder ID if exists/created, None on error
        """
        if not path:
            return self.get_root_id()

        try:
            # Check if folder already exists
            existing = self.get_by_path(path)
            if existing:
                # Update description if provided
                if description and description != existing.get('description'):
                    with self._conn.transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            'UPDATE folders SET description = ? WHERE id = ?',
                            (description, existing['id'])
                        )
                return existing['id']

            # Need to create folder - ensure parent exists first
            parts = path.split('/')
            parent_id = self.get_root_id()

            for i, part in enumerate(parts):
                current_path = '/'.join(parts[:i + 1])
                folder = self.get_by_path(current_path)

                if folder:
                    parent_id = folder['id']
                else:
                    # Create this folder
                    is_last = (i == len(parts) - 1)
                    folder_id = self.create(
                        name=part,
                        parent_id=parent_id,
                        description=description if is_last else ""
                    )
                    if folder_id:
                        parent_id = folder_id
                    else:
                        return None

            return parent_id

        except Exception:
            return None

    def get_all_with_paths(self) -> List[Dict[str, Any]]:
        """
        Get all folders with their full paths.

        Returns:
            List of folder dicts with path, description
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT path, description FROM folders
                WHERE parent_id IS NOT NULL
                ORDER BY path
            ''')
            return rows_to_list(cursor.fetchall())
        except Exception:
            return []


__all__ = ['FolderRepository']
