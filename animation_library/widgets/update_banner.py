"""
The "there's a new version" bar.

This used to live behind a Check for Updates button inside the About dialog,
which meant nobody found it - users ran months-old builds without knowing, and
one of them assumed updating the Blender addon updated the app too. So the check
now runs by itself at startup and says so across the top of the window.

Quiet when it matters: the check runs off the UI thread and stays silent on any
failure. Someone working offline, or behind a firewall that eats GitHub, must
never see an error they didn't ask for.
"""

import logging

from PyQt6.QtCore import Qt, QObject, QRunnable, QThreadPool, pyqtSignal, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..services.update_service import UpdateService, UpdateInfo, can_self_update

logger = logging.getLogger(__name__)


class _CheckSignals(QObject):
    finished = pyqtSignal(object)          # UpdateInfo or None


class _CheckTask(QRunnable):
    """One background update check."""

    def __init__(self):
        super().__init__()
        self.signals = _CheckSignals()

    def run(self):
        info = None
        try:
            info = UpdateService().get_update_info()
        except Exception as e:
            logger.debug(f"Background update check failed: {e}")
        self.signals.finished.emit(info)


class UpdateBanner(QWidget):
    """Full-width bar shown only when a newer release exists."""

    update_requested = pyqtSignal(object)   # UpdateInfo

    def __init__(self, parent=None):
        super().__init__(parent)
        self._info = None
        self._build()
        self.hide()

    def _build(self):
        self.setFixedHeight(38)
        self.setStyleSheet("""
            UpdateBanner {
                background-color: #2d5a8c;
                border-bottom: 1px solid #1e3d5f;
            }
            QLabel { color: #ffffff; font-size: 13px; }
            QPushButton {
                color: #ffffff;
                background-color: rgba(255, 255, 255, 30);
                border: 1px solid rgba(255, 255, 255, 70);
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 55); }
            QPushButton#dismiss {
                background: transparent; border: none;
                padding: 4px 8px; font-size: 15px;
            }
            QPushButton#dismiss:hover { background-color: rgba(255, 255, 255, 40); }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(10)

        self._label = QLabel()
        layout.addWidget(self._label)
        layout.addStretch()

        self._update_btn = QPushButton("Update Now")
        self._update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_btn.clicked.connect(self._on_update_clicked)
        layout.addWidget(self._update_btn)

        dismiss = QPushButton("✕")
        dismiss.setObjectName("dismiss")
        dismiss.setToolTip("Hide until the next launch")
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.clicked.connect(self.hide)
        layout.addWidget(dismiss)

    # ------------------------------------------------------------------ check

    def start_check(self, delay_ms: int = 2500):
        """Check in the background shortly after launch.

        Delayed so it never competes with the library scan for the first
        moments of startup - the user is looking at their animations, not at us.
        """
        QTimer.singleShot(delay_ms, self._run_check)

    def _run_check(self):
        task = _CheckTask()
        task.signals.finished.connect(self._on_check_finished)
        QThreadPool.globalInstance().start(task)

    def _on_check_finished(self, info):
        if not info:
            return                              # current, or check failed - say nothing
        self._info = info

        ok, _ = can_self_update()
        if ok and info.download_url:
            self._label.setText(
                f"<b>Action Library {info.version} is available.</b> "
                f"You're on {self._current()}.")
            self._update_btn.setText("Update Now")
        else:
            # Source checkout, unwritable install, or a release with no build
            # attached. Still tell them - just don't promise to do it for them.
            self._label.setText(
                f"<b>Action Library {info.version} is available.</b> "
                f"You're on {self._current()}.")
            self._update_btn.setText("View Release")
        self.show()

    @staticmethod
    def _current():
        from ..config import Config
        return Config.APP_VERSION

    def _on_update_clicked(self):
        if self._info:
            self.update_requested.emit(self._info)


__all__ = ['UpdateBanner']
