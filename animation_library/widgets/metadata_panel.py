"""
MetadataPanel - Display animation details

Pattern: QWidget with form layout
Inspired by: Current animation_library metadata display
"""

from typing import Optional, Dict, Any
import cv2
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea,
    QFrame, QGridLayout, QPushButton, QSlider, QHBoxLayout, QStyle
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QPixmap, QImage

from ..themes.theme_manager import get_theme_manager
from ..utils.icon_loader import IconLoader


class MetadataPanel(QWidget):
    """
    Panel for displaying animation metadata

    Features:
    - Animation name and description
    - Technical information (frames, FPS, duration)
    - Rig information
    - Tags display
    - File paths
    - Timestamps

    Layout:
        ┌─────────────────┐
        │  Animation Name │
        │  Description    │
        ├─────────────────┤
        │  Technical Info │
        │  - Frames       │
        │  - FPS          │
        │  - Duration     │
        ├─────────────────┤
        │  Rig Info       │
        │  - Type         │
        │  - Armature     │
        │  - Bone Count   │
        ├─────────────────┤
        │  Tags           │
        │  [tag1] [tag2]  │
        └─────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Current animation
        self._animation: Optional[Dict[str, Any]] = None

        # Load media control icons
        theme = get_theme_manager().get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#1a1a1a"
        from ..utils.icon_utils import colorize_white_svg

        self._play_icon = colorize_white_svg(IconLoader.get("play"), icon_color)
        self._pause_icon = colorize_white_svg(IconLoader.get("pause"), icon_color)
        self._loop_icon = colorize_white_svg(IconLoader.get("loop"), icon_color)

        # Video playback state
        self._cv_cap: Optional[cv2.VideoCapture] = None
        self._cv_timer = QTimer(self)
        self._cv_timer.timeout.connect(self._update_video_frame)
        self._cv_fps = 24
        self._cv_frame_count = 0
        self._cv_total_frames = 0
        self._is_playing = False
        self._is_seeking = False

        # Theme manager for gradients
        self._theme_manager = get_theme_manager()
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

        # Event bus for edit mode changes
        from ..events.event_bus import get_event_bus
        self._event_bus = get_event_bus()
        self._event_bus.edit_mode_changed.connect(lambda enabled: self._update_tags_section())

        # Setup UI
        self._create_widgets()
        self._create_layout()

        # Set minimum width
        self.setMinimumWidth(300)

    def _create_widgets(self):
        """Create panel widgets"""

        # Scroll area for content
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # Content widget
        self._content_widget = QWidget()

        # Description label
        self._description_label = QLabel("")
        self._description_label.setWordWrap(True)

        # Create info sections
        self._technical_section = self._create_section("Technical Information")
        self._rig_section = self._create_section("Rig Information")
        self._file_section = self._create_section("Files")
        self._tags_section = self._create_section("Tags")

    def _create_section(self, title: str) -> QWidget:
        """Create a metadata section with highlighted header"""

        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 8, 0, 8)

        # Section title with subtle background
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)

        # Add subtle gray background for header differentiation
        title_label.setStyleSheet("""
            QLabel {
                background-color: rgba(128, 128, 128, 0.15);
                padding: 4px 8px;
                border-radius: 3px;
            }
        """)
        layout.addWidget(title_label)

        # Grid for key-value pairs
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        # Store grid for later updates
        section.setProperty("grid", grid)

        return section

    def _create_preview_section(self) -> QWidget:
        """Create video preview section with controls"""

        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Video display label (350px height to match old repo)
        self._video_label = QLabel()
        self._video_label.setFixedHeight(350)
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setStyleSheet("background-color: #000000;")
        self._video_label.setText("No preview loaded")
        layout.addWidget(self._video_label)

        # Control buttons row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(2)

        # Play/Pause toggle button (single button with icon swap)
        self._play_pause_button = QPushButton()
        self._play_pause_button.setIcon(self._play_icon)
        self._play_pause_button.setIconSize(QSize(24, 24))
        self._play_pause_button.setFixedSize(36, 36)
        self._play_pause_button.setProperty("media", "true")
        self._play_pause_button.setEnabled(False)
        self._play_pause_button.setToolTip("Play/Pause preview")
        self._play_pause_button.clicked.connect(self._toggle_playback)
        controls_layout.addWidget(self._play_pause_button)

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
        # Subtle highlight when loop is enabled (sharp corners, subtle background)
        self._loop_button.setStyleSheet("""
            QPushButton:checked {
                background-color: rgba(255, 255, 255, 0.35);
            }
        """)
        controls_layout.addWidget(self._loop_button)

        # Progress slider
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setProperty("progress", "true")  # Property for CSS selector
        self._progress_slider.setFixedHeight(32)  # Match old repo height
        self._progress_slider.setMinimum(0)
        self._progress_slider.setMaximum(1000)
        self._progress_slider.setValue(0)
        self._progress_slider.setEnabled(False)
        self._progress_slider.setToolTip("Seek preview timeline")
        self._progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self._progress_slider.sliderReleased.connect(self._on_slider_released)
        self._progress_slider.mousePressEvent = self._progress_slider_mouse_press
        controls_layout.addWidget(self._progress_slider)

        layout.addLayout(controls_layout)

        return section

    def _create_layout(self):
        """Create panel layout"""

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Content layout
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Add widgets to content (preview section first)
        content_layout.addWidget(self._create_preview_section())
        content_layout.addWidget(self._technical_section)
        content_layout.addWidget(self._description_label)
        content_layout.addWidget(self._rig_section)
        content_layout.addWidget(self._file_section)
        content_layout.addWidget(self._tags_section)

        # Set content in scroll area
        self._scroll_area.setWidget(self._content_widget)

        # Add scroll area to main layout
        main_layout.addWidget(self._scroll_area)

    def set_animation(self, animation: Dict[str, Any]):
        """
        Display animation metadata

        Args:
            animation: Animation data dict
        """
        self._animation = animation

        # Load video preview
        preview_path = animation.get('preview_path', '')
        if preview_path:
            self._load_video(preview_path)
        else:
            self._video_label.setText("No preview available")
            self._disable_controls()

        # Update description
        description = animation.get('description', '')
        if description:
            self._description_label.setText(description)
            self._description_label.show()
        else:
            self._description_label.hide()

        # Update technical info
        self._update_technical_section()

        # Update rig info
        self._update_rig_section()

        # Update file info
        self._update_file_section()

        # Update tags
        self._update_tags_section()

    def clear(self):
        """Clear panel"""
        self._animation = None
        self._description_label.clear()
        self._description_label.hide()

        # Stop and release video
        if self._cv_cap:
            self._cv_timer.stop()
            self._cv_cap.release()
            self._cv_cap = None

        self._is_playing = False
        self._video_label.clear()
        self._video_label.setText("No preview loaded")
        self._disable_controls()

        # Clear sections
        self._clear_section(self._technical_section)
        self._clear_section(self._rig_section)
        self._clear_section(self._file_section)
        self._clear_section(self._tags_section)

    def _update_technical_section(self):
        """Update technical information section"""

        if not self._animation:
            return

        grid = self._technical_section.property("grid")
        self._clear_grid(grid)

        row = 0

        # Animation name
        name = self._animation.get('name')
        if name:
            self._add_info_row(grid, row, "Name:", name)
            row += 1

        # Frame count
        frame_count = self._animation.get('frame_count')
        if frame_count:
            self._add_info_row(grid, row, "Frame Count:", str(frame_count))
            row += 1

        # FPS
        fps = self._animation.get('fps')
        if fps:
            self._add_info_row(grid, row, "FPS:", str(fps))
            row += 1

        # Duration
        duration = self._animation.get('duration_seconds')
        if duration:
            self._add_info_row(grid, row, "Duration:", f"{duration:.2f}s")
            row += 1

    def _update_rig_section(self):
        """Update rig information section"""

        if not self._animation:
            return

        grid = self._rig_section.property("grid")
        self._clear_grid(grid)

        row = 0

        # Rig type
        rig_type = self._animation.get('rig_type')
        if rig_type:
            self._add_info_row(grid, row, "Rig Type:", rig_type)
            row += 1

        # Armature name
        armature = self._animation.get('armature_name')
        if armature:
            self._add_info_row(grid, row, "Armature:", armature)
            row += 1

        # Bone count
        bone_count = self._animation.get('bone_count')
        if bone_count:
            self._add_info_row(grid, row, "Bone Count:", str(bone_count))
            row += 1

    def _update_file_section(self):
        """Update file information section"""

        if not self._animation:
            return

        grid = self._file_section.property("grid")
        self._clear_grid(grid)

        row = 0

        # File size
        file_size = self._animation.get('file_size_mb')
        if file_size:
            self._add_info_row(grid, row, "File Size:", f"{file_size:.2f} MB")
            row += 1

        # Author
        author = self._animation.get('author')
        if author:
            self._add_info_row(grid, row, "Author:", author)
            row += 1

        # Created date
        created = self._animation.get('created_date')
        if created:
            self._add_info_row(grid, row, "Created:", str(created)[:10])  # Just date
            row += 1

    def _update_tags_section(self):
        """Update tags section with clickable badges"""

        if not self._animation:
            return

        grid = self._tags_section.property("grid")
        self._clear_grid(grid)

        # Label
        label_widget = QLabel("Tags:")
        label_font = QFont()
        label_font.setBold(True)
        label_widget.setFont(label_font)
        grid.addWidget(label_widget, 0, 0, Qt.AlignmentFlag.AlignTop)

        # Tag badges container
        tags = self._animation.get('tags', [])
        if not tags:
            no_tags_label = QLabel("None")
            grid.addWidget(no_tags_label, 0, 1)
            return

        # Create horizontal layout for tag badges
        tags_widget = QWidget()
        tags_layout = QHBoxLayout(tags_widget)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setSpacing(4)

        # Get edit mode state
        is_edit_mode = self._event_bus.is_edit_mode()

        for tag in tags:
            badge = self._create_tag_badge(tag, removable=is_edit_mode)
            tags_layout.addWidget(badge)

        tags_layout.addStretch()
        grid.addWidget(tags_widget, 0, 1)

    def _create_tag_badge(self, tag: str, removable: bool = False) -> QWidget:
        """Create a tag badge widget"""

        # Get theme colors
        from ..themes.theme_manager import get_theme_manager
        theme_manager = get_theme_manager()
        theme = theme_manager.get_current_theme()

        badge = QFrame()
        badge.setFrameShape(QFrame.Shape.StyledPanel)

        # Style based on removable state (use theme colors)
        if removable:
            bg_color = theme.palette.error if theme else "#dc3545"
            badge.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border-radius: 3px;
                    padding: 2px 6px;
                }}
            """)
        else:
            bg_color = theme.palette.accent if theme else "#4a90e2"
            badge.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border-radius: 3px;
                    padding: 2px 6px;
                }}
            """)

        layout = QHBoxLayout(badge)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Tag text
        tag_label = QLabel(tag)
        tag_label.setStyleSheet("color: white; font-size: 9pt;")
        layout.addWidget(tag_label)

        # Remove button (× symbol) if removable
        if removable:
            remove_btn = QPushButton("×")
            remove_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: white;
                    border: none;
                    font-size: 12pt;
                    font-weight: bold;
                    padding: 0px;
                    margin: 0px;
                }
                QPushButton:hover {
                    color: #ffcccc;
                }
            """)
            remove_btn.setFixedSize(16, 16)
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.clicked.connect(lambda: self._on_remove_tag_clicked(tag))
            layout.addWidget(remove_btn)

        return badge

    def _on_remove_tag_clicked(self, tag: str):
        """Handle tag removal from animation"""

        if not self._animation:
            return

        from PyQt6.QtWidgets import QMessageBox

        # Confirm removal
        reply = QMessageBox.question(
            self,
            "Remove Tag",
            f"Remove tag '{tag}' from this animation?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Get current tags
        tags = self._animation.get('tags', [])
        if tag not in tags:
            return

        # Remove tag
        tags.remove(tag)

        # Update database
        from ..services.database_service import get_database_service
        db_service = get_database_service()

        success = db_service.update_animation(
            self._animation['uuid'],
            {'tags': tags}
        )

        if success:
            # Update local animation data
            self._animation['tags'] = tags

            # Refresh tags display
            self._update_tags_section()

            # Notify via event bus
            self._event_bus.tags_updated.emit(self._animation['uuid'], tags)

            QMessageBox.information(self, "Tag Removed", f"Removed tag '{tag}'")
        else:
            QMessageBox.warning(self, "Error", f"Failed to remove tag '{tag}'")

    def _add_info_row(self, grid: QGridLayout, row: int, label: str, value: str):
        """Add a key-value row to grid"""

        # Label (bold)
        label_widget = QLabel(label)
        label_font = QFont()
        label_font.setBold(True)
        label_widget.setFont(label_font)

        # Value
        value_widget = QLabel(value)
        value_widget.setWordWrap(True)

        grid.addWidget(label_widget, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(value_widget, row, 1)

    def _clear_grid(self, grid: QGridLayout):
        """Clear all widgets from grid"""

        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_section(self, section: QWidget):
        """Clear a section"""

        grid = section.property("grid")
        if grid:
            self._clear_grid(grid)

    # ==================== VIDEO PLAYBACK METHODS ====================

    def _load_video(self, video_path: str) -> bool:
        """Load video file for preview"""

        # Release previous video
        if self._cv_cap:
            self._cv_cap.release()
            self._cv_cap = None

        # Stop playback
        self._cv_timer.stop()
        self._is_playing = False

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

        # Get video properties
        self._cv_fps = self._cv_cap.get(cv2.CAP_PROP_FPS) or 24
        self._cv_total_frames = int(self._cv_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._cv_frame_count = 0

        # Show first frame
        if self._show_current_frame():
            # Enable controls
            self._enable_controls()
            return True
        else:
            self._video_label.setText("Failed to read video")
            self._disable_controls()
            return False

    def _show_current_frame(self) -> bool:
        """Display current video frame"""

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
        """Timer callback to update frame during playback"""

        if not self._show_current_frame():
            # End of video
            if self._loop_button.isChecked():
                # Loop back to start
                self._cv_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._cv_frame_count = 0
                self._show_current_frame()
            else:
                # Stop playback
                self._cv_timer.stop()
                self._is_playing = False
                self._play_pause_button.setIcon(self._play_icon)
        else:
            # Update progress
            self._cv_frame_count += 1
            if not self._is_seeking and self._cv_total_frames > 0:
                progress = int((self._cv_frame_count / self._cv_total_frames) * 1000)
                self._progress_slider.setValue(progress)

    def _toggle_playback(self):
        """Toggle play/pause state"""

        if self._is_playing:
            # Pause
            self._cv_timer.stop()
            self._is_playing = False
            self._play_pause_button.setIcon(self._play_icon)  # Switch to play icon
        else:
            # Play
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
            self._play_pause_button.setIcon(self._pause_icon)  # Switch to pause icon

    def _on_slider_pressed(self):
        """Handle slider drag start"""
        self._is_seeking = True

    def _on_slider_released(self):
        """Handle slider drag end - seek to position"""
        self._is_seeking = False
        self._seek_to_position(self._progress_slider.value())

    def _progress_slider_mouse_press(self, event):
        """Handle mouse press on progress slider for click-to-seek"""
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

    def _seek_to_position(self, slider_value):
        """Seek video to position based on slider value"""
        if self._cv_cap and self._cv_total_frames > 0:
            target_frame = int((slider_value / 1000) * self._cv_total_frames)
            self._cv_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            self._cv_frame_count = target_frame
            self._show_current_frame()

    def _enable_controls(self):
        """Enable video controls"""
        self._play_pause_button.setEnabled(True)
        self._loop_button.setEnabled(True)
        self._progress_slider.setEnabled(True)

    def _disable_controls(self):
        """Disable video controls"""
        self._play_pause_button.setEnabled(False)
        self._loop_button.setEnabled(False)
        self._progress_slider.setEnabled(False)
        self._progress_slider.setValue(0)

    def _on_theme_changed(self, theme_name: str):
        """Reload icons when theme changes"""
        theme = get_theme_manager().get_current_theme()
        if not theme:
            return

        icon_color = theme.palette.header_icon_color
        from ..utils.icon_utils import colorize_white_svg

        # Reload icons with new color
        self._play_icon = colorize_white_svg(IconLoader.get("play"), icon_color)
        self._pause_icon = colorize_white_svg(IconLoader.get("pause"), icon_color)
        self._loop_icon = colorize_white_svg(IconLoader.get("loop"), icon_color)

        # Update current button icon
        if self._is_playing:
            self._play_pause_button.setIcon(self._pause_icon)
        else:
            self._play_pause_button.setIcon(self._play_icon)

        self._loop_button.setIcon(self._loop_icon)


__all__ = ['MetadataPanel']
