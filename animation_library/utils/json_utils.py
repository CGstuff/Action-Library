"""
JSON Utilities - Safe JSON file operations

Provides centralized functions for:
- Safe JSON loading with fallback
- Safe JSON writing with encoding
- JSON file validation
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


def safe_json_load(path: Union[str, Path], default: Any = None) -> Any:
    """
    Safely load JSON from a file with error handling.

    Args:
        path: Path to JSON file
        default: Value to return if file doesn't exist or is invalid

    Returns:
        Parsed JSON data, or default value on error

    Examples:
        >>> data = safe_json_load("config.json", default={})
        >>> settings = safe_json_load("settings.json", default={"theme": "dark"})
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return default

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {path}: {e}")
        return default
    except IOError as e:
        logger.warning(f"Could not read {path}: {e}")
        return default
    except Exception as e:
        logger.error(f"Unexpected error loading {path}: {e}")
        return default


def safe_json_save(path: Union[str, Path], data: Any,
                   indent: int = 2, ensure_ascii: bool = False) -> bool:
    """
    Safely save data to a JSON file with error handling.

    Args:
        path: Path to JSON file
        data: Data to serialize to JSON
        indent: Indentation level for pretty printing
        ensure_ascii: If False, allow non-ASCII characters

    Returns:
        True if save succeeded, False otherwise

    Examples:
        >>> success = safe_json_save("config.json", {"key": "value"})
        >>> safe_json_save("data.json", my_data, indent=4)
    """
    try:
        file_path = Path(path)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)

        return True

    except TypeError as e:
        logger.error(f"Data not JSON serializable for {path}: {e}")
        return False
    except IOError as e:
        logger.error(f"Could not write to {path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving {path}: {e}")
        return False


def safe_json_update(path: Union[str, Path], updates: dict) -> bool:
    """
    Safely update specific keys in a JSON file.

    Loads existing data, merges updates, and saves back.
    Creates file with updates if it doesn't exist.

    Args:
        path: Path to JSON file
        updates: Dictionary of keys to update

    Returns:
        True if update succeeded, False otherwise

    Examples:
        >>> safe_json_update("config.json", {"theme": "light"})
    """
    try:
        data = safe_json_load(path, default={})

        if not isinstance(data, dict):
            logger.warning(f"Cannot update non-dict JSON in {path}")
            return False

        data.update(updates)
        return safe_json_save(path, data)

    except Exception as e:
        logger.error(f"Failed to update {path}: {e}")
        return False


def is_valid_json_file(path: Union[str, Path]) -> bool:
    """
    Check if a file contains valid JSON.

    Args:
        path: Path to file to check

    Returns:
        True if file exists and contains valid JSON
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return False

        with open(file_path, 'r', encoding='utf-8') as f:
            json.load(f)
        return True

    except (json.JSONDecodeError, IOError):
        return False


__all__ = [
    'safe_json_load',
    'safe_json_save',
    'safe_json_update',
    'is_valid_json_file',
]
