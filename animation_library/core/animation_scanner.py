"""
AnimationScanner - Scan directories for Blender animation files

Pattern: Directory traversal and file discovery
Inspired by: Current animation_library scanning logic
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import json

from ..config import Config
from .metadata_extractor import MetadataExtractor
from .thumbnail_generator import ThumbnailGenerator


class AnimationScanner:
    """
    Scan directories for Blender animation files and metadata

    Features:
    - Recursive directory scanning
    - Blender file discovery (.blend)
    - JSON metadata parsing
    - Thumbnail discovery
    - Folder structure analysis

    Usage:
        scanner = AnimationScanner()
        animations = scanner.scan_directory(base_path)
        for anim in animations:
            db.add_animation(anim)
    """

    def __init__(self):
        self.metadata_extractor = MetadataExtractor()
        self.thumbnail_generator = ThumbnailGenerator()

    def scan_directory(
        self,
        base_path: Path,
        folder_id: int = 1,
        recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Scan directory for animation files

        Args:
            base_path: Base directory to scan
            folder_id: Database folder ID for animations
            recursive: Whether to scan subdirectories

        Returns:
            List of animation metadata dicts
        """
        animations = []

        if not base_path.exists() or not base_path.is_dir():
            print(f"Invalid directory: {base_path}")
            return animations

        print(f"[AnimationScanner] Scanning {base_path}...")

        # Find all .blend files
        if recursive:
            blend_files = list(base_path.rglob("*.blend"))
        else:
            blend_files = list(base_path.glob("*.blend"))

        print(f"[AnimationScanner] Found {len(blend_files)} .blend files")

        for blend_file in blend_files:
            animation_data = self._process_blend_file(blend_file, folder_id)
            if animation_data:
                animations.append(animation_data)

        return animations

    def _process_blend_file(
        self,
        blend_path: Path,
        folder_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Process single Blender file

        Args:
            blend_path: Path to .blend file
            folder_id: Database folder ID

        Returns:
            Animation metadata dict or None
        """
        # Look for accompanying JSON metadata
        json_path = blend_path.with_suffix('.json')

        if json_path.exists():
            # Load from JSON
            metadata = self.metadata_extractor.extract_from_json(json_path)
            if metadata:
                # Update paths
                metadata['blend_file_path'] = str(blend_path)
                metadata['json_file_path'] = str(json_path)
                metadata['folder_id'] = folder_id

                # Look for thumbnail
                thumbnail_path = blend_path.with_suffix('.png')
                if thumbnail_path.exists():
                    metadata['thumbnail_path'] = str(thumbnail_path)

                # Look for preview video
                preview_path = blend_path.with_suffix('.mp4')
                if preview_path.exists():
                    metadata['preview_path'] = str(preview_path)

                return metadata
        else:
            # No JSON - create basic metadata from filename
            print(f"[AnimationScanner] No JSON for {blend_path.name}, creating basic metadata")

            name = blend_path.stem
            metadata = self.metadata_extractor.create_metadata(
                name=name,
                rig_type="Unknown",
                folder_id=folder_id,
                blend_file_path=str(blend_path)
            )

            # Look for thumbnail
            thumbnail_path = blend_path.with_suffix('.png')
            if thumbnail_path.exists():
                metadata['thumbnail_path'] = str(thumbnail_path)

            return metadata

        return None

    def scan_for_thumbnails(
        self,
        base_path: Path,
        recursive: bool = True
    ) -> Dict[str, Path]:
        """
        Scan for thumbnail images

        Args:
            base_path: Base directory
            recursive: Scan subdirectories

        Returns:
            Dict mapping animation names to thumbnail paths
        """
        thumbnails = {}

        if recursive:
            png_files = list(base_path.rglob("*.png"))
        else:
            png_files = list(base_path.glob("*.png"))

        for png_file in png_files:
            # Use stem as animation name
            name = png_file.stem
            thumbnails[name] = png_file

        return thumbnails

    def discover_folder_structure(
        self,
        base_path: Path
    ) -> List[Dict[str, Any]]:
        """
        Discover folder structure for organization

        Args:
            base_path: Base animations directory

        Returns:
            List of folder dicts with structure information
        """
        folders = []

        if not base_path.exists():
            return folders

        # Walk directory tree
        for item in base_path.rglob("*"):
            if item.is_dir():
                relative_path = item.relative_to(base_path)

                # Count animations in folder
                blend_count = len(list(item.glob("*.blend")))

                folder_data = {
                    'name': item.name,
                    'path': str(relative_path),
                    'full_path': str(item),
                    'animation_count': blend_count,
                }

                folders.append(folder_data)

        return folders

    def validate_animation_files(
        self,
        base_path: Path
    ) -> Dict[str, List[str]]:
        """
        Validate animation file structure

        Args:
            base_path: Base directory

        Returns:
            Dict with 'valid', 'missing_json', 'missing_thumbnail' lists
        """
        result = {
            'valid': [],
            'missing_json': [],
            'missing_thumbnail': [],
        }

        blend_files = list(base_path.rglob("*.blend"))

        for blend_file in blend_files:
            name = blend_file.stem

            json_path = blend_file.with_suffix('.json')
            thumbnail_path = blend_file.with_suffix('.png')

            has_json = json_path.exists()
            has_thumbnail = thumbnail_path.exists()

            if has_json and has_thumbnail:
                result['valid'].append(name)
            else:
                if not has_json:
                    result['missing_json'].append(name)
                if not has_thumbnail:
                    result['missing_thumbnail'].append(name)

        return result


__all__ = ['AnimationScanner']
