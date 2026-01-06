"""
Console/Log Viewer Dialog for Animation Library v2
"""
import logging
import os
import subprocess
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QComboBox, QLabel, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ...utils.logging_config import LoggingConfig
from ...config import Config


class LogConsoleDialog(QDialog):
    """Console dialog for viewing application logs"""

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.log_handler = None

        self.setWindowTitle("Console & Logs")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        self.setup_ui()
        self.apply_theme()
        self.connect_to_logging()

    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Log level filter
        level_label = QLabel("Log Level:")
        toolbar.addWidget(level_label)

        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.setCurrentText("INFO")
        self.level_combo.setFixedWidth(120)
        self.level_combo.currentTextChanged.connect(self.on_level_changed)
        toolbar.addWidget(self.level_combo)

        toolbar.addSpacing(20)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(80)
        clear_btn.clicked.connect(self.clear_logs)
        toolbar.addWidget(clear_btn)

        # Save button
        save_btn = QPushButton("Save to File")
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self.save_logs)
        toolbar.addWidget(save_btn)

        # Open log folder button
        open_folder_btn = QPushButton("Open Log Folder")
        open_folder_btn.setFixedWidth(120)
        open_folder_btn.clicked.connect(self.open_log_folder)
        toolbar.addWidget(open_folder_btn)

        toolbar.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.close)
        toolbar.addWidget(close_btn)

        layout.addLayout(toolbar)

        # Log viewer
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumBlockCount(1000)  # Limit to 1000 lines
        self.log_viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Monospace font
        font = QFont("Consolas, Monaco, Courier New", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_viewer.setFont(font)

        layout.addWidget(self.log_viewer)

        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Logs displayed: Real-time")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

    def apply_theme(self):
        """Apply theme colors to the dialog"""
        if not self.theme_manager:
            return

        theme = self.theme_manager.get_current_theme()
        if not theme:
            return

        p = theme.palette

        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p.dialog_background};
            }}
            QLabel {{
                color: {p.dialog_text};
            }}
            QPushButton {{
                background-color: #555555;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: #666666;
            }}
            QComboBox {{
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: #3a3a3a;
                color: #ffffff;
                selection-background-color: {p.accent};
                selection-color: #ffffff;
                border: 1px solid #555555;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 5px;
                color: #ffffff;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #4a4a4a;
            }}
        """)

        # Log viewer styling (dark console theme)
        self.log_viewer.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: #1a1a1a;
                color: #00ff00;
                border: 1px solid {p.border};
                border-radius: 3px;
                padding: 5px;
            }}
        """)

    def connect_to_logging(self):
        """Connect this dialog to the logging system"""
        # Add this widget as a logging handler
        self.log_handler = LoggingConfig.add_widget_handler(
            self.log_viewer,
            log_level="DEBUG"  # Capture all logs, we'll filter in UI
        )

        # Log that console was opened
        logger = LoggingConfig.get_logger(__name__)
        logger.info("Log console opened")

    def on_level_changed(self, level: str):
        """Handle log level filter change"""
        if not self.log_handler:
            return

        if level == "ALL":
            self.log_handler.setLevel(logging.DEBUG)
        else:
            numeric_level = getattr(logging, level, logging.INFO)
            self.log_handler.setLevel(numeric_level)

        self.status_label.setText(f"Filtering: {level}")

    def clear_logs(self):
        """Clear the log viewer"""
        self.log_viewer.clear()
        logger = LoggingConfig.get_logger(__name__)
        logger.info("Log console cleared")

    def save_logs(self):
        """Save current logs to a file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logs",
            str(Path.home() / "animation_library_logs.txt"),
            "Text Files (*.txt);;Log Files (*.log);;All Files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_viewer.toPlainText())

                logger = LoggingConfig.get_logger(__name__)
                logger.info(f"Logs saved to: {file_path}")
                self.status_label.setText(f"Saved to: {Path(file_path).name}")
            except Exception as e:
                logger = LoggingConfig.get_logger(__name__)
                logger.error(f"Failed to save logs: {e}")

    def open_log_folder(self):
        """Open the logs folder in file explorer"""
        try:
            log_dir = Config.get_user_data_dir() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            logger = LoggingConfig.get_logger(__name__)

            # Open folder using platform-specific method
            if sys.platform == "win32":
                os.startfile(str(log_dir))
                logger.info(f"Opened log folder: {log_dir}")
            elif sys.platform == "darwin":
                subprocess.run(["open", str(log_dir)], check=True)
                logger.info(f"Opened log folder: {log_dir}")
            else:  # Linux
                subprocess.run(["xdg-open", str(log_dir)], check=True)
                logger.info(f"Opened log folder: {log_dir}")

        except Exception as e:
            logger = LoggingConfig.get_logger(__name__)
            logger.error(f"Failed to open log folder: {e}")

    def closeEvent(self, event):
        """Handle dialog close"""
        # Remove widget handler when closing
        LoggingConfig.remove_widget_handler()

        logger = LoggingConfig.get_logger(__name__)
        logger.info("Log console closed")
        event.accept()


__all__ = ['LogConsoleDialog']
