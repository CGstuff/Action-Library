"""
ThemeTab - Theme customization tab for settings dialog

Pattern: QWidget with theme selector, preview, and management buttons
Inspired by: Old repo's theme tab
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QLabel, QPushButton, QFileDialog,
    QMessageBox, QFrame, QSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from .theme_editor_dialog import ThemeEditorDialog


class ThemeTab(QWidget):
    """
    Theme customization tab for settings dialog

    Features:
    - Theme selector dropdown
    - Color palette preview (6 color squares)
    - Theme info display
    - Customize/Import/Export/Delete buttons

    Usage:
        tab = ThemeTab(theme_manager)
        settings_dialog.addTab(tab, "Appearance")
    """

    def __init__(self, theme_manager, parent=None):
        """
        Initialize theme tab

        Args:
            theme_manager: ThemeManager instance
            parent: Parent widget
        """
        super().__init__(parent)

        self.theme_manager = theme_manager
        self.current_theme_name = None

        self._create_ui()
        self._load_themes()
        self._load_current_theme()

    def _create_ui(self):
        """Create tab UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Theme Selection Group
        selection_group = QGroupBox("Theme Selection")
        selection_layout = QVBoxLayout(selection_group)

        # Theme dropdown
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo, 1)
        selection_layout.addLayout(theme_row)

        # Color palette preview
        preview_label = QLabel("Color Preview:")
        selection_layout.addWidget(preview_label)

        self.color_preview_widget = self._create_color_preview_widget()
        selection_layout.addWidget(self.color_preview_widget)

        # Theme info
        self.theme_info_label = QLabel()
        self.theme_info_label.setWordWrap(True)
        selection_layout.addWidget(self.theme_info_label)

        layout.addWidget(selection_group)

        # UI Customization Group
        ui_group = QGroupBox("UI Customization")
        ui_layout = QVBoxLayout(ui_group)

        # Folder text size
        folder_size_row = QHBoxLayout()
        folder_size_row.addWidget(QLabel("Folder Text Size:"))
        self.folder_size_spinbox = QSpinBox()
        self.folder_size_spinbox.setMinimum(8)
        self.folder_size_spinbox.setMaximum(20)
        self.folder_size_spinbox.setSuffix(" pt")
        self.folder_size_spinbox.setFixedWidth(80)
        self.folder_size_spinbox.setValue(self.theme_manager.get_folder_text_size())
        self.folder_size_spinbox.valueChanged.connect(self._on_folder_size_changed)
        folder_size_row.addWidget(self.folder_size_spinbox)
        folder_size_row.addStretch()
        ui_layout.addLayout(folder_size_row)

        layout.addWidget(ui_group)

        # Management Buttons
        management_group = QGroupBox("Theme Management")
        management_layout = QVBoxLayout(management_group)

        # Row 1: Customize, Import
        row1 = QHBoxLayout()
        self.customize_btn = QPushButton("Customize Theme...")
        self.customize_btn.clicked.connect(self._on_customize_clicked)
        row1.addWidget(self.customize_btn)

        self.import_btn = QPushButton("Import Theme...")
        self.import_btn.clicked.connect(self._on_import_clicked)
        row1.addWidget(self.import_btn)

        management_layout.addLayout(row1)

        # Row 2: Export, Delete
        row2 = QHBoxLayout()
        self.export_btn = QPushButton("Export Theme...")
        self.export_btn.clicked.connect(self._on_export_clicked)
        row2.addWidget(self.export_btn)

        self.delete_btn = QPushButton("Delete Theme")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        row2.addWidget(self.delete_btn)

        management_layout.addLayout(row2)

        layout.addWidget(management_group)

        # Stretch to push everything to top
        layout.addStretch()

    def _create_color_preview_widget(self) -> QWidget:
        """
        Create color preview widget with 6 color squares

        Returns:
            Widget showing color palette preview
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Create 6 color preview squares
        self.color_squares = []
        for i in range(6):
            square = QFrame()
            square.setFixedSize(50, 50)
            square.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
            square.setLineWidth(1)
            self.color_squares.append(square)
            layout.addWidget(square)

        layout.addStretch()

        return widget

    def _load_themes(self):
        """Load all available themes into dropdown"""
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()

        themes = self.theme_manager.get_all_themes()
        for theme in themes:
            self.theme_combo.addItem(theme.name)

        self.theme_combo.blockSignals(False)

    def _load_current_theme(self):
        """Load and display current theme"""
        current_theme = self.theme_manager.get_current_theme()
        if current_theme:
            self.current_theme_name = current_theme.name

            # Select in dropdown
            index = self.theme_combo.findText(current_theme.name)
            if index >= 0:
                self.theme_combo.setCurrentIndex(index)

            # Update preview and info
            self._update_theme_preview(current_theme)

    def _update_theme_preview(self, theme):
        """
        Update color preview squares and theme info

        Args:
            theme: Theme to preview
        """
        palette = theme.palette

        # Update color squares (6 representative colors)
        colors = [
            palette.background,
            palette.text_primary,
            palette.accent,
            palette.gold_primary,
            palette.success,
            palette.error,
        ]

        for square, color in zip(self.color_squares, colors):
            square.setStyleSheet(f"background-color: {color}; border: 1px solid #666;")

        # Update theme info
        author_text = f"<br>theme by:<br>{theme.author}" if theme.author and theme.author != "Unknown" else ""
        self.theme_info_label.setText(
            f"<b>{theme.name}</b>{author_text}"
        )

        # Update delete button state (only enable for custom themes)
        is_custom = self._is_custom_theme(theme.name)
        self.delete_btn.setEnabled(is_custom)

    def _is_custom_theme(self, theme_name: str) -> bool:
        """
        Check if theme is custom (not built-in)

        Args:
            theme_name: Theme name

        Returns:
            True if custom theme
        """
        return not self.theme_manager.is_builtin_theme(theme_name)

    def _on_theme_changed(self, theme_name: str):
        """
        Handle theme selection change

        Args:
            theme_name: Selected theme name
        """
        if not theme_name:
            return

        try:
            self.theme_manager.set_theme(theme_name)
            self.current_theme_name = theme_name

            # Update preview
            current_theme = self.theme_manager.get_current_theme()
            if current_theme:
                self._update_theme_preview(current_theme)

            # Update folder size spinbox to match new theme
            self.folder_size_spinbox.blockSignals(True)
            self.folder_size_spinbox.setValue(self.theme_manager.get_folder_text_size())
            self.folder_size_spinbox.blockSignals(False)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load theme: {e}")

    def _on_folder_size_changed(self, size: int):
        """
        Handle folder text size change

        Args:
            size: New font size in points
        """
        self.theme_manager.set_folder_text_size(size)

    def _on_customize_clicked(self):
        """Open theme editor dialog"""
        current_theme = self.theme_manager.get_current_theme()
        if not current_theme:
            QMessageBox.warning(self, "No Theme", "No theme selected.")
            return

        # Custom themes can be edited directly, built-in themes require save-as
        is_custom = self._is_custom_theme(current_theme.name)

        dialog = ThemeEditorDialog(
            current_theme,
            self.theme_manager,
            is_custom_theme=is_custom,
            parent=self
        )

        if dialog.exec():
            # Theme was saved, refresh list and select it
            saved_theme = dialog.get_theme()
            self._refresh_theme_list()
            self._select_theme(saved_theme.name)

    def _on_import_clicked(self):
        """Import theme from JSON file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Theme",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if not filepath:
            return

        if self.theme_manager.import_theme(Path(filepath)):
            QMessageBox.information(self, "Success", "Theme imported successfully.")
            self._refresh_theme_list()
        else:
            QMessageBox.critical(self, "Error", "Failed to import theme.")

    def _on_export_clicked(self):
        """Export current theme to JSON file"""
        if not self.current_theme_name:
            QMessageBox.warning(self, "No Theme", "No theme selected.")
            return

        # Suggest filename
        suggested_name = self.current_theme_name.lower().replace(' ', '_') + '.json'

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Theme",
            suggested_name,
            "JSON Files (*.json);;All Files (*)"
        )

        if not filepath:
            return

        if self.theme_manager.export_theme(self.current_theme_name, Path(filepath)):
            QMessageBox.information(self, "Success", f"Theme exported to:\n{filepath}")
        else:
            QMessageBox.critical(self, "Error", "Failed to export theme.")

    def _on_delete_clicked(self):
        """Delete custom theme"""
        if not self.current_theme_name:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Theme",
            f"Are you sure you want to delete the theme '{self.current_theme_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.theme_manager.delete_custom_theme(self.current_theme_name):
            QMessageBox.information(self, "Success", "Theme deleted successfully.")

            # Switch to default theme
            self._refresh_theme_list()
            self._select_theme("dark")
        else:
            QMessageBox.critical(self, "Error", "Failed to delete theme.")

    def _refresh_theme_list(self):
        """Refresh theme dropdown list"""
        self._load_themes()

    def _select_theme(self, theme_name: str):
        """
        Select theme in dropdown

        Args:
            theme_name: Theme name to select
        """
        index = self.theme_combo.findText(theme_name)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

    def save_settings(self):
        """Save theme settings (called by parent dialog)"""
        # Theme is already saved when changed, nothing to do here
        pass


__all__ = ['ThemeTab']
