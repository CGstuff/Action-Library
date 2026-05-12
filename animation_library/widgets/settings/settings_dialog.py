"""
SettingsDialog - Application settings dialog for Animation Library v2

Pattern: QDialog with sidebar list + stacked pages (Photoshop/Blender style)
"""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QDialogButtonBox, QFrame
)

from ...config import Config
from .storage_locations_tab import StorageLocationsTab
from .blender_integration_tab import BlenderIntegrationTab
from .theme_tab import ThemeTab
from .library_tab import LibraryTab
from .maintenance_tab import MaintenanceTab
from .studio_mode_tab import StudioModeTab
from .identity_tab import IdentityTab


class SettingsDialog(QDialog):
    """
    Main settings dialog with sidebar navigation

    Features:
    - Sidebar list of categories (Photoshop/Blender prefs style)
    - Stacked page area on the right
    - OK/Cancel/Apply buttons

    Usage:
        dialog = SettingsDialog(theme_manager, parent=main_window)
        if dialog.exec():
            # Settings were saved
            pass
    """

    SIDEBAR_WIDTH = 180

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        self.setWindowTitle(f"Settings - {Config.APP_NAME}")
        self.setModal(True)
        self.resize(820, 560)

        self._tabs = []  # list of (label, widget) for index lookup
        self._create_ui()

    def _create_ui(self):
        """Create UI layout"""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sharp button style for dialog buttons
        button_style = """
            QPushButton {
                border-radius: 0px;
            }
        """

        # ---- Body: sidebar + stacked pages ----
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Sidebar list
        self._sidebar = QListWidget()
        self._sidebar.setObjectName("settingsSidebar")
        self._sidebar.setFixedWidth(self.SIDEBAR_WIDTH)
        self._sidebar.setFrameShape(QFrame.Shape.NoFrame)
        self._sidebar.setUniformItemSizes(True)
        self._sidebar.setSpacing(0)
        self._sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.setObjectName("settingsStack")

        body.addWidget(self._sidebar)
        body.addWidget(self._stack, 1)

        # Instantiate tabs (same set, same order as before)
        self.storage_tab = StorageLocationsTab(self.theme_manager, self)
        self.blender_tab = BlenderIntegrationTab(self.theme_manager, self)
        self.theme_tab = ThemeTab(self.theme_manager, self)
        self.library_tab = LibraryTab(self.theme_manager, self)
        self.maintenance_tab = MaintenanceTab(self.theme_manager, self)
        self.studio_mode_tab = StudioModeTab(self.theme_manager, self)
        self.identity_tab = IdentityTab(self.theme_manager, self)

        for label, widget in [
            ("Storage Locations",   self.storage_tab),
            ("Blender Integration", self.blender_tab),
            ("Appearance",          self.theme_tab),
            ("Backup",              self.library_tab),
            ("Maintenance",         self.maintenance_tab),
            ("Operation Mode",      self.studio_mode_tab),
            ("Identity",            self.identity_tab),
        ]:
            self._add_page(label, widget)

        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        # Apply sidebar styling using the theme palette
        self._sidebar.setStyleSheet(self._sidebar_qss())

        # Restyle live if the user changes the theme inside this dialog
        try:
            self.theme_manager.theme_changed.connect(self._refresh_sidebar_style)
        except Exception:
            pass

        body_widget = QFrame()
        body_widget.setLayout(body)
        outer.addWidget(body_widget, 1)

        # ---- Button box ----
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply
        )

        for button in button_box.buttons():
            button.setStyleSheet(button_style)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(12, 8, 12, 12)
        button_row.addStretch(1)
        button_row.addWidget(button_box)
        outer.addLayout(button_row)

    def _add_page(self, label: str, widget):
        """Add one (label, widget) pair to the sidebar + stack."""
        item = QListWidgetItem(label)
        item.setSizeHint(QSize(self.SIDEBAR_WIDTH, 32))
        self._sidebar.addItem(item)
        self._stack.addWidget(widget)
        self._tabs.append((label, widget))

    def _sidebar_qss(self) -> str:
        """Sidebar styling — pulls colors from the active theme palette."""
        theme = None
        try:
            theme = self.theme_manager.get_current_theme()
        except Exception:
            pass

        if theme is None:
            sidebar_bg = "#1a1a1a"
            border = "#404040"
            text = "#e0e0e0"
            hover_bg = "#2d2d2d"
            sel_bg = "#3A8FB7"
            sel_text = "#ffffff"
        else:
            p = theme.palette
            sidebar_bg = p.background_secondary
            border = p.border
            text = p.text_primary
            hover_bg = p.list_item_hover
            sel_bg = p.list_item_selected
            sel_text = p.selection_text

        return f"""
        QListWidget#settingsSidebar {{
            background: {sidebar_bg};
            border: none;
            border-right: 1px solid {border};
            outline: 0;
            padding-top: 6px;
            color: {text};
        }}
        QListWidget#settingsSidebar::item {{
            padding: 6px 14px;
            border: none;
            color: {text};
        }}
        QListWidget#settingsSidebar::item:hover {{
            background: {hover_bg};
        }}
        QListWidget#settingsSidebar::item:selected {{
            background: {sel_bg};
            color: {sel_text};
        }}
        """

    def _refresh_sidebar_style(self, *_):
        """Re-apply the sidebar QSS when the active theme changes."""
        self._sidebar.setStyleSheet(self._sidebar_qss())

    def _on_apply(self):
        """Handle Apply button - save settings without closing dialog"""
        self.blender_tab.save_settings()
        self.theme_tab.save_settings()
        self.studio_mode_tab.save_settings()
        self.identity_tab.save_settings()

    def accept(self):
        """Handle OK button - save and close"""
        self._on_apply()
        super().accept()

    def open_identity_tab(self) -> None:
        """
        Switch the dialog to the Identity tab.

        Used by the header identity pill: parent calls this on the dialog
        before exec() so the user lands directly on the Identity editor.
        """
        for i, (_, widget) in enumerate(self._tabs):
            if widget is self.identity_tab:
                self._sidebar.setCurrentRow(i)
                return


__all__ = ['SettingsDialog']
