"""
Trash Repository - Database operations for trashed animations

Handles second-stage deletion (staging for permanent delete).
"""

from typing import List, Dict, Optional, Any

from .connection import DatabaseConnection
from .helpers import row_to_dict, rows_to_list


class TrashRepository:
    """
    Repository for trash database operations.

    Handles second-stage deletion (trash before permanent delete).
    """

    def __init__(self, connection: DatabaseConnection):
        """
        Initialize trash repository.

        Args:
            connection: Database connection manager
        """
        self._conn = connection

    def add(self, trash_data: Dict[str, Any]) -> Optional[int]:
        """
        Add animation to trash table (staging for hard delete).

        Args:
            trash_data: Dict with keys:
                - uuid (required)
                - name (required)
                - trash_folder_path (required)
                - thumbnail_path
                - archived_date (when it was first archived)

        Returns:
            Trash record ID or None on error
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO trash (
                        uuid, name, trash_folder_path, thumbnail_path,
                        trashed_date, archived_date
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ''', (
                    trash_data.get('uuid'),
                    trash_data.get('name'),
                    trash_data.get('trash_folder_path'),
                    trash_data.get('thumbnail_path'),
                    trash_data.get('archived_date')
                ))
                return cursor.lastrowid
        except Exception:
            return None

    def get_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get trash item by UUID.

        Args:
            uuid: Animation UUID

        Returns:
            Trash item data dict or None
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trash WHERE uuid = ?', (uuid,))
            return row_to_dict(cursor.fetchone())
        except Exception:
            return None

    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all items in trash.

        Returns:
            List of trash item dicts, ordered by trashed_date DESC
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trash ORDER BY trashed_date DESC')
            return rows_to_list(cursor.fetchall())
        except Exception:
            return []

    def delete(self, uuid: str) -> bool:
        """
        Remove item from trash table.

        Args:
            uuid: Animation UUID

        Returns:
            True if deleted, False on error
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trash WHERE uuid = ?', (uuid,))
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_count(self) -> int:
        """
        Get number of items in trash.

        Returns:
            Trash item count
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM trash')
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def exists(self, uuid: str) -> bool:
        """
        Check if a UUID exists in trash.

        Args:
            uuid: Animation UUID to check

        Returns:
            True if UUID is in trash
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM trash WHERE uuid = ? LIMIT 1', (uuid,))
            return cursor.fetchone() is not None
        except Exception:
            return False


__all__ = ['TrashRepository']
