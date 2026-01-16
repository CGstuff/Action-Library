"""
File Utilities - Safe file and folder operations

Provides centralized functions for:
- Transactional folder operations
- Safe file copying/moving
- Rollback support
"""

import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)


@contextmanager
def transactional_move(src: Path, dst: Path,
                       cleanup_on_error: bool = True) -> Generator[None, None, None]:
    """
    Context manager for transactional folder move operations.

    If an exception occurs within the context, the destination folder
    is cleaned up (if it was created) to maintain consistency.

    Args:
        src: Source path
        dst: Destination path
        cleanup_on_error: If True, remove dst on error

    Yields:
        None

    Examples:
        >>> with transactional_move(src_folder, dst_folder):
        ...     # Do operations that might fail
        ...     shutil.move(src_folder, dst_folder)
        ...     update_database(dst_folder)

    Raises:
        Re-raises any exception after cleanup
    """
    dst_existed_before = dst.exists()

    try:
        yield
    except Exception:
        if cleanup_on_error and dst.exists() and not dst_existed_before:
            try:
                shutil.rmtree(dst)
                logger.debug(f"Cleaned up {dst} after error")
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up {dst}: {cleanup_error}")
        raise


@contextmanager
def atomic_write(path: Path) -> Generator[Path, None, None]:
    """
    Context manager for atomic file writes.

    Writes to a temporary file first, then renames to target.
    If an error occurs, the temporary file is cleaned up.

    Args:
        path: Target file path

    Yields:
        Path to temporary file to write to

    Examples:
        >>> with atomic_write(config_path) as tmp_path:
        ...     with open(tmp_path, 'w') as f:
        ...         json.dump(data, f)
    """
    tmp_path = path.with_suffix(path.suffix + '.tmp')

    try:
        yield tmp_path

        # Rename temp to target (atomic on most filesystems)
        if tmp_path.exists():
            tmp_path.replace(path)

    except Exception:
        # Clean up temp file on error
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise


def safe_remove_tree(path: Path, ignore_errors: bool = True) -> bool:
    """
    Safely remove a directory tree.

    Args:
        path: Path to directory to remove
        ignore_errors: If True, log errors but don't raise

    Returns:
        True if removal succeeded or path didn't exist
    """
    if not path.exists():
        return True

    try:
        shutil.rmtree(path)
        return True
    except PermissionError as e:
        if ignore_errors:
            logger.warning(f"Permission denied removing {path}: {e}")
            return False
        raise
    except OSError as e:
        if ignore_errors:
            logger.warning(f"Could not remove {path}: {e}")
            return False
        raise


def ensure_parent_exists(path: Path) -> bool:
    """
    Ensure the parent directory of a path exists.

    Args:
        path: File or directory path

    Returns:
        True if parent exists or was created
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Could not create parent directory for {path}: {e}")
        return False


def get_unique_path(path: Path) -> Path:
    """
    Get a unique path by appending a number if path exists.

    Args:
        path: Desired path

    Returns:
        Unique path (original if doesn't exist, or with _2, _3, etc.)

    Examples:
        >>> get_unique_path(Path("folder"))
        Path('folder')  # if doesn't exist
        >>> get_unique_path(Path("folder"))
        Path('folder_2')  # if folder exists
    """
    if not path.exists():
        return path

    counter = 2
    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1

        # Safety limit
        if counter > 1000:
            raise ValueError(f"Could not find unique path for {path}")


__all__ = [
    'transactional_move',
    'atomic_write',
    'safe_remove_tree',
    'ensure_parent_exists',
    'get_unique_path',
]
