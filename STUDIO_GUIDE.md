# Studio Deployment Guide

This guide covers deploying Action Library in a multi-artist studio environment with shared storage, custom configurations, and pipeline integration.

> For solo artists, the default setup works out of the box. This guide is for teams needing shared infrastructure.

---

## Network Storage Setup

### Shared Library Location
Action Library stores animations in a single directory structure. For team access:

- **NAS/Server Path**: Point all workstations to a shared network path (e.g., `//server/animation_library/`)
- **Permissions**: All artists need read/write access to the library folder
- **Database**: The SQLite database (`.actionlibrary/database.db`) lives inside the library folder—concurrent writes from multiple users are supported via WAL mode, but for large teams (10+), consider periodic syncs rather than live shared access

### Recommended Folder Structure
```
/server/animation_library/
├── library/                    # Animation files (.blend, .json, thumbnails)
│   ├── {uuid}/
│   │   ├── animation.blend
│   │   ├── metadata.json
│   │   ├── preview.webm
│   │   └── thumbnail.png
├── .actionlibrary/
│   └── database.db             # SQLite database
└── backups/                    # .animlib export archives
```

### Performance Considerations
- **Local SSD Cache**: For best playback performance, consider syncing previews locally
- **Network Speed**: 1Gbps minimum recommended; 10Gbps for smooth video preview playback
- **Latency**: Keep library on same LAN segment as workstations

---

## Multi-User Workflows

### Concurrent Access
- Multiple artists can browse and apply animations simultaneously
- Capturing new animations writes to unique UUID folders (no conflicts)
- Folder organization changes sync on next app refresh

### Permissions Model
| Role | Browse | Apply | Capture | Delete | Manage Folders |
|------|--------|-------|---------|--------|----------------|
| Artist | ✓ | ✓ | ✓ | — | — |
| Lead | ✓ | ✓ | ✓ | ✓ | ✓ |
| Admin | ✓ | ✓ | ✓ | ✓ | ✓ |

*Note: Action Library doesn't enforce permissions—use filesystem/NAS permissions for access control.*

---

## Lineage System (Version Control)

Action Library includes a lineage system for tracking animation iterations—essential for studios where animations go through multiple revision cycles.

### How Lineage Works

1. **First Capture**: Animation is saved with version `v001` and a unique `version_group_id`
2. **Apply & Edit**: Artist applies animation from library, edits it in Blender
3. **Capture Again**: System detects the action came from the library and offers:
   - **Create New Version** → Saves as `v002` with same lineage (version_group_id)
   - **Create New Animation** → Saves as fresh `v001` with new lineage

### Cold Storage (Version Visibility)

- Only the **latest version** appears in the main library view
- Older versions are in "cold storage"—accessible via **View Lineage** in the metadata panel
- From the Lineage dialog, any version can be:
  - **Promoted to Latest** (swaps visibility)
  - **Applied** directly to Blender

### Studio Workflow Example

```
Walk_Cycle_v001  ← Lead captures initial animation
     ↓
Walk_Cycle_v002  ← Artist A iterates, captures revision
     ↓
Walk_Cycle_v003  ← Director feedback, Artist B makes changes
     ↓
[View Lineage]   ← Compare all versions, promote v002 if v003 was wrong direction
```

### Lineage in Database

Animations in the same lineage share a `version_group_id`. Pipeline tools can query:

```python
# Get all versions of an animation
cursor.execute('''
    SELECT uuid, name, version_label, is_latest, status
    FROM animations
    WHERE version_group_id = ?
    ORDER BY version DESC
''', (version_group_id,))
```

---

## Lifecycle Status System

Action Library supports pipeline status tracking for review/approval workflows.

### Available Statuses

| Status | Color | Use Case |
|--------|-------|----------|
| **None** | Gray (hidden on cards) | Default—for solo artists or animations not in review |
| **WIP** | Orange | Work in progress, not ready for review |
| **In Review** | Blue | Submitted for director/lead review |
| **Needs Work** | Red | Reviewed, requires changes |
| **Approved** | Green | Passed review, ready for use |
| **Final** | Purple | Locked, shipped/published version |

### Default Behavior

- New animations default to **None** status (no badge displayed)
- Solo artists can ignore the status system entirely—library works as simple asset browser
- Studios enable status workflow by setting animations to WIP/Review/etc.

### Setting Status

**In the App:**
- Select animation → Metadata Panel → Click status badge → Choose from dropdown

**Via Database (for pipeline tools):**
```python
cursor.execute('''
    UPDATE animations SET status = ?, modified_date = CURRENT_TIMESTAMP
    WHERE uuid = ?
''', ('review', animation_uuid))
```

### Status in Lineage

Each version in a lineage can have its own status:
```
Walk_Cycle_v001  [Approved]   ← Original approved version
Walk_Cycle_v002  [WIP]        ← New iteration in progress
Walk_Cycle_v003  [In Review]  ← Latest, awaiting feedback
```

### Pipeline Integration Examples

**Shotgrid/Flow Integration:**
```python
# Sync status from Shotgrid review
def on_shotgrid_status_change(entity_id, new_status):
    animation_uuid = lookup_animation_by_shotgrid_id(entity_id)
    status_map = {'rev': 'review', 'apr': 'approved', 'rtk': 'needs_work'}
    cursor.execute('UPDATE animations SET status = ? WHERE uuid = ?',
                   (status_map.get(new_status, 'wip'), animation_uuid))
```

**Batch Status Update:**
```python
# Mark all animations in a folder as approved
cursor.execute('''
    UPDATE animations SET status = 'approved'
    WHERE folder_id = ? AND status = 'review'
''', (folder_id,))
```

**Query by Status:**
```python
# Get all animations pending review
cursor.execute('''
    SELECT uuid, name, version_label FROM animations
    WHERE status = 'review' AND is_latest = 1
''')
```

---

## Customization for Studios

### Rig Type Configuration
Studios using custom rigs can extend rig detection in:
```
blender_plugin/utils/queue_client.py → detect_rig_type()
```

Add bone patterns for your studio rigs:
```python
STUDIO_RIG_PATTERNS = {
    'studio_biped': ['root', 'COG', 'spine_01', 'spine_02'],
    'studio_quadruped': ['root', 'COG', 'front_leg_L', 'back_leg_L'],
}
```

### Metadata Extensions
Add custom metadata fields for your pipeline in:
```
blender_plugin/operators/AL_capture_animation.py
```

Common studio additions:
- Project/show name
- Shot/sequence identifier
- Artist assignment

> **Note**: Approval status is now built-in via the [Lifecycle Status System](#lifecycle-status-system).

### Theme Customization
Create a studio-branded theme:
1. Export an existing theme from Settings → Appearance → Export Theme
2. Modify colors to match studio branding
3. Distribute the `.json` file to artists
4. Import via Settings → Appearance → Import Theme

---

## Pipeline Integration

### Automation / Batch Operations
The library structure is designed for scripting:

```python
# Example: Batch import animations from render farm output
import json
from pathlib import Path

library_path = Path("/server/animation_library/library")
for anim_folder in library_path.iterdir():
    metadata_file = anim_folder / "metadata.json"
    if metadata_file.exists():
        data = json.loads(metadata_file.read_text())
        # Process: validate, tag, move to folders, etc.
```

### Integration Points
- **Shotgrid/Flow**: Tag animations with shot IDs, query library via metadata
- **Deadline/Farm**: Post-render hooks can auto-capture approved animations
- **Review Tools**: Preview videos are standard WebM—compatible with RV, DJV, etc.

### Database Access
Direct SQLite access for pipeline tools:
```python
import sqlite3
db_path = "/server/animation_library/.actionlibrary/database.db"
conn = sqlite3.connect(db_path)
# Query animations, folders, tags, etc.
```

---

## Deployment Checklist

### Initial Setup
- [ ] Provision shared storage with adequate space (1GB per ~100 animations)
- [ ] Set filesystem permissions (read/write for artists, full for leads)
- [ ] Install Action Library on each workstation
- [ ] Configure library path to shared location on first run
- [ ] Install Blender addon on each workstation
- [ ] Configure addon to point to same shared library path

### Ongoing Maintenance
- [ ] Schedule regular `.animlib` backups (Settings → Backup → Export)
- [ ] Monitor disk usage—thumbnails and previews add up
- [ ] Periodically vacuum SQLite database if performance degrades
- [ ] Document studio-specific rig types and naming conventions

---

## Troubleshooting

### "Database is locked" errors
- Cause: Multiple users writing simultaneously
- Fix: Ensure WAL mode is enabled (default), or stagger capture operations

### Slow thumbnail loading
- Cause: Network latency to storage
- Fix: Check network path, consider local preview cache

### Missing animations after capture
- Cause: Permission issues on write
- Fix: Verify artist has write access to library folder

---

## Support

- [GitHub Issues](https://github.com/CGstuff/action-library/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/CGstuff/action-library/discussions) - Questions and community support
