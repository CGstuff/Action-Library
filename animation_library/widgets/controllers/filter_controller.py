"""
FilterController - Manages filtering and sorting of animations

Encapsulates proxy model interactions for cleaner MainWindow code.
"""

from typing import Optional, Set


class FilterController:
    """
    Manages filtering and sorting of animations.

    Encapsulates all proxy model interactions:
    - Search text filtering
    - Folder filtering
    - Favorites/recent filtering
    - Rig type and tag filtering
    - Sort configuration
    """

    def __init__(self, proxy_model, status_bar):
        """
        Initialize filter controller.

        Args:
            proxy_model: Animation filter proxy model
            status_bar: Status bar for messages
        """
        self._proxy = proxy_model
        self._status_bar = status_bar
        self._current_context: Optional[str] = None

    @property
    def row_count(self) -> int:
        """Get current filtered row count."""
        return self._proxy.rowCount()

    def set_search_text(self, text: str) -> None:
        """
        Set search text filter.

        Args:
            text: Search query string
        """
        self._proxy.set_search_text(text)
        self._update_status(search_text=text)

    def set_folder_filter(
        self,
        folder_id: Optional[int],
        folder_name: Optional[str],
        recursive_ids: Optional[Set[int]] = None
    ) -> None:
        """
        Set folder filter.

        Args:
            folder_id: Folder ID to filter by (None for all)
            folder_name: Folder name for tag-based filtering
            recursive_ids: Set of folder IDs for recursive filtering
        """
        self._proxy.set_folder_filter(folder_id, recursive_ids, folder_name)
        self._current_context = folder_name
        self._update_status()

    def set_favorites_only(self, enabled: bool) -> None:
        """
        Enable/disable favorites-only filter.

        Args:
            enabled: True to show only favorites
        """
        self._proxy.set_favorites_only(enabled)
        if enabled:
            self._current_context = "Favorites"
        self._update_status()

    def set_recent_only(self, enabled: bool) -> None:
        """
        Enable/disable recent-only filter.

        Args:
            enabled: True to show only recent animations
        """
        self._proxy.set_recent_only(enabled)
        if enabled:
            self._current_context = "Recent"
        self._update_status()

    def set_poses_only(self, enabled: bool) -> None:
        """
        Enable/disable poses-only filter.

        Args:
            enabled: True to show only poses
        """
        self._proxy.set_poses_only(enabled)
        if enabled:
            self._current_context = "Poses"
        self._update_status()

    def set_animations_only(self, enabled: bool) -> None:
        """
        Enable/disable animations-only filter (excludes poses).

        Args:
            enabled: True to show only actions
        """
        self._proxy.set_animations_only(enabled)
        if enabled:
            self._current_context = "Actions"
        self._update_status()

    def set_rig_type_filter(self, rig_types: Set[str]) -> None:
        """
        Set rig type filter.

        Args:
            rig_types: Set of rig types to include (empty for all)
        """
        self._proxy.set_rig_type_filter(rig_types)
        self._update_status()

    def set_tag_filter(self, tags: Set[str]) -> None:
        """
        Set tag filter.

        Args:
            tags: Set of tags to include (empty for all)
        """
        self._proxy.set_tag_filter(tags)
        self._update_status()

    def set_sort_config(self, sort_by: str, sort_order: str) -> None:
        """
        Set sort configuration.

        Args:
            sort_by: Field to sort by (e.g., 'name', 'date', 'duration')
            sort_order: Sort order ('ASC' or 'DESC')
        """
        self._proxy.set_sort_config(sort_by, sort_order)

    def clear_special_filters(self) -> None:
        """Clear favorites, recent, poses, and animations filters."""
        self._proxy.set_favorites_only(False)
        self._proxy.set_recent_only(False)
        self._proxy.set_poses_only(False)
        self._proxy.set_animations_only(False)

    def clear_folder_filter(self) -> None:
        """Clear folder filter to show all animations."""
        self._proxy.set_folder_filter(None, None, None)
        self._current_context = "Home"
        self._update_status()

    def clear_all_filters(self) -> None:
        """Clear all active filters."""
        self._proxy.set_search_text("")
        self._proxy.set_folder_filter(None, None, None)
        self._proxy.set_favorites_only(False)
        self._proxy.set_recent_only(False)
        self._proxy.set_rig_type_filter(set())
        self._proxy.set_tag_filter(set())
        self._current_context = None
        self._update_status()

    def _update_status(self, search_text: str = None) -> None:
        """
        Update status bar with current filter state.

        Args:
            search_text: Optional search text for status message
        """
        count = self._proxy.rowCount()

        if search_text:
            self._status_bar.showMessage(f"{count} animations match '{search_text}'")
        elif self._current_context:
            self._status_bar.showMessage(f"{count} animations in {self._current_context}")
        else:
            self._status_bar.showMessage(f"{count} animations")

    def update_status(self, context: str = None) -> None:
        """
        Update status bar with custom context.

        Args:
            context: Optional context string (e.g., folder name)
        """
        if context:
            self._current_context = context
        self._update_status()


__all__ = ['FilterController']
