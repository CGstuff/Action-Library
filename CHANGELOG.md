# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-01-10

### Added

- **Pose Support**
  - Capture poses (single-frame bone snapshots) directly from Blender
  - Apply poses instantly to armatures in Blender
  - Poses are simple building blocks - no versioning or lifecycle tracking
  - Auto-keyframe support: when Blender's auto-key is enabled, applying a pose inserts keyframes
  - Pose badge on cards distinguishes poses from actions

- **Pose Blending**
  - Right-click hold + drag on any pose to blend from current pose to target
  - Drag right to increase blend (0-100%), drag left to decrease
  - Hold Ctrl while dragging to mirror the pose
  - Left-click or Escape to cancel and restore original pose
  - Release right-click to apply the blended result
  - Clean overlay UI showing percentage, pose name, and mirror status

- **Keyboard Shortcuts**
  - **Double-click** - Apply animation/pose
  - **Ctrl + Double-click** - Apply mirrored (swaps left/right bones)
  - **Shift + Double-click** - Apply action as slot (actions only)
  - **Ctrl + Shift + Double-click** - Apply mirrored as slot
  - **?** button in toolbar - Show keyboard shortcuts

- **Help Overlay**
  - click ? to view all keyboard shortcuts
  - Organized by category: Apply Actions, Pose Blending, Navigation, General

- **Instant Application via Socket Bridge**
  - Real-time TCP socket connection between desktop app and Blender
  - Apply actions and poses instantly without file-based polling
  - Automatic fallback to file-based queue if socket unavailable
  - Modal operator ensures reliable main-thread execution in Blender

- **Reorganized Virtual Folders**
  - **Home** - Shows all items (actions + poses)
  - **Actions** - Shows only actions (excludes poses)
  - **Poses** - Shows only poses
  - **Recent** - Recently viewed items
  - **Favorites** - Favorited items

- **Blender 5.0 Action API Compatibility**
  - Updated pose capture for Blender 5.0's layered action system
  - Proper handling of action layers, strips, and channelbags

- **Power User Setting**
  - Option to hide Mirror/Slots toggles in Apply panel (Settings > Appearance)
  - Power users can use keyboard shortcuts instead for cleaner UI

### Changed

- Poses do not use versioning/lineage (they're fast, iterative building blocks)
- Poses do not show version badges or lifecycle status badges
- Metadata panel hides version section for poses
- Apply button renamed from "APPLY ACTION TO BLENDER" to "APPLY TO BLENDER"
- Mirrored pose application now uses Blender's native pose copy/paste for accurate results

### Fixed

- Fixed checkbox styling in settings - clear distinction between on (accent) and off (gray) states
- Sharp UI styling throughout settings dialogs for consistent appearance

---

## [1.1.0] - 2026-01-09

### Added

- **Lineage System (Animation Versioning)**
  - Track animation versions with shared lineage (version_group_id)
  - Automatic version detection when capturing edited library animations
  - Version choice dialog: "Create New Version" or "Create New Animation"
  - View Lineage dialog showing all versions of an animation
  - Cold storage: only latest version shown in main view, older versions accessible via lineage
  - Continuous iteration in Blender: capture v002 → edit → capture v003 without re-applying
  - Smart version naming: strips existing suffix (Jump_v002 → Jump_v003)

- **Library Action Detection in Blender**
  - Actions applied from library store metadata (UUID, version, lineage info)
  - Panel indicator shows "Library Action Detected" with source info
  - Metadata persists through edits and updates after each capture

- **Lifecycle Status System**
  - Pipeline-ready status workflow: WIP, In Review, Approved, Needs Work, Final
  - "None" status option for solo animators who prefer a simple asset browser experience
  - Clickable status badge in metadata panel with dropdown menu
  - Color-coded status badges on animation cards (grid and list view)
  - Status visible in Lineage dialog for each version
  - New animations default to "None" status - no badge clutter for casual users


---

## [1.0.0] - 2026-01-06

### Added

- **Archive & Trash System**
  - Archive animations instead of permanent deletion
  - Trash folder with restore capability
  - Empty trash manually or automatically

- **Apply to Blender Panel**
  - Dedicated apply panel in desktop app with options
  - Apply modes: New Action or Insert at Playhead
  - Mirror animation (swap left/right bones)
  - Reverse animation playback
  - Apply to selected bones only
  - Use Action Slots (experimental - for future animation layers workflow)

- **Video Preview**
  - Hover preview popup for animation cards
  - Inline video playback in details panel

- **Blender 5.0 Support**
  - Full compatibility with Blender 5.0+
  - FFmpeg fallback for video preview generation

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

- **Help & Documentation**
  - About dialog with version information
  - Comprehensive logging system for debugging
  - Studio Deployment Guide for multi-artist teams

- **UI Customization**
  - Adjustable folder tree text/icon size in Theme settings

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
