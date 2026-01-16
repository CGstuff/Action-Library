"""
Permissions - Role-based permission system for Studio Mode

Handles permission checking for note operations based on user roles.
In Solo mode, all permissions return True.
"""

from typing import Optional
from enum import IntEnum


class RoleLevel(IntEnum):
    """Role hierarchy levels."""
    ARTIST = 1
    LEAD = 2
    DIRECTOR = 2
    SUPERVISOR = 3
    ADMIN = 4


ROLE_LEVELS = {
    'artist': RoleLevel.ARTIST,
    'lead': RoleLevel.LEAD,
    'director': RoleLevel.DIRECTOR,
    'supervisor': RoleLevel.SUPERVISOR,
    'admin': RoleLevel.ADMIN
}

ROLE_LABELS = {
    'artist': 'Artist',
    'lead': 'Lead',
    'director': 'Director',
    'supervisor': 'Supervisor',
    'admin': 'Admin'
}

ROLE_COLORS = {
    'artist': '#888888',
    'lead': '#4FC3F7',
    'director': '#FFB74D',
    'supervisor': '#AB47BC',
    'admin': '#EF5350'
}


class NotePermissions:
    """
    Permission checking for note operations.

    In Solo mode, all methods return True (unrestricted).
    In Studio mode, permissions are role-based.
    """

    @staticmethod
    def get_role_level(role: str) -> int:
        """Get numeric level for a role."""
        return ROLE_LEVELS.get(role.lower(), RoleLevel.ARTIST)

    @staticmethod
    def get_role_label(role: str) -> str:
        """Get display label for a role."""
        return ROLE_LABELS.get(role.lower(), 'Artist')

    @staticmethod
    def get_role_color(role: str) -> str:
        """Get color for a role badge."""
        return ROLE_COLORS.get(role.lower(), '#888888')

    @staticmethod
    def can_add_note(is_studio_mode: bool, user_role: str = '') -> bool:
        """Everyone can add notes."""
        return True

    @staticmethod
    def can_edit_note(
        is_studio_mode: bool,
        user_role: str,
        note_author: str,
        current_user: str
    ) -> bool:
        """
        Check if user can edit a note.

        Solo mode: Always allowed
        Studio mode: Users can only edit their own notes
        """
        if not is_studio_mode:
            return True

        # Users can only edit their own notes
        return note_author == current_user

    @staticmethod
    def can_delete_note(
        is_studio_mode: bool,
        user_role: str,
        note_author: str,
        current_user: str
    ) -> bool:
        """
        Check if user can delete a note.

        Solo mode: Always allowed
        Studio mode:
            - Artists: Cannot delete any notes
            - Leads/Directors: Can delete their own notes only
            - Supervisors/Admins: Can delete any note
        """
        if not is_studio_mode:
            return True

        level = NotePermissions.get_role_level(user_role)

        if level >= RoleLevel.SUPERVISOR:
            return True  # Supervisor/Admin can delete any
        if level >= RoleLevel.LEAD:
            return note_author == current_user  # Lead/Director own notes only
        return False  # Artists cannot delete

    @staticmethod
    def can_restore_note(is_studio_mode: bool, user_role: str) -> bool:
        """
        Check if user can restore deleted notes.

        Solo mode: Always allowed
        Studio mode: Only Supervisors and Admins
        """
        if not is_studio_mode:
            return True

        return NotePermissions.get_role_level(user_role) >= RoleLevel.SUPERVISOR

    @staticmethod
    def can_view_deleted(is_studio_mode: bool, user_role: str) -> bool:
        """
        Check if user can view deleted notes.

        Solo mode: Always allowed (optional toggle)
        Studio mode: Leads and above
        """
        if not is_studio_mode:
            return True

        return NotePermissions.get_role_level(user_role) >= RoleLevel.LEAD

    @staticmethod
    def can_manage_users(is_studio_mode: bool, user_role: str) -> bool:
        """
        Check if user can manage other users.

        Only Admins can manage users.
        """
        if not is_studio_mode:
            return True

        return NotePermissions.get_role_level(user_role) >= RoleLevel.ADMIN

    @staticmethod
    def is_elevated_role(role: str) -> bool:
        """Check if role is Lead or higher (for badge display)."""
        return NotePermissions.get_role_level(role) >= RoleLevel.LEAD


class DrawoverPermissions:
    """
    Permission checking for drawover/annotation operations.

    In Solo mode, all methods return True (unrestricted).
    In Studio mode, permissions are role-based with stroke-level granularity.
    """

    @staticmethod
    def can_add_stroke(is_studio_mode: bool, user_role: str = '') -> bool:
        """Everyone can add strokes/annotations."""
        return True

    @staticmethod
    def can_edit_stroke(
        is_studio_mode: bool,
        user_role: str,
        stroke_author: str,
        current_user: str
    ) -> bool:
        """
        Check if user can edit a stroke.

        Solo mode: Always allowed
        Studio mode: Users can only edit their own strokes
        """
        if not is_studio_mode:
            return True

        return stroke_author == current_user

    @staticmethod
    def can_delete_stroke(
        is_studio_mode: bool,
        user_role: str,
        stroke_author: str,
        current_user: str
    ) -> bool:
        """
        Check if user can delete a stroke.

        Solo mode: Always allowed (hard delete)
        Studio mode:
            - Artists: Cannot delete any strokes
            - Leads/Directors: Can delete their own strokes only
            - Supervisors/Admins: Can delete any stroke
        """
        if not is_studio_mode:
            return True

        level = NotePermissions.get_role_level(user_role)

        if level >= RoleLevel.SUPERVISOR:
            return True  # Supervisor/Admin can delete any
        if level >= RoleLevel.LEAD:
            return stroke_author == current_user  # Lead/Director own strokes only
        return False  # Artists cannot delete

    @staticmethod
    def can_restore_stroke(is_studio_mode: bool, user_role: str) -> bool:
        """
        Check if user can restore deleted strokes.

        Solo mode: N/A (hard delete, no restore)
        Studio mode: Only Supervisors and Admins
        """
        if not is_studio_mode:
            return False  # Solo mode uses hard delete

        return NotePermissions.get_role_level(user_role) >= RoleLevel.SUPERVISOR

    @staticmethod
    def can_clear_frame(
        is_studio_mode: bool,
        user_role: str,
        frame_has_others_strokes: bool
    ) -> bool:
        """
        Check if user can clear all strokes on a frame.

        Solo mode: Always allowed
        Studio mode:
            - If frame only has user's own strokes: Leads and above
            - If frame has other users' strokes: Supervisors and above
        """
        if not is_studio_mode:
            return True

        level = NotePermissions.get_role_level(user_role)

        if frame_has_others_strokes:
            return level >= RoleLevel.SUPERVISOR
        else:
            return level >= RoleLevel.LEAD

    @staticmethod
    def can_view_deleted_strokes(is_studio_mode: bool, user_role: str) -> bool:
        """
        Check if user can view deleted strokes.

        Solo mode: Always allowed
        Studio mode: Leads and above
        """
        if not is_studio_mode:
            return True

        return NotePermissions.get_role_level(user_role) >= RoleLevel.LEAD

    @staticmethod
    def use_soft_delete(is_studio_mode: bool) -> bool:
        """
        Determine if soft delete should be used.

        Solo mode: Hard delete (no audit trail)
        Studio mode: Soft delete (preserves for restore/audit)
        """
        return is_studio_mode


__all__ = [
    'NotePermissions',
    'DrawoverPermissions',
    'RoleLevel',
    'ROLE_LEVELS',
    'ROLE_LABELS',
    'ROLE_COLORS'
]
