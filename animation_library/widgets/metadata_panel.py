"""
MetadataPanel - Display animation details

Pattern: QWidget with form layout
Inspired by: Current animation_library metadata display
"""

from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea,
    QFrame, QGridLayout, QPushButton, QHBoxLayout, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

from ..themes.theme_manager import get_theme_manager
from ..config import Config
from .video_preview_widget import VideoPreviewWidget
from .dialogs import VersionHistoryDialog


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
    - Version information (v5)

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
        ├─────────────────┤
        │  Version Info   │
        │  v001 [LATEST]  │
        │  [View History] │
        └─────────────────┘
    """

    # Signals
    version_changed = pyqtSignal(str)  # Emits UUID when version changes

    def __init__(self, parent=None):
        super().__init__(parent)

        # Current animation
        self._animation: Optional[Dict[str, Any]] = None

        # Theme manager
        self._theme_manager = get_theme_manager()

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
        self._version_section = self._create_version_section()

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
        """Create video preview section using VideoPreviewWidget"""
        self._video_preview = VideoPreviewWidget()
        return self._video_preview

    def _create_version_section(self) -> QWidget:
        """Create version information section with history button and status badge"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 8, 0, 8)

        # Section title with subtle background
        title_label = QLabel("Lineage")
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("""
            QLabel {
                background-color: rgba(128, 128, 128, 0.15);
                padding: 4px 8px;
                border-radius: 3px;
            }
        """)
        layout.addWidget(title_label)

        # Version info container
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(8, 4, 8, 4)
        info_layout.setSpacing(8)

        # Version label (e.g., "v001")
        self._version_label = QLabel("v001")
        self._version_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        info_layout.addWidget(self._version_label)

        # Latest badge
        self._latest_badge = QLabel("LATEST")
        self._latest_badge.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                color: white;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)
        info_layout.addWidget(self._latest_badge)

        # Version count label
        self._version_count_label = QLabel("")
        self._version_count_label.setStyleSheet("color: #888; font-size: 9pt;")
        info_layout.addWidget(self._version_count_label)

        info_layout.addStretch()
        layout.addWidget(info_widget)

        # Status row
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(8, 4, 8, 4)
        status_layout.setSpacing(8)

        # Status label
        status_text = QLabel("Status:")
        status_text.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(status_text)

        # Status badge (clickable button styled as badge)
        self._status_badge = QPushButton("WIP")
        self._status_badge.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._status_badge.clicked.connect(self._on_status_badge_clicked)
        self._update_status_badge_style('wip')
        status_layout.addWidget(self._status_badge)

        status_layout.addStretch()
        layout.addWidget(status_widget)

        # View History button
        self._history_btn = QPushButton("View Lineage")
        self._history_btn.clicked.connect(self._on_view_history_clicked)
        self._history_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
            }
        """)
        layout.addWidget(self._history_btn)

        return section

    def _update_status_badge_style(self, status: str):
        """Update the status badge appearance based on status"""
        status_info = Config.LIFECYCLE_STATUSES.get(status, {'color': '#9E9E9E', 'label': status.upper()})
        color = status_info['color']
        label = status_info['label']

        self._status_badge.setText(label)

        # Special styling for 'none' status - subtle/muted appearance
        if status == 'none' or color is None:
            self._status_badge.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    color: #888888;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 10pt;
                    font-weight: bold;
                    border: 1px solid #555555;
                }
                QPushButton:hover {
                    background-color: #505050;
                    border: 1px solid #666666;
                }
            """)
        else:
            self._status_badge.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 10pt;
                    font-weight: bold;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {color};
                    border: 2px solid white;
                }}
            """)

    def _create_layout(self):
        """Create panel layout"""

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Content layout
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Add widgets to content (preview section first, then version info)
        content_layout.addWidget(self._create_preview_section())
        content_layout.addWidget(self._version_section)
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
            self._video_preview.load_video(preview_path)
        else:
            self._video_preview.clear()

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

        # Update version info
        self._update_version_section()

    def clear(self):
        """Clear panel"""
        self._animation = None
        self._description_label.clear()
        self._description_label.hide()

        # Clear video preview
        self._video_preview.clear()

        # Clear sections
        self._clear_section(self._technical_section)
        self._clear_section(self._rig_section)
        self._clear_section(self._file_section)
        self._clear_section(self._tags_section)

        # Clear version section
        self._version_label.setText("v001")
        self._latest_badge.hide()
        self._version_count_label.setText("")
        self._history_btn.setEnabled(False)
        self._update_status_badge_style('none')  # Reset status badge

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

    # ==================== VERSION SECTION ====================

    def _update_version_section(self):
        """Update version information section"""

        if not self._animation:
            self._version_section.hide()
            return

        self._version_section.show()

        # Get version info
        version_label = self._animation.get('version_label', 'v001')
        is_latest = self._animation.get('is_latest', 1)
        version_group_id = self._animation.get('version_group_id')

        # Update version label
        self._version_label.setText(version_label)

        # Show/hide latest badge
        if is_latest:
            self._latest_badge.show()
        else:
            self._latest_badge.hide()

        # Update status badge
        status = self._animation.get('status', 'none')
        self._update_status_badge_style(status)

        # Get version count from database
        # Use version_group_id or fall back to animation's own UUID
        group_id = version_group_id or self._animation.get('uuid')

        if group_id:
            from ..services.database_service import get_database_service
            db_service = get_database_service()
            version_count = db_service.get_version_count(group_id)

            if version_count > 1:
                self._version_count_label.setText(f"({version_count} versions)")
                self._version_count_label.show()
            else:
                self._version_count_label.hide()

            # Always enable button so user can view lineage
            self._history_btn.setEnabled(True)
        else:
            self._version_count_label.hide()
            self._history_btn.setEnabled(False)

    def _on_status_badge_clicked(self):
        """Show status selection menu when badge is clicked"""
        if not self._animation:
            return

        menu = QMenu(self)

        current_status = self._animation.get('status', 'wip')

        # Add status options
        for status_key, status_info in Config.LIFECYCLE_STATUSES.items():
            action = menu.addAction(status_info['label'])
            action.setData(status_key)

            # Check mark for current status
            if status_key == current_status:
                action.setCheckable(True)
                action.setChecked(True)

            # Connect action
            action.triggered.connect(lambda checked, s=status_key: self._on_status_selected(s))

        # Show menu below the badge
        menu.exec(self._status_badge.mapToGlobal(
            self._status_badge.rect().bottomLeft()
        ))

    def _on_status_selected(self, status: str):
        """Handle status selection from menu"""
        if not self._animation:
            return

        uuid = self._animation.get('uuid')
        if not uuid:
            return

        # Update database
        from ..services.database_service import get_database_service
        db_service = get_database_service()

        if db_service.set_status(uuid, status):
            # Update local animation data
            self._animation['status'] = status

            # Update badge appearance
            self._update_status_badge_style(status)

            # Notify via event bus
            self._event_bus.animation_updated.emit(uuid)

    def _on_view_history_clicked(self):
        """Open version history dialog"""

        if not self._animation:
            return

        # Use version_group_id if available, otherwise fall back to animation's own UUID
        version_group_id = self._animation.get('version_group_id') or self._animation.get('uuid')
        if not version_group_id:
            return

        # Open version history dialog
        dialog = VersionHistoryDialog(
            version_group_id,
            parent=self,
            theme_manager=self._theme_manager
        )

        # Connect signals
        dialog.version_selected.connect(self._on_version_selected)
        dialog.version_set_as_latest.connect(self._on_version_set_as_latest)

        dialog.exec()

    def _on_version_selected(self, uuid: str):
        """Handle version selection from history dialog"""
        # Emit signal for parent to handle (e.g., load that version)
        self.version_changed.emit(uuid)

    def _on_version_set_as_latest(self, uuid: str):
        """Handle version set as latest from history dialog"""
        # Refresh the version section if it's the current animation
        if self._animation and self._animation.get('uuid') == uuid:
            # Refresh animation data from database
            from ..services.database_service import get_database_service
            db_service = get_database_service()
            updated = db_service.get_animation_by_uuid(uuid)
            if updated:
                self._animation = updated
                self._update_version_section()

        # Emit signal for parent to handle
        self.version_changed.emit(uuid)


__all__ = ['MetadataPanel']
