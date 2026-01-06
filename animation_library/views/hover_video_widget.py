"""
HoverVideoWidget - Preview video playback on hover

Pattern: QWidget with OpenCV video playback
Inspired by: Current animation_library hover preview
"""

import cv2
from pathlib import Path
from typing import Optional, Tuple
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QPoint
from PyQt6.QtGui import QImage, QPixmap, QPainter

from ..config import Config
from ..utils.gradient_utils import composite_image_on_gradient_colors
from ..themes.theme_manager import get_theme_manager


class HoverVideoWidget(QWidget):
    """
    Popup widget for playing preview videos on hover

    Features:
    - OpenCV video playback
    - Looping playback
    - Gradient compositing
    - Automatic resource cleanup
    - Positioning near cursor

    Usage:
        widget = HoverVideoWidget()
        widget.play_video(video_path, position)
        widget.stop()
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Video playback
        self._video_capture: Optional[cv2.VideoCapture] = None
        self._playback_timer = QTimer(self)
        self._playback_timer.timeout.connect(self._update_frame)
        self._current_video_path: Optional[Path] = None

        # Gradient colors
        self._gradient_top: Optional[Tuple[float, float, float]] = None
        self._gradient_bottom: Optional[Tuple[float, float, float]] = None

        # Theme
        self._theme_manager = get_theme_manager()

        # Setup UI
        self._setup_ui()

        # Window flags
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

    def _setup_ui(self):
        """Setup UI components"""

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Label for video frames
        self._video_label = QLabel()
        self._video_label.setScaledContents(False)
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._video_label)

        # Set default size
        self.setFixedSize(Config.THUMBNAIL_SIZE, Config.THUMBNAIL_SIZE)

    def play_video(
        self,
        video_path: Path,
        position: QPoint,
        gradient_top: Optional[Tuple[float, float, float]] = None,
        gradient_bottom: Optional[Tuple[float, float, float]] = None
    ):
        """
        Start playing video

        Args:
            video_path: Path to video file
            position: Global position to display widget
            gradient_top: Top gradient color (R, G, B) 0-1
            gradient_bottom: Bottom gradient color (R, G, B) 0-1
        """
        # Stop current video
        self.stop()

        if not video_path.exists():
            print(f"[HoverVideoWidget] Video not found: {video_path}")
            return

        # Store gradient colors
        if gradient_top and gradient_bottom:
            self._gradient_top = gradient_top
            self._gradient_bottom = gradient_bottom
        else:
            # Use theme gradient
            self._gradient_top, self._gradient_bottom = self._theme_manager.get_gradient_colors()

        # Open video
        self._video_capture = cv2.VideoCapture(str(video_path))
        if not self._video_capture.isOpened():
            print(f"[HoverVideoWidget] Failed to open video: {video_path}")
            self._video_capture = None
            return

        self._current_video_path = video_path

        # Get video properties
        fps = self._video_capture.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = Config.PREVIEW_VIDEO_FPS

        # Start playback timer
        interval_ms = int(1000 / fps)
        self._playback_timer.start(interval_ms)

        # Position widget near cursor (offset to not block)
        offset_x = 20
        offset_y = 20
        self.move(position.x() + offset_x, position.y() + offset_y)

        # Show widget
        self.show()
        self.raise_()

    def stop(self):
        """Stop playback and cleanup"""

        self._playback_timer.stop()

        if self._video_capture:
            self._video_capture.release()
            self._video_capture = None

        self._current_video_path = None
        self.hide()

    def _update_frame(self):
        """Update to next frame"""

        if not self._video_capture:
            return

        # Read frame
        ret, frame = self._video_capture.read()

        if not ret:
            # End of video - loop back to start
            self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._video_capture.read()

            if not ret:
                # Failed to loop
                self.stop()
                return

        # Convert frame to QImage
        qimage = self._opencv_to_qimage(frame)
        if not qimage:
            return

        # Composite on gradient
        if self._gradient_top and self._gradient_bottom:
            composited = composite_image_on_gradient_colors(
                qimage,
                self._gradient_top,
                self._gradient_bottom,
                Config.THUMBNAIL_SIZE
            )
            pixmap = QPixmap.fromImage(composited)
        else:
            pixmap = QPixmap.fromImage(qimage)

        # Display frame
        self._video_label.setPixmap(pixmap)

    def _opencv_to_qimage(self, cv_image) -> Optional[QImage]:
        """
        Convert OpenCV image to QImage

        Args:
            cv_image: OpenCV image (numpy array)

        Returns:
            QImage or None
        """
        try:
            # OpenCV uses BGR, convert to RGB
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

            height, width, channels = rgb_image.shape
            bytes_per_line = channels * width

            qimage = QImage(
                rgb_image.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_RGB888
            )

            # Make a copy so numpy array can be garbage collected
            return qimage.copy()

        except Exception as e:
            print(f"[HoverVideoWidget] Error converting frame: {e}")
            return None

    def closeEvent(self, event):
        """Handle widget close"""
        self.stop()
        super().closeEvent(event)

    def hideEvent(self, event):
        """Handle widget hide"""
        self.stop()
        super().hideEvent(event)


__all__ = ['HoverVideoWidget']
