"""
Review Notes Repository - Database operations for frame-specific review notes

Handles CRUD operations for dailies review notes attached to animation versions.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any

from .connection import DatabaseConnection


class ReviewNotesRepository:
    """
    Repository for review notes database operations.

    Handles:
    - Adding/updating/deleting review notes
    - Querying notes by animation UUID
    - Toggling resolved status
    """

    def __init__(self, connection: DatabaseConnection):
        """
        Initialize review notes repository.

        Args:
            connection: Database connection manager
        """
        self._conn = connection

    def get_notes_for_animation(self, animation_uuid: str) -> List[Dict[str, Any]]:
        """
        Get all review notes for an animation, ordered by frame.

        Args:
            animation_uuid: UUID of the animation

        Returns:
            List of note dicts with id, frame, note, author, created_date, resolved
        """
        conn = self._conn.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, animation_uuid, frame, note, author, created_date, resolved
            FROM review_notes
            WHERE animation_uuid = ?
            ORDER BY frame ASC
        ''', (animation_uuid,))

        notes = []
        for row in cursor.fetchall():
            notes.append({
                'id': row[0],
                'animation_uuid': row[1],
                'frame': row[2],
                'note': row[3],
                'author': row[4],
                'created_date': row[5],
                'resolved': bool(row[6])
            })

        return notes

    def add_note(
        self,
        animation_uuid: str,
        frame: int,
        note: str,
        author: str = ''
    ) -> Optional[int]:
        """
        Add a new review note.

        Args:
            animation_uuid: UUID of the animation
            frame: Frame number for the note
            note: Note text content
            author: Author name (optional)

        Returns:
            Note ID or None on error
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO review_notes (animation_uuid, frame, note, author, created_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (animation_uuid, frame, note, author, datetime.now()))

                return cursor.lastrowid

        except Exception as e:
            print(f"Error adding review note: {e}")
            return None

    def update_note(self, note_id: int, note: str) -> bool:
        """
        Update note text content.

        Args:
            note_id: ID of the note to update
            note: New note text

        Returns:
            True if successful
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE review_notes
                    SET note = ?
                    WHERE id = ?
                ''', (note, note_id))

                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating review note: {e}")
            return False

    def update_note_frame(self, note_id: int, frame: int) -> bool:
        """
        Update note frame number.

        Args:
            note_id: ID of the note to update
            frame: New frame number

        Returns:
            True if successful
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE review_notes
                    SET frame = ?
                    WHERE id = ?
                ''', (frame, note_id))

                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating review note frame: {e}")
            return False

    def delete_note(self, note_id: int) -> bool:
        """
        Delete a review note.

        Args:
            note_id: ID of the note to delete

        Returns:
            True if successful
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('DELETE FROM review_notes WHERE id = ?', (note_id,))

                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error deleting review note: {e}")
            return False

    def toggle_resolved(self, note_id: int) -> Optional[bool]:
        """
        Toggle the resolved status of a note.

        Args:
            note_id: ID of the note

        Returns:
            New resolved status, or None on error
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()

            # Get current status
            cursor.execute('SELECT resolved FROM review_notes WHERE id = ?', (note_id,))
            row = cursor.fetchone()

            if not row:
                return None

            new_status = 0 if row[0] else 1

            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE review_notes
                    SET resolved = ?
                    WHERE id = ?
                ''', (new_status, note_id))

            return bool(new_status)

        except Exception as e:
            print(f"Error toggling review note resolved status: {e}")
            return None

    def set_resolved(self, note_id: int, resolved: bool) -> bool:
        """
        Set the resolved status of a note.

        Args:
            note_id: ID of the note
            resolved: New resolved status

        Returns:
            True if successful
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE review_notes
                    SET resolved = ?
                    WHERE id = ?
                ''', (1 if resolved else 0, note_id))

                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error setting review note resolved status: {e}")
            return False

    def get_note_count(self, animation_uuid: str) -> int:
        """
        Get count of review notes for an animation.

        Args:
            animation_uuid: UUID of the animation

        Returns:
            Number of notes
        """
        conn = self._conn.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM review_notes WHERE animation_uuid = ?
        ''', (animation_uuid,))

        return cursor.fetchone()[0]

    def get_unresolved_count(self, animation_uuid: str) -> int:
        """
        Get count of unresolved review notes for an animation.

        Args:
            animation_uuid: UUID of the animation

        Returns:
            Number of unresolved notes
        """
        conn = self._conn.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM review_notes
            WHERE animation_uuid = ? AND resolved = 0
        ''', (animation_uuid,))

        return cursor.fetchone()[0]

    def delete_notes_for_animation(self, animation_uuid: str) -> int:
        """
        Delete all review notes for an animation.

        Args:
            animation_uuid: UUID of the animation

        Returns:
            Number of notes deleted
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    DELETE FROM review_notes WHERE animation_uuid = ?
                ''', (animation_uuid,))

                return cursor.rowcount

        except Exception as e:
            print(f"Error deleting review notes: {e}")
            return 0


__all__ = ['ReviewNotesRepository']
