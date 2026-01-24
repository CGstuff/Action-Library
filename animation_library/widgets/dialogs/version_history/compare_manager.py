"""
Compare manager for VersionHistoryDialog.

Handles the compare mode state machine for side-by-side version comparison.
"""

from typing import TYPE_CHECKING, Optional, List, Dict, Any, Callable

from PyQt6.QtWidgets import QAbstractItemView

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QTableWidget, QWidget


class CompareManager:
    """
    Manages compare mode for side-by-side version comparison.

    Handles:
    - Enter/exit compare mode state
    - Multi-selection handling
    - Version comparison display
    """

    TABLE_WIDTH_COMPARE = 180

    def __init__(
        self,
        table: 'QTableWidget',
        versions: List[Dict[str, Any]],
        get_notes_callback: Callable[[str, str], List[Dict]],
        show_comparison_callback: Callable[[Dict, Dict, List, List], None],
        hide_comparison_callback: Callable[[], None]
    ):
        """
        Initialize compare manager.

        Args:
            table: The version table widget
            versions: List of version dictionaries
            get_notes_callback: Callback to get notes for a version (uuid, label) -> notes
            show_comparison_callback: Callback to show comparison (ver_a, ver_b, notes_a, notes_b)
            hide_comparison_callback: Callback to hide comparison
        """
        self._table = table
        self._versions = versions
        self._get_notes = get_notes_callback
        self._show_comparison = show_comparison_callback
        self._hide_comparison = hide_comparison_callback

        self._compare_mode = False
        self._compare_selections: List[str] = []

    @property
    def is_active(self) -> bool:
        """Check if compare mode is active."""
        return self._compare_mode

    @property
    def selections(self) -> List[str]:
        """Get currently selected UUIDs in compare mode."""
        return self._compare_selections

    def update_versions(self, versions: List[Dict[str, Any]]):
        """Update the versions list reference."""
        self._versions = versions

    def enter(self):
        """Enter compare mode."""
        self._compare_mode = True
        self._compare_selections = []

        # Set table to multi-selection mode
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._table.clearSelection()

    def exit(self):
        """Exit compare mode."""
        self._compare_mode = False
        self._compare_selections = []

        # Set table back to single-selection mode
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.clearSelection()

        # Hide comparison widget
        self._hide_comparison()

    def on_selection_changed(self):
        """
        Handle selection changes in compare mode.

        Limits selection to 2 versions and triggers comparison when both selected.
        """
        if not self._compare_mode:
            return

        try:
            selected_items = self._table.selectedItems()
            selected_rows = []
            seen = set()

            for item in selected_items:
                row = item.row()
                if row not in seen:
                    seen.add(row)
                    uuid = self._table.item(row, 0).data(0x0100)  # Qt.ItemDataRole.UserRole
                    if uuid:
                        selected_rows.append((row, uuid))

            # Limit to 2 selections
            if len(selected_rows) > 2:
                self._table.blockSignals(True)
                self._table.clearSelection()
                for row, uuid in selected_rows[:2]:
                    for col in range(self._table.columnCount()):
                        item = self._table.item(row, col)
                        if item:
                            item.setSelected(True)
                self._table.blockSignals(False)
                self._compare_selections = [uuid for _, uuid in selected_rows[:2]]
            else:
                self._compare_selections = [uuid for _, uuid in selected_rows]

            # Trigger comparison if 2 versions selected
            if len(self._compare_selections) == 2:
                self._do_comparison()
            else:
                self._hide_comparison()

            return 2 - len(self._compare_selections)  # Return count needed

        except Exception:
            pass  # Silent fail for compare mode selection changes

        return 2

    def _do_comparison(self):
        """Execute the comparison between two selected versions."""
        if len(self._compare_selections) != 2:
            return

        version_a = next(
            (v for v in self._versions if v.get('uuid') == self._compare_selections[0]),
            None
        )
        version_b = next(
            (v for v in self._versions if v.get('uuid') == self._compare_selections[1]),
            None
        )

        if version_a and version_b:
            # Load notes for each version
            notes_a = []
            notes_b = []

            label_a = version_a.get('version_label', '')
            label_b = version_b.get('version_label', '')
            uuid_a = version_a.get('uuid', '')
            uuid_b = version_b.get('uuid', '')

            if uuid_a and label_a:
                notes_a = self._get_notes(uuid_a, label_a)
            if uuid_b and label_b:
                notes_b = self._get_notes(uuid_b, label_b)

            self._show_comparison(version_a, version_b, notes_a, notes_b)


__all__ = ['CompareManager']
