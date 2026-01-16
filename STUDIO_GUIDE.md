# Studio Deployment Guide

This guide covers deploying Action Library in a multi-artist studio environment with shared storage, custom configurations, and pipeline integration.

> **⚠️ Upgrading from v1.2 or earlier?**
>
> Version 1.3 has a new database format that is **not backwards compatible**. All workstations must migrate:
>
> 1. Have artists apply their animations to Blender and save as .blend files
> 2. Deploy v1.3 with a fresh shared storage folder
> 3. Re-capture animations from Blender into the new library
>
> See the [Changelog](CHANGELOG.md) for details.

> For solo artists, the default setup works out of the box. This guide is for teams needing shared infrastructure.

---

## Network Storage Setup

### Shared Library Location
Action Library stores animations in a single directory structure. For team access:

- **NAS/Server Path**: Point all workstations to a shared network path (e.g., `//server/animation_library/`)
- **Permissions**: All artists need read/write access to the library folder
- **Database**: The SQLite database (`.meta/database.db`) lives inside the library folder—concurrent writes from multiple users are supported via WAL mode, but for large teams (10+), consider periodic syncs rather than live shared access

### Recommended Folder Structure
```
/server/animation_library/
├── library/                    # Hot storage - latest versions
│   └── walk_cycle/             # Human-readable folder name (base name)
│       ├── walk_cycle_v002.blend
│       ├── walk_cycle_v002.json
│       ├── walk_cycle_v002.webm
│       └── walk_cycle_v002.png
├── _versions/                  # Cold storage - old versions
│   └── walk_cycle/
│       └── v001/
│           └── walk_cycle_v001.*
├── .meta/                      # Database and config
│   └── database.db
├── .deleted/                   # Soft-deleted items
├── .trash/                     # Permanent delete staging
└── backups/                    # .animlib export archives
```

### Performance Considerations
- **Local SSD Cache**: For best playback performance, consider syncing previews locally
- **Network Speed**: 1Gbps minimum recommended; 10Gbps for smooth video preview playback
- **Latency**: Keep library on same LAN segment as workstations

---

## Studio Mode (v1.4)

Action Library supports two operational modes:

| Mode | Use Case | Features |
|------|----------|----------|
| **Solo Mode** | Individual artists | No restrictions, simple workflow, no login |
| **Studio Mode** | Multi-user teams | Role-based permissions, audit trail, soft delete |

### Enabling Studio Mode

1. Open **Settings → Studio Mode** tab
2. Select **Studio Mode (Multi-User)**
3. Select your user from the dropdown (or add users first)
4. Click **OK**

### Role Hierarchy

| Role | Level | Color | Typical Use |
|------|-------|-------|-------------|
| Artist | 1 | Gray | Animators, junior artists |
| Lead | 2 | Blue | Animation leads, team leads |
| Director | 2 | Orange | Creative directors |
| Supervisor | 3 | Purple | Department supervisors |
| Admin | 4 | Red | Pipeline TDs, IT |

### Review Notes Permissions

| Permission | Artist | Lead/Director | Supervisor | Admin |
|------------|--------|---------------|------------|-------|
| Add notes | ✓ | ✓ | ✓ | ✓ |
| Edit own notes | ✓ | ✓ | ✓ | ✓ |
| Delete own notes | — | ✓ | ✓ | ✓ |
| Delete any note | — | — | ✓ | ✓ |
| View deleted notes | — | ✓ | ✓ | ✓ |
| Restore deleted notes | — | — | ✓ | ✓ |
| Manage users | — | — | — | ✓ |

### Soft Delete & Restore

Notes are never permanently deleted:
- Deleted notes are marked with `deleted=1` in the database
- Original author and deletion info preserved
- Supervisors/Admins can restore via "Show Deleted" toggle
- Deleted notes appear with strikethrough styling

### Audit Trail

All note actions are logged to `note_audit_log` table:
- Created, edited, deleted, restored events
- Actor username and role
- Timestamp
- Change details (old/new values for edits)

Query audit history:
```python
import sqlite3
conn = sqlite3.connect('storage/.actionlibrary/notes.db')
cursor = conn.cursor()

# Get all actions on a note
cursor.execute('''
    SELECT action, actor, actor_role, timestamp, details
    FROM note_audit_log WHERE note_id = ?
    ORDER BY timestamp DESC
''', (note_id,))

# Get recent activity
cursor.execute('''
    SELECT * FROM note_audit_log
    ORDER BY timestamp DESC LIMIT 50
''')
```

### User Management

Admins can manage users via **Settings → Studio Mode → Manage Users**:
- Add new users with username, display name, role
- Edit user roles
- Deactivate/reactivate users

Users are stored in `studio_users` table in `notes.db`.

---

## Customizing Studio Mode for Your Pipeline

The built-in Studio Mode uses an **honor system**—users select their own identity. For production environments, studios typically extend this with real authentication.

### Option 1: OS Username Auto-Detection

Modify `studio_mode_tab.py` to auto-detect the logged-in user:

```python
import getpass

# Instead of dropdown selection:
current_user = getpass.getuser().lower()  # Returns "john.smith"

# Look up in database
user = self._notes_db.get_user(current_user)
if user:
    # User exists, use their role
    role = user['role']
else:
    # Unknown user, default to artist
    role = 'artist'
```

### Option 2: Lock Settings UI

Hide the Studio Mode tab for non-admins:

```python
# In settings_dialog.py
def _create_ui(self):
    # ... existing code ...

    # Only show Studio Mode tab to admins
    from ..services.notes_database import get_notes_database
    from ..services.permissions import NotePermissions

    notes_db = get_notes_database()
    current_user = getpass.getuser().lower()
    user = notes_db.get_user(current_user)
    role = user.get('role', 'artist') if user else 'artist'

    if NotePermissions.can_manage_users(True, role):
        self.studio_mode_tab = StudioModeTab(self.theme_manager, self)
        self.tab_widget.addTab(self.studio_mode_tab, "Studio Mode")
```

### Option 3: Config File Deployment

Pre-configure machines via config file that IT deploys:

```json
// studio_config.json (deployed by IT)
{
    "mode": "studio",
    "user": "john.smith",
    "role": "artist",
    "locked": true
}
```

```python
# Load at startup, override database settings
import json
config_path = Path('/studio/config/studio_config.json')
if config_path.exists():
    config = json.loads(config_path.read_text())
    if config.get('locked'):
        # Use config values, disable settings UI
        pass
```

### Option 4: LDAP/Active Directory Integration

For enterprise environments, query AD for user info:

```python
import ldap3

def get_user_from_ad(username):
    server = ldap3.Server('ldap://your-domain-controller')
    conn = ldap3.Connection(server, user='service_account', password='...')
    conn.bind()

    conn.search(
        'dc=studio,dc=com',
        f'(sAMAccountName={username})',
        attributes=['cn', 'memberOf']
    )

    if conn.entries:
        entry = conn.entries[0]
        groups = entry.memberOf.values

        # Map AD groups to roles
        if 'CN=Animation_Supervisors' in groups:
            return {'display_name': str(entry.cn), 'role': 'supervisor'}
        elif 'CN=Animation_Leads' in groups:
            return {'display_name': str(entry.cn), 'role': 'lead'}
        else:
            return {'display_name': str(entry.cn), 'role': 'artist'}

    return None
```

### Option 5: Central Database

For larger studios, replace SQLite with PostgreSQL/MySQL:

1. Modify `notes_database.py` to use your database driver
2. Point all workstations to central server
3. User management syncs automatically

### Database Schema Reference

**notes.db tables:**

```sql
-- User accounts
CREATE TABLE studio_users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT DEFAULT 'artist',  -- artist, lead, director, supervisor, admin
    created_at TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

-- App settings
CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
-- Keys: 'app_mode' (solo/studio), 'current_user', 'show_deleted_notes'

-- Audit log
CREATE TABLE note_audit_log (
    id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL,
    action TEXT NOT NULL,  -- created, edited, deleted, restored
    actor TEXT NOT NULL,
    actor_role TEXT,
    timestamp TIMESTAMP,
    details TEXT  -- JSON with change details
);
```

---

## Multi-User Workflows

### Concurrent Access
- Multiple artists can browse and apply animations simultaneously
- Capturing new animations writes to unique UUID folders (no conflicts)
- Folder organization changes sync on next app refresh

### Asset Permissions Model
| Role | Browse | Apply | Capture | Delete | Manage Folders |
|------|--------|-------|---------|--------|----------------|
| Artist | ✓ | ✓ | ✓ | — | — |
| Lead | ✓ | ✓ | ✓ | ✓ | ✓ |
| Admin | ✓ | ✓ | ✓ | ✓ | ✓ |

*Note: Asset permissions use filesystem/NAS access control. Review note permissions are enforced by Studio Mode.*

---

## Pose Library (v1.2)

Action Library now supports **poses** alongside actions. Poses are single-frame bone snapshots designed as quick building blocks for animation.

### Poses vs Actions

| Feature | Actions | Poses |
|---------|---------|-------|
| Frame count | Multi-frame | Single frame |
| Versioning | Full lineage system | None (simple) |
| Lifecycle status | WIP, Approved, etc. | None |
| Use case | Complete animations | Building blocks |
| Workflow | Iterate and refine | Create, use, discard |

### Studio Pose Workflow

Poses are intentionally **lightweight**:
- Capture a pose in seconds
- Apply instantly to any armature
- Auto-keyframe when Blender's auto-key is enabled
- No approval workflow overhead—if it works, keep it; if not, delete it

### Folder Organization

The virtual folder structure separates poses from actions:
- **Home** - All items (actions + poses)
- **Actions** - Only actions
- **Poses** - Only poses
- **Recent** / **Favorites** - Both types

This allows teams to maintain separate pose libraries (e.g., facial expressions, hand poses) without cluttering the action view.

### Instant Application

Actions and poses now apply via real-time TCP socket connection:
- No file-based polling delays
- Poses appear instantly on the armature
- Fallback to file queue if socket unavailable

### Pose Blending

Blend between poses directly in the desktop app:
- **Right-click hold + drag** on any pose card to blend from current pose to target
- **Drag right** to increase blend amount (0-100%)
- **Hold Ctrl** while dragging to mirror the pose
- **Left-click** to cancel and restore original pose
- **Release** right-click to apply the blended result

This enables rapid pose exploration without leaving the library interface.

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

## Studio Naming Engine (v1.3)

The Studio Naming Engine provides template-based naming for animations—essential for studios with established naming conventions.

### Overview

Instead of free-form naming, animations are named using a **template** with placeholders:

```
{show}_{asset}_{task}_v{version:03}  →  MYPROJ_hero_walk_v001
```

Key principles:
- **Version is immutable** - Once assigned, version numbers cannot be changed
- **Fields are editable** - Change `hero` to `villain`, keep version
- **Template stored with animation** - Each animation remembers its template for renaming

### Configuration in Blender

Configure the naming engine in **Blender Preferences → Add-ons → Animation Library → Studio Naming**:

1. **Enable Studio Mode** - Toggle on to activate template naming
2. **Naming Template** - Define your pattern:
   - `{show}_{shot}_{asset}_v{version:03}` → `PROJ_0100_hero_v001`
   - `{asset}_{task}_v{version:04}` → `hero_walk_v0001`
   - `{seq}_{shot}_{variant}_v{version:03}` → `010_0020_A_v001`

3. **Context Mode** - How to auto-fill fields:
   - **Manual** - Enter all fields by hand in the capture panel
   - **Scene Name** - Extract from Blender's scene name via regex
   - **Folder Path** - Extract from .blend file path via regex

### Context Extraction Examples

**Scene Name Mode:**
```
Scene name: MYPROJ_ep01_0100
Pattern:    (?P<show>\w+)_(?P<seq>\w+)_(?P<shot>\w+)
Extracts:   show=MYPROJ, seq=ep01, shot=0100
```

**Folder Path Mode:**
```
File path: /projects/MYPROJ/episodes/ep01/shots/0100/anim/hero_walk.blend
Pattern:   /(?P<show>\w+)/episodes/(?P<seq>\w+)/shots/(?P<shot>\w+)/
Extracts:  show=MYPROJ, seq=ep01, shot=0100
```

### Capture Workflow

When capturing with Studio Mode enabled:

1. Open capture panel in Blender
2. Enable "Studio Naming" checkbox
3. Fill in required fields (or let context extraction fill them)
4. See live preview of generated name
5. Click "Capture Action"

Animation is saved with:
- Generated name (`MYPROJ_hero_v001`)
- `naming_fields` JSON (`{"show":"MYPROJ","asset":"hero"}`)
- `naming_template` string

### Renaming in Desktop App

Click **Rename** button in metadata panel:

- **With naming fields**: Shows field-based editor with read-only version
  ```
  Show:    [MYPROJ    ]
  Asset:   [hero      ]
  Version: v001 (read-only)
  Preview: MYPROJ_hero_v001
  ```

- **Without naming fields**: Shows simplified editor
  ```
  Base Name: [hero_walk]
  Version:   v001 (read-only)
  Preview:   hero_walk_v001
  ```

### Renaming Across Lineage

When renaming, you can apply to:
- **Single version** - Only this animation changes
- **All versions in lineage** - All versions get new fields, each keeps its own version number

Example:
```
Before:                    After (rename to NEWPROJ):
MYPROJ_hero_v001          NEWPROJ_hero_v001
MYPROJ_hero_v002     →    NEWPROJ_hero_v002
MYPROJ_hero_v003          NEWPROJ_hero_v003
```

### Pipeline Integration

Query animations by naming fields:
```python
import json
cursor.execute('SELECT uuid, name, naming_fields FROM animations WHERE naming_template IS NOT NULL')
for row in cursor.fetchall():
    fields = json.loads(row['naming_fields'])
    if fields.get('show') == 'MYPROJ':
        print(f"Found: {row['name']}")
```

---

## Version Comparison (v1.3)

Compare animation versions side-by-side in the Lineage dialog.

### How to Compare

1. Open **View Lineage** from metadata panel
2. Click **Compare** button
3. Select exactly 2 versions (click rows to select)
4. Click **Compare Selected**

### Comparison Features

- **Side-by-side layout** - Both versions visible at once
- **Synchronized playback** - Play/pause affects both videos
- **Shared progress slider** - Scrub both videos to same frame
- **Exit compare** - Return to normal lineage view

### Use Cases

- Compare before/after a director's note
- Review animation changes between iterations
- Quality check before promoting a version to latest

---

## Version Notes (v1.3)

Add notes to versions for documentation and review tracking.

### Adding Notes

1. Open **View Lineage** from metadata panel
2. Select a version
3. Type in the **Notes** field below the preview
4. Click **Save Notes**

### Note Ideas

- Document what changed in this version
- Record director feedback
- Note approval status or blockers
- Reference related shots or dependencies

Notes are stored in the animation's `description` field and persist with the animation metadata.

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
