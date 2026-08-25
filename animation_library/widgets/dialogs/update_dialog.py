"""
Download-and-install dialog for app updates.

The install itself can't happen while we're running - Windows locks the exe and
the loaded DLLs - so the last step is: write a swap script, launch it, quit. The
script waits for us to exit, swaps the files, and starts the new build. See
utils/update_swap.py.

The dialog is explicit about what will happen (the app closes and reopens) and
about what won't (nothing in the library is touched), because "an app that
replaces itself" is exactly the kind of thing people are right to be wary of.
"""

import logging

from PyQt6.QtCore import Qt, QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QMessageBox, QProgressBar, QPushButton,
                             QTextBrowser, QVBoxLayout)

from ...config import Config
from ...services.update_service import UpdateService, UpdateInfo, can_self_update
from ...utils import update_swap

logger = logging.getLogger(__name__)


class _DownloadSignals(QObject):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object, object)      # (staged_dir | None, error | None)


class _DownloadTask(QRunnable):
    def __init__(self, info: UpdateInfo):
        super().__init__()
        self._info = info
        self._cancelled = False
        self.signals = _DownloadSignals()

    def cancel(self):
        self._cancelled = True

    def run(self):
        service = UpdateService()
        staged, err = service.download_and_stage(
            self._info,
            progress=lambda d, t: self.signals.progress.emit(d, t),
            should_cancel=lambda: self._cancelled,
        )
        self.signals.finished.emit(staged, err)


class UpdateDialog(QDialog):
    """Shows what's new, downloads it, then hands off to the swapper."""

    def __init__(self, info: UpdateInfo, parent=None):
        super().__init__(parent)
        self._info = info
        self._task = None
        self._staged = None

        self.setWindowTitle(f"Action Library {info.version}")
        self.setMinimumSize(560, 460)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        heading = QLabel(f"<h2 style='margin:0'>Version {self._info.version} is available</h2>")
        layout.addWidget(heading)

        sub = f"You're running {Config.APP_VERSION}."
        if self._info.size_bytes:
            sub += f"  Download size: {self._info.size_mb:.0f} MB."
        layout.addWidget(QLabel(sub))

        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(self._info.notes or "_No release notes._")
        layout.addWidget(notes, 1)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self._close_btn = QPushButton("Not Now")
        self._close_btn.clicked.connect(self.reject)
        buttons.addWidget(self._close_btn)

        self._action_btn = QPushButton()
        self._action_btn.setDefault(True)
        buttons.addWidget(self._action_btn)
        layout.addLayout(buttons)

        ok, reason = can_self_update()
        if ok and self._info.download_url and update_swap.is_supported():
            self._action_btn.setText("Download && Install")
            self._action_btn.clicked.connect(self._start_download)
            self._status.setText(
                "The app will close and reopen to finish installing.\n"
                "Your library, settings and animations are not touched.")
        else:
            self._action_btn.setText("Open Release Page")
            self._action_btn.clicked.connect(self._open_page)
            self._status.setText(
                reason or "This build can't update itself - download it manually.")

    # --------------------------------------------------------------- download

    def _start_download(self):
        self._action_btn.setEnabled(False)
        self._close_btn.setText("Cancel")
        try:
            self._close_btn.clicked.disconnect()
        except TypeError:
            pass
        self._close_btn.clicked.connect(self._cancel_download)

        self._progress.setVisible(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._status.setText("Downloading...")

        self._task = _DownloadTask(self._info)
        self._task.signals.progress.connect(self._on_progress)
        self._task.signals.finished.connect(self._on_downloaded)
        QThreadPool.globalInstance().start(self._task)

    def _cancel_download(self):
        if self._task:
            self._task.cancel()
        self._status.setText("Cancelling...")

    def _on_progress(self, done: int, total: int):
        if total > 0:
            self._progress.setValue(int(done * 100 / total))
            self._status.setText(
                f"Downloading... {done/1024/1024:.0f} of {total/1024/1024:.0f} MB")
        else:
            self._progress.setRange(0, 0)

    def _on_downloaded(self, staged, error):
        self._progress.setVisible(False)
        if error:
            self._status.setText(error)
            if error != "Cancelled.":
                QMessageBox.warning(self, "Update Failed",
                                    f"{error}\n\nNothing on your computer was changed.")
            self.reject()
            return

        self._staged = staged
        self._install()

    # ---------------------------------------------------------------- install

    def _install(self):
        script, err = update_swap.write_swap_script(self._staged, self._info.version)
        if err:
            QMessageBox.warning(self, "Update Failed",
                                f"{err}\n\nNothing on your computer was changed.")
            UpdateService.clear_staging()
            self.reject()
            return

        reply = QMessageBox.question(
            self, "Restart to Finish",
            f"Action Library {self._info.version} is ready to install.\n\n"
            "The app will close, swap in the new version, and reopen.\n"
            "Your library and settings are left alone.\n\n"
            "Restart now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self._status.setText(
                "Downloaded. It will install next time you choose to update.")
            self.reject()
            return

        ok, err = update_swap.launch_swap(script)
        if not ok:
            QMessageBox.warning(self, "Update Failed",
                                f"{err}\n\nNothing on your computer was changed.")
            self.reject()
            return

        # The script is now waiting on our PID. Quit so it can proceed.
        self.accept()
        QApplication.instance().quit()

    def _open_page(self):
        QDesktopServices.openUrl(QUrl(self._info.page_url))
        self.accept()


__all__ = ['UpdateDialog']
