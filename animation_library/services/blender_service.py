"""
BlenderService - Communication with Blender plugin via single file

Pattern: File-based communication (single file, replaced on each apply)
Inspired by: Current animation_library Blender integration
"""

import json
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class BlenderService:
    """
    Service for communicating with Blender plugin

    Communication Method:
    - Desktop app writes single "apply_animation.json" file (overwrites each time)
    - Blender plugin polls and processes the request
    - Plugin deletes file after processing

    File Format:
    {
        "status": "pending",
        "animation_id": "uuid",
        "animation_name": "Walk Cycle",
        "timestamp": "2024-01-01T12:00:00"
    }

    Usage:
        blender_service = BlenderService()
        blender_service.queue_apply_animation(animation_uuid, animation_name)
    """

    # Single file name for apply requests
    APPLY_FILE = "apply_animation.json"

    def __init__(self):
        # Queue directory in system temp
        self._queue_dir = Path(tempfile.gettempdir()) / "animation_library_queue"
        self._queue_dir.mkdir(parents=True, exist_ok=True)

        # Clean up any old queue files from previous versions
        self._cleanup_old_queue_files()

    def _cleanup_old_queue_files(self):
        """Remove old-style queue files (apply_*.json with timestamps)"""
        try:
            old_files = [f for f in self._queue_dir.glob("apply_*.json")
                        if f.name != self.APPLY_FILE]
            for file in old_files:
                file.unlink()
        except Exception:
            pass  # Silently ignore cleanup errors

    def queue_apply_animation(
        self,
        animation_id: str,
        animation_name: str,
        options: dict = None
    ) -> bool:
        """
        Set animation for application in Blender (replaces any previous)

        Args:
            animation_id: Animation UUID
            animation_name: Animation name (for display)
            options: Apply options dict with keys:
                - apply_mode: "NEW" or "INSERT"
                - mirror: bool
                - reverse: bool
                - selected_bones_only: bool
                - use_slots: bool

        Returns:
            True if set successfully
        """
        try:
            # Single file - overwrites each time
            timestamp = datetime.now().isoformat()
            apply_file = self._queue_dir / self.APPLY_FILE

            # Default options if not provided
            if options is None:
                options = {
                    "apply_mode": "NEW",
                    "mirror": False,
                    "reverse": False,
                    "selected_bones_only": False,
                    "use_slots": False
                }

            request_data = {
                "status": "pending",
                "animation_id": animation_id,
                "animation_name": animation_name,
                "timestamp": timestamp,
                "options": options
            }

            with open(apply_file, 'w') as f:
                json.dump(request_data, f, indent=2)

            return True

        except Exception:
            return False

    def get_queue_size(self) -> int:
        """
        Check if there's a pending request

        Returns:
            1 if pending request exists, 0 otherwise
        """
        try:
            apply_file = self._queue_dir / self.APPLY_FILE
            return 1 if apply_file.exists() else 0
        except Exception:
            return 0

    def clear_queue(self):
        """Clear pending request"""
        try:
            apply_file = self._queue_dir / self.APPLY_FILE
            if apply_file.exists():
                apply_file.unlink()
        except Exception:
            pass  # Silently ignore clear errors

    def get_queue_directory(self) -> Path:
        """
        Get queue directory path

        Returns:
            Path to queue directory
        """
        return self._queue_dir

# Singleton instance
_blender_service_instance: Optional[BlenderService] = None


def get_blender_service() -> BlenderService:
    """
    Get global BlenderService singleton

    Returns:
        Global BlenderService instance
    """
    global _blender_service_instance
    if _blender_service_instance is None:
        _blender_service_instance = BlenderService()
    return _blender_service_instance


__all__ = ['BlenderService', 'get_blender_service']
