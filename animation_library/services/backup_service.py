"""
BackupService - Export and Import .animlib archives

Handles:
- Exporting entire library to compressed .animlib archive
- Importing archives with conflict resolution
- Archive validation and manifest reading
- Portable metadata export/import (tags, favorites, folders)
"""

import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

from ..config import Config

# Metadata file name for portable library export
METADATA_FILENAME = "library_metadata.json"
METADATA_VERSION = "1.0"


class BackupService:
    """Service for backing up and restoring animation libraries"""

    # Archive format version for future compatibility
    ARCHIVE_VERSION = "1.1"  # Bumped for metadata support

    @classmethod
    def export_library(
        cls,
        library_path: Path,
        output_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """
        Export entire library to .animlib archive

        Args:
            library_path: Path to the animation library
            output_path: Path where .animlib file should be saved
            progress_callback: Optional callback(current, total, message)

        Returns:
            True if export succeeded
        """
        try:
            # Ensure output has .animlib extension
            if not str(output_path).endswith('.animlib'):
                output_path = Path(str(output_path) + '.animlib')

            # Collect files to archive
            files_to_archive = cls._collect_files(library_path)
            total_files = len(files_to_archive)

            if total_files == 0:
                if progress_callback:
                    progress_callback(0, 0, "No files to export")
                return False

            # Create manifest
            manifest = cls._create_manifest(library_path, files_to_archive)

            # Create ZIP archive
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Write manifest
                manifest_json = json.dumps(manifest, indent=2)
                zipf.writestr('manifest.json', manifest_json)

                # Export library metadata (tags, favorites, folders)
                if progress_callback:
                    progress_callback(0, total_files, "Exporting metadata...")
                metadata = cls._export_metadata()
                if metadata:
                    metadata_json = json.dumps(metadata, indent=2)
                    zipf.writestr(METADATA_FILENAME, metadata_json)

                if progress_callback:
                    progress_callback(0, total_files, "Starting export...")

                # Add all files
                for idx, (file_path, archive_name) in enumerate(files_to_archive):
                    if progress_callback:
                        progress_callback(
                            idx + 1,
                            total_files,
                            f"Exporting: {Path(archive_name).name}"
                        )

                    zipf.write(file_path, archive_name)

            if progress_callback:
                progress_callback(total_files, total_files, "Export complete!")

            return True

        except Exception as e:
            if progress_callback:
                progress_callback(0, 0, f"Error: {str(e)}")
            raise

    @classmethod
    def import_library(
        cls,
        archive_path: Path,
        library_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Import library from .animlib archive

        Args:
            archive_path: Path to .animlib file
            library_path: Path to the animation library
            progress_callback: Optional callback(current, total, message)

        Returns:
            Dictionary with import statistics
        """
        stats = {
            'imported': 0,
            'metadata_imported': 0,
            'errors': []
        }

        metadata = None

        try:
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                # Read and validate manifest
                manifest_data = zipf.read('manifest.json')
                manifest = json.loads(manifest_data)

                # Check version compatibility
                if not cls._is_compatible_version(manifest.get('version', '1.0')):
                    raise ValueError(f"Incompatible archive version: {manifest.get('version')}")

                # Check for metadata file
                if METADATA_FILENAME in zipf.namelist():
                    try:
                        metadata_data = zipf.read(METADATA_FILENAME)
                        metadata = json.loads(metadata_data)
                    except Exception:
                        pass  # Metadata is optional

                # Get list of files to extract (skip special files and database folder)
                skip_files = {'manifest.json', METADATA_FILENAME}
                file_list = [
                    name for name in zipf.namelist()
                    if name not in skip_files and not name.startswith(Config.DB_FOLDER_NAME)
                ]
                total_files = len(file_list)

                if progress_callback:
                    progress_callback(0, total_files, "Starting import...")

                # Extract files
                for idx, file_name in enumerate(file_list):
                    if progress_callback:
                        progress_callback(
                            idx + 1,
                            total_files,
                            f"Importing: {Path(file_name).name}"
                        )

                    try:
                        target_path = library_path / file_name

                        # Ensure parent directory exists
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        # Extract file (overwrites existing - same UUID = same animation)
                        with zipf.open(file_name) as source:
                            with open(target_path, 'wb') as target:
                                shutil.copyfileobj(source, target)

                        stats['imported'] += 1

                    except Exception as e:
                        stats['errors'].append(f"{file_name}: {str(e)}")

            # Import metadata after files are extracted (saves to pending file)
            if metadata:
                if progress_callback:
                    progress_callback(total_files, total_files, "Saving metadata...")
                metadata_stats = cls._import_metadata(metadata)
                stats['metadata_imported'] = metadata_stats.get('pending', 0)

            if progress_callback:
                progress_callback(total_files, total_files, "Import complete!")

        except Exception as e:
            stats['errors'].append(f"Archive error: {str(e)}")
            if progress_callback:
                progress_callback(0, 0, f"Error: {str(e)}")

        return stats

    @classmethod
    def _collect_files(cls, library_path: Path) -> List[tuple]:
        """
        Collect all files to be archived

        Args:
            library_path: Path to library

        Returns:
            List of (file_path, archive_name) tuples
        """
        files = []

        # NOTE: Database is NOT included in exports - it can be rebuilt by scanning
        # Only animation files and metadata are exported

        # Include folder_icons.json if it exists
        icons_path = library_path / 'folder_icons.json'
        if icons_path.exists():
            files.append((icons_path, 'folder_icons.json'))

        # Collect animation files from library/ folder
        library_folder = library_path / 'library'
        if library_folder.exists():
            for root, dirs, filenames in os.walk(library_folder):
                root_path = Path(root)

                for filename in filenames:
                    file_path = root_path / filename

                    # Skip hidden files and system files
                    if filename.startswith('.') or filename == 'desktop.ini':
                        continue

                    # Include animation files
                    if filename.endswith(('.blend', '.json', '.webm', '.mp4', '.png')):
                        rel_path = file_path.relative_to(library_path)
                        files.append((file_path, str(rel_path).replace('\\', '/')))

        return files

    @classmethod
    def _create_manifest(cls, library_path: Path, files: List[tuple]) -> Dict:
        """Create manifest with archive metadata"""
        # Calculate total size
        total_size = sum(f[0].stat().st_size for f in files if f[0].exists())
        total_size_mb = total_size / (1024 * 1024)

        # Count animations (unique UUIDs from .json files)
        animation_count = sum(1 for f in files if str(f[1]).endswith('.json')
                             and not str(f[1]).endswith('folder_icons.json'))

        return {
            'version': cls.ARCHIVE_VERSION,
            'created': datetime.now().isoformat(),
            'app_version': Config.APP_VERSION,
            'animation_count': animation_count,
            'total_size_mb': round(total_size_mb, 2),
            'file_count': len(files)
        }

    @classmethod
    def _is_compatible_version(cls, version: str) -> bool:
        """Check if archive version is compatible"""
        # Support version 1.0 and any 1.x versions
        try:
            major = int(version.split('.')[0])
            return major == 1
        except (ValueError, IndexError):
            return False

    @classmethod
    def get_archive_info(cls, archive_path: Path) -> Optional[Dict]:
        """
        Get information about an archive without extracting it

        Args:
            archive_path: Path to .animlib file

        Returns:
            Manifest dictionary with added info, or None if invalid
        """
        try:
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                manifest_data = zipf.read('manifest.json')
                manifest = json.loads(manifest_data)

                # Add computed info if not in manifest
                if 'file_count' not in manifest:
                    manifest['file_count'] = len(zipf.namelist()) - 1  # Exclude manifest

                if 'total_size_mb' not in manifest:
                    total_size = sum(info.file_size for info in zipf.infolist())
                    manifest['total_size_mb'] = round(total_size / (1024 * 1024), 2)

                return manifest
        except Exception:
            return None

    @classmethod
    def validate_archive(cls, archive_path: Path) -> tuple[bool, str]:
        """
        Validate an archive file

        Args:
            archive_path: Path to .animlib file

        Returns:
            (is_valid, message) tuple
        """
        if not archive_path.exists():
            return False, "File does not exist"

        if not str(archive_path).endswith('.animlib'):
            return False, "File is not a .animlib archive"

        try:
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                # Check for manifest
                if 'manifest.json' not in zipf.namelist():
                    return False, "Archive is missing manifest.json"

                # Read and validate manifest
                manifest_data = zipf.read('manifest.json')
                manifest = json.loads(manifest_data)

                # Check version
                version = manifest.get('version', '0.0')
                if not cls._is_compatible_version(version):
                    return False, f"Incompatible archive version: {version}"

                # Check integrity
                bad_file = zipf.testzip()
                if bad_file:
                    return False, f"Corrupted file in archive: {bad_file}"

                return True, "Archive is valid"

        except zipfile.BadZipFile:
            return False, "File is not a valid ZIP archive"
        except json.JSONDecodeError:
            return False, "Manifest is not valid JSON"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    @classmethod
    def _export_metadata(cls) -> Optional[Dict]:
        """
        Export library metadata (tags, favorites, folders) to portable format.

        Returns:
            Metadata dict for JSON serialization, or None on error
        """
        try:
            from .database_service import get_database_service
            from .folder_icon_service import get_folder_icon_service

            db_service = get_database_service()
            icon_service = get_folder_icon_service(db_service)

            metadata = {
                'version': METADATA_VERSION,
                'exported': datetime.now().isoformat(),
                'folders': [],
                'animations': {}
            }

            # Export folders with icons
            folders = db_service.get_all_folders_with_paths()
            icon_assignments = icon_service.get_all_assignments()

            for folder in folders:
                folder_data = {'path': folder['path']}
                if folder.get('description'):
                    folder_data['description'] = folder['description']
                # Add icon if assigned
                if folder['path'] in icon_assignments:
                    folder_data['icon'] = icon_assignments[folder['path']]
                metadata['folders'].append(folder_data)

            # Export animation metadata
            metadata['animations'] = db_service.get_all_animation_metadata()

            return metadata

        except Exception:
            return None

    @classmethod
    def _import_metadata(cls, metadata: Dict) -> Dict[str, int]:
        """
        Save metadata to be applied after library rescan.

        Animations aren't in the database yet after file import - they need
        to be scanned first. So we save the metadata to a pending file that
        will be applied when the library is rescanned.

        Args:
            metadata: Parsed metadata dict from library_metadata.json

        Returns:
            Dict with import statistics
        """
        stats = {'folders_created': 0, 'folders_updated': 0, 'updated': 0, 'pending': 0}

        try:
            from .database_service import get_database_service
            from .folder_icon_service import get_folder_icon_service

            db_service = get_database_service()
            icon_service = get_folder_icon_service(db_service)

            # Import folders first - these CAN be created immediately
            for folder_data in metadata.get('folders', []):
                path = folder_data.get('path')
                if not path:
                    continue

                description = folder_data.get('description')
                icon = folder_data.get('icon')

                # Ensure folder exists (creates if missing)
                folder_id = db_service.ensure_folder_exists(path, description)
                if folder_id:
                    stats['folders_created'] += 1

                    # Set icon if specified
                    if icon:
                        icon_service.set_folder_icon(path, icon)

            # Save animation metadata to pending file - will be applied after rescan
            animations_metadata = metadata.get('animations', {})
            if animations_metadata:
                pending_file = cls._get_pending_metadata_path()
                pending_file.parent.mkdir(parents=True, exist_ok=True)

                with open(pending_file, 'w', encoding='utf-8') as f:
                    json.dump(animations_metadata, f, indent=2)

                stats['pending'] = len(animations_metadata)

            return stats

        except Exception:
            return stats

    @classmethod
    def _get_pending_metadata_path(cls) -> Path:
        """Get path to pending metadata file"""
        library_path = Config.load_library_path()
        if library_path:
            return library_path / Config.DB_FOLDER_NAME / "pending_metadata.json"
        return Config.get_user_data_dir() / "pending_metadata.json"

    @classmethod
    def apply_pending_metadata(cls) -> Dict[str, int]:
        """
        Apply any pending metadata from a previous import.
        Should be called after library rescan.

        Returns:
            Dict with statistics
        """
        stats = {'updated': 0, 'skipped': 0}
        pending_file = cls._get_pending_metadata_path()

        if not pending_file.exists():
            return stats

        try:
            from .database_service import get_database_service
            db_service = get_database_service()

            with open(pending_file, 'r', encoding='utf-8') as f:
                animations_metadata = json.load(f)

            for uuid, anim_metadata in animations_metadata.items():
                if db_service.update_animation_metadata_by_uuid(uuid, anim_metadata):
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1

            # Delete pending file after successful apply
            pending_file.unlink()

        except Exception:
            pass

        return stats

    @classmethod
    def has_pending_metadata(cls) -> bool:
        """Check if there's pending metadata to apply"""
        return cls._get_pending_metadata_path().exists()


__all__ = ['BackupService']
