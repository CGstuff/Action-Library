"""
Library switching - point the app at a different library at runtime.

Why this exists:
    Every library-bound service is a module-level singleton that resolves its
    paths ONCE, at construction, from Config.load_library_path(). That made the
    configured library effectively immutable for the lifetime of the process:
    changing it required a restart, because get_database_service() would keep
    handing back an instance still connected to the old .meta/database.db.

    This module is the single place that knows the full set of things bound to a
    library. Keeping it in one place is the point - if resetting is scattered
    across callers, every service added later becomes a silent switching bug that
    only shows up as "why is it still reading the old library?".

Scope:
    This resets the SERVICE layer only. The UI still has to rebuild its models
    and views afterwards; the widgets hold rows that no longer exist. The
    intended shape is that app startup and a library switch run the SAME reload
    path, so the switch path is exercised on every launch instead of rotting
    until someone uses it.
"""

import logging
from pathlib import Path
from typing import Tuple, Union

from ..config import Config

logger = logging.getLogger(__name__)


def reset_library_services() -> None:
    """Discard every service bound to the current library.

    After this, the next get_*() call rebuilds against whatever library is
    configured NOW. Safe to call when nothing has been constructed yet.
    """
    from .archive_service import reset_archive_service
    from .blender_service import reset_blender_service
    from .database_service import reset_database_service
    from .drawover_storage import reset_drawover_storage
    from .folder_icon_service import reset_folder_icon_service
    from .notes_database import reset_notes_database
    from .thumbnail_loader import reset_thumbnail_loader
    from .trash_service import reset_trash_service

    # Dependents first. ArchiveService and TrashService cache a DatabaseService
    # at construction, so they must be dropped before the database itself -
    # otherwise they'd be left holding a service whose connections we just
    # closed.
    reset_archive_service()
    reset_trash_service()
    reset_folder_icon_service()

    # Resolves the .queue folder from the library; would keep polling the old
    # library's queue otherwise.
    reset_blender_service()

    # Library-specific rendered content.
    reset_drawover_storage()
    reset_thumbnail_loader()

    # There are TWO databases, not one: review notes live in their own file in
    # the same .meta folder. Miss this and notes stay bound to the old library.
    reset_notes_database()

    # Last - this closes the connections everything above was using.
    reset_database_service()


def switch_library(
    new_path: Union[str, Path],
    create: bool = True,
    reset_services: bool = True,
) -> Tuple[bool, str]:
    """Point the application at a different library.

    Args:
        new_path: Library root folder. An empty folder is valid - the database
                  and folder structure are created on demand.
        create: Create the folder if it doesn't exist.
        reset_services: Discard the services bound to the old library. Pass False
            when the caller is about to RELAUNCH the process instead: the reset
            is redundant (process exit closes everything), and tearing down
            before the relaunch is confirmed would leave a still-open app with
            dead services if the relaunch failed. Such callers should pass
            reset_library_services as restart_application's on_confirmed, so the
            teardown only happens once the new instance is definitely starting.

    Returns:
        (success, message) - message is the resolved path on success, or the
        reason on failure.

    Note:
        Callers must rebuild the UI afterwards (or relaunch). This only touches
        the service layer. Passing the CURRENT library is allowed and acts as a
        full reload.
    """
    path = Path(new_path)

    # Check this BEFORE mkdir: mkdir on an existing file raises FileExistsError,
    # so we'd refuse with "Could not create library folder: [WinError 183]..."
    # instead of telling the user the plain truth. This message goes straight
    # into a dialog.
    if path.exists() and not path.is_dir():
        return False, f"Not a folder: {path}"

    if create:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, f"Could not create library folder: {e}"

    if not path.exists():
        return False, f"Library folder does not exist: {path}"
    if not path.is_dir():
        return False, f"Not a folder: {path}"

    # Save the pointer BEFORE resetting anything. Services rebuild themselves
    # from Config.load_library_path(), so the new value has to be on disk first
    # or they'd reconstruct against the old library. This write is also what
    # releases the Blender addon: it polls library_path.txt and follows within a
    # couple of seconds (see blender_plugin/utils/library_path_sync.py).
    if not Config.save_library_path(path):
        return False, f"Could not save library path: {path}"

    # Remember it so the picker's list builds itself - you should never have to
    # browse for a library you've already used.
    try:
        from .known_libraries import get_known_libraries_store
        get_known_libraries_store().remember(path)
    except Exception as e:
        logger.warning(f"Could not record library in known list: {e}")

    if reset_services:
        reset_library_services()

    logger.info(f"Switched library to: {path}")
    return True, str(path)


def get_current_library() -> Union[Path, None]:
    """The library the app is currently configured to use, or None."""
    return Config.load_library_path()


__all__ = ['switch_library', 'reset_library_services', 'get_current_library']
