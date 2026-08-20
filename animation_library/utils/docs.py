"""
Documentation - find and open the local user docs.

The docs are plain HTML/CSS/images on disk, opened in the user's DEFAULT BROWSER
rather than an embedded Qt viewer. That's deliberate: a real browser renders
animated GIFs, full CSS and proper layout faithfully, and costs nothing to
maintain. It also works with no internet - the whole point is that a confused
first-time user shouldn't have to go find GitHub or YouTube.

Layout (source):
    docs/help/index.html        landing page / directory
    docs/help/<topic>.html      one page per topic
    docs/help/style.css         shared styling
    docs/help/nav.js            top nav + on-this-page sidebar, defined ONCE
    docs/help/images/           screenshots and GIFs, referenced relatively

Where it looks, in order:
    1. <repo>/docs/help/index.html          - running from source (dev)
    2. <exedir>/docs/index.html             - frozen build, docs copied next to
                                              the exe (the layout Painter uses)
    3. <exedir>/docs/help/index.html        - frozen, tree copied wholesale
    4. <PyInstaller _MEIPASS>/docs/help/    - bundled into the onefile temp dir
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional

from ..config import Config

logger = logging.getLogger(__name__)


def _candidate_paths() -> List[Path]:
    """Every place the docs index might live, best guess first."""
    candidates: List[Path] = []

    # Running from source: docs/ sits beside the animation_library package.
    candidates.append(Config.APP_ROOT.parent / 'docs' / 'help' / 'index.html')

    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / 'docs' / 'index.html')
        candidates.append(exe_dir / 'docs' / 'help' / 'index.html')

        # PyInstaller onefile unpacks data to a temp dir it advertises here.
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.append(Path(meipass) / 'docs' / 'help' / 'index.html')
            candidates.append(Path(meipass) / 'docs' / 'index.html')

    return candidates


def get_docs_index() -> Optional[Path]:
    """Path to the documentation landing page, or None if it isn't installed."""
    for candidate in _candidate_paths():
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def get_docs_page(page: str) -> Optional[Path]:
    """Path to a specific docs page (e.g. 'installation.html'), or None.

    Lets callers deep-link - e.g. an addon-install error pointing straight at the
    installation page instead of the front door.
    """
    index = get_docs_index()
    if index is None:
        return None
    target = index.parent / page
    return target if target.is_file() else None


def open_documentation(page: Optional[str] = None) -> bool:
    """Open the docs in the user's default browser.

    Args:
        page: Optional specific page, e.g. 'installation.html'. Falls back to the
              index if that page doesn't exist, so a stale link still lands
              somewhere useful instead of failing.

    Returns:
        True if a browser was asked to open the docs. False means they aren't
        installed - the caller should say where they were expected.
    """
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices

    target = get_docs_page(page) if page else None
    if target is None:
        target = get_docs_index()

    if target is None:
        logger.warning(
            "Documentation not found. Looked in: %s",
            ", ".join(str(c) for c in _candidate_paths()),
        )
        return False

    logger.info(f"Opening documentation: {target}")
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))


def get_expected_docs_location() -> Path:
    """Where the docs SHOULD be - for the 'not found' message."""
    return _candidate_paths()[0].parent


__all__ = [
    'open_documentation',
    'get_docs_index',
    'get_docs_page',
    'get_expected_docs_location',
]
