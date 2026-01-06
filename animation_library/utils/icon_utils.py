"""
Icon Utilities
Handles SVG icon colorization for theme customization with saturation-based variations
"""

import os
import re
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QByteArray
from .color_utils import rgb_to_hex, hsl_to_rgb, rgb_to_hsl, hex_to_rgb

def calculate_brightness(hex_color: str) -> float:
    """
    Calculate perceived brightness/luminosity of a color (0-100%)

    Args:
        hex_color: Hex color string

    Returns:
        Brightness percentage (0-100)
    """
    r, g, b = hex_to_rgb(hex_color)
    # Use perceived brightness formula (weighted for human eye sensitivity)
    brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return brightness * 100


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
    # Keep lightness relatively close to original brightness
    new_lightness = l * (original_brightness / 100.0) * 1.2  # 1.2 factor to keep it visible
    new_lightness = min(new_lightness, 90)  # Cap at 90% to avoid pure white
    new_lightness = max(new_lightness, 10)  # Floor at 10% to avoid pure black

    # Convert back to RGB and hex
    new_r, new_g, new_b = hsl_to_rgb(h, new_saturation, new_lightness)
    return rgb_to_hex((new_r, new_g, new_b))


def colorize_white_svg(svg_path: str, hex_color: str, use_saturation_variations: bool = True) -> QIcon:
    """
    Colorize an SVG icon with custom color and saturation variations based on gray values

    Args:
        svg_path: Path to the SVG file
        hex_color: Target color as hex string (e.g., '#D4AF37')
        use_saturation_variations: If True, maps gray values to saturation variations.
                                   If False, uses flat single color (legacy behavior)

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
            # NEW: Saturation-based variation system
            # Find all hex colors and replace with saturation-varied versions

            def replace_color_with_variation(match):
                """Replace matched color with saturation-varied version"""
                original_color = match.group(1)
                # Calculate brightness of original color
                brightness = calculate_brightness(original_color)
                # Get new color with adjusted saturation
                new_color = apply_saturation_variation(hex_color, brightness)
                # Return the full match with new color
                prefix = match.group(0).split(original_color)[0]
                suffix = match.group(0).split(original_color)[1] if len(match.group(0).split(original_color)) > 1 else ''
                return f'{prefix}{new_color}{suffix}'

            # Pattern 1: CSS style fill colors - fill: #xxxxxx;
            svg_content = re.sub(
                r'fill:\s*(#[0-9a-fA-F]{3,6})\b',
                replace_color_with_variation,
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 2: CSS style stroke colors - stroke: #xxxxxx;
            svg_content = re.sub(
                r'stroke:\s*(#[0-9a-fA-F]{3,6})\b',
                replace_color_with_variation,
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 3: Attribute format - fill="#xxxxxx"
            svg_content = re.sub(
                r'fill="(#[0-9a-fA-F]{3,6})"',
                replace_color_with_variation,
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 4: Attribute format - stroke="#xxxxxx"
            svg_content = re.sub(
                r'stroke="(#[0-9a-fA-F]{3,6})"',
                replace_color_with_variation,
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 5: Replace named color "white" (treat as 100% brightness)
            white_replacement = apply_saturation_variation(hex_color, 95.0)  # Near-white
            svg_content = re.sub(r'fill:\s*white\b', f'fill: {white_replacement}', svg_content, flags=re.IGNORECASE)
            svg_content = re.sub(r'stroke:\s*white\b', f'stroke: {white_replacement}', svg_content, flags=re.IGNORECASE)
            svg_content = re.sub(r'fill="white"', f'fill="{white_replacement}"', svg_content, flags=re.IGNORECASE)
            svg_content = re.sub(r'stroke="white"', f'stroke="{white_replacement}"', svg_content, flags=re.IGNORECASE)

            # Pattern 6: Colorize gradient stop colors (for linearGradient and radialGradient)
            # Find stop-color attributes in gradient definitions and apply saturation variations
            def replace_gradient_stop_color(match):
                """Replace gradient stop color with saturation-varied version"""
                stop_color_value = match.group(1)
                # Extract RGB values from rgb(R,G,B) or convert hex
                if 'rgb(' in stop_color_value:
                    # Parse rgb(R, G, B) - handle with or without spaces
                    rgb_match = re.search(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', stop_color_value)
                    if rgb_match:
                        r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
                        # Convert to hex for brightness calculation
                        original_hex = rgb_to_hex((r, g, b))
                        brightness = calculate_brightness(original_hex)
                        new_color = apply_saturation_variation(hex_color, brightness)
                        return f'stop-color:{new_color}'
                elif stop_color_value.lower() == 'white':
                    # Handle named color "white"
                    brightness = 95.0
                    new_color = apply_saturation_variation(hex_color, brightness)
                    return f'stop-color:{new_color}'
                elif stop_color_value.startswith('#'):
                    # Handle hex colors
                    brightness = calculate_brightness(stop_color_value)
                    new_color = apply_saturation_variation(hex_color, brightness)
                    return f'stop-color:{new_color}'
                return match.group(0)  # Return unchanged if not recognized

            # Match stop-color in CSS style or as attribute, handling rgb() with parentheses
            svg_content = re.sub(
                r'stop-color:\s*([^;"\)]+(?:\([^)]*\))?[^;"]*)',
                replace_gradient_stop_color,
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 7: Affinity Designer - Inline RGB colors in style attributes
            # Handles: style="fill:rgb(171,171,171)" or style="stroke:rgb(100,100,100)"
            def replace_inline_rgb_color(match):
                """Replace inline RGB color with saturation-varied version"""
                property_name = match.group(1)  # 'fill' or 'stroke'
                r, g, b = int(match.group(2)), int(match.group(3)), int(match.group(4))
                # Convert to hex for brightness calculation
                original_hex = rgb_to_hex((r, g, b))
                brightness = calculate_brightness(original_hex)
                new_color = apply_saturation_variation(hex_color, brightness)
                # Return fill: or stroke: with new color
                return f'{property_name}:{new_color}'

            svg_content = re.sub(
                r'(fill|stroke):\s*rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
                replace_inline_rgb_color,
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 8: Affinity Designer - Remove gradient URL fills and replace with solid color
            # Handles: fill:url(#_Linear1) or fill="url(#gradientId)"
            # Strategy: Replace gradient references with a solid fill based on average brightness
            def replace_gradient_url(match):
                """Replace gradient URL with solid color fill"""
                # Use medium-high brightness (80%) as default for gradients
                # This assumes most gradients are light-colored (white-ish)
                default_brightness = 80.0
                new_color = apply_saturation_variation(hex_color, default_brightness)
                # Determine if it's CSS style or attribute format
                if 'fill:' in match.group(0):
                    return f'fill:{new_color}'
                else:
                    return f'fill="{new_color}"'

            svg_content = re.sub(
                r'fill:\s*url\([^)]+\)',
                replace_gradient_url,
                svg_content,
                flags=re.IGNORECASE
            )
            svg_content = re.sub(
                r'fill="url\([^)]+\)"',
                replace_gradient_url,
                svg_content,
                flags=re.IGNORECASE
            )

        else:
            # LEGACY: Flat single color replacement (original behavior)
            # Replace ALL hex colors with target color

            # Pattern 1: CSS style fill colors - fill: #xxxxxx;
            svg_content = re.sub(
                r'fill:\s*#[0-9a-fA-F]{3,6}\b',
                f'fill: {hex_color}',
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 2: CSS style stroke colors - stroke: #xxxxxx;
            svg_content = re.sub(
                r'stroke:\s*#[0-9a-fA-F]{3,6}\b',
                f'stroke: {hex_color}',
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 3: Attribute format - fill="#xxxxxx"
            svg_content = re.sub(
                r'fill="#[0-9a-fA-F]{3,6}"',
                f'fill="{hex_color}"',
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 4: Attribute format - stroke="#xxxxxx"
            svg_content = re.sub(
                r'stroke="#[0-9a-fA-F]{3,6}"',
                f'stroke="{hex_color}"',
                svg_content,
                flags=re.IGNORECASE
            )

            # Pattern 5: Replace named color "white" if present
            svg_content = re.sub(r'fill:\s*white\b', f'fill: {hex_color}', svg_content, flags=re.IGNORECASE)
            svg_content = re.sub(r'stroke:\s*white\b', f'stroke: {hex_color}', svg_content, flags=re.IGNORECASE)
            svg_content = re.sub(r'fill="white"', f'fill="{hex_color}"', svg_content, flags=re.IGNORECASE)
            svg_content = re.sub(r'stroke="white"', f'stroke="{hex_color}"', svg_content, flags=re.IGNORECASE)

            # Pattern 6: Replace gradient stop colors (flat color in legacy mode)
            # Replace all stop-color values with the single target color
            # This pattern handles rgb(), hex, and named colors in one pass
            svg_content = re.sub(
                r'stop-color:\s*([^;"\)]+(?:\([^)]*\))?[^;"]*)',
                f'stop-color:{hex_color}',
                svg_content,
                flags=re.IGNORECASE
            )

        # Convert to QByteArray and create QIcon
        svg_bytes = QByteArray(svg_content.encode('utf-8'))
        pixmap = QPixmap()
        pixmap.loadFromData(svg_bytes, 'SVG')

        return QIcon(pixmap)

    except Exception as e:
        print(f"Error colorizing SVG {svg_path}: {e}")
        # Fallback to loading original icon
        return QIcon(svg_path)


__all__ = ['colorize_white_svg', 'calculate_brightness', 'apply_saturation_variation']
