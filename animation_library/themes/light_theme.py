"""
Light theme implementation

Professional light color palette
"""

from .theme_manager import Theme, ColorPalette


class LightTheme(Theme):
    """Light theme with clean, modern color palette"""

    def __init__(self):
        palette = ColorPalette(
            # Background colors
            background="#FFFFFF",  # White
            background_secondary="#F5F5F5",  # Light gray

            # Text colors
            text_primary="#212121",  # Near black
            text_secondary="#757575",  # Medium gray
            text_disabled="#BDBDBD",  # Light gray

            # Accent colors
            accent="#2196F3",  # Material blue
            accent_hover="#42A5F5",  # Lighter blue
            accent_pressed="#1976D2",  # Darker blue

            # Card colors
            card_background="#FFFFFF",
            card_border="#E0E0E0",
            card_selected="#2196F3",

            # Gradient colors (normalized RGB)
            gradient_top=(0.6, 0.7, 0.9),  # Light blue
            gradient_bottom=(0.85, 0.85, 0.85),  # Light gray

            # Button colors
            button_background="#F5F5F5",
            button_hover="#EEEEEE",
            button_pressed="#E0E0E0",
            button_disabled="#FAFAFA",

            # Status colors
            error="#F44336",  # Red
            warning="#FF9800",  # Orange
            success="#4CAF50",  # Green

            # Border/Divider colors
            border="#E0E0E0",
            divider="#EEEEEE",
        )

        super().__init__("light", palette)

    def get_stylesheet(self) -> str:
        """Generate QSS stylesheet for light theme"""

        p = self.palette

        return f"""
/* ===== GLOBAL STYLES ===== */
QWidget {{
    background-color: {p.background};
    color: {p.text_primary};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}}

/* ===== MAIN WINDOW ===== */
QMainWindow {{
    background-color: {p.background};
}}

/* ===== LABELS ===== */
QLabel {{
    color: {p.text_primary};
    background-color: transparent;
}}

QLabel[secondary="true"] {{
    color: {p.text_secondary};
}}

QLabel[disabled="true"] {{
    color: {p.text_disabled};
}}

/* ===== PUSH BUTTONS ===== */
QPushButton {{
    background-color: {p.button_background};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: {p.button_hover};
}}

QPushButton:pressed {{
    background-color: {p.button_pressed};
}}

QPushButton:disabled {{
    background-color: {p.button_disabled};
    color: {p.text_disabled};
}}

QPushButton[accent="true"] {{
    background-color: {p.accent};
    color: #FFFFFF;
    border: none;
}}

QPushButton[accent="true"]:hover {{
    background-color: {p.accent_hover};
}}

QPushButton[accent="true"]:pressed {{
    background-color: {p.accent_pressed};
}}

/* ===== LINE EDIT (TEXT INPUT) ===== */
QLineEdit {{
    background-color: {p.background};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {p.accent};
    selection-color: #FFFFFF;
}}

QLineEdit:focus {{
    border: 1px solid {p.accent};
}}

QLineEdit:disabled {{
    background-color: {p.button_disabled};
    color: {p.text_disabled};
}}

/* ===== LIST VIEW ===== */
QListView {{
    background-color: {p.background};
    border: 1px solid {p.border};
    outline: none;
}}

QListView::item {{
    background-color: transparent;
}}

QListView::item:selected {{
    background-color: rgba(33, 150, 243, 0.1);
    border: 2px solid {p.accent};
}}

QListView::item:hover {{
    background-color: rgba(33, 150, 243, 0.05);
}}

/* ===== TREE VIEW (FOLDER TREE) ===== */
QTreeView {{
    background-color: {p.background_secondary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    outline: none;
}}

QTreeView::item {{
    padding: 4px;
}}

QTreeView::item:selected {{
    background-color: {p.accent};
    color: #FFFFFF;
}}

QTreeView::item:hover {{
    background-color: {p.button_hover};
}}

/* ===== SCROLL BARS ===== */
QScrollBar:vertical {{
    background-color: {p.background_secondary};
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {p.button_background};
    min-height: 20px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {p.button_hover};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {p.background_secondary};
    height: 12px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {p.button_background};
    min-width: 20px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {p.button_hover};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ===== SLIDERS ===== */
QSlider::groove:horizontal {{
    background-color: {p.background_secondary};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background-color: {p.accent};
    width: 16px;
    height: 16px;
    border-radius: 8px;
    margin: -5px 0;
}}

QSlider::handle:horizontal:hover {{
    background-color: {p.accent_hover};
}}

/* ===== CARD SIZE SLIDER ===== */
QSlider[cardsize="true"]::groove:horizontal {{
    background: rgba(0, 0, 0, 0.1);
    height: 20px;
    border: none;
    border-radius: 0px;
}}

QSlider[cardsize="true"]::handle:horizontal {{
    background: {p.accent};
    width: 10px;
    height: 20px;
    margin: 0px;
    border: none;
    border-radius: 0px;
}}

QSlider[cardsize="true"]::handle:horizontal:hover {{
    background: {p.accent_hover};
}}

QSlider[cardsize="true"]::handle:horizontal:pressed {{
    background: {p.accent_pressed};
}}

QSlider[cardsize="true"]::sub-page:horizontal {{
    background: {p.accent};
    height: 20px;
    border: none;
    border-radius: 0px;
}}

QSlider[cardsize="true"]::add-page:horizontal {{
    background: rgba(0, 0, 0, 0.1);
    height: 20px;
    border: none;
    border-radius: 0px;
}}

/* ===== SPLITTER ===== */
QSplitter::handle {{
    background-color: {p.divider};
}}

QSplitter::handle:hover {{
    background-color: {p.border};
}}

/* ===== COMBO BOX ===== */
QComboBox {{
    background-color: {p.button_background};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 4px 8px;
}}

QComboBox:hover {{
    background-color: {p.button_hover};
}}

QComboBox::drop-down {{
    border: none;
}}

QComboBox QAbstractItemView {{
    background-color: {p.background};
    color: {p.text_primary};
    border: 1px solid {p.border};
    selection-background-color: {p.accent};
    selection-color: #FFFFFF;
}}

/* ===== CHECKBOXES ===== */
QCheckBox {{
    color: {p.text_primary};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {p.border};
    border-radius: 3px;
    background-color: {p.background};
}}

QCheckBox::indicator:checked {{
    background-color: {p.accent};
    border-color: {p.accent};
}}

QCheckBox::indicator:hover {{
    border-color: {p.accent_hover};
}}

/* ===== TOOLBARS ===== */
QToolBar {{
    background-color: {p.background_secondary};
    border: 1px solid {p.border};
    spacing: 4px;
    padding: 4px;
}}

QToolButton {{
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px;
}}

QToolButton:hover {{
    background-color: {p.button_hover};
}}

QToolButton:pressed {{
    background-color: {p.button_pressed};
}}

/* ===== TABS ===== */
QTabWidget::pane {{
    border: 1px solid {p.border};
    background-color: {p.background};
}}

QTabBar::tab {{
    background-color: {p.background_secondary};
    color: {p.text_secondary};
    padding: 8px 16px;
    border: 1px solid {p.border};
    border-bottom: none;
}}

QTabBar::tab:selected {{
    background-color: {p.background};
    color: {p.text_primary};
    border-bottom: 2px solid {p.accent};
}}

QTabBar::tab:hover {{
    background-color: {p.button_hover};
}}

/* ===== MENUS ===== */
QMenuBar {{
    background-color: {p.background_secondary};
    color: {p.text_primary};
    border-bottom: 1px solid {p.border};
}}

QMenuBar::item:selected {{
    background-color: {p.button_hover};
}}

QMenu {{
    background-color: {p.background};
    color: {p.text_primary};
    border: 1px solid {p.border};
}}

QMenu::item:selected {{
    background-color: {p.accent};
    color: #FFFFFF;
}}

/* ===== TOOLTIPS ===== */
QToolTip {{
    background-color: {p.background};
    color: {p.text_primary};
    border: 1px solid {p.border};
    padding: 4px;
}}
"""


__all__ = ['LightTheme']
