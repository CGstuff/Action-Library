# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.2] - 2026-10-21

### Added

- **Capture All Slots** - When the rig's action holds more than one slot, the Capture section now offers **Active Slot | All Slots**. All Slots saves every take that belongs to this rig in one library entry - the slot it's playing, plus any unused slot whose bones all exist on the rig. Slots used by another rig or object, shape keys, materials, slots animating bones this rig doesn't have, and empty slots are left out. The panel lists what will be captured and what won't, with the reason for each, before you press Capture, and the capture repeats which slots it skipped so nothing goes missing silently. Applying the entry brings all its takes back and plays the one you were on when you captured; switch takes in Blender's Action editor afterwards.
- **The Library Shows an Entry's Slots** - Cards for entries holding several slots carry an "N slots" badge beside the version badge (shortened to "×N", or left out, when a small card needs the room for its status badge); list view shows the count after the name. The metadata panel lists each slot with its frame range and marks the one that plays. Entries captured from Blender actions with slots record which slot they came from; older entries simply show nothing.

### Fixed

- **Capture Ignored the Slot You Were Working On** - The addon had no idea Blender actions can hold several slots, so everything it did read the action's first slot, whichever one the rig was actually playing. With a 25-frame slot and a 17-frame slot, the panel and the capture always reported 25 frames - and after deleting the first slot's keys, it said "No keyframes found" while the second slot played on screen. The capture also saved the whole action, so the library file held every other take and any other object's animation sharing that action, while the preview rendered the slot you were on over the first slot's frame range. Capture, Capture Selected, Update Preview and the panel's frame and keyframe counts now all follow the slot the rig is playing, and the library file holds only that slot.
- **Capturing a Second Slot Offered to Version the First** - Library tracking was stored once per action, so after capturing one slot, capturing another slot of the same action asked whether to save it as a new version of the first. Tracking is now kept per slot. Actions tracked by earlier versions keep working: their tracking is treated as belonging to the first slot and moved over the next time it's written.
- **Applying Could Play the Wrong Slot - Even a Camera's** - Applying always played an action's first slot. For library files that held several slots, that could be a prop's or a camera's, whose movement then drove your rig. Apply now plays the slot the capture recorded, and for older files the first slot whose bones all exist on the rig - never a slot meant for something else.
- **Insert at Playhead Wrote Into the Wrong Slot** - Inserting at the playhead put the keys into the action's first slot, not the one the rig was playing, so they appeared to vanish. They now go into the active slot.
- **Curves Lost Their Shape When Copied** - "Add as slot", Duplicate Slot, Reverse and Selected Bones Only copied each key's frame and value and nothing else, so handles, interpolation and easing fell back to Blender's defaults: stepped blocking came out smoothed, custom handles came out auto. Every key property now comes across intact. Reversing also swaps handles, ease-in and ease-out, and moves each segment's interpolation to the key that now starts it, so a reversed curve really is the original played backwards.
- **Slot Manager Showed "Slot 1, Slot 2"** - The slot list now shows each slot's real name, duplicates are named after their source, and the merge selection no longer shifts onto the wrong slots after one is deleted.
- **Applies Silently Went to Another Addon** - The addon and the Blender MCP addon both listen on port 9876, and on Windows both were allowed to hold it at once - each connection from the app then landed on whichever one Windows picked. When it was MCP, the apply simply failed with an error that said nothing about why. The addon no longer shares a port another program holds: it shows a red warning in its panel and its preferences and falls back to the slower file queue, which still reaches Blender. The app now checks it is actually talking to Action Library before applying, and when something else answers it says so plainly once, with how to fix it, and queues the apply instead. Changing the Socket Port in the addon's preferences or the app's Settings > Blender Integration now takes effect immediately - no restart of either.

### Changed

- **Database Schema v13** - Three columns record how many slots an entry holds, how it was captured, and which slots they are. The upgrade happens on first launch, only adds columns, and keeps every existing entry as it was; versions of the app that haven't updated keep reading and writing the shared library. Entries captured since slot support began fill in their slot information on the next library refresh.

## [1.6.1] - 2026-10-11

### Fixed

- **"Access Is Denied" When Launching the App From Blender** - Launching the desktop app from the N-panel could fail with `[WinError 5] Access is denied`, which reads like an antivirus or permissions problem and usually wasn't one. If the executable path in the addon's preferences pointed at the install *folder* instead of the .exe inside it, nothing caught it: the preferences panel checked only that the path existed - which is true of a folder - and confidently reported "Executable found", so there was no reason to suspect the setting. The launch then handed a directory to Windows, which refused it. Both the panel and the launch now check that the path is a file and an actual .exe, and say which of those is wrong. A genuine permission refusal is now reported as one, naming antivirus and the "Unblock" checkbox in the file's Properties.
- **Installing the Addon From the App Could Point It at Python Instead of the App** - Settings > Blender Integration > Install Addon fills in the executable path for you, so you never have to find it yourself. It used the path of the running program - correct for the packaged app, but when Action Library is run from source that is `python.exe`. The addon was handed the interpreter, forced into Production mode, and clicking Launch started a bare Python process with no script and no window: nothing appeared to happen and nothing explained why. The installer now recognises which way it is running and configures the addon for the matching mode - the .exe for a packaged build, `run.py` and Development mode from source.
- **Installing With No Library Path Set Mixed Up the Addon's Settings** - If the addon installer had a launch path to configure but no library path, the launch path was written into the addon's *library path* setting instead, leaving both wrong. The settings are passed positionally and an empty one was skipped rather than left blank, so everything after it shifted up by one.
- **Preferences Said the Wrong Filenames** - The addon's preferences asked for `AnimationLibrary.exe` and `studio_main.py`; the build produces `ActionLibrary.exe` and the script is `run.py`. The build location shown was wrong too. Leftovers from the project's old name, which made the field harder to fill in correctly, not easier.

## [1.6.0] - 2026-08-27

### Fixed

- **The Blender Panel Made Heavy Rigs Unresponsive** - With the Action Library tab open in the N-panel and an animation loaded, bones became sluggish or stopped responding to dragging altogether - and switching to any other tab fixed it instantly. The panel recounted every keyframe on every curve in the action, twice, and rescanned every bone name to detect the rig type - not once, but on every single redraw, which Blender performs continuously as you move the mouse. On a game rig with a few hundred bones that was tens of milliseconds of work per redraw, on the same thread Blender uses to handle your input, so your dragging simply queued up behind it. Nothing was ever locked. Those values are now calculated when they change instead of when they are drawn.
- **A Failed Apply Could Leave a Rig Permanently Unanimatable** - If applying an animation from the app failed for any reason, the request was left in the queue and retried ten times a second for as long as Blender stayed open - re-applying the animation over whatever you were doing, so bones appeared locked and only intermittently responded. The queue lives inside the library, so restarting Blender didn't help, and disabling the addon only appeared to fix it because that stopped the retries. A failed request is now discarded, anything older than two minutes is abandoned, and the retry rate drops while the addon is waiting for you to select a rig.
- **Poses Captured With No Thumbnail** - If Blender's output was set to Video (Output Properties > Output > Media Type), capturing a pose produced no thumbnail at all - the pose saved fine, but the card stayed blank with nothing to explain why. With the media type set to Video, Blender only permits video file formats, so the addon's attempt to switch the output to PNG for the thumbnail was rejected outright and the render never happened. Pose capture now switches the media type as well, takes the thumbnail, and restores your output settings exactly as they were. The other capture paths already did this; only poses were affected.
- **A Failed Thumbnail Is No Longer Silent** - When a thumbnail can't be rendered, capture now says so instead of reporting success, and no longer records a thumbnail that doesn't exist. If Blender writes the image under a name of its own choosing, it is found and put where it belongs rather than treated as a failure.
- **Capturing Changed Your Viewport Lighting and Left It That Way** - Capturing could leave the viewport's solid-mode lighting switched to Studio, so anyone working in Flat or with a MatCap silently lost their setting. Preview rendering changed the lighting without recording what it was, so there was nothing to restore. Pose capture could also leave overlays, gizmos, the toolbar and the header switched off, because setting up the render referenced a lighting preset that isn't valid for solid shading and aborted part-way through. Both are fixed across all four capture paths.

### Changed

- **The Addon Idles Quietly** - With no app connected, the addon's background checks drop from thirty wake-ups a second to three, and the check for queued work no longer lists the library folder unless something in it actually changed. On a shared network library that listing was a round-trip on Blender's main thread, ten times a second, for as long as Blender was open. Responsiveness while the app IS connected is unchanged.
- **Background Work Scales to Your Machine** - The desktop app sized its background workers to a fixed number regardless of the computer running it - a small share of a workstation, but every core of a laptop, while Blender was trying to use the same processor. Worker counts now scale with the machine, and preview generation gets its own smaller pool so it can never crowd out the rest of the app.

## [1.5.9] - 2026-08-26

### Fixed

- **Poses Captured With No Thumbnail** - If Blender's output was set to Video (Output Properties > Output > Media Type), capturing a pose produced no thumbnail at all - the pose saved fine, but the card stayed blank with nothing to explain why. With the media type set to Video, Blender only allows video file formats, so the addon's attempt to switch the output to PNG for the thumbnail was rejected outright and the render never happened. The pose capture now switches the media type as well, takes the thumbnail, and puts your output settings back exactly as they were. Animation capture already did this correctly; only poses were affected.
- **A Failed Thumbnail Is No Longer Silent** - When a thumbnail can't be rendered, the capture now says so instead of reporting success, and no longer records a thumbnail that doesn't exist - which is what left cards loading forever with nothing behind them. If Blender writes the image under a name of its own choosing, it's now found and put where it belongs rather than treated as a failure.
- **Pose Capture Left the Viewport Changed** - Capturing a pose could leave your overlays, gizmos, toolbar and header switched off. Setting up the preview render referenced a lighting preset that isn't valid for solid shading, which aborted the setup part-way through and skipped restoring anything it had already changed. The preset is now chosen from ones that exist, and a setup that fails part-way still restores what it touched.

## [1.5.8] - 2026-08-26

### Fixed

- **Poses Stuck on "Loading..." Forever** - Cards whose thumbnail couldn't be found sat on "Loading..." indefinitely instead of saying the image was missing, and re-attempted the load on every single repaint - a library whose thumbnails didn't resolve would keep the loader busy for as long as the window was open. A failed thumbnail is now attempted once and the card honestly reports "No Image". Re-capturing a preview or running a repair clears that and tries again.
- **Poses Filed Under the Wrong Type Lost Their Thumbnails** - Whether an asset is a pose decides which folder every lookup searches. If that flag disagreed with where the files actually sat - most often after a library was moved or opened from another machine - every search went to the wrong folder and the thumbnail was never found, even though the file was right there on disk. Poses were hit hardest: an action in the wrong place usually still gets rescued by a folder-level fallback, a pose doesn't.
- **Fix Pose Flags Now Repairs That** - The repair in Settings > Maintenance previously only looked at frame counts, and could only ever mark something as a pose. It now also compares each asset against the folder it is actually stored in and corrects the flag in either direction, reporting what it changed. Only unambiguous cases are touched, and it corrects the database rather than moving any files.

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
