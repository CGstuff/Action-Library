"""
LibraryTab - Library management, export and import settings

Provides UI for:
- Database location and info display
- Export library to .animlib archive
- Import library from .animlib archive
- Database reset functionality
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QFileDialog, QMessageBox,
    QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ...config import Config
from ...services.backup_service import BackupService
from ...services.database_service import get_database_service


class ExportWorker(QThread):
    """Background worker for export operation"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, library_path, output_path):
        super().__init__()
        self.library_path = library_path
        self.output_path = output_path

    def run(self):
        try:
            success = BackupService.export_library(
                self.library_path,
                self.output_path,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m)
            )
            self.finished.emit(success, "Export complete!" if success else "Export failed")
        except Exception as e:
            self.finished.emit(False, str(e))


class ImportWorker(QThread):
    """Background worker for import operation"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict)

    def __init__(self, archive_path, library_path):
        super().__init__()
        self.archive_path = archive_path
        self.library_path = library_path

    def run(self):
        stats = BackupService.import_library(
            self.archive_path,
            self.library_path,
            progress_callback=lambda c, t, m: self.progress.emit(c, t, m)
        )
        self.finished.emit(stats)


class LibraryTab(QWidget):
    """Library management settings tab"""

    # Signal emitted when library import completes successfully
    library_imported = pyqtSignal()

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._worker = None
        self._progress_dialog = None
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

        # Database Info Group
        layout.addWidget(self._create_database_section())

        # Export Group
        layout.addWidget(self._create_export_section())

        # Import Group
        layout.addWidget(self._create_import_section())

        layout.addStretch()

    def _create_database_section(self):
        """Create database information section"""
        group = QGroupBox("Database Location")
        group_layout = QVBoxLayout(group)

        # Get database info
        db_path = Config.get_database_path()
        db_exists = db_path.exists()

        # Path display
        path_label = QLabel(f"<b>Path:</b> {db_path}")
        path_label.setWordWrap(True)
        group_layout.addWidget(path_label)

        # Size and animation count
        if db_exists:
            size_mb = db_path.stat().st_size / (1024 * 1024)
            db_service = get_database_service()
            anim_count = db_service.get_animation_count()
            info_label = QLabel(f"<b>Size:</b> {size_mb:.2f} MB  |  <b>Animations:</b> {anim_count}")
        else:
            info_label = QLabel("<i>Database not yet created</i>")

        group_layout.addWidget(info_label)

        group_layout.addSpacing(10)

        # Button
        open_btn = QPushButton("Open Folder")
        open_btn.setStyleSheet(self._button_style)
        open_btn.clicked.connect(self._open_database_folder)
        group_layout.addWidget(open_btn)

        return group

    def _create_export_section(self):
        """Create export section"""
        group = QGroupBox("Export Library")
        group_layout = QVBoxLayout(group)

        desc = QLabel(
            "Create a backup of your entire animation library. "
            "Includes all animations, previews, thumbnails, and metadata."
        )
        desc.setWordWrap(True)
        group_layout.addWidget(desc)

        group_layout.addSpacing(5)

        export_btn = QPushButton("Export Library...")
        export_btn.setStyleSheet(self._button_style)
        export_btn.clicked.connect(self._export_library)
        group_layout.addWidget(export_btn)

        # Tip
        tip = QLabel("Tip: Backup regularly to an external drive or cloud storage.")
        tip.setWordWrap(True)
        self._apply_secondary_style(tip)
        group_layout.addWidget(tip)

        return group

    def _create_import_section(self):
        """Create import section"""
        group = QGroupBox("Import Library")
        group_layout = QVBoxLayout(group)

        desc = QLabel(
            "Restore animations from a .animlib backup. "
            "You can choose how to handle conflicts with existing animations."
        )
        desc.setWordWrap(True)
        group_layout.addWidget(desc)

        group_layout.addSpacing(5)

        import_btn = QPushButton("Import Library...")
        import_btn.setStyleSheet(self._button_style)
        import_btn.clicked.connect(self._import_library)
        group_layout.addWidget(import_btn)

        # Note
        note = QLabel("Note: Large libraries may take several minutes to import.")
        note.setWordWrap(True)
        self._apply_secondary_style(note)
        group_layout.addWidget(note)

        return group

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

    def _open_database_folder(self):
        """Open the database folder in file explorer"""
        db_folder = Config.get_database_folder()

        if not db_folder.exists():
            QMessageBox.warning(
                self,
                "Folder Not Found",
                f"The database folder does not exist:\n{db_folder}"
            )
            return

        try:
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', str(db_folder)])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(db_folder)])
            else:
                subprocess.Popen(['xdg-open', str(db_folder)])
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open folder:\n{e}"
            )

    def _export_library(self):
        """Export library to .animlib file"""
        library_path = Config.load_library_path()
        if not library_path or not library_path.exists():
            QMessageBox.warning(
                self,
                "No Library",
                "No animation library is configured.\n\n"
                "Please set up a library location first."
            )
            return

        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"ActionLibrary_Backup_{timestamp}.animlib"

        # Get save location
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Library",
            str(Path.home() / default_name),
            "Animation Library Archive (*.animlib)"
        )

        if not output_path:
            return

        # Create progress dialog
        self._progress_dialog = QProgressDialog(
            "Preparing export...",
            "Cancel",
            0, 100,
            self
        )
        self._progress_dialog.setWindowTitle("Exporting Library")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)

        # Start worker
        self._worker = ExportWorker(library_path, Path(output_path))
        self._worker.progress.connect(self._on_export_progress)
        self._worker.finished.connect(self._on_export_finished)
        self._progress_dialog.canceled.connect(self._worker.terminate)
        self._worker.start()

    def _on_export_progress(self, current, total, message):
        """Handle export progress updates"""
        dialog = self._progress_dialog
        if dialog:
            if total > 0:
                percent = int((current / total) * 100)
                dialog.setValue(percent)
            dialog.setLabelText(message)

    def _on_export_finished(self, success, message):
        """Handle export completion"""
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None

        if success:
            QMessageBox.information(
                self,
                "Export Complete",
                "Library exported successfully!"
            )
        else:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Failed to export library:\n{message}"
            )

        self._worker = None

    def _import_library(self):
        """Import library from .animlib file"""
        library_path = Config.load_library_path()
        if not library_path:
            QMessageBox.warning(
                self,
                "No Library",
                "No animation library is configured.\n\n"
                "Please set up a library location first."
            )
            return

        # Get archive file
        archive_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Library",
            str(Path.home()),
            "Animation Library Archive (*.animlib)"
        )

        if not archive_path:
            return

        archive_path = Path(archive_path)

        # Validate archive
        is_valid, message = BackupService.validate_archive(archive_path)
        if not is_valid:
            QMessageBox.warning(
                self,
                "Invalid Archive",
                f"Cannot import this archive:\n{message}"
            )
            return

        # Get archive info
        info = BackupService.get_archive_info(archive_path)
        if info:
            info_text = (
                f"Archive contains {info.get('animation_count', 'unknown')} animations\n"
                f"Total size: {info.get('total_size_mb', 0):.1f} MB\n"
                f"Created: {info.get('created', 'unknown')}"
            )
        else:
            info_text = "Archive information unavailable"

        # Confirm import
        reply = QMessageBox.question(
            self,
            "Import Library",
            f"Import animations from this archive?\n\n{info_text}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Create progress dialog
        self._progress_dialog = QProgressDialog(
            "Preparing import...",
            "Cancel",
            0, 100,
            self
        )
        self._progress_dialog.setWindowTitle("Importing Library")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)

        # Start worker
        self._worker = ImportWorker(archive_path, library_path)
        self._worker.progress.connect(self._on_import_progress)
        self._worker.finished.connect(self._on_import_finished)
        self._progress_dialog.canceled.connect(self._worker.terminate)
        self._worker.start()

    def _on_import_progress(self, current, total, message):
        """Handle import progress updates"""
        dialog = self._progress_dialog
        if dialog:
            if total > 0:
                percent = int((current / total) * 100)
                dialog.setValue(percent)
            dialog.setLabelText(message)

    def _on_import_finished(self, stats):
        """Handle import completion"""
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None

        # Build result message
        message = f"Import complete!\n\n"
        message += f"Imported: {stats['imported']} files\n"

        # Show pending metadata info (will be applied after refresh)
        pending_count = stats.get('metadata_imported', 0)
        if pending_count > 0:
            message += f"Metadata to restore: {pending_count} animations\n"

        if stats['errors']:
            message += f"\nErrors: {len(stats['errors'])}"
            if len(stats['errors']) <= 5:
                message += "\n" + "\n".join(stats['errors'][:5])

        if stats['errors']:
            QMessageBox.warning(self, "Import Complete", message)
        else:
            QMessageBox.information(self, "Import Complete", message)

        # Emit signal to trigger library refresh
        if stats['imported'] > 0:
            self.library_imported.emit()

        self._worker = None


__all__ = ['LibraryTab']
