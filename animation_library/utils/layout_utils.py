"""
Layout Utilities - Common layout manipulation helpers

Provides reusable functions for clearing layouts and managing widgets.
Consolidates 15+ repeated layout clearing patterns.
"""

from PyQt6.QtWidgets import QLayout, QGridLayout, QLabel


def clear_layout(layout: QLayout) -> None:
    """
    Remove all widgets from a layout and delete them.

    Args:
        layout: The layout to clear
    """
    if layout is None:
        return

    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            # Recursively clear nested layouts
            clear_layout(item.layout())


def clear_grid(grid: QGridLayout) -> None:
    """
    Clear a grid layout and delete all widgets.

    Args:
        grid: The grid layout to clear
    """
    if grid is None:
        return

    while grid.count():
        item = grid.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def add_grid_row(
    grid: QGridLayout,
    row: int,
    label_text: str,
    value_text: str,
    label_style: str = None,
    value_style: str = None
) -> tuple:
    """
    Add a label-value row to a grid layout.

    Args:
        grid: The grid layout to add to
        row: Row index
        label_text: Text for the label column
        value_text: Text for the value column
        label_style: Optional stylesheet for label
        value_style: Optional stylesheet for value

    Returns:
        Tuple of (label_widget, value_widget)
    """
    label = QLabel(label_text)
    value = QLabel(value_text)

    if label_style:
        label.setStyleSheet(label_style)
    if value_style:
        value.setStyleSheet(value_style)

    grid.addWidget(label, row, 0)
    grid.addWidget(value, row, 1)

    return label, value


def set_layout_margins(layout: QLayout, margins: int) -> None:
    """
    Set uniform margins on a layout.

    Args:
        layout: The layout to modify
        margins: Margin size in pixels (applied to all sides)
    """
    layout.setContentsMargins(margins, margins, margins, margins)


def set_layout_spacing(layout: QLayout, spacing: int) -> None:
    """
    Set spacing between items in a layout.

    Args:
        layout: The layout to modify
        spacing: Spacing in pixels
    """
    layout.setSpacing(spacing)


__all__ = [
    'clear_layout',
    'clear_grid',
    'add_grid_row',
    'set_layout_margins',
    'set_layout_spacing'
]
