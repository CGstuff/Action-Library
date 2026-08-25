# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.7] - 2026-08-25

### Added

- **Updates Install Themselves** - Action Library now notices when a newer release exists and offers to install it. A bar across the top of the window tells you which version is waiting; **Update Now** shows the release notes and download size, fetches the build, then closes, swaps itself for the new version and reopens. Previously the check was a button buried in the About dialog that only opened a browser, so most people never found it - one user ran months-old builds without realising, and another assumed updating the Blender addon updated the app too. It doesn't; they're separate downloads, and now the app says so itself.
- **The Update Never Touches Your Library** - Only the program itself is replaced - `ActionLibrary.exe` and its `_internal` folder, named explicitly. Everything else in the install folder is left exactly as it is, which matters because a default install keeps your library at `storage/` right beside the program. The download is unpacked somewhere else entirely and only copied in once it's verified complete, and the previous version is set aside rather than deleted, so a failed update puts itself back instead of leaving you with a broken install.
- **It Stays Out of Your Way** - The check runs in the background a couple of seconds after launch and shows nothing at all unless there's genuinely something newer - no dialog, no error if you're offline or GitHub is unreachable. The bar can be dismissed for the session. If the app can't update itself - running from source, or installed somewhere it lacks write permission - it says so plainly and points you at the release page instead of failing partway through.

## [1.5.6] - 2026-08-25

### Fixed

- **The App Reported the Wrong Version** - 1.5.4 and 1.5.5 both installed and reported themselves as "1.5.3". The build stamps the version from the newest git tag it can see, and the clone the releases are built from was missing the newer tags, so both releases went out carrying the old number. The Blender addon bundled with those builds was stamped from the same number, so its `bl_info` was wrong too - which could produce a spurious version-mismatch warning in the N-panel against an addon that was actually up to date. The build now refuses to run if the tag it detects doesn't match the top entry in this changelog, instead of silently shipping a mislabelled build.
- **"Addon Up To Date" When the App Wasn't** - the N-panel only ever checked whether the addon was *older* than the app. Updating the addon from inside Blender doesn't update the desktop app, so that left the common case backwards: the addon was newer, the check treated that as fine, and the panel showed a green "Addon up to date" tick while the app sat two versions behind. It now says which half is behind, and when it's the app it spells out that updating the addon does not update the app and points at the releases page. The install docs now cover the in-Blender updater and its scope as well.
- **Antivirus Flagging and Closing the App** - the Windows build was compressed with UPX, an executable packer commonly used to obfuscate malware, which meant antivirus heuristics flagged it on sight - in some cases terminating the app a few seconds after launch. In this build layout UPX was also compressing every bundled library, multiplying the detections. It's now disabled. The download is larger as a result. This reduces false positives but does not eliminate them: the application is not yet code-signed, and unsigned installers are always treated with suspicion. If your antivirus still objects, reporting it to your vendor as a false positive is the fastest route, and it genuinely helps other users.

## [1.5.5] - 2026-08-25

### Added

- **Animated Previews in the Grid** - Every card in the grid plays its animation at once, the way a browsing library should behave, instead of showing a still thumbnail until you hover. It's on by default; turn it off with the **▶ Previews** button in the header or in Settings > Appearance. Decoding a video per card would have been far too expensive to do for a whole screenful, so each preview is baked once into a sprite sheet and played back from that: a full screen of animating cards costs a fraction of a percent of one CPU core, and sheets are released as you scroll past so memory stays flat no matter how large the library. Sheets are cached per machine rather than in the library, so they cost no network traffic and nothing is written to a shared disk. Each card starts on a slightly different frame so the grid doesn't pulse in lockstep, and previews pause while the app is in the background. Hovering a card still opens the larger popup preview as before - animated cards are in addition to it, not a replacement.
- **The Preview Panel Plays on Its Own** - Selecting a card now starts the large preview on the right immediately instead of waiting for you to press play. Looping is already on by default, so it keeps running while you look at it. Compare mode and version history are unchanged - those play on demand so the clips you're comparing stay in step.

## [1.5.4] - 2026-08-20

### Fixed

- **Apply At Playhead Did Nothing on a Rig With No Action** - Applying at the playhead onto a rig that had no action yet produced an empty action that didn't drive anything. The action was created without the layer/strip/slot structure Blender 4.4+ needs, so no keyframe channels could be made and the whole insert failed silently. It now builds and binds the slot properly. A channel that still can't be created is skipped with a named warning instead of aborting the rest of the animation.
- **Apply At Playhead Flattened Curve Interpolation** - Pasting at the playhead only carried each keyframe's frame and value, so interpolation was inherited from whatever was already in the destination channel — or from Blender's Default Interpolation preference when the channel was empty. Stepped blocking came back smoothed, and hand-tuned eases were lost. Interpolation, easing, keyframe type and bezier handles now come across from the source, with handles offset to the paste position (and mirrored when applying reversed). Thanks to the report on GitHub that pinned this down.

## [1.5.3] - 2026-08-20

### Added

- **Update the Addon from Blender** - The Blender addon can now check GitHub for new releases and update itself in place, from its own preferences (Edit > Preferences > Add-ons > Action Library > Updates). It backs up the current addon before updating, and an available update is also flagged in the N-panel. Installing from the desktop app still works as before.
- **Addon Version Warning in the N-panel** - The addon now shows whether it matches the desktop app that owns your library: a confirmation when it's current, or a warning telling you to reinstall when it's older. The app and the addon are versioned together, so a mismatch is the cause of most odd behaviour.
- **Edit Author in the App** - The author field is now editable from the metadata panel, alongside the description. Writes to both the database and the JSON sidecar.

### Changed

- **Card Size is Remembered** - The grid card-size slider now persists between sessions instead of resetting to the default on every launch.

## [1.5.2] - 2026-08-20

### Added

- **Edit Descriptions in the App** - An animation's description is now editable directly in the metadata panel (Edit → type → Save). Previously it could only be set at capture, so users hand-edited the JSON sidecar and the change never appeared — the app doesn't re-read that field for an animation it already knows. Editing in the app writes both the database and the JSON sidecar, so the two always agree.
- **In-App Documentation (work in progress)** - Started building local documentation that opens in your browser (Docs button in the header, or F1) — no internet needed. Covers getting started, installing/updating the Blender addon, the library, capturing, applying, versions, organizing, review, archive/delete, storage, settings, and a reference. More topics and screenshots to come.

### Changed

- **New Versions Inherit the Description** - Capturing a new version now carries the previous version's description forward (alongside tags and folder, which already inherited), instead of starting blank. Anything typed in the capture panel still overrides it. Per-take commentary belongs in review notes, which remain per-version.

## [1.5.1] - 2026-07-15

updated Bl_info

## [1.5.0] - 2026-07-15

### Fixed

- **Blender Auto-Save Restored** - With the addon enabled, Blender's auto-save silently never ran because the socket listener was a permanent modal operator (Blender skips auto-save while a modal operator is active). The listener now drains its queue via `bpy.app.timers`, so auto-save works normally without toggling the addon off.
- **App Freeze / Stall on Apply** - Fixed the desktop app freezing on the second Apply (a socket response desync left the connection permanently out of step) and, separately, the UI stalling on slow applies (the socket round-trip now runs off the UI thread instead of blocking it for up to 30s).
- **Rename Broke Apply** - Applying an animation after renaming it failed ("blend file not found") because the addon trusted a stale embedded path. Apply now locates the file by UUID, so renamed assets apply correctly.
- **Thumbnails/Previews Missing for Other Animators** - On shared/network libraries, peers on a different drive letter saw missing thumbnails because path resolution reconstructed the wrong folder. Resolution now rebuilds the correct `actions/`/`poses/` folder and falls back to matching files, so all animators see previews.
- **Deleting the Latest Version Erased the Asset** - Deleting the latest version of a multi-version animation left the lineage with no current version, making the whole asset vanish from the grid. A surviving version is now promoted automatically.
- **Move to Archive Crash** - "Move to Archive" from the card context menu crashed (missing method); it now archives correctly.
- **Archive/Restore Data Loss** - Restoring from Archive placed files in the wrong location, could create a corrupted version state (two "latest" versions), and lost the custom thumbnail gradient/favorite/status. Restore now targets the correct folder, reconciles the version flags, and preserves that metadata.
- **Honest Apply Status** - The app no longer reports "Applied" when Blender is closed and the request was only queued; it now distinguishes Applied / Queued / Failed.
- **Apply-as-Slot on a Fresh Rig (Blender 5)** - Applying with "Use Slots" onto an armature with no existing action silently degraded to a plain (non-slotted) action; it now creates a proper slotted action.

### Reliability

- **Network Database Corruption Guard** - The shared metadata database used SQLite WAL mode, which relies on shared memory that is unreliable over network shares and can corrupt the database. It now uses a network-safe rollback journal; existing databases convert automatically and safely on first open.

## [1.4.4] - 2026-05-13

### Changed

- **Settings UI Redesign** - Replaced the tabbed Settings dialog with a sidebar + stacked-page layout (Photoshop / Blender prefs style). Sidebar styling reacts live to theme changes.

### Fixed

- **Annotations Corrupted by Hidden Playback** - With annotations hidden, pressing Play overwrote every subsequent frame's drawover on disk with the previously-loaded frame's strokes. Hide mode now skips both the save and load paths, so the stale canvas state can't leak across frames.
- **Erased Frames Not Persisting** - Erasing all strokes on a frame previously left the old data on disk and kept the timeline marker visible. The empty state is now written and the marker is cleared.
- **Annotations Frozen During Compare-Mode Playback** - In side-by-side compare mode, drawovers stayed stuck on the entry frame as the video played. Per-frame annotations now refresh on every playback tick.
- **Frame Timeline Off-By-One** - Clicking near the right edge of the frame ruler could return a frame whose marker rendered slightly to the left. Click and marker positions now round-trip symmetrically.
- **Eraser Memory Leak** - Erased strokes left orphan entries in the canvas's internal data map across erase/undo cycles. Entries are now removed alongside the stroke.

### Reliability

- **Atomic Annotation Saves** - Drawover JSON files are now written via tempfile + atomic rename. A crash mid-write can no longer leave a truncated, unparseable file.
- **Concurrent-Edit Safety** - All load-modify-write paths in the annotation storage layer are now guarded by a reentrant lock. Concurrent stroke add/remove on the same frame can no longer drop strokes through a lost-update race.
- **Audit Log + Metadata in One Transaction** - Studio Mode's drawover audit log and the per-frame metadata table now update inside a single database transaction. They can no longer drift out of sync.
- **Manifest Consistency** - The drawover manifest is now written before the PNG cache is invalidated, and a failed PNG delete no longer breaks the manifest.
- **Restore Stroke Safety** - Restoring a soft-deleted stroke now stages the modified state locally before writing; a failed write can no longer leave a dangling deletion record.
- **Thread-Safe Annotation Cache** - The in-memory drawover cache is now thread-safe.

### Internal

- Annotation storage and notes-database error reports moved from ad-hoc `print(...)` to logger calls; failures now surface in the log file with stack traces.
- Removed leftover debug prints from the storage layer.
- `datetime.utcnow()` (deprecated in Python 3.12+) replaced with `datetime.now(timezone.utc)` in annotation timestamp generation.

---

## [1.4.3] - 2026-02-16

### Fixed

- **AnimLib Import Path Rebasing** - Importing an `.animlib` archive from a different storage location no longer leaves stale absolute paths in the database or JSON files. All file paths (`blend_file_path`, `json_file_path`, `preview_path`, `thumbnail_path`) are now automatically rebased to the actual filesystem location during import and library rescan.

- **Manual Library Copy Support** - Manually copying a library folder to a new location and rescanning now correctly updates all paths. Previously, the scanner trusted absolute paths from JSON files even when the files had moved.

- **JSON Path Cleanup on Import** - After extracting an `.animlib` archive, JSON files on disk are rewritten with corrected paths so that future re-exports produce clean, portable archives.

### Added

- **Blender Addon: Sync Library Path from Desktop App** - New sync button in addon preferences reads the library path from the desktop app's config (`library_path.txt`), eliminating the need to manually set the same path in both places.

- **Auto-Sync on First Load** - When the Blender addon has no library path configured, it automatically reads the path from the desktop app on file load (first-time setup convenience).

---

## [1.4.2] - 2026-02-12

### Fixed

- **Addon Install Crash on Windowed Exe** - Fixed "argument of type 'NoneType' is not iterable" error when clicking Install Addon from the packaged app. Subprocess stdout can be `None` in PyInstaller windowed mode on Windows; all Blender subprocess calls now guard against this. Also suppresses console window flash during Blender verification and addon installation.

---

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
