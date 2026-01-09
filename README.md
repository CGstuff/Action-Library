# Action Library

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/PyQt-6.5+-green.svg)](https://pypi.org/project/PyQt6/)

A high-performance animation library manager for Blender with modern Qt6 architecture.

## Background

This tool was built after completing a 55-minute 3D animated feature film, produced largely as a solo technical director.

During production, I repeatedly hit limitations in Blender when managing animation data at scale—particularly around reuse, organization, and pipeline-style workflows. By the end, these issues formed a clear pattern.

Action Library is the result: a Blender-native, pipeline-oriented animation manager designed for scalability and long-form production. Open-sourced so others working on serious Blender projects can build on the same foundation.

<!--
## Screenshots
Add screenshots here:
![Main Window](screenshots/main.png)
![Theme Editor](screenshots/theme-editor.png)
-->

## Features

### Core
- **High Performance** - Handles 4000+ animations with <2s startup and 60 FPS scrolling
- **Modern UI** - Grid and list views, customizable themes, smooth animations
- **Smart Organization** - Folders, tags, favorites, and powerful search/filtering
- **Blender Integration** - One-click animation loading with built-in addon installer (Blender 4.5 - 5.0+)
- **Library Backup** - Export/import with .animlib archives, preserves all metadata
- **Setup Wizard** - Guided first-run configuration for new users
- **Portable** - Single-folder distribution, no installation required

### Pipeline Features (v1.1)
- **Lineage System** - Track animation versions with automatic iteration detection
  - Apply animation → Edit in Blender → Capture as v002, v003, etc.
  - Cold storage: only latest version visible, older versions accessible via View Lineage
  - Promote any version to latest, compare version history
- **Lifecycle Status** - Pipeline-ready approval workflow
  - Statuses: None (default), WIP, In Review, Approved, Needs Work, Final
  - Color-coded badges on cards and metadata panel
  - Solo artists can ignore (defaults to no badge); studios enable for review tracking

## Installation

### Option 1: Download Release (Recommended)

Download the latest portable release from the [Releases](../../releases) page.

> **Note:** Windows may show an "Unknown publisher" warning on first run. Click **More info** → **Run anyway**. This is normal for unsigned open source software.

### Option 2: Run from Source

**Prerequisites:**
- Python 3.9 or higher
- Git

**Steps:**

```bash
# Clone the repository
git clone https://github.com/CGstuff/action-library.git
cd action-library

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

## Building Portable Version

To create a standalone portable build:

```bash
# Install PyInstaller (if not already installed)
pip install pyinstaller

# Run the build script
build.bat
```

The portable build will be created in `dist/ActionLibrary/`.

## Architecture

Built with:
- **PyQt6** - Modern Qt6 bindings for Python
- **Model/View Pattern** - Efficient handling of large datasets
- **Async Loading** - Background thumbnail loading via thread pool
- **Event Bus** - Decoupled component communication
- **SQLite** - Fast local database with WAL mode

For detailed architecture information, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Documentation

- [Getting Started](GETTING_STARTED.md) - First-time setup and onboarding guide
- [Studio Guide](STUDIO_GUIDE.md) - Multi-user deployment and pipeline integration
- [Architecture Overview](ARCHITECTURE.md) - System design and patterns
- [Developer Guide](DEVELOPER_GUIDE.md) - Development setup and guidelines
- [Widget Reference](WIDGET_REFERENCE.md) - UI component documentation
- [Contributing](CONTRIBUTING.md) - How to contribute
- [Changelog](CHANGELOG.md) - Version history

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
