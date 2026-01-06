"""
BulkEditToolbar - Toolbar for bulk operations

Pattern: QWidget with centered horizontal layout
Features: Remove tags, move to folder, gradient presets
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QComboBox, QStyledItemDelegate, QStyle
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon

from ..events.event_bus import get_event_bus
from ..utils.color_presets import GRADIENT_PRESETS


class ColorSquareDelegate(QStyledItemDelegate):
    """Custom delegate to draw color squares in the gradient dropdown"""

    def paint(self, painter, option, index):
        # Draw default background for selection/hover
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, option.palette.midlight())

        # Get item data
        icon_color = index.data(Qt.ItemDataRole.UserRole + 1)
        text = index.data(Qt.ItemDataRole.DisplayRole)

        painter.save()

        # Draw color square if we have a color
        square_size = 14
        margin = 6
        text_offset = margin

        if icon_color:
            square_x = option.rect.x() + margin
            square_y = option.rect.y() + (option.rect.height() - square_size) // 2

            painter.fillRect(square_x, square_y, square_size, square_size, QColor(icon_color))
            painter.setPen(QColor("#666666"))
            painter.drawRect(square_x, square_y, square_size - 1, square_size - 1)

            text_offset = margin + square_size + 8

        # Draw text
        text_rect = option.rect.adjusted(text_offset, 0, -margin, 0)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(140, 28)


class BulkEditToolbar(QWidget):
    """
    Toolbar for bulk editing selected animations

    Features:
    - Remove tags from selected
    - Move to folder
    - Gradient presets dropdown with color squares
    - Centered, minimalistic layout

    Layout:
        [stretch] [Selection Label] [stretch]
        [stretch] [Remove Tags] [Move to Folder] [Gradient ▼] [stretch]
    """

    # Signals
    remove_tags_clicked = pyqtSignal()
    move_to_folder_clicked = pyqtSignal()
    gradient_preset_selected = pyqtSignal(str, tuple, tuple)  # name, top_color, bottom_color
    custom_gradient_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Event bus
        self._event_bus = get_event_bus()

        # Setup UI
        self._create_widgets()
        self._create_layout()
        self._connect_signals()
        self._apply_styling()

        # Set initial state
        self._update_selection_count(0)

    def _create_widgets(self):
        """Create toolbar widgets"""

        # Selection count label
        self._selection_label = QLabel("No animations selected")
        self._selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Remove tags button
        self._remove_tags_btn = QPushButton("Remove Tags")
        self._remove_tags_btn.setToolTip("Remove tags from selected animations")

        # Move to folder button
        self._move_folder_btn = QPushButton("Move to Folder")
        self._move_folder_btn.setToolTip("Move selected animations to a folder")

        # Gradient preset dropdown
        self._gradient_combo = QComboBox()
        self._gradient_combo.setToolTip("Set gradient for selected animations")
        self._gradient_combo.setItemDelegate(ColorSquareDelegate(self._gradient_combo))
        self._gradient_combo.setMinimumWidth(150)

        # Populate gradient dropdown
        self._gradient_combo.addItem("Gradient")  # Placeholder
        self._gradient_combo.model().item(0).setEnabled(False)

        for preset in GRADIENT_PRESETS:
            self._gradient_combo.addItem(preset["name"])
            # Store icon color for delegate
            idx = self._gradient_combo.count() - 1
            self._gradient_combo.setItemData(idx, preset["icon"], Qt.ItemDataRole.UserRole + 1)
            # Store gradient colors
            self._gradient_combo.setItemData(idx, preset["top"], Qt.ItemDataRole.UserRole + 2)
            self._gradient_combo.setItemData(idx, preset["bottom"], Qt.ItemDataRole.UserRole + 3)

        # Add separator and Custom option
        self._gradient_combo.insertSeparator(self._gradient_combo.count())
        self._gradient_combo.addItem("Custom...")
        custom_idx = self._gradient_combo.count() - 1
        self._gradient_combo.setItemData(custom_idx, None, Qt.ItemDataRole.UserRole + 1)

    def _create_layout(self):
        """Create centered toolbar layout"""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # Row 1: Selection label (centered)
        label_row = QHBoxLayout()
        label_row.addStretch()
        label_row.addWidget(self._selection_label)
        label_row.addStretch()
        main_layout.addLayout(label_row)

        # Row 2: Action buttons (centered)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(12)
        buttons_row.addStretch()
        buttons_row.addWidget(self._remove_tags_btn)
        buttons_row.addWidget(self._move_folder_btn)
        buttons_row.addWidget(self._gradient_combo)
        buttons_row.addStretch()
        main_layout.addLayout(buttons_row)

    def _connect_signals(self):
        """Connect internal signals"""

        # Buttons
        self._remove_tags_btn.clicked.connect(self._on_remove_tags_clicked)
        self._move_folder_btn.clicked.connect(self._on_move_folder_clicked)

        # Gradient dropdown
        self._gradient_combo.currentIndexChanged.connect(self._on_gradient_selected)

        # Event bus - selection changes
        self._event_bus.selected_animations_changed.connect(self._on_selection_changed)

    def _apply_styling(self):
        """Apply sharp, minimalistic styling"""

        self.setStyleSheet("""
            BulkEditToolbar {
                border-bottom: 1px solid #444;
            }

            QLabel {
                font-weight: bold;
                font-size: 11px;
            }

            QPushButton {
                border: 1px solid #555;
                border-radius: 0px;
                padding: 6px 16px;
                background-color: #3a3a3a;
                min-width: 80px;
            }

            QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #666;
            }

            QPushButton:pressed {
                background-color: #2a2a2a;
            }

            QPushButton:disabled {
                background-color: #2a2a2a;
                border-color: #444;
                color: #666;
            }

            QComboBox {
                border: 1px solid #555;
                border-radius: 0px;
                padding: 6px 12px;
                background-color: #3a3a3a;
                min-width: 130px;
            }

            QComboBox:hover {
                background-color: #4a4a4a;
                border-color: #666;
            }

            QComboBox:disabled {
                background-color: #2a2a2a;
                border-color: #444;
                color: #666;
            }

            QComboBox::drop-down {
                border: none;
                width: 20px;
            }

            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #aaa;
                margin-right: 8px;
            }

            QComboBox QAbstractItemView {
                border: 1px solid #555;
                background-color: #2e2e2e;
                selection-background-color: #569eff;
            }
        """)

    def _on_remove_tags_clicked(self):
        """Handle remove tags button click"""
        self.remove_tags_clicked.emit()

    def _on_move_folder_clicked(self):
        """Handle move to folder button click"""
        self.move_to_folder_clicked.emit()

    def _on_gradient_selected(self, index: int):
        """Handle gradient preset selection"""
        if index <= 0:  # Placeholder or invalid
            return

        text = self._gradient_combo.currentText()

        if text == "Custom...":
            # Reset to placeholder and emit custom signal
            self._gradient_combo.blockSignals(True)
            self._gradient_combo.setCurrentIndex(0)
            self._gradient_combo.blockSignals(False)
            self.custom_gradient_clicked.emit()
        else:
            # Get preset colors and emit
            top = self._gradient_combo.itemData(index, Qt.ItemDataRole.UserRole + 2)
            bottom = self._gradient_combo.itemData(index, Qt.ItemDataRole.UserRole + 3)

            if top and bottom:
                self.gradient_preset_selected.emit(text, top, bottom)

            # Reset dropdown to placeholder
            self._gradient_combo.blockSignals(True)
            self._gradient_combo.setCurrentIndex(0)
            self._gradient_combo.blockSignals(False)

    def _on_selection_changed(self, selected_uuids: set):
        """Handle selection change from event bus"""
        self._update_selection_count(len(selected_uuids))

    def _update_selection_count(self, count: int):
        """Update selection count display and button states"""

        if count == 0:
            self._selection_label.setText("No animations selected")
        elif count == 1:
            self._selection_label.setText("1 animation selected")
        else:
            self._selection_label.setText(f"{count} animations selected")

        # Enable/disable controls
        enabled = count > 0
        self._remove_tags_btn.setEnabled(enabled)
        self._move_folder_btn.setEnabled(enabled)
        self._gradient_combo.setEnabled(enabled)


__all__ = ['BulkEditToolbar']
