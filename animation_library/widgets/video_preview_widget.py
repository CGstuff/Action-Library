"""
VideoPreviewWidget - Self-contained video preview with playback controls

Extracts video playback logic from MetadataPanel for better separation of concerns.
"""

from typing import Optional
from pathlib import Path
import cv2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QSlider,
    QHBoxLayout, QStyle
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from ..themes.theme_manager import get_theme_manager
from ..utils.icon_loader import IconLoader
from ..utils.icon_utils import colorize_white_svg


class VideoPreviewWidget(QWidget):
    """
    Self-contained video preview widget with playback controls.

    Features:
    - Video loading and display
    - Play/pause toggle
    - Loop toggle
    - Progress slider with seek
    - Theme-aware icons

    Signals:
        frame_changed(int): Emitted when current frame changes
        playback_state_changed(bool): Emitted when playing state changes
    """

    frame_changed = pyqtSignal(int)  # Current frame number
    playback_state_changed = pyqtSignal(bool)  # Is playing

    def __init__(self, parent=None):
        super().__init__(parent)

        # Video capture state
        self._cv_cap: Optional[cv2.VideoCapture] = None
        self._cv_timer = QTimer(self)
        self._cv_timer.timeout.connect(self._update_video_frame)
        self._cv_fps = 24
        self._cv_frame_count = 0
        self._cv_total_frames = 0
        self._is_playing = False
        self._is_seeking = False
        self._current_video_path: Optional[str] = None

        # Load icons
        self._load_icons()

        # Setup UI
        self._create_widgets()
        self._create_layout()

        # Connect to theme changes
        theme_manager = get_theme_manager()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _load_icons(self):
        """Load media control icons with theme colors."""
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#1a1a1a"

        self._play_icon = colorize_white_svg(IconLoader.get("play"), icon_color)
        self._pause_icon = colorize_white_svg(IconLoader.get("pause"), icon_color)
        self._loop_icon = colorize_white_svg(IconLoader.get("loop"), icon_color)

    def _create_widgets(self):
        """Create preview widgets."""
        # Video display label (350px height)
        self._video_label = QLabel()
        self._video_label.setFixedHeight(350)
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setStyleSheet("background-color: #000000;")
        self._video_label.setText("No preview loaded")

        # Play/Pause toggle button
        self._play_pause_button = QPushButton()
        self._play_pause_button.setIcon(self._play_icon)
        self._play_pause_button.setIconSize(QSize(24, 24))
        self._play_pause_button.setFixedSize(36, 36)
        self._play_pause_button.setProperty("media", "true")
        self._play_pause_button.setEnabled(False)
        self._play_pause_button.setToolTip("Play/Pause preview")
        self._play_pause_button.clicked.connect(self._toggle_playback)

        # Loop toggle button
        self._loop_button = QPushButton()
        self._loop_button.setIcon(self._loop_icon)
        self._loop_button.setIconSize(QSize(24, 24))
        self._loop_button.setFixedSize(36, 36)
        self._loop_button.setProperty("media", "true")
        self._loop_button.setCheckable(True)
        self._loop_button.setChecked(True)  # Default: loop enabled
        self._loop_button.setEnabled(False)
        self._loop_button.setToolTip("Toggle loop playback")
        self._loop_button.setStyleSheet("""
            QPushButton:checked {
                background-color: rgba(255, 255, 255, 0.35);
            }
        """)

        # Progress slider
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setProperty("progress", "true")
        self._progress_slider.setFixedHeight(32)
        self._progress_slider.setMinimum(0)
        self._progress_slider.setMaximum(1000)
        self._progress_slider.setValue(0)
        self._progress_slider.setEnabled(False)
        self._progress_slider.setToolTip("Seek preview timeline")
        self._progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self._progress_slider.sliderReleased.connect(self._on_slider_released)
        self._progress_slider.mousePressEvent = self._progress_slider_mouse_press

    def _create_layout(self):
        """Create widget layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Video display
        layout.addWidget(self._video_label)

        # Control buttons row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(2)
        controls_layout.addWidget(self._play_pause_button)
        controls_layout.addWidget(self._loop_button)
        controls_layout.addWidget(self._progress_slider)

        layout.addLayout(controls_layout)

    # ==================== PUBLIC API ====================

    def load_video(self, video_path: str) -> bool:
        """
        Load video file for preview.

        Args:
            video_path: Path to video file

        Returns:
            True if loaded successfully
        """
        # Release previous video
        self._cleanup_video()

        # Check if file exists
        if not Path(video_path).exists():
            self._video_label.setText("Preview not found")
            self._disable_controls()
            return False

        # Open video
        self._cv_cap = cv2.VideoCapture(video_path)
        if not self._cv_cap.isOpened():
            self._video_label.setText("Failed to load preview")
            self._disable_controls()
            return False

        # Store path
        self._current_video_path = video_path

        # Get video properties
        self._cv_fps = self._cv_cap.get(cv2.CAP_PROP_FPS) or 24
        self._cv_total_frames = int(self._cv_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._cv_frame_count = 0

        # Show first frame
        if self._show_current_frame():
            self._enable_controls()
            return True
        else:
            self._video_label.setText("Failed to read video")
            self._disable_controls()
            return False

    def clear(self):
        """Clear video and reset state."""
        self._cleanup_video()
        self._video_label.clear()
        self._video_label.setText("No preview loaded")
        self._disable_controls()
        self._current_video_path = None

    def play(self):
        """Start video playback."""
        if not self._is_playing and self._cv_cap:
            self._start_playback()

    def pause(self):
        """Pause video playback."""
        if self._is_playing:
            self._stop_playback()

    def toggle_playback(self):
        """Toggle play/pause state."""
        self._toggle_playback()

    def seek_to_frame(self, frame: int):
        """
        Seek to specific frame.

        Args:
            frame: Target frame number
        """
        if self._cv_cap and 0 <= frame < self._cv_total_frames:
            self._cv_cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            self._cv_frame_count = frame
            self._show_current_frame()
            self._update_slider_position()

    def set_loop(self, enabled: bool):
        """
        Set loop mode.

        Args:
            enabled: True to enable looping
        """
        self._loop_button.setChecked(enabled)

    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._is_playing

    @property
    def current_frame(self) -> int:
        """Get current frame number."""
        return self._cv_frame_count

    @property
    def total_frames(self) -> int:
        """Get total frame count."""
        return self._cv_total_frames

    @property
    def fps(self) -> float:
        """Get video FPS."""
        return self._cv_fps

    # ==================== INTERNAL METHODS ====================

    def _show_current_frame(self) -> bool:
        """Display current video frame."""
        if not self._cv_cap or not self._cv_cap.isOpened():
            return False

        ret, frame = self._cv_cap.read()
        if not ret:
            return False

        # Get frame dimensions
        h, w = frame.shape[:2]

        # Convert OpenCV BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert to QImage
        bytes_per_line = 3 * w
        qt_frame = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

        # Convert to QPixmap
        pixmap = QPixmap.fromImage(qt_frame.copy())

        # Scale to fit label while preserving aspect ratio
        scaled = pixmap.scaled(
            self._video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self._video_label.setPixmap(scaled)
        return True

    def _update_video_frame(self):
        """Timer callback to update frame during playback."""
        if not self._show_current_frame():
            # End of video
            if self._loop_button.isChecked():
                # Loop back to start
                self._cv_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._cv_frame_count = 0
                self._show_current_frame()
            else:
                # Stop playback
                self._stop_playback()
        else:
            # Update progress
            self._cv_frame_count += 1
            self._update_slider_position()
            self.frame_changed.emit(self._cv_frame_count)

    def _update_slider_position(self):
        """Update slider to reflect current frame."""
        if not self._is_seeking and self._cv_total_frames > 0:
            progress = int((self._cv_frame_count / self._cv_total_frames) * 1000)
            self._progress_slider.setValue(progress)

    def _toggle_playback(self):
        """Toggle play/pause state."""
        if self._is_playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        """Start video playback."""
        if self._cv_cap is None:
            return

        # Check if at end of video
        if self._cv_frame_count >= self._cv_total_frames - 1:
            # Restart from beginning
            self._cv_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._cv_frame_count = 0

        # Start playback timer
        frame_interval = int(1000 / self._cv_fps)
        self._cv_timer.start(frame_interval)
        self._is_playing = True
        self._play_pause_button.setIcon(self._pause_icon)
        self.playback_state_changed.emit(True)

    def _stop_playback(self):
        """Stop video playback."""
        self._cv_timer.stop()
        self._is_playing = False
        self._play_pause_button.setIcon(self._play_icon)
        self.playback_state_changed.emit(False)

    def _on_slider_pressed(self):
        """Handle slider drag start."""
        self._is_seeking = True

    def _on_slider_released(self):
        """Handle slider drag end - seek to position."""
        self._is_seeking = False
        self._seek_to_position(self._progress_slider.value())

    def _progress_slider_mouse_press(self, event):
        """Handle mouse press on progress slider for click-to-seek."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Calculate position from click
            value = QStyle.sliderValueFromPosition(
                self._progress_slider.minimum(),
                self._progress_slider.maximum(),
                event.pos().x(),
                self._progress_slider.width()
            )
            self._progress_slider.setValue(value)
            self._seek_to_position(value)
        # Call original handler
        QSlider.mousePressEvent(self._progress_slider, event)

    def _seek_to_position(self, slider_value: int):
        """Seek video to position based on slider value."""
        if self._cv_cap and self._cv_total_frames > 0:
            target_frame = int((slider_value / 1000) * self._cv_total_frames)
            self._cv_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            self._cv_frame_count = target_frame
            self._show_current_frame()
            self.frame_changed.emit(self._cv_frame_count)

    def _enable_controls(self):
        """Enable video controls."""
        self._play_pause_button.setEnabled(True)
        self._loop_button.setEnabled(True)
        self._progress_slider.setEnabled(True)

    def _disable_controls(self):
        """Disable video controls."""
        self._play_pause_button.setEnabled(False)
        self._loop_button.setEnabled(False)
        self._progress_slider.setEnabled(False)
        self._progress_slider.setValue(0)

    def _cleanup_video(self):
        """Release video resources."""
        if self._cv_cap:
            self._cv_timer.stop()
            self._cv_cap.release()
            self._cv_cap = None
        self._is_playing = False

    def _on_theme_changed(self, theme_name: str):
        """Reload icons when theme changes."""
        self._load_icons()

        # Update current button icon
        if self._is_playing:
            self._play_pause_button.setIcon(self._pause_icon)
        else:
            self._play_pause_button.setIcon(self._play_icon)

        self._loop_button.setIcon(self._loop_icon)


__all__ = ['VideoPreviewWidget']
