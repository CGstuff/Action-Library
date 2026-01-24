"""
Version history dialog subpackage.

Provides modular components for the version history dialog:
- export_manager: Video export with annotations
- compare_manager: Side-by-side version comparison
- review_notes_manager: Notes CRUD operations
- canvas_manager: Annotation canvas management
"""

from .export_manager import AnnotatedExportWorker, AnnotatedExportManager
from .compare_manager import CompareManager
from .review_notes_manager import ReviewNotesManager
from .canvas_manager import AnnotationCanvasManager

__all__ = [
    'AnnotatedExportWorker',
    'AnnotatedExportManager',
    'CompareManager',
    'ReviewNotesManager',
    'AnnotationCanvasManager',
]
