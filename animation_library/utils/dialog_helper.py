"""
Dialog Helper - Centralized dialog utilities

Provides consistent QMessageBox dialogs across the application.
Consolidates 59+ scattered dialog calls into reusable methods.
"""

from PyQt6.QtWidgets import QWidget, QMessageBox, QInputDialog


class DialogHelper:
    """Centralized dialog creation utilities"""

    @staticmethod
    def confirm(
        parent: QWidget,
        title: str,
        message: str,
        yes_text: str = "Yes",
        no_text: str = "No"
    ) -> bool:
        """
        Show Yes/No confirmation dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            message: Dialog message
            yes_text: Text for Yes button (default: "Yes")
            no_text: Text for No button (default: "No")

        Returns:
            True if user clicked Yes, False otherwise
        """
        reply = QMessageBox.question(
            parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    @staticmethod
    def confirm_destructive(
        parent: QWidget,
        title: str,
        message: str
    ) -> bool:
        """
        Show warning-style confirmation for destructive actions.

        Args:
            parent: Parent widget
            title: Dialog title
            message: Warning message

        Returns:
            True if user confirmed, False otherwise
        """
        reply = QMessageBox.warning(
            parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    @staticmethod
    def warning(parent: QWidget, title: str, message: str) -> None:
        """
        Show warning dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            message: Warning message
        """
        QMessageBox.warning(parent, title, message)

    @staticmethod
    def info(parent: QWidget, title: str, message: str) -> None:
        """
        Show information dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            message: Info message
        """
        QMessageBox.information(parent, title, message)

    @staticmethod
    def error(parent: QWidget, title: str, message: str) -> None:
        """
        Show error dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            message: Error message
        """
        QMessageBox.critical(parent, title, message)

    @staticmethod
    def select_item(
        parent: QWidget,
        title: str,
        label: str,
        items: list,
        current: int = 0,
        editable: bool = False
    ) -> tuple:
        """
        Show item selection dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            label: Selection label
            items: List of items to choose from
            current: Index of initially selected item
            editable: Whether user can type custom value

        Returns:
            Tuple of (selected_item, ok_pressed)
        """
        return QInputDialog.getItem(
            parent,
            title,
            label,
            items,
            current,
            editable
        )

    @staticmethod
    def get_text(
        parent: QWidget,
        title: str,
        label: str,
        default: str = ""
    ) -> tuple:
        """
        Show text input dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            label: Input label
            default: Default text value

        Returns:
            Tuple of (entered_text, ok_pressed)
        """
        return QInputDialog.getText(
            parent,
            title,
            label,
            text=default
        )


__all__ = ['DialogHelper']
