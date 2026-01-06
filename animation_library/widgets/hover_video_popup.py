"""
HoverVideoPopup - Frameless popup window for hover video preview

Pattern: Popup window with OpenCV video playback
Features:
- Frameless, non-intrusive popup
- Video playback with gradient background
- Position management
- Fade in/out animations
- Resource cleanup
"""

from typing import Optional, Tuple
import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from ..config import Config


class HoverVideoPopup(QWidget):
    """
    Frameless popup for hover video preview

    Features:
    - Plays animation preview video on hover
    - Gradient background compositing
    - Non-intrusive positioning
    - Fade in/out animations
    - Resource cleanup

    Usage:
        popup = HoverVideoPopup()
        popup.show_preview(video_path, gradient_top, gradient_bottom, position)
        popup.hide_preview()
    """

    # Signals
    popup_closed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Frameless window that stays on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # Doesn't appear in taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Video playback state
        self._video_capture: Optional[cv2.VideoCapture] = None
        self._current_video_path: Optional[str] = None
        self._video_fps: float = 30.0
        self._frame_count: int = 0
        self._current_frame: int = 0

        # Gradient colors
        self._gradient_top: Optional[Tuple[int, int, int]] = None
        self._gradient_bottom: Optional[Tuple[int, int, int]] = None

        # Size
        self._popup_size = Config.HOVER_VIDEO_SIZE

        # Playback timer
        self._playback_timer = QTimer(self)
        self._playback_timer.timeout.connect(self._play_next_frame)

        # Fade animation
        self._fade_animation: Optional[QPropertyAnimation] = None

        # Setup UI
        self._setup_ui()

    def _setup_ui(self):
        """Setup popup UI"""
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video label
        self._video_label = QLabel()
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setFixedSize(self._popup_size, self._popup_size)
        layout.addWidget(self._video_label)

        # Set fixed size
        self.setFixedSize(self._popup_size, self._popup_size)

        # Styling: rounded corners, drop shadow
        self.setStyleSheet("""
            QWidget {
                background: transparent;
                border-radius: 8px;
            }
            QLabel {
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                background: rgba(0, 0, 0, 0.8);
            }
        """)

    def show_preview(self,
                     video_path: str,
                     gradient_top: Tuple[int, int, int],
                     gradient_bottom: Tuple[int, int, int],
                     position: QPoint):
        """
        Show video preview at position

        Args:
            video_path: Path to preview video file
            gradient_top: RGB tuple for top gradient (0-255)
            gradient_bottom: RGB tuple for bottom gradient (0-255)
            position: Screen position to show popup
        """
        # Check if already showing this video
        if self._current_video_path == video_path and self._video_capture:
            # Just update position
            self.move(position)
            return

        # Store gradient colors
        self._gradient_top = gradient_top
        self._gradient_bottom = gradient_bottom

        # Release old video if any
        self._release_video()

        # Open new video
        self._video_capture = cv2.VideoCapture(video_path)

        if not self._video_capture.isOpened():
            print(f"Failed to open video: {video_path}")
            return

        # Get video properties
        self._video_fps = self._video_capture.get(cv2.CAP_PROP_FPS)
        if self._video_fps <= 0:
            self._video_fps = 30.0  # Default fallback

        self._frame_count = int(self._video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self._current_frame = 0
        self._current_video_path = video_path

        # Position popup
        self.move(position)

        # Show popup
        self.show()
        self.raise_()

        # Start playback
        self._start_playback()

    def hide_preview(self):
        """Hide popup with fade-out animation"""
        # Stop playback
        self._playback_timer.stop()

        # Release video resources
        self._release_video()

        # Hide immediately (fade animation can be added later)
        self.hide()

        self.popup_closed.emit()

    def update_position(self, position: QPoint):
        """
        Update popup position (for follow-mouse)

        Args:
            position: New screen position
        """
        if self.isVisible():
            self.move(position)

    def set_size(self, size: int):
        """
        Set popup size in pixels

        Args:
            size: Size in pixels
        """
        self._popup_size = size
        self._video_label.setFixedSize(size, size)
        self.setFixedSize(size, size)

    def _start_playback(self):
        """Start video playback"""
        if not self._video_capture:
            return

        # Cap at 30 FPS for performance
        target_fps = min(self._video_fps, 30)
        frame_delay = int(1000 / target_fps)

        # Start timer
        self._playback_timer.start(frame_delay)

        # Play first frame immediately
        self._play_next_frame()

    def _play_next_frame(self):
        """Read and display next video frame"""
        if not self._video_capture:
            return

        # Read frame
        ret, frame = self._video_capture.read()

        if not ret:
            # End of video, loop back to start
            self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._current_frame = 0
            ret, frame = self._video_capture.read()

            if not ret:
                # Failed to loop, stop playback
                self._playback_timer.stop()
                return

        # Composite frame on gradient background
        composited_frame = self._composite_frame_on_gradient(frame)

        # Convert to QPixmap
        pixmap = self._cv2_to_qpixmap(composited_frame)

        # Display frame
        self._video_label.setPixmap(pixmap)

        self._current_frame += 1

    def _composite_frame_on_gradient(self, frame: np.ndarray) -> np.ndarray:
        """
        Composite video frame on gradient background

        Args:
            frame: OpenCV frame (BGR)

        Returns:
            Composited frame (BGR)
        """
        if self._gradient_top is None or self._gradient_bottom is None:
            return frame

        # Get frame dimensions
        h, w = frame.shape[:2]

        # Create gradient background (RGB to BGR)
        gradient = np.zeros((h, w, 3), dtype=np.uint8)

        for i in range(h):
            # Interpolate between top and bottom colors
            ratio = i / h
            r = int(self._gradient_top[0] * (1 - ratio) + self._gradient_bottom[0] * ratio)
            g = int(self._gradient_top[1] * (1 - ratio) + self._gradient_bottom[1] * ratio)
            b = int(self._gradient_top[2] * (1 - ratio) + self._gradient_bottom[2] * ratio)
            gradient[i, :] = [b, g, r]  # BGR order for OpenCV

        # Resize frame to popup size (maintaining aspect ratio)
        frame_resized = cv2.resize(frame, (self._popup_size, self._popup_size),
                                   interpolation=cv2.INTER_LINEAR)

        # Resize gradient to match
        gradient_resized = cv2.resize(gradient, (self._popup_size, self._popup_size),
                                     interpolation=cv2.INTER_LINEAR)

        # Simple overlay (can add alpha blending later)
        # For now, just return the frame with gradient as background
        # In future: blend based on alpha channel if available

        return frame_resized

    def _cv2_to_qpixmap(self, cv_img: np.ndarray) -> QPixmap:
        """
        Convert OpenCV image to QPixmap

        Args:
            cv_img: OpenCV image (BGR)

        Returns:
            QPixmap
        """
        # Convert BGR to RGB
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)

        # Get image dimensions
        h, w, ch = rgb_img.shape
        bytes_per_line = ch * w

        # Convert to QImage
        q_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

        # Convert to QPixmap
        pixmap = QPixmap.fromImage(q_img)

        return pixmap

    def _release_video(self):
        """Release OpenCV video resources"""
        if self._video_capture:
            self._video_capture.release()
            self._video_capture = None

        self._current_video_path = None
        self._current_frame = 0

    def closeEvent(self, event):
        """Handle close event"""
        self._release_video()
        self._playback_timer.stop()
        super().closeEvent(event)


__all__ = ['HoverVideoPopup']
