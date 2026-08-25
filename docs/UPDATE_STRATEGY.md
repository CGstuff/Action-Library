# Update & Configuration Strategy

This document outlines the architecture implemented in v1.3.2 to streamline updates, persistence, and Blender integration.

## Level 1: Persistent Configuration (AppData)

**Problem:** Previously, settings were stored in `_internal/data` inside the app folder. Updating the app (deleting the folder) caused data loss.

**Solution:**
- `Config.get_user_data_dir()` now points to the OS user data directory:
  - **Windows:** `%LOCALAPPDATA%\ActionLibrary\`
  - **Mac:** `~/Library/Application Support/ActionLibrary/`
  - **Linux:** `~/.local/share/ActionLibrary/`
- **Portable Mode:** If a file named `portable.txt` exists next to the executable, it reverts to using the local `data` folder (for USB usage).

**Benefit:** Users can delete the old app folder and unzip a new version without losing their library path, theme, favorites, or settings.

---

## Level 2: Smart Addon Installation & Updates

**Problem:** Users had to manually install the addon zip, then manually configure the library path and executable path in Blender preferences.

**Solution:**
1.  **Zip-based Installer:**
    - The app zips the `blender_plugin` folder on the fly.
    - It runs a python script (`install_addon.py`) inside Blender (headless mode) to install this zip.
    - This ensures Blender treats it as a proper addon (persistent registration).

2.  **Auto-Configuration:**
    - The installer script accepts arguments for `storage_path` and `exe_path`.
    - Immediately after installation, it sets these values in the addon preferences and saves `userpref.blend`.
    - **Result:** The user clicks "Install" once, and everything is fully configured.

3.  **Update Detection:**
    - The **Integration Tab** checks the installed addon version (by reading `__init__.py` in the addons folder).
    - If the installed version is older than `Config.APP_VERSION`, the button changes to **"Update Addon"** (Orange).
    - Clicking it overwrites the old addon with the new code.

---

## Level 2.5: Application Update Notification

**Problem:** Users didn't know when a new version of the Desktop App was available.

**Solution:**
- **UpdateService:** Checks the GitHub API (`repos/CGstuff/Action-Library/releases/latest`).
- **About Dialog:** Added a **"Check for Updates"** button.
    - Compares current `APP_VERSION` with the latest GitHub tag.
    - If newer, offers to open the download page in the browser.

---

## Future Roadmap (Level 3)

**Goal:** Full Auto-Updater (Chrome-style).

**Requirements:**
1.  **Hosting:** A reliable endpoint for `latest.json` and `.zip` files.
2.  **Updater.exe:** A separate small executable shipped with the app.
3.  **Process:**
    - App downloads update to `%TEMP%`.
    - App launches `Updater.exe` and closes itself.
    - `Updater.exe` moves files from Temp to Install Dir.
    - `Updater.exe` restarts Main App.

*Current Status:* Manual download (Level 2.5) is safer and sufficient for now.
