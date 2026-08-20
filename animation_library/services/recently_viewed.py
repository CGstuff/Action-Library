"""
RecentlyViewedStore - per-machine "recently viewed" tracking.

"Recently viewed" is a PER-USER concept, but it used to be written to the
`last_viewed_date` column of the SHARED library database. On a studio setup that
meant:

1. Every card selection took a WRITE LOCK on a SQLite file sitting on a network
   share - from every client, on every click (a multi-select wrote once per
   selected item). Pure contention for something nobody asked to persist.
2. "Recently Viewed" was actually GLOBAL: your recents were a mixture of the
   whole studio's browsing, because everyone wrote to the same row.

This keeps it local to the machine, so it is both correct (your recents are
yours) and free of shared-database traffic.

Storage: {user_data_dir}/recently_viewed.json  ->  {uuid: iso8601_timestamp}
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

from ..config import Config


class RecentlyViewedStore:
    """Local, per-machine record of when each animation was last viewed."""

    MAX_ENTRIES = 500  # keep the file small; drop the oldest beyond this

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else (Config.get_user_data_dir() / 'recently_viewed.json')
        self._lock = threading.RLock()
        self._data: Dict[str, str] = {}
        self._loaded = False

    # ==================== PUBLIC API ====================

    def mark_viewed(self, uuid: str, when: Optional[datetime] = None) -> None:
        """Record that an animation was viewed just now."""
        self.mark_many_viewed([uuid], when)

    def mark_many_viewed(self, uuids: Iterable[str], when: Optional[datetime] = None) -> None:
        """Record several animations at once (one file write, not one per item)."""
        stamp = (when or datetime.now()).isoformat()
        with self._lock:
            self._load()
            changed = False
            for uuid in uuids:
                if uuid:
                    self._data[uuid] = stamp
                    changed = True
            if changed:
                self._trim()
                self._save()

    def get_viewed_at(self, uuid: str) -> Optional[str]:
        """ISO timestamp this animation was last viewed on THIS machine, or None."""
        if not uuid:
            return None
        with self._lock:
            self._load()
            return self._data.get(uuid)

    def clear(self) -> None:
        """Forget all recently-viewed history on this machine."""
        with self._lock:
            self._loaded = True
            self._data = {}
            self._save()

    # ==================== INTERNAL ====================

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True  # set first: a broken file must not retry every call
        try:
            if self._path.exists():
                with open(self._path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._data = {k: v for k, v in data.items()
                                  if isinstance(k, str) and isinstance(v, str)}
        except (OSError, json.JSONDecodeError, ValueError):
            self._data = {}

    def _trim(self) -> None:
        if len(self._data) <= self.MAX_ENTRIES:
            return
        newest = sorted(self._data.items(), key=lambda kv: kv[1], reverse=True)
        self._data = dict(newest[:self.MAX_ENTRIES])

    def _save(self) -> None:
        """Atomic write (temp + replace) so a crash can't truncate the file."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix('.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._data, f)
            os.replace(tmp, self._path)
        except OSError:
            pass  # recents are best-effort; never break the UI over them


_store_instance: Optional[RecentlyViewedStore] = None


def get_recently_viewed_store() -> RecentlyViewedStore:
    """Get the global per-machine recently-viewed store."""
    global _store_instance
    if _store_instance is None:
        _store_instance = RecentlyViewedStore()
    return _store_instance


__all__ = ['RecentlyViewedStore', 'get_recently_viewed_store']
