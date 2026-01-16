"""
Rename Dialog - Field-based renaming for studio naming engine

Allows editing individual naming fields while preserving:
- UUID (identity)
- Version (immutable)
- Version group (lineage)

Uses the naming_template stored with the animation (from Blender capture)
rather than loading settings - this ensures animations keep their original
template even if Blender's settings change later.
"""

import re
import json
from typing import Dict, Optional, Any, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFormLayout, QGroupBox, QCheckBox, QMessageBox,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal

from ...services.database_service import get_database_service


class NamingTemplate:
    """Simple template parser for rename dialog."""

    FIELD_PATTERN = re.compile(r'\{(\w+)(?::([^}]+))?\}')

    def __init__(self, template: str):
        self.template = template
        self.fields = self._extract_fields()

    def _extract_fields(self) -> List[Dict[str, Any]]:
        """Extract field names and format specs from template."""
        fields = []
        for match in self.FIELD_PATTERN.finditer(self.template):
            fields.append({
                'name': match.group(1),
                'format_spec': match.group(2),
                'is_version': match.group(1) == "version"
            })
        return fields

    def get_required_fields(self) -> List[str]:
        """Return field names (excluding version)."""
        return [f['name'] for f in self.fields if not f['is_version']]

    def render(self, field_data: Dict[str, str], version: int) -> str:
        """Render template with field values."""
        all_data = {**field_data, "version": version}

        result = self.template
        for field in self.fields:
            name = field['name']
            format_spec = field['format_spec']

            placeholder = f"{{{name}}}"
            if format_spec:
                placeholder = f"{{{name}:{format_spec}}}"

            value = all_data.get(name, "")
            if format_spec and name == "version":
                formatted = format(int(value), format_spec)
            elif format_spec and isinstance(value, (int, float)):
                formatted = format(value, format_spec)
            else:
                formatted = str(value)

            result = result.replace(placeholder, formatted)

        return result


class RenameDialog(QDialog):
    """
    Field-based rename dialog for animations.

    Features:
    - Edit individual naming fields
    - Version field is read-only (immutable)
    - Live preview of generated name
    - Option to apply to all versions in lineage
    """

    # Emitted when rename is successful: (uuid, new_name, apply_to_all)
    renamed = pyqtSignal(str, str, bool)

    def __init__(
        self,
        animation_uuid: str,
        animation_data: Dict[str, Any],
        parent=None
    ):
        super().__init__(parent)

        self._uuid = animation_uuid
        self._animation = animation_data
        self._db_service = get_database_service()

        # Use the template stored with the animation
        template_str = animation_data.get('naming_template', '{asset}_v{version:03}')
        self._template = NamingTemplate(template_str)

        # Extract current field values from stored JSON
        naming_fields_str = animation_data.get('naming_fields', '{}')
        try:
            self._original_fields = json.loads(naming_fields_str) if naming_fields_str else {}
        except json.JSONDecodeError:
            self._original_fields = {}

        self._version = animation_data.get('version', 1)

        # Field input widgets
        self._field_inputs: Dict[str, QLineEdit] = {}

        self._configure_window()
        self._build_ui()

    def _configure_window(self):
        """Configure window properties"""
        self.setWindowTitle("Rename Animation")
        self.setMinimumWidth(450)
        self.setModal(True)

    def _build_ui(self):
        """Build the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Current name display
        current_group = QGroupBox("Current Name")
        current_layout = QVBoxLayout(current_group)
        current_name = self._animation.get('name', 'Unknown')
        current_label = QLabel(current_name)
        current_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        current_layout.addWidget(current_label)
        layout.addWidget(current_group)

        # Field editors
        fields_group = QGroupBox("Edit Fields")
        form_layout = QFormLayout(fields_group)
        form_layout.setSpacing(12)

        # Get required fields from template
        template_fields = self._template.get_required_fields()

        # Create input for each field
        for field_name in template_fields:
            label = field_name.title()

            input_widget = QLineEdit()
            input_widget.setText(self._original_fields.get(field_name, ''))
            input_widget.setPlaceholderText(f"Enter {label.lower()}")
            input_widget.textChanged.connect(self._update_preview)

            self._field_inputs[field_name] = input_widget
            form_layout.addRow(f"{label}:", input_widget)

        # Version field (read-only)
        version_input = QLineEdit()
        version_input.setText(f"v{self._version:03d}")
        version_input.setReadOnly(True)
        version_input.setStyleSheet(
            "background-color: #2a2a2a; color: #888; font-style: italic;"
        )
        version_input.setToolTip("Version cannot be changed")
        form_layout.addRow("Version:", version_input)

        layout.addWidget(fields_group)

        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_label = QLabel("")
        self._preview_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; padding: 10px; "
            "background-color: #2a2a2a; border: 1px solid #404040;"
        )
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._preview_label)

        layout.addWidget(preview_group)

        # Apply to all versions checkbox
        self._apply_all_checkbox = QCheckBox("Apply to all versions in lineage")
        self._apply_all_checkbox.setToolTip(
            "If checked, all versions of this animation will be renamed "
            "with the new field values (each keeps its own version number)."
        )
        layout.addWidget(self._apply_all_checkbox)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #404040;")
        layout.addWidget(separator)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._rename_btn = QPushButton("Rename")
        self._rename_btn.clicked.connect(self._on_rename)
        self._rename_btn.setDefault(True)
        btn_layout.addWidget(self._rename_btn)

        layout.addLayout(btn_layout)

        # Initial preview
        self._update_preview()

    def _get_field_data(self) -> Dict[str, str]:
        """Get current field values from inputs"""
        return {
            name: input_widget.text().strip()
            for name, input_widget in self._field_inputs.items()
        }

    def _update_preview(self):
        """Update the preview based on current input values"""
        field_data = self._get_field_data()

        try:
            # Check for empty required fields
            missing = [f for f in self._template.get_required_fields() if not field_data.get(f)]
            if missing:
                self._preview_label.setText(f"Missing: {', '.join(missing)}")
                self._preview_label.setStyleSheet(
                    "font-weight: bold; font-size: 14px; padding: 10px; "
                    "background-color: #2a2a2a; border: 1px solid #404040; "
                    "color: #F44336;"
                )
                self._rename_btn.setEnabled(False)
                return

            # Generate preview name
            new_name = self._template.render(field_data, self._version)
            self._preview_label.setText(new_name)
            self._preview_label.setStyleSheet(
                "font-weight: bold; font-size: 14px; padding: 10px; "
                "background-color: #2a2a2a; border: 1px solid #404040; "
                "color: #4CAF50;"
            )
            self._rename_btn.setEnabled(True)
        except Exception as e:
            self._preview_label.setText(f"Error: {str(e)}")
            self._preview_label.setStyleSheet(
                "font-weight: bold; font-size: 14px; padding: 10px; "
                "background-color: #2a2a2a; border: 1px solid #404040; "
                "color: #F44336;"
            )
            self._rename_btn.setEnabled(False)

    def _prepare_rename_updates(self, field_data: Dict[str, str], version: int) -> Dict[str, Any]:
        """Prepare database update dict for rename."""
        new_name = self._template.render(field_data, version)
        return {
            'name': new_name,
            'naming_fields': json.dumps(field_data),
            'naming_template': self._template.template,
        }

    def _on_rename(self):
        """Handle rename button click"""
        field_data = self._get_field_data()
        apply_to_all = self._apply_all_checkbox.isChecked()

        try:
            if apply_to_all:
                # Rename all versions in lineage
                # For all versions: update naming fields but only rename files for current animation
                version_group_id = self._animation.get('version_group_id')
                if version_group_id:
                    versions = self._db_service.get_version_history(version_group_id)
                    for v in versions:
                        new_name_for_version = self._template.render(field_data, v['version'])
                        if v['uuid'] == self._uuid:
                            # Current animation - full rename with files
                            self._db_service.rename_animation(
                                v['uuid'],
                                new_name_for_version,
                                naming_fields=field_data,
                                naming_template=self._template.template
                            )
                        else:
                            # Other versions - just update DB metadata (they're in cold storage)
                            updates = self._prepare_rename_updates(field_data, v['version'])
                            self._db_service.update_animation(v['uuid'], updates)
            else:
                # Rename only this animation (with file rename)
                new_name = self._template.render(field_data, self._version)
                self._db_service.rename_animation(
                    self._uuid,
                    new_name,
                    naming_fields=field_data,
                    naming_template=self._template.template
                )

            # Get the new name for the signal
            new_name = self._template.render(field_data, self._version)

            self.renamed.emit(self._uuid, new_name, apply_to_all)
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Rename Error", f"Failed to rename: {str(e)}")


class SimpleRenameDialog(QDialog):
    """
    Simple rename dialog for animations without template fields.

    Allows editing the base name but keeps version immutable.
    """

    renamed = pyqtSignal(str, str)  # uuid, new_name

    def __init__(
        self,
        animation_uuid: str,
        current_name: str,
        version: int,
        parent=None
    ):
        super().__init__(parent)

        self._uuid = animation_uuid
        self._current_name = current_name
        self._version = version
        self._db_service = get_database_service()

        # Parse base name (remove version suffix if present)
        self._base_name = self._extract_base_name(current_name, version)

        self._configure_window()
        self._build_ui()

    def _extract_base_name(self, name: str, version: int) -> str:
        """Extract base name by removing version suffix."""
        import re
        # Try common version patterns: _v001, _v1, -v001, .v001
        patterns = [
            rf'[_\-\.]v{version:03d}$',
            rf'[_\-\.]v{version}$',
            rf'_v{version:03d}$',
            rf'_v{version}$',
        ]
        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return name[:match.start()]
        return name

    def _configure_window(self):
        """Configure window properties"""
        self.setWindowTitle("Rename Animation")
        self.setMinimumWidth(400)
        self.setModal(True)

    def _build_ui(self):
        """Build the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Current name display
        current_group = QGroupBox("Current Name")
        current_layout = QVBoxLayout(current_group)
        current_label = QLabel(self._current_name)
        current_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        current_layout.addWidget(current_label)
        layout.addWidget(current_group)

        # Edit section
        edit_group = QGroupBox("Edit Name")
        form_layout = QFormLayout(edit_group)
        form_layout.setSpacing(12)

        # Base name input
        self._name_input = QLineEdit()
        self._name_input.setText(self._base_name)
        self._name_input.textChanged.connect(self._update_preview)
        form_layout.addRow("Base Name:", self._name_input)

        # Version (read-only)
        version_input = QLineEdit()
        version_input.setText(f"v{self._version:03d}")
        version_input.setReadOnly(True)
        version_input.setStyleSheet(
            "background-color: #2a2a2a; color: #888; font-style: italic;"
        )
        version_input.setToolTip("Version cannot be changed")
        form_layout.addRow("Version:", version_input)

        layout.addWidget(edit_group)

        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self._preview_label = QLabel("")
        self._preview_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; padding: 10px; "
            "background-color: #2a2a2a; border: 1px solid #404040;"
        )
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._preview_label)
        layout.addWidget(preview_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._rename_btn = QPushButton("Rename")
        self._rename_btn.clicked.connect(self._on_rename)
        self._rename_btn.setDefault(True)
        btn_layout.addWidget(self._rename_btn)

        layout.addLayout(btn_layout)

        # Initial preview
        self._update_preview()

    def _update_preview(self):
        """Update preview with new name"""
        base_name = self._name_input.text().strip()

        if not base_name:
            self._preview_label.setText("Name cannot be empty")
            self._preview_label.setStyleSheet(
                "font-weight: bold; font-size: 14px; padding: 10px; "
                "background-color: #2a2a2a; border: 1px solid #404040; "
                "color: #F44336;"
            )
            self._rename_btn.setEnabled(False)
            return

        # Generate new name with version
        new_name = f"{base_name}_v{self._version:03d}"
        self._preview_label.setText(new_name)
        self._preview_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; padding: 10px; "
            "background-color: #2a2a2a; border: 1px solid #404040; "
            "color: #4CAF50;"
        )
        self._rename_btn.setEnabled(True)

    def _on_rename(self):
        """Handle rename button click"""
        base_name = self._name_input.text().strip()

        if not base_name:
            QMessageBox.warning(self, "Error", "Name cannot be empty")
            return

        try:
            new_name = f"{base_name}_v{self._version:03d}"
            # Use rename_animation to handle folder/file renaming
            self._db_service.rename_animation(self._uuid, new_name)
            self.renamed.emit(self._uuid, new_name)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Rename Error", f"Failed to rename: {str(e)}")


def show_rename_dialog(
    animation_uuid: str,
    animation_data: Dict[str, Any],
    parent=None
) -> Optional[str]:
    """
    Show the appropriate rename dialog based on whether animation has naming fields.

    Version is ALWAYS immutable regardless of dialog type.

    Args:
        animation_uuid: UUID of animation to rename
        animation_data: Full animation data dict
        parent: Parent widget

    Returns:
        New name if renamed, None if cancelled
    """
    # Check if animation has naming fields (was created with studio naming in Blender)
    has_naming_fields = bool(animation_data.get('naming_fields'))
    has_template = bool(animation_data.get('naming_template'))

    version = animation_data.get('version', 1)

    if has_naming_fields and has_template:
        # Use field-based rename dialog (template fields + immutable version)
        dialog = RenameDialog(animation_uuid, animation_data, parent)
    else:
        # Use simple rename dialog (base name + immutable version)
        dialog = SimpleRenameDialog(
            animation_uuid,
            animation_data.get('name', ''),
            version,
            parent
        )

    if dialog.exec():
        # Return the new name (stored in the dialog after successful rename)
        return animation_data.get('name')  # Will be updated by signal
    return None


__all__ = ['RenameDialog', 'SimpleRenameDialog', 'show_rename_dialog']
