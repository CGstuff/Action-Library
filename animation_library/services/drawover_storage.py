"""
DrawoverStorage - File storage management for frame annotations

Handles saving/loading drawover JSON files and PNG cache generation.
"""

import json
import uuid as uuid_lib
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime
from collections import OrderedDict

from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtGui import QImage, QPainter, QColor, QPen, QPainterPath, QFont
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF

from ..config import Config


class DrawoverStorage:
    """
    Manages drawover file storage on disk.

    File structure:
        storage/.meta/drawovers/{uuid}/{version}/
        ├── f0125.json       # Frame 125 vector data
        ├── f0125.png        # Frame 125 PNG cache
        └── manifest.json    # Index of all drawovers
    """

    JSON_VERSION = "1.0"

    def __init__(self, base_path: Optional[Path] = None):
        if base_path is None:
            base_path = Path(Config.get_database_folder())
        self._base = base_path / 'drawovers'
        self._base.mkdir(parents=True, exist_ok=True)

    def get_drawover_dir(self, animation_uuid: str, version: str) -> Path:
        """Get directory for a version's drawovers."""
        return self._base / animation_uuid / version

    def get_drawover_path(self, animation_uuid: str, version: str, frame: int) -> Path:
        """Get path for a frame's drawover JSON."""
        return self.get_drawover_dir(animation_uuid, version) / f'f{frame:04d}.json'

    def get_png_cache_path(self, animation_uuid: str, version: str, frame: int) -> Path:
        """Get path for a frame's PNG cache."""
        return self.get_drawover_dir(animation_uuid, version) / f'f{frame:04d}.png'

    def get_manifest_path(self, animation_uuid: str, version: str) -> Path:
        """Get path for manifest file."""
        return self.get_drawover_dir(animation_uuid, version) / 'manifest.json'

    # ==================== Save/Load ====================

    def save_drawover(
        self,
        animation_uuid: str,
        version: str,
        frame: int,
        strokes: List[Dict],
        author: str = '',
        canvas_size: Tuple[int, int] = (1920, 1080)
    ) -> bool:
        """
        Save drawover data for a frame.

        Args:
            animation_uuid: Animation UUID
            version: Version label (e.g., 'v001')
            frame: Frame number
            strokes: List of stroke dictionaries
            author: Current user (for new strokes)
            canvas_size: Video dimensions

        Returns:
            True if saved successfully
        """
        try:
            path = self.get_drawover_path(animation_uuid, version, frame)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing data or create new
            existing = self.load_drawover(animation_uuid, version, frame)
            now = datetime.utcnow().isoformat() + 'Z'

            if existing:
                data = existing
                data['modified_at'] = now
                data['strokes'] = strokes
            else:
                data = {
                    'version': self.JSON_VERSION,
                    'frame': frame,
                    'canvas_size': list(canvas_size),
                    'created_at': now,
                    'modified_at': now,
                    'author': author,
                    'strokes': strokes,
                    'deleted_strokes': []
                }

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            # Invalidate PNG cache
            png_path = self.get_png_cache_path(animation_uuid, version, frame)
            if png_path.exists():
                png_path.unlink()

            # Update manifest
            self._update_manifest(animation_uuid, version)

            return True

        except Exception as e:
            print(f"Error saving drawover: {e}")
            return False

    def load_drawover(self, animation_uuid: str, version: str, frame: int) -> Optional[Dict]:
        """Load drawover data for a frame."""
        path = self.get_drawover_path(animation_uuid, version, frame)
        if not path.exists():
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading drawover: {e}")
            return None

    def delete_drawover(self, animation_uuid: str, version: str, frame: int) -> bool:
        """Delete a frame's drawover files (hard delete)."""
        try:
            json_path = self.get_drawover_path(animation_uuid, version, frame)
            png_path = self.get_png_cache_path(animation_uuid, version, frame)

            if json_path.exists():
                json_path.unlink()
            if png_path.exists():
                png_path.unlink()

            self._update_manifest(animation_uuid, version)
            return True

        except Exception as e:
            print(f"Error deleting drawover: {e}")
            return False

    def has_drawover(self, animation_uuid: str, version: str, frame: int) -> bool:
        """Check if a frame has actual strokes (not just soft-deleted)."""
        path = self.get_drawover_path(animation_uuid, version, frame)
        if not path.exists():
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return bool(data.get('strokes', []))
        except (json.JSONDecodeError, IOError):
            return False

    def list_frames_with_drawovers(self, animation_uuid: str, version: str) -> List[int]:
        """Get list of frames that have actual strokes (not soft-deleted)."""
        drawover_dir = self.get_drawover_dir(animation_uuid, version)
        if not drawover_dir.exists():
            return []

        frames = []
        for path in drawover_dir.glob('f*.json'):
            try:
                # Extract frame number from filename (f0125.json -> 125)
                frame_str = path.stem[1:]  # Remove 'f' prefix
                frame_num = int(frame_str)

                # Check if the file actually has strokes (not just soft-deleted)
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    strokes = data.get('strokes', [])
                    if strokes:  # Only include if there are actual strokes
                        frames.append(frame_num)
            except (ValueError, json.JSONDecodeError, IOError):
                continue

        return sorted(frames)

    # ==================== Stroke Management ====================

    def add_stroke(
        self,
        animation_uuid: str,
        version: str,
        frame: int,
        stroke: Dict,
        author: str = '',
        canvas_size: Tuple[int, int] = (1920, 1080)
    ) -> Optional[str]:
        """
        Add a single stroke to a frame's drawover.

        Returns:
            Stroke ID if successful, None otherwise
        """
        # Generate stroke ID if not present
        if 'id' not in stroke:
            stroke['id'] = f"stroke_{uuid_lib.uuid4().hex[:8]}"

        stroke['created_at'] = datetime.utcnow().isoformat() + 'Z'
        stroke['author'] = author

        # Load existing or create new
        existing = self.load_drawover(animation_uuid, version, frame)
        if existing:
            existing['strokes'].append(stroke)
            strokes = existing['strokes']
        else:
            strokes = [stroke]

        if self.save_drawover(animation_uuid, version, frame, strokes, author, canvas_size):
            return stroke['id']
        return None

    def remove_stroke(
        self,
        animation_uuid: str,
        version: str,
        frame: int,
        stroke_id: str,
        soft_delete: bool = True,
        deleted_by: str = ''
    ) -> bool:
        """
        Remove a stroke from a frame's drawover.

        Args:
            soft_delete: If True, move to deleted_strokes array (Studio Mode)
                        If False, permanently remove (Solo Mode)
        """
        data = self.load_drawover(animation_uuid, version, frame)
        if not data:
            return False

        # Find stroke
        stroke_to_remove = None
        for i, stroke in enumerate(data['strokes']):
            if stroke.get('id') == stroke_id:
                stroke_to_remove = data['strokes'].pop(i)
                break

        if not stroke_to_remove:
            return False

        if soft_delete:
            # Move to deleted_strokes
            if 'deleted_strokes' not in data:
                data['deleted_strokes'] = []

            deleted_entry = {
                'id': stroke_id,
                'deleted_at': datetime.utcnow().isoformat() + 'Z',
                'deleted_by': deleted_by,
                'original_data': stroke_to_remove
            }
            data['deleted_strokes'].append(deleted_entry)

        # Save updated data
        path = self.get_drawover_path(animation_uuid, version, frame)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            # Invalidate PNG cache
            png_path = self.get_png_cache_path(animation_uuid, version, frame)
            if png_path.exists():
                png_path.unlink()

            self._update_manifest(animation_uuid, version)
            return True

        except Exception as e:
            print(f"Error removing stroke: {e}")
            return False

    def restore_stroke(
        self,
        animation_uuid: str,
        version: str,
        frame: int,
        stroke_id: str,
        restored_by: str = ''
    ) -> bool:
        """Restore a soft-deleted stroke."""
        data = self.load_drawover(animation_uuid, version, frame)
        if not data or 'deleted_strokes' not in data:
            return False

        # Find deleted stroke
        for i, deleted in enumerate(data['deleted_strokes']):
            if deleted.get('id') == stroke_id:
                # Restore original data
                original = deleted['original_data']
                data['strokes'].append(original)
                data['deleted_strokes'].pop(i)

                # Save
                path = self.get_drawover_path(animation_uuid, version, frame)
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

                # Invalidate cache
                png_path = self.get_png_cache_path(animation_uuid, version, frame)
                if png_path.exists():
                    png_path.unlink()

                return True

        return False

    def clear_frame(
        self,
        animation_uuid: str,
        version: str,
        frame: int,
        soft_delete: bool = True,
        deleted_by: str = ''
    ) -> bool:
        """Clear all strokes on a frame."""
        print(f"[DEBUG Storage.clear_frame] uuid={animation_uuid}, version={version}, frame={frame}")
        print(f"[DEBUG Storage.clear_frame] soft_delete={soft_delete}, deleted_by={deleted_by}")

        path = self.get_drawover_path(animation_uuid, version, frame)
        print(f"[DEBUG Storage.clear_frame] JSON path: {path}")
        print(f"[DEBUG Storage.clear_frame] Path exists: {path.exists()}")

        data = self.load_drawover(animation_uuid, version, frame)
        print(f"[DEBUG Storage.clear_frame] Loaded data: {data is not None}")
        if data:
            print(f"[DEBUG Storage.clear_frame] Strokes in data: {len(data.get('strokes', []))}")

        if not data:
            print("[DEBUG Storage.clear_frame] No data found - returning True (nothing to clear)")
            return True  # Nothing to clear

        if soft_delete:
            # Move all to deleted
            if 'deleted_strokes' not in data:
                data['deleted_strokes'] = []

            now = datetime.utcnow().isoformat() + 'Z'
            for stroke in data['strokes']:
                deleted_entry = {
                    'id': stroke.get('id', ''),
                    'deleted_at': now,
                    'deleted_by': deleted_by,
                    'original_data': stroke
                }
                data['deleted_strokes'].append(deleted_entry)

        data['strokes'] = []
        print(f"[DEBUG Storage.clear_frame] Strokes after clear: {len(data['strokes'])}")

        # Save
        path = self.get_drawover_path(animation_uuid, version, frame)
        try:
            print(f"[DEBUG Storage.clear_frame] Saving to {path}...")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print("[DEBUG Storage.clear_frame] Saved successfully")

            # Invalidate cache
            png_path = self.get_png_cache_path(animation_uuid, version, frame)
            if png_path.exists():
                png_path.unlink()

            self._update_manifest(animation_uuid, version)
            return True

        except Exception as e:
            print(f"Error clearing frame: {e}")
            return False

    # ==================== PNG Rendering ====================

    def render_to_png(
        self,
        animation_uuid: str,
        version: str,
        frame: int,
        size: Tuple[int, int]
    ) -> Optional[Path]:
        """
        Render drawover to PNG, using cache if valid.

        Returns:
            Path to PNG file, or None if no drawover exists
        """
        json_path = self.get_drawover_path(animation_uuid, version, frame)
        png_path = self.get_png_cache_path(animation_uuid, version, frame)

        if not json_path.exists():
            return None

        # Check if cache is valid
        if png_path.exists():
            if png_path.stat().st_mtime >= json_path.stat().st_mtime:
                return png_path

        # Load and render
        data = self.load_drawover(animation_uuid, version, frame)
        if not data:
            return None

        try:
            self._render_strokes_to_png(data, png_path, size)
            return png_path
        except Exception as e:
            print(f"Error rendering PNG: {e}")
            return None

    def _render_strokes_to_png(
        self,
        data: Dict,
        output_path: Path,
        size: Tuple[int, int]
    ):
        """Render strokes to PNG file with transparency."""
        width, height = size
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))  # Transparent

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Check if strokes use UV format (normalized 0-1 coordinates)
        # or legacy pixel coordinates
        canvas_size = data.get('canvas_size', [width, height])

        for stroke in data.get('strokes', []):
            if stroke.get('format') == 'uv':
                # UV format: coordinates are 0-1 normalized
                # Scale directly from UV to output size
                self._render_stroke_uv(painter, stroke, width, height)
            else:
                # Legacy pixel format: scale from canvas_size to output size
                scale_x = width / canvas_size[0] if canvas_size[0] > 0 else 1
                scale_y = height / canvas_size[1] if canvas_size[1] > 0 else 1
                self._render_stroke(painter, stroke, scale_x, scale_y)

        painter.end()
        image.save(str(output_path), 'PNG')

    def _render_stroke(
        self,
        painter: QPainter,
        stroke: Dict,
        scale_x: float,
        scale_y: float
    ):
        """Render a single stroke."""
        stroke_type = stroke.get('type', 'path')
        color = QColor(stroke.get('color', '#FF5722'))
        opacity = stroke.get('opacity', 1.0)
        color.setAlphaF(opacity)
        width = stroke.get('width', 3)

        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        if stroke_type == 'path':
            points = stroke.get('points', [])
            if len(points) >= 2:
                path = QPainterPath()
                path.moveTo(points[0][0] * scale_x, points[0][1] * scale_y)
                for point in points[1:]:
                    path.lineTo(point[0] * scale_x, point[1] * scale_y)
                painter.drawPath(path)

        elif stroke_type == 'line':
            start = stroke.get('start', [0, 0])
            end = stroke.get('end', [0, 0])
            painter.drawLine(
                QPointF(start[0] * scale_x, start[1] * scale_y),
                QPointF(end[0] * scale_x, end[1] * scale_y)
            )

        elif stroke_type == 'arrow':
            start = stroke.get('start', [0, 0])
            end = stroke.get('end', [0, 0])
            head_size = stroke.get('head_size', 12) * scale_x

            # Draw line
            start_pt = QPointF(start[0] * scale_x, start[1] * scale_y)
            end_pt = QPointF(end[0] * scale_x, end[1] * scale_y)
            painter.drawLine(start_pt, end_pt)

            # Draw arrow head
            import math
            line = QLineF(start_pt, end_pt)
            angle = math.atan2(-line.dy(), line.dx())

            p1 = end_pt + QPointF(
                math.cos(angle + math.pi * 0.8) * head_size,
                -math.sin(angle + math.pi * 0.8) * head_size
            )
            p2 = end_pt + QPointF(
                math.cos(angle - math.pi * 0.8) * head_size,
                -math.sin(angle - math.pi * 0.8) * head_size
            )

            painter.drawLine(end_pt, p1)
            painter.drawLine(end_pt, p2)

        elif stroke_type == 'rect':
            bounds = stroke.get('bounds', [0, 0, 100, 100])
            fill = stroke.get('fill', False)
            rect = QRectF(
                bounds[0] * scale_x,
                bounds[1] * scale_y,
                bounds[2] * scale_x,
                bounds[3] * scale_y
            )
            if fill:
                painter.fillRect(rect, color)
            else:
                painter.drawRect(rect)

        elif stroke_type == 'ellipse':
            bounds = stroke.get('bounds', [0, 0, 100, 100])
            fill = stroke.get('fill', False)
            rect = QRectF(
                bounds[0] * scale_x,
                bounds[1] * scale_y,
                bounds[2] * scale_x,
                bounds[3] * scale_y
            )
            if fill:
                painter.setBrush(color)
            painter.drawEllipse(rect)

        elif stroke_type == 'text':
            position = stroke.get('position', [0, 0])
            text = stroke.get('text', '')
            font_size = int(stroke.get('font_size', 14) * scale_x)
            bg_color = stroke.get('background', None)

            font = QFont('Arial', font_size)
            painter.setFont(font)

            pos = QPointF(position[0] * scale_x, position[1] * scale_y)

            if bg_color:
                bg = QColor(bg_color)
                bg.setAlphaF(stroke.get('opacity', 0.8))
                metrics = painter.fontMetrics()
                text_rect = metrics.boundingRect(text)
                text_rect.moveTopLeft(pos.toPoint())
                text_rect.adjust(-4, -2, 4, 2)
                painter.fillRect(text_rect, bg)

            painter.setPen(color)
            painter.drawText(pos, text)

    def _render_stroke_uv(
        self,
        painter: QPainter,
        stroke: Dict,
        width: int,
        height: int
    ):
        """
        Render a single stroke from UV coordinates.

        UV coordinates are normalized 0-1, where (0,0) is top-left
        and (1,1) is bottom-right of the video frame.
        """
        stroke_type = stroke.get('type', 'path')
        color = QColor(stroke.get('color', '#FF5722'))
        opacity = stroke.get('opacity', 1.0)
        color.setAlphaF(opacity)

        # Width is stored normalized relative to min(width, height)
        min_dim = min(width, height)
        normalized_width = stroke.get('width', 0.005)
        stroke_width = max(1, normalized_width * min_dim)

        pen = QPen(color, stroke_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        if stroke_type == 'path':
            points = stroke.get('points', [])
            if len(points) >= 2:
                path = QPainterPath()
                # UV to pixel: multiply by dimensions
                path.moveTo(points[0][0] * width, points[0][1] * height)
                for point in points[1:]:
                    path.lineTo(point[0] * width, point[1] * height)
                painter.drawPath(path)

        elif stroke_type == 'line':
            start = stroke.get('start', [0, 0])
            end = stroke.get('end', [0, 0])
            painter.drawLine(
                QPointF(start[0] * width, start[1] * height),
                QPointF(end[0] * width, end[1] * height)
            )

        elif stroke_type == 'arrow':
            start = stroke.get('start', [0, 0])
            end = stroke.get('end', [0, 0])
            # Head size is also normalized
            head_size = stroke.get('head_size', 0.02) * min_dim

            start_pt = QPointF(start[0] * width, start[1] * height)
            end_pt = QPointF(end[0] * width, end[1] * height)
            painter.drawLine(start_pt, end_pt)

            # Draw arrow head
            import math
            line = QLineF(start_pt, end_pt)
            if line.length() > 0:
                angle = math.atan2(-line.dy(), line.dx())

                p1 = end_pt + QPointF(
                    math.cos(angle + math.pi * 0.8) * head_size,
                    -math.sin(angle + math.pi * 0.8) * head_size
                )
                p2 = end_pt + QPointF(
                    math.cos(angle - math.pi * 0.8) * head_size,
                    -math.sin(angle - math.pi * 0.8) * head_size
                )

                painter.drawLine(end_pt, p1)
                painter.drawLine(end_pt, p2)

        elif stroke_type == 'rect':
            bounds = stroke.get('bounds', [0, 0, 0.5, 0.5])
            fill = stroke.get('fill', False)
            # bounds are [u, v, width_uv, height_uv]
            rect = QRectF(
                bounds[0] * width,
                bounds[1] * height,
                bounds[2] * width,
                bounds[3] * height
            )
            if fill:
                painter.fillRect(rect, color)
            else:
                painter.drawRect(rect)

        elif stroke_type == 'ellipse':
            bounds = stroke.get('bounds', [0, 0, 0.5, 0.5])
            fill = stroke.get('fill', False)
            rect = QRectF(
                bounds[0] * width,
                bounds[1] * height,
                bounds[2] * width,
                bounds[3] * height
            )
            if fill:
                painter.setBrush(color)
            painter.drawEllipse(rect)

        elif stroke_type == 'text':
            position = stroke.get('position', [0, 0])
            text = stroke.get('text', '')
            # Font size is normalized
            font_size = int(stroke.get('font_size', 0.02) * min_dim)
            bg_color = stroke.get('background', None)

            font = QFont('Arial', max(8, font_size))
            painter.setFont(font)

            pos = QPointF(position[0] * width, position[1] * height)

            if bg_color:
                bg = QColor(bg_color)
                bg.setAlphaF(stroke.get('opacity', 0.8))
                metrics = painter.fontMetrics()
                text_rect = metrics.boundingRect(text)
                text_rect.moveTopLeft(pos.toPoint())
                text_rect.adjust(-4, -2, 4, 2)
                painter.fillRect(text_rect, bg)

            painter.setPen(color)
            painter.drawText(pos, text)

    # ==================== Manifest ====================

    def _update_manifest(self, animation_uuid: str, version: str):
        """Update manifest file for a version."""
        drawover_dir = self.get_drawover_dir(animation_uuid, version)
        if not drawover_dir.exists():
            return

        manifest_path = self.get_manifest_path(animation_uuid, version)

        frames = {}
        total_strokes = 0

        for json_path in drawover_dir.glob('f*.json'):
            try:
                frame_str = json_path.stem[1:]
                frame = int(frame_str)

                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                stroke_count = len(data.get('strokes', []))
                total_strokes += stroke_count

                frames[str(frame)] = {
                    'json': json_path.name,
                    'png': f'f{frame:04d}.png',
                    'modified_at': data.get('modified_at', ''),
                    'stroke_count': stroke_count
                }

            except Exception:
                continue

        manifest = {
            'version': '1.0',
            'animation_uuid': animation_uuid,
            'version_label': version,
            'frames': frames,
            'total_frames': len(frames),
            'total_strokes': total_strokes
        }

        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

    def get_manifest(self, animation_uuid: str, version: str) -> Optional[Dict]:
        """Get manifest data for a version."""
        path = self.get_manifest_path(animation_uuid, version)
        if not path.exists():
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None


# ==================== Cache ====================

class DrawoverCache:
    """LRU cache for loaded drawover data."""

    def __init__(self, max_size: int = 50):
        self._cache: OrderedDict[str, Dict] = OrderedDict()
        self._max_size = max_size

    def _make_key(self, animation_uuid: str, version: str, frame: int) -> str:
        return f"{animation_uuid}:{version}:{frame}"

    def get(self, animation_uuid: str, version: str, frame: int) -> Optional[Dict]:
        key = self._make_key(animation_uuid, version, frame)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, animation_uuid: str, version: str, frame: int, data: Dict):
        key = self._make_key(animation_uuid, version, frame)
        self._cache[key] = data
        self._cache.move_to_end(key)

        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate(self, animation_uuid: str, version: str, frame: int):
        key = self._make_key(animation_uuid, version, frame)
        self._cache.pop(key, None)

    def invalidate_version(self, animation_uuid: str, version: str):
        """Invalidate all cached data for a version."""
        prefix = f"{animation_uuid}:{version}:"
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
        for key in keys_to_remove:
            self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()


# ==================== Singleton ====================

_storage_instance: Optional[DrawoverStorage] = None
_cache_instance: Optional[DrawoverCache] = None


def get_drawover_storage() -> DrawoverStorage:
    """Get singleton DrawoverStorage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = DrawoverStorage()
    return _storage_instance


def get_drawover_cache() -> DrawoverCache:
    """Get singleton DrawoverCache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DrawoverCache()
    return _cache_instance


__all__ = [
    'DrawoverStorage',
    'DrawoverCache',
    'get_drawover_storage',
    'get_drawover_cache'
]
