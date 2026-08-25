# Studio Mode & Note Permissions Design

## Overview

Two operational modes for the Animation Library:
- **Solo Mode**: Single user, unrestricted access, simple workflow
- **Studio Mode**: Multi-user, role-based permissions, audit trail, soft delete

---

## Database Schema Changes

### 1. Modified `review_notes` table

```sql
-- Add soft delete and authorship fields
ALTER TABLE review_notes ADD COLUMN author TEXT DEFAULT '';
ALTER TABLE review_notes ADD COLUMN author_role TEXT DEFAULT 'artist';
ALTER TABLE review_notes ADD COLUMN deleted INTEGER DEFAULT 0;
ALTER TABLE review_notes ADD COLUMN deleted_by TEXT;
ALTER TABLE review_notes ADD COLUMN deleted_at TIMESTAMP;
```

### 2. New `note_audit_log` table

```sql
CREATE TABLE note_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    action TEXT NOT NULL,  -- 'created', 'edited', 'deleted', 'restored'
    actor TEXT NOT NULL,
    actor_role TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT,  -- JSON: {"field": "note", "old": "...", "new": "..."}
    FOREIGN KEY (note_id) REFERENCES review_notes(id) ON DELETE CASCADE
);

CREATE INDEX idx_audit_note ON note_audit_log(note_id);
CREATE INDEX idx_audit_timestamp ON note_audit_log(timestamp);
```

### 3. New `studio_users` table

```sql
CREATE TABLE studio_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT DEFAULT 'artist',  -- artist, lead, director, supervisor, admin
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

-- Default admin user
INSERT INTO studio_users (username, display_name, role)
VALUES ('admin', 'Administrator', 'admin');
```

### 4. New `app_settings` table

```sql
CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Default settings
INSERT INTO app_settings (key, value) VALUES ('app_mode', 'solo');
INSERT INTO app_settings (key, value) VALUES ('current_user', '');
INSERT INTO app_settings (key, value) VALUES ('show_deleted_notes', 'false');
```

---

## Role Hierarchy

| Role       | Level | Can Add | Can Edit Own | Can Delete Own | Can Delete Any | Can Restore | See Deleted |
|------------|-------|---------|--------------|----------------|----------------|-------------|-------------|
| Artist     | 1     | Yes     | Yes          | No             | No             | No          | No          |
| Lead       | 2     | Yes     | Yes          | Yes            | No             | No          | Yes         |
| Director   | 2     | Yes     | Yes          | Yes            | No             | No          | Yes         |
| Supervisor | 3     | Yes     | Yes          | Yes            | Yes            | Yes         | Yes         |
| Admin      | 4     | Yes     | Yes          | Yes            | Yes            | Yes         | Yes         |

---

## Permission Logic

```python
class NotePermissions:
    ROLE_LEVELS = {
        'artist': 1,
        'lead': 2,
        'director': 2,
        'supervisor': 3,
        'admin': 4
    }

    @staticmethod
    def can_edit_note(user_role: str, note_author: str, current_user: str) -> bool:
        """Users can only edit their own notes."""
        return note_author == current_user

    @staticmethod
    def can_delete_note(user_role: str, note_author: str, current_user: str) -> bool:
        """
        - Artists: Cannot delete any notes
        - Leads/Directors: Can delete their own notes only
        - Supervisors/Admins: Can delete any note
        """
        level = NotePermissions.ROLE_LEVELS.get(user_role, 1)

        if level >= 3:  # Supervisor/Admin
            return True
        if level >= 2:  # Lead/Director
            return note_author == current_user
        return False  # Artist

    @staticmethod
    def can_restore_note(user_role: str) -> bool:
        """Only Supervisors and Admins can restore deleted notes."""
        return NotePermissions.ROLE_LEVELS.get(user_role, 1) >= 3

    @staticmethod
    def can_view_deleted(user_role: str) -> bool:
        """Leads and above can view deleted notes."""
        return NotePermissions.ROLE_LEVELS.get(user_role, 1) >= 2
```

---

## Mode Behavior

### Solo Mode
- No login required
- All permissions enabled (unrestricted)
- Soft delete still used (for undo/recovery)
- Simple "Undo Delete" option
- No audit logging
- No role badges on notes

### Studio Mode
- User selection required at startup
- Permissions enforced based on role
- Full audit trail
- Deleted notes hidden by default
- "Show Deleted" toggle for authorized users
- Role badges displayed on notes
- Author attribution on all notes

---

## UI Components

### Settings Dialog - Mode Section

```
┌─────────────────────────────────────────┐
│ Application Mode                        │
├─────────────────────────────────────────┤
│ ○ Solo Mode (Single User)               │
│   - No restrictions                     │
│   - Simple workflow                     │
│                                         │
│ ● Studio Mode (Multi-User)              │
│   - Role-based permissions              │
│   - Audit trail                         │
│   - Soft delete with restore            │
│                                         │
│ Current User: [Dropdown ▼]              │
│ Role: Lead                              │
│                                         │
│ [Manage Users...]                       │
└─────────────────────────────────────────┘
```

### User Management Dialog (Studio Mode)

```
┌─────────────────────────────────────────────────┐
│ User Management                            [X]  │
├─────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────┐ │
│ │ Username    │ Display Name │ Role     │ Act │ │
│ ├─────────────┼──────────────┼──────────┼─────┤ │
│ │ admin       │ Administrator│ Admin    │ ✓   │ │
│ │ john.smith  │ John Smith   │ Director │ ✓   │ │
│ │ jane.doe    │ Jane Doe     │ Lead     │ ✓   │ │
│ │ bob.artist  │ Bob Artist   │ Artist   │ ✓   │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ [Add User]  [Edit]  [Deactivate]       [Close]  │
└─────────────────────────────────────────────────┘
```

### Note Item with Role Info (Studio Mode)

```
┌─────────────────────────────────────────────────┐
│ [f125] [✓] [LEAD] John Smith           [🗑]     │
│ Fix the arc on the arm, timing is off          │
└─────────────────────────────────────────────────┘

# If deleted (visible to authorized users):
┌─────────────────────────────────────────────────┐
│ [f125] [DELETED] Originally by: Jane Doe       │
│ ░░ Old note content (strikethrough) ░░         │
│ Deleted by: admin on 2024-01-15 10:30          │
│                                    [Restore]    │
└─────────────────────────────────────────────────┘
```

### Review Notes Panel Header (Studio Mode)

```
┌─────────────────────────────────────────────────┐
│ Review Notes (3 open)        [☐ Show Deleted]   │
│ [Add note at current frame...           ] [+]   │
└─────────────────────────────────────────────────┘
```

---

## Soft Delete Workflow

### Delete Action
1. User clicks delete on a note
2. System checks permissions
3. If allowed:
   - Set `deleted = 1`
   - Set `deleted_by = current_user`
   - Set `deleted_at = NOW()`
   - Log to `note_audit_log`
4. Note disappears from default view
5. Show toast: "Note deleted. [Undo]"

### Restore Action
1. User enables "Show Deleted" toggle
2. Deleted notes appear with visual indicator
3. User clicks "Restore" on deleted note
4. System checks permissions (supervisor+)
5. If allowed:
   - Set `deleted = 0`
   - Clear `deleted_by`, `deleted_at`
   - Log to `note_audit_log`
6. Note reappears in normal view

---

## Audit Log Usage

### Log Entries Created For:
- Note created
- Note edited (with old/new values)
- Note deleted (with reason if provided)
- Note restored
- Note resolved/unresolved

### Audit Query Examples:
```sql
-- Get all actions on a specific note
SELECT * FROM note_audit_log WHERE note_id = ? ORDER BY timestamp;

-- Get all deletes by a user
SELECT * FROM note_audit_log WHERE action = 'deleted' AND actor = ?;

-- Get activity in last 24 hours
SELECT * FROM note_audit_log
WHERE timestamp > datetime('now', '-1 day')
ORDER BY timestamp DESC;
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `services/permissions.py` | CREATE | Permission checking logic |
| `services/user_service.py` | CREATE | User management (CRUD) |
| `services/notes_database.py` | MODIFY | Add soft delete, audit, schema v2 |
| `config.py` | MODIFY | Add mode settings |
| `widgets/dialogs/version_history_dialog.py` | MODIFY | Permission-aware UI |
| `widgets/dialogs/user_management_dialog.py` | CREATE | User CRUD dialog |
| `widgets/settings/settings_dialog.py` | MODIFY | Mode switcher section |

---

## Migration Strategy

### Schema Version 2 Migration:
1. Add new columns to `review_notes`
2. Create `note_audit_log` table
3. Create `studio_users` table
4. Create `app_settings` table
5. Set default values

### Data Migration:
- Existing notes get `author = ''` (unknown in solo mode)
- No audit history for existing notes
- Default mode = 'solo' (non-breaking)

---

## Safety Rules

1. **No Hard Delete**: Notes are never permanently deleted from database
2. **Audit Everything**: Every modification in studio mode is logged
3. **Permission Check First**: Always validate permissions before action
4. **Graceful Degradation**: If user service fails, fall back to solo mode
5. **Confirmation Required**: Delete actions require confirmation dialog
6. **Undo Window**: 5-second undo toast after delete

---

## Future Enhancements (Out of Scope)

- LDAP/Active Directory integration
- Note locking (prevent edits during review)
- Comment threads/replies
- @mentions with notifications
- Export audit log to CSV/PDF
- Note templates
- Bulk operations with approval workflow
