"""
Folder Repository - Database operations for folders

Handles folder CRUD and hierarchy management.
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any

from .connection import DatabaseConnection
from .helpers import row_to_dict, rows_to_list


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

    def create(self, name: str, parent_id: Optional[int] = None,
               description: str = "") -> Optional[int]:
        """
        Create new folder.

        Args:
            name: Folder name
            parent_id: Parent folder ID (None for root level)
            description: Folder description

        Returns:
            Folder ID or None on error
        """
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

    def delete(self, folder_id: int) -> bool:
        """
        Delete folder (and all contained animations via CASCADE).

        Args:
            folder_id: Folder ID to delete

        Returns:
            True if deleted, False on error
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
                return cursor.rowcount > 0
        except Exception:
            return False

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
