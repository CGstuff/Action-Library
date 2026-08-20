"""
KnownLibrariesStore - the list of libraries this machine knows about.

Per-machine, and it has to be: a list of libraries cannot live inside a library,
for the same reason library_path.txt can't - whichever one you're currently
pointed at only knows about itself. This sits next to the pointer file, in the
user data dir.

Storage: {user_data_dir}/libraries.json
    [{"path": "Z:\\Studio\\AnimLib", "label": "Studio",
      "last_used": "2026-07-16T12:00:00"}, ...]

Entries are never auto-removed for being unreachable. A network library is
"unavailable" when you're off the VPN, not gone - dropping it would silently
empty the list every time you worked from a laptop.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..config import Config


class KnownLibrariesStore:
    """Local, per-machine record of libraries the user has used."""

    MAX_ENTRIES = 20

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else (Config.get_user_data_dir() / 'libraries.json')
        self._lock = threading.RLock()
        self._entries: List[Dict[str, Any]] = []
        self._loaded = False

    # ==================== PUBLIC API ====================

    def list_libraries(self, include_current: bool = True) -> List[Dict[str, Any]]:
        """Known libraries, most recently used first.

        Each entry: {path, label, last_used, exists, is_current}.
        `exists` is resolved live, so an unplugged drive shows as unavailable
        rather than disappearing.
        """
        with self._lock:
            self._load()
            if include_current:
                self._ensure_current_locked()

            current_key = self._key(Config.load_library_path())

            result = []
            for entry in sorted(self._entries,
                                key=lambda e: e.get('last_used', ''), reverse=True):
                path = entry['path']
                result.append({
                    'path': path,
                    'label': entry.get('label') or self._default_label(path),
                    'last_used': entry.get('last_used', ''),
                    'exists': Path(path).is_dir(),
                    'is_current': bool(current_key) and self._key(path) == current_key,
                })
            return result

    def remember(self, path: Union[str, Path], label: Optional[str] = None) -> None:
        """Add a library, or bump its last_used if already known."""
        cleaned = self._clean(path)
        if not cleaned:
            return
        key = self._key(cleaned)

        with self._lock:
            self._load()
            stamp = datetime.now().isoformat()
            for entry in self._entries:
                if self._key(entry['path']) == key:
                    entry['last_used'] = stamp
                    if label:
                        entry['label'] = label
                    break
            else:
                self._entries.append({
                    'path': cleaned,
                    'label': label or self._default_label(cleaned),
                    'last_used': stamp,
                })
            self._trim()
            self._save()

    def forget(self, path: Union[str, Path]) -> bool:
        """Remove an entry from the list. Never touches the library's files."""
        key = self._key(path)
        with self._lock:
            self._load()
            before = len(self._entries)
            self._entries = [e for e in self._entries if self._key(e['path']) != key]
            if len(self._entries) == before:
                return False
            self._save()
            return True

    def set_label(self, path: Union[str, Path], label: str) -> bool:
        """Rename an entry. An empty label reverts to the folder name."""
        key = self._key(path)
        with self._lock:
            self._load()
            for entry in self._entries:
                if self._key(entry['path']) == key:
                    entry['label'] = label.strip() or self._default_label(entry['path'])
                    self._save()
                    return True
            return False

    # ==================== INTERNAL ====================

    @staticmethod
    def _clean(path: Union[str, Path, None]) -> str:
        """The form we STORE and DISPLAY: tidied, but original casing intact."""
        if not path:
            return ""
        try:
            return os.path.normpath(str(path))
        except (TypeError, ValueError):
            return ""

    @classmethod
    def _key(cls, path: Union[str, Path, None]) -> str:
        """The form we COMPARE by, so one folder isn't listed twice under two
        spellings.

        Separate from _clean because os.path.normcase LOWERCASES on Windows.
        Storing that would mean displaying 'studio' instead of 'Studio' and
        deriving lowercase labels from it - the comparison form is not fit to
        show a human.
        """
        cleaned = cls._clean(path)
        if not cleaned:
            return ""
        try:
            return os.path.normcase(cleaned)
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _default_label(path: str) -> str:
        """Folder name, e.g. Z:\\Studio\\AnimLib -> 'AnimLib'."""
        name = Path(path).name
        return name or str(path)

    def _ensure_current_locked(self) -> None:
        """Seed the list with the library we're using, so it's never empty."""
        current = Config.load_library_path()
        if not current:
            return
        cleaned = self._clean(current)
        key = self._key(cleaned)
        if any(self._key(e['path']) == key for e in self._entries):
            return
        self._entries.append({
            'path': cleaned,
            'label': self._default_label(cleaned),
            'last_used': datetime.now().isoformat(),
        })
        self._save()

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True  # set first: a broken file must not retry every call
        try:
            if self._path.exists():
                with open(self._path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._entries = [
                        e for e in data
                        if isinstance(e, dict) and isinstance(e.get('path'), str) and e['path']
                    ]
        except (OSError, json.JSONDecodeError, ValueError):
            self._entries = []

    def _trim(self) -> None:
        if len(self._entries) <= self.MAX_ENTRIES:
            return
        self._entries.sort(key=lambda e: e.get('last_used', ''), reverse=True)
        self._entries = self._entries[:self.MAX_ENTRIES]

    def _save(self) -> None:
        """Atomic write (temp + replace) so a crash can't truncate the list."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix('.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._entries, f, indent=2)
            os.replace(tmp, self._path)
        except OSError:
            pass  # best-effort; never break the UI over the recents list


_store_instance: Optional[KnownLibrariesStore] = None


def get_known_libraries_store() -> KnownLibrariesStore:
    """Get the global per-machine known-libraries store."""
    global _store_instance
    if _store_instance is None:
        _store_instance = KnownLibrariesStore()
    return _store_instance


__all__ = ['KnownLibrariesStore', 'get_known_libraries_store']
