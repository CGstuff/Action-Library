"""
Application update: check GitHub for a newer release, download it, stage it.

The file swap itself is NOT done here - see utils/update_swap.py. Windows holds
an exclusive lock on a running .exe and on every DLL loaded out of _internal/,
so the app physically cannot overwrite itself. Staging happens while we run; the
swap happens after we exit.

Two rules this module will not bend:

  * Nothing is ever written into the install directory. Downloads and unpacking
    go to the user data dir. The Blender addon updater wrote its scratch into
    the addon folder and left 260MB buried in a working tree; not repeating it.

  * An update is an ALLOWLIST, never a wipe. Only ActionLibrary.exe and
    _internal/ get replaced. This matters more than it looks: a default install
    keeps the library at {install}/storage, right beside the exe, so anything
    that cleared the install directory would delete the user's animations.
"""

import json
import logging
import shutil
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from ..config import Config

logger = logging.getLogger(__name__)

REPO = "CGstuff/Action-Library"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"

# The ONLY things an update may replace. Everything else in the install folder
# - storage/, data/, portable.txt, README.txt - belongs to the user.
UPDATE_ITEMS = ("ActionLibrary.exe", "_internal")


@dataclass
class UpdateInfo:
    """A release newer than what we're running."""
    version: str            # "1.5.6"
    tag: str                # "1.5.6" / "v1.5.6" as GitHub has it
    name: str               # release title
    notes: str              # release body (markdown)
    page_url: str           # human release page
    download_url: str       # the .zip asset
    asset_name: str
    size_bytes: int

    @property
    def size_mb(self) -> float:
        return self.size_bytes / 1024 / 1024


def parse_version(v_str: str) -> tuple:
    """'v1.2.3' -> (1, 2, 3). (0, 0, 0) if it can't be read."""
    try:
        v_str = str(v_str).lower().lstrip('v').split('-')[0]
        return tuple(int(p) if p.isdigit() else 0 for p in v_str.split('.'))
    except Exception:
        return (0, 0, 0)


def get_install_dir() -> Optional[Path]:
    """Folder holding ActionLibrary.exe, or None when running from source."""
    if not getattr(sys, 'frozen', False):
        return None
    return Path(sys.executable).parent


def can_self_update() -> Tuple[bool, str]:
    """Can we replace ourselves here? Returns (ok, reason_if_not).

    Refused on a source checkout for the same reason the Blender addon refuses:
    'updating' a dev tree means overwriting your own working copy with a build.
    """
    if not getattr(sys, 'frozen', False):
        return False, "Running from source - update with git instead."

    install = get_install_dir()
    if install is None or not install.exists():
        return False, "Could not locate the installation folder."

    # Program Files without admin rights is the common case. Find out now, while
    # we can still say so plainly, instead of after a 60MB download.
    probe = install / '.al_write_test'
    try:
        probe.write_text('x', encoding='utf-8')
        probe.unlink()
    except OSError:
        return False, (f"No permission to write to {install}.\n"
                       "Install somewhere writable, or update manually.")

    return True, ""


class UpdateService:
    """Checks GitHub for a newer release and stages it for installation."""

    UPDATE_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

    def __init__(self):
        self._cached: Optional[UpdateInfo] = None

    # ---------------------------------------------------------------- check

    def check_for_updates(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Back-compatible check used by the About dialog.

        Returns (update_available, latest_version_str, release_page_url).
        """
        info = self.get_update_info()
        if info is None:
            return False, None, None
        return True, info.tag, info.page_url

    def get_update_info(self, timeout: int = 10) -> Optional[UpdateInfo]:
        """The newer release, or None if we're current / the check failed.

        Network failures are deliberately quiet - a background check that
        can't reach GitHub must never interrupt the user.
        """
        data = self._fetch(timeout)
        if data is None:
            return None

        tag = data.get('tag_name') or ''
        latest = parse_version(tag)
        current = parse_version(Config.APP_VERSION)
        if latest <= current:
            self._cached = None
            return None

        asset = self._pick_asset(data.get('assets') or [])
        if asset is None:
            # A release with no build attached is nothing we can install. Still
            # worth telling the user about, so they can grab it themselves.
            logger.info(f"Release {tag} has no downloadable build attached")

        self._cached = UpdateInfo(
            version='.'.join(str(x) for x in latest),
            tag=tag,
            name=data.get('name') or tag,
            notes=(data.get('body') or '').strip(),
            page_url=data.get('html_url') or RELEASES_PAGE,
            download_url=(asset or {}).get('browser_download_url', ''),
            asset_name=(asset or {}).get('name', ''),
            size_bytes=int((asset or {}).get('size') or 0),
        )
        return self._cached

    def _fetch(self, timeout: int) -> Optional[Dict[str, Any]]:
        try:
            req = urllib.request.Request(self.UPDATE_URL)
            req.add_header('Accept', 'application/vnd.github.v3+json')
            req.add_header('User-Agent', f'ActionLibrary/{Config.APP_VERSION}')
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    return None
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            logger.debug(f"Update check failed: {e}")
            return None

    @staticmethod
    def _pick_asset(assets) -> Optional[dict]:
        """Prefer the portable Windows zip; fall back to any zip."""
        zips = [a for a in assets
                if str(a.get('name', '')).lower().endswith('.zip')]
        if not zips:
            return None
        for a in zips:
            if 'portable' in a['name'].lower():
                return a
        return zips[0]

    # ------------------------------------------------------------- download

    @staticmethod
    def staging_dir() -> Path:
        """Scratch space - user data dir, never the install folder."""
        d = Config.get_user_data_dir() / 'update_staging'
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def clear_staging(cls) -> None:
        shutil.rmtree(cls.staging_dir(), ignore_errors=True)

    def download_and_stage(
        self,
        info: UpdateInfo,
        progress: Optional[Callable[[int, int], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Tuple[Optional[Path], Optional[str]]:
        """Download and unpack the release. Returns (staged_dir, error).

        staged_dir holds the UPDATE_ITEMS ready for the swapper to copy across.
        Nothing here goes near the install folder.
        """
        if not info.download_url:
            return None, "That release has no downloadable build attached."

        self.clear_staging()
        stage = self.staging_dir()
        zip_path = stage / (info.asset_name or 'update.zip')

        try:
            req = urllib.request.Request(info.download_url)
            req.add_header('User-Agent', f'ActionLibrary/{Config.APP_VERSION}')
            with urllib.request.urlopen(req, timeout=60) as response:
                total = int(response.headers.get('Content-Length')
                            or info.size_bytes or 0)
                done = 0
                with open(zip_path, 'wb') as f:
                    while True:
                        if should_cancel and should_cancel():
                            self.clear_staging()
                            return None, "Cancelled."
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, total)
        except Exception as e:
            self.clear_staging()
            return None, f"Download failed: {e}"

        unpacked = stage / 'unpacked'
        try:
            with zipfile.ZipFile(zip_path) as zf:
                self._safe_extract(zf, unpacked)
        except Exception as e:
            self.clear_staging()
            return None, f"Could not unpack the download: {e}"

        root = self._find_app_root(unpacked)
        if root is None:
            self.clear_staging()
            return None, "The download did not contain ActionLibrary.exe."

        missing = [n for n in UPDATE_ITEMS if not (root / n).exists()]
        if missing:
            self.clear_staging()
            return None, (f"The download looks incomplete "
                          f"(missing {', '.join(missing)}). Nothing was changed.")

        try:
            zip_path.unlink()
        except OSError:
            pass
        return root, None

    @staticmethod
    def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
        """Extract, refusing any entry that would escape dest (zip-slip)."""
        dest = dest.resolve()
        dest.mkdir(parents=True, exist_ok=True)
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if not str(target).startswith(str(dest)):
                raise ValueError(
                    f"Refusing unsafe path in archive: {member.filename}")
        zf.extractall(dest)

    @staticmethod
    def _find_app_root(base: Path) -> Optional[Path]:
        """Find the folder holding ActionLibrary.exe in the extracted zip."""
        exe = 'ActionLibrary.exe'
        if not base.exists():
            return None
        if (base / exe).exists():
            return base
        subs = [d for d in base.iterdir() if d.is_dir()]
        if len(subs) == 1 and (subs[0] / exe).exists():
            return subs[0]
        for found in base.rglob(exe):
            return found.parent
        return None


__all__ = ['UpdateService', 'UpdateInfo', 'can_self_update', 'get_install_dir',
           'parse_version', 'UPDATE_ITEMS', 'RELEASES_PAGE']
