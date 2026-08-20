"""
Addon / app version check.

The desktop app and this addon are ONE product versioned together, so an addon
older than the app is the source of most odd behaviour ("I installed it and
nothing happened"). The app stamps its version into the library at
{library}/.meta/app_version.txt; this reads it and lets the panel warn when the
addon is behind, pointing the user at the reinstall in the app's Settings.

Caching: the panel's draw() runs on every redraw, and the library may be on a
network share, so the marker is read ONCE per library path and cached for the
session. The app version only changes when the user updates the app - after
which they reinstall the addon and restart Blender anyway, which clears this - so
a session-long cache is correct, not just an optimization.
"""

import os

# {library_path: parsed_version_tuple_or_None}
_app_version_cache = {}


def _parse_version(text):
    """'1.5.2' -> (1, 5, 2). Returns None if it can't be parsed."""
    if not text:
        return None
    try:
        parts = str(text).strip().split('.')
        return tuple(int(p) for p in parts[:3])
    except (ValueError, TypeError):
        return None


def get_addon_version():
    """This addon's version, from bl_info, as a tuple."""
    try:
        import importlib
        pkg = __name__.split('.')[0]
        bl_info = importlib.import_module(pkg).bl_info
        return tuple(bl_info.get('version', (0, 0, 0)))
    except Exception:
        return (0, 0, 0)


def get_library_app_version(library_path):
    """The app version stamped into this library, as a tuple, or None.

    Cached per library path for the session - see the module note.
    """
    if not library_path:
        return None
    if library_path in _app_version_cache:
        return _app_version_cache[library_path]

    version = None
    try:
        marker = os.path.join(library_path, '.meta', 'app_version.txt')
        if os.path.exists(marker):
            with open(marker, 'r', encoding='utf-8') as f:
                version = _parse_version(f.read())
    except OSError:
        version = None

    _app_version_cache[library_path] = version
    return version


def check_outdated(library_path):
    """Is the addon older than the app that owns this library?

    Returns (is_outdated, addon_version_str, app_version_str). is_outdated is
    False when the app version is unknown (old app, offline library, or a
    brand-new library the app hasn't stamped yet) - we only warn on a definite
    mismatch, never on a guess.
    """
    addon_ver = get_addon_version()
    app_ver = get_library_app_version(library_path)

    def as_str(v):
        return '.'.join(str(x) for x in v) if v else '?'

    if app_ver is None:
        return (False, as_str(addon_ver), '?')
    return (addon_ver < app_ver, as_str(addon_ver), as_str(app_ver))


def clear_cache():
    """Forget cached app versions - e.g. if the library path changed."""
    _app_version_cache.clear()


__all__ = ['check_outdated', 'get_addon_version', 'get_library_app_version', 'clear_cache']
