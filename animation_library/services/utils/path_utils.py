"""
Path Utilities - Shared folder path helpers for services

Centralizes library folder path operations that were duplicated
across archive_service.py and trash_service.py.
"""

from pathlib import Path
from typing import Optional

from ...config import Config


def get_library_path() -> Optional[Path]:
    """
    Get configured library root path

    Returns:
        Path to library root or None if not configured
    """
    return Config.load_library_path()


def get_library_folder(ensure_exists: bool = False) -> Optional[Path]:
    """
    Get library/animations folder path

    Args:
        ensure_exists: If True, create folder if it doesn't exist

    Returns:
        Path to library folder or None if library not configured
    """
    library_path = get_library_path()
    if not library_path:
        return None

    folder = library_path / "library"
    if ensure_exists:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_archive_folder(ensure_exists: bool = True) -> Optional[Path]:
    """
    Get .archive folder path

    Args:
        ensure_exists: If True, create folder if it doesn't exist (default: True)

    Returns:
        Path to .archive folder or None if library not configured
    """
    library_path = get_library_path()
    if not library_path:
        return None

    archive_folder = library_path / Config.ARCHIVE_FOLDER_NAME
    if ensure_exists:
        archive_folder.mkdir(parents=True, exist_ok=True)
    return archive_folder


def get_trash_folder(ensure_exists: bool = True) -> Optional[Path]:
    """
    Get .trash folder path

    Args:
        ensure_exists: If True, create folder if it doesn't exist (default: True)

    Returns:
        Path to .trash folder or None if library not configured
    """
    library_path = get_library_path()
    if not library_path:
        return None

    trash_folder = library_path / Config.TRASH_FOLDER_NAME
    if ensure_exists:
        trash_folder.mkdir(parents=True, exist_ok=True)
    return trash_folder


def get_queue_folder(ensure_exists: bool = True) -> Optional[Path]:
    """
    Get queue folder path (for Blender communication)

    Args:
        ensure_exists: If True, create folder if it doesn't exist (default: True)

    Returns:
        Path to queue folder or None if library not configured
    """
    library_path = get_library_path()
    if not library_path:
        return None

    queue_folder = library_path / "queue"
    if ensure_exists:
        queue_folder.mkdir(parents=True, exist_ok=True)
    return queue_folder


__all__ = [
    'get_library_path',
    'get_library_folder',
    'get_archive_folder',
    'get_trash_folder',
    'get_queue_folder',
]
