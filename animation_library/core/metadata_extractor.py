"""
MetadataExtractor - Extract animation metadata from files

Pattern: Data extraction and parsing
Inspired by: Current animation_library
"""

import json
import uuid as uuid_lib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class MetadataExtractor:
    """
    Extract animation metadata from Blender files and JSON

    Features:
    - Parse JSON metadata files
    - Extract frame ranges and timing
    - Generate UUIDs for animations
    - Validate metadata structure

    Usage:
        extractor = MetadataExtractor()
        metadata = extractor.extract_from_json(json_path)
        metadata = extractor.create_metadata(name="Walk Cycle", rig_type="humanoid")
    """

    def __init__(self):
        pass

    def create_metadata(
        self,
        name: str,
        rig_type: str,
        folder_id: int,
        description: str = "",
        author: str = "",
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create new animation metadata dict

        Args:
            name: Animation name
            rig_type: Rig type (e.g., "humanoid", "quadruped")
            folder_id: Database folder ID
            description: Animation description
            author: Author name
            tags: List of tags
            **kwargs: Additional fields (frame_start, frame_end, etc.)

        Returns:
            Metadata dict ready for database insertion
        """
        # Generate UUID if not provided
        animation_uuid = kwargs.get('uuid') or str(uuid_lib.uuid4())

        metadata = {
            'uuid': animation_uuid,
            'name': name,
            'description': description,
            'folder_id': folder_id,
            'rig_type': rig_type,
            'author': author,
            'tags': tags or [],

            # Optional fields from kwargs
            'armature_name': kwargs.get('armature_name'),
            'bone_count': kwargs.get('bone_count'),
            'frame_start': kwargs.get('frame_start'),
            'frame_end': kwargs.get('frame_end'),
            'frame_count': kwargs.get('frame_count'),
            'duration_seconds': kwargs.get('duration_seconds'),
            'fps': kwargs.get('fps', 30),
            'blend_file_path': kwargs.get('blend_file_path'),
            'json_file_path': kwargs.get('json_file_path'),
            'preview_path': kwargs.get('preview_path'),
            'thumbnail_path': kwargs.get('thumbnail_path'),
            'file_size_mb': kwargs.get('file_size_mb'),

            # Custom gradient
            'use_custom_thumbnail_gradient': kwargs.get('use_custom_thumbnail_gradient', 0),
            'thumbnail_gradient_top': kwargs.get('thumbnail_gradient_top'),
            'thumbnail_gradient_bottom': kwargs.get('thumbnail_gradient_bottom'),

            # Timestamps
            'created_date': datetime.now(),
            'modified_date': datetime.now(),
        }

        return metadata

    def extract_from_json(self, json_path: Path) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from JSON file

        Args:
            json_path: Path to JSON metadata file

        Returns:
            Metadata dict or None on error
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate required fields
            required_fields = ['name', 'rig_type', 'folder_id']
            for field in required_fields:
                if field not in data:
                    print(f"Missing required field '{field}' in {json_path}")
                    return None

            # Ensure UUID exists
            if 'uuid' not in data:
                data['uuid'] = str(uuid_lib.uuid4())

            return data

        except FileNotFoundError:
            print(f"JSON file not found: {json_path}")
            return None
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {json_path}: {e}")
            return None
        except Exception as e:
            print(f"Error reading JSON {json_path}: {e}")
            return None

    def save_to_json(self, metadata: Dict[str, Any], json_path: Path) -> bool:
        """
        Save metadata to JSON file

        Args:
            metadata: Metadata dict
            json_path: Destination JSON path

        Returns:
            True if saved successfully
        """
        try:
            # Create parent directory if needed
            json_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert datetime objects to ISO strings
            metadata_copy = metadata.copy()
            for key, value in metadata_copy.items():
                if isinstance(value, datetime):
                    metadata_copy[key] = value.isoformat()

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(metadata_copy, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"Error saving JSON to {json_path}: {e}")
            return False

    def extract_from_blend_file(self, blend_path: Path) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from Blender file

        NOTE: This is a placeholder. Full Blender file parsing requires
        either running Blender in subprocess or using a library like blender-file-reader.

        Args:
            blend_path: Path to .blend file

        Returns:
            Partial metadata dict or None
        """
        # TODO: Implement Blender file parsing in Phase 6
        # For now, return basic file information

        if not blend_path.exists():
            return None

        file_size_mb = blend_path.stat().st_size / (1024 * 1024)

        return {
            'blend_file_path': str(blend_path),
            'file_size_mb': round(file_size_mb, 2),
        }

    def calculate_frame_info(
        self,
        frame_start: int,
        frame_end: int,
        fps: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate frame count and duration from frame range

        Args:
            frame_start: Start frame
            frame_end: End frame
            fps: Frames per second

        Returns:
            Dict with frame_count and duration_seconds
        """
        frame_count = frame_end - frame_start + 1
        duration_seconds = frame_count / fps if fps > 0 else 0.0

        return {
            'frame_start': frame_start,
            'frame_end': frame_end,
            'frame_count': frame_count,
            'duration_seconds': round(duration_seconds, 2),
            'fps': fps,
        }

    def validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Validate metadata has required fields

        Args:
            metadata: Metadata dict

        Returns:
            True if valid, False otherwise
        """
        required_fields = ['uuid', 'name', 'rig_type', 'folder_id']

        for field in required_fields:
            if field not in metadata:
                print(f"Validation failed: missing required field '{field}'")
                return False

        return True


__all__ = ['MetadataExtractor']
