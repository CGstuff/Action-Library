# Getting Started

This guide walks you through setting up Action Library from first launch to capturing your first animation.

> **⚠️ Upgrading from v1.2 or earlier?**
>
> Version 1.3 has a new database format that is **not backwards compatible**.
>
> 1. **Before updating**: Apply your animations to Blender and save them as .blend files
> 2. **Install v1.3** with a fresh storage folder
> 3. **Re-capture** your animations from Blender into the new library
>
> See the [Changelog](CHANGELOG.md) for details.

---

## Prerequisites

- **Blender 4.5 or later** (supports up to Blender 5.0+)
- **Action Library** downloaded from the [Releases](../../releases) page

---

## Step 1: First Launch - Desktop App Setup

When you launch Action Library for the first time, a **Setup Wizard** will guide you through the initial configuration.

1. **Welcome Screen** - Overview of the library and its requirements
a storage folder will be created in the same directory as the .exe file

2. **Choose Library Location** 
   - the created storage file will be automatically chosen however you can pick any directory  
   - This folder will contain your animation files, thumbnails, and database
   - Choose a location with plenty of free space (roughly 1 GB per 100 animations)
   - You can change this later in Settings > Storage Locations
3. **Setup Complete** - Confirmation that your library is ready

---

## Step 2: Configure Blender Integration

After the setup wizard, configure the connection to Blender:

1. Click the **Settings** icon (gear) in the toolbar
2. Go to the **Blender Integration** tab
3. In the **Blender Executable** section:
   - Click **Browse...** and locate your `blender.exe` file
   - Or paste the full path directly
4. Click **Verify Blender** to confirm the path is valid
   - You should see a green checkmark and the Blender version

---

## Step 3: Install the Blender Addon

Still in the Blender Integration tab:

1. Click the **Install Addon** button
2. The addon will be automatically copied to Blender's addons folder
3. You'll see a success message when complete

> **Note:** You must restart Blender for the addon to appear.

---

## Step 4: Enable the Addon in Blender

After restarting Blender:

1. Go to **Edit > Preferences**
2. Select the **Add-ons** tab
3. Search for **"Action Library"**
4. Check the box to enable the addon

---

## Step 5: Configure Addon Preferences

With the addon enabled, expand its preferences panel:

### Action Library Settings

- **Actions Library Path** - Set this to the **same folder** you chose in Step 1
  - This is critical: the app and addon must use the same library location
  - Click the folder icon to browse, or paste the path

### Desktop App Launch Configuration

Choose how the addon will launch the desktop app:

**Production Mode** (Recommended for most users):
- Set **Launch Mode** to "Executable"
- Set **Executable Path** to your `AnimationLibrary.exe` location
  - Example: `C:\Tools\ActionLibrary\AnimationLibrary.exe`

**Development Mode** (For developers running from source):
- Set **Launch Mode** to "Python Script"
- Set **Script Path** to `run.py` in the project folder
- Set **Python Executable** to your Python path (or leave as "python" if in PATH)

---

## Step 6: Capture Your First Animation

Now you're ready to capture animations:

1. **Select an armature** with animation data in Blender
2. Press **N** to open the sidebar in the 3D Viewport
3. Find the **Animation Library** tab
4. Fill in the animation details:
   - **Animation Name** (defaults to the action name)
   - **Description** (optional)
   - **Tags** (comma-separated, for filtering)
   - **Author** (your name)
5. Click **Capture Action**

The animation will be saved to your library and appear in the desktop app!

---

## Step 7: Apply Animations to Blender

Once you have animations in your library, you can apply them to rigs in Blender:

### Quick Apply (Recommended)
- **Double-click** any animation or pose to apply it instantly
- **Ctrl + Double-click** to apply mirrored (swaps left/right bones)
- **Shift + Double-click** to apply as action slot (actions only)
- **Ctrl + Shift + Double-click** to apply mirrored as slot

### Using the Apply Panel
1. **Select an animation** in the desktop app by clicking on it
2. Configure apply options in the **Apply Panel** (right side):
   - **Apply Mode**: New Action (replaces current) or Insert at Playhead
   - **Mirror**: Swap left/right bones (e.g., walk cycle facing opposite direction)
   - **Reverse**: Play animation backwards
   - **Selected Bones Only**: Apply only to bones selected in Blender
   - **Use Slots**: Use Blender 4.5+ action slots system
3. Click **APPLY TO BLENDER**

> **Tip:** Power users can hide the Mirror/Slots toggles in Settings > Appearance and use keyboard shortcuts instead.

---

## Keyboard Shortcuts

Press **H** or click the **?** button in the toolbar to see all shortcuts:

| Shortcut | Action |
|----------|--------|
| Double-click | Apply animation/pose |
| Ctrl + Double-click | Apply mirrored |
| Shift + Double-click | Apply as slot (actions only) |
| Ctrl + Shift + Double-click | Apply mirrored as slot |
| Right-click + Drag | Blend pose (poses only) |
| Ctrl (while blending) | Mirror blend |
| Left-click / Escape | Cancel blend |
| H | Toggle help overlay |
| Escape | Close dialogs |

---

## Working with Poses

Poses are single-frame bone snapshots - perfect for building pose libraries.

### Capturing Poses

1. **Pose your armature** in Blender
2. Open the **Animation Library** panel (N key in 3D Viewport)
3. Fill in the pose details:
   - **Pose Name**
   - **Description** (optional)
   - **Tags** (comma-separated)
4. Click **Capture Pose**

### Applying Poses

- **Double-click** a pose to apply it instantly
- **Ctrl + Double-click** to apply mirrored

### Pose Blending

Smoothly blend between your current pose and a library pose:

1. **Right-click and hold** on any pose card
2. **Drag right** to increase blend (0% → 100%)
3. **Drag left** to decrease blend
4. **Hold Ctrl** while dragging to mirror the target pose
5. **Release** to apply the blended result
6. **Left-click or Escape** to cancel and restore original pose

> **Tip:** Pose blending is great for creating in-between poses or mixing expressions.

---

## Managing Animations

### Lineage System (Version Control)

When you edit and re-capture library animations, Action Library tracks versions automatically:

1. **Apply an animation** from the library to Blender
2. **Edit it** (modify keyframes, timing, etc.)
3. **Capture again** - The addon detects it's a library animation and offers:
   - **Create New Version** → Saves as v002 (same lineage)
   - **Create New Animation** → Saves as new v001 (fresh start)

**View Lineage**: Select any animation → Metadata Panel → Click **View Lineage** to see all versions

> **Tip:** Only the latest version shows in the main library. Older versions are in "cold storage" but accessible via View Lineage.

### Lifecycle Status (Optional)

For pipeline workflows, you can set a status on animations:

1. Select an animation
2. In the Metadata Panel, click the **Status badge** (defaults to "None")
3. Choose: WIP, In Review, Approved, Needs Work, or Final

> **Solo Artists:** You can ignore status entirely—new animations default to "None" (no badge shown on cards).

See the [Studio Guide](STUDIO_GUIDE.md) for detailed pipeline integration.

### Renaming Animations

Click the **Rename** button in the Metadata Panel (next to the animation name):

- **Edit the base name** - Change `hero_walk` to `hero_run`
- **Version stays locked** - You cannot change `v001` to `v002` (versions are immutable)
- **Preview** - See the new name before applying
- **Apply to lineage** - Optionally rename all versions at once

> **Studio Naming:** If you use the Studio Naming Engine, the rename dialog shows template fields instead of a simple text input. See the [Studio Guide](STUDIO_GUIDE.md) for details.

### Version Comparison

Compare two versions of an animation side-by-side:

1. Select an animation → **View Lineage**
2. Click **Compare**
3. Select 2 versions
4. Videos play in sync - great for spotting differences

### Version Notes

Add notes to track changes per version:

1. **View Lineage** → Select a version
2. Type notes in the **Notes** field
3. Click **Save Notes**

---

### Archive & Trash

Action Library uses a two-stage deletion system to prevent accidental data loss:

- **Archive**: Enter Edit Mode (click the edit button in the toolbar), select animations, and click the archive button
  - Archived animations move to the Archive folder
  - They can be restored or moved to Trash

- **Restore from Archive**:
  1. Click the Archive folder in the folder tree
  2. Enter Edit Mode
  3. Select animations you want to restore
  4. Click "Restore to Library" button

- **Restore from Trash**:
  1. Click the Trash folder in the folder tree
  2. Enter Edit Mode
  3. Select animations you want to restore
  4. Click "Restore to Archive" button

- **Empty Trash**: Right-click the Trash folder and select "Empty Trash" to permanently delete all trashed items

---

## Tips & Troubleshooting

### Library Path Must Match
The most common issue is mismatched paths. Ensure the library path in **Blender addon preferences** matches the path shown in **Action Library > Settings > Storage Locations**.

### Restart Blender After Installation
The addon won't appear until you restart Blender after installation.

### FFmpeg for Video Previews (Blender 5.0+)
If you're using Blender 5.0 or later, video preview generation requires FFmpeg. The addon will fall back to PNG sequences if FFmpeg isn't available.

### Supported Rig Types
The library automatically detects common rig types:
- Rigify
- Mixamo
- Auto-Rig Pro
- Epic Skeleton (Unreal)
- Custom rigs
-you can also override and name your rigs

### Need Help?
- Check the [README](README.md) for feature overview
- See the [Studio Guide](STUDIO_GUIDE.md) for multi-artist/team deployment
- Report issues on [GitHub Issues](../../issues)
