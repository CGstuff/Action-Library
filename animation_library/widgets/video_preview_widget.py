"""
VideoPreviewWidget - Self-contained video preview with playback controls

Extracts video playback logic from MetadataPanel for better separation of concerns.
"""

from typing import Optional
from pathlib import Path
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QSlider,
    QHBoxLayout, QStyle, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QKeyEvent

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
    playback_speed_changed = pyqtSignal(float)  # Speed multiplier

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
        self._size_locked = False  # Once True, don't recalculate size on each frame
        self._locked_size = None  # (width, height) when locked

        # Playback speed and direction
        self._playback_speed = 1.0  # Speed multiplier: 0.25, 0.5, 1.0, 2.0
        self._reverse_playback = False  # True for reverse direction (J key)

        # Load icons
        self._load_icons()

        # Setup UI
        self._create_widgets()
        self._create_layout()

        # Connect to theme changes
        theme_manager = get_theme_manager()
        theme_manager.theme_changed.connect(self._on_theme_changed)

        # Enable keyboard focus for shortcuts
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _load_icons(self):
        """Load media control icons with theme colors."""
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#1a1a1a"

        self._play_icon = colorize_white_svg(IconLoader.get("play"), icon_color)
        self._pause_icon = colorize_white_svg(IconLoader.get("pause"), icon_color)
        self._loop_icon = colorize_white_svg(IconLoader.get("loop"), icon_color)

    def _create_widgets(self):
        """Create preview widgets."""
        # Video display label - sizes itself to exactly match video content
        self._video_label = QLabel()
        self._video_label.setMinimumSize(100, 100)
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setStyleSheet("background-color: transparent;")  # Transparent - no letterboxing
        self._video_label.setText("No preview loaded")
        # Use Preferred policy so it can be sized to match video exactly
        self._video_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred
        )

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

        # Speed button - cycles through playback speeds
        self._speed_button = QPushButton("1x")
        self._speed_button.setFixedSize(60, 36)
        self._speed_button.setProperty("media", "true")
        self._speed_button.setEnabled(False)
        self._speed_button.setToolTip("Playback speed (click to cycle)")
        self._speed_button.clicked.connect(self._cycle_speed)
        self._speed_button.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                color: #e0e0e0;
            }
        """)

        # Progress slider with playhead styling
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

        # Style the slider as a timeline with visible playhead
        self._progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #3a3a3a;
                height: 32px;
            }
            QSlider::sub-page:horizontal {
                background: #3A8FB7;
                height: 32px;
            }
            QSlider::handle:horizontal {
                background: #e0e0e0;
                width: 2px;
                height: 32px;
                margin: 0;
            }
            QSlider::handle:horizontal:disabled {
                background: #555555;
            }
        """)

    def _create_layout(self):
        """Create widget layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Video display - centered in its container
        layout.addWidget(self._video_label, 1, Qt.AlignmentFlag.AlignCenter)

        # Control buttons row in a container widget (so it can be hidden)
        self._controls_widget = QWidget()
        controls_layout = QHBoxLayout(self._controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(2)
        controls_layout.addWidget(self._play_pause_button)
        controls_layout.addWidget(self._loop_button)
        controls_layout.addWidget(self._speed_button)
        controls_layout.addWidget(self._progress_slider)

        layout.addWidget(self._controls_widget)

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

        # Reset size lock for new video
        self._size_locked = False
        self._locked_size = None

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
        self._size_locked = False
        self._locked_size = None

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
        Seek to specific frame using timestamp-based seeking for accuracy.

        Args:
            frame: Target frame number
        """
        if self._cv_cap and 0 <= frame < self._cv_total_frames:
            # Use timestamp-based seeking for better accuracy with compressed video
            # CAP_PROP_POS_FRAMES is unreliable with H.264 and other codecs
            if self._cv_fps > 0:
                target_ms = (frame / self._cv_fps) * 1000.0
                self._cv_cap.set(cv2.CAP_PROP_POS_MSEC, target_ms)
            else:
                self._cv_cap.set(cv2.CAP_PROP_POS_FRAMES, frame)

            # Verify and adjust frame position after seek
            actual_pos = int(self._cv_cap.get(cv2.CAP_PROP_POS_FRAMES))

            # If we're not at the target, step forward to reach it
            # (keyframe seeking may land us before the target)
            while actual_pos < frame and actual_pos < self._cv_total_frames - 1:
                ret = self._cv_cap.grab()  # grab() is faster than read()
                if not ret:
                    break
                actual_pos += 1

            self._cv_frame_count = frame
            self._show_current_frame()
            self._update_slider_position()
            self.frame_changed.emit(frame)

    def hide_controls(self):
        """Hide the built-in controls row (when using external timeline)."""
        self._controls_widget.hide()

    def show_controls(self):
        """Show the built-in controls row."""
        self._controls_widget.show()

    def hide_progress_slider(self):
        """Hide just the progress slider (keep play/loop buttons)."""
        self._progress_slider.hide()

    def show_progress_slider(self):
        """Show the progress slider."""
        self._progress_slider.show()

    def set_loop(self, enabled: bool):
        """
        Set loop mode.

        Args:
            enabled: True to enable looping
        """
        self._loop_button.setChecked(enabled)

    def set_playback_speed(self, speed: float):
        """
        Set playback speed multiplier.

        Args:
            speed: Speed multiplier (0.25, 0.5, 1.0, 2.0)
        """
        self._playback_speed = speed
        # Format: "2x" for whole numbers, "0.5x" for decimals
        speed_text = f"{int(speed)}x" if speed == int(speed) else f"{speed}x"
        self._speed_button.setText(speed_text)

        # Update timer if currently playing
        if self._is_playing:
            self._cv_timer.stop()
            frame_interval = int(1000 / (self._cv_fps * self._playback_speed))
            self._cv_timer.start(frame_interval)

        self.playback_speed_changed.emit(speed)

    def step_forward(self):
        """Step forward one frame."""
        if self._cv_cap and self._cv_frame_count < self._cv_total_frames - 1:
            self.pause()
            self.seek_to_frame(self._cv_frame_count + 1)

    def step_backward(self):
        """Step backward one frame."""
        if self._cv_cap and self._cv_frame_count > 0:
            self.pause()
            self.seek_to_frame(self._cv_frame_count - 1)

    def unlock_size(self):
        """Unlock size to allow recalculation on next frame display."""
        self._size_locked = False
        self._locked_size = None

    def recalculate_size(self):
        """Unlock size and refresh the current frame to recalculate."""
        self.unlock_size()
        if self._cv_cap and self._cv_cap.isOpened():
            # Re-seek to current position to refresh display
            current = self._cv_frame_count
            self._cv_cap.set(cv2.CAP_PROP_POS_FRAMES, current)
            self._show_current_frame()

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

    @property
    def playback_speed(self) -> float:
        """Get current playback speed multiplier."""
        return self._playback_speed

    @property
    def video_label(self) -> QLabel:
        """Get the video display label widget."""
        return self._video_label

    def get_video_display_rect(self):
        """
        Get the actual video content rect within the label (excluding letterbox bars).

        Returns:
            QRect of the video content area in label coordinates, or None if no video
        """
        from PyQt6.QtCore import QRect

        if not self._cv_cap or not self._cv_cap.isOpened():
            return None

        pixmap = self._video_label.pixmap()
        if pixmap is None or pixmap.isNull():
            return None

        # Get label and pixmap sizes
        label_w = self._video_label.width()
        label_h = self._video_label.height()
        pixmap_w = pixmap.width()
        pixmap_h = pixmap.height()

        # Calculate offset (pixmap is centered in label)
        x_offset = (label_w - pixmap_w) // 2
        y_offset = (label_h - pixmap_h) // 2

        return QRect(x_offset, y_offset, pixmap_w, pixmap_h)

    def get_video_native_size(self):
        """
        Get the native video resolution.

        Returns:
            Tuple of (width, height) or None if no video loaded
        """
        if not self._cv_cap or not self._cv_cap.isOpened():
            return None

        width = int(self._cv_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cv_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (width, height)

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
        video_aspect = w / h

        # Convert OpenCV BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert to QImage
        bytes_per_line = 3 * w
        qt_frame = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

        # Convert to QPixmap
        pixmap = QPixmap.fromImage(qt_frame.copy())

        # Use locked size if available, otherwise calculate
        if self._size_locked and self._locked_size:
            new_w, new_h = self._locked_size
        else:
            # Get available space from the widget itself
            # Use our own size as the constraint, minus space for controls if visible
            available_w = self.width()
            available_h = self.height()

            # Subtract controls height if controls are visible
            if self._controls_widget.isVisible():
                available_h -= self._controls_widget.height() + 8  # 8 for spacing

            # Ensure we have valid dimensions (fallback to reasonable defaults)
            if available_w <= 100:
                available_w = 640
            if available_h <= 100:
                available_h = 480

            # Calculate size maintaining aspect ratio
            container_aspect = available_w / available_h

            if container_aspect > video_aspect:
                # Container is wider than video - height constrained
                new_h = available_h
                new_w = int(new_h * video_aspect)
            else:
                # Container is taller than video - width constrained
                new_w = available_w
                new_h = int(new_w / video_aspect)

            # Lock the size after first calculation
            if not self._size_locked:
                self._locked_size = (new_w, new_h)
                self._size_locked = True

        # Scale the pixmap
        scaled = pixmap.scaled(
            new_w, new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Resize label to exactly fit the scaled video (no black bars)
        self._video_label.setFixedSize(new_w, new_h)
        self._video_label.setPixmap(scaled)
        return True

    def _update_video_frame(self):
        """Timer callback to update frame during playback."""
        if self._reverse_playback:
            # Reverse playback - step backwards
            self._cv_frame_count -= 1
            if self._cv_frame_count < 0:
                if self._loop_button.isChecked():
                    self._cv_frame_count = self._cv_total_frames - 1
                else:
                    self._stop_playback()
                    return
            self.seek_to_frame(self._cv_frame_count)
        else:
            # Forward playback
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

        # Check if at end of video (for forward playback)
        if not self._reverse_playback and self._cv_frame_count >= self._cv_total_frames - 1:
            # Restart from beginning
            self._cv_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._cv_frame_count = 0

        # Check if at start (for reverse playback)
        if self._reverse_playback and self._cv_frame_count <= 0:
            # Start from end
            self._cv_frame_count = self._cv_total_frames - 1
            self.seek_to_frame(self._cv_frame_count)

        # Start playback timer with speed adjustment
        frame_interval = int(1000 / (self._cv_fps * self._playback_speed))
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
        self._speed_button.setEnabled(True)
        self._progress_slider.setEnabled(True)

    def _disable_controls(self):
        """Disable video controls."""
        self._play_pause_button.setEnabled(False)
        self._loop_button.setEnabled(False)
        self._speed_button.setEnabled(False)
        self._progress_slider.setEnabled(False)
        self._progress_slider.setValue(0)

    def _cycle_speed(self):
        """Cycle through playback speeds."""
        speeds = [0.25, 0.5, 1.0, 2.0]
        try:
            current_idx = speeds.index(self._playback_speed)
        except ValueError:
            current_idx = 2  # Default to 1.0
        next_idx = (current_idx + 1) % len(speeds)
        self.set_playback_speed(speeds[next_idx])

    def _cleanup_video(self):
        """Release video resources."""
        if self._cv_cap:
            self._cv_timer.stop()
            self._cv_cap.release()
            self._cv_cap = None
        self._is_playing = False

    def closeEvent(self, event):
        """
        Handle widget close - stop timer and release video resources.

        This prevents crashes when timer tries to update a deleted widget.
        """
        # Stop timer first to prevent callbacks during cleanup
        self._cv_timer.stop()

        # Cleanup video resources
        self._cleanup_video()

        # Disconnect theme signal to prevent callbacks after widget is deleted
        try:
            theme_manager = get_theme_manager()
            theme_manager.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            # Already disconnected or theme manager gone
            pass

        super().closeEvent(event)

    def _on_theme_changed(self, theme_name: str):
        """Reload icons when theme changes."""
        self._load_icons()

        # Update current button icon
        if self._is_playing:
            self._play_pause_button.setIcon(self._pause_icon)
        else:
            self._play_pause_button.setIcon(self._play_icon)

        self._loop_button.setIcon(self._loop_icon)

    def keyPressEvent(self, event: QKeyEvent):
        """
        Handle playback keyboard shortcuts.

        J = reverse play
        K = pause
        L = forward play
        Left arrow = step back 1 frame
        Right arrow = step forward 1 frame
        Space = toggle play/pause
        """
        key = event.key()

        # J = Reverse play
        if key == Qt.Key.Key_J:
            self._reverse_playback = True
            self.play()
            event.accept()
            return

        # K = Pause
        if key == Qt.Key.Key_K:
            self.pause()
            event.accept()
            return

        # L = Forward play
        if key == Qt.Key.Key_L:
            self._reverse_playback = False
            self.play()
            event.accept()
            return

        # Space = Toggle play/pause
        if key == Qt.Key.Key_Space:
            self.toggle_playback()
            event.accept()
            return

        # Left arrow = Step back 1 frame
        if key == Qt.Key.Key_Left:
            self.step_backward()
            event.accept()
            return

        # Right arrow = Step forward 1 frame
        if key == Qt.Key.Key_Right:
            self.step_forward()
            event.accept()
            return

        super().keyPressEvent(event)


__all__ = ['VideoPreviewWidget']
