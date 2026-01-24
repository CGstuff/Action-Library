"""
Undo commands for drawover canvas operations.

Provides QUndoCommand subclasses for stroke add/remove/clear operations.
"""

from typing import TYPE_CHECKING, List, Dict, Tuple

from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from ..drawover_canvas import DrawoverCanvas


class AddStrokeCommand(QUndoCommand):
    """Undo command for adding a stroke."""

    def __init__(self, canvas: 'DrawoverCanvas', item: QGraphicsItem, stroke_data: Dict):
        super().__init__("Add Stroke")
        self._canvas = canvas
        self._item = item
        self._stroke_data = stroke_data

    def redo(self):
        if self._item.scene() is None:
            self._canvas._scene.addItem(self._item)

    def undo(self):
        if self._item.scene() is not None:
            self._canvas._scene.removeItem(self._item)


class RemoveStrokeCommand(QUndoCommand):
    """Undo command for removing a stroke."""

    def __init__(self, canvas: 'DrawoverCanvas', item: QGraphicsItem, stroke_data: Dict):
        super().__init__("Remove Stroke")
        self._canvas = canvas
        self._item = item
        self._stroke_data = stroke_data

    def redo(self):
        if self._item.scene() is not None:
            self._canvas._scene.removeItem(self._item)

    def undo(self):
        if self._item.scene() is None:
            self._canvas._scene.addItem(self._item)


class ClearFrameCommand(QUndoCommand):
    """Undo command for clearing all strokes."""

    def __init__(self, canvas: 'DrawoverCanvas', items: List[Tuple[QGraphicsItem, Dict]]):
        super().__init__("Clear Frame")
        self._canvas = canvas
        self._items = items  # List of (item, stroke_data) tuples

    def redo(self):
        for item, _ in self._items:
            if item.scene() is not None:
                self._canvas._scene.removeItem(item)

    def undo(self):
        for item, _ in self._items:
            if item.scene() is None:
                self._canvas._scene.addItem(item)


__all__ = ['AddStrokeCommand', 'RemoveStrokeCommand', 'ClearFrameCommand']
