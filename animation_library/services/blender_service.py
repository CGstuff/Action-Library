"""
BlenderService - Communication with Blender plugin

Communication Methods (in order of preference):
1. Socket-based: Real-time TCP socket for instant application (~10-50ms latency)
2. File-based: JSON queue files as fallback (~100-500ms latency)

The service automatically tries socket communication first and falls back
to file-based communication if the socket server is not available.

Uses the protocol package for consistent message building and validation.
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..config import Config
from ..protocol import (
    build_apply_animation,
    build_apply_pose,
    QUEUE_DIR_NAME,
    FALLBACK_QUEUE_DIR,
    APPLY_ANIMATION_FILE,
    MessageStatus,
)


logger = logging.getLogger(__name__)


class BlenderService:
    """
    Service for communicating with Blender plugin

    Communication Method:
    - Desktop app writes single "apply_animation.json" file (overwrites each time)
    - Blender plugin polls and processes the request
    - Plugin deletes file after processing

    Queue Location:
    - Uses .queue folder inside the library path (shared between Blender and desktop app)
    - Falls back to system temp if no library configured

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

    # Single file name for apply requests (from protocol)
    APPLY_FILE = APPLY_ANIMATION_FILE

    def __init__(self):
        self._queue_dir = None
        self._init_queue_dir()

        # Clean up any old queue files from previous versions
        self._cleanup_old_queue_files()

    def _init_queue_dir(self):
        """Initialize queue directory from library path"""
        library_path = Config.load_library_path()
        if library_path and library_path.exists():
            # Use .queue folder inside library (shared between Blender and desktop app)
            self._queue_dir = library_path / QUEUE_DIR_NAME
        else:
            # Fallback to system temp if no library configured
            self._queue_dir = Path(tempfile.gettempdir()) / FALLBACK_QUEUE_DIR

        self._queue_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Queue directory: {self._queue_dir}")

    def refresh_queue_dir(self):
        """Refresh queue directory (call when library path changes)"""
        self._init_queue_dir()

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
        Apply animation in Blender - tries socket first, then file-based fallback.

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
            True if command sent successfully
        """
        # Default options if not provided
        if options is None:
            options = {
                "apply_mode": "NEW",
                "mirror": False,
                "reverse": False,
                "selected_bones_only": False,
                "use_slots": False
            }

        # Try socket communication first (instant)
        try:
            from .socket_client import try_socket_apply
            response = try_socket_apply(
                animation_id=animation_id,
                animation_name=animation_name,
                options=options,
                is_pose=False
            )

            if response is not None:
                if response.get('status') == 'success':
                    logger.info(f"Socket: Applied animation '{animation_name}'")
                    return True
                else:
                    logger.warning(f"Socket: Error - {response.get('message')}")
                    # Don't fall back on actual errors (like no armature selected)
                    # Only fall back if socket communication itself failed
                    return False
        except Exception as e:
            logger.debug(f"Socket unavailable, using file fallback: {e}")

        # Fallback to file-based communication
        return self._queue_apply_animation_file(animation_id, animation_name, options)

    def _queue_apply_animation_file(
        self,
        animation_id: str,
        animation_name: str,
        options: dict
    ) -> bool:
        """File-based fallback for animation application"""
        try:
            apply_file = self._queue_dir / self.APPLY_FILE

            # Build message using protocol (adds type, timestamp automatically)
            request_data = build_apply_animation(animation_id, animation_name, options)
            request_data['status'] = MessageStatus.PENDING

            with open(apply_file, 'w') as f:
                json.dump(request_data, f, indent=2)

            logger.debug(f"Wrote queue file: {apply_file}")
            return True

        except Exception as e:
            logger.error(f"Error writing queue file: {e}")
            return False

    def queue_apply_pose(
        self,
        pose_id: str,
        pose_name: str,
        blend_file_path: str,
        mirror: bool = False
    ) -> bool:
        """
        Apply a pose in Blender - tries socket first, then file-based fallback.

        Poses are applied instantly (no keyframe insertion, just transforms).

        Args:
            pose_id: Pose UUID
            pose_name: Pose name (for display)
            blend_file_path: Path to the .blend file containing the pose action
            mirror: If True, apply pose mirrored (swap L/R bones)

        Returns:
            True if command sent successfully
        """
        # Try socket communication first (instant)
        try:
            from .socket_client import try_socket_apply
            response = try_socket_apply(
                animation_id=pose_id,
                animation_name=pose_name,
                is_pose=True,
                blend_file_path=blend_file_path,
                mirror=mirror
            )

            if response is not None:
                if response.get('status') == 'success':
                    logger.info(f"Socket: Applied pose '{pose_name}'")
                    return True
                else:
                    logger.warning(f"Socket: Error - {response.get('message')}")
                    return False
        except Exception as e:
            logger.debug(f"Socket unavailable, using file fallback: {e}")

        # Fallback to file-based communication
        return self._queue_apply_pose_file(pose_id, pose_name, blend_file_path, mirror)

    def _queue_apply_pose_file(
        self,
        pose_id: str,
        pose_name: str,
        blend_file_path: str,
        mirror: bool = False
    ) -> bool:
        """File-based fallback for pose application"""
        try:
            apply_file = self._queue_dir / self.APPLY_FILE

            # Build message using protocol (adds type, timestamp automatically)
            request_data = build_apply_pose(pose_id, pose_name, blend_file_path, mirror)
            request_data['status'] = MessageStatus.PENDING

            with open(apply_file, 'w') as f:
                json.dump(request_data, f, indent=2)

            logger.debug(f"Wrote pose queue file: {apply_file}")
            return True

        except Exception as e:
            logger.error(f"Error writing pose queue file: {e}")
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

    def is_blender_connected(self) -> bool:
        """
        Check if Blender is connected via socket.

        Returns:
            True if socket connection is available
        """
        try:
            from .socket_client import get_socket_client
            client = get_socket_client()
            return client.ping()
        except Exception:
            return False

    def get_blender_status(self) -> Optional[Dict[str, Any]]:
        """
        Get Blender status via socket.

        Returns:
            Dict with Blender info, or None if not connected
        """
        try:
            from .socket_client import get_socket_client
            client = get_socket_client()
            return client.get_status()
        except Exception:
            return None


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
