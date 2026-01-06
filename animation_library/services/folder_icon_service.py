"""
FolderIconService - Manage folder icon preset assignments

Pattern: Service layer for folder icon persistence
Uses folder paths (not database IDs) for portability across imports/exports.
"""

import json
from pathlib import Path
from typing import Optional, Dict, List
from ..config import Config


class FolderIconService:
    """Manage folder icon preset assignments using folder paths"""

    # Built-in icon presets
    DEFAULT_PRESETS = [
        {'id': 'default', 'name': 'Default Folder', 'icon_key': 'folder_default'},
        {'id': 'body', 'name': 'Body Motion', 'icon_key': 'folder_body'},
        {'id': 'face', 'name': 'Face Animation', 'icon_key': 'folder_face'},
        {'id': 'hand', 'name': 'Hand Animation', 'icon_key': 'folder_hand'},
        {'id': 'locomotion', 'name': 'Locomotion', 'icon_key': 'folder_locomotion'},
        {'id': 'combat', 'name': 'Combat/Action', 'icon_key': 'folder_combat'},
        {'id': 'idle', 'name': 'Idle/Poses', 'icon_key': 'folder_idle'},
    ]

    def __init__(self, library_path: Path, db_service=None):
        self.library_path = Path(library_path)
        self.icons_file = self.library_path / "folder_icons.json"
        self._db_service = db_service
        self.icon_assignments = self._load_icons()

    def _load_icons(self) -> Dict[str, str]:
        """Load icon assignments from JSON, migrating from ID-based if needed"""
        if self.icons_file.exists():
            try:
                with open(self.icons_file, 'r') as f:
                    data = json.load(f)
                    icons = data.get('folder_icons', {})

                    # Check if migration needed (keys are numeric IDs)
                    if icons and self._needs_migration(icons):
                        icons = self._migrate_to_paths(icons)
                        # Save migrated data
                        self.icon_assignments = icons
                        self._save_icons()

                    return icons
            except Exception:
                pass
        return {}

    def _needs_migration(self, icons: Dict[str, str]) -> bool:
        """Check if icon assignments use old ID-based format"""
        if not icons:
            return False
        # If all keys are numeric strings, it's the old format
        return all(key.isdigit() for key in icons.keys())

    def _migrate_to_paths(self, old_icons: Dict[str, str]) -> Dict[str, str]:
        """Migrate ID-based icon assignments to path-based"""
        if not self._db_service:
            return {}

        new_icons = {}
        for folder_id_str, icon_id in old_icons.items():
            try:
                folder_id = int(folder_id_str)
                folder = self._db_service.get_folder_by_id(folder_id)
                if folder and folder.get('path'):
                    new_icons[folder['path']] = icon_id
            except (ValueError, TypeError):
                pass
        return new_icons

    def _save_icons(self):
        """Save icon assignments to JSON"""
        try:
            data = {'folder_icons': self.icon_assignments}
            with open(self.icons_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def set_folder_icon(self, folder_path: str, icon_id: str):
        """Assign icon to folder by path"""
        if folder_path:
            self.icon_assignments[folder_path] = icon_id
            self._save_icons()

    def get_folder_icon(self, folder_path: str) -> Optional[str]:
        """Get assigned icon for folder by path"""
        if not folder_path:
            return None
        return self.icon_assignments.get(folder_path)

    def clear_folder_icon(self, folder_path: str):
        """Remove icon assignment"""
        if folder_path and folder_path in self.icon_assignments:
            del self.icon_assignments[folder_path]
            self._save_icons()

    def get_all_presets(self) -> List[Dict]:
        """Get all available icon presets"""
        return self.DEFAULT_PRESETS.copy()

    def get_all_assignments(self) -> Dict[str, str]:
        """Get all icon assignments (path -> icon_id)"""
        return self.icon_assignments.copy()


# Singleton instance
_folder_icon_service: Optional[FolderIconService] = None


def get_folder_icon_service(db_service=None) -> FolderIconService:
    """Get folder icon service singleton"""
    global _folder_icon_service
    if _folder_icon_service is None:
        library_path = Config.load_library_path()
        if library_path:
            _folder_icon_service = FolderIconService(library_path, db_service)
        else:
            # Fallback to user data dir if no library path configured
            _folder_icon_service = FolderIconService(Config.get_user_data_dir(), db_service)
    return _folder_icon_service


def reset_folder_icon_service():
    """Reset singleton (for testing or reinitialization)"""
    global _folder_icon_service
    _folder_icon_service = None


__all__ = ['FolderIconService', 'get_folder_icon_service', 'reset_folder_icon_service']
