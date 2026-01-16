"""
Comparison Widget - Side-by-side video comparison with synchronized playback

Uses CompareVideoColumn for each version, showing:
- Video with read-only drawover annotations
- Version label and status
- Frame ruler timeline with note markers
- Compact notes panel

Shared controls at bottom sync both videos.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import cv2

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QStyleOptionSlider, QStyle
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QMouseEvent, QKeyEvent

from ..compare_video_column import CompareVideoColumn
from ...utils.icon_loader import IconLoader
from ...utils.icon_utils import colorize_white_svg
from ...themes.theme_manager import get_theme_manager


class ClickableSlider(QSlider):
    """Slider that jumps to click position instead of stepping."""

    def mousePressEvent(self, event: QMouseEvent):
        """Jump to click position on mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Calculate value from click position
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)

            groove_rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_Slider, opt,
                QStyle.SubControl.SC_SliderGroove, self
            )
            handle_rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_Slider, opt,
                QStyle.SubControl.SC_SliderHandle, self
            )

            if self.orientation() == Qt.Orientation.Horizontal:
                slider_length = handle_rect.width()
                slider_min = groove_rect.x()
                slider_max = groove_rect.right() - slider_length + 1
                pos = event.position().x()
            else:
                slider_length = handle_rect.height()
                slider_min = groove_rect.y()
                slider_max = groove_rect.bottom() - slider_length + 1
                pos = event.position().y()

            # Calculate and set new value
            if slider_max != slider_min:
                value = QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(),
                    int(pos - slider_min), slider_max - slider_min,
                    opt.upsideDown
                )
                self.setValue(value)

        super().mousePressEvent(event)


class ComparisonWidget(QWidget):
    """
    Side-by-side video comparison widget with synchronized playback.

    Features:
    - Two CompareVideoColumn widgets with video, timeline, and notes
    - Shared progress slider that syncs both videos
    - Shared play/pause and loop controls
    - Read-only annotation display for each version
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._version_a: Optional[Dict[str, Any]] = None
        self._version_b: Optional[Dict[str, Any]] = None
        self._notes_a: List[Dict] = []
        self._notes_b: List[Dict] = []

        # Playback state
        self._is_playing = False
        self._is_seeking = False
        self._loop_enabled = True
        self._current_frame = 0
        self._total_frames = 0

        # Sync timer for frame updates
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._sync_frame_update)
        self._fps = 24

        # Playback speed
        self._playback_speed = 1.0

        self._load_icons()
        self._build_ui()
        self._connect_signals()

        # Enable keyboard focus for shortcuts
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _load_icons(self):
        """Load media control icons."""
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#e0e0e0"

        self._play_icon = colorize_white_svg(IconLoader.get("play"), icon_color)
        self._pause_icon = colorize_white_svg(IconLoader.get("pause"), icon_color)
        self._loop_icon = colorize_white_svg(IconLoader.get("loop"), icon_color)

    def _build_ui(self):
        """Build the comparison UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Two columns side by side
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(16)

        # Column A
        self._column_a = CompareVideoColumn()
        columns_layout.addWidget(self._column_a, 1)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet("color: #404040;")
        columns_layout.addWidget(separator)

        # Column B
        self._column_b = CompareVideoColumn()
        columns_layout.addWidget(self._column_b, 1)

        layout.addLayout(columns_layout, 1)

        # Shared controls at bottom
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        controls_layout.setContentsMargins(0, 8, 0, 0)

        # Play/Pause button
        self._play_btn = QPushButton()
        self._play_btn.setIcon(self._play_icon)
        self._play_btn.setIconSize(QSize(24, 24))
        self._play_btn.setFixedSize(40, 40)
        self._play_btn.setToolTip("Play/Pause (synced)")
        self._play_btn.setStyleSheet("""
            QPushButton {
                background: #2d2d2d;
                border: 1px solid #444;
                border-radius: 0;
            }
            QPushButton:hover {
                background: #3a3a3a;
            }
        """)
        self._play_btn.clicked.connect(self._toggle_playback)
        controls_layout.addWidget(self._play_btn)

        # Loop button
        self._loop_btn = QPushButton()
        self._loop_btn.setIcon(self._loop_icon)
        self._loop_btn.setIconSize(QSize(24, 24))
        self._loop_btn.setFixedSize(40, 40)
        self._loop_btn.setCheckable(True)
        self._loop_btn.setChecked(True)
        self._loop_btn.setToolTip("Toggle loop")
        self._loop_btn.clicked.connect(self._toggle_loop)
        self._loop_btn.setStyleSheet("""
            QPushButton {
                background: #2d2d2d;
                border: 1px solid #444;
                border-radius: 0;
            }
            QPushButton:hover {
                background: #3a3a3a;
            }
            QPushButton:checked {
                background-color: rgba(58, 143, 183, 0.5);
                border: 1px solid #3A8FB7;
            }
        """)
        controls_layout.addWidget(self._loop_btn)

        # Speed button
        self._speed_btn = QPushButton("1x")
        self._speed_btn.setFixedSize(60, 40)
        self._speed_btn.setToolTip("Playback speed (click to cycle)")
        self._speed_btn.clicked.connect(self._cycle_speed)
        self._speed_btn.setStyleSheet("""
            QPushButton {
                background: #2d2d2d;
                border: 1px solid #444;
                border-radius: 0;
                font-size: 11px;
                font-weight: bold;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background: #3a3a3a;
            }
        """)
        controls_layout.addWidget(self._speed_btn)

        # Progress slider (sharp style to match main preview)
        self._progress_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setMinimum(0)
        self._progress_slider.setMaximum(1000)
        self._progress_slider.setValue(0)
        self._progress_slider.setFixedHeight(32)
        self._progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #3a3a3a;
                height: 32px;
            }
            QSlider::sub-page:horizontal {
                background: #FF5722;
                height: 32px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #888;
                width: 10px;
                height: 32px;
                margin: 0;
            }
            QSlider::handle:horizontal:hover {
                background: #f0f0f0;
                border: 1px solid #666;
            }
        """)
        self._progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self._progress_slider.sliderReleased.connect(self._on_slider_released)
        self._progress_slider.sliderMoved.connect(self._on_slider_moved)
        self._progress_slider.valueChanged.connect(self._on_slider_value_changed)
        controls_layout.addWidget(self._progress_slider, 1)

        # Frame counter
        self._frame_label = QLabel("0 / 0")
        self._frame_label.setStyleSheet("font-size: 12px; color: #888; min-width: 80px;")
        self._frame_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        controls_layout.addWidget(self._frame_label)

        layout.addLayout(controls_layout)

    def _connect_signals(self):
        """Connect column signals for sync."""
        self._column_a.frame_clicked.connect(self._on_column_frame_clicked)
        self._column_b.frame_clicked.connect(self._on_column_frame_clicked)

    def set_versions(
        self,
        version_a: Dict[str, Any],
        version_b: Dict[str, Any],
        notes_a: List[Dict] = None,
        notes_b: List[Dict] = None
    ):
        """
        Set the two versions to compare.

        Args:
            version_a: First version data dict
            version_b: Second version data dict
            notes_a: Optional notes for version A
            notes_b: Optional notes for version B
        """
        self._version_a = version_a
        self._version_b = version_b
        self._notes_a = notes_a or []
        self._notes_b = notes_b or []

        # Stop any current playback
        self._stop_playback()

        # Set up columns
        self._column_a.set_version(version_a, self._notes_a)
        self._column_b.set_version(version_b, self._notes_b)

        # Calculate total frames from longest video
        self._fps = max(self._column_a.fps, self._column_b.fps, 24)
        self._total_frames = max(self._column_a.total_frames, self._column_b.total_frames)

        # Reset state
        self._current_frame = 0
        self._progress_slider.setValue(0)
        self._frame_label.setText(f"0 / {self._total_frames}")

        # Sync both columns to frame 0 and load initial annotations
        self._column_a.set_current_frame(0, load_drawover=True)
        self._column_b.set_current_frame(0, load_drawover=True)

    def _on_column_frame_clicked(self, frame: int):
        """Handle frame click from either column - sync both."""
        self._seek_both(frame)

    def _toggle_playback(self):
        """Toggle play/pause for both videos."""
        if self._is_playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        """Start synced playback."""
        if self._total_frames == 0:
            return

        self._is_playing = True
        self._play_btn.setIcon(self._pause_icon)

        # Start sync timer with speed adjustment
        frame_interval = int(1000 / (self._fps * self._playback_speed))
        self._sync_timer.start(frame_interval)

    def _stop_playback(self):
        """Stop synced playback."""
        self._sync_timer.stop()
        self._is_playing = False
        self._play_btn.setIcon(self._play_icon)

        # Load annotations for current frame now that playback stopped
        self._column_a.set_current_frame(self._current_frame, load_drawover=True)
        self._column_b.set_current_frame(self._current_frame, load_drawover=True)

    def _sync_frame_update(self):
        """Update both videos in sync."""
        self._current_frame += 1

        # Check if we've reached the end of the longest video
        if self._current_frame >= self._total_frames:
            if self._loop_enabled:
                self._seek_both(0)
            else:
                self._stop_playback()
            return

        # Update both columns' internal video widgets
        video_a = self._column_a.video_widget
        video_b = self._column_b.video_widget

        # Update video A - stay on last frame if shorter
        if video_a._cv_cap and self._current_frame < self._column_a.total_frames:
            video_a._show_current_frame()
            video_a._cv_frame_count += 1

        # Update video B - stay on last frame if shorter
        if video_b._cv_cap and self._current_frame < self._column_b.total_frames:
            video_b._show_current_frame()
            video_b._cv_frame_count += 1

        # Update playhead positions on both timelines
        self._column_a.set_current_frame(self._current_frame)
        self._column_b.set_current_frame(self._current_frame)

        # Update slider
        if not self._is_seeking and self._total_frames > 0:
            progress = int((self._current_frame / self._total_frames) * 1000)
            self._progress_slider.setValue(progress)
            self._frame_label.setText(f"{self._current_frame} / {self._total_frames}")

    def _toggle_loop(self):
        """Toggle loop mode."""
        self._loop_enabled = self._loop_btn.isChecked()

    def _on_slider_pressed(self):
        """Handle slider drag start."""
        self._is_seeking = True
        self._stop_playback()

    def _on_slider_released(self):
        """Handle slider drag end."""
        self._is_seeking = False
        self._seek_to_slider_position()

    def _on_slider_moved(self, value: int):
        """Handle slider movement during drag."""
        if self._is_seeking:
            self._seek_to_slider_position()

    def _on_slider_value_changed(self, value: int):
        """Handle slider value change (includes click-to-position)."""
        # Only respond if not playing and not already in seeking mode
        # This catches click-on-track events that don't trigger sliderPressed
        if not self._is_playing and not self._is_seeking:
            self._seek_to_slider_position()

    def _seek_to_slider_position(self):
        """Seek both videos to current slider position."""
        value = self._progress_slider.value()
        if self._total_frames > 0:
            target_frame = int((value / 1000) * self._total_frames)
            self._seek_both(target_frame)

    def _seek_both(self, frame: int):
        """Seek both videos to the same frame (clamped to each video's length)."""
        self._current_frame = frame

        # Seek both columns (they handle clamping internally)
        self._column_a.seek_to_frame(frame)
        self._column_b.seek_to_frame(frame)

        # Update slider and frame label (block signals to prevent infinite loop)
        # Don't update slider during seeking - user is controlling it via drag
        if not self._is_seeking:
            self._progress_slider.blockSignals(True)
            if self._total_frames > 0:
                progress = int((frame / self._total_frames) * 1000)
                self._progress_slider.setValue(progress)
            self._progress_slider.blockSignals(False)
        self._frame_label.setText(f"{frame} / {self._total_frames}")

    def _cycle_speed(self):
        """Cycle through playback speeds."""
        speeds = [0.25, 0.5, 1.0, 2.0]
        try:
            current_idx = speeds.index(self._playback_speed)
        except ValueError:
            current_idx = 2  # Default to 1.0
        next_idx = (current_idx + 1) % len(speeds)
        self._playback_speed = speeds[next_idx]
        # Format: "2x" for whole numbers, "0.5x" for decimals
        speed = self._playback_speed
        speed_text = f"{int(speed)}x" if speed == int(speed) else f"{speed}x"
        self._speed_btn.setText(speed_text)

        # Update timer if playing
        if self._is_playing:
            self._sync_timer.stop()
            frame_interval = int(1000 / (self._fps * self._playback_speed))
            self._sync_timer.start(frame_interval)

    def step_forward(self):
        """Step forward one frame."""
        if self._total_frames > 0 and self._current_frame < self._total_frames - 1:
            self._stop_playback()
            self._seek_both(self._current_frame + 1)

    def step_backward(self):
        """Step backward one frame."""
        if self._total_frames > 0 and self._current_frame > 0:
            self._stop_playback()
            self._seek_both(self._current_frame - 1)

    def keyPressEvent(self, event: QKeyEvent):
        """
        Handle playback keyboard shortcuts.

        K = pause
        L = forward play
        Left arrow = step back 1 frame
        Right arrow = step forward 1 frame
        Space = toggle play/pause
        """
        key = event.key()

        # K = Pause
        if key == Qt.Key.Key_K:
            self._stop_playback()
            event.accept()
            return

        # L = Forward play
        if key == Qt.Key.Key_L:
            self._start_playback()
            event.accept()
            return

        # Space = Toggle play/pause
        if key == Qt.Key.Key_Space:
            self._toggle_playback()
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

    def clear(self):
        """Clear both columns."""
        self._stop_playback()
        self._column_a.clear()
        self._column_b.clear()
        self._current_frame = 0
        self._total_frames = 0
        self._progress_slider.setValue(0)
        self._frame_label.setText("0 / 0")


__all__ = ['ComparisonWidget']
