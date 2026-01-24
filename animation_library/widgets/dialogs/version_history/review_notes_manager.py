"""
Review notes manager for VersionHistoryDialog.

Handles CRUD operations for review notes with audit trail support.
"""

from typing import TYPE_CHECKING, Optional, List, Dict, Any, Callable

from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from ....services.notes_database import NotesDatabase


class ReviewNotesManager:
    """
    Manages review notes for version history.

    Handles:
    - Loading notes for a version
    - Adding new notes
    - Resolving/unresolving notes
    - Soft delete with audit trail
    - Restoring deleted notes
    - Editing notes
    """

    def __init__(
        self,
        parent_widget: 'QWidget',
        notes_db: 'NotesDatabase',
        is_studio_mode: bool,
        current_user: str,
        current_user_role: str,
        on_notes_changed: Callable[[], None]
    ):
        """
        Initialize review notes manager.

        Args:
            parent_widget: Parent widget for dialogs
            notes_db: Notes database service
            is_studio_mode: Whether studio mode is active
            current_user: Current user name
            current_user_role: Current user role
            on_notes_changed: Callback when notes change (for reload)
        """
        self._parent = parent_widget
        self._notes_db = notes_db
        self._is_studio_mode = is_studio_mode
        self._current_user = current_user
        self._current_user_role = current_user_role
        self._on_notes_changed = on_notes_changed

        self._show_deleted = False
        self._review_notes: List[Dict] = []

    @property
    def notes(self) -> List[Dict]:
        """Get current notes list."""
        return self._review_notes

    @property
    def show_deleted(self) -> bool:
        """Get show deleted state."""
        return self._show_deleted

    @show_deleted.setter
    def show_deleted(self, value: bool):
        """Set show deleted state."""
        self._show_deleted = value

    def load_notes(self, animation_uuid: str, version_label: str) -> List[Dict]:
        """
        Load review notes for a version.

        Args:
            animation_uuid: Animation UUID
            version_label: Version label

        Returns:
            List of note dictionaries
        """
        if not animation_uuid or not version_label:
            self._review_notes = []
            return []

        self._review_notes = self._notes_db.get_notes_for_version(
            animation_uuid,
            version_label,
            include_deleted=self._show_deleted
        )

        return self._review_notes

    def get_active_notes(self) -> List[Dict]:
        """Get only non-deleted notes (for timeline markers)."""
        return [n for n in self._review_notes if not n.get('deleted', 0)]

    def add_note(
        self,
        animation_uuid: str,
        version_label: str,
        frame: int,
        text: str
    ) -> bool:
        """
        Add a new note.

        Args:
            animation_uuid: Animation UUID
            version_label: Version label
            frame: Frame number
            text: Note text

        Returns:
            True if note was added successfully
        """
        if not text:
            return False

        if not animation_uuid or not version_label:
            QMessageBox.warning(self._parent, "Error", "No version selected.")
            return False

        note_id = self._notes_db.add_note(
            animation_uuid,
            version_label,
            frame,
            text,
            author=self._current_user if self._is_studio_mode else '',
            author_role=self._current_user_role if self._is_studio_mode else 'artist'
        )

        if note_id:
            self._on_notes_changed()
            return True
        else:
            QMessageBox.warning(self._parent, "Error", "Failed to add note.")
            return False

    def resolve_note(self, note_id: int, resolved: bool) -> bool:
        """
        Set note resolved status.

        Args:
            note_id: Note ID
            resolved: New resolved status

        Returns:
            True if successful
        """
        if self._notes_db.set_note_resolved(note_id, resolved):
            self._on_notes_changed()
            return True
        else:
            QMessageBox.warning(self._parent, "Error", "Failed to update note.")
            return False

    def delete_note(self, note_id: int, confirm: bool = True) -> bool:
        """
        Delete a note (soft delete with audit trail).

        Args:
            note_id: Note ID
            confirm: Whether to show confirmation dialog

        Returns:
            True if deleted successfully
        """
        if confirm:
            reply = QMessageBox.question(
                self._parent, "Delete Note", "Delete this review note?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        success = self._notes_db.soft_delete_note(
            note_id,
            deleted_by=self._current_user if self._is_studio_mode else 'user',
            actor_role=self._current_user_role if self._is_studio_mode else ''
        )

        if success:
            self._on_notes_changed()
            return True
        else:
            QMessageBox.warning(self._parent, "Error", "Failed to delete note.")
            return False

    def restore_note(self, note_id: int) -> bool:
        """
        Restore a soft-deleted note.

        Args:
            note_id: Note ID

        Returns:
            True if restored successfully
        """
        success = self._notes_db.restore_note(
            note_id,
            restored_by=self._current_user if self._is_studio_mode else 'user',
            actor_role=self._current_user_role if self._is_studio_mode else ''
        )

        if success:
            self._on_notes_changed()
            return True
        else:
            QMessageBox.warning(self._parent, "Error", "Failed to restore note.")
            return False

    def edit_note(self, note_id: int, new_text: str) -> bool:
        """
        Edit note text with audit trail.

        Args:
            note_id: Note ID
            new_text: New note text

        Returns:
            True if updated successfully
        """
        success = self._notes_db.update_note(
            note_id,
            new_text,
            actor=self._current_user if self._is_studio_mode else '',
            actor_role=self._current_user_role if self._is_studio_mode else ''
        )

        if success:
            self._on_notes_changed()
            return True
        else:
            QMessageBox.warning(self._parent, "Error", "Failed to update note.")
            return False


__all__ = ['ReviewNotesManager']
