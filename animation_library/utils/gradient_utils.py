"""
Gradient utilities for thumbnail compositing

Pattern: Image processing helpers
Inspired by: Current animation_library + hybrid plan
"""

import numpy as np
from typing import Tuple
from PyQt6.QtGui import QImage, QPixmap, QPainter
from PyQt6.QtCore import Qt


def create_vertical_gradient(
    width: int,
    height: int,
    top_color: Tuple[float, float, float],
    bottom_color: Tuple[float, float, float]
) -> QImage:
    """
    Create vertical gradient QImage

    Args:
        width: Width in pixels
        height: Height in pixels
        top_color: Top color as (R, G, B) normalized 0-1
        bottom_color: Bottom color as (R, G, B) normalized 0-1

    Returns:
        QImage with gradient
    """
    # Create numpy array for gradient
    gradient = np.zeros((height, width, 3), dtype=np.uint8)

    # Convert normalized RGB to 0-255
    top_rgb = (int(top_color[0] * 255), int(top_color[1] * 255), int(top_color[2] * 255))
    bottom_rgb = (int(bottom_color[0] * 255), int(bottom_color[1] * 255), int(bottom_color[2] * 255))

    # Create gradient row by row
    for y in range(height):
        t = y / (height - 1) if height > 1 else 0
        r = int(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * t)
        g = int(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * t)
        b = int(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * t)
        gradient[y, :] = [r, g, b]

    # Convert to QImage (RGB888 format)
    qimage = QImage(gradient.data, width, height, width * 3, QImage.Format.Format_RGB888)

    # Make a copy so numpy array can be garbage collected
    return qimage.copy()


def composite_image_on_gradient_colors(
    foreground_image: QImage,
    top_color: Tuple[float, float, float],
    bottom_color: Tuple[float, float, float],
    canvas_size: int = 300
) -> QImage:
    """
    Composite foreground image on gradient background with colorkey support

    Args:
        foreground_image: Foreground QImage (may have alpha)
        top_color: Top gradient color (R, G, B) normalized 0-1
        bottom_color: Bottom gradient color (R, G, B) normalized 0-1
        canvas_size: Size of square canvas

    Returns:
        Composited QImage
    """
    # Create gradient background
    gradient = create_vertical_gradient(canvas_size, canvas_size, top_color, bottom_color)

    # Convert to numpy for alpha compositing
    # Thumbnails from Blender have proper RGBA alpha channel (film_transparent=True)
    fg_width = foreground_image.width()
    fg_height = foreground_image.height()

    # Convert QImage to RGBA format first to ensure consistent handling
    if foreground_image.format() != QImage.Format.Format_RGBA8888:
        foreground_image = foreground_image.convertToFormat(QImage.Format.Format_RGBA8888)

    # Convert QImage to numpy array (RGBA format)
    ptr = foreground_image.constBits()
    ptr.setsize(fg_width * fg_height * 4)
    fg_array = np.array(ptr, dtype=np.uint8).reshape((fg_height, fg_width, 4)).copy()

    # Extract RGB and alpha channels
    fg_rgb = fg_array[:, :, :3]  # RGB channels
    fg_alpha = fg_array[:, :, 3]  # Alpha channel

    # Use alpha channel directly (Blender renders with proper transparency)
    # No colorkey needed - trust the native alpha from Blender's film_transparent
    alpha = fg_alpha[:, :, np.newaxis] / 255.0

    # Convert gradient QImage to numpy
    gradient_ptr = gradient.constBits()
    gradient_ptr.setsize(canvas_size * canvas_size * 3)
    gradient_full = np.array(gradient_ptr, dtype=np.uint8).reshape((canvas_size, canvas_size, 3)).copy()

    # Extract the portion matching foreground position
    x = (canvas_size - fg_width) // 2
    y = (canvas_size - fg_height) // 2
    gradient_bg_array = gradient_full[y:y+fg_height, x:x+fg_width]

    # Alpha composite: result = foreground * alpha + background * (1 - alpha)
    composited = (fg_rgb * alpha + gradient_bg_array * (1 - alpha)).astype(np.uint8)

    # Convert back to QImage
    composited_qimage = QImage(composited.data, fg_width, fg_height, fg_width * 3, QImage.Format.Format_RGB888).copy()

    # Now place this on the full canvas
    result_pixmap = QPixmap.fromImage(gradient)
    painter = QPainter(result_pixmap)
    painter.drawImage(x, y, composited_qimage)
    painter.end()

    return result_pixmap.toImage()


def get_gradient_from_theme(theme_manager) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Get gradient colors from theme manager

    Args:
        theme_manager: ThemeManager instance

    Returns:
        Tuple of (top_color, bottom_color)
    """
    return theme_manager.get_gradient_colors()


__all__ = [
    'create_vertical_gradient',
    'composite_image_on_gradient_colors',
    'get_gradient_from_theme',
]
