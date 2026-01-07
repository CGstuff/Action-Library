"""
ThemeEditorDialog - Visual theme editor with live preview

Pattern: QDialog with scrollable color picker groups
Inspired by: Old repo's theme editor
"""

import copy
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea,
    QWidget, QGroupBox, QPushButton, QCheckBox,
    QLineEdit, QLabel, QMessageBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer

from .color_picker_row import ColorPickerRow
from ...themes.theme_manager import Theme, ColorPalette


class ThemeEditorDialog(QDialog):
    """
    Visual theme editor with live preview

    Features:
    - Live preview toggle (debounced)
    - Scrollable color picker groups
    - Save dialog prompts for name and author
    - Always saves as new custom theme

    Usage:
        dialog = ThemeEditorDialog(theme, theme_manager)
        if dialog.exec():
            # Theme was saved as custom theme
            saved_theme = dialog.get_theme()
    """

    def __init__(self, theme: Theme, theme_manager, is_custom_theme=False, parent=None):
        """
        Initialize theme editor dialog

        Args:
            theme: Theme to edit
            theme_manager: ThemeManager instance
            is_custom_theme: True if editing a custom theme (saves directly),
                           False if customizing built-in (shows save-as dialog)
            parent: Parent widget
        """
        super().__init__(parent)

        self.original_theme = theme
        self.working_theme = self._copy_theme(theme)
        self.theme_manager = theme_manager
        self.is_custom_theme = is_custom_theme

        self.color_pickers = {}  # Map of color_name -> ColorPickerRow
        self.live_preview_enabled = False
        self.preview_theme_name = f"__preview__{theme.name}"  # Temp name for preview
        self.preview_debounce_timer = QTimer()
        self.preview_debounce_timer.setSingleShot(True)
        self.preview_debounce_timer.setInterval(100)  # 100ms debounce
        self.preview_debounce_timer.timeout.connect(self._apply_preview)

        self._setup_dialog()
        self._create_ui()

    def _setup_dialog(self):
        """Configure dialog properties"""
        self.setWindowTitle(f"Customize Theme - {self.working_theme.name}")
        self.setModal(True)
        self.resize(600, 700)

    def _copy_theme(self, theme: Theme) -> Theme:
        """Deep copy theme"""
        palette_copy = copy.deepcopy(theme.palette)
        theme_copy = Theme(theme.name, palette_copy)

        # Create a new get_stylesheet method that uses the copied palette
        from ...themes.dark_theme import DarkTheme
        def get_stylesheet_for_copy():
            """Generate stylesheet using copied theme's palette"""
            dark_theme = DarkTheme()
            dark_theme.palette = theme_copy.palette  # Use copied palette
            return dark_theme.get_stylesheet()

        theme_copy.get_stylesheet = get_stylesheet_for_copy
        return theme_copy

    def _create_ui(self):
        """Create dialog UI"""
        layout = QVBoxLayout(self)

        # Live preview toggle
        self.live_preview_checkbox = QCheckBox("Live Preview")
        self.live_preview_checkbox.stateChanged.connect(self._on_live_preview_toggled)
        layout.addWidget(self.live_preview_checkbox)

        # Scrollable color picker area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(15)

        # Add color picker groups
        container_layout.addWidget(self._create_background_group())
        container_layout.addWidget(self._create_foreground_group())
        container_layout.addWidget(self._create_accent_group())
        container_layout.addWidget(self._create_gold_group())
        container_layout.addWidget(self._create_status_group())
        container_layout.addWidget(self._create_border_group())
        container_layout.addWidget(self._create_button_group())
        container_layout.addWidget(self._create_header_group())
        container_layout.addWidget(self._create_dialog_group())
        container_layout.addWidget(self._create_dropdown_group())

        container_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Button box
        button_box = QDialogButtonBox()
        # Custom themes save directly, built-in themes show save-as dialog
        save_text = "Save" if self.is_custom_theme else "Save As..."
        save_btn = button_box.addButton(save_text, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        reset_btn = button_box.addButton("Reset", QDialogButtonBox.ButtonRole.ResetRole)

        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        reset_btn.clicked.connect(self._on_reset)

        layout.addWidget(button_box)

    def _create_color_picker(self, label: str, color_attr: str) -> ColorPickerRow:
        """
        Create color picker row and register it

        Args:
            label: Display label
            color_attr: ColorPalette attribute name

        Returns:
            ColorPickerRow instance
        """
        initial_color = getattr(self.working_theme.palette, color_attr)
        picker = ColorPickerRow(label, initial_color)
        picker.color_changed.connect(lambda color: self._on_color_changed(color_attr, color))
        self.color_pickers[color_attr] = picker
        return picker

    def _create_background_group(self) -> QGroupBox:
        """Create background colors group"""
        group = QGroupBox("Background Colors")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Primary", "background"))
        layout.addWidget(self._create_color_picker("Secondary", "background_secondary"))

        return group

    def _create_foreground_group(self) -> QGroupBox:
        """Create foreground/text colors group"""
        group = QGroupBox("Text Colors")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Primary Text", "text_primary"))
        layout.addWidget(self._create_color_picker("Secondary Text", "text_secondary"))
        layout.addWidget(self._create_color_picker("Disabled Text", "text_disabled"))

        return group

    def _create_accent_group(self) -> QGroupBox:
        """Create accent colors group"""
        group = QGroupBox("Accent Colors")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Accent Primary", "accent"))
        layout.addWidget(self._create_color_picker("Accent Hover", "accent_hover"))
        layout.addWidget(self._create_color_picker("Accent Pressed", "accent_pressed"))

        return group

    def _create_gold_group(self) -> QGroupBox:
        """Create favorite/highlight colors group"""
        group = QGroupBox("Favorite & Selection")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Favorite Star", "gold_primary"))
        layout.addWidget(self._create_color_picker("Selection Border", "selection_border"))

        return group

    def _create_status_group(self) -> QGroupBox:
        """Create status colors group"""
        group = QGroupBox("Status Colors")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Error", "error"))
        layout.addWidget(self._create_color_picker("Warning", "warning"))
        layout.addWidget(self._create_color_picker("Success", "success"))

        return group

    def _create_border_group(self) -> QGroupBox:
        """Create border colors group"""
        group = QGroupBox("Border Colors")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Border Primary", "border"))
        layout.addWidget(self._create_color_picker("Divider", "divider"))

        return group

    def _create_button_group(self) -> QGroupBox:
        """Create button colors group"""
        group = QGroupBox("Button Colors")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Button Background", "button_background"))
        layout.addWidget(self._create_color_picker("Button Hover", "button_hover"))
        layout.addWidget(self._create_color_picker("Button Pressed", "button_pressed"))
        layout.addWidget(self._create_color_picker("Button Disabled", "button_disabled"))

        return group

    def _create_header_group(self) -> QGroupBox:
        """Create header colors group"""
        group = QGroupBox("Header Colors")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Gradient Start", "header_gradient_start"))
        layout.addWidget(self._create_color_picker("Gradient End", "header_gradient_end"))
        layout.addWidget(self._create_color_picker("Header Icon Color", "header_icon_color"))
        layout.addWidget(self._create_color_picker("Folder Icon Color", "folder_icon_color"))

        return group

    def _create_dialog_group(self) -> QGroupBox:
        """Create dialog colors group"""
        group = QGroupBox("Dialog Colors")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Dialog Background", "dialog_background"))
        layout.addWidget(self._create_color_picker("Dialog Text", "dialog_text"))
        layout.addWidget(self._create_color_picker("Dialog Border", "dialog_border"))

        return group

    def _create_dropdown_group(self) -> QGroupBox:
        """Create dropdown/list item colors group"""
        group = QGroupBox("Dropdown Colors")
        layout = QVBoxLayout(group)

        layout.addWidget(self._create_color_picker("Item Background", "list_item_background"))
        layout.addWidget(self._create_color_picker("Item Hover", "list_item_hover"))
        layout.addWidget(self._create_color_picker("Item Selected", "list_item_selected"))

        return group

    def _on_color_changed(self, color_attr: str, new_hex_color: str):
        """
        Handle color change from picker

        Args:
            color_attr: ColorPalette attribute name
            new_hex_color: New hex color value
        """
        # Update working theme palette
        setattr(self.working_theme.palette, color_attr, new_hex_color)

        # Trigger debounced preview if enabled
        if self.live_preview_enabled:
            self.preview_debounce_timer.start()

    def _on_live_preview_toggled(self, state):
        """Handle live preview checkbox toggle"""
        self.live_preview_enabled = (state == Qt.CheckState.Checked.value)

        if self.live_preview_enabled:
            self._apply_preview()
        else:
            # Restore original theme
            self._restore_original_theme()

    def _apply_preview(self):
        """Apply working theme to main window (for live preview)"""
        if not self.live_preview_enabled:
            return

        # Create a preview copy with temp name (so we don't overwrite original)
        preview_theme = self._copy_theme(self.working_theme)
        preview_theme.name = self.preview_theme_name

        # Temporarily register and set preview theme
        self.theme_manager.register_theme(preview_theme)
        self.theme_manager.set_theme(self.preview_theme_name)

    def _restore_original_theme(self):
        """Restore the original theme (undo live preview changes)"""
        # Re-register original theme to ensure it's not corrupted
        self.theme_manager.register_theme(self.original_theme)
        self.theme_manager.set_theme(self.original_theme.name)

    def _on_reset(self):
        """Reset all colors to original theme"""
        self.working_theme = self._copy_theme(self.original_theme)

        # Update all color pickers
        for color_attr, picker in self.color_pickers.items():
            new_color = getattr(self.working_theme.palette, color_attr)
            picker.set_color(new_color)

        # Update preview if live preview is enabled
        if self.live_preview_enabled:
            self._apply_preview()

    def _on_save(self):
        """Save theme - directly for custom themes, with dialog for built-in"""
        if self.is_custom_theme:
            # Custom theme: save directly
            if self.theme_manager.save_custom_theme(self.working_theme):
                self.theme_manager.set_theme(self.working_theme.name)
                self.accept()
            else:
                QMessageBox.critical(self, "Save Failed", "Failed to save theme.")
        else:
            # Built-in theme: show save-as dialog
            self._show_save_as_dialog()

    def _show_save_as_dialog(self):
        """Show save-as dialog for creating new custom theme from built-in"""
        from PyQt6.QtWidgets import QDialog, QFormLayout

        # Create save dialog
        save_dialog = QDialog(self)
        save_dialog.setWindowTitle("Save Theme As")
        save_dialog.setModal(True)
        save_dialog.setMinimumWidth(350)
        dialog_layout = QVBoxLayout(save_dialog)

        # Form layout for inputs
        form = QFormLayout()

        # Theme name input
        name_input = QLineEdit(f"{self.working_theme.name} (Custom)")
        name_input.selectAll()
        form.addRow("Theme Name:", name_input)

        # Author input
        author_input = QLineEdit("")
        author_input.setPlaceholderText("Your name (optional)")
        form.addRow("Author:", author_input)

        dialog_layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(save_dialog.accept)
        buttons.rejected.connect(save_dialog.reject)
        dialog_layout.addWidget(buttons)

        # Show dialog
        if save_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Validate name
        new_name = name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a theme name.")
            return

        # Update theme metadata
        self.working_theme.name = new_name
        self.working_theme.author = author_input.text().strip() or "Unknown"

        # Save as custom theme
        if self.theme_manager.save_custom_theme(self.working_theme):
            self.theme_manager.set_theme(self.working_theme.name)
            self.accept()
        else:
            QMessageBox.critical(self, "Save Failed", "Failed to save theme.")

    def get_theme(self) -> Theme:
        """
        Get the edited theme

        Returns:
            Working theme instance
        """
        return self.working_theme

    def reject(self):
        """Handle cancel button - restore original theme"""
        self._restore_original_theme()
        super().reject()

    def closeEvent(self, event):
        """Handle dialog close (X button)"""
        # Restore original theme if live preview was active
        if self.live_preview_enabled:
            self._restore_original_theme()
        super().closeEvent(event)


__all__ = ['ThemeEditorDialog']
