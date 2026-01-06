"""
ThumbnailGenerator - Generate thumbnails and preview videos

Pattern: Image processing and video generation
Inspired by: Current animation_library with OpenCV
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from ..config import Config


class ThumbnailGenerator:
    """
    Generate thumbnails and preview videos from Blender renders

    Features:
    - Create PNG thumbnails from images
    - Generate preview videos (GIF/MP4)
    - Resize and optimize images
    - Composite on gradient backgrounds

    Usage:
        generator = ThumbnailGenerator()
        thumbnail_path = generator.create_thumbnail(source_image, output_path)
        preview_path = generator.create_preview_video(frames, output_path)
    """

    def __init__(self):
        self.thumbnail_size = Config.THUMBNAIL_SIZE
        self.preview_fps = Config.PREVIEW_VIDEO_FPS
        self.preview_duration = Config.PREVIEW_VIDEO_DURATION_SEC

    def create_thumbnail(
        self,
        source_image_path: Path,
        output_path: Path,
        size: Optional[int] = None
    ) -> Optional[Path]:
        """
        Create thumbnail from source image

        Args:
            source_image_path: Path to source image
            output_path: Destination path for thumbnail
            size: Max dimension (defaults to Config.THUMBNAIL_SIZE)

        Returns:
            Path to created thumbnail or None on error
        """
        try:
            size = size or self.thumbnail_size

            # Load image
            image = Image.open(source_image_path)

            # Resize maintaining aspect ratio
            image.thumbnail((size, size), Image.Resampling.LANCZOS)

            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save as PNG
            image.save(output_path, 'PNG', optimize=True)

            return output_path

        except Exception as e:
            print(f"Error creating thumbnail: {e}")
            return None

    def create_thumbnail_with_gradient(
        self,
        source_image_path: Path,
        output_path: Path,
        gradient_top: Tuple[float, float, float],
        gradient_bottom: Tuple[float, float, float],
        size: Optional[int] = None
    ) -> Optional[Path]:
        """
        Create thumbnail composited on gradient background

        Args:
            source_image_path: Path to source image
            output_path: Destination path
            gradient_top: Top gradient color as (R, G, B) normalized 0-1
            gradient_bottom: Bottom gradient color as (R, G, B) normalized 0-1
            size: Max dimension

        Returns:
            Path to created thumbnail or None on error
        """
        try:
            size = size or self.thumbnail_size

            # Load source image with OpenCV
            img = cv2.imread(str(source_image_path), cv2.IMREAD_UNCHANGED)
            if img is None:
                print(f"Failed to load image: {source_image_path}")
                return None

            # Resize maintaining aspect ratio
            h, w = img.shape[:2]
            scale = min(size / w, size / h)
            new_w, new_h = int(w * scale), int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

            # Create gradient background
            gradient = self._create_gradient(size, size, gradient_top, gradient_bottom)

            # Composite image on gradient
            result = self._composite_on_gradient(img, gradient)

            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save
            cv2.imwrite(str(output_path), result)

            return output_path

        except Exception as e:
            print(f"Error creating thumbnail with gradient: {e}")
            return None

    def _create_gradient(
        self,
        width: int,
        height: int,
        top_color: Tuple[float, float, float],
        bottom_color: Tuple[float, float, float]
    ) -> np.ndarray:
        """
        Create vertical gradient image

        Args:
            width: Width in pixels
            height: Height in pixels
            top_color: Top color (R, G, B) normalized 0-1
            bottom_color: Bottom color (R, G, B) normalized 0-1

        Returns:
            Gradient image as numpy array (BGR)
        """
        # Convert to BGR and 0-255
        top_bgr = (int(top_color[2] * 255), int(top_color[1] * 255), int(top_color[0] * 255))
        bottom_bgr = (int(bottom_color[2] * 255), int(bottom_color[1] * 255), int(bottom_color[0] * 255))

        # Create gradient
        gradient = np.zeros((height, width, 3), dtype=np.uint8)

        for y in range(height):
            t = y / (height - 1) if height > 1 else 0
            color = (
                int(top_bgr[0] + (bottom_bgr[0] - top_bgr[0]) * t),
                int(top_bgr[1] + (bottom_bgr[1] - top_bgr[1]) * t),
                int(top_bgr[2] + (bottom_bgr[2] - top_bgr[2]) * t)
            )
            gradient[y, :] = color

        return gradient

    def _composite_on_gradient(
        self,
        foreground: np.ndarray,
        background: np.ndarray
    ) -> np.ndarray:
        """
        Composite foreground image on background gradient

        Args:
            foreground: Foreground image (may have alpha channel)
            background: Background gradient

        Returns:
            Composited image
        """
        fg_h, fg_w = foreground.shape[:2]
        bg_h, bg_w = background.shape[:2]

        # Center foreground on background
        y_offset = (bg_h - fg_h) // 2
        x_offset = (bg_w - fg_w) // 2

        # Start with background copy
        result = background.copy()

        # Extract alpha channel if present
        if foreground.shape[2] == 4:
            alpha = foreground[:, :, 3] / 255.0
            foreground_rgb = foreground[:, :, :3]
        else:
            alpha = np.ones((fg_h, fg_w), dtype=float)
            foreground_rgb = foreground

        # Alpha blend
        for c in range(3):
            result[y_offset:y_offset+fg_h, x_offset:x_offset+fg_w, c] = (
                alpha * foreground_rgb[:, :, c] +
                (1 - alpha) * result[y_offset:y_offset+fg_h, x_offset:x_offset+fg_w, c]
            )

        return result

    def create_preview_video(
        self,
        frame_paths: list[Path],
        output_path: Path,
        fps: Optional[int] = None
    ) -> Optional[Path]:
        """
        Create preview video from frames

        NOTE: This is a placeholder for Phase 3 implementation

        Args:
            frame_paths: List of paths to frame images
            output_path: Destination video path
            fps: Frames per second

        Returns:
            Path to created video or None
        """
        # TODO: Implement in Phase 3 with OpenCV VideoWriter
        fps = fps or self.preview_fps
        print(f"[ThumbnailGenerator] Preview video creation not yet implemented")
        print(f"  Would create {len(frame_paths)} frame video at {fps} FPS")
        return None


__all__ = ['ThumbnailGenerator']
