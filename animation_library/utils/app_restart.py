"""
Application restart.

Why the app relaunches to change library:
    Every library-bound service resolves its paths ONCE, at construction, and
    six long-lived objects cache one of those services - the folder tree, header
    toolbar, metadata panel, animation view, card delegate and list model.
    Re-pointing in-process means re-injecting into every one of them, and a
    single missed reference keeps reading the OLD library silently: no crash, no
    error, just wrong data.

    Changing library is rare, so a relaunch is the better trade. It's also the
    strongest version of "make the switch path the startup path" - it IS the
    startup path, so it can't rot from disuse.
"""

import logging
import os
import subprocess
import sys
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


def get_relaunch_command() -> List[str]:
    """Build the command that re-runs this application.

    Handles both a frozen build (PyInstaller: sys.executable IS the app, and
    sys.argv[0] is that same exe - so it must not be passed again as a script)
    and a source run (python run.py ...).
    """
    if getattr(sys, 'frozen', False):
        return [sys.executable] + sys.argv[1:]
    return [sys.executable] + sys.argv


def restart_application(on_confirmed: Optional[Callable[[], None]] = None) -> bool:
    """Launch a fresh instance of this app, then quit this one.

    Args:
        on_confirmed: Optional callable, run ONLY once the new process has been
            launched successfully and just before quitting. Use it for teardown
            that would leave this instance broken if the relaunch never happened.

    Returns:
        True if a new instance was launched (and a quit has been requested).
        False if it could not be launched - in which case this instance is left
        running and untouched, because closing the only window and starting
        nothing is worse than not restarting at all. Callers should tell the
        user to restart manually.
    """
    cmd = get_relaunch_command()
    logger.info(f"Restarting application: {cmd}")

    try:
        subprocess.Popen(cmd, cwd=os.getcwd(), close_fds=True)
    except Exception as e:
        logger.error(f"Failed to relaunch application: {e}")
        return False

    if on_confirmed is not None:
        try:
            on_confirmed()
        except Exception as e:
            # Teardown failure must not strand us: the new instance is already
            # starting, so carry on and quit regardless.
            logger.warning(f"Pre-quit cleanup failed: {e}")

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app.quit()

    return True


__all__ = ['restart_application', 'get_relaunch_command']
