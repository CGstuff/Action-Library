"""
Theme system for Animation Library v2

Provides light and dark themes with customizable color palettes
"""

from .theme_manager import ThemeManager, Theme, ColorPalette, get_theme_manager
from .light_theme import LightTheme
from .dark_theme import DarkTheme

__all__ = [
    'ThemeManager',
    'Theme',
    'ColorPalette',
    'get_theme_manager',
    'LightTheme',
    'DarkTheme',
]
