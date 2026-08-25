"""
The half of updating that cannot happen while we're running.

Windows keeps an exclusive lock on a running .exe and on every DLL loaded out of
_internal/, so the app cannot replace its own files. The sequence is:

    app downloads + unpacks   ->  staging dir (user data, not the install)
    app writes a swap script  ->  staging dir
    app launches the script detached, then quits
    script waits for our PID  ->  files are unlocked
    script swaps the files    ->  relaunches the app  ->  deletes itself

Design notes worth keeping:

* The old files are MOVED aside, not copied. A rename is instant and costs no
  extra disk; copying _internal would mean ~100MB and a second copy to clean up.
  It also gives a real rollback: if anything fails, move them back.

* Only ActionLibrary.exe and _internal/ are touched. A default install keeps the
  library at {install}/storage, so the script must never operate on the install
  folder as a whole. Every path it writes to is spelled out literally.

* Everything is logged to update.log next to the app's settings, because when
  this goes wrong the app is closed and there is nothing else to look at.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from ..config import Config
from ..services.update_service import UPDATE_ITEMS, get_install_dir

logger = logging.getLogger(__name__)


def log_path() -> Path:
    return Config.get_user_data_dir() / 'update.log'


# `install` and `stage` are baked in as quoted literals rather than passed as
# arguments - paths with spaces through cmd argument parsing are a bug farm.
_SWAP_SCRIPT = r'''@echo off
title Updating Action Library
echo Updating Action Library to {version}...
echo.

echo [1/4] Waiting for Action Library to close...
:waitloop
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul
if not errorlevel 1 (
    ping -n 2 127.0.0.1 >nul
    goto waitloop
)

echo [2/4] Setting the current version aside...
if exist "{install}\_internal.old" rmdir /s /q "{install}\_internal.old"
if exist "{install}\ActionLibrary.exe.old" del /q "{install}\ActionLibrary.exe.old"
move "{install}\_internal" "{install}\_internal.old" >nul
if errorlevel 1 goto fail_early
move "{install}\ActionLibrary.exe" "{install}\ActionLibrary.exe.old" >nul
if errorlevel 1 goto rollback

echo [3/4] Installing the new version...
robocopy "{src}\_internal" "{install}\_internal" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto rollback
copy /y "{src}\ActionLibrary.exe" "{install}\ActionLibrary.exe" >nul
if errorlevel 1 goto rollback

echo       Done. Removing the previous version...
if exist "{install}\_internal.old" rmdir /s /q "{install}\_internal.old"
if exist "{install}\ActionLibrary.exe.old" del /q "{install}\ActionLibrary.exe.old"
goto relaunch

:rollback
echo.
echo   UPDATE FAILED - putting the previous version back.
if exist "{install}\_internal" rmdir /s /q "{install}\_internal"
if exist "{install}\_internal.old" move "{install}\_internal.old" "{install}\_internal" >nul
if exist "{install}\ActionLibrary.exe.old" move "{install}\ActionLibrary.exe.old" "{install}\ActionLibrary.exe" >nul
echo   The previous version was restored. Nothing in your library was touched.
goto relaunch

:fail_early
echo.
echo   Could not replace the program files - they may still be in use.
echo   Nothing was changed. Try again, or install manually.
goto relaunch

:relaunch
echo [4/4] Starting Action Library...
start "" "{install}\ActionLibrary.exe"
rmdir /s /q "{stage}" 2>nul
(goto) 2>nul & del "%~f0"
'''


def is_supported() -> bool:
    """Self-update swapping is Windows-only for now."""
    return sys.platform == 'win32'


def write_swap_script(staged_dir: Path, version: str) -> Tuple[Optional[Path], Optional[str]]:
    """Write the swap script into the staging folder. Returns (path, error)."""
    if not is_supported():
        return None, "Automatic updating is only supported on Windows."

    install = get_install_dir()
    if install is None:
        return None, "Running from source - nothing to swap."

    missing = [n for n in UPDATE_ITEMS if not (staged_dir / n).exists()]
    if missing:
        return None, f"Staged update is incomplete (missing {', '.join(missing)})."

    # src is where the new files ARE; stage is the whole scratch tree to delete
    # afterwards. They are different directories - conflating them means copying
    # from a folder that holds nothing.
    script = _SWAP_SCRIPT.format(
        pid=os.getpid(),
        install=str(install).rstrip('\\'),
        src=str(staged_dir).rstrip('\\'),
        stage=str(staged_dir.parent).rstrip('\\'),
        version=version,
    )
    path = staged_dir.parent / 'apply_update.bat'
    try:
        # cp1252: cmd.exe reads .bat in the OEM/ANSI codepage, not UTF-8.
        path.write_text(script, encoding='cp1252', errors='replace')
    except OSError as e:
        return None, f"Could not write the update script: {e}"
    return path, None


def launch_swap(script_path: Path) -> Tuple[bool, Optional[str]]:
    """Start the swap script detached so it outlives us, then let the app quit."""
    try:
        creation = 0
        if sys.platform == 'win32':
            creation = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
        with open(log_path(), 'w', encoding='utf-8') as log:
            log.write(f"Launching update swap: {script_path}\n")
        subprocess.Popen(
            ['cmd.exe', '/c', str(script_path)],
            cwd=str(script_path.parent),
            creationflags=creation,
            close_fds=True,
        )
        return True, None
    except Exception as e:
        logger.error(f"Could not launch the update swap: {e}")
        return False, f"Could not start the updater: {e}"


__all__ = ['write_swap_script', 'launch_swap', 'is_supported', 'log_path']
