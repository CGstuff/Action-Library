"""
Color Presets - Built-in gradient presets for animation thumbnails

Provides predefined gradient color combinations for quick thumbnail styling.
"""

from typing import List, Dict, Tuple, Optional


# Gradient preset type definition
GradientPreset = Dict[str, any]


# Built-in gradient presets
# Each preset has: name, top color (RGB 0-1), bottom color (RGB 0-1), icon color (hex)
GRADIENT_PRESETS: List[GradientPreset] = [
    {
        "name": "Idle",
        "top": (0.25, 0.35, 0.55),
        "bottom": (0.5, 0.5, 0.5),
        "icon": "#3D5A8C",
    },
    {
        "name": "Walk",
        "top": (0.2, 0.5, 0.3),
        "bottom": (0.4, 0.4, 0.35),
        "icon": "#4D8050",
    },
    {
        "name": "Attack",
        "top": (0.7, 0.2, 0.2),
        "bottom": (0.4, 0.3, 0.3),
        "icon": "#B33333",
    },
    {
        "name": "Jump",
        "top": (0.45, 0.3, 0.6),
        "bottom": (0.55, 0.45, 0.65),
        "icon": "#734D99",
    },
    {
        "name": "Death",
        "top": (0.3, 0.3, 0.3),
        "bottom": (0.15, 0.15, 0.15),
        "icon": "#4D4D4D",
    },
    {
        "name": "Dance",
        "top": (0.7, 0.3, 0.6),
        "bottom": (0.5, 0.4, 0.55),
        "icon": "#B34D99",
    },
    {
        "name": "Crouch",
        "top": (0.2, 0.25, 0.4),
        "bottom": (0.25, 0.25, 0.3),
        "icon": "#334066",
    },
    {
        "name": "Cast",
        "top": (0.2, 0.5, 0.6),
        "bottom": (0.35, 0.45, 0.5),
        "icon": "#338099",
    },
]


def get_preset_by_name(name: str) -> Optional[GradientPreset]:
    """
    Get a gradient preset by name.

    Args:
        name: Preset name (case-insensitive)

    Returns:
        Preset dict or None if not found
    """
    name_lower = name.lower()
    for preset in GRADIENT_PRESETS:
        if preset["name"].lower() == name_lower:
            return preset
    return None


def get_preset_gradient(name: str) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    """
    Get gradient colors for a preset by name.

    Args:
        name: Preset name

    Returns:
        Tuple of (top_color, bottom_color) or None if not found
    """
    preset = get_preset_by_name(name)
    if preset:
        return (preset["top"], preset["bottom"])
    return None


__all__ = [
    'GRADIENT_PRESETS',
    'GradientPreset',
    'get_preset_by_name',
    'get_preset_gradient',
]
