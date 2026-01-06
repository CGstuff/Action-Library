# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-06

### Added

- **Animation Library Management**
  - Import and organize animation files (.blend)
  - Automatic metadata extraction (frame count, FPS, duration)
  - Thumbnail generation with customizable gradients
  - Favorites system for quick access
  - Recent animations tracking

- **Folder Organization**
  - Create custom folder hierarchy
  - Drag and drop animations between folders
  - Virtual folders (All Animations, Recent, Favorites)
  - Custom folder icons with color presets

- **Search and Filtering**
  - Real-time search across animation names
  - Filter by rig type
  - Filter by tags
  - Multiple sort options (name, date, duration)

- **View Modes**
  - Grid view with adjustable card sizes
  - List view for compact browsing
  - Edit mode for bulk selection and deletion

- **Theme System**
  - 4 built-in themes (Dark, Maya Classic, Light, High Contrast)
  - Custom theme editor with live preview
  - Per-color customization (40+ color options)
  - Save and share custom themes

- **Blender Integration**
  - One-click animation loading into Blender
  - Blender addon for seamless workflow
  - Addon installer built into the app
  - Support for Blender 4.5+

- **Library Backup System**
  - Export entire library to portable .animlib archive
  - Import archives with automatic metadata restoration
  - Preserves tags, favorites, folder structure, and folder icons

- **First-Run Experience**
  - Setup wizard for new users
  - Library path selection and configuration

- **Help & Information**
  - About dialog with version information
  - Comprehensive logging system for debugging

- **Portable Distribution**
  - Single-folder portable build
  - No installation required
  - PyInstaller-based packaging
  - Windows support

- **Performance**
  - Handles 4000+ animations efficiently
  - Async thumbnail loading
  - SQLite database with WAL mode
  - Virtual scrolling for large libraries

### Technical

- Built with PyQt6 and Python 3.9+
- Model/View/Controller architecture
- Event bus for component communication
- Thread-safe database operations
- Comprehensive logging system
