"""
String Utilities - Common string manipulation functions

Provides centralized functions for:
- Filename sanitization
- Path-safe string conversion
- Version string handling
"""

import re
from typing import Optional


def sanitize_filename(name: str, default: str = 'unnamed') -> str:
    """
    Sanitize a string for use as a filename.

    Removes characters that are invalid in Windows/Mac/Linux filenames:
    < > : " / \\ | ? *

    Also strips leading/trailing spaces and dots, and collapses
    multiple underscores into single underscores.

    Args:
        name: String to sanitize
        default: Default value if result would be empty

    Returns:
        Sanitized string safe for use as filename

    Examples:
        >>> sanitize_filename("Walk Cycle")
        'Walk Cycle'
        >>> sanitize_filename("test:file<name>")
        'test_file_name_'
        >>> sanitize_filename("   ")
        'unnamed'
    """
    if not name:
        return default

    # Replace invalid characters with underscore
    safe = re.sub(r'[<>:"/\\|?*]', '_', name)

    # Strip leading/trailing spaces and dots
    safe = safe.strip(' .')

    # Return default if empty after stripping
    if not safe:
        return default

    # Collapse multiple underscores
    safe = re.sub(r'_+', '_', safe)

    return safe


def sanitize_for_path(name: str, default: str = 'unnamed') -> str:
    """
    Sanitize a string for use in a file path component.

    Same as sanitize_filename but more aggressive - also removes
    spaces and converts to lowercase for consistency.

    Args:
        name: String to sanitize
        default: Default value if result would be empty

    Returns:
        Sanitized string safe for use in paths
    """
    safe = sanitize_filename(name, default)
    # Replace spaces with underscores for paths
    safe = safe.replace(' ', '_')
    return safe


def strip_version_suffix(name: str) -> str:
    """
    Strip version suffix from animation name.

    Removes patterns like _v001, _v02, _v1234 from the end of a name.

    Args:
        name: Animation name potentially with version suffix

    Returns:
        Name with version suffix removed

    Examples:
        >>> strip_version_suffix("walk_cycle_v001")
        'walk_cycle'
        >>> strip_version_suffix("Jump")
        'Jump'
        >>> strip_version_suffix("test_v01_final")
        'test_v01_final'  # Only removes from end
    """
    return re.sub(r'_v\d{2,4}$', '', name)


def format_version_label(version: int) -> str:
    """
    Format a version number as a version label.

    Args:
        version: Version number (1, 2, 3, etc.)

    Returns:
        Formatted version label (v001, v002, etc.)

    Examples:
        >>> format_version_label(1)
        'v001'
        >>> format_version_label(42)
        'v042'
    """
    return f"v{version:03d}"


def parse_version_label(label: str) -> Optional[int]:
    """
    Parse a version label into a version number.

    Args:
        label: Version label like 'v001' or 'v42'

    Returns:
        Version number, or None if invalid format

    Examples:
        >>> parse_version_label("v001")
        1
        >>> parse_version_label("v42")
        42
        >>> parse_version_label("invalid")
        None
    """
    match = re.match(r'^v(\d+)$', label)
    if match:
        return int(match.group(1))
    return None


__all__ = [
    'sanitize_filename',
    'sanitize_for_path',
    'strip_version_suffix',
    'format_version_label',
    'parse_version_label',
]
