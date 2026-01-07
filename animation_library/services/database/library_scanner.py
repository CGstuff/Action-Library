"""
Library Scanner - Library scanning and metadata import/export

Handles scanning animation libraries and syncing with database.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

from .connection import DatabaseConnection
from .animations import AnimationRepository
from .folders import FolderRepository
from .helpers import is_valid_uuid, parse_json_field


class LibraryScanner:
    """
    Library scanning and metadata operations.

    Handles:
    - Scanning library folders for animations
    - Importing animations from JSON
    - Metadata export/import
    """

    def __init__(
        self,
        connection: DatabaseConnection,
        animations: AnimationRepository,
        folders: FolderRepository
    ):
        """
        Initialize library scanner.

        Args:
            connection: Database connection manager
            animations: Animation repository
            folders: Folder repository
        """
        self._conn = connection
        self._animations = animations
        self._folders = folders

    def import_from_json(self, json_file_path: Path) -> bool:
        """
        Import animation from JSON file into database.

        Args:
            json_file_path: Path to animation JSON file

        Returns:
            True if imported successfully
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                animation_data = json.load(f)

            # Normalize: handle both 'uuid' and 'id' fields
            uuid = animation_data.get('uuid') or animation_data.get('id')
            if not uuid:
                return False

            # Ensure 'uuid' key exists
            if 'uuid' not in animation_data:
                animation_data['uuid'] = uuid

            existing = self._animations.get_by_uuid(uuid)
            if existing:
                return False  # Already exists

            # Ensure folder_id is set
            if 'folder_id' not in animation_data or animation_data['folder_id'] is None:
                animation_data['folder_id'] = self._folders.get_root_id()

            result = self._animations.add(animation_data)
            return result is not None

        except Exception:
            return False

    def scan_folder(self, library_path: Path) -> Tuple[int, int]:
        """
        Scan library folder for animations and import them.

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
            library_dir = library_path / "library"
            if library_dir.exists():
                for root, dirs, files in os.walk(library_dir):
                    root_path = Path(root)
                    for dirname in dirs:
                        if is_valid_uuid(dirname):
                            folder_path = root_path / dirname
                            total_found += 1
                            json_file = folder_path / f"{dirname}.json"
                            if json_file.exists():
                                if self.import_from_json(json_file):
                                    newly_imported += 1

            return (total_found, newly_imported)

        except Exception:
            return (total_found, newly_imported)

    def sync_library(self, library_path: Path) -> Tuple[int, int]:
        """
        Sync library with database.

        Args:
            library_path: Path to animation library

        Returns:
            Tuple of (total_found, newly_imported)
        """
        if not library_path:
            return (0, 0)
        return self.scan_folder(library_path)

    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for all animations, keyed by UUID.

        Returns:
            Dict mapping UUID to metadata
        """
        try:
            conn = self._conn.get_connection()
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

                # Tags
                if row['tags']:
                    metadata['tags'] = parse_json_field(row['tags'], [])

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

                if metadata:
                    result[uuid] = metadata

            return result
        except Exception:
            return {}

    def update_metadata_by_uuid(self, uuid: str, metadata: Dict[str, Any]) -> bool:
        """
        Update metadata fields for an animation by UUID.

        Args:
            uuid: Animation UUID
            metadata: Dict with optional keys

        Returns:
            True if updated
        """
        try:
            updates = []
            params = []

            # Tags - merge with existing
            if 'tags' in metadata:
                new_tags = metadata['tags']
                if isinstance(new_tags, list):
                    existing = self._animations.get_by_uuid(uuid)
                    if existing and existing.get('tags'):
                        existing_tags = existing['tags']
                        if isinstance(existing_tags, list):
                            new_tags = list(set(existing_tags) | set(new_tags))
                    updates.append('tags = ?')
                    params.append(json.dumps(new_tags))

            # Booleans
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

            # Folder path
            if 'folder_path' in metadata:
                folder = self._folders.get_by_path(metadata['folder_path'])
                if folder:
                    updates.append('folder_id = ?')
                    params.append(folder['id'])

            if not updates:
                return True  # Nothing to update

            params.append(uuid)
            query = f"UPDATE animations SET {', '.join(updates)} WHERE uuid = ?"

            with self._conn.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.rowcount > 0

        except Exception:
            return False


__all__ = ['LibraryScanner']
