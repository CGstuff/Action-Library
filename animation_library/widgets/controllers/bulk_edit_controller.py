"""
BulkEditController - Handles bulk edit operations on animations

Extracts bulk edit logic from MainWindow for better separation of concerns.
"""

import json
from typing import List, Tuple, Callable, Optional
from PyQt6.QtWidgets import QWidget, QMessageBox, QInputDialog


class BulkEditController:
    """
    Manages bulk edit operations on animations.

    Handles:
    - Remove tags from selected animations
    - Move animations to folder
    - Apply gradient presets
    - Apply custom gradients
    """

    def __init__(
        self,
        parent: QWidget,
        animation_view,
        animation_model,
        db_service,
        event_bus,
        status_bar,
        reload_animations_callback: Callable[[], None]
    ):
        """
        Initialize bulk edit controller.

        Args:
            parent: Parent widget for dialogs
            animation_view: Animation view widget
            animation_model: Animation list model
            db_service: Database service
            event_bus: Event bus for signals
            status_bar: Status bar for messages
            reload_animations_callback: Callback to reload animations after changes
        """
        self._parent = parent
        self._animation_view = animation_view
        self._animation_model = animation_model
        self._db_service = db_service
        self._event_bus = event_bus
        self._status_bar = status_bar
        self._reload_animations = reload_animations_callback

    def _get_selected_uuids(self) -> List[str]:
        """Get selected animation UUIDs from view."""
        return self._animation_view.get_selected_uuids()

    def _check_selection(self) -> Optional[List[str]]:
        """Check if there's a selection and return UUIDs or show warning."""
        selected_uuids = self._get_selected_uuids()
        if not selected_uuids:
            QMessageBox.warning(
                self._parent, "No Selection", "Please select animations first"
            )
            return None
        return selected_uuids

    def remove_tags(self) -> None:
        """Remove a tag from selected animations."""
        selected_uuids = self._check_selection()
        if not selected_uuids:
            return

        # Collect all unique tags from selected animations
        all_tags = set()
        for uuid in selected_uuids:
            animation = self._animation_model.get_animation_by_uuid(uuid)
            if animation:
                all_tags.update(animation.get('tags', []))

        if not all_tags:
            QMessageBox.information(
                self._parent, "No Tags", "Selected animations have no tags"
            )
            return

        # Show tag selection dialog
        tag_list = sorted(list(all_tags))
        tag, ok = QInputDialog.getItem(
            self._parent,
            "Remove Tag",
            "Select tag to remove:",
            tag_list,
            0,
            False
        )

        if not ok or not tag:
            return

        # Confirm removal
        reply = QMessageBox.question(
            self._parent,
            "Confirm Removal",
            f"Remove tag '{tag}' from {len(selected_uuids)} animation(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Remove tag from each selected animation
        success_count = 0
        for uuid in selected_uuids:
            animation = self._animation_model.get_animation_by_uuid(uuid)
            if not animation:
                continue

            current_tags = animation.get('tags', [])
            if tag in current_tags:
                current_tags.remove(tag)

                if self._db_service.update_animation(uuid, {'tags': current_tags}):
                    success_count += 1

        # Reload animations
        if success_count > 0:
            self._reload_animations()
            self._status_bar.showMessage(
                f"Removed tag '{tag}' from {success_count} animation(s)"
            )
        else:
            QMessageBox.warning(self._parent, "Error", "Failed to remove tags")

    def move_to_folder(self) -> None:
        """Move selected animations to a folder."""
        selected_uuids = self._check_selection()
        if not selected_uuids:
            return

        # Get all folders
        folders = self._db_service.get_all_folders()
        user_folders = [f for f in folders if f.get('parent_id')]  # Exclude root

        if not user_folders:
            QMessageBox.information(
                self._parent, "No Folders", "Please create a folder first"
            )
            return

        # Build folder list for selection
        folder_names = [f['name'] for f in user_folders]
        folder_name, ok = QInputDialog.getItem(
            self._parent,
            "Move to Folder",
            "Select destination folder:",
            folder_names,
            0,
            False
        )

        if not ok or not folder_name:
            return

        # Find folder ID
        folder_id = None
        for f in user_folders:
            if f['name'] == folder_name:
                folder_id = f['id']
                break

        if not folder_id:
            return

        # Move animations
        success_count = 0
        for uuid in selected_uuids:
            if self._db_service.move_animation_to_folder(uuid, folder_id):
                success_count += 1

        # Reload animations
        if success_count > 0:
            self._reload_animations()
            self._status_bar.showMessage(
                f"Moved {success_count} animation(s) to '{folder_name}'"
            )
        else:
            QMessageBox.warning(self._parent, "Error", "Failed to move animations")

    def apply_gradient_preset(self, name: str, top_color: tuple, bottom_color: tuple) -> None:
        """
        Apply a gradient preset to selected animations.

        Args:
            name: Preset name for status message
            top_color: RGB tuple for top gradient color
            bottom_color: RGB tuple for bottom gradient color
        """
        self._apply_gradient(top_color, bottom_color, name)

    def apply_custom_gradient(self) -> None:
        """Open gradient picker dialog and apply custom gradient."""
        selected_uuids = self._get_selected_uuids()
        if not selected_uuids:
            return

        from ..dialogs.gradient_picker_dialog import GradientPickerDialog

        dialog = GradientPickerDialog(self._parent)
        if not dialog.exec():
            return

        top_color, bottom_color = dialog.get_gradient()
        self._apply_gradient(top_color, bottom_color, "Custom")

    def _apply_gradient(self, top_color: tuple, bottom_color: tuple, preset_name: str) -> None:
        """
        Apply gradient colors to all selected animations.

        Args:
            top_color: RGB tuple for top gradient color
            bottom_color: RGB tuple for bottom gradient color
            preset_name: Name for status message
        """
        selected_uuids = self._check_selection()
        if not selected_uuids:
            return

        success_count = 0
        for uuid in selected_uuids:
            updates = {
                'use_custom_thumbnail_gradient': 1,
                'thumbnail_gradient_top': json.dumps(list(top_color)),
                'thumbnail_gradient_bottom': json.dumps(list(bottom_color))
            }

            if self._db_service.update_animation(uuid, updates):
                success_count += 1

        if success_count > 0:
            # Reload animations
            self._reload_animations()

            # Clear thumbnail cache and refresh view
            from ...services.thumbnail_loader import get_thumbnail_loader
            thumbnail_loader = get_thumbnail_loader()
            thumbnail_loader.clear_cache()
            self._animation_view.viewport().update()

            self._status_bar.showMessage(
                f"Applied '{preset_name}' gradient to {success_count} animation(s)"
            )
        else:
            QMessageBox.warning(self._parent, "Error", "Failed to apply gradient")

    def execute_bulk_operation(
        self,
        operation_name: str,
        operation_callback: Callable[[str], bool],
        success_message: str,
        reload: bool = True
    ) -> Tuple[int, List[str]]:
        """
        Execute a bulk operation on selected animations.

        Args:
            operation_name: Name for error messages
            operation_callback: Function that takes UUID and returns success bool
            success_message: Message template with {count} placeholder
            reload: Whether to reload animations after operation

        Returns:
            Tuple of (success_count, error_messages)
        """
        selected_uuids = self._check_selection()
        if not selected_uuids:
            return (0, [])

        success_count = 0
        errors = []

        for uuid in selected_uuids:
            try:
                if operation_callback(uuid):
                    success_count += 1
            except Exception as e:
                errors.append(str(e))

        if success_count > 0:
            if reload:
                self._reload_animations()
            self._status_bar.showMessage(success_message.format(count=success_count))

        if errors:
            self._event_bus.report_error(
                operation_name, f"Some operations failed: {errors[0]}"
            )

        return (success_count, errors)


__all__ = ['BulkEditController']
