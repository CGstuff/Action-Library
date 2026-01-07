"""
Controllers Module - Extracted controllers from MainWindow

Provides focused controllers for:
- archive_trash_controller: Archive and trash view operations
- bulk_edit_controller: Bulk edit operations on animations
- filter_controller: Filtering and sorting management
"""

from .archive_trash_controller import ArchiveTrashController
from .bulk_edit_controller import BulkEditController
from .filter_controller import FilterController

__all__ = [
    'ArchiveTrashController',
    'BulkEditController',
    'FilterController',
]
