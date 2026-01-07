"""
Archive Repository - Database operations for archived animations

Handles soft-deleted animations in the archive table.
"""

from typing import List, Dict, Optional, Any

from .connection import DatabaseConnection
from .helpers import row_to_dict, rows_to_list


class ArchiveRepository:
    """
    Repository for archive database operations.

    Handles first-stage deletion (soft delete to archive).
    """

    def __init__(self, connection: DatabaseConnection):
        """
        Initialize archive repository.

        Args:
            connection: Database connection manager
        """
        self._conn = connection

    def add(self, archive_data: Dict[str, Any]) -> Optional[int]:
        """
        Add animation to archive table (soft delete).

        Args:
            archive_data: Dict with keys:
                - uuid (required)
                - name (required)
                - archive_folder_path (required)
                - original_folder_id
                - original_folder_path
                - rig_type, frame_count, duration_seconds, file_size_mb
                - thumbnail_path
                - original_created_date

        Returns:
            Archive record ID or None on error
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO archive (
                        uuid, name, original_folder_id, original_folder_path,
                        rig_type, frame_count, duration_seconds, file_size_mb,
                        archive_folder_path, thumbnail_path,
                        archived_date, original_created_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ''', (
                    archive_data.get('uuid'),
                    archive_data.get('name'),
                    archive_data.get('original_folder_id'),
                    archive_data.get('original_folder_path'),
                    archive_data.get('rig_type'),
                    archive_data.get('frame_count'),
                    archive_data.get('duration_seconds'),
                    archive_data.get('file_size_mb'),
                    archive_data.get('archive_folder_path'),
                    archive_data.get('thumbnail_path'),
                    archive_data.get('original_created_date')
                ))
                return cursor.lastrowid
        except Exception:
            return None

    def get_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get archive item by UUID.

        Args:
            uuid: Animation UUID

        Returns:
            Archive item data dict or None
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM archive WHERE uuid = ?', (uuid,))
            return row_to_dict(cursor.fetchone())
        except Exception:
            return None

    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all items in archive.

        Returns:
            List of archive item dicts, ordered by archived_date DESC
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM archive ORDER BY archived_date DESC')
            return rows_to_list(cursor.fetchall())
        except Exception:
            return []

    def delete(self, uuid: str) -> bool:
        """
        Remove item from archive table.

        Args:
            uuid: Animation UUID

        Returns:
            True if deleted, False on error
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM archive WHERE uuid = ?', (uuid,))
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_count(self) -> int:
        """
        Get number of items in archive.

        Returns:
            Archive item count
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM archive')
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def get_total_size(self) -> float:
        """
        Get total size of all items in archive.

        Returns:
            Total size in MB
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT SUM(file_size_mb) FROM archive')
            result = cursor.fetchone()
            return result[0] if result[0] else 0.0
        except Exception:
            return 0.0

    def exists(self, uuid: str) -> bool:
        """
        Check if a UUID exists in archive.

        Args:
            uuid: Animation UUID to check

        Returns:
            True if UUID is in archive
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM archive WHERE uuid = ? LIMIT 1', (uuid,))
            return cursor.fetchone() is not None
        except Exception:
            return False


__all__ = ['ArchiveRepository']
