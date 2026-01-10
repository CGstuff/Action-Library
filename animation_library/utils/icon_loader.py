"""
Icon Loader - Centralized icon path resolution with theme-aware colorization

Provides easy access to SVG icons by name with automatic colorization.
"""
import os
import re
from pathlib import Path
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QByteArray
from .color_utils import hex_to_rgb, rgb_to_hex, rgb_to_hsl, hsl_to_rgb


class IconLoader:
    """Load icons from icons directory"""

    # Base directory - go up one level from utils to animation_library, then to icons
    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "icons"
    )

    # Icon registry
    ICONS = {
        "arrow_down": "arrow_down.svg",
        "arrow_right": "arrow_right.svg",
        "checkbox_checked": "checkbox_checked.svg",
        "checkbox_unchecked": "checkbox_unchecked.svg",
        "play": "play.svg",
        "pause": "pause.svg",
        "loop": "loop.svg",
        "add": "add.svg",
        "edit": "edit.svg",
        "refresh": "refresh.svg",
        "delete": "delete.svg",
        "apply_to_blender": "apply_to_blender.svg",
        "al_icon": "AL.svg",
        "settings": "settings.svg",
        "view_mode": "view_mode.svg",
        "console": "console.svg",
        "resize_grid": "resize_grid.svg",
        "folder_closed": "folder_closed.svg",
        "folder_open": "folder_open.svg",
        "root_icon": "root.svg",
        "favorite_icon": "favorite.svg",
        "recent_icon": "recent.svg",
        "archive_icon": "Archives.svg",  # Archive folder icon
        "trash_icon": "delete.svg",  # Reuse delete icon for trash
        "pose_icon": "pose.svg",  # Pose folder icon
        "animation_icon": "action.svg",  # Animation folder icon

        # Card badges
        "action_badge": "action.svg",  # Badge for action cards
        "pose_badge": "pose.svg",  # Badge for pose cards

        # Folder presets
        "folder_default": "folder_presets/default.svg",
        "folder_body": "folder_presets/body.svg",
        "folder_face": "folder_presets/face.svg",
        "folder_hand": "folder_presets/hand.svg",
        "folder_locomotion": "folder_presets/locomotion.svg",
        "folder_combat": "folder_presets/combat.svg",
        "folder_idle": "folder_presets/idle.svg",
    }

    @classmethod
    def get(cls, name: str) -> str:
        """
        Get icon path by name

        Args:
            name: Icon name from ICONS registry

        Returns:
            Absolute path to icon file with forward slashes

        Raises:
            KeyError: If icon name not found
        """
        filename = cls.ICONS.get(name)
        if not filename:
            raise KeyError(f"Icon '{name}' not found")
        return os.path.join(cls.base_dir, filename).replace("\\", "/")

    @staticmethod
    def calculate_brightness(hex_color: str) -> float:
        """
        Calculate perceived brightness of a color (0-100%)

        Args:
            hex_color: Hex color string

        Returns:
            Brightness percentage (0-100)
        """
        r, g, b = hex_to_rgb(hex_color)
        # Use perceived brightness formula (weighted for human eye sensitivity)
        brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        return brightness * 100

    @staticmethod
    def apply_saturation_variation(target_color: str, original_brightness: float) -> str:
        """
        Apply saturation variation based on original brightness

        Args:
            target_color: Target theme color as hex string
            original_brightness: Original color brightness (0-100%)

        Returns:
            New color with adjusted saturation as hex string
        """
        # Convert target color to HSL
        r, g, b = hex_to_rgb(target_color)
        h, s, l = rgb_to_hsl(r, g, b)

        # Map brightness to saturation multiplier
        if original_brightness >= 80:
            # White/Light gray -> 100% saturation (full theme color)
            saturation_multiplier = 1.0
        elif original_brightness >= 60:
            # Medium-light gray -> 70% saturation
            saturation_multiplier = 0.7
        elif original_brightness >= 40:
            # Medium gray -> 50% saturation
            saturation_multiplier = 0.5
        elif original_brightness >= 20:
            # Dark gray -> 30% saturation
            saturation_multiplier = 0.3
        else:
            # Very dark -> 15% saturation
            saturation_multiplier = 0.15

        # Apply saturation multiplier
        new_saturation = s * saturation_multiplier

        # Adjust lightness based on original brightness to maintain similar visual weight
        new_lightness = l * (original_brightness / 100.0) * 1.2  # 1.2 factor to keep it visible
        new_lightness = min(new_lightness, 90)  # Cap at 90% to avoid pure white
        new_lightness = max(new_lightness, 10)  # Floor at 10% to avoid pure black

        # Convert back to RGB and hex
        new_r, new_g, new_b = hsl_to_rgb(h, new_saturation, new_lightness)
        return rgb_to_hex((new_r, new_g, new_b))

    @staticmethod
    def colorize_icon(svg_path: str, hex_color: str, use_saturation_variations: bool = True) -> QIcon:
        """
        Colorize an SVG icon with custom color and saturation variations

        Args:
            svg_path: Path to the SVG file
            hex_color: Target color as hex string (e.g., '#D4AF37')
            use_saturation_variations: If True, maps gray values to saturation variations

        Returns:
            QIcon with the colorized SVG
        """
        if not os.path.exists(svg_path):
            print(f"Warning: SVG icon not found: {svg_path}")
            return QIcon()

        try:
            # Read SVG file as text
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()

            # Normalize hex color (ensure it has #)
            if not hex_color.startswith('#'):
                hex_color = '#' + hex_color

            if use_saturation_variations:
                # Saturation-based variation system
                def replace_color_with_variation(match):
                    """Replace matched color with saturation-varied version"""
                    original_color = match.group(1)
                    brightness = IconLoader.calculate_brightness(original_color)
                    new_color = IconLoader.apply_saturation_variation(hex_color, brightness)
                    prefix = match.group(0).split(original_color)[0]
                    suffix = match.group(0).split(original_color)[1] if len(match.group(0).split(original_color)) > 1 else ''
                    return f'{prefix}{new_color}{suffix}'

                # Replace various SVG color patterns
                svg_content = re.sub(r'fill:\s*(#[0-9a-fA-F]{3,6})\b', replace_color_with_variation, svg_content, flags=re.IGNORECASE)
                svg_content = re.sub(r'stroke:\s*(#[0-9a-fA-F]{3,6})\b', replace_color_with_variation, svg_content, flags=re.IGNORECASE)
                svg_content = re.sub(r'fill="(#[0-9a-fA-F]{3,6})"', replace_color_with_variation, svg_content, flags=re.IGNORECASE)
                svg_content = re.sub(r'stroke="(#[0-9a-fA-F]{3,6})"', replace_color_with_variation, svg_content, flags=re.IGNORECASE)

                # Handle named color "white"
                white_replacement = IconLoader.apply_saturation_variation(hex_color, 95.0)
                svg_content = re.sub(r'fill:\s*white\b', f'fill: {white_replacement}', svg_content, flags=re.IGNORECASE)
                svg_content = re.sub(r'stroke:\s*white\b', f'stroke: {white_replacement}', svg_content, flags=re.IGNORECASE)
                svg_content = re.sub(r'fill="white"', f'fill="{white_replacement}"', svg_content, flags=re.IGNORECASE)
                svg_content = re.sub(r'stroke="white"', f'stroke="{white_replacement}"', svg_content, flags=re.IGNORECASE)

            # Convert to QByteArray and create QIcon
            svg_bytes = QByteArray(svg_content.encode('utf-8'))
            pixmap = QPixmap()
            pixmap.loadFromData(svg_bytes, 'SVG')

            return QIcon(pixmap)

        except Exception as e:
            print(f"Error colorizing SVG {svg_path}: {e}")
            # Fallback to loading original icon
            return QIcon(svg_path)

    @classmethod
    def get_themed_icon(cls, name: str, color: str = None) -> QIcon:
        """
        Get an icon with theme-aware colorization.

        Convenience method that combines get() and colorize_icon() with
        automatic theme color detection.

        Args:
            name: Icon name from ICONS registry
            color: Optional hex color. If None, uses current theme's icon color.

        Returns:
            QIcon with theme-appropriate colorization
        """
        # Import here to avoid circular imports
        from ..themes.theme_manager import get_theme_manager

        icon_path = cls.get(name)

        if color is None:
            theme = get_theme_manager().get_current_theme()
            color = theme.palette.icon_color if theme else "#FFFFFF"

        return cls.colorize_icon(icon_path, color)


__all__ = ['IconLoader']
