"""
Drawover canvas subpackage.

Provides modular components for the drawover annotation system:
- undo_commands: Undo/redo command classes
- stroke_renderer: Graphics item creation from stroke data
- stroke_serializer: UV/screen coordinate conversion and serialization
- ghost_renderer: Ghost/onion skin rendering
"""

from .undo_commands import AddStrokeCommand, RemoveStrokeCommand, ClearFrameCommand
from .stroke_renderer import (
    add_arrow_head_to_path,
    render_brush_stroke_to_group,
    create_item_from_stroke
)
from .stroke_serializer import simplify_points, scale_stroke, uv_stroke_to_screen
from .ghost_renderer import GhostRenderer

__all__ = [
    # Undo commands
    'AddStrokeCommand',
    'RemoveStrokeCommand',
    'ClearFrameCommand',
    # Stroke rendering
    'add_arrow_head_to_path',
    'render_brush_stroke_to_group',
    'create_item_from_stroke',
    # Serialization
    'simplify_points',
    'scale_stroke',
    'uv_stroke_to_screen',
    # Ghost rendering
    'GhostRenderer',
]
