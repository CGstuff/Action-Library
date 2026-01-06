# Getting Started

This guide walks you through setting up Action Library from first launch to capturing your first animation.

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
- Report issues on [GitHub Issues](../../issues)
