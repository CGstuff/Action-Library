# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.1] - 2026-02-01

### Added

- **Solo Mode Instant Delete**
  - In Solo mode: Delete button permanently removes animations instantly (no archive staging)
  - In Studio/Pipeline mode: Archive button soft-deletes to Archive folder (existing behavior)
  - Context menu adapts: shows "Delete" in Solo mode, "Move to Archive" in Studio/Pipeline mode
  - Archive and Trash virtual folders hidden in Solo mode (not needed)
  - UI automatically updates when switching modes in Settings → Operation Mode

- **Archived Animation Protection (Blender)**
  - Blender addon now detects when source animation has been archived
  - Blocks capture with clear error message: "Animation has been archived. Please save as a new animation with a different name."
  - Prevents accidental overwrites of archived work in studio/pipeline workflows

### Fixed

- **Archive/Trash Folder Naming** - Archived and trashed animations now preserve their human-readable folder names (e.g., `walk_cycle/`) instead of being renamed to UUIDs. Collision handling adds `_2`, `_3` suffixes when needed.

- **Settings Dialog Lag** - Removed unnecessary Blender verification on settings open. Previously spawned `blender.exe --version` every time, causing 1-3 second lag. Users can still click "Verify Blender" manually when needed.

---

## [1.4.0] - 2026-01-24


#### Annotation System Overhaul

- **Always-On Annotations** - Annotation mode is now always active, and has been seperated from comments.
- **Separate Timestamps** - Annotations and comments now have independent timestamps, allowing drawings and text notes to be tracked separately on the timeline.
- **Ghosting** - See annotations from adjacent frames as faded overlays.
- **Hold** - Keep an annotation visible across multiple frames instead of just the frame it was drawn on.
- **Hide Annotations** - Quickly toggle annotation visibility on/off without deleting them (SyncSketch-style workflow).
- **MP4 Export** - Export annotated frames as MP4 video for sharing review feedback with your team.


### Fixed

- **Capture Selected Fix** - Fixed issue with a captured selected action not being applied from the app

---

## [1.3.2] - 2026-01-16

### Fixed

- **Update Notification** - Added a "Check for Updates" button in the About dialog.
- **Persistent Configuration** - Settings and database configuration are now stored in the user's AppData folder, ensuring they persist across future application updates.

## [1.3.1] - 2026-01-16

### Fixed

-**Addon Installation** - The installer now installs the plugin as a zip (ensuring persistent preferences), activates it, and automatically configures the library storage path and executable location.

## [1.3.0] - 2026-01-15

> **IMPORTANT: Breaking Change for Existing Users**
>
> Version 1.3 includes a complete database overhaul for improved stability, performance, and future extensibility. **This is a breaking change - the old library format is not compatible.**
>
> **New users:** No action needed - just install and start using the app!
>
> **Existing users (v1.2 or earlier):**
> 1. **Before updating**, apply each of your animations to Blender and save them as .blend files
> 2. Install v1.3 fresh with a new storage folder
> 3. Re-capture your animations from Blender into the new v1.3 library
>
> We sincerely apologize for this inconvenience. This database restructuring was necessary to support new features and ensure the long-term stability of the application as your library grows. We made this difficult decision now rather than later when migration would affect even more users.
>
> Thank you for your understanding and patience!

### Added

#### Dailies & Review

- **Version Comparison**
  - Side-by-side compare mode in Lineage dialog
  - Select any 2 versions to compare simultaneously
  - Synchronized playback - both videos play/pause together
  - Shared progress slider for frame-accurate comparison
  - Dialog expands to fit both previews at full size

- **Review Notes**
  - Add timestamped notes to any frame during review
  - Click timestamp to jump to that frame in preview
  - Multi-line note input with Enter for new lines
  - Multi-line editing with Save/Cancel buttons
  - Marker index badges (1, 2, 3) on notes matching timeline markers
  - Notes persist with the animation metadata

- **Unresolved Comments Badge**
  - Info icon with count appears on cards with unresolved comments
  - Badge shows in both grid and list view modes
  - Comment indicator also shown in metadata panel
  - Badge disappears when all comments are resolved

- **Drawover Annotations**
  - Draw directly on video frames during review
  - Multiple drawing tools (pen, line, arrow, shapes)
  - Annotations saved per-frame and persist with animation

#### Apply to Blender

- **Redesigned Apply Panel**
  - Split into two dedicated buttons: "New Action" and "Insert at Playhead"
  - Removed dropdown menu for cleaner, faster workflow
  - Double-click on card defaults to New Action
  - **Alt + Double-click** inserts at playhead
  - Clearer visual distinction between apply modes

#### Blender Capture

- **Selective Keyframe Capture**
  - Capture only keyframes within a specified frame range
  - Option to capture only selected bones' keyframes
  - Useful for extracting specific parts of longer animations

- **Studio Naming Engine**
  - Template-based naming system for pipeline integration
  - Configure in Blender Addon Preferences → Studio Naming
  - Template syntax: `{show}_{asset}_v{version:03}` → `MYPROJ_hero_v001`
  - Three context modes:
    - **Manual** - Enter all fields manually
    - **Scene Name** - Auto-extract fields from Blender scene name via regex
    - **Folder Path** - Auto-extract fields from .blend file path via regex
  - **Immutable versions** - Version numbers can never be changed
  - Field-based renaming in desktop app preserves template structure

#### Lineage

- **Video Preview in Lineage Dialog**
  - Preview any version directly in the Lineage dialog
  - No need to switch to main view to see animation previews

- **Version Notes**
  - Add notes to any version in the Lineage dialog
  - Document changes, feedback, or approval status per version

#### Video Preview

- **Playback Speed Control**
  - Cycle through 0.25x, 0.5x, 1x, 2x playback speeds
  - Speed button in playback controls
  - Works in both main preview and comparison mode

- **Keyboard Shortcuts**
  - **J** - Reverse playback
  - **K** - Pause
  - **L** - Forward playback
  - **Left/Right arrows** - Step single frames
  - **Space** - Toggle play/pause

- **Resizable Video Preview**
  - Drag splitter in metadata panel to resize preview area

#### Maintenance & Migration

- **v1.2 → v1.3 Migration**
  - Automatic detection of legacy v1.2 animations
  - Legacy animations imported as fresh v001 with new UUID
  - Old metadata cleared to prevent corruption
  - One-time migration only (future updates won't trigger)

- **Rebuild Database**
  - New "Rebuild Database" button in Maintenance tab
  - Clears all animations and rescans library from disk
  - Useful for fixing database corruption or sync issues

- **Maintenance Tab**
  - Database maintenance and repair tools
  - Rescan library to sync with file system
  - Orphan cleanup and integrity checks

- **Backup System Enhancements**
  - Review notes database (notes.db) now included in .animlib backups
  - Drawover annotations (.meta/drawovers/) included in backups
  - Manifest reports `includes_notes` and `drawover_count`

### Changed

- Apply panel redesigned with two buttons instead of dropdown menu
- Double-click behavior updated: plain double-click = New Action, Alt+double-click = Insert at Playhead
- Rename button added to metadata panel (next to animation name)
- Rename dialog shows field editors based on template used at capture time
- Animations captured without studio naming show simplified rename (base name + immutable version)
- Review note input now uses confirm button instead of Enter to submit
- Lineage dialog now refreshes comment badges when closed
- JSON metadata now includes `app_version` field for future compatibility

### Fixed

- **Version Inheritance** - New versions now correctly inherit folder and tags from source animation
- **is_latest Flag** - Fixed versions in cold storage incorrectly marked as latest after database rebuild
- **JSON Sync** - Database folder/tag changes now sync back to JSON files on disk

- **Blender 4.5+/5.0 Video Output Bug** - Thumbnails and previews now generate correctly when Blender's output is set to video format (handles new `media_type` property)
- **Annotation Clear Bug** - Clearing annotations no longer restores them when exiting annotation mode (cache invalidation fix)
- Fixed "Animation Library" → "Action Library" in addon installation instructions

---

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
