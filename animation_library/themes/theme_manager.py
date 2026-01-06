"""
ThemeManager - Centralized theme management

Pattern: Strategy pattern for theme switching
Inspired by: Current animation_library with improvements
"""

from typing import Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
from PyQt6.QtCore import QObject, pyqtSignal, QSettings


@dataclass
class ColorPalette:
    """Color palette for a theme"""

    # Background colors
    background: str
    background_secondary: str

    # Text colors
    text_primary: str
    text_secondary: str
    text_disabled: str

    # Accent colors
    accent: str
    accent_hover: str
    accent_pressed: str

    # Card colors
    card_background: str
    card_border: str
    card_selected: str

    # Gradient colors (normalized RGB tuples)
    gradient_top: Tuple[float, float, float]
    gradient_bottom: Tuple[float, float, float]

    # Button colors
    button_background: str
    button_hover: str
    button_pressed: str
    button_disabled: str

    # Error/Warning colors
    error: str
    warning: str
    success: str

    # Border/Divider colors
    border: str
    divider: str

    # Gold accent colors (for media controls and highlights)
    gold_primary: str = "#D4AF37"
    gold_hover: str = "#F0C040"
    gold_pressed: str = "#C4A030"
    gold_disabled: str = "#8A7828"

    # Media control colors
    media_background: str = "#2B2B2B"
    media_border: str = "#D4AF37"
    media_hover: str = "#3A3A3A"

    # Dialog colors (light theme for contrast)
    dialog_background: str = "#F5F5F5"
    dialog_text: str = "#2B2B2B"
    dialog_border: str = "#CCCCCC"

    # Header gradient colors (orange/gold theme from old repo)
    header_gradient_start: str = "#E5C046"  # Light gold/orange
    header_gradient_end: str = "#D4AF37"    # Darker gold
    header_icon_color: str = "#1a1a1a"      # Dark icons on light header
    folder_icon_color: str = "#D4AF37"      # Gold for folder tree icons

    # Selection and hover colors (Studio Library inspired)
    selection_text: str = "#FFFFFF"  # White text on selection
    selection_border: str = "#D4AF37"  # Border around selected items
    hover_overlay: str = "rgba(255, 255, 255, 60)"  # Hover state overlay
    card_overlay: str = "rgba(255, 255, 255, 20)"  # Subtle card background

    # List/dropdown item colors
    list_item_background: str = "#3A3A3A"  # Default gray background
    list_item_hover: str = "#3A8FB7"       # Hover state (accent)
    list_item_selected: str = "#3A8FB7"    # Selected state (accent)

    # UI sizing
    folder_text_size: int = 13  # Folder tree text size (8-20pt)


class Theme:
    """Base theme class"""

    def __init__(self, name: str, palette: ColorPalette, author: str = "Unknown", description: str = ""):
        self.name = name
        self.palette = palette
        self.author = author
        self.description = description

    def get_stylesheet(self) -> str:
        """
        Generate Qt stylesheet for this theme

        Returns:
            Complete QSS stylesheet string
        """
        raise NotImplementedError("Subclasses must implement get_stylesheet()")

    def get_gradient_colors(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """
        Get gradient colors for thumbnail backgrounds

        Returns:
            Tuple of (top_color, bottom_color) as normalized RGB tuples
        """
        return (self.palette.gradient_top, self.palette.gradient_bottom)

    @classmethod
    def from_json_file(cls, filepath: Path) -> 'Theme':
        """
        Load theme from JSON file

        Args:
            filepath: Path to JSON theme file

        Returns:
            Theme instance loaded from JSON
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> 'Theme':
        """
        Create theme from dictionary

        Args:
            data: Theme data dictionary

        Returns:
            Theme instance
        """
        from .dark_theme import DarkTheme  # Import here to avoid circular dependency

        name = data.get('name', 'Custom Theme')
        author = data.get('author', 'Unknown')
        description = data.get('description', '')
        colors = data.get('colors', {})

        # Map JSON structure to ColorPalette fields
        # JSON uses nested structure, ColorPalette uses flat structure
        palette_dict = {}

        # Background colors
        bg = colors.get('background', {})
        palette_dict['background'] = bg.get('primary', '#1E1E1E')
        palette_dict['background_secondary'] = bg.get('secondary', '#2D2D2D')

        # Text/Foreground colors
        fg = colors.get('foreground', {})
        palette_dict['text_primary'] = fg.get('primary', '#FFFFFF')
        palette_dict['text_secondary'] = fg.get('secondary', '#B0B0B0')
        palette_dict['text_disabled'] = fg.get('disabled', '#606060')

        # Accent colors
        accent = colors.get('accent', {})
        palette_dict['accent'] = accent.get('primary', '#3A8FB7')
        palette_dict['accent_hover'] = accent.get('hover', '#4A9FC7')
        palette_dict['accent_pressed'] = accent.get('pressed', '#2A7FA7')

        # Gold colors
        gold = colors.get('gold', {})
        palette_dict['gold_primary'] = gold.get('primary', '#D4AF37')
        palette_dict['gold_hover'] = gold.get('hover', '#F0C040')
        palette_dict['gold_pressed'] = gold.get('pressed', '#C4A030')
        palette_dict['gold_disabled'] = gold.get('light', '#8A7828')  # Use light as disabled fallback

        # Status colors
        danger = colors.get('danger', {})
        palette_dict['error'] = danger.get('primary', '#E74C3C')
        palette_dict['warning'] = danger.get('hover', '#F39C12')  # Use danger.hover as warning

        success = colors.get('success', {})
        palette_dict['success'] = success.get('primary', '#27AE60')

        # Border colors
        border = colors.get('border', {})
        palette_dict['border'] = border.get('primary', '#404040')
        palette_dict['divider'] = border.get('secondary', '#353535')

        # Button colors
        button = colors.get('button', {})
        palette_dict['button_background'] = button.get('background', '#3A3A3A')
        palette_dict['button_hover'] = button.get('hover', '#4A4A4A')
        palette_dict['button_pressed'] = button.get('pressed', '#2A2A2A')
        palette_dict['button_disabled'] = button.get('disabled', '#252525')

        # Card colors
        card = colors.get('card', {})
        palette_dict['card_background'] = card.get('background', '#2D2D2D')
        palette_dict['card_border'] = card.get('border', '#404040')
        palette_dict['card_selected'] = card.get('border_selected', '#3A8FB7')

        # Header colors
        header = colors.get('header', {})
        palette_dict['header_gradient_start'] = header.get('gradient_start', '#E5C046')
        palette_dict['header_gradient_end'] = header.get('gradient_end', '#D4AF37')
        palette_dict['header_icon_color'] = header.get('icon_color', '#1a1a1a')
        palette_dict['folder_icon_color'] = header.get('folder_icon_color', '#D4AF37')

        # Dialog colors
        dialog = colors.get('dialog', {})
        palette_dict['dialog_background'] = dialog.get('background', '#F5F5F5')
        palette_dict['dialog_text'] = dialog.get('text', '#2B2B2B')
        palette_dict['dialog_border'] = dialog.get('border', '#CCCCCC')

        # Selection and hover colors (Studio Library inspired)
        selection = colors.get('selection', {})
        palette_dict['selection_text'] = selection.get('text', '#FFFFFF')
        palette_dict['selection_border'] = selection.get('border', '#D4AF37')
        palette_dict['hover_overlay'] = selection.get('hover_overlay', 'rgba(255, 255, 255, 60)')
        palette_dict['card_overlay'] = selection.get('card_overlay', 'rgba(255, 255, 255, 20)')

        # List/dropdown item colors
        list_item = colors.get('list_item', {})
        palette_dict['list_item_background'] = list_item.get('background', '#3A3A3A')
        palette_dict['list_item_hover'] = list_item.get('hover', '#3A8FB7')
        palette_dict['list_item_selected'] = list_item.get('selected', '#3A8FB7')

        # UI sizing
        ui = colors.get('ui', {})
        palette_dict['folder_text_size'] = ui.get('folder_text_size', 13)

        # Gradient colors (for background gradients) - use tuples
        palette_dict['gradient_top'] = (0.25, 0.35, 0.55)
        palette_dict['gradient_bottom'] = (0.5, 0.5, 0.5)

        # Media control colors (use defaults)
        palette_dict['media_background'] = '#2B2B2B'
        palette_dict['media_border'] = palette_dict['gold_primary']
        palette_dict['media_hover'] = '#3A3A3A'

        # Create palette, using defaults for missing fields
        try:
            palette = ColorPalette(**palette_dict)
        except TypeError as e:
            # If some fields are missing, create with defaults from DarkTheme
            dark = DarkTheme()
            default_dict = dark.palette.__dict__.copy()
            default_dict.update(palette_dict)
            palette = ColorPalette(**default_dict)

        theme = cls(name, palette, author, description)

        # Create a get_stylesheet method that uses the theme's current palette
        # This ensures live preview works when palette is modified
        def get_stylesheet_dynamic():
            """Generate stylesheet using current theme palette"""
            dark_theme = DarkTheme()
            dark_theme.palette = theme.palette  # Use current palette
            return dark_theme.get_stylesheet()

        theme.get_stylesheet = get_stylesheet_dynamic
        return theme

    def to_json_file(self, filepath: Path):
        """
        Save theme to JSON file

        Args:
            filepath: Path to save JSON file
        """
        data = self.to_dict()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def to_dict(self) -> dict:
        """
        Convert theme to dictionary

        Returns:
            Theme data as dictionary (matching JSON structure)
        """
        p = self.palette

        # Build nested structure matching JSON format
        colors = {
            'background': {
                'primary': p.background,
                'secondary': p.background_secondary,
                'tertiary': p.background,  # Reuse primary
                'hover': p.button_hover,  # Use button hover as fallback
                'selected': p.card_selected,
                'grid_top': p.background_secondary,
                'grid_bottom': p.background
            },
            'foreground': {
                'primary': p.text_primary,
                'secondary': p.text_secondary,
                'tertiary': p.text_secondary,  # Reuse secondary
                'disabled': p.text_disabled
            },
            'accent': {
                'primary': p.accent,
                'hover': p.accent_hover,
                'pressed': p.accent_pressed,
                'light': p.accent_hover  # Use hover as light
            },
            'gold': {
                'primary': p.gold_primary,
                'hover': p.gold_hover,
                'pressed': p.gold_pressed,
                'light': p.gold_hover  # Use hover as light
            },
            'danger': {
                'primary': p.error,
                'hover': p.warning,  # Use warning as danger.hover
                'pressed': p.error,  # Reuse error
                'light': p.error
            },
            'success': {
                'primary': p.success,
                'hover': p.success,
                'pressed': p.success
            },
            'border': {
                'primary': p.border,
                'secondary': p.divider,
                'light': p.border,
                'darker': p.divider
            },
            'button': {
                'background': p.button_background,
                'hover': p.button_hover,
                'pressed': p.button_pressed,
                'disabled': p.button_disabled
            },
            'card': {
                'background': p.card_background,
                'border': p.card_border,
                'border_hover': p.gold_primary,  # Use gold for hover
                'border_selected': p.card_selected,
                'background_hover': p.button_hover
            },
            'header': {
                'gradient_start': p.header_gradient_start,
                'gradient_end': p.header_gradient_end,
                'icon_color': p.header_icon_color,
                'folder_icon_color': p.folder_icon_color
            },
            'ui': {
                'folder_text_size': p.folder_text_size
            },
            'dialog': {
                'background': p.dialog_background,
                'text': p.dialog_text,
                'button_background': p.button_background,
                'button_text': p.text_primary,
                'input_background': p.background,
                'input_text': p.text_primary,
                'border': p.dialog_border
            },
            'selection': {
                'text': p.selection_text,
                'border': p.selection_border
            },
            'list_item': {
                'background': p.list_item_background,
                'hover': p.list_item_hover,
                'selected': p.list_item_selected
            }
        }

        return {
            'name': self.name,
            'description': self.description or f'{self.name} theme',
            'author': self.author or 'Unknown',
            'colors': colors
        }


class ThemeManager(QObject):
    """
    Manages application themes and style switching

    Usage:
        theme_manager = ThemeManager()
        theme_manager.set_theme("dark")
        stylesheet = theme_manager.get_current_stylesheet()
    """

    # Signals
    theme_changed = pyqtSignal(str)  # Emits theme name when theme changes
    folder_text_size_changed = pyqtSignal(int)  # Emits when folder text size changes

    def __init__(self):
        super().__init__()
        self._themes = {}
        self._current_theme: Optional[Theme] = None
        self._load_builtin_themes()
        self._load_custom_themes()

    def register_theme(self, theme: Theme):
        """
        Register a theme

        Args:
            theme: Theme instance to register
        """
        self._themes[theme.name] = theme

    def set_theme(self, theme_name: str):
        """
        Set active theme

        Args:
            theme_name: Name of theme to activate ("light" or "dark")

        Raises:
            ValueError: If theme name not found
        """
        if theme_name not in self._themes:
            raise ValueError(f"Theme '{theme_name}' not found. Available: {list(self._themes.keys())}")

        self._current_theme = self._themes[theme_name]

        # Save theme preference to settings
        from ..config import Config
        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)
        settings.setValue("theme/current", theme_name)

        self.theme_changed.emit(theme_name)  # Emit signal when theme changes

    def get_current_theme(self) -> Optional[Theme]:
        """Get currently active theme"""
        return self._current_theme

    def get_current_stylesheet(self) -> str:
        """
        Get stylesheet for current theme

        Returns:
            QSS stylesheet string, or empty string if no theme set
        """
        if self._current_theme is None:
            return ""
        return self._current_theme.get_stylesheet()

    def get_gradient_colors(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """
        Get gradient colors from current theme

        Returns:
            Tuple of (top_color, bottom_color) as normalized RGB tuples
        """
        if self._current_theme is None:
            # Return default if no theme set
            from ..config import Config
            return (Config.DEFAULT_GRADIENT_TOP, Config.DEFAULT_GRADIENT_BOTTOM)

        return self._current_theme.get_gradient_colors()

    def get_color(self, color_name: str) -> str:
        """
        Get specific color from current theme palette

        Args:
            color_name: Name of color (e.g., "accent", "background")

        Returns:
            Color as hex string (e.g., "#FF5500")
        """
        if self._current_theme is None:
            return "#000000"

        return getattr(self._current_theme.palette, color_name, "#000000")

    def set_folder_text_size(self, size: int):
        """
        Set folder tree text size and emit signal

        Args:
            size: Font size in points (8-20)
        """
        if self._current_theme is None:
            return

        # Clamp to valid range
        size = max(8, min(20, size))

        # Update palette
        self._current_theme.palette.folder_text_size = size

        # Emit signal
        self.folder_text_size_changed.emit(size)

    def get_folder_text_size(self) -> int:
        """Get current folder text size"""
        if self._current_theme is None:
            return 13
        return self._current_theme.palette.folder_text_size

    def _load_builtin_themes(self):
        """Load built-in themes from JSON files"""
        from ..config import Config
        builtin_dir = Config.APP_ROOT / 'themes' / 'built_in'
        if builtin_dir.exists():
            for json_file in builtin_dir.glob('*.json'):
                try:
                    theme = Theme.from_json_file(json_file)
                    self.register_theme(theme)
                except Exception as e:
                    print(f"Failed to load theme {json_file}: {e}")

        # Fallback: register hardcoded themes if no JSON found
        if not self._themes:
            from .dark_theme import DarkTheme
            from .light_theme import LightTheme
            self.register_theme(DarkTheme())
            self.register_theme(LightTheme())

    def _load_custom_themes(self):
        """Load user custom themes"""
        from ..config import Config
        custom_dir = Config.APP_ROOT / 'themes' / 'custom'
        if custom_dir.exists():
            for json_file in custom_dir.glob('*.json'):
                try:
                    theme = Theme.from_json_file(json_file)
                    self.register_theme(theme)
                except Exception as e:
                    print(f"Failed to load custom theme {json_file}: {e}")

    def save_custom_theme(self, theme: Theme) -> bool:
        """
        Save custom theme to JSON

        Args:
            theme: Theme to save

        Returns:
            True if saved successfully
        """
        from ..config import Config
        custom_dir = Config.APP_ROOT / 'themes' / 'custom'
        custom_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize theme name for filename
        filename = theme.name.lower().replace(' ', '_') + '.json'
        filepath = custom_dir / filename

        try:
            theme.to_json_file(filepath)
            self.register_theme(theme)
            return True
        except Exception as e:
            print(f"Failed to save theme: {e}")
            return False

    def delete_custom_theme(self, theme_name: str) -> bool:
        """
        Delete custom theme

        Args:
            theme_name: Name of theme to delete

        Returns:
            True if deleted successfully
        """
        from ..config import Config
        custom_dir = Config.APP_ROOT / 'themes' / 'custom'
        filename = theme_name.lower().replace(' ', '_') + '.json'
        filepath = custom_dir / filename

        if filepath.exists():
            filepath.unlink()
            if theme_name in self._themes:
                del self._themes[theme_name]
            return True
        return False

    def is_builtin_theme(self, theme_name: str) -> bool:
        """
        Check if a theme is built-in (not custom)

        Args:
            theme_name: Name of theme to check

        Returns:
            True if theme is built-in
        """
        from ..config import Config
        import json

        builtin_dir = Config.APP_ROOT / 'themes' / 'built_in'
        if builtin_dir.exists():
            for json_file in builtin_dir.glob('*.json'):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get('name') == theme_name:
                            return True
                except Exception:
                    pass
        return False

    def import_theme(self, filepath: Path) -> bool:
        """
        Import theme from external JSON file

        Args:
            filepath: Path to JSON theme file

        Returns:
            True if imported successfully
        """
        try:
            theme = Theme.from_json_file(filepath)
            return self.save_custom_theme(theme)
        except Exception as e:
            print(f"Failed to import theme: {e}")
            return False

    def export_theme(self, theme_name: str, filepath: Path) -> bool:
        """
        Export theme to JSON file

        Args:
            theme_name: Name of theme to export
            filepath: Path to save JSON file

        Returns:
            True if exported successfully
        """
        if theme_name not in self._themes:
            return False

        try:
            theme = self._themes[theme_name]
            theme.to_json_file(filepath)
            return True
        except Exception as e:
            print(f"Failed to export theme: {e}")
            return False

    def get_all_themes(self) -> list:
        """
        Get list of all available themes

        Returns:
            List of Theme instances
        """
        return list(self._themes.values())


# Singleton instance
_theme_manager_instance: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """
    Get global ThemeManager singleton instance

    Returns:
        Global ThemeManager instance
    """
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = ThemeManager()

        # Load saved theme preference from settings
        from ..config import Config
        settings = QSettings(Config.APP_AUTHOR, Config.APP_NAME)
        saved_theme = settings.value("theme/current", Config.DEFAULT_THEME)

        # Set theme (try saved theme first, then default, then first available)
        try:
            _theme_manager_instance.set_theme(saved_theme)
        except ValueError:
            # Saved theme not found, try default
            try:
                _theme_manager_instance.set_theme(Config.DEFAULT_THEME)
            except ValueError:
                # Fallback to first available theme if default not found
                themes = _theme_manager_instance.get_all_themes()
                if themes:
                    _theme_manager_instance.set_theme(themes[0].name)

    return _theme_manager_instance


__all__ = ['Theme', 'ColorPalette', 'ThemeManager', 'get_theme_manager']
