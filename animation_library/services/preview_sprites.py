"""
Preview sprite sheets - animated cards without a video decoder per card.

WHY NOT JUST PLAY THE VIDEOS
    Cards are 160px; the previews are 640x640 webm. Decoding one costs ~1.35ms
    per frame through the full pipeline (decode -> RGB -> QImage -> scale), so a
    grid of 30 cards at 30fps needs ~122% of a CPU core, permanently, competing
    with the UI thread. Browsers get away with this (Mixamo, ActorCore) because
    <video> uses the GPU's hardware decoder; OpenCV decodes in software.

WHAT THIS DOES INSTEAD
    Decode each preview ONCE into a grid of small frames - a sprite sheet - and
    cache it as a single image. Playback is then drawing a sub-rectangle of an
    already-loaded pixmap: no decoding at all, and it rides the existing
    thumbnail infrastructure (async load, QPixmapCache).

    Frames are sampled evenly across the whole clip and capped, so a 30-second
    take costs exactly as much as a 1-second one - a flipbook of the motion
    rather than a faithful playback.

BACKGROUND KEYING
    Blender renders these previews over a flat grey, while the PNG thumbnail is
    transparent and gets composited onto the card's gradient. Left alone, a
    playing card would suddenly grow a grey box. The background is perfectly
    uniform, so it's keyed back out to alpha and the card looks the same
    playing or still.

CACHE LOCATION
    The user data dir, NOT the library's .meta. Two reasons: on a shared network
    library every client would otherwise write derived files into the shared
    folder, and reading sprite sheets back over SMB would defeat the point.
    Keyed by uuid + source mtime, so a re-captured preview rebuilds itself.
"""

import logging
import math
import os
from pathlib import Path
from typing import Dict, Optional

from ..config import Config

logger = logging.getLogger(__name__)

DEFAULT_FRAME_SIZE = 160
# Cap the cache so it can't grow without bound. Sheets are ~100KB each, so this
# holds roughly 2000 animations - past that the least recently used go first.
MAX_CACHE_MB = 200
DEFAULT_MAX_FRAMES = 24
# The flat background is uniform, so this can be tight - a loose tolerance
# starts punching holes in a character that happens to contain the same grey.
KEY_TOLERANCE = 12


def get_cache_dir() -> Path:
    d = Config.get_user_data_dir() / 'preview_sprites'
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(uuid: str, preview_path, frame_size: int) -> Optional[str]:
    """Identity of a cached sheet: asset + source mtime + frame size.

    mtime is in there so re-capturing a preview invalidates the old sheet.
    """
    try:
        mtime = int(os.path.getmtime(preview_path))
    except OSError:
        return None
    return f"{uuid}_{mtime}_{frame_size}"


def sprite_path_for(uuid: str, preview_path, frame_size: int, count: int) -> Optional[Path]:
    """Cache path for a sheet holding `count` frames.

    The ACTUAL frame count is in the filename - not the cap - because playback
    needs it to know where the flipbook loops. A clip capped at 24 frames may
    only have 8, and the grid always has a few empty cells at the end (24 frames
    tile as 5x5 = 25). Cycling on the grid size instead of the real count shows
    those empty cells as a blank flash at the end of every loop.

    The "n" prefix marks this filename format, so sheets written by the earlier
    version (which stored the cap here) can't be misread as a frame count.
    """
    key = cache_key(uuid, preview_path, frame_size)
    if key is None:
        return None
    return get_cache_dir() / f"{key}_n{count}.png"


def find_cached(uuid: str, preview_path, frame_size: int) -> Optional[Dict]:
    """Look for an existing sheet for this preview, recovering its frame count."""
    key = cache_key(uuid, preview_path, frame_size)
    if key is None:
        return None
    try:
        for path in get_cache_dir().glob(f"{key}_n*.png"):
            try:
                count = int(path.stem.rsplit('_n', 1)[1])
            except (IndexError, ValueError):
                continue
            if count <= 0:
                continue
            cols, rows = grid_for(count)
            return {'path': str(path), 'columns': cols, 'rows': rows,
                    'count': count, 'frame_size': frame_size}
    except OSError:
        pass
    return None


def grid_for(count: int):
    """Frames -> (cols, rows). Square-ish, so the sheet stays compact."""
    cols = max(1, math.ceil(math.sqrt(count)))
    rows = max(1, math.ceil(count / cols))
    return cols, rows


def build_sprite_sheet(preview_path, out_path,
                       frame_size: int = DEFAULT_FRAME_SIZE,
                       max_frames: int = DEFAULT_MAX_FRAMES,
                       key_background: bool = True) -> Optional[Dict]:
    """Decode a preview video into a sprite sheet PNG. Returns its metadata.

    Runs off the UI thread - it's ~60ms per clip.
    """
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(preview_path))
    if not cap.isOpened():
        logger.warning(f"Could not open preview: {preview_path}")
        return None

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if total <= 0:
        cap.release()
        return None

    n = min(max_frames, total)
    # Evenly spaced across the WHOLE clip, so long takes still read correctly.
    wanted = {round(i * (total - 1) / max(n - 1, 1)) for i in range(n)}

    frames = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx in wanted:
            small = cv2.resize(frame, (frame_size, frame_size),
                               interpolation=cv2.INTER_AREA)
            frames.append(small)
        idx += 1
    cap.release()

    if not frames:
        return None

    cols, rows = grid_for(len(frames))
    sheet = np.zeros((rows * frame_size, cols * frame_size, 4), dtype=np.uint8)

    # Key from the first frame's corner - the render background, sampled before
    # any resizing softened it.
    bg = frames[0][0, 0].astype(np.int16) if key_background else None

    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        bgra = np.dstack([f, np.full(f.shape[:2], 255, dtype=np.uint8)])
        if bg is not None:
            dist = np.abs(f.astype(np.int16) - bg).sum(axis=2)
            bgra[:, :, 3] = np.where(dist < KEY_TOLERANCE, 0, 255).astype(np.uint8)
        sheet[r * frame_size:(r + 1) * frame_size,
              c * frame_size:(c + 1) * frame_size] = bgra

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix('.tmp.png')
    if not cv2.imwrite(str(tmp), sheet):
        return None
    os.replace(tmp, out_path)

    return {'path': str(out_path), 'columns': cols, 'rows': rows,
            'count': len(frames), 'frame_size': frame_size}


def _clear_stale(uuid: str, preview_path, frame_size: int, keep: Path):
    """Drop other sheets for the same asset - old formats, or a stale count."""
    key = cache_key(uuid, preview_path, frame_size)
    if not key:
        return
    try:
        for path in get_cache_dir().glob(f"{key}_*.png"):
            if path != keep:
                path.unlink(missing_ok=True)
    except OSError:
        pass


def parse_sprite_path(path) -> Optional[Dict]:
    """Recover the layout from a cached sheet's filename."""
    try:
        uuid, mtime, size, maxf = Path(path).stem.split('_')[-4:]
        size = int(size)
    except (ValueError, AttributeError):
        return None
    from PyQt6.QtGui import QImage
    img = QImage(str(path))
    if img.isNull():
        return None
    cols, rows = img.width() // size, img.height() // size
    return {'path': str(path), 'columns': cols, 'rows': rows, 'frame_size': size}


def get_or_build(uuid: str, preview_path,
                 frame_size: int = DEFAULT_FRAME_SIZE,
                 max_frames: int = DEFAULT_MAX_FRAMES) -> Optional[Dict]:
    """Cached sheet for this preview, building it on first use."""
    if not preview_path or not os.path.exists(preview_path):
        return None
    cached = find_cached(uuid, preview_path, frame_size)
    if cached:
        return cached

    # Build to a temp name first: the real frame count isn't known until the
    # clip has been decoded, and the count is part of the final filename.
    staging = get_cache_dir() / f"{uuid}_building_{frame_size}.png"
    meta = build_sprite_sheet(preview_path, staging, frame_size, max_frames)
    if not meta:
        return None

    final = sprite_path_for(uuid, preview_path, frame_size, meta['count'])
    if final is None:
        staging.unlink(missing_ok=True)
        return None
    os.replace(staging, final)
    _clear_stale(uuid, preview_path, frame_size, keep=final)
    meta['path'] = str(final)
    return meta


def cache_size_mb() -> float:
    """Current size of the sprite cache, in MB."""
    try:
        return sum(f.stat().st_size for f in get_cache_dir().glob('*.png')) / 1024 / 1024
    except OSError:
        return 0.0


def prune_cache(max_mb: float = MAX_CACHE_MB) -> int:
    """Delete least-recently-used sheets until the cache fits in max_mb.

    Sheets are derived data - anything deleted is rebuilt on next view for the
    cost of one decode, so evicting is cheap and always safe. Uses access time
    where the filesystem tracks it, falling back to modified time.

    Returns the number of files deleted.
    """
    try:
        files = list(get_cache_dir().glob('*.png'))
    except OSError:
        return 0

    total = 0
    stats = []
    for f in files:
        try:
            st = f.stat()
        except OSError:
            continue
        total += st.st_size
        stats.append((max(st.st_atime, st.st_mtime), st.st_size, f))

    limit = max_mb * 1024 * 1024
    if total <= limit:
        return 0

    stats.sort()                      # oldest first
    deleted = 0
    for _, size, f in stats:
        if total <= limit:
            break
        try:
            f.unlink()
            total -= size
            deleted += 1
        except OSError:
            continue
    if deleted:
        logger.info(f"Pruned {deleted} sprite sheet(s); cache now "
                    f"{total/1024/1024:.0f}MB of {max_mb:.0f}MB")
    return deleted


__all__ = ['build_sprite_sheet', 'get_or_build', 'sprite_path_for',
           'parse_sprite_path', 'find_cached', 'cache_key', 'get_cache_dir', 'grid_for',
           'prune_cache', 'cache_size_mb', 'MAX_CACHE_MB']
