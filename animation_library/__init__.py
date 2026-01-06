"""
Animation Library v2

A high-performance animation library for Blender with modern Qt6 architecture.
"""

__version__ = "2.0.0"
__author__ = "CGstuff"

from .config import Config
from .events.event_bus import EventBus, get_event_bus
from .themes.theme_manager import ThemeManager, get_theme_manager

__all__ = [
    'Config',
    'EventBus',
    'get_event_bus',
    'ThemeManager',
    'get_theme_manager',
]
