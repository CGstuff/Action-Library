"""
Database Helpers - Shared utility functions for database operations

Provides common serialization/deserialization and row processing.
"""

import json
import re
from typing import Dict, Any, List, Optional


def deserialize_animation(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deserialize an animation row from database format.

    Handles:
    - JSON-encoded tags field
    - Version field defaults
    - Any other future JSON fields

    Args:
        row_dict: Raw row data from database

    Returns:
        Processed animation dict with deserialized fields
    """
    data = dict(row_dict)

    # Deserialize tags JSON
    if data.get('tags'):
        try:
            data['tags'] = json.loads(data['tags'])
        except (json.JSONDecodeError, TypeError):
            data['tags'] = []
    else:
        data['tags'] = []

    # Ensure version fields have sensible defaults
    if data.get('version') is None:
        data['version'] = 1
    if data.get('version_label') is None:
        data['version_label'] = 'v001'
    if data.get('version_group_id') is None:
        # Use UUID as the version group ID for uninitialized animations
        data['version_group_id'] = data.get('uuid')
    if data.get('is_latest') is None:
        data['is_latest'] = 1

    return data


def serialize_tags(tags: Any) -> str:
    """
    Serialize tags to JSON string for database storage.

    Args:
        tags: Tags as list or already serialized string

    Returns:
        JSON string representation of tags
    """
    if isinstance(tags, list):
        return json.dumps(tags)
    elif isinstance(tags, str):
        # Already serialized or empty
        return tags
    else:
        return '[]'


def row_to_dict(row) -> Optional[Dict[str, Any]]:
    """
    Convert SQLite row to dictionary.

    Args:
        row: SQLite Row object or None

    Returns:
        Dictionary representation or None
    """
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> List[Dict[str, Any]]:
    """
    Convert list of SQLite rows to list of dictionaries.

    Args:
        rows: List of SQLite Row objects

    Returns:
        List of dictionaries
    """
    return [dict(row) for row in rows]


def is_valid_uuid(value: str) -> bool:
    """
    Check if a string is a valid UUID format.

    Args:
        value: String to check

    Returns:
        True if valid UUID format
    """
    uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    return bool(re.match(uuid_pattern, value.lower()))


def parse_json_field(value: str, default: Any = None) -> Any:
    """
    Safely parse a JSON field from database.

    Args:
        value: JSON string or None
        default: Default value if parsing fails

    Returns:
        Parsed value or default
    """
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


__all__ = [
    'deserialize_animation',
    'serialize_tags',
    'row_to_dict',
    'rows_to_list',
    'is_valid_uuid',
    'parse_json_field'
]
