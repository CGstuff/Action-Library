"""
Setup Wizard for first-time Action Library configuration
"""
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QStackedWidget, QWidget,
    QGroupBox, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap

from ...config import Config


class SetupWizardPage(QWidget):
    """Base class for wizard pages"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)


class WelcomePage(SetupWizardPage):
    """Welcome page with app introduction"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Icon
        icon_label = QLabel()

        # Get icon path - handle both dev and compiled modes
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            icon_path = Path(sys._MEIPASS) / "assets" / "Icon.png"
        else:
            # Running from source
            icon_path = Config.APP_ROOT.parent / "assets" / "Icon.png"

        # Load and display icon
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    100, 100,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label.setPixmap(scaled_pixmap)

        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(icon_label)

        self.layout.addSpacing(10)

        # Title
        title = QLabel("Welcome to Action Library!")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white;")
        self.layout.addWidget(title)

        self.layout.addSpacing(20)

        # Description
        description = QLabel(
            "Action Library is a powerful tool for capturing, organizing, "
            "and applying animations across different Blender rigs.\n\n"
            "This wizard will help you set up your animation storage location."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("color: white;")
        self.layout.addWidget(description)

        self.layout.addStretch()

        # Info box
        info_box = QGroupBox("What you'll need:")
        info_box.setStyleSheet(
            "QGroupBox { color: white; } QGroupBox::title { color: white; }"
        )
        info_layout = QVBoxLayout()

        requirements = [
            "A folder to store your animation library",
            "About 1 GB of disk space per 100 animations",
            "Blender 4.4 or later"
        ]

        for req in requirements:
            label = QLabel(f"• {req}")
            label.setStyleSheet("color: white;")
            info_layout.addWidget(label)

        info_box.setLayout(info_layout)
        self.layout.addWidget(info_box)

        self.layout.addStretch()


class LibraryPathPage(SetupWizardPage):
    """Page for choosing library path"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Title
        title = QLabel("Choose Action Library Location")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")
        self.layout.addWidget(title)

        self.layout.addSpacing(20)

        # Description
        description = QLabel(
            "Select a folder where your animation library will be stored.\n"
            "This folder will contain all your saved animations, metadata, and previews."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: white;")
        self.layout.addWidget(description)

        self.layout.addSpacing(20)

        # Path input and browse button
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select a folder...")
        self.path_input.setReadOnly(True)

        # Set default path to storage folder next to app
        default_path = self._get_default_storage_path()
        self.path_input.setText(str(default_path))

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_folder)

        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_button)
        self.layout.addLayout(path_layout)

        self.layout.addSpacing(20)

        # Info box
        info_box = QGroupBox("Tips:")
        info_box.setStyleSheet(
            "QGroupBox { color: white; } QGroupBox::title { color: white; }"
        )
        info_layout = QVBoxLayout()

        tips = [
            "Choose a location with plenty of free space",
            "Avoid system or program folders",
            "You can change this location later in Settings"
        ]

        for tip in tips:
            label = QLabel(f"• {tip}")
            label.setStyleSheet("color: white;")
            info_layout.addWidget(label)

        info_box.setLayout(info_layout)
        self.layout.addWidget(info_box)

        self.layout.addStretch()

    def _get_default_storage_path(self) -> Path:
        """Get default storage path (storage folder next to exe for portable mode)"""
        if getattr(sys, 'frozen', False):
            # Running as compiled exe - storage next to exe
            return Path(sys.executable).parent / "storage"
        else:
            # Running from source - storage in project root
            return Config.APP_ROOT.parent / "storage"

    def browse_folder(self):
        """Open folder browser dialog"""
        current_path = self.path_input.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Action Library Folder",
            current_path,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if folder:
            self.path_input.setText(folder)

    def get_library_path(self) -> str:
        """Get the selected library path"""
        return self.path_input.text()


class FinishPage(SetupWizardPage):
    """Final page showing setup summary"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Title
        title = QLabel("Setup Complete!")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white;")
        self.layout.addWidget(title)

        self.layout.addSpacing(20)

        # Summary label (will be updated when showing this page)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setStyleSheet("color: white;")
        self.layout.addWidget(self.summary_label)

        self.layout.addStretch()

        # Next steps
        next_steps = QGroupBox("Next Steps:")
        next_steps.setStyleSheet(
            "QGroupBox { color: white; } QGroupBox::title { color: white; }"
        )
        next_layout = QVBoxLayout()

        steps = [
            "1. Install the Blender addon (Settings > Blender Integration)",
            "2. Configure the addon library path in Blender",
            "3. Start capturing animations!"
        ]

        for step in steps:
            label = QLabel(step)
            label.setStyleSheet("color: white;")
            next_layout.addWidget(label)

        next_steps.setLayout(next_layout)
        self.layout.addWidget(next_steps)

        self.layout.addStretch()

    def set_summary(self, library_path: Path):
        """Set the summary text"""
        summary = (
            f"Action Library is now configured!\n\n"
            f"Your animations will be stored in:\n{library_path}"
        )
        self.summary_label.setText(summary)


class SetupWizard(QDialog):
    """
    First-run setup wizard for Action Library.
    Guides users through choosing library location.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Library Setup")
        self.setModal(True)
        self.resize(600, 500)

        # Set dark background to match white text labels
        self.setStyleSheet("QDialog { background-color: #2b2b2b; }")

        # Store pages
        self.welcome_page = WelcomePage(self)
        self.library_page = LibraryPathPage(self)
        self.finish_page = FinishPage(self)

        # Create layout
        main_layout = QVBoxLayout(self)

        # Stacked widget for pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome_page)   # Index 0
        self.stack.addWidget(self.library_page)   # Index 1
        self.stack.addWidget(self.finish_page)    # Index 2
        main_layout.addWidget(self.stack)

        # Button layout
        button_layout = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.next_button = QPushButton("Next")
        self.finish_button = QPushButton("Finish")

        self.back_button.clicked.connect(self.go_back)
        self.next_button.clicked.connect(self.go_next)
        self.finish_button.clicked.connect(self.finish_setup)

        button_layout.addStretch()
        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.next_button)
        button_layout.addWidget(self.finish_button)
        main_layout.addLayout(button_layout)

        # Initial state
        self.update_buttons()

    def update_buttons(self):
        """Update button visibility based on current page"""
        current_index = self.stack.currentIndex()
        page_count = self.stack.count()

        # Back button
        self.back_button.setVisible(current_index > 0)

        # Next button
        self.next_button.setVisible(current_index < page_count - 1)

        # Finish button
        self.finish_button.setVisible(current_index == page_count - 1)

    def go_back(self):
        """Go to previous page"""
        current_index = self.stack.currentIndex()
        if current_index > 0:
            self.stack.setCurrentIndex(current_index - 1)
            self.update_buttons()

    def go_next(self):
        """Go to next page"""
        current_index = self.stack.currentIndex()

        # Special logic based on current page
        if current_index == 1:  # Library path page
            # Validate path
            library_path = self.library_page.get_library_path()
            if not library_path:
                QMessageBox.warning(self, "Invalid Path", "Please select a valid folder.")
                return
            # Go to finish page
            self.prepare_finish_page()
            self.stack.setCurrentIndex(2)
        else:
            # Normal progression
            self.stack.setCurrentIndex(current_index + 1)

        self.update_buttons()

    def prepare_finish_page(self):
        """Prepare the finish page with summary"""
        library_path = Path(self.library_page.get_library_path())
        self.finish_page.set_summary(library_path)

    def finish_setup(self):
        """Complete setup and save configuration"""
        # Save library path to config
        library_path = self.library_page.get_library_path()
        Config.save_library_path(library_path)

        # Create directory structure
        library_path = Path(library_path)
        library_path.mkdir(parents=True, exist_ok=True)

        print(f"Library path configured: {library_path}")

        self.accept()


__all__ = ['SetupWizard']
