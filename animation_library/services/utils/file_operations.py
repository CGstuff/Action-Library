"""
File Operations - Safe file copy/delete utilities with retry logic

Centralizes file operations that were duplicated in archive_service.py.
Uses retry logic and gc.collect() to handle locked files on Windows.
"""

import gc
import shutil
import time
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


def safe_copy_file(
    source: Path,
    dest: Path,
    max_retries: int = 3,
    retry_delay: float = 0.3
) -> Tuple[bool, str]:
    """
    Copy a single file with retry logic for locked files

    Args:
        source: Source file path
        dest: Destination file path
        max_retries: Number of retry attempts (default: 3)
        retry_delay: Delay between retries in seconds (default: 0.3)

    Returns:
        Tuple of (success, error_message or empty string)
    """
    for attempt in range(max_retries):
        try:
            gc.collect()  # Release Python file handles
            shutil.copy2(str(source), str(dest))
            return True, ""
        except PermissionError as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return False, f"Permission denied: {e}"
        except Exception as e:
            return False, str(e)

    return False, "Max retries exceeded"


def safe_copy_folder_contents(
    source_folder: Path,
    dest_folder: Path,
    skip_files: Optional[List[str]] = None,
    max_retries: int = 3,
    retry_delay: float = 0.3
) -> Tuple[bool, List[str]]:
    """
    Copy folder contents file by file, handling locked files gracefully

    Args:
        source_folder: Source folder path
        dest_folder: Destination folder path
        skip_files: List of filenames to skip
        max_retries: Number of retry attempts per file (default: 3)
        retry_delay: Delay between retries in seconds (default: 0.3)

    Returns:
        Tuple of (all_success, list of failed filenames)
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    skip_files = skip_files or []
    failed_files = []

    for file_path in source_folder.iterdir():
        if file_path.name in skip_files:
            continue

        dest_path = dest_folder / file_path.name
        try:
            if file_path.is_file():
                success, error = safe_copy_file(
                    file_path, dest_path,
                    max_retries=max_retries,
                    retry_delay=retry_delay
                )
                if not success:
                    logger.warning(f"Failed to copy {file_path.name}: {error}")
                    failed_files.append(file_path.name)
            elif file_path.is_dir():
                # Recursively copy subdirectories
                shutil.copytree(str(file_path), str(dest_path), dirs_exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to copy {file_path.name}: {e}")
            failed_files.append(file_path.name)

    return len(failed_files) == 0, failed_files


def safe_delete_file(
    file_path: Path,
    max_retries: int = 3,
    retry_delay: float = 0.3
) -> Tuple[bool, str]:
    """
    Delete a single file with retry logic for locked files

    Args:
        file_path: Path to file to delete
        max_retries: Number of retry attempts (default: 3)
        retry_delay: Delay between retries in seconds (default: 0.3)

    Returns:
        Tuple of (success, error_message or empty string)
    """
    for attempt in range(max_retries):
        try:
            gc.collect()  # Release Python file handles
            file_path.unlink()
            return True, ""
        except PermissionError as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return False, f"Permission denied: {e}"
        except FileNotFoundError:
            return True, ""  # Already deleted
        except Exception as e:
            return False, str(e)

    return False, "Max retries exceeded"


def safe_delete_folder_contents(
    folder: Path,
    skip_files: Optional[List[str]] = None,
    remove_folder_if_empty: bool = True
) -> List[str]:
    """
    Delete folder contents, skipping specified files

    Args:
        folder: Folder to clean
        skip_files: List of filenames to skip (still locked)
        remove_folder_if_empty: If True, remove folder if empty after cleanup

    Returns:
        List of filenames that couldn't be deleted
    """
    skip_files = skip_files or []
    still_locked = []

    for file_path in folder.iterdir():
        if file_path.name in skip_files:
            still_locked.append(file_path.name)
            continue

        try:
            gc.collect()
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
        except PermissionError:
            still_locked.append(file_path.name)
        except Exception as e:
            logger.warning(f"Failed to delete {file_path.name}: {e}")
            still_locked.append(file_path.name)

    # Try to remove folder if empty
    if remove_folder_if_empty and not still_locked:
        try:
            folder.rmdir()
        except OSError:
            pass  # Not empty or locked

    return still_locked


def safe_delete_folder(folder: Path, max_retries: int = 3) -> Tuple[bool, str]:
    """
    Safely delete an entire folder with retry logic

    Args:
        folder: Folder to delete
        max_retries: Number of retry attempts (default: 3)

    Returns:
        Tuple of (success, error_message or empty string)
    """
    for attempt in range(max_retries):
        try:
            gc.collect()
            if folder.exists():
                shutil.rmtree(folder)
            return True, ""
        except PermissionError as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
            else:
                return False, f"Permission denied: {e}"
        except Exception as e:
            return False, str(e)

    return False, "Max retries exceeded"


__all__ = [
    'safe_copy_file',
    'safe_copy_folder_contents',
    'safe_delete_file',
    'safe_delete_folder_contents',
    'safe_delete_folder',
]
