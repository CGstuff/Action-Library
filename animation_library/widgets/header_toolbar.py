"""
HeaderToolbar - Main toolbar with search and controls

Pattern: QWidget with horizontal layout
Inspired by: Current animation_library toolbar
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QSlider, QLabel, QSpacerItem, QSizePolicy, QComboBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QIcon

from ..config import Config
from ..events.event_bus import get_event_bus
from ..services.database_service import get_database_service
from ..utils import IconLoader, colorize_white_svg
from ..themes.theme_manager import get_theme_manager


class HeaderToolbar(QWidget):
    """
    Header toolbar with search and view controls

    Features:
    - Search box with live filtering
    - View mode toggle (grid/list)
    - Card size slider (grid mode)
    - Edit mode toggle
    - Delete button
    - Event bus integration

    Layout:
        [Search] [Grid/List] [Size: ----] [Edit Mode] [Delete]
    """

    # Signals
    search_text_changed = pyqtSignal(str)
    view_mode_changed = pyqtSignal(str)  # "grid" or "list"
    card_size_changed = pyqtSignal(int)
    edit_mode_changed = pyqtSignal(bool)
    delete_clicked = pyqtSignal()
    refresh_library_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()  # New: settings button
    new_folder_clicked = pyqtSignal()  # New: create folder button
    about_clicked = pyqtSignal()  # New: about button
    console_clicked = pyqtSignal()  # New: console button
    rig_type_filter_changed = pyqtSignal(list)  # List of selected rig types
    tags_filter_changed = pyqtSignal(list)  # List of selected tags
    sort_changed = pyqtSignal(str, str)  # (sort_by, sort_order)
    help_clicked = pyqtSignal()  # Help button clicked

    def __init__(self, parent=None, db_service=None, event_bus=None, theme_manager=None):
        super().__init__(parent)

        # Set header property for theme-based styling (orange gradient)
        self.setProperty("header", "true")
        # Enable styled background for gradient to work with property selector
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Fixed height like old repo
        self.setFixedHeight(50)

        # Services (injectable for testing)
        self._event_bus = event_bus or get_event_bus()
        self._db_service = db_service or get_database_service()
        self._theme_manager = theme_manager or get_theme_manager()

        # State
        self._view_mode = Config.DEFAULT_VIEW_MODE
        self._card_size = Config.DEFAULT_CARD_SIZE
        self._edit_mode = False

        # Setup UI
        self._create_widgets()
        self._create_layout()
        self._connect_signals()

        # Load filter data
        self._refresh_filter_data()

        # Force Qt to reapply stylesheet for dynamic property AFTER widgets are created
        self.style().unpolish(self)
        self.style().polish(self)

    def _create_widgets(self):
        """Create toolbar widgets"""

        # Get theme for icon colorization
        theme = self._theme_manager.get_current_theme()
        icon_color = theme.palette.header_icon_color if theme else "#1a1a1a"

        # Search box (match old repo: 200px wide)
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search...")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.setFixedWidth(200)  # Match old repo

        # Refresh library button (icon-only)
        self._refresh_btn = QPushButton()
        refresh_icon_path = IconLoader.get("refresh")
        refresh_icon = colorize_white_svg(refresh_icon_path, icon_color)
        self._refresh_btn.setIcon(refresh_icon)
        self._refresh_btn.setIconSize(QSize(24, 24))
        self._refresh_btn.setFixedSize(40, 40)
        self._refresh_btn.setToolTip("Refresh Library (F5)")

        # New folder button (40x40, icon-only)
        self._new_folder_btn = QPushButton()
        add_icon_path = IconLoader.get("add")
        add_icon = colorize_white_svg(add_icon_path, icon_color)
        self._new_folder_btn.setIcon(add_icon)
        self._new_folder_btn.setIconSize(QSize(24, 24))
        self._new_folder_btn.setFixedSize(40, 40)
        self._new_folder_btn.setToolTip("Create New Folder (Ctrl+N)")

        # View mode toggle button (icon-only, smaller like old repo: 32x32)
        self._view_mode_btn = QPushButton()
        view_mode_icon_path = IconLoader.get("view_mode")
        view_mode_icon = colorize_white_svg(view_mode_icon_path, icon_color)
        self._view_mode_btn.setIcon(view_mode_icon)
        self._view_mode_btn.setIconSize(QSize(20, 20))  # Smaller icon
        self._view_mode_btn.setFixedSize(32, 32)  # Match old repo: 32x32
        self._view_mode_btn.setCheckable(True)
        self._view_mode_btn.setChecked(self._view_mode == "grid")
        self._view_mode_btn.setToolTip("Toggle Grid/List View")

        # Card size slider with grid icon
        self._grid_icon_label = QLabel()
        grid_icon_path = IconLoader.get("resize_grid")
        grid_icon = colorize_white_svg(grid_icon_path, icon_color)
        self._grid_icon_label.setPixmap(grid_icon.pixmap(20, 20))
        self._grid_icon_label.setToolTip("Card Size")

        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setProperty("cardsize", "true")  # Property for CSS selector
        self._size_slider.setMinimum(Config.MIN_CARD_SIZE)
        self._size_slider.setMaximum(Config.MAX_CARD_SIZE)
        self._size_slider.setValue(self._card_size)
        self._size_slider.setSingleStep(Config.CARD_SIZE_STEP)
        self._size_slider.setPageStep(Config.CARD_SIZE_STEP * 2)
        self._size_slider.setFixedWidth(120)
        self._size_slider.setToolTip(f"Card size ({Config.MIN_CARD_SIZE}-{Config.MAX_CARD_SIZE}px)")

        # Edit mode toggle (icon-only)
        self._edit_mode_btn = QPushButton()
        edit_icon_path = IconLoader.get("edit")
        edit_icon = colorize_white_svg(edit_icon_path, icon_color)
        self._edit_mode_btn.setIcon(edit_icon)
        self._edit_mode_btn.setIconSize(QSize(24, 24))
        self._edit_mode_btn.setFixedSize(40, 40)
        self._edit_mode_btn.setCheckable(True)
        self._edit_mode_btn.setChecked(False)
        self._edit_mode_btn.setToolTip("Toggle Edit Mode")

        # Delete/Archive button (icon-only)
        # Solo mode: instant delete (trash icon)
        # Studio/Pipeline mode: soft delete to archive (archive icon)
        self._delete_btn = QPushButton()
        self._delete_btn.setIconSize(QSize(24, 24))
        self._delete_btn.setFixedSize(40, 40)
        self._delete_btn.setEnabled(False)
        self._update_delete_button_mode(icon_color)

        # About button (icon-only)
        self._about_btn = QPushButton()
        about_icon_path = IconLoader.get("al_icon")  # App logo icon
        about_icon = colorize_white_svg(about_icon_path, icon_color)
        self._about_btn.setIcon(about_icon)
        self._about_btn.setIconSize(QSize(24, 24))
        self._about_btn.setFixedSize(40, 40)
        self._about_btn.setToolTip("About Animation Library")

        # Console button (icon-only)
        self._console_btn = QPushButton()
        console_icon_path = IconLoader.get("console")
        console_icon = colorize_white_svg(console_icon_path, icon_color)
        self._console_btn.setIcon(console_icon)
        self._console_btn.setIconSize(QSize(24, 24))
        self._console_btn.setFixedSize(40, 40)
        self._console_btn.setToolTip("Console & Logs")

        # Settings button (icon-only, new)
        self._settings_btn = QPushButton()
        settings_icon_path = IconLoader.get("settings")
        settings_icon = colorize_white_svg(settings_icon_path, icon_color)
        self._settings_btn.setIcon(settings_icon)
        self._settings_btn.setIconSize(QSize(24, 24))
        self._settings_btn.setFixedSize(40, 40)
        self._settings_btn.setToolTip("Settings (Ctrl+,)")

        # Help button (shows keyboard shortcuts)
        self._help_btn = QPushButton("?")
        self._help_btn.setFixedSize(40, 40)
        self._help_btn.setToolTip("Keyboard Shortcuts (H)")
        self._help_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
            }
        """)

        # Rig type filter dropdown
        self._rig_type_combo = QComboBox()
        self._rig_type_combo.addItem("All Rig Types")
        self._rig_type_combo.setFixedWidth(140)
        self._rig_type_combo.setToolTip("Filter by Rig Type")

        # Tags filter dropdown (shows all tags, multiple can be selected via dialog)
        self._tags_combo = QComboBox()
        self._tags_combo.addItem("All Tags")
        self._tags_combo.setFixedWidth(120)
        self._tags_combo.setToolTip("Filter by Tags")

        # Sort dropdown
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Sort: Name ↑", ("name", "ASC"))
        self._sort_combo.addItem("Sort: Name ↓", ("name", "DESC"))
        self._sort_combo.addItem("Sort: Date ↑", ("created_date", "ASC"))
        self._sort_combo.addItem("Sort: Date ↓", ("created_date", "DESC"))
        self._sort_combo.addItem("Sort: Duration ↑", ("duration_seconds", "ASC"))
        self._sort_combo.addItem("Sort: Duration ↓", ("duration_seconds", "DESC"))
        self._sort_combo.addItem("Sort: Recent", ("last_viewed_date", "DESC"))
        self._sort_combo.setFixedWidth(140)
        self._sort_combo.setToolTip("Sort Animations")

    def _create_layout(self):
        """Create toolbar layout with filters and sorting"""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)  # Match old repo: 15px left/right
        layout.setSpacing(8)

        # ===== SECTION 1: LEFT - Creation =====
        layout.addWidget(self._new_folder_btn)
        layout.addSpacing(16)  # Space after New Folder

        # ===== SECTION 2: MIDDLE-LEFT - Search & Filters =====
        layout.addWidget(self._search_box)
        layout.addSpacing(4)
        layout.addWidget(self._rig_type_combo)
        layout.addWidget(self._tags_combo)
        layout.addWidget(self._sort_combo)
        layout.addSpacing(24)  # Space after filters

        # ===== SECTION 3: MIDDLE-RIGHT - View & Edit Controls (grouped) =====
        # Group with tight spacing (4px between items)
        layout.addWidget(self._view_mode_btn)  # Moved from position 2 to here
        layout.addSpacing(4)
        layout.addWidget(self._grid_icon_label)
        layout.addWidget(self._size_slider)
        layout.addSpacing(4)
        layout.addWidget(self._edit_mode_btn)
        layout.addSpacing(4)
        layout.addWidget(self._refresh_btn)

        # Stretch spacer to push right buttons to far right
        layout.addStretch()

        # ===== SECTION 4: RIGHT - Archive & System Buttons =====
        # Archive button separated from refresh to prevent accidental clicks
        layout.addWidget(self._delete_btn)
        layout.addSpacing(16)  # Extra spacing before system buttons
        layout.addWidget(self._about_btn)
        layout.addSpacing(4)
        layout.addWidget(self._console_btn)
        layout.addSpacing(4)
        layout.addWidget(self._help_btn)
        layout.addSpacing(4)
        layout.addWidget(self._settings_btn)

    def _connect_signals(self):
        """Connect internal signals"""

        # Search box
        self._search_box.textChanged.connect(self._on_search_text_changed)

        # Refresh button
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)

        # New folder button
        self._new_folder_btn.clicked.connect(self._on_new_folder_clicked)

        # View mode button
        self._view_mode_btn.clicked.connect(self._on_view_mode_clicked)

        # Card size slider
        self._size_slider.valueChanged.connect(self._on_card_size_changed)

        # Edit mode button
        self._edit_mode_btn.clicked.connect(self._on_edit_mode_clicked)

        # Delete button
        self._delete_btn.clicked.connect(self._on_delete_clicked)

        # Settings button
        self._settings_btn.clicked.connect(self.settings_clicked.emit)

        # Help button
        self._help_btn.clicked.connect(self.help_clicked.emit)

        # About button
        self._about_btn.clicked.connect(self._on_about_clicked)

        # Console button
        self._console_btn.clicked.connect(self._on_console_clicked)

        # Filter and sort dropdowns
        self._rig_type_combo.currentIndexChanged.connect(self._on_rig_type_filter_changed)
        self._tags_combo.currentIndexChanged.connect(self._on_tags_filter_changed)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)

        # Event bus - button states
        self._event_bus.delete_button_enabled.connect(self._delete_btn.setEnabled)

        # Theme changes - reload icons with new color
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

    def _update_delete_button_mode(self, icon_color: str = None):
        """
        Update delete button icon and tooltip based on operation mode.
        
        Solo mode: trash icon, "Delete Selected"
        Studio/Pipeline mode: archive icon, "Archive Selected"
        """
        if icon_color is None:
            theme = self._theme_manager.get_current_theme()
            icon_color = theme.palette.header_icon_color if theme else "#1a1a1a"
        
        if Config.is_solo_mode():
            # Solo mode - instant delete
            delete_icon_path = IconLoader.get("delete")
            delete_icon = colorize_white_svg(delete_icon_path, icon_color)
            self._delete_btn.setIcon(delete_icon)
            self._delete_btn.setToolTip("Delete Selected (Del)")
        else:
            # Studio/Pipeline mode - archive (soft delete)
            archive_icon_path = IconLoader.get("archive_icon")
            archive_icon = colorize_white_svg(archive_icon_path, icon_color)
            self._delete_btn.setIcon(archive_icon)
            self._delete_btn.setToolTip("Archive Selected (Del)")

    def _on_theme_changed(self, theme_name: str):
        """Reload all icons when theme changes"""
        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        icon_color = theme.palette.header_icon_color

        # Reload all icons with new color
        add_icon = colorize_white_svg(IconLoader.get("add"), icon_color)
        self._new_folder_btn.setIcon(add_icon)

        refresh_icon = colorize_white_svg(IconLoader.get("refresh"), icon_color)
        self._refresh_btn.setIcon(refresh_icon)

        view_mode_icon = colorize_white_svg(IconLoader.get("view_mode"), icon_color)
        self._view_mode_btn.setIcon(view_mode_icon)

        grid_icon = colorize_white_svg(IconLoader.get("resize_grid"), icon_color)
        self._grid_icon_label.setPixmap(grid_icon.pixmap(20, 20))

        edit_icon = colorize_white_svg(IconLoader.get("edit"), icon_color)
        self._edit_mode_btn.setIcon(edit_icon)

        # Update delete button based on mode
        self._update_delete_button_mode(icon_color)

        about_icon = colorize_white_svg(IconLoader.get("al_icon"), icon_color)
        self._about_btn.setIcon(about_icon)

        console_icon = colorize_white_svg(IconLoader.get("console"), icon_color)
        self._console_btn.setIcon(console_icon)

        settings_icon = colorize_white_svg(IconLoader.get("settings"), icon_color)
        self._settings_btn.setIcon(settings_icon)

        # Force style refresh for gradient background
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def refresh_mode(self):
        """Refresh button appearance when operation mode changes."""
        self._update_delete_button_mode()

    def _on_search_text_changed(self, text: str):
        """Handle search text change"""
        self.search_text_changed.emit(text)
        self._event_bus.set_search_text(text)

    def _on_refresh_clicked(self):
        """Handle refresh library button click"""
        self.refresh_library_clicked.emit()

    def _on_new_folder_clicked(self):
        """Handle new folder button click"""
        self.new_folder_clicked.emit()

    def _on_view_mode_clicked(self):
        """Handle view mode button click"""

        # Toggle mode
        if self._view_mode == "grid":
            self._view_mode = "list"
            self._size_slider.setEnabled(False)  # Size only for grid
        else:
            self._view_mode = "grid"
            self._size_slider.setEnabled(True)

        # Update button checked state (stays icon-only)
        self._view_mode_btn.setChecked(self._view_mode == "grid")

        # Emit signals
        self.view_mode_changed.emit(self._view_mode)
        self._event_bus.set_view_mode(self._view_mode)

    def _on_card_size_changed(self, size: int):
        """Handle card size slider change"""

        self._card_size = size

        # Emit signals
        self.card_size_changed.emit(size)
        self._event_bus.set_card_size(size)

    def _on_edit_mode_clicked(self):
        """Handle edit mode button click"""

        self._edit_mode = self._edit_mode_btn.isChecked()

        # Emit signals
        self.edit_mode_changed.emit(self._edit_mode)
        self._event_bus.set_edit_mode(self._edit_mode)

    def _on_delete_clicked(self):
        """Handle delete button click"""
        self.delete_clicked.emit()

    def _on_about_clicked(self):
        """Handle about button click"""
        self.about_clicked.emit()

        # Show About dialog
        from .dialogs.about_dialog import AboutDialog

        dialog = AboutDialog(self, self._theme_manager)
        dialog.exec()

    def _on_console_clicked(self):
        """Handle console button click"""
        self.console_clicked.emit()

        # Show Console/Logs dialog
        from .dialogs.log_console_dialog import LogConsoleDialog

        dialog = LogConsoleDialog(self, self._theme_manager)
        dialog.exec()

    def _on_rig_type_filter_changed(self, index: int):
        """Handle rig type filter change"""
        if index == 0:
            # "All Rig Types" selected
            self.rig_type_filter_changed.emit([])
        else:
            # Specific rig type selected
            rig_type = self._rig_type_combo.currentText()
            self.rig_type_filter_changed.emit([rig_type])

    def _on_tags_filter_changed(self, index: int):
        """Handle tags filter change"""
        if index == 0:
            # "All Tags" selected
            self.tags_filter_changed.emit([])
        else:
            # Specific tag selected
            tag = self._tags_combo.currentText()
            self.tags_filter_changed.emit([tag])

    def _on_sort_changed(self, index: int):
        """Handle sort option change"""
        # Get sort data from combobox item
        sort_data = self._sort_combo.itemData(index)
        if sort_data:
            sort_by, sort_order = sort_data
            self.sort_changed.emit(sort_by, sort_order)

    def _refresh_filter_data(self):
        """Refresh filter dropdown data from database"""
        # Get all unique rig types
        rig_types = self._db_service.get_all_rig_types()

        # Update rig type combo
        self._rig_type_combo.blockSignals(True)  # Prevent triggering filter change
        self._rig_type_combo.clear()
        self._rig_type_combo.addItem("All Rig Types")
        for rig_type in rig_types:
            self._rig_type_combo.addItem(rig_type)
        self._rig_type_combo.blockSignals(False)

        # Get all unique tags
        tags = self._db_service.get_all_tags()

        # Update tags combo
        self._tags_combo.blockSignals(True)  # Prevent triggering filter change
        self._tags_combo.clear()
        self._tags_combo.addItem("All Tags")
        for tag in tags:
            self._tags_combo.addItem(tag)
        self._tags_combo.blockSignals(False)

    def refresh_filters(self):
        """Public method to refresh filter data (e.g., after library refresh)"""
        self._refresh_filter_data()


__all__ = ['HeaderToolbar']
