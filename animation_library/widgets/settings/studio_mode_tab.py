"""
StudioModeTab - Settings tab for Solo/Studio mode switching and user management
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QRadioButton, QButtonGroup,
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from ...services.notes_database import get_notes_database
from ...services.permissions import NotePermissions, ROLE_LABELS, ROLE_COLORS


class UserManagementDialog(QDialog):
    """Dialog for managing studio users (Admin only)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notes_db = get_notes_database()
        self._setup_ui()
        self._load_users()

    def _setup_ui(self):
        self.setWindowTitle("User Management")
        self.setModal(True)
        self.resize(500, 400)

        # Sharp styling
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3a3a3a;
                border-radius: 0px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #555;
                border-radius: 0px;
                padding: 6px 8px;
                color: #e0e0e0;
            }
            QLineEdit:focus {
                border-color: #3A8FB7;
            }
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #555;
                border-radius: 0px;
                padding: 6px 8px;
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 0px;
                padding: 6px 16px;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QTableWidget {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                gridline-color: #2a2a2a;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                border: none;
                border-bottom: 1px solid #3a3a3a;
                padding: 6px;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)

        # Users table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Username", "Display Name", "Role", "Active"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 60)

        layout.addWidget(self._table)

        # Add user section
        add_group = QGroupBox("Add New User")
        add_layout = QHBoxLayout(add_group)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("Username")
        add_layout.addWidget(self._username_input)

        self._display_name_input = QLineEdit()
        self._display_name_input.setPlaceholderText("Display Name")
        add_layout.addWidget(self._display_name_input)

        self._role_combo = QComboBox()
        for role_key, role_label in ROLE_LABELS.items():
            self._role_combo.addItem(role_label, role_key)
        add_layout.addWidget(self._role_combo)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_add_user)
        add_layout.addWidget(add_btn)

        layout.addWidget(add_group)

        # Action buttons
        btn_layout = QHBoxLayout()

        edit_btn = QPushButton("Edit Role")
        edit_btn.clicked.connect(self._on_edit_user)
        btn_layout.addWidget(edit_btn)

        toggle_btn = QPushButton("Toggle Active")
        toggle_btn.clicked.connect(self._on_toggle_active)
        btn_layout.addWidget(toggle_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_users(self):
        users = self._notes_db.get_all_users(include_inactive=True)
        self._table.setRowCount(len(users))

        for row, user in enumerate(users):
            self._table.setItem(row, 0, QTableWidgetItem(user['username']))
            self._table.setItem(row, 1, QTableWidgetItem(user['display_name']))

            role_item = QTableWidgetItem(ROLE_LABELS.get(user['role'], user['role']))
            role_color = ROLE_COLORS.get(user['role'], '#888')
            role_item.setForeground(QColor(role_color))
            self._table.setItem(row, 2, role_item)

            active_item = QTableWidgetItem("Yes" if user['is_active'] else "No")
            if not user['is_active']:
                active_item.setForeground(QColor('#666'))
            self._table.setItem(row, 3, active_item)

    def _on_add_user(self):
        username = self._username_input.text().strip().lower()
        display_name = self._display_name_input.text().strip()
        role = self._role_combo.currentData()

        if not username or not display_name:
            QMessageBox.warning(self, "Error", "Username and display name are required.")
            return

        if self._notes_db.add_user(username, display_name, role):
            self._username_input.clear()
            self._display_name_input.clear()
            self._load_users()
        else:
            QMessageBox.warning(self, "Error", "Failed to add user. Username may already exist.")

    def _on_edit_user(self):
        selected = self._table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        username = self._table.item(row, 0).text()
        current_display = self._table.item(row, 1).text()

        # Simple edit - just update role for now
        from PyQt6.QtWidgets import QInputDialog
        roles = list(ROLE_LABELS.values())
        current_role_label = self._table.item(row, 2).text()
        current_idx = roles.index(current_role_label) if current_role_label in roles else 0

        new_role_label, ok = QInputDialog.getItem(
            self, "Edit User Role",
            f"Select role for {username}:",
            roles, current_idx, False
        )

        if ok:
            # Find role key from label
            new_role = next(k for k, v in ROLE_LABELS.items() if v == new_role_label)
            if self._notes_db.update_user(username, role=new_role):
                self._load_users()
            else:
                QMessageBox.warning(self, "Error", "Failed to update user.")

    def _on_toggle_active(self):
        selected = self._table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        username = self._table.item(row, 0).text()
        is_active = self._table.item(row, 3).text() == "Yes"

        if is_active:
            if self._notes_db.deactivate_user(username):
                self._load_users()
        else:
            if self._notes_db.reactivate_user(username):
                self._load_users()


class StudioModeTab(QWidget):
    """Settings tab for Solo/Studio mode configuration."""

    mode_changed = pyqtSignal(bool)  # True = studio mode

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._notes_db = get_notes_database()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        # Sharp styling for the tab
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3a3a3a;
                border-radius: 0px;
                margin-top: 12px;
                padding: 12px;
                padding-top: 24px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #e0e0e0;
            }
            QRadioButton {
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 0px;
            }
            QRadioButton::indicator:unchecked {
                background-color: #2a2a2a;
                border: 1px solid #555;
            }
            QRadioButton::indicator:checked {
                background-color: #3A8FB7;
                border: 1px solid #3A8FB7;
            }
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #555;
                border-radius: 0px;
                padding: 6px 10px;
                color: #e0e0e0;
                min-width: 180px;
            }
            QComboBox:hover {
                border-color: #666;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 0px;
                padding: 8px 16px;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Mode selection group
        mode_group = QGroupBox("Application Mode")
        mode_layout = QVBoxLayout(mode_group)

        self._mode_btn_group = QButtonGroup(self)

        # Solo mode option
        self._solo_radio = QRadioButton("Solo Mode (Single User)")
        self._solo_radio.setStyleSheet("font-weight: bold; font-size: 12px;")
        mode_layout.addWidget(self._solo_radio)

        solo_desc = QLabel("No restrictions. Simple workflow for individual use.")
        solo_desc.setStyleSheet("color: #888; margin-left: 22px; margin-bottom: 12px; font-size: 11px;")
        mode_layout.addWidget(solo_desc)

        # Studio mode option
        self._studio_radio = QRadioButton("Studio Mode (Multi-User)")
        self._studio_radio.setStyleSheet("font-weight: bold; font-size: 12px;")
        mode_layout.addWidget(self._studio_radio)

        studio_desc = QLabel("Role-based permissions. Audit trail. Soft delete with restore.")
        studio_desc.setStyleSheet("color: #888; margin-left: 22px; font-size: 11px;")
        mode_layout.addWidget(studio_desc)

        self._mode_btn_group.addButton(self._solo_radio, 0)
        self._mode_btn_group.addButton(self._studio_radio, 1)
        self._mode_btn_group.idToggled.connect(self._on_mode_changed)

        layout.addWidget(mode_group)

        # User selection group (only visible in studio mode)
        self._user_group = QGroupBox("Current User")
        user_layout = QVBoxLayout(self._user_group)

        user_row = QHBoxLayout()

        user_label = QLabel("User:")
        user_label.setStyleSheet("font-size: 12px;")
        user_row.addWidget(user_label)

        self._user_combo = QComboBox()
        self._user_combo.setMinimumWidth(200)
        self._user_combo.currentIndexChanged.connect(self._on_user_changed)
        user_row.addWidget(self._user_combo)

        user_row.addStretch()

        # Role badge - sharp corners
        self._role_badge = QLabel("")
        self._role_badge.setStyleSheet("""
            QLabel {
                padding: 4px 10px;
                border-radius: 0px;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        user_row.addWidget(self._role_badge)

        user_layout.addLayout(user_row)

        # Manage users button (admin only)
        self._manage_users_btn = QPushButton("Manage Users...")
        self._manage_users_btn.clicked.connect(self._on_manage_users)
        user_layout.addWidget(self._manage_users_btn)

        layout.addWidget(self._user_group)

        # Permissions info
        self._permissions_group = QGroupBox("Your Permissions")
        perm_layout = QVBoxLayout(self._permissions_group)

        self._perm_labels = {}
        permissions = [
            ('add', 'Add notes'),
            ('edit', 'Edit own notes'),
            ('delete', 'Delete notes'),
            ('restore', 'Restore deleted notes'),
            ('view_deleted', 'View deleted notes'),
            ('manage_users', 'Manage users')
        ]

        for key, label in permissions:
            perm_row = QHBoxLayout()
            perm_label = QLabel(label)
            perm_row.addWidget(perm_label)
            perm_row.addStretch()
            status = QLabel("--")
            self._perm_labels[key] = status
            perm_row.addWidget(status)
            perm_layout.addLayout(perm_row)

        layout.addWidget(self._permissions_group)

        layout.addStretch()

    def _load_settings(self):
        """Load current settings from database."""
        is_studio = self._notes_db.is_studio_mode()
        current_user = self._notes_db.get_current_user()

        if is_studio:
            self._studio_radio.setChecked(True)
        else:
            self._solo_radio.setChecked(True)

        self._update_user_combo()

        # Select current user
        if current_user:
            idx = self._user_combo.findData(current_user)
            if idx >= 0:
                self._user_combo.setCurrentIndex(idx)

        self._update_ui_visibility()

    def _update_user_combo(self):
        """Refresh user dropdown."""
        self._user_combo.blockSignals(True)
        self._user_combo.clear()

        users = self._notes_db.get_all_users()
        for user in users:
            display = f"{user['display_name']} ({user['username']})"
            self._user_combo.addItem(display, user['username'])

        self._user_combo.blockSignals(False)

    def _update_ui_visibility(self):
        """Update visibility based on mode."""
        is_studio = self._studio_radio.isChecked()

        self._user_group.setVisible(is_studio)
        self._permissions_group.setVisible(is_studio)

        if is_studio:
            self._update_role_badge()
            self._update_permissions_display()

    def _update_role_badge(self):
        """Update role badge for current user."""
        username = self._user_combo.currentData()
        if not username:
            self._role_badge.setText("")
            return

        user = self._notes_db.get_user(username)
        if user:
            role = user.get('role', 'artist')
            role_label = ROLE_LABELS.get(role, role)
            role_color = ROLE_COLORS.get(role, '#888')

            self._role_badge.setText(role_label.upper())
            self._role_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {role_color};
                    color: white;
                    padding: 4px 10px;
                    border-radius: 0px;
                    font-weight: bold;
                    font-size: 11px;
                }}
            """)

            # Show/hide manage users button based on permission
            can_manage = NotePermissions.can_manage_users(True, role)
            self._manage_users_btn.setVisible(can_manage)

    def _update_permissions_display(self):
        """Update permissions display for current user."""
        username = self._user_combo.currentData()
        user = self._notes_db.get_user(username) if username else None
        role = user.get('role', 'artist') if user else 'artist'

        def set_perm(key: str, allowed: bool):
            label = self._perm_labels.get(key)
            if label:
                if allowed:
                    label.setText("Yes")
                    label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                else:
                    label.setText("No")
                    label.setStyleSheet("color: #666;")

        set_perm('add', NotePermissions.can_add_note(True, role))
        set_perm('edit', True)  # Can always edit own
        set_perm('delete', NotePermissions.can_delete_note(True, role, '', ''))
        set_perm('restore', NotePermissions.can_restore_note(True, role))
        set_perm('view_deleted', NotePermissions.can_view_deleted(True, role))
        set_perm('manage_users', NotePermissions.can_manage_users(True, role))

    def _on_mode_changed(self, button_id: int, checked: bool):
        """Handle mode radio button change."""
        if checked:
            self._update_ui_visibility()

    def _on_user_changed(self, index: int):
        """Handle user selection change."""
        self._update_role_badge()
        self._update_permissions_display()

    def _on_manage_users(self):
        """Open user management dialog."""
        dialog = UserManagementDialog(self)
        dialog.exec()
        self._update_user_combo()
        self._update_role_badge()
        self._update_permissions_display()

    def save_settings(self):
        """Save settings to database."""
        is_studio = self._studio_radio.isChecked()
        current_user = self._user_combo.currentData() or ''

        self._notes_db.set_setting('app_mode', 'studio' if is_studio else 'solo')
        self._notes_db.set_setting('current_user', current_user)


__all__ = ['StudioModeTab']
