"""Color conversion utilities

Consolidated color conversion functions used throughout the UI.
Supports hex, RGB (0-1 range), and RGB (0-255 range) conversions.
"""

from typing import Tuple


def rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    """Convert RGB tuple (0-1 range) to hex color string

    Args:
        rgb: RGB color as tuple (0.0-1.0 range)

    Returns:
        Hex color string (e.g., "#FF5733")

    Example:
        >>> rgb_to_hex((1.0, 0.34, 0.2))
        "#FF5733"
    """
    # Normalize if needed
    if max(rgb[0], rgb[1], rgb[2]) > 1:
        rgb = tuple(c / 255.0 for c in rgb)

    return '#{:02x}{:02x}{:02x}'.format(
        int(rgb[0] * 255),
        int(rgb[1] * 255),
        int(rgb[2] * 255)
    )


def hex_to_rgb(hex_color: str) -> tuple:
    """
    Convert hex color to RGB tuple (0-255 range)

    Args:
        hex_color: Hex color string (e.g., '#AABBCC' or 'AABBCC')

    Returns:
        Tuple of (r, g, b) values in 0-255 range
    """
    hex_color = hex_color.lstrip('#')
    # Handle 3-digit hex codes
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_255_to_normalized(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert RGB (0-255 range) to normalized RGB (0-1 range)

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        RGB tuple (0.0-1.0 range)

    Example:
        >>> rgb_255_to_normalized(255, 128, 0)
        (1.0, 0.5, 0.0)
    """
    return (r / 255.0, g / 255.0, b / 255.0)


def rgb_normalized_to_255(rgb: Tuple[float, float, float]) -> Tuple[int, int, int]:
    """Convert normalized RGB (0-1 range) to RGB (0-255 range)

    Args:
        rgb: RGB tuple (0.0-1.0 range)

    Returns:
        RGB tuple (0-255 range)

    Example:
        >>> rgb_normalized_to_255((1.0, 0.5, 0.0))
        (255, 128, 0)
    """
    return (
        int(rgb[0] * 255),
        int(rgb[1] * 255),
        int(rgb[2] * 255)
    )

def rgb_to_hsl(r: int, g: int, b: int) -> tuple:
    """
    Convert RGB to HSL color space

    Args:
        r, g, b: RGB values in 0-255 range

    Returns:
        Tuple of (h, s, l) where h is 0-360, s and l are 0-100
    """
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    diff = max_val - min_val

    # Lightness
    l = (max_val + min_val) / 2.0

    if diff == 0:
        # Achromatic (gray)
        h = s = 0
    else:
        # Saturation
        s = diff / (2.0 - max_val - min_val) if l > 0.5 else diff / (max_val + min_val)

        # Hue
        if max_val == r:
            h = (g - b) / diff + (6 if g < b else 0)
        elif max_val == g:
            h = (b - r) / diff + 2
        else:
            h = (r - g) / diff + 4
        h /= 6

    return (h * 360, s * 100, l * 100)


def hsl_to_rgb(h: float, s: float, l: float) -> tuple:
    """
    Convert HSL to RGB color space

    Args:
        h: Hue in 0-360 range
        s: Saturation in 0-100 range
        l: Lightness in 0-100 range

    Returns:
        Tuple of (r, g, b) values in 0-255 range
    """
    h, s, l = h / 360.0, s / 100.0, l / 100.0

    if s == 0:
        # Achromatic (gray)
        r = g = b = l
    else:
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p

        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)

    return (int(r * 255), int(g * 255), int(b * 255))
