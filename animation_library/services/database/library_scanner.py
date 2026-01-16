"""
Library Scanner - Library scanning and metadata import/export

Handles scanning animation libraries and syncing with database.
"""

import os
import json
import uuid as uuid_lib
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

from .connection import DatabaseConnection
from .animations import AnimationRepository
from .folders import FolderRepository
from .helpers import parse_json_field
from ...config import Config


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

    def _is_legacy_animation(self, animation_data: dict) -> bool:
        """
        Detect if animation JSON is from v1.2 (legacy).

        ONE-TIME migration check: if app_version field is missing,
        this is a legacy v1.2 animation that needs fresh import.

        Args:
            animation_data: Animation data from JSON

        Returns:
            True if legacy v1.2 animation
        """
        # If app_version exists, it's modern (v1.3+)
        if animation_data.get('app_version'):
            return False
        # Missing app_version = legacy v1.2
        return True

    def _convert_to_fresh(self, animation_data: dict, json_file_path: Path) -> dict:
        """
        Convert legacy v1.2 animation to fresh v001.

        Generates new UUID and resets all metadata for clean import.

        Args:
            animation_data: Original animation data
            json_file_path: Path to JSON file (will be updated)

        Returns:
            Fresh animation data dict
        """
        old_uuid = animation_data.get('uuid') or animation_data.get('id')
        new_uuid = str(uuid_lib.uuid4())

        print(f"[SCAN] LEGACY v1.2 DETECTED: {animation_data.get('name', 'unknown')}")
        print(f"[SCAN] Converting {old_uuid[:8] if old_uuid else 'N/A'}... → {new_uuid[:8]}... (fresh v001)")

        # Create fresh animation data - reset all metadata
        fresh_data = {
            'uuid': new_uuid,
            'app_version': '1.3.0',
            'name': animation_data.get('name', 'unknown'),
            # Fresh versioning
            'version': 1,
            'version_label': 'v001',
            'version_group_id': new_uuid,  # Self-referencing = fresh v001
            'is_latest': 1,
            # Keep core animation data
            'rig_type': animation_data.get('rig_type'),
            'armature_name': animation_data.get('armature_name'),
            'bone_count': animation_data.get('bone_count'),
            'bone_names': animation_data.get('bone_names'),
            'action_name': animation_data.get('action_name'),
            'frame_start': animation_data.get('frame_start'),
            'frame_end': animation_data.get('frame_end'),
            'frame_count': animation_data.get('frame_count'),
            'duration_seconds': animation_data.get('duration_seconds'),
            'fps': animation_data.get('fps'),
            'file_size_mb': animation_data.get('file_size_mb'),
            # Keep file paths
            'blend_file_path': animation_data.get('blend_file_path'),
            'json_file_path': str(json_file_path),
            'preview_path': animation_data.get('preview_path'),
            'thumbnail_path': animation_data.get('thumbnail_path'),
            'created_date': animation_data.get('created_date'),
            # Reset all user metadata (clean slate)
            'description': '',
            'author': '',
            'tags': [],
            'is_favorite': 0,
            'is_locked': 0,
            'status': 'none',
            # Keep type flags
            'is_pose': animation_data.get('is_pose', 0),
            'is_partial': animation_data.get('is_partial', 0),
            # Reset studio naming
            'naming_fields': None,
            'naming_template': None,
            # Reset gradient
            'use_custom_thumbnail_gradient': 0,
            'thumbnail_gradient_top': None,
            'thumbnail_gradient_bottom': None,
        }

        # Update JSON file on disk with fresh data
        try:
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(fresh_data, f, indent=2)
            print(f"[SCAN] Updated JSON with fresh UUID")
        except Exception as e:
            print(f"[SCAN] WARNING: Could not update JSON: {e}")

        return fresh_data

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

            # ONE-TIME v1.2→v1.3 migration: detect legacy animations
            if self._is_legacy_animation(animation_data):
                animation_data = self._convert_to_fresh(animation_data, json_file_path)

            # Normalize: handle both 'uuid' and 'id' fields
            uuid = animation_data.get('uuid') or animation_data.get('id')
            name = animation_data.get('name', 'unknown')

            if not uuid:
                print(f"[SCAN] SKIP (no UUID): {json_file_path}")
                return False

            # Check if this is from cold storage (_versions/) - force is_latest = 0
            is_cold_storage = '_versions' in str(json_file_path)
            if is_cold_storage:
                animation_data['is_latest'] = 0
                print(f"[SCAN] Cold storage: {name} - forcing is_latest=0")

            # Ensure 'uuid' key exists
            if 'uuid' not in animation_data:
                animation_data['uuid'] = uuid

            existing = self._animations.get_by_uuid(uuid)
            if existing:
                print(f"[SCAN] EXISTS: {name} (UUID: {uuid[:8]}...) - already in DB")
                # Update flags and naming fields if they differ (for migrations)
                updates = {}
                new_is_pose = animation_data.get('is_pose', 0)
                if existing.get('is_pose', 0) != new_is_pose:
                    updates['is_pose'] = new_is_pose
                new_is_partial = animation_data.get('is_partial', 0)
                if existing.get('is_partial', 0) != new_is_partial:
                    updates['is_partial'] = new_is_partial
                # Update naming fields if present in JSON but missing in database
                new_naming_fields = animation_data.get('naming_fields')
                if new_naming_fields and not existing.get('naming_fields'):
                    updates['naming_fields'] = new_naming_fields
                new_naming_template = animation_data.get('naming_template')
                if new_naming_template and not existing.get('naming_template'):
                    updates['naming_template'] = new_naming_template
                if updates:
                    self._animations.update(uuid, updates)
                return False  # Already exists (but may have updated flags/naming)

            # Ensure folder_id is set
            # Priority: folder_id from JSON > folder_path lookup > root folder
            if 'folder_id' not in animation_data or animation_data['folder_id'] is None:
                # Try to resolve folder_path to folder_id
                folder_path = animation_data.get('folder_path')
                if folder_path:
                    folder = self._folders.get_by_path(folder_path)
                    if folder:
                        animation_data['folder_id'] = folder['id']
                    else:
                        animation_data['folder_id'] = self._folders.get_root_id()
                else:
                    animation_data['folder_id'] = self._folders.get_root_id()

            # Handle versioning: if this is a new version in an existing group,
            # clear is_latest on other versions in the same group
            version_group_id = animation_data.get('version_group_id')
            is_latest = animation_data.get('is_latest', 1)

            if version_group_id and version_group_id != uuid and is_latest:
                # This is a new version of an existing animation - clear is_latest on others
                self._clear_latest_in_group(version_group_id)

            result = self._animations.add(animation_data)
            if result:
                print(f"[SCAN] IMPORTED: {name} (UUID: {uuid[:8]}..., is_latest: {is_latest})")
            else:
                print(f"[SCAN] FAILED to add: {name} (UUID: {uuid[:8]}...)")
            return result is not None

        except Exception as e:
            print(f"[SCAN] ERROR importing {json_file_path}: {e}")
            return False

    def _clear_latest_in_group(self, version_group_id: str) -> bool:
        """
        Clear is_latest flag on all animations in a version group.

        Args:
            version_group_id: Version group UUID

        Returns:
            True if successful
        """
        try:
            conn = self._conn.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE animations SET is_latest = 0 WHERE version_group_id = ?',
                (version_group_id,)
            )
            conn.commit()
            return True
        except Exception:
            return False

    def scan_folder(self, library_path: Path) -> Tuple[int, int]:
        """
        Scan library folder for animations and import them.

        Scans:
        - Hot storage: library/{name}/{name}.json
        - Cold storage: _versions/{name}/{version}/{name}.json

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
            # Scan hot storage: library/
            library_dir = library_path / Config.LIBRARY_FOLDER_NAME
            if library_dir.exists():
                found, imported = self._scan_library_folder(library_dir)
                total_found += found
                newly_imported += imported

            # Scan cold storage: _versions/
            versions_dir = library_path / Config.VERSIONS_FOLDER_NAME
            if versions_dir.exists():
                found, imported = self._scan_versions_folder(versions_dir)
                total_found += found
                newly_imported += imported

            return (total_found, newly_imported)

        except Exception:
            return (total_found, newly_imported)

    def _scan_library_folder(self, library_dir: Path) -> Tuple[int, int]:
        """
        Scan library folder for animations (hot storage).

        Supports both structures:
        - New: library/actions/{name}/{name}.json and library/poses/{name}/{name}.json
        - Legacy: library/{name}/{name}.json

        Args:
            library_dir: Path to library folder

        Returns:
            Tuple of (total_found, newly_imported)
        """
        total_found = 0
        newly_imported = 0

        # Scan new structure: actions/ and poses/ subfolders
        for subfolder_name in ['actions', 'poses']:
            subfolder = library_dir / subfolder_name
            if subfolder.exists() and subfolder.is_dir():
                found, imported = self._scan_animation_folder(subfolder)
                total_found += found
                newly_imported += imported

        # Also scan direct children for backwards compatibility (legacy structure)
        found, imported = self._scan_animation_folder(library_dir, skip_subdirs=['actions', 'poses'])
        total_found += found
        newly_imported += imported

        return (total_found, newly_imported)

    def _scan_animation_folder(self, folder: Path, skip_subdirs: list = None) -> Tuple[int, int]:
        """
        Scan a folder for animation JSON files.

        Args:
            folder: Path to folder to scan
            skip_subdirs: List of subdirectory names to skip

        Returns:
            Tuple of (total_found, newly_imported)
        """
        total_found = 0
        newly_imported = 0
        skip_subdirs = skip_subdirs or []

        print(f"[SCAN] Scanning folder: {folder}")

        for item in folder.iterdir():
            if not item.is_dir():
                continue

            dirname = item.name

            # Skip specified subdirectories
            if dirname in skip_subdirs:
                continue

            total_found += 1

            # Try {folder_name}.json
            json_file = item / f"{dirname}.json"
            if json_file.exists():
                print(f"[SCAN] Found: {json_file.name} in {dirname}/")
                if self.import_from_json(json_file):
                    newly_imported += 1
                continue

            # Try any .json file in the folder
            json_files = list(item.glob("*.json"))
            if json_files:
                print(f"[SCAN] Found (fallback): {json_files[0].name} in {dirname}/")
                if self.import_from_json(json_files[0]):
                    newly_imported += 1
            else:
                print(f"[SCAN] WARNING: No JSON found in {dirname}/")

        print(f"[SCAN] Folder scan complete: found={total_found}, imported={newly_imported}")
        return (total_found, newly_imported)

    def _scan_versions_folder(self, versions_dir: Path) -> Tuple[int, int]:
        """
        Scan versions folder for archived animations (cold storage).

        Structure: _versions/{name}/{version}/{name}.json

        Args:
            versions_dir: Path to _versions folder

        Returns:
            Tuple of (total_found, newly_imported)
        """
        total_found = 0
        newly_imported = 0

        # _versions/{animation_name}/
        for animation_folder in versions_dir.iterdir():
            if not animation_folder.is_dir():
                continue

            animation_name = animation_folder.name

            # _versions/{animation_name}/{version_label}/
            for version_folder in animation_folder.iterdir():
                if not version_folder.is_dir():
                    continue

                total_found += 1

                # Try {animation_name}.json
                json_file = version_folder / f"{animation_name}.json"
                if json_file.exists():
                    if self.import_from_json(json_file):
                        newly_imported += 1
                    continue

                # Try any .json file
                json_files = list(version_folder.glob("*.json"))
                if json_files:
                    if self.import_from_json(json_files[0]):
                        newly_imported += 1

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
                       a.version, a.version_label, a.version_group_id, a.is_latest,
                       a.status, a.is_pose, a.is_partial,
                       a.naming_fields, a.naming_template,
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

                # Versioning (v5)
                if row['version'] and row['version'] != 1:
                    metadata['version'] = row['version']
                if row['version_label'] and row['version_label'] != 'v001':
                    metadata['version_label'] = row['version_label']
                if row['version_group_id']:
                    metadata['version_group_id'] = row['version_group_id']
                if row['is_latest'] == 0:
                    metadata['is_latest'] = False

                # Lifecycle status (v6)
                if row['status'] and row['status'] != 'none':
                    metadata['status'] = row['status']

                # Pose flags (v7, v8)
                if row['is_pose']:
                    metadata['is_pose'] = True
                if row['is_partial']:
                    metadata['is_partial'] = True

                # Studio naming (v9)
                if row['naming_fields']:
                    metadata['naming_fields'] = parse_json_field(row['naming_fields'], {})
                if row['naming_template']:
                    metadata['naming_template'] = row['naming_template']

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

            # Versioning (v5)
            if 'version' in metadata:
                updates.append('version = ?')
                params.append(metadata['version'])
            if 'version_label' in metadata:
                updates.append('version_label = ?')
                params.append(metadata['version_label'])
            if 'version_group_id' in metadata:
                updates.append('version_group_id = ?')
                params.append(metadata['version_group_id'])
            if 'is_latest' in metadata:
                updates.append('is_latest = ?')
                params.append(1 if metadata['is_latest'] else 0)

            # Lifecycle status (v6)
            if 'status' in metadata:
                updates.append('status = ?')
                params.append(metadata['status'])

            # Pose flags (v7, v8)
            if metadata.get('is_pose'):
                updates.append('is_pose = ?')
                params.append(1)
            if metadata.get('is_partial'):
                updates.append('is_partial = ?')
                params.append(1)

            # Studio naming (v9)
            if 'naming_fields' in metadata:
                updates.append('naming_fields = ?')
                params.append(json.dumps(metadata['naming_fields']))
            if 'naming_template' in metadata:
                updates.append('naming_template = ?')
                params.append(metadata['naming_template'])

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
