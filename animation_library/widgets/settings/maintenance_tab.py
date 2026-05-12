"""
MaintenanceTab - Database maintenance and status settings

Provides UI for:
- Database schema version status
- Manual schema upgrade trigger
- Integrity check
- Database optimization (VACUUM)
- Backup management
"""

from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QAbstractItemView
)
from PyQt6.QtCore import Qt

from ...services.database_service import get_database_service
from ...services.database import SCHEMA_VERSION
from ...services.notes_database import get_notes_database


class MaintenanceTab(QWidget):
    """Database maintenance settings tab"""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._db_service = get_database_service()
        self._init_ui()

    def _init_ui(self):
        """Initialize UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Sharp button style
        self._button_style = """
            QPushButton {
                border-radius: 0px;
            }
        """

        # Database Status Group
        layout.addWidget(self._create_status_section())

        # Maintenance Actions Group
        layout.addWidget(self._create_maintenance_section())

        # Activity Log Group (Option B Phase 6 — surfaces the previously
        # write-only audit log)
        layout.addWidget(self._create_activity_log_section())
        # Initial load of recent activity. Surface-level only — failure
        # here shouldn't block the rest of the tab from opening.
        try:
            self._load_activity()
        except Exception as e:
            print(f"Initial activity log load failed: {e}")

        layout.addStretch()

        # Note at bottom
        note = QLabel(
            "Note: A backup is automatically created before any schema upgrade. "
            "Your animations are preserved - only new features are added."
        )
        note.setWordWrap(True)
        self._apply_secondary_style(note)
        layout.addWidget(note)

    def _create_status_section(self):
        """Create database status section"""
        group = QGroupBox("Database Status")
        group_layout = QVBoxLayout(group)

        # Get database stats
        stats = self._db_service.get_database_stats()

        # Schema version row
        version_layout = QHBoxLayout()

        current_version = stats['schema_version']
        latest_version = stats['latest_version']

        if stats['needs_upgrade']:
            version_text = f"<b>Schema Version:</b>  {current_version}  →  {latest_version} available"
            self._version_label = QLabel(version_text)
            self._version_label.setStyleSheet("color: #FFA500;")  # Orange for needs upgrade
        else:
            version_text = f"<b>Schema Version:</b>  {current_version}  (Up to date)"
            self._version_label = QLabel(version_text)
            self._version_label.setStyleSheet("color: #4CAF50;")  # Green for up to date

        version_layout.addWidget(self._version_label)
        version_layout.addStretch()

        # Upgrade/Refresh button
        if stats['needs_upgrade']:
            self._upgrade_btn = QPushButton("Upgrade Now")
            self._upgrade_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 0px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self._upgrade_btn.clicked.connect(self._on_upgrade_clicked)
        else:
            self._upgrade_btn = QPushButton("Check Again")
            self._upgrade_btn.setStyleSheet(self._button_style)
            self._upgrade_btn.clicked.connect(self._refresh_status)

        version_layout.addWidget(self._upgrade_btn)
        group_layout.addLayout(version_layout)

        group_layout.addSpacing(10)

        # Database info
        info_text = (
            f"<b>Database Size:</b> {stats['db_size_mb']} MB<br>"
            f"<b>Animations:</b> {stats['animation_count']}  |  "
            f"<b>Folders:</b> {stats['folder_count']}  |  "
            f"<b>Archived:</b> {stats['archive_count']}"
        )
        self._info_label = QLabel(info_text)
        group_layout.addWidget(self._info_label)

        # Pending features (if upgrade available)
        if stats['needs_upgrade'] and stats['pending_features']:
            group_layout.addSpacing(10)

            features_text = "<b>New features available:</b><br>"
            for feature in stats['pending_features']:
                features_text += f"  • {feature}<br>"

            self._features_label = QLabel(features_text)
            self._features_label.setStyleSheet("color: #2196F3;")
            group_layout.addWidget(self._features_label)

        return group

    def _create_maintenance_section(self):
        """Create maintenance actions section"""
        group = QGroupBox("Database Maintenance")
        group_layout = QVBoxLayout(group)

        # Integrity Check button
        integrity_layout = QHBoxLayout()
        integrity_btn = QPushButton("Run Integrity Check")
        integrity_btn.setStyleSheet(self._button_style)
        integrity_btn.clicked.connect(self._on_integrity_check)
        integrity_layout.addWidget(integrity_btn)

        integrity_desc = QLabel("Verify database health and foreign key constraints")
        self._apply_secondary_style(integrity_desc)
        integrity_layout.addWidget(integrity_desc)
        integrity_layout.addStretch()

        group_layout.addLayout(integrity_layout)
        group_layout.addSpacing(10)

        # Optimize button
        optimize_layout = QHBoxLayout()
        optimize_btn = QPushButton("Optimize Database")
        optimize_btn.setStyleSheet(self._button_style)
        optimize_btn.clicked.connect(self._on_optimize)
        optimize_layout.addWidget(optimize_btn)

        optimize_desc = QLabel("Reclaim unused space (VACUUM)")
        self._apply_secondary_style(optimize_desc)
        optimize_layout.addWidget(optimize_desc)
        optimize_layout.addStretch()

        group_layout.addLayout(optimize_layout)
        group_layout.addSpacing(10)

        # View Backups button
        backups_layout = QHBoxLayout()
        backups_btn = QPushButton("View Backups")
        backups_btn.setStyleSheet(self._button_style)
        backups_btn.clicked.connect(self._on_view_backups)
        backups_layout.addWidget(backups_btn)

        backups_desc = QLabel("Manage automatic pre-migration backups")
        self._apply_secondary_style(backups_desc)
        backups_layout.addWidget(backups_desc)
        backups_layout.addStretch()

        group_layout.addLayout(backups_layout)
        group_layout.addSpacing(10)

        # Rebuild Database button
        rebuild_layout = QHBoxLayout()
        rebuild_btn = QPushButton("Rebuild Database")
        rebuild_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border-radius: 0px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
        """)
        rebuild_btn.clicked.connect(self._on_rebuild_database)
        rebuild_layout.addWidget(rebuild_btn)

        rebuild_desc = QLabel("Clear database and reimport all animations from files")
        self._apply_secondary_style(rebuild_desc)
        rebuild_layout.addWidget(rebuild_desc)
        rebuild_layout.addStretch()

        group_layout.addLayout(rebuild_layout)

        return group

    def _create_activity_log_section(self):
        """Create the Activity Log section (Option B Phase 6).

        Surfaces the audit trail that was previously written but never
        read. Notes-only for now (drawover audit log is a sibling table
        with a different shape; future work).
        """
        group = QGroupBox("Activity Log")
        group_layout = QVBoxLayout(group)

        desc = QLabel(
            "Recent actions on review notes (latest 100 entries). "
            "Read-only audit trail."
        )
        desc.setWordWrap(True)
        self._apply_secondary_style(desc)
        group_layout.addWidget(desc)

        # Read-only table.
        self._activity_table = QTableWidget()
        self._activity_table.setColumnCount(5)
        self._activity_table.setHorizontalHeaderLabels(
            ["Time", "Actor", "Action", "Frame", "Note"]
        )
        self._activity_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._activity_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._activity_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._activity_table.verticalHeader().setVisible(False)
        self._activity_table.setMinimumHeight(220)
        self._activity_table.setAlternatingRowColors(True)

        header = self._activity_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)   # Time
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)   # Actor
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)   # Action
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)   # Frame
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Note
        self._activity_table.setColumnWidth(0, 145)
        self._activity_table.setColumnWidth(1, 110)
        self._activity_table.setColumnWidth(2, 90)
        self._activity_table.setColumnWidth(3, 60)

        group_layout.addWidget(self._activity_table)

        # Refresh button row.
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._refresh_activity_btn = QPushButton("Refresh")
        self._refresh_activity_btn.setStyleSheet(self._button_style)
        self._refresh_activity_btn.clicked.connect(self._load_activity)
        btn_layout.addWidget(self._refresh_activity_btn)
        group_layout.addLayout(btn_layout)

        return group

    def _load_activity(self):
        """Re-query the audit log and repopulate the activity table."""
        notes_db = get_notes_database()
        try:
            entries = notes_db.get_recent_activity(limit=100)
        except Exception as e:
            # Defensive — DB might not be initialized in some edge paths.
            print(f"Activity log query failed: {e}")
            entries = []

        if not entries:
            # Show an empty-state row spanning all columns.
            self._activity_table.setRowCount(1)
            empty = QTableWidgetItem("No recorded activity yet.")
            empty.setFlags(Qt.ItemFlag.ItemIsEnabled)
            empty.setForeground(Qt.GlobalColor.gray)
            self._activity_table.setItem(0, 0, empty)
            self._activity_table.setSpan(0, 0, 1, 5)
            return

        # Clear any previous span before re-populating.
        self._activity_table.clearSpans()
        self._activity_table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            timestamp = str(entry.get('timestamp', '') or '')
            actor = entry.get('actor', '') or '(unknown)'
            action_raw = entry.get('action', '') or ''
            action = action_raw.replace('_', ' ').title()
            frame = entry.get('frame', 0)
            note_preview = (entry.get('note_preview', '') or '')
            # Single-line preview, capped — keeps table tidy.
            note_preview = note_preview.replace('\n', ' ').strip()
            if len(note_preview) > 90:
                note_preview = note_preview[:87] + '...'

            self._activity_table.setItem(row, 0, QTableWidgetItem(timestamp))
            self._activity_table.setItem(row, 1, QTableWidgetItem(actor))
            self._activity_table.setItem(row, 2, QTableWidgetItem(action))
            self._activity_table.setItem(row, 3, QTableWidgetItem(f"f{frame}"))
            self._activity_table.setItem(row, 4, QTableWidgetItem(note_preview))

    def _apply_secondary_style(self, label):
        """Apply secondary text styling to a label"""
        current_theme = self.theme_manager.get_current_theme()
        if current_theme:
            palette = current_theme.palette
            label.setStyleSheet(
                f"font-style: italic; color: {palette.text_secondary};"
            )
        else:
            label.setStyleSheet("font-style: italic; color: gray;")

    def _refresh_status(self):
        """Refresh the status display"""
        stats = self._db_service.get_database_stats()

        current_version = stats['schema_version']
        latest_version = stats['latest_version']

        if stats['needs_upgrade']:
            version_text = f"<b>Schema Version:</b>  {current_version}  →  {latest_version} available"
            self._version_label.setText(version_text)
            self._version_label.setStyleSheet("color: #FFA500;")
            self._upgrade_btn.setText("Upgrade Now")
            self._upgrade_btn.clicked.disconnect()
            self._upgrade_btn.clicked.connect(self._on_upgrade_clicked)
            self._upgrade_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 0px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            version_text = f"<b>Schema Version:</b>  {current_version}  (Up to date)"
            self._version_label.setText(version_text)
            self._version_label.setStyleSheet("color: #4CAF50;")
            self._upgrade_btn.setText("Check Again")
            self._upgrade_btn.setStyleSheet(self._button_style)

        info_text = (
            f"<b>Database Size:</b> {stats['db_size_mb']} MB<br>"
            f"<b>Animations:</b> {stats['animation_count']}  |  "
            f"<b>Folders:</b> {stats['folder_count']}  |  "
            f"<b>Archived:</b> {stats['archive_count']}"
        )
        self._info_label.setText(info_text)

        QMessageBox.information(
            self,
            "Status Refreshed",
            f"Database is at schema version {current_version}.\n"
            f"Latest available: {latest_version}."
        )

    def _on_upgrade_clicked(self):
        """Handle upgrade button click"""
        stats = self._db_service.get_database_stats()

        if not stats['needs_upgrade']:
            QMessageBox.information(
                self,
                "Already Up to Date",
                "Your database is already at the latest schema version."
            )
            return

        # Confirm upgrade
        pending = stats['pending_features']
        features_text = "\n".join(f"  • {f}" for f in pending) if pending else "  (Various improvements)"

        reply = QMessageBox.question(
            self,
            "Upgrade Database Schema",
            f"Upgrade database from version {stats['schema_version']} to {stats['latest_version']}?\n\n"
            f"New features:\n{features_text}\n\n"
            f"A backup will be created automatically before the upgrade.\n"
            f"Your existing animations will be preserved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Run upgrade
        success, message = self._db_service.run_schema_upgrade()

        if success:
            QMessageBox.information(
                self,
                "Upgrade Complete",
                f"Database upgraded successfully!\n\n{message}"
            )
            self._refresh_status()
        else:
            QMessageBox.critical(
                self,
                "Upgrade Failed",
                f"Database upgrade failed:\n\n{message}"
            )

    def _on_integrity_check(self):
        """Run integrity check"""
        is_ok, message = self._db_service.run_integrity_check()

        if is_ok:
            QMessageBox.information(
                self,
                "Integrity Check",
                f"Database integrity check passed!\n\n{message}"
            )
        else:
            QMessageBox.warning(
                self,
                "Integrity Check",
                f"Database integrity check found issues:\n\n{message}"
            )

    def _on_optimize(self):
        """Optimize database"""
        reply = QMessageBox.question(
            self,
            "Optimize Database",
            "Run VACUUM to reclaim unused space?\n\n"
            "This may take a moment for large databases.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        size_before, size_after = self._db_service.optimize_database()

        saved = size_before - size_after
        saved_mb = saved / (1024 * 1024)
        before_mb = size_before / (1024 * 1024)
        after_mb = size_after / (1024 * 1024)

        QMessageBox.information(
            self,
            "Optimization Complete",
            f"Database optimized!\n\n"
            f"Before: {before_mb:.2f} MB\n"
            f"After: {after_mb:.2f} MB\n"
            f"Saved: {saved_mb:.2f} MB"
        )

        # Refresh the displayed stats
        self._refresh_status()

    def _on_view_backups(self):
        """Show backup management dialog"""
        dialog = BackupsDialog(self._db_service, self)
        dialog.exec()

    def _on_rebuild_database(self):
        """Rebuild database by clearing and reimporting all animations"""
        # Confirm with user
        reply = QMessageBox.warning(
            self,
            "Rebuild Database",
            "This will:\n\n"
            "1. Create a backup of the current database\n"
            "2. Clear all animations from the database\n"
            "3. Reimport all animations from JSON files\n\n"
            "Use this if animations are missing or out of sync.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Create backup first
            self._db_service.create_backup()

            # Clear all animations
            cleared = self._db_service.clear_all_animations()

            # Rescan library
            total_found, newly_imported = self._db_service.sync_library()

            # Show results
            QMessageBox.information(
                self,
                "Rebuild Complete",
                f"Database rebuilt successfully!\n\n"
                f"Cleared: {cleared} old entries\n"
                f"Found: {total_found} animation folders\n"
                f"Imported: {newly_imported} animations\n\n"
                f"Please close Settings and refresh the library."
            )

            # Refresh the status display
            self._refresh_status()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Rebuild Failed",
                f"Failed to rebuild database:\n\n{str(e)}"
            )


class BackupsDialog(QDialog):
    """Dialog for viewing and managing database backups"""

    def __init__(self, db_service, parent=None):
        super().__init__(parent)
        self._db_service = db_service

        self.setWindowTitle("Database Backups")
        self.setModal(True)
        self.resize(600, 400)

        self._init_ui()
        self._load_backups()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        # Info label
        info = QLabel(
            "Backups are created automatically before schema upgrades. "
            "You can also create manual backups."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Backups table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Filename", "Size", "Date"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(2, 150)
        layout.addWidget(self._table)

        # Buttons
        btn_layout = QHBoxLayout()

        create_btn = QPushButton("Create Backup Now")
        create_btn.clicked.connect(self._create_backup)
        btn_layout.addWidget(create_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_backup)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_backups(self):
        """Load and display backups"""
        backups = self._db_service.get_backups()

        self._table.setRowCount(len(backups))

        for row, backup in enumerate(backups):
            # Filename
            filename_item = QTableWidgetItem(backup['filename'])
            filename_item.setData(Qt.ItemDataRole.UserRole, backup['path'])
            self._table.setItem(row, 0, filename_item)

            # Size
            size_item = QTableWidgetItem(f"{backup['size_mb']:.2f} MB")
            self._table.setItem(row, 1, size_item)

            # Date
            date_str = backup['date'].strftime("%Y-%m-%d %H:%M:%S")
            date_item = QTableWidgetItem(date_str)
            self._table.setItem(row, 2, date_item)

        if not backups:
            self._table.setRowCount(1)
            no_backups = QTableWidgetItem("No backups found")
            no_backups.setFlags(Qt.ItemFlag.NoItemFlags)
            self._table.setItem(0, 0, no_backups)
            self._table.setSpan(0, 0, 1, 3)

    def _create_backup(self):
        """Create a new backup"""
        try:
            backup_path = self._db_service.create_backup()
            QMessageBox.information(
                self,
                "Backup Created",
                f"Backup created successfully:\n{backup_path}"
            )
            self._load_backups()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Backup Failed",
                f"Failed to create backup:\n{str(e)}"
            )

    def _delete_backup(self):
        """Delete selected backup"""
        selected = self._table.selectedItems()
        if not selected:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select a backup to delete."
            )
            return

        # Get the path from the first column's UserRole
        row = selected[0].row()
        path_item = self._table.item(row, 0)
        if not path_item:
            return

        backup_path = path_item.data(Qt.ItemDataRole.UserRole)
        if not backup_path:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Backup",
            f"Delete this backup?\n\n{Path(backup_path).name}\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Delete
        if self._db_service.delete_backup(Path(backup_path)):
            QMessageBox.information(
                self,
                "Deleted",
                "Backup deleted successfully."
            )
            self._load_backups()
        else:
            QMessageBox.warning(
                self,
                "Delete Failed",
                "Failed to delete backup."
            )


__all__ = ['MaintenanceTab']
