"""
Services Utilities Package

Shared utilities for services layer.
"""

from .path_utils import (
    get_library_path,
    get_library_folder,
    get_archive_folder,
    get_trash_folder,
    get_queue_folder,
)
from .file_operations import (
    safe_copy_file,
    safe_copy_folder_contents,
    safe_delete_file,
    safe_delete_folder_contents,
)

__all__ = [
    # Path utilities
    'get_library_path',
    'get_library_folder',
    'get_archive_folder',
    'get_trash_folder',
    'get_queue_folder',
    # File operations
    'safe_copy_file',
    'safe_copy_folder_contents',
    'safe_delete_file',
    'safe_delete_folder_contents',
]
