"""
Font Configuration

Centralized font definitions for the entire application.
Edit this file to change fonts across the app.

Usage:
    from ..themes.fonts import Fonts, get_font, get_font_stylesheet
    
    # As QFont object
    label.setFont(get_font(Fonts.HEADER))
    
    # As stylesheet string
    label.setStyleSheet(get_font_stylesheet(Fonts.METADATA_VALUE))
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Union
from PyQt6.QtGui import QFont


@dataclass
class FontDef:
    """Font definition with family, size, weight, and italic."""
    family: str
    size: int
    weight: int = QFont.Weight.Normal  # QFont.Weight.Bold, etc.
    italic: bool = False
    
    def to_qfont(self) -> QFont:
        """Convert to QFont object."""
        font = QFont(self.family, self.size, self.weight)
        font.setItalic(self.italic)
        return font
    
    def to_stylesheet(self) -> str:
        """Convert to CSS stylesheet string."""
        weight_map = {
            QFont.Weight.Thin: 100,
            QFont.Weight.Light: 300,
            QFont.Weight.Normal: 400,
            QFont.Weight.Medium: 500,
            QFont.Weight.DemiBold: 600,
            QFont.Weight.Bold: 700,
            QFont.Weight.ExtraBold: 800,
            QFont.Weight.Black: 900,
        }
        css_weight = weight_map.get(self.weight, 400)
        italic_str = " font-style: italic;" if self.italic else ""
        return f"font-family: '{self.family}'; font-size: {self.size}px; font-weight: {css_weight};{italic_str}"


class Fonts:
    """
    Application font definitions.
    
    Adjust these values to change fonts throughout the app.
    After changing, restart the application to see updates.
    
    ============================================================
    HOW TO CUSTOMIZE:
    
    1. Pick your fonts (e.g., "Roboto", "Inter", "Rajdhani")
    2. Update the FontDef entries below
    3. Restart the app
    
    BUNDLED FONTS (in assets/fonts/):
        - Rajdhani (Light, Regular, Medium, SemiBold, Bold)
        - Saira (Variable — all weights)
        - Electrolize (Regular)
    
    FONT ROLES:
        - Rajdhani   → Cards (names, metadata on cards)
        - Saira      → General UI (headers, metadata panel, settings,
                        folder tree, captions, tooltips)
        - Electrolize → Badges, tags, buttons
    
    SYSTEM FONTS (always available):
        - Segoe UI (Windows)
        - Consolas (monospace)
    ============================================================
    """
    
    # ===== DEFAULT FONT =====
    # Used as fallback for anything not explicitly defined
    DEFAULT = FontDef("Saira", 11)
    
    # ===== HEADERS =====
    HEADER_LARGE = FontDef("Saira", 18, QFont.Weight.Bold)
    HEADER = FontDef("Saira", 15, QFont.Weight.Bold)
    HEADER_SMALL = FontDef("Saira", 13, QFont.Weight.Bold)
    
    # ===== TREE VIEWS =====
    FOLDER_TREE = FontDef("Saira", 12)
    FOLDER_TREE_SELECTED = FontDef("Saira", 12, QFont.Weight.Bold)
    
    # ===== SHOT CARDS (main grid view) =====
    SHOT_CARD_NAME = FontDef("Rajdhani", 12)
    SHOT_CARD_DURATION = FontDef("Rajdhani", 10)
    SHOT_CARD_BADGE = FontDef("Electrolize", 9)
    
    # ===== SEQUENCE REVIEW - SHOT LIST =====
    SHOT_LIST_NAME = FontDef("Rajdhani", 14)
    SHOT_LIST_DURATION = FontDef("Rajdhani", 12)
    SHOT_LIST_HEADER = FontDef("Saira", 11, QFont.Weight.Bold)
    
    # ===== METADATA PANEL =====
    METADATA_LABEL = FontDef("Saira", 11)
    METADATA_VALUE = FontDef("Saira", 11, QFont.Weight.DemiBold)
    
    # ===== BUTTONS & CONTROLS =====
    BUTTON = FontDef("Electrolize", 12)
    BUTTON_SMALL = FontDef("Electrolize", 10)
    CHECKBOX = FontDef("Saira", 12)
    
    # ===== SPECIAL / MONOSPACE =====
    TIMECODE = FontDef("Consolas", 13)
    CODE = FontDef("Consolas", 11)
    
    # ===== SMALL TEXT =====
    CAPTION = FontDef("Saira", 10)
    TOOLTIP = FontDef("Saira", 11)


# ===== HELPER FUNCTIONS =====

def get_font(font_def: FontDef) -> QFont:
    """Get QFont object from a FontDef."""
    return font_def.to_qfont()


def get_font_stylesheet(font_def: FontDef) -> str:
    """Get CSS stylesheet string from a FontDef."""
    return font_def.to_stylesheet()


def apply_font(widget, font_def: FontDef) -> None:
    """Apply font to a widget."""
    widget.setFont(font_def.to_qfont())


# ===== APP-WIDE DEFAULT =====

def get_app_font() -> QFont:
    """Get the default application font. Use in main.py with app.setFont()"""
    return Fonts.DEFAULT.to_qfont()


__all__ = ['Fonts', 'FontDef', 'get_font', 'get_font_stylesheet', 'apply_font', 'get_app_font']
