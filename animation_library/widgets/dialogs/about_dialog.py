"""
About Dialog for Action Library v1
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QSizePolicy,
    QFrame, QPushButton, QApplication, QMessageBox
)
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QUrl

from ...config import Config
from ...services.update_service import UpdateService


class AboutDialog(QDialog):
    """About dialog showing application information"""

    WIDTH = 500
    HEIGHT = 600

    def __init__(self, parent, theme_manager):
        super().__init__(parent)

        self.theme_manager = theme_manager

        self._configure_window()
        self._apply_theme_styles()
        self._center_over_parent()
        self._build_ui()

    def _configure_window(self):
        """Configure window properties"""
        self.setWindowTitle("About Action Library")
        self.setMinimumSize(self.WIDTH, self.HEIGHT)
        self.setMaximumSize(self.WIDTH, self.HEIGHT)
        self.setModal(True)

        # Fixed size & disable maximize
        # self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

    def _apply_theme_styles(self):
        """Apply theme styling"""
        if not self.theme_manager:
            return

        theme = self.theme_manager.get_current_theme()
        if not theme:
            return

        p = theme.palette

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p.dialog_background};
            }}
            QLabel {{
                color: {p.dialog_text};
            }}
            QLabel a {{
                color: {p.accent};
                text-decoration: none;
            }}
            QLabel a:hover {{
                text-decoration: underline;
            }}
            QPushButton {{
                background-color: {p.button_background};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 3px;
                padding: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {p.button_hover};
            }}
            QPushButton:pressed {{
                background-color: {p.button_pressed};
            }}
        """)

    def _center_over_parent(self):
        """Center dialog over parent window"""
        if self.parent():
            pg = self.parent().geometry()
            x = pg.x() + (pg.width() - self.WIDTH) // 2
            y = pg.y() + (pg.height() - self.HEIGHT) // 2

            # Clamp to screen bounds to ensure title bar is visible
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()

                # Ensure title bar is at least 30px below top of screen
                min_y = screen_geometry.y() + 30
                max_y = screen_geometry.y() + screen_geometry.height() - self.HEIGHT
                max_x = screen_geometry.x() + screen_geometry.width() - self.WIDTH

                x = max(screen_geometry.x(), min(x, max_x))
                y = max(min_y, min(y, max_y))

            self.move(x, y)

    def _build_ui(self):
        """Build the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Application icon
        icon_label = QLabel()
        icon_path = Path(__file__).parent.parent.parent.parent / "assets" / "Icon.png"

        if icon_path.exists():
            pixmap = QPixmap(str(icon_path)).scaled(
                80, 80,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Application name
        name_label = QLabel("Action Library")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(name_label)

        # Version number
        version_label = QLabel(f"Version {Config.APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(version_label)

        # Description
        desc = QLabel(
            "A professional animation management system for Blender.\n"
            "Organize, preview, and apply animations with ease."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 15px;")
        layout.addWidget(desc)

        # Creator & links
        info_frame = QFrame()
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(8)

        creator = QLabel("© 2026 CG_Stuff")
        creator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        creator.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(creator)

        license_lbl = QLabel("Licensed under GPL-3.0")
        license_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_lbl.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(license_lbl)

        website = QLabel(
            'Website: <a href="https://cgstuff.xyz">cgstuff.xyz</a>'
        )
        website.setOpenExternalLinks(True)
        website.setAlignment(Qt.AlignmentFlag.AlignCenter)
        website.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(website)

        yt = QLabel(
            'YouTube: <a href="https://www.youtube.com/@cgstuff87">'
            '@cgstuff87</a>'
        )
        yt.setOpenExternalLinks(True)
        yt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        yt.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(yt)

        gh = QLabel(
            'GitHub: <a href="https://github.com/CGstuff">'
            'CGstuff</a>'
        )
        gh.setOpenExternalLinks(True)
        gh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gh.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(gh)

        layout.addWidget(info_frame)
        layout.addStretch()

        # Update button
        self._update_btn = QPushButton("Check for Updates")
        self._update_btn.setFixedHeight(40)
        self._update_btn.clicked.connect(self._on_check_updates)
        layout.addWidget(self._update_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(40)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _on_check_updates(self):
        """Check for updates"""
        self._update_btn.setText("Checking...")
        self._update_btn.setEnabled(False)
        QApplication.processEvents() # Force UI update

        service = UpdateService()
        has_update, latest_version, url = service.check_for_updates()

        self._update_btn.setText("Check for Updates")
        self._update_btn.setEnabled(True)

        if has_update:
            reply = QMessageBox.question(
                self,
                "Update Available",
                f"A new version ({latest_version}) is available!\n\n"
                "Do you want to open the download page?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(url))
        else:
            QMessageBox.information(
                self,
                "Up to Date",
                f"You are running the latest version ({Config.APP_VERSION})."
            )

__all__ = ['AboutDialog']
