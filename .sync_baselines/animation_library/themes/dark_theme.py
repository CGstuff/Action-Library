"""
Dark theme implementation

Inspired by current animation_library dark mode
"""

from .theme_manager import Theme, ColorPalette
from .fonts import Fonts


class DarkTheme(Theme):
    """Dark theme with professional color palette"""

    def __init__(self):
        palette = ColorPalette(
            # Background colors
            background="#1E1E1E",  # Dark gray
            background_secondary="#2D2D2D",  # Slightly lighter

            # Text colors
            text_primary="#FFFFFF",  # White
            text_secondary="#B0B0B0",  # Light gray
            text_disabled="#606060",  # Dim gray

            # Accent colors
            accent="#3A8FB7",  # Blue
            accent_hover="#4A9FC7",  # Lighter blue
            accent_pressed="#2A7FA7",  # Darker blue

            # Card colors
            card_background="#2D2D2D",
            card_border="#404040",
            card_selected="#3A8FB7",

            # Gradient colors (normalized RGB)
            gradient_top=(0.25, 0.35, 0.55),  # Muted blue
            gradient_bottom=(0.5, 0.5, 0.5),  # Gray

            # Button colors
            button_background="#3A3A3A",
            button_hover="#4A4A4A",
            button_pressed="#2A2A2A",
            button_disabled="#252525",

            # Status colors
            error="#E74C3C",  # Red
            warning="#F39C12",  # Orange
            success="#27AE60",  # Green

            # Border/Divider colors
            border="#404040",
            divider="#353535",

            # Gold accent colors
            gold_primary="#D4AF37",
            gold_hover="#F0C040",
            gold_pressed="#C4A030",
            gold_disabled="#8A7828",

            # Media control colors
            media_background="#2B2B2B",
            media_border="#D4AF37",
            media_hover="#3A3A3A",

            # Dialog colors (light theme)
            dialog_background="#F5F5F5",
            dialog_text="#2B2B2B",
            dialog_border="#CCCCCC",

            # Header gradient (orange/gold from old repo)
            header_gradient_start="#E5C046",
            header_gradient_end="#D4AF37",
            header_icon_color="#1a1a1a",
        )

        super().__init__("dark", palette)

    def get_stylesheet(self) -> str:
        """Generate QSS stylesheet for dark theme"""

        p = self.palette

        return f"""
/* ===== GLOBAL STYLES ===== */
QWidget {{
    background-color: {p.background};
    color: {p.text_primary};
    font-family: "{Fonts.DEFAULT.family}", Arial, sans-serif;
    font-size: {Fonts.DEFAULT.size}pt;
}}

/* ===== MAIN WINDOW ===== */
QMainWindow {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p.background_secondary}, stop:1 {p.background});
}}

/* ===== HEADER TOOLBAR ===== */
/* Orange gradient header like old repo */
QWidget[header="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p.header_gradient_start},
        stop:1 {p.header_gradient_end});
    min-height: 50px;
    max-height: 50px;
}}

/* Header toolbar buttons (icon-only, transparent background) */
QWidget[header="true"] QPushButton {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 0px;
}}

QWidget[header="true"] QPushButton:hover {{
    background: rgba(0, 0, 0, 0.15);
}}

QWidget[header="true"] QPushButton:pressed {{
    background: rgba(0, 0, 0, 0.25);
}}

QWidget[header="true"] QPushButton:disabled {{
    opacity: 0.3;
}}

/* Search box on orange header (white background for contrast) */
QWidget[header="true"] QLineEdit {{
    background: rgba(255, 255, 255, 0.9);
    color: #1a1a1a;
    border: none;
    border-radius: 0px;
    padding: 6px 12px;
    font-size: 9pt;
}}

QWidget[header="true"] QLineEdit:focus {{
    background: rgba(255, 255, 255, 1.0);
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
    color: {p.text_primary};
    border: none;
}}

QPushButton[accent="true"]:hover {{
    background-color: {p.accent_hover};
}}

QPushButton[accent="true"]:pressed {{
    background-color: {p.accent_pressed};
}}

/* Media control buttons - minimal flat design */
QPushButton[media="true"] {{
    background-color: {p.media_background};
    border: 1px solid {p.border};
    border-radius: 0px;
    color: {p.text_primary};
}}

QPushButton[media="true"]:hover {{
    background-color: {p.media_hover};
    border-color: {p.border};
    color: {p.text_primary};
}}

QPushButton[media="true"]:pressed {{
    background-color: {p.button_pressed};
    border-color: {p.border};
    color: {p.text_primary};
}}

QPushButton[media="true"]:disabled {{
    background-color: {p.button_disabled};
    border-color: {p.border};
    color: {p.text_disabled};
}}

/* ===== PROGRESS SLIDER (MEDIA CONTROLS) ===== */
QSlider[progress="true"]::groove:horizontal {{
    background: rgba(255, 255, 255, 0.2);
    height: 32px;
    border: none;
}}

QSlider[progress="true"]::handle:horizontal {{
    background: transparent;
    width: 0px;
    height: 0px;
    margin: 0px;
    border: none;
}}

QSlider[progress="true"]::sub-page:horizontal {{
    background: white;
    height: 32px;
    border: none;
}}

QSlider[progress="true"]::add-page:horizontal {{
    background: rgba(255, 255, 255, 0.2);
    height: 32px;
    border: none;
}}

/* ===== CARD SIZE SLIDER ===== */
QSlider[cardsize="true"]::groove:horizontal {{
    background: rgba(255, 255, 255, 0.2);
    height: 20px;
    border: none;
    border-radius: 0px;
}}

QSlider[cardsize="true"]::handle:horizontal {{
    background: white;
    width: 10px;
    height: 20px;
    margin: 0px;
    border: none;
    border-radius: 0px;
}}

QSlider[cardsize="true"]::handle:horizontal:hover {{
    background: {p.accent};
}}

QSlider[cardsize="true"]::handle:horizontal:pressed {{
    background: {p.accent};
}}

QSlider[cardsize="true"]::sub-page:horizontal {{
    background: {p.accent};
    height: 20px;
    border: none;
    border-radius: 0px;
}}

QSlider[cardsize="true"]::add-page:horizontal {{
    background: rgba(255, 255, 255, 0.2);
    height: 20px;
    border: none;
    border-radius: 0px;
}}

/* Primary action buttons */
QPushButton[primary="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p.accent_hover}, stop:1 {p.accent});
    color: {p.text_primary};
    border: none;
    font-weight: bold;
}}

QPushButton[primary="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p.accent_hover}, stop:1 {p.accent_hover});
}}

QPushButton[primary="true"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p.accent_pressed}, stop:1 {p.accent});
}}

/* Danger/delete buttons */
QPushButton[danger="true"] {{
    background-color: {p.error};
    color: {p.text_primary};
    border: none;
}}

QPushButton[danger="true"]:hover {{
    background-color: {p.error};
    opacity: 0.9;
}}

QPushButton[danger="true"]:pressed {{
    background-color: {p.error};
    opacity: 0.7;
}}

/* ===== LINE EDIT (TEXT INPUT) ===== */
QLineEdit {{
    background-color: {p.background_secondary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 0px;
    padding: 4px 8px;
    selection-background-color: {p.accent};
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
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p.card_background}, stop:1 {p.background_secondary});
    border: 2px solid {p.selection_border};
    border-radius: 0px;
}}

QListView::item:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p.button_hover}, stop:1 {p.card_background});
    border: 1px solid {p.selection_border};
    border-radius: 0px;
}}

/* ===== TREE VIEW (FOLDER TREE) ===== */
QTreeView {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p.background_secondary}, stop:1 {p.background});
    color: {p.text_primary};
    border: 1px solid {p.border};
    outline: none;
    alternate-background-color: transparent;
}}

QTreeView::item {{
    padding: 4px;
    color: {p.text_primary};
    background-color: transparent;
}}

QTreeView::item:selected {{
    background-color: {p.accent};
    color: #FFFFFF;
}}

QTreeView::item:hover:!selected {{
    background-color: {p.button_hover};
    color: {p.text_primary};
}}

QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {{
    image: url(icons/branch-closed.png);
}}

QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings {{
    image: url(icons/branch-open.png);
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
    border-radius: 0px;
    padding: 4px 8px;
}}

QComboBox:hover {{
    background-color: {p.button_hover};
}}

QComboBox::drop-down {{
    border: none;
}}

QComboBox QAbstractItemView {{
    background-color: {p.list_item_background};
    color: {p.text_primary};
    border: 1px solid {p.border};
    selection-background-color: transparent;
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    padding: 4px 8px;
    background-color: {p.list_item_background};
    border: 1px solid transparent;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {p.list_item_hover};
    border: 1px solid {p.selection_border};
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {p.list_item_selected};
    border: 1px solid {p.selection_border};
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
    background-color: {p.background_secondary};
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
    background-color: {p.list_item_background};
    color: {p.text_secondary};
    padding: 8px 16px;
    border: 1px solid {p.border};
    border-bottom: none;
}}

QTabBar::tab:selected {{
    background-color: {p.list_item_selected};
    color: {p.text_primary};
    border-bottom: none;
}}

QTabBar::tab:hover:!selected {{
    background-color: {p.list_item_hover};
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
    background-color: {p.list_item_background};
    color: {p.text_primary};
    border: 1px solid {p.border};
}}

QMenu::item {{
    padding: 6px 20px;
    background-color: {p.list_item_background};
}}

QMenu::item:selected {{
    background-color: {p.list_item_selected};
    border: 1px solid {p.selection_border};
}}

/* ===== TOOLTIPS ===== */
QToolTip {{
    background-color: {p.background_secondary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    padding: 4px;
}}

/* ===== TABLE WIDGET ===== */
QTableWidget {{
    background-color: {p.background_secondary};
    alternate-background-color: {p.background_secondary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    gridline-color: {p.border};
    selection-background-color: {p.accent};
    selection-color: {p.text_primary};
}}

QTableWidget::item {{
    padding: 8px;
    background-color: transparent;
    color: {p.text_primary};
}}

QTableWidget::item:selected {{
    background-color: {p.accent};
    color: {p.text_primary};
}}

QTableWidget::item:selected:!active {{
    background-color: {p.accent};
    color: {p.text_primary};
}}

QTableWidget::item:hover:!selected {{
    background-color: {p.button_hover};
}}

QTableWidget::item:!selected {{
    background-color: transparent;
}}

/* ===== TABLE HEADER ===== */
QHeaderView::section {{
    background-color: {p.button_hover};
    color: {p.text_primary};
    padding: 8px;
    border: none;
    border-right: 1px solid {p.border};
    border-bottom: 1px solid {p.border};
    font-weight: bold;
}}

QHeaderView::section:hover {{
    background-color: {p.button_background};
}}
"""


__all__ = ['DarkTheme']
