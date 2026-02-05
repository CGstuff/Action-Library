<p align="center">
  <img src="assets/Icon.png" alt="Action Library" width="128" height="128">
</p>

<h1 align="center">Action Library</h1>

<p align="center">
  <strong>A production-grade animation & pose library manager for Blender</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg" alt="License: GPL-3.0"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
  <a href="https://pypi.org/project/PyQt6/"><img src="https://img.shields.io/badge/PyQt-6.5+-green.svg" alt="PyQt6"></a>
  <a href="https://www.blender.org/"><img src="https://img.shields.io/badge/Blender-4.5--5.0+-orange.svg" alt="Blender 4.5-5.0+"></a>
</p>

<p align="center">
  <img src="media/Hero.gif" alt="Action Library — browse, organize, and apply animations" width="100%">
</p>

---

Built after completing a 55-minute 3D animated feature film as a solo technical director. During production, I kept hitting the same limitations in Blender — managing animation data at scale, reusing clips across scenes, tracking iterations, and reviewing work. Action Library is the tool I wish I'd had from day one.

Open-sourced so others working on serious Blender projects can build on the same foundation.

---

## Apply Animations Instantly

Double-click any animation card to apply it to your rig in Blender — no file menus, no importing. The desktop app talks to Blender over a real-time socket connection, so it's immediate.

- **Ctrl + Double-click** to apply mirrored
- **Shift + Double-click** to apply as action slot
- **Alt + Double-click** to insert at playhead

<p align="center">
  <img src="media/Apply.gif" alt="Apply animations to Blender with a double-click" width="100%">
</p>

---

## Pose Blending

Right-click and drag on any pose to blend between your current pose and the library pose in real-time. Hold **Ctrl** while dragging to mirror. Release to apply, **Escape** to cancel.

<p align="center">
  <img src="media/blending.gif" alt="Real-time pose blending" width="100%">
</p>

---

## Capture from Blender

Capture actions and poses directly from the Blender sidebar. Supports selective frame ranges, selected bones only, and auto-detection of rig types (Rigify, Mixamo, Auto-Rig Pro, Epic Skeleton, custom).

<p align="center">
  <img src="media/capture.gif" alt="Capture animations from Blender" width="100%">
</p>

---

## Version Comparison & Review

Track iterations with the lineage system (v001 → v002 → v003). Compare any two versions side by side with synchronized playback. Add timestamped review notes and draw annotations directly on frames.

<p align="center">
  <img src="media/compare.gif" alt="Side-by-side version comparison" width="100%">
</p>

---

## Drawover Annotations

Draw directly on video frames during review — pen, line, arrow, shapes. Annotations are saved per-frame, support ghosting across adjacent frames, and can be exported as MP4 for sharing feedback.

<p align="center">
  <img src="media/anotate.gif" alt="Drawover annotations for review" width="100%">
</p>

---

## Themes

Four built-in themes plus a full custom theme editor with 40+ color options and live preview.

<p align="center">
  <img src="media/themes.gif" alt="Theme options" width="100%">
</p>

---

## Features

| Category | Details |
|----------|---------|
| **Library** | Actions & poses, folders, tags, favorites, search, filtering, grid/list views |
| **Apply** | Real-time socket bridge to Blender, mirror, reverse, selected bones, action slots |
| **Pose Blending** | Right-click drag blending with mirror support |
| **Versioning** | Lineage system with cold storage, immutable version numbers |
| **Review** | Version comparison, timestamped notes, drawover annotations, MP4 export |
| **Capture** | Full action, frame range, selected bones, auto rig detection |
| **Pipeline** | Studio naming templates, lifecycle status (WIP → Review → Approved), multi-user storage |
| **UI** | 4 themes + custom editor, keyboard shortcuts (J/K/L playback), resizable panels |
| **Performance** | Handles 1000+ animations, async thumbnail loading, SQLite + WAL, virtual scrolling |

---

## Installation

### Option 1: Download Release (Recommended)

Download the latest portable release from the [Releases](../../releases) page. Unzip and run — no installation required.

> **Note:** Windows may show an "Unknown publisher" warning on first run. Click **More info** → **Run anyway**. This is normal for unsigned open source software.

### Option 2: Run from Source

```bash
git clone https://github.com/CGstuff/action-library.git
cd action-library
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
python run.py
```

---

## Quick Start

1. **Launch** Action Library
2. **Settings → Blender Integration** — browse to your `blender.exe` and click **Verify**
3. **Install Addon** — click the button, then restart Blender
4. **Enable** the addon in Blender: Edit → Preferences → Add-ons → search "Action Library"
5. **Set the library path** in addon preferences to match the desktop app's storage location
6. **Capture** — select an armature in Blender, open the N-panel → Animation Library tab, click **Capture Action**
7. **Apply** — double-click any card in the desktop app to load it into Blender

For the full walkthrough, see [Getting Started](GETTING_STARTED.md).

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](GETTING_STARTED.md) | First-time setup, addon installation, first capture |
| [Studio Guide](STUDIO_GUIDE.md) | Multi-user deployment, shared storage, pipeline integration |
| [Architecture](ARCHITECTURE.md) | System design, patterns, and performance |
| [Developer Guide](DEVELOPER_GUIDE.md) | Development setup and contribution guidelines |
| [Changelog](CHANGELOG.md) | Version history |

---

## Architecture

Built with **PyQt6** and a Model/View architecture. Key design choices:

- **Event Bus** — decoupled component communication
- **Thread Pool** — async thumbnail loading, background operations
- **SQLite + WAL** — concurrent database access with write-ahead logging
- **Socket Bridge** — real-time TCP connection to Blender (fallback to file-based queue)
- **Virtual Scrolling** — renders only visible items, tested with 4000+ animations

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).

> Earlier versions (≤ 1.4) were published under GPL while using PyQt (GPL/commercial). As of v1.4.1, the license is explicitly GPL-3.0 for full compatibility. No retroactive relicensing implied.
