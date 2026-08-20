"""
Library path sync - keep the addon pointed at the desktop app's library.

The desktop app OWNS the library location. It writes it to library_path.txt in
its per-machine user-data dir (see Config.save_library_path). The addon mirrors
that value into prefs.actions_library_path, so every existing caller can keep
reading preferences exactly as before - they just can't go stale now.

Why poll instead of watching:
    bpy has no filesystem-watch API. But library_path.txt is tiny and lives on
    LOCAL disk (AppData) - never on the network share - so the OS serves the
    stat from page cache. We only re-read the file when its mtime moves, and we
    only touch preferences when the value actually differs, so an unchanged
    library costs one cached stat every few seconds and nothing else.

Why a dedicated timer instead of the socket listener's tick:
    The socket tick only runs while the socket server is up (see
    AL_socket_listener). The library path has to stay correct whether or not the
    desktop app is connected, so this owns its own timer. Timers are cheap and,
    unlike modal operators, do NOT block Blender's auto-save.
"""

import os

import bpy

# How often to check the pointer file. The path changes roughly never, so this
# only has to be fast enough to feel instant when it does.
SYNC_INTERVAL = 2.0

# mtime of library_path.txt as of the last read. None = never read.
_last_mtime = None

# Whether the timer is meant to be running (the callback reads this to decide
# whether to reschedule itself or unregister).
_timer_running = False


def _get_addon_prefs():
    """Get this addon's preferences, or None if unavailable."""
    addon_name = __name__.split('.')[0]
    if addon_name not in bpy.context.preferences.addons:
        return None
    return bpy.context.preferences.addons[addon_name].preferences


def sync_now(force: bool = False) -> bool:
    """Pull the desktop app's library path into addon preferences.

    Args:
        force: Re-read the pointer file even if its mtime hasn't changed.
               Used by the manual sync button and on file load.

    Returns:
        True if the preference value actually changed.
    """
    global _last_mtime

    try:
        from ..preferences.AL_preferences import (
            get_desktop_app_config_file,
            get_desktop_app_library_path,
        )

        config_file = get_desktop_app_config_file()
        if not config_file or not os.path.exists(config_file):
            return False

        # Cheap gate: only read the file when it has actually been rewritten.
        try:
            mtime = os.path.getmtime(config_file)
        except OSError:
            return False

        if not force and mtime == _last_mtime:
            return False
        _last_mtime = mtime

        desktop_path = get_desktop_app_library_path()
        if not desktop_path:
            # Empty result means the app hasn't configured a library yet, OR we
            # caught the file mid-rewrite. Either way, never clobber a working
            # path with nothing - we'll pick up the real value on a later tick.
            return False

        prefs = _get_addon_prefs()
        if prefs is None:
            return False

        if prefs.actions_library_path == desktop_path:
            return False

        prefs.actions_library_path = desktop_path
        print(f"[Action Library] Library path synced from desktop app: {desktop_path}")
        return True

    except Exception:
        # Never let a sync failure break a timer or a file load.
        return False


def _sync_timer_tick():
    """Timer callback: re-sync if the pointer file changed."""
    if not _timer_running:
        return None  # Stop: unregister the timer

    sync_now()
    return SYNC_INTERVAL


def start_path_sync():
    """Start watching the desktop app's pointer file.

    Idempotent: safe to call repeatedly. The timer is persistent, so it survives
    .blend file loads.
    """
    global _timer_running
    _timer_running = True

    if not bpy.app.timers.is_registered(_sync_timer_tick):
        bpy.app.timers.register(
            _sync_timer_tick,
            first_interval=1.0,
            persistent=True,
        )


def stop_path_sync():
    """Stop watching the pointer file."""
    global _timer_running
    _timer_running = False

    if bpy.app.timers.is_registered(_sync_timer_tick):
        try:
            bpy.app.timers.unregister(_sync_timer_tick)
        except (ValueError, RuntimeError):
            # Already unregistered (e.g. by a file load) - nothing to do.
            pass


__all__ = ['sync_now', 'start_path_sync', 'stop_path_sync', 'SYNC_INTERVAL']
