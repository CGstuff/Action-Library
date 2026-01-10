"""
AnimationFilterProxyModel - Filtering and searching for animations

Pattern: Proxy pattern with QSortFilterProxyModel
Inspired by: Hybrid plan for instant filtering
"""

from typing import Optional, Set
from PyQt6.QtCore import QSortFilterProxyModel, QModelIndex, Qt

from .animation_list_model import AnimationRole


class AnimationFilterProxyModel(QSortFilterProxyModel):
    """
    Proxy model for filtering and searching animations

    Features:
    - Instant text search (name, description, tags)
    - Folder filtering
    - Tag filtering
    - Rig type filtering
    - Case-insensitive search
    - Performance: Uses Qt's built-in caching

    Usage:
        proxy = AnimationFilterProxyModel()
        proxy.setSourceModel(animation_list_model)
        proxy.set_search_text("walk")
        proxy.set_folder_filter(5)
        view.setModel(proxy)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Filter criteria
        self._search_text: str = ""
        self._folder_id: Optional[int] = None
        self._folder_ids: Set[int] = set()  # For recursive folder filtering
        self._folder_name: Optional[str] = None  # For tag-based folder filtering
        self._filter_tags: Set[str] = set()
        self._filter_rig_types: Set[str] = set()
        self._favorites_only: bool = False
        self._recent_only: bool = False
        self._poses_only: bool = False
        self._animations_only: bool = False

        # Sort configuration
        self._sort_by: str = "name"  # name, date, duration, fps
        self._sort_order: str = "ASC"  # ASC or DESC

        # Configure sorting/filtering
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setDynamicSortFilter(True)  # Auto-refilter on data changes

    def set_search_text(self, text: str):
        """
        Set search text filter

        Args:
            text: Search query (searches name, description, tags)
        """
        if self._search_text != text:
            self._search_text = text.strip().lower()
            self.invalidateFilter()

    def set_folder_filter(self, folder_id: Optional[int], folder_ids: Optional[Set[int]] = None, folder_name: Optional[str] = None):
        """
        Set folder filter

        Args:
            folder_id: Single folder ID to filter by, or None for all folders
            folder_ids: Set of folder IDs for recursive filtering (optional)
            folder_name: Folder name to filter by tags (optional)
        """
        changed = False

        if self._folder_id != folder_id:
            self._folder_id = folder_id
            changed = True

        new_folder_ids = folder_ids if folder_ids is not None else set()
        if self._folder_ids != new_folder_ids:
            self._folder_ids = new_folder_ids
            changed = True

        # NEW: Store folder name for tag-based filtering
        if self._folder_name != folder_name:
            self._folder_name = folder_name
            changed = True

        if changed:
            self.invalidateFilter()

    def set_tag_filter(self, tags: Set[str]):
        """
        Set tag filter (animations must have ALL specified tags)

        Args:
            tags: Set of tag strings
        """
        if self._filter_tags != tags:
            self._filter_tags = tags
            self.invalidateFilter()

    def add_tag_filter(self, tag: str):
        """Add single tag to filter"""
        self._filter_tags.add(tag)
        self.invalidateFilter()

    def remove_tag_filter(self, tag: str):
        """Remove single tag from filter"""
        self._filter_tags.discard(tag)
        self.invalidateFilter()

    def clear_tag_filter(self):
        """Clear all tag filters"""
        if self._filter_tags:
            self._filter_tags.clear()
            self.invalidateFilter()

    def set_rig_type_filter(self, rig_types: Set[str]):
        """
        Set rig type filter

        Args:
            rig_types: Set of rig type strings (e.g., {"humanoid", "quadruped"})
        """
        if self._filter_rig_types != rig_types:
            self._filter_rig_types = rig_types
            self.invalidateFilter()

    def add_rig_type_filter(self, rig_type: str):
        """Add single rig type to filter"""
        self._filter_rig_types.add(rig_type)
        self.invalidateFilter()

    def remove_rig_type_filter(self, rig_type: str):
        """Remove single rig type from filter"""
        self._filter_rig_types.discard(rig_type)
        self.invalidateFilter()

    def clear_rig_type_filter(self):
        """Clear all rig type filters"""
        if self._filter_rig_types:
            self._filter_rig_types.clear()
            self.invalidateFilter()

    def set_favorites_only(self, favorites_only: bool):
        """
        Set favorites only filter

        Args:
            favorites_only: True to show only favorited animations
        """
        if self._favorites_only != favorites_only:
            self._favorites_only = favorites_only
            self.invalidateFilter()

    def set_recent_only(self, recent_only: bool):
        """
        Set recent only filter

        Args:
            recent_only: True to show only recently viewed animations
        """
        if self._recent_only != recent_only:
            self._recent_only = recent_only
            self.invalidateFilter()

    def set_poses_only(self, poses_only: bool):
        """
        Set poses only filter

        Args:
            poses_only: True to show only poses (single-frame snapshots)
        """
        if self._poses_only != poses_only:
            self._poses_only = poses_only
            self.invalidateFilter()

    def set_animations_only(self, animations_only: bool):
        """
        Set animations only filter (excludes poses)

        Args:
            animations_only: True to show only animations (multi-frame actions)
        """
        if self._animations_only != animations_only:
            self._animations_only = animations_only
            self.invalidateFilter()

    def set_sort_config(self, sort_by: str, sort_order: str):
        """
        Set sort configuration

        Args:
            sort_by: Field to sort by (name, date, duration, fps)
            sort_order: Sort order (ASC or DESC)
        """
        if self._sort_by != sort_by or self._sort_order != sort_order:
            self._sort_by = sort_by
            self._sort_order = sort_order
            self.invalidate()  # Clear cache and re-sort
            self.sort(0)  # Trigger re-sort (column 0)

    def clear_all_filters(self):
        """Clear all filters"""
        changed = False

        if self._search_text:
            self._search_text = ""
            changed = True

        if self._folder_id is not None:
            self._folder_id = None
            changed = True

        if self._folder_ids:
            self._folder_ids.clear()
            changed = True

        if self._folder_name is not None:
            self._folder_name = None
            changed = True

        if self._filter_tags:
            self._filter_tags.clear()
            changed = True

        if self._filter_rig_types:
            self._filter_rig_types.clear()
            changed = True

        if self._favorites_only:
            self._favorites_only = False
            changed = True

        if self._recent_only:
            self._recent_only = False
            changed = True

        if self._poses_only:
            self._poses_only = False
            changed = True

        if self._animations_only:
            self._animations_only = False
            changed = True

        if changed:
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """
        Determine if row should be shown

        Args:
            source_row: Row in source model
            source_parent: Parent index

        Returns:
            True if row matches filters, False otherwise
        """
        source_model = self.sourceModel()
        if not source_model:
            return True

        index = source_model.index(source_row, 0, source_parent)

        # Favorites only filter
        if self._favorites_only:
            is_favorite = source_model.data(index, AnimationRole.IsFavoriteRole)
            if not is_favorite:
                return False

        # Recent only filter
        if self._recent_only:
            last_viewed = source_model.data(index, AnimationRole.LastViewedDateRole)
            if not last_viewed:
                return False

        # Poses only filter
        if self._poses_only:
            is_pose = source_model.data(index, AnimationRole.IsPoseRole)
            if not is_pose:
                return False

        # Animations only filter (excludes poses)
        if self._animations_only:
            is_pose = source_model.data(index, AnimationRole.IsPoseRole)
            if is_pose:
                return False

        # Folder filter - check tags instead of folder_id
        if self._folder_name and self._folder_name not in ["Home", "Actions", "Poses", "Favorites", "Recent"]:
            # Get animation tags
            animation_tags = source_model.data(index, AnimationRole.TagsRole)

            # Check if folder name is in animation's tags
            if not animation_tags or self._folder_name not in animation_tags:
                return False

        # Legacy folder_id filtering for recursive mode (if still needed)
        elif self._folder_ids:
            # Recursive folder filtering (check if in any of the folder IDs)
            folder_id = source_model.data(index, AnimationRole.FolderIdRole)
            if folder_id not in self._folder_ids:
                return False

        # Tag filter (animation must have ALL specified tags)
        if self._filter_tags:
            animation_tags = source_model.data(index, AnimationRole.TagsRole)
            if not animation_tags:
                return False
            animation_tag_set = set(animation_tags)
            if not self._filter_tags.issubset(animation_tag_set):
                return False

        # Rig type filter
        if self._filter_rig_types:
            rig_type = source_model.data(index, AnimationRole.RigTypeRole)
            if rig_type not in self._filter_rig_types:
                return False

        # Search text filter
        if self._search_text:
            # Search in name
            name = source_model.data(index, AnimationRole.NameRole)
            if name and self._search_text in name.lower():
                return True

            # Search in description
            description = source_model.data(index, AnimationRole.DescriptionRole)
            if description and self._search_text in description.lower():
                return True

            # Search in tags
            tags = source_model.data(index, AnimationRole.TagsRole)
            if tags:
                for tag in tags:
                    if self._search_text in tag.lower():
                        return True

            # Search in rig type
            rig_type = source_model.data(index, AnimationRole.RigTypeRole)
            if rig_type and self._search_text in rig_type.lower():
                return True

            # Not found in any searchable field
            return False

        # No filters active or all filters passed
        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """
        Compare items for sorting based on current sort configuration

        Args:
            left: Left index
            right: Right index

        Returns:
            True if left < right
        """
        source_model = self.sourceModel()
        if not source_model:
            return False

        # Map sort_by to AnimationRole
        role_map = {
            "name": AnimationRole.NameRole,
            "created_date": AnimationRole.CreatedDateRole,
            "duration_seconds": AnimationRole.DurationSecondsRole,
            "last_viewed_date": AnimationRole.LastViewedDateRole,
        }

        role = role_map.get(self._sort_by, AnimationRole.NameRole)

        left_value = source_model.data(left, role)
        right_value = source_model.data(right, role)

        # Handle None values (put them at the end)
        if left_value is None and right_value is None:
            return False
        if left_value is None:
            return self._sort_order == "DESC"
        if right_value is None:
            return self._sort_order == "ASC"

        # Compare based on type
        if self._sort_by == "name":
            # Case-insensitive string comparison
            result = str(left_value).lower() < str(right_value).lower()
        else:
            # Numeric or date comparison
            result = left_value < right_value

        # Reverse for DESC order
        if self._sort_order == "DESC":
            return not result

        return result

    # ==================== GETTERS FOR CURRENT FILTERS ====================

    def get_search_text(self) -> str:
        """Get current search text"""
        return self._search_text

    def get_folder_filter(self) -> Optional[int]:
        """Get current folder filter"""
        return self._folder_id

    def get_tag_filter(self) -> Set[str]:
        """Get current tag filter"""
        return self._filter_tags.copy()

    def get_rig_type_filter(self) -> Set[str]:
        """Get current rig type filter"""
        return self._filter_rig_types.copy()

    def has_active_filters(self) -> bool:
        """Check if any filters are active"""
        return bool(
            self._search_text or
            self._folder_id is not None or
            self._filter_tags or
            self._filter_rig_types
        )


__all__ = ['AnimationFilterProxyModel']
