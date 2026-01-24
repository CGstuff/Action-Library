"""
ThumbnailLoader - Async thumbnail loading with QThreadPool

Pattern: Background loading with QRunnable workers
Inspired by: Maya Studio Library + Hybrid plan optimizations
"""

import time
from pathlib import Path
from typing import Optional, Tuple, Set, Dict, Any
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, QThreadPool
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPixmapCache, QImage

from ..config import Config
from ..utils.gradient_utils import composite_image_on_gradient_colors
from ..utils.image_utils import load_image_as_qimage, scale_image


class ThumbnailLoadSignals(QObject):
    """Signals for ThumbnailLoadTask"""

    load_complete = pyqtSignal(str, str, QImage, float)  # uuid, cache_key, image, elapsed_ms
    load_failed = pyqtSignal(str, str, str)  # uuid, cache_key, error_message


class ThumbnailLoadTask(QRunnable):
    """
    Background task for loading and compositing thumbnails

    Features:
    - Loads image from disk
    - Composites on gradient background
    - DPI scaling support
    - Performance timing

    Usage:
        task = ThumbnailLoadTask(uuid, thumbnail_path, gradient_colors, cache_key)
        threadpool.start(task)
    """

    def __init__(
        self,
        animation_uuid: str,
        thumbnail_path: Path,
        gradient_top: Tuple[float, float, float],
        gradient_bottom: Tuple[float, float, float],
        cache_key: str,
        canvas_size: int = 300
    ):
        super().__init__()
        self.animation_uuid = animation_uuid
        self.thumbnail_path = thumbnail_path
        self.gradient_top = gradient_top
        self.gradient_bottom = gradient_bottom
        self.cache_key = cache_key
        self.canvas_size = canvas_size
        self.signals = ThumbnailLoadSignals()
        self.start_time = time.time()

    def run(self):
        """Execute thumbnail loading task"""
        try:
            # Load source image
            source_image = load_image_as_qimage(self.thumbnail_path)
            if source_image is None:
                self.signals.load_failed.emit(
                    self.animation_uuid,
                    self.cache_key,
                    f"Failed to load image: {self.thumbnail_path}"
                )
                return

            # Scale to fit canvas
            source_image = scale_image(source_image, self.canvas_size, smooth=True)

            # Composite on gradient
            composited_image = composite_image_on_gradient_colors(
                source_image,
                self.gradient_top,
                self.gradient_bottom,
                self.canvas_size
            )

            # Apply DPI scaling (Maya-inspired)
            if QApplication.instance():
                screen = QApplication.primaryScreen()
                if screen:
                    device_ratio = screen.devicePixelRatio()
                    composited_image.setDevicePixelRatio(device_ratio)

            # Calculate elapsed time
            elapsed_ms = (time.time() - self.start_time) * 1000

            # Emit success signal
            self.signals.load_complete.emit(
                self.animation_uuid,
                self.cache_key,
                composited_image,
                elapsed_ms
            )

        except Exception as e:
            self.signals.load_failed.emit(
                self.animation_uuid,
                self.cache_key,
                f"Thumbnail load error: {e}"
            )


class ThumbnailLoader(QObject):
    """
    Manages async thumbnail loading with QThreadPool

    Features:
    - Background loading with worker threads
    - Load deduplication (prevents duplicate requests)
    - Performance monitoring (cache hit rates, load times)
    - QPixmapCache integration
    - DPI scaling support

    Usage:
        loader = ThumbnailLoader()
        loader.thumbnail_loaded.connect(on_thumbnail_ready)
        pixmap = loader.load_thumbnail(uuid, path, gradient_colors)
    """

    # Signals
    thumbnail_loaded = pyqtSignal(str, QPixmap)  # uuid, pixmap
    thumbnail_failed = pyqtSignal(str, str)  # uuid, error_message

    def __init__(self, parent=None):
        super().__init__(parent)

        # Thread pool for background loading
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(Config.THUMBNAIL_THREAD_COUNT)

        # Load deduplication (Maya-inspired)
        self.pending_requests: Set[str] = set()

        # Performance monitoring (Maya-inspired)
        self.load_times: list[float] = []
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.total_requests: int = 0


    def load_thumbnail(
        self,
        animation_uuid: str,
        thumbnail_path: Path,
        gradient_top: Tuple[float, float, float],
        gradient_bottom: Tuple[float, float, float],
        use_custom_gradient: bool = False
    ) -> Optional[QPixmap]:
        """
        Load thumbnail (from cache or async)

        Args:
            animation_uuid: Animation UUID
            thumbnail_path: Path to thumbnail image
            gradient_top: Top gradient color (R, G, B) 0-1
            gradient_bottom: Bottom gradient color (R, G, B) 0-1
            use_custom_gradient: Whether using custom gradient

        Returns:
            QPixmap if in cache, None if loading in background
        """
        self.total_requests += 1

        # Generate cache key
        cache_key = self._generate_cache_key(
            animation_uuid,
            gradient_top,
            gradient_bottom
        )

        # Check cache first
        pixmap = QPixmapCache.find(cache_key)
        if pixmap:
            self.cache_hits += 1
            self._log_performance()
            return pixmap

        self.cache_misses += 1

        # Check if already loading (deduplication)
        if cache_key in self.pending_requests:
            # Already loading, don't start duplicate request
            return None

        # Not in cache - start background load
        self.pending_requests.add(cache_key)

        task = ThumbnailLoadTask(
            animation_uuid,
            thumbnail_path,
            gradient_top,
            gradient_bottom,
            cache_key,
            canvas_size=Config.THUMBNAIL_SIZE
        )

        # Connect signals
        task.signals.load_complete.connect(self._on_load_complete)
        task.signals.load_failed.connect(self._on_load_failed)

        # Start task
        self.thread_pool.start(task)

        return None

    def _on_load_complete(self, uuid: str, cache_key: str, image: QImage, elapsed_ms: float):
        """Handle successful thumbnail load"""

        # Remove from pending
        self.pending_requests.discard(cache_key)

        # Track load time
        self.load_times.append(elapsed_ms)

        # Convert to pixmap
        pixmap = QPixmap.fromImage(image)

        # Store in cache
        QPixmapCache.insert(cache_key, pixmap)

        # Emit signal
        self.thumbnail_loaded.emit(uuid, pixmap)

        self._log_performance()

    def _on_load_failed(self, uuid: str, cache_key: str, error_message: str):
        """Handle failed thumbnail load"""

        # Remove from pending using the exact cache key
        self.pending_requests.discard(cache_key)

        # Emit failure signal
        self.thumbnail_failed.emit(uuid, error_message)

    def _generate_cache_key(
        self,
        animation_uuid: str,
        gradient_top: Tuple[float, float, float],
        gradient_bottom: Tuple[float, float, float]
    ) -> str:
        """
        Generate cache key for thumbnail

        Args:
            animation_uuid: Animation UUID
            gradient_top: Top gradient color
            gradient_bottom: Bottom gradient color

        Returns:
            Unique cache key string
        """
        # Include gradient colors in key so custom gradients cache separately
        return f"{animation_uuid}_{gradient_top}_{gradient_bottom}"

    def _log_performance(self):
        """Log performance statistics periodically"""
        pass  # Performance logging disabled

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics (Maya-inspired)

        Returns:
            Dict with cache statistics
        """
        hit_rate = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0
        avg_load_time = (sum(self.load_times) / len(self.load_times)) if self.load_times else 0

        return {
            'total_requests': self.total_requests,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': hit_rate,
            'avg_load_time_ms': avg_load_time,
            'pending_count': len(self.pending_requests),
            'thread_count': self.thread_pool.maxThreadCount(),
        }

    def clear_cache(self):
        """Clear QPixmapCache"""
        QPixmapCache.clear()

    def invalidate_animation(self, animation_uuid: str):
        """
        Invalidate cached thumbnails for a specific animation.

        Since QPixmapCache doesn't support wildcard removal, this clears
        the entire cache. The thumbnails will be reloaded on demand.

        Args:
            animation_uuid: UUID of the animation to invalidate
        """
        # QPixmapCache.remove() requires exact key, but we don't track
        # which gradient combinations were used. Clear all for safety.
        QPixmapCache.clear()

        # Also remove from pending requests if any
        keys_to_remove = [k for k in self.pending_requests if k.startswith(animation_uuid)]
        for key in keys_to_remove:
            self.pending_requests.discard(key)

    def reset_stats(self):
        """Reset performance statistics"""
        self.load_times.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_requests = 0


# Singleton instance
_thumbnail_loader_instance: Optional[ThumbnailLoader] = None


def get_thumbnail_loader() -> ThumbnailLoader:
    """
    Get global ThumbnailLoader singleton

    Returns:
        Global ThumbnailLoader instance
    """
    global _thumbnail_loader_instance
    if _thumbnail_loader_instance is None:
        _thumbnail_loader_instance = ThumbnailLoader()
    return _thumbnail_loader_instance


__all__ = ['ThumbnailLoader', 'ThumbnailLoadTask', 'get_thumbnail_loader']
