"""
Version History Dialog - View and manage animation versions

Displays all versions of an animation and allows:
- Viewing version details
- Setting a version as latest
- Applying specific versions
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QApplication, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from typing import Optional, List, Dict, Any

from ...config import Config
from ...services.database_service import get_database_service


class VersionHistoryDialog(QDialog):
    """
    Dialog for viewing and managing animation version history.

    Features:
    - List all versions of an animation
    - Set any version as "latest"
    - Apply specific versions
    - Visual indicator for current version
    """

    # Signals
    version_selected = pyqtSignal(str)  # Emits UUID of selected version
    version_set_as_latest = pyqtSignal(str)  # Emits UUID when set as latest

    WIDTH = 700
    HEIGHT = 450

    def __init__(self, version_group_id: str, parent=None, theme_manager=None):
        super().__init__(parent)

        self._version_group_id = version_group_id
        self._theme_manager = theme_manager
        self._db_service = get_database_service()
        self._versions: List[Dict[str, Any]] = []
        self._selected_uuid: Optional[str] = None

        self._configure_window()
        self._apply_theme_styles()
        self._build_ui()
        self._load_versions()
        self._center_over_parent()

    def _configure_window(self):
        """Configure window properties"""
        self.setWindowTitle("Animation Lineage")
        self.setMinimumSize(self.WIDTH, self.HEIGHT)
        self.setModal(True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def _apply_theme_styles(self):
        """Apply theme styling"""
        if not self._theme_manager:
            # Default dark theme fallback
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1e1e;
                }
                QLabel {
                    color: #e0e0e0;
                    background-color: transparent;
                }
                QPushButton {
                    background-color: #3a3a3a;
                    color: #e0e0e0;
                    border: 1px solid #404040;
                    border-radius: 3px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
                QPushButton:disabled {
                    background-color: #252525;
                    color: #606060;
                }
                QTableWidget {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border: 1px solid #404040;
                    gridline-color: #404040;
                    selection-background-color: #3A8FB7;
                    selection-color: #ffffff;
                }
                QTableWidget::item {
                    padding: 8px;
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
                QTableWidget::item:selected {
                    background-color: #3A8FB7;
                    color: #ffffff;
                }
                QTableWidget::item:hover:!selected {
                    background-color: #3a3a3a;
                }
                QHeaderView::section {
                    background-color: #3a3a3a;
                    color: #ffffff;
                    padding: 8px;
                    border: none;
                    border-right: 1px solid #404040;
                    border-bottom: 1px solid #404040;
                }
                QScrollBar:vertical {
                    background-color: #2d2d2d;
                    width: 12px;
                    border: none;
                }
                QScrollBar::handle:vertical {
                    background-color: #3a3a3a;
                    min-height: 20px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #4a4a4a;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
            """)
            return

        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        p = theme.palette
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p.background};
            }}
            QLabel {{
                color: {p.text_primary};
                background-color: transparent;
            }}
            QPushButton {{
                background-color: {p.button_background};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 3px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {p.button_hover};
            }}
            QPushButton:pressed {{
                background-color: {p.button_pressed};
            }}
            QPushButton:disabled {{
                background-color: {p.button_disabled};
                color: {p.text_disabled};
            }}
            QTableWidget {{
                background-color: {p.background};
                color: {p.text_primary};
                border: 1px solid {p.border};
                gridline-color: {p.border};
                selection-background-color: {p.accent};
                selection-color: {p.text_primary};
            }}
            QTableWidget::item {{
                padding: 8px;
                background-color: {p.background};
                color: {p.text_primary};
            }}
            QTableWidget::item:selected {{
                background-color: {p.accent};
                color: {p.text_primary};
            }}
            QTableWidget::item:hover:!selected {{
                background-color: {p.button_background};
            }}
            QHeaderView::section {{
                background-color: {p.button_background};
                color: {p.text_primary};
                padding: 8px;
                border: none;
                border-right: 1px solid {p.border};
                border-bottom: 1px solid {p.border};
            }}
            QScrollBar:vertical {{
                background-color: {p.background_secondary};
                width: 12px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {p.button_background};
                min-height: 20px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {p.button_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

    def _center_over_parent(self):
        """Center dialog over parent window"""
        if self.parent():
            pg = self.parent().geometry()
            x = pg.x() + (pg.width() - self.width()) // 2
            y = pg.y() + (pg.height() - self.height()) // 2

            screen = QApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                x = max(sg.x(), min(x, sg.x() + sg.width() - self.width()))
                y = max(sg.y() + 30, min(y, sg.y() + sg.height() - self.height()))

            self.move(x, y)

    def _build_ui(self):
        """Build the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("Animation Lineage")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)

        # Animation name (will be set when loading)
        self._name_label = QLabel("")
        self._name_label.setStyleSheet("font-size: 13px; color: #888;")
        layout.addWidget(self._name_label)

        # Version table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Version", "Latest", "Status", "Date Created", "Duration", "Frames"
        ])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(False)

        # Column sizing
        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 70)
        self._table.setColumnWidth(1, 60)
        self._table.setColumnWidth(2, 90)
        self._table.setColumnWidth(4, 80)
        self._table.setColumnWidth(5, 70)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(self._on_double_click)

        layout.addWidget(self._table)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._set_latest_btn = QPushButton("Set as Latest")
        self._set_latest_btn.setEnabled(False)
        self._set_latest_btn.clicked.connect(self._on_set_as_latest)
        btn_layout.addWidget(self._set_latest_btn)

        self._apply_btn = QPushButton("Apply This Version")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply_version)
        btn_layout.addWidget(self._apply_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_versions(self):
        """Load version history from database"""
        self._versions = self._db_service.get_version_history(self._version_group_id)

        if not self._versions:
            self._name_label.setText("No versions found")
            return

        # Set animation name from first version
        self._name_label.setText(f"Animation: {self._versions[0].get('name', 'Unknown')}")

        # Populate table
        self._table.setRowCount(len(self._versions))

        for row, version in enumerate(self._versions):
            # Version label
            version_label = version.get('version_label', 'v001')
            version_item = QTableWidgetItem(version_label)
            version_item.setData(Qt.ItemDataRole.UserRole, version.get('uuid'))
            self._table.setItem(row, 0, version_item)

            # Latest indicator
            is_latest = version.get('is_latest', 0)
            latest_text = "Yes" if is_latest else ""
            latest_item = QTableWidgetItem(latest_text)
            if is_latest:
                latest_item.setForeground(QColor("#4CAF50"))
            self._table.setItem(row, 1, latest_item)

            # Lifecycle status with color
            status = version.get('status', 'none')
            status_info = Config.LIFECYCLE_STATUSES.get(status, {'label': status.upper(), 'color': '#9E9E9E'})
            status_item = QTableWidgetItem(status_info['label'])
            # Use gray color for 'none' status
            if status == 'none' or status_info.get('color') is None:
                status_item.setForeground(QColor('#888888'))
            else:
                status_item.setForeground(QColor(status_info['color']))
            self._table.setItem(row, 2, status_item)

            # Date created
            created = version.get('created_date', '')
            date_str = created[:16] if created else '-'
            self._table.setItem(row, 3, QTableWidgetItem(date_str))

            # Duration
            duration = version.get('duration_seconds')
            dur_str = f"{duration:.1f}s" if duration else '-'
            self._table.setItem(row, 4, QTableWidgetItem(dur_str))

            # Frame count
            frames = version.get('frame_count')
            frame_str = str(frames) if frames else '-'
            self._table.setItem(row, 5, QTableWidgetItem(frame_str))

    def _on_selection_changed(self):
        """Handle table selection change"""
        selected = self._table.selectedItems()
        if selected:
            row = selected[0].row()
            self._selected_uuid = self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

            # Check if selected version is already latest
            is_latest = self._versions[row].get('is_latest', 0)
            self._set_latest_btn.setEnabled(not is_latest)
            self._apply_btn.setEnabled(True)
        else:
            self._selected_uuid = None
            self._set_latest_btn.setEnabled(False)
            self._apply_btn.setEnabled(False)

    def _on_double_click(self, item: QTableWidgetItem):
        """Handle double-click to apply version"""
        self._on_apply_version()

    def _on_set_as_latest(self):
        """Set selected version as latest"""
        if not self._selected_uuid:
            return

        reply = QMessageBox.question(
            self,
            "Set as Latest",
            "Set this version as the latest?\n\n"
            "This will make it the default version shown in the library.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._db_service.set_version_as_latest(self._selected_uuid):
                self.version_set_as_latest.emit(self._selected_uuid)
                self._load_versions()  # Refresh table
                QMessageBox.information(
                    self,
                    "Success",
                    "Version set as latest successfully."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to set version as latest."
                )

    def _on_apply_version(self):
        """Apply selected version"""
        if self._selected_uuid:
            self.version_selected.emit(self._selected_uuid)
            self.accept()

    def get_selected_uuid(self) -> Optional[str]:
        """Get UUID of selected version"""
        return self._selected_uuid


__all__ = ['VersionHistoryDialog']
