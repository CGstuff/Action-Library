"""
Export manager for VersionHistoryDialog.

Handles exporting video with annotations burned in as MP4.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Callable
import subprocess
import sys

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QProgressDialog, QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget


class AnnotatedExportWorker(QThread):
    """Background worker for exporting video with annotations."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(bool, str)       # success, message

    def __init__(
        self,
        video_path: str,
        output_path: str,
        animation_uuid: str,
        version_label: str,
        fps: int = 24,
        parent=None
    ):
        super().__init__(parent)
        self._video_path = video_path
        self._output_path = output_path
        self._animation_uuid = animation_uuid
        self._version_label = version_label
        self._fps = fps
        self._cancelled = False

    def run(self):
        """Execute the export."""
        from ....services.annotated_export_service import export_with_annotations

        success, message = export_with_annotations(
            video_path=self._video_path,
            output_path=self._output_path,
            animation_uuid=self._animation_uuid,
            version_label=self._version_label,
            fps=self._fps,
            progress_callback=self._on_progress,
            cancelled_check=self._is_cancelled
        )
        self.finished.emit(success, message)

    def _on_progress(self, current: int, total: int, message: str):
        """Emit progress signal."""
        self.progress.emit(current, total, message)

    def _is_cancelled(self) -> bool:
        """Check if export was cancelled."""
        return self._cancelled

    def cancel(self):
        """Request cancellation."""
        self._cancelled = True


class AnnotatedExportManager:
    """
    Manages the export workflow for video with annotations.

    Handles:
    - FFmpeg availability check
    - Output path generation
    - Progress dialog management
    - Worker thread lifecycle
    """

    def __init__(self, parent_widget: 'QWidget'):
        """
        Initialize export manager.

        Args:
            parent_widget: Parent widget for dialogs
        """
        self._parent = parent_widget
        self._worker: Optional[AnnotatedExportWorker] = None
        self._progress_dialog: Optional[QProgressDialog] = None
        self._output_path: Optional[str] = None

    def start_export(
        self,
        video_path: str,
        animation_uuid: str,
        version_label: str,
        animation_name: str,
        fps: int = 24
    ) -> bool:
        """
        Start exporting video with annotations.

        Args:
            video_path: Path to source video
            animation_uuid: Animation UUID
            version_label: Version label (e.g., 'v001')
            animation_name: Animation name for output filename
            fps: Frames per second

        Returns:
            True if export started successfully
        """
        from ....services.annotated_export_service import (
            find_ffmpeg, get_reviews_folder, generate_export_filename
        )
        from PyQt6.QtCore import Qt

        # Check for preview video
        if not video_path or not Path(video_path).exists():
            QMessageBox.warning(
                self._parent, "No Preview",
                "This version does not have a preview video to export."
            )
            return False

        # Check for FFmpeg
        if not find_ffmpeg():
            QMessageBox.warning(
                self._parent, "FFmpeg Required",
                "FFmpeg is required to export video with annotations.\n\n"
                "Please install FFmpeg:\n"
                "1. Download from https://ffmpeg.org/download.html\n"
                "2. Add the 'bin' folder to your system PATH\n"
                "3. Restart the application"
            )
            return False

        # Generate output filename
        filename = generate_export_filename(animation_name, version_label)
        self._output_path = str(get_reviews_folder() / filename)

        # Create progress dialog
        self._progress_dialog = QProgressDialog(
            "Preparing export...", "Cancel", 0, 100, self._parent
        )
        self._progress_dialog.setWindowTitle("Exporting with Annotations")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)
        self._progress_dialog.canceled.connect(self._on_cancelled)

        # Create and start worker
        self._worker = AnnotatedExportWorker(
            video_path=video_path,
            output_path=self._output_path,
            animation_uuid=animation_uuid,
            version_label=version_label,
            fps=fps,
            parent=self._parent
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

        return True

    def cancel(self):
        """Cancel any running export."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)

    def is_running(self) -> bool:
        """Check if an export is currently running."""
        return self._worker is not None and self._worker.isRunning()

    def _on_progress(self, current: int, total: int, message: str):
        """Handle export progress update."""
        if self._progress_dialog:
            if total > 0:
                percent = int((current / total) * 100)
                self._progress_dialog.setValue(percent)
                self._progress_dialog.setLabelText(message)
            else:
                # Indeterminate progress (encoding phase)
                self._progress_dialog.setRange(0, 0)
                self._progress_dialog.setLabelText(message)

    def _on_cancelled(self):
        """Handle export cancellation."""
        if self._worker:
            self._worker.cancel()

    def _on_finished(self, success: bool, message: str):
        """Handle export completion."""
        # Close progress dialog
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None

        if success:
            self._show_success_dialog()
        else:
            if "cancelled" not in message.lower():
                QMessageBox.critical(
                    self._parent, "Export Failed",
                    f"Failed to export video:\n\n{message}"
                )

        self._worker = None

    def _show_success_dialog(self):
        """Show success dialog with option to open folder."""
        msg_box = QMessageBox(self._parent)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Export Complete")
        msg_box.setText("Video exported successfully!")
        msg_box.setInformativeText(f"Saved to:\n{self._output_path}")

        open_btn = msg_box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)

        msg_box.exec()

        if msg_box.clickedButton() == open_btn:
            self._open_containing_folder()

    def _open_containing_folder(self):
        """Open the folder containing the exported file."""
        if not self._output_path:
            return

        folder_path = str(Path(self._output_path).parent)
        if sys.platform == 'win32':
            subprocess.run(['explorer', '/select,', self._output_path], check=False)
        elif sys.platform == 'darwin':
            subprocess.run(['open', '-R', self._output_path], check=False)
        else:
            subprocess.run(['xdg-open', folder_path], check=False)


__all__ = ['AnnotatedExportWorker', 'AnnotatedExportManager']
