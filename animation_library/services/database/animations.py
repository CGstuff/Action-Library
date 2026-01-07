"""
Animation Repository - Database operations for animations

Handles animation CRUD, search, and filtering.
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Any

from .connection import DatabaseConnection
from .helpers import deserialize_animation, serialize_tags, row_to_dict


class AnimationRepository:
    """
    Repository for animation database operations.

    Handles:
    - Animation CRUD operations
    - Search and filtering
    - Favorites and recent tracking
    """

    def __init__(self, connection: DatabaseConnection):
        """
        Initialize animation repository.

        Args:
            connection: Database connection manager
        """
        self._conn = connection

    def add(self, animation_data: Dict[str, Any]) -> Optional[int]:
        """
        Add animation to database.

        Args:
            animation_data: Animation metadata dict

        Returns:
            Animation database ID or None on error
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                tags_json = serialize_tags(animation_data.get('tags', []))
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

    def get_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get animation by UUID.

        Args:
            uuid: Animation UUID

        Returns:
            Animation data dict or None
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM animations WHERE uuid = ?', (uuid,))
            result = cursor.fetchone()
            return deserialize_animation(dict(result)) if result else None
        except Exception:
            return None

    def get_by_id(self, animation_id: int) -> Optional[Dict[str, Any]]:
        """
        Get animation by database ID.

        Args:
            animation_id: Animation database ID

        Returns:
            Animation data dict or None
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM animations WHERE id = ?', (animation_id,))
            result = cursor.fetchone()
            return deserialize_animation(dict(result)) if result else None
        except Exception:
            return None

    def get_all(self, folder_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all animations, optionally filtered by folder.

        Args:
            folder_id: Optional folder ID to filter by

        Returns:
            List of animation dicts
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()

            if folder_id is not None:
                cursor.execute('SELECT * FROM animations WHERE folder_id = ? ORDER BY name', (folder_id,))
            else:
                cursor.execute('SELECT * FROM animations ORDER BY name')

            return [deserialize_animation(dict(row)) for row in cursor.fetchall()]
        except Exception:
            return []

    def update(self, uuid: str, updates: Dict[str, Any]) -> bool:
        """
        Update animation metadata.

        Args:
            uuid: Animation UUID
            updates: Dict of fields to update

        Returns:
            True if updated, False on error
        """
        try:
            with self._conn.transaction() as conn:
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

    def delete(self, uuid: str) -> bool:
        """
        Delete animation by UUID.

        Args:
            uuid: Animation UUID

        Returns:
            True if deleted, False on error
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM animations WHERE uuid = ?', (uuid,))
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_count(self, folder_id: Optional[int] = None) -> int:
        """
        Get count of animations.

        Args:
            folder_id: Optional folder ID

        Returns:
            Animation count
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()

            if folder_id is not None:
                cursor.execute('SELECT COUNT(*) FROM animations WHERE folder_id = ?', (folder_id,))
            else:
                cursor.execute('SELECT COUNT(*) FROM animations')

            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def move_to_folder(self, uuid: str, folder_id: int) -> bool:
        """
        Move animation to a different folder and add folder name to tags.

        Args:
            uuid: Animation UUID
            folder_id: Target folder ID

        Returns:
            True if successful
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                # Get folder name
                cursor.execute('SELECT name FROM folders WHERE id = ?', (folder_id,))
                folder = cursor.fetchone()
                if not folder:
                    return False

                folder_name = folder['name']

                # Get current animation tags
                cursor.execute('SELECT tags FROM animations WHERE uuid = ?', (uuid,))
                animation = cursor.fetchone()
                if not animation:
                    return False

                # Parse and update tags
                tags = []
                if animation['tags']:
                    try:
                        tags = json.loads(animation['tags'])
                    except:
                        tags = []

                if folder_name not in tags:
                    tags.append(folder_name)

                tags_json = json.dumps(tags)

                # Update both folder_id and tags
                cursor.execute(
                    """
                    UPDATE animations
                    SET folder_id = ?, tags = ?, modified_date = CURRENT_TIMESTAMP
                    WHERE uuid = ?
                    """,
                    (folder_id, tags_json, uuid)
                )

                return cursor.rowcount > 0

        except Exception:
            return False

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search animations by name, description, or tags.

        Args:
            query: Search query

        Returns:
            List of matching animation dicts
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()

            search_pattern = f"%{query}%"
            cursor.execute('''
                SELECT * FROM animations
                WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
                ORDER BY name
            ''', (search_pattern, search_pattern, search_pattern))

            return [deserialize_animation(dict(row)) for row in cursor.fetchall()]
        except Exception:
            return []

    def toggle_favorite(self, uuid: str) -> bool:
        """
        Toggle favorite status for an animation.

        Args:
            uuid: Animation UUID

        Returns:
            True if toggled successfully
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT is_favorite FROM animations WHERE uuid = ?', (uuid,))
                result = cursor.fetchone()
                if not result:
                    return False

                new_status = 0 if result[0] == 1 else 1

                cursor.execute(
                    'UPDATE animations SET is_favorite = ?, modified_date = CURRENT_TIMESTAMP WHERE uuid = ?',
                    (new_status, uuid)
                )

                return cursor.rowcount > 0
        except Exception:
            return False

    def set_favorite(self, uuid: str, is_favorite: bool) -> bool:
        """
        Set favorite status for an animation.

        Args:
            uuid: Animation UUID
            is_favorite: True to mark as favorite

        Returns:
            True if updated successfully
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE animations SET is_favorite = ?, modified_date = CURRENT_TIMESTAMP WHERE uuid = ?',
                    (1 if is_favorite else 0, uuid)
                )
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_favorites(self) -> List[Dict[str, Any]]:
        """
        Get all favorite animations.

        Returns:
            List of favorite animation dicts
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM animations WHERE is_favorite = 1 ORDER BY name')
            return [deserialize_animation(dict(row)) for row in cursor.fetchall()]
        except Exception:
            return []

    def update_last_viewed(self, uuid: str) -> bool:
        """
        Update last viewed timestamp for an animation.

        Args:
            uuid: Animation UUID

        Returns:
            True if updated successfully
        """
        try:
            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE animations SET last_viewed_date = CURRENT_TIMESTAMP WHERE uuid = ?',
                    (uuid,)
                )
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recently viewed animations.

        Args:
            limit: Maximum number to return

        Returns:
            List of recent animation dicts
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM animations
                WHERE last_viewed_date IS NOT NULL
                ORDER BY last_viewed_date DESC
                LIMIT ?
            ''', (limit,))
            return [deserialize_animation(dict(row)) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_filtered(
        self,
        folder_id: Optional[int] = None,
        rig_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        favorites_only: bool = False,
        sort_by: str = "name",
        sort_order: str = "ASC"
    ) -> List[Dict[str, Any]]:
        """
        Get animations with advanced filtering and sorting.

        Args:
            folder_id: Optional folder ID
            rig_types: Optional list of rig types
            tags: Optional list of tags (OR logic)
            favorites_only: If True, only return favorites
            sort_by: Column to sort by
            sort_order: Sort order (ASC or DESC)

        Returns:
            List of animation dicts
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()

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
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("tags LIKE ?")
                    params.append(f'%"{tag}"%')
                query += f" AND ({' OR '.join(tag_conditions)})"

            if favorites_only:
                query += " AND is_favorite = 1"

            # Add sorting
            valid_columns = ["name", "created_date", "duration_seconds", "rig_type",
                            "last_viewed_date", "custom_order"]
            if sort_by in valid_columns:
                query += f" ORDER BY {sort_by} {sort_order}"
            else:
                query += " ORDER BY name ASC"

            cursor.execute(query, params)
            return [deserialize_animation(dict(row)) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_all_tags(self) -> List[str]:
        """
        Get all unique tags used across all animations.

        Returns:
            List of unique tag strings
        """
        try:
            conn = self._conn.get_connection()
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
        Get all unique rig types used across all animations.

        Returns:
            List of unique rig type strings
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT rig_type FROM animations WHERE rig_type IS NOT NULL ORDER BY rig_type')
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []


__all__ = ['AnimationRepository']
