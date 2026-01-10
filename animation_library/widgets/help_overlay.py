"""
Help Overlay - Keyboard shortcuts legend

Shows a semi-transparent overlay with all keyboard shortcuts.
Toggle with 'H' key.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QFont, QKeyEvent

from ..themes.theme_manager import get_theme_manager


class HelpOverlay(QWidget):
    """
    Semi-transparent overlay showing keyboard shortcuts.

    Usage:
        overlay = HelpOverlay(parent)
        overlay.toggle()  # Show/hide
    """

    # Shortcut categories and their shortcuts
    SHORTCUTS = [
        ("Apply Actions", [
            ("Double-click", "Apply animation/pose"),
            ("Ctrl + Double-click", "Apply mirrored"),
            ("Shift + Double-click", "Apply as slot (actions only)"),
            ("Ctrl + Shift + Double-click", "Apply mirrored as slot"),
        ]),
        ("Pose Blending", [
            ("Right-click + Drag", "Blend pose (drag right to increase)"),
            ("Ctrl (while dragging)", "Mirror blend"),
            ("Left-click", "Cancel blend"),
            ("Escape", "Cancel blend"),
        ]),
        ("Navigation", [
            ("Scroll", "Browse library"),
            ("Click", "Select item"),
            ("Ctrl + Click", "Multi-select"),
            ("Shift + Click", "Range select"),
        ]),
        ("General", [
            ("H", "Toggle this help"),
            ("Escape", "Close dialogs / Cancel"),
        ]),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._theme_manager = get_theme_manager()
        self._visible = False

        # Style as overlay - no special window flags needed for child widget
        self.setAutoFillBackground(True)

        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        """Setup the overlay UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create container frame
        self._container = QFrame()
        self._container.setObjectName("helpContainer")
        layout.addWidget(self._container, alignment=Qt.AlignmentFlag.AlignCenter)

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(30, 25, 30, 25)
        container_layout.setSpacing(20)

        # Title
        title = QLabel("Keyboard Shortcuts")
        title.setObjectName("helpTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(title)

        # Shortcuts by category
        for category_name, shortcuts in self.SHORTCUTS:
            # Category header
            category_label = QLabel(category_name)
            category_label.setObjectName("helpCategory")
            container_layout.addWidget(category_label)

            # Shortcuts in this category
            for key, description in shortcuts:
                row = QWidget()
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(10, 2, 0, 2)
                row_layout.setSpacing(0)

                # Create horizontal layout for key + description
                shortcut_text = QLabel(f"<b>{key}</b>  —  {description}")
                shortcut_text.setObjectName("helpShortcut")
                row_layout.addWidget(shortcut_text)

                container_layout.addWidget(row)

        # Footer hint
        footer = QLabel("Press H to close")
        footer.setObjectName("helpFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(footer)

        self._apply_styles()

    def _apply_styles(self):
        """Apply theme-aware styles"""
        theme = self._theme_manager.get_current_theme()
        if not theme:
            return

        palette = theme.palette

        self.setStyleSheet(f"""
            HelpOverlay {{
                background-color: rgba(0, 0, 0, 180);
            }}

            #helpContainer {{
                background-color: {palette.background};
                border: 1px solid {palette.border};
                border-radius: 12px;
                min-width: 400px;
                max-width: 500px;
            }}

            #helpTitle {{
                color: {palette.text_primary};
                font-size: 18px;
                font-weight: bold;
                padding-bottom: 10px;
            }}

            #helpCategory {{
                color: {palette.accent};
                font-size: 13px;
                font-weight: bold;
                padding-top: 5px;
                border-bottom: 1px solid {palette.border};
                padding-bottom: 5px;
            }}

            #helpShortcut {{
                color: {palette.text_secondary};
                font-size: 11px;
            }}

            #helpShortcut b {{
                color: {palette.text_primary};
            }}

            #helpFooter {{
                color: {palette.text_secondary};
                font-size: 10px;
                padding-top: 15px;
                font-style: italic;
            }}
        """)

    def toggle(self):
        """Toggle visibility"""
        if self._visible:
            self.hide()
            self._visible = False
        else:
            self._resize_to_parent()
            self.show()
            self.raise_()
            self.setFocus()
            self._visible = True

    def _resize_to_parent(self):
        """Resize to match parent size"""
        if self.parent():
            parent = self.parent()
            self.setGeometry(0, 0, parent.width(), parent.height())

    def paintEvent(self, event):
        """Paint semi-transparent background"""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 180))
        super().paintEvent(event)

    def mousePressEvent(self, event):
        """Close on click outside container"""
        # Check if click is outside the container
        container_rect = self._container.geometry()
        if not container_rect.contains(event.pos()):
            self.toggle()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press to close"""
        if event.key() in (Qt.Key.Key_H, Qt.Key.Key_Escape):
            self.toggle()
            event.accept()
        else:
            super().keyPressEvent(event)


__all__ = ['HelpOverlay']
