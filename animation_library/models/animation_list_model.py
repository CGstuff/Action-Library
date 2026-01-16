"""
AnimationListModel - Qt Model for animation data

Pattern: Model/View architecture with QAbstractListModel
Inspired by: Hybrid plan + Maya Studio Library patterns
"""

import time
from enum import IntEnum
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import (
    QAbstractListModel, QModelIndex, Qt, QMimeData, QByteArray
)

from ..config import Config
from ..services.database_service import get_database_service
from ..services.notes_database import get_notes_database


class AnimationRole(IntEnum):
    """Custom Qt roles for animation data"""

    # Required fields
    UUIDRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    FolderIdRole = Qt.ItemDataRole.UserRole + 3
    RigTypeRole = Qt.ItemDataRole.UserRole + 4

    # Rig information
    ArmatureNameRole = Qt.ItemDataRole.UserRole + 10
    BoneCountRole = Qt.ItemDataRole.UserRole + 11

    # Animation timing
    FrameStartRole = Qt.ItemDataRole.UserRole + 20
    FrameEndRole = Qt.ItemDataRole.UserRole + 21
    FrameCountRole = Qt.ItemDataRole.UserRole + 22
    DurationSecondsRole = Qt.ItemDataRole.UserRole + 23
    FPSRole = Qt.ItemDataRole.UserRole + 24

    # File paths
    BlendFilePathRole = Qt.ItemDataRole.UserRole + 30
    JSONFilePathRole = Qt.ItemDataRole.UserRole + 31
    PreviewPathRole = Qt.ItemDataRole.UserRole + 32
    ThumbnailPathRole = Qt.ItemDataRole.UserRole + 33
    FileSizeMBRole = Qt.ItemDataRole.UserRole + 34

    # Organization
    DescriptionRole = Qt.ItemDataRole.UserRole + 40
    TagsRole = Qt.ItemDataRole.UserRole + 41
    AuthorRole = Qt.ItemDataRole.UserRole + 42

    # Thumbnail gradient
    UseCustomGradientRole = Qt.ItemDataRole.UserRole + 50
    GradientTopRole = Qt.ItemDataRole.UserRole + 51
    GradientBottomRole = Qt.ItemDataRole.UserRole + 52

    # Timestamps
    CreatedDateRole = Qt.ItemDataRole.UserRole + 60
    ModifiedDateRole = Qt.ItemDataRole.UserRole + 61

    # User features (v2)
    IsFavoriteRole = Qt.ItemDataRole.UserRole + 70
    LastViewedDateRole = Qt.ItemDataRole.UserRole + 71
    CustomOrderRole = Qt.ItemDataRole.UserRole + 72
    IsLockedRole = Qt.ItemDataRole.UserRole + 73

    # Versioning (v5)
    VersionRole = Qt.ItemDataRole.UserRole + 80
    VersionLabelRole = Qt.ItemDataRole.UserRole + 81
    VersionGroupIdRole = Qt.ItemDataRole.UserRole + 82
    IsLatestRole = Qt.ItemDataRole.UserRole + 83

    # Lifecycle status (v6)
    StatusRole = Qt.ItemDataRole.UserRole + 90

    # Pose flag (v7)
    IsPoseRole = Qt.ItemDataRole.UserRole + 95
    IsPartialRole = Qt.ItemDataRole.UserRole + 96

    # Review notes indicators
    HasNotesRole = Qt.ItemDataRole.UserRole + 97
    UnresolvedCommentCountRole = Qt.ItemDataRole.UserRole + 98

    # Complete data dict
    AnimationDataRole = Qt.ItemDataRole.UserRole + 100


class AnimationListModel(QAbstractListModel):
    """
    Qt model for animation list

    Features:
    - Lightweight data storage
    - Custom Qt roles for all fields
    - Sparse data access with .get()
    - Performance logging
    - Drag & drop support

    Usage:
        model = AnimationListModel()
        model.set_animations(animation_list)
        view.setModel(model)
    """

    def __init__(self, parent=None, db_service=None):
        super().__init__(parent)
        self._animations: List[Dict[str, Any]] = []
        self._db_service = db_service  # Lazy init - use get_db_service()

        # Performance monitoring (Maya-inspired)
        self._load_time: float = 0.0
        self._data_access_count: int = 0

        # Cache for animations with notes (for badge display)
        self._animations_with_notes: set = set()
        self._unresolved_counts: dict = {}

    def _get_db_service(self):
        """Get database service (lazy initialization)"""
        if self._db_service is None:
            self._db_service = get_database_service()
        return self._db_service

    def set_animations(self, animations: List[Dict[str, Any]]):
        """
        Set animation data

        Args:
            animations: List of animation dicts from database
        """
        start_time = time.time()

        self.beginResetModel()
        self._animations = animations
        self.endResetModel()

        self._load_time = (time.time() - start_time) * 1000  # Convert to ms

        # Refresh notes cache
        self.refresh_notes_cache()

    def refresh_notes_cache(self, emit_change: bool = False):
        """
        Refresh the cache of animations with notes/drawovers and unresolved counts.

        Args:
            emit_change: If True, emit dataChanged for all items to trigger repaint
        """
        try:
            notes_db = get_notes_database()
            self._animations_with_notes = notes_db.get_animations_with_notes()
            self._unresolved_counts = notes_db.get_unresolved_counts()
        except Exception:
            self._animations_with_notes = set()
            self._unresolved_counts = {}

        if emit_change and len(self._animations) > 0:
            # Notify view that data changed (for badge updates)
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._animations) - 1, 0)
            self.dataChanged.emit(top_left, bottom_right)

    def append_animation(self, animation: Dict[str, Any]):
        """
        Append single animation to model

        Args:
            animation: Animation data dict
        """
        row = len(self._animations)
        self.beginInsertRows(QModelIndex(), row, row)
        self._animations.append(animation)
        self.endInsertRows()

    def remove_animation(self, uuid: str) -> bool:
        """
        Remove animation by UUID

        Args:
            uuid: Animation UUID

        Returns:
            True if removed, False if not found
        """
        for i, anim in enumerate(self._animations):
            if anim.get('uuid') == uuid:
                self.beginRemoveRows(QModelIndex(), i, i)
                del self._animations[i]
                self.endRemoveRows()
                return True
        return False

    def update_animation(self, uuid: str, updates: Dict[str, Any]) -> bool:
        """
        Update animation data

        Args:
            uuid: Animation UUID
            updates: Dict of fields to update

        Returns:
            True if updated, False if not found
        """
        for i, anim in enumerate(self._animations):
            if anim.get('uuid') == uuid:
                anim.update(updates)
                # Emit dataChanged for this row
                index = self.index(i, 0)
                self.dataChanged.emit(index, index)
                return True
        return False

    def refresh_animation(self, uuid: str) -> bool:
        """
        Refresh animation data from database

        Args:
            uuid: Animation UUID

        Returns:
            True if refreshed, False if not found
        """
        db_service = self._get_db_service()
        updated_data = db_service.get_animation_by_uuid(uuid)

        if updated_data:
            for i, anim in enumerate(self._animations):
                if anim.get('uuid') == uuid:
                    self._animations[i] = updated_data
                    # Emit dataChanged for this row
                    index = self.index(i, 0)
                    self.dataChanged.emit(index, index)
                    return True
        return False

    def get_animation_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get animation data by UUID

        Args:
            uuid: Animation UUID

        Returns:
            Animation dict or None
        """
        for anim in self._animations:
            if anim.get('uuid') == uuid:
                return anim
        return None

    def get_animation_at_index(self, row: int) -> Optional[Dict[str, Any]]:
        """
        Get animation data at row index

        Args:
            row: Row index

        Returns:
            Animation dict or None
        """
        if 0 <= row < len(self._animations):
            return self._animations[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return number of animations"""
        if parent.isValid():
            return 0
        return len(self._animations)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get data for index and role

        Args:
            index: Model index
            role: Data role

        Returns:
            Data for role or None
        """
        if not index.isValid() or index.row() >= len(self._animations):
            return None

        animation = self._animations[index.row()]
        self._data_access_count += 1

        # Sparse data access - use .get() for optional fields
        if role == Qt.ItemDataRole.DisplayRole:
            return animation.get('name', 'Unknown')

        elif role == AnimationRole.UUIDRole:
            return animation.get('uuid')

        elif role == AnimationRole.NameRole:
            return animation.get('name', 'Unknown')

        elif role == AnimationRole.FolderIdRole:
            return animation.get('folder_id')

        elif role == AnimationRole.RigTypeRole:
            return animation.get('rig_type', 'Unknown')

        elif role == AnimationRole.ArmatureNameRole:
            return animation.get('armature_name')

        elif role == AnimationRole.BoneCountRole:
            return animation.get('bone_count')

        elif role == AnimationRole.FrameStartRole:
            return animation.get('frame_start')

        elif role == AnimationRole.FrameEndRole:
            return animation.get('frame_end')

        elif role == AnimationRole.FrameCountRole:
            return animation.get('frame_count')

        elif role == AnimationRole.DurationSecondsRole:
            return animation.get('duration_seconds')

        elif role == AnimationRole.FPSRole:
            return animation.get('fps')

        elif role == AnimationRole.BlendFilePathRole:
            return animation.get('blend_file_path')

        elif role == AnimationRole.JSONFilePathRole:
            return animation.get('json_file_path')

        elif role == AnimationRole.PreviewPathRole:
            # Resolve preview path (checks library and archive folders)
            stored_path = animation.get('preview_path')
            if stored_path and Path(stored_path).exists():
                return stored_path
            # Try to resolve actual path for archived versions
            db_service = self._get_db_service()
            resolved = db_service.animations.resolve_preview_file(animation)
            return str(resolved) if resolved else stored_path

        elif role == AnimationRole.ThumbnailPathRole:
            # Resolve thumbnail path (checks library and archive folders)
            stored_path = animation.get('thumbnail_path')
            if stored_path and Path(stored_path).exists():
                return stored_path
            # Try to resolve actual path for archived versions
            db_service = self._get_db_service()
            resolved = db_service.animations.resolve_thumbnail_file(animation)
            return str(resolved) if resolved else stored_path

        elif role == AnimationRole.FileSizeMBRole:
            return animation.get('file_size_mb')

        elif role == AnimationRole.DescriptionRole:
            return animation.get('description', '')

        elif role == AnimationRole.TagsRole:
            return animation.get('tags', [])

        elif role == AnimationRole.AuthorRole:
            return animation.get('author', '')

        elif role == AnimationRole.UseCustomGradientRole:
            return animation.get('use_custom_thumbnail_gradient', 0)

        elif role == AnimationRole.GradientTopRole:
            return animation.get('thumbnail_gradient_top')

        elif role == AnimationRole.GradientBottomRole:
            return animation.get('thumbnail_gradient_bottom')

        elif role == AnimationRole.CreatedDateRole:
            return animation.get('created_date')

        elif role == AnimationRole.ModifiedDateRole:
            return animation.get('modified_date')

        elif role == AnimationRole.IsFavoriteRole:
            return animation.get('is_favorite', 0)

        elif role == AnimationRole.LastViewedDateRole:
            return animation.get('last_viewed_date')

        elif role == AnimationRole.CustomOrderRole:
            return animation.get('custom_order')

        elif role == AnimationRole.IsLockedRole:
            return animation.get('is_locked', 0)

        # Versioning roles
        elif role == AnimationRole.VersionRole:
            return animation.get('version', 1)

        elif role == AnimationRole.VersionLabelRole:
            return animation.get('version_label', 'v001')

        elif role == AnimationRole.VersionGroupIdRole:
            return animation.get('version_group_id')

        elif role == AnimationRole.IsLatestRole:
            return animation.get('is_latest', 1)

        elif role == AnimationRole.StatusRole:
            return animation.get('status', 'none')

        elif role == AnimationRole.IsPoseRole:
            return animation.get('is_pose', 0)

        elif role == AnimationRole.IsPartialRole:
            return animation.get('is_partial', 0)

        elif role == AnimationRole.HasNotesRole:
            uuid = animation.get('uuid')
            return uuid in self._animations_with_notes if uuid else False

        elif role == AnimationRole.UnresolvedCommentCountRole:
            uuid = animation.get('uuid')
            return self._unresolved_counts.get(uuid, 0) if uuid else 0

        elif role == AnimationRole.AnimationDataRole:
            return animation

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """
        Return item flags for drag & drop support

        Args:
            index: Model index

        Returns:
            Item flags
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return (
            Qt.ItemFlag.ItemIsEnabled |
            Qt.ItemFlag.ItemIsSelectable |
            Qt.ItemFlag.ItemIsDragEnabled
        )

    def supportedDragActions(self) -> Qt.DropAction:
        """Return supported drag actions"""
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction

    def mimeTypes(self) -> List[str]:
        """Return supported MIME types for drag & drop"""
        return ['application/x-animation-uuid']

    def mimeData(self, indexes: List[QModelIndex]) -> QMimeData:
        """
        Create MIME data for drag operation

        Args:
            indexes: List of dragged indexes

        Returns:
            MIME data with animation UUIDs
        """
        mime_data = QMimeData()
        uuids = []

        for index in indexes:
            if index.isValid():
                uuid = self.data(index, AnimationRole.UUIDRole)
                if uuid:
                    uuids.append(uuid)

        # Encode as newline-separated UUIDs
        mime_data.setData('application/x-animation-uuid', QByteArray('\n'.join(uuids).encode()))
        return mime_data

    # ==================== PERFORMANCE MONITORING ====================

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics (Maya-inspired)

        Returns:
            Dict with performance metrics
        """
        return {
            'animation_count': len(self._animations),
            'load_time_ms': self._load_time,
            'data_access_count': self._data_access_count,
        }

    def reset_performance_stats(self):
        """Reset performance counters"""
        self._data_access_count = 0
        self._load_time = 0.0


__all__ = ['AnimationListModel', 'AnimationRole']
