# Timestamp Review Notes System Design

## Overview

A Loom/SyncSketch-style review system for frame-specific notes on animation versions.

## Architecture Principles

1. **Separate Database** - Notes live in `notes.db`, not the main database
   - Assets & versions remain immutable
   - Notes are conversational and change frequently
   - Easy cleanup of orphaned notes
   - Studio-safe: notes can be synced separately

2. **Inline UI** - No popup windows, everything inline
   - Notes panel below video preview
   - Click to expand/collapse
   - Single expanded note at a time

3. **Version-Scoped** - Each version has its own review session
   - Notes don't carry between versions
   - Clear separation for dailies workflow

---

## Database Schema (notes.db)

```sql
-- Review sessions link notes to specific animation versions
CREATE TABLE review_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animation_uuid TEXT NOT NULL,
    version_label TEXT NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP,
    status TEXT DEFAULT 'active'  -- 'active', 'archived'
);

CREATE INDEX idx_sessions_uuid ON review_sessions(animation_uuid);

-- Individual review notes
CREATE TABLE review_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    frame INTEGER NOT NULL,
    note TEXT NOT NULL,
    author TEXT DEFAULT '',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMP,
    resolved INTEGER DEFAULT 0,
    resolved_by TEXT,
    resolved_date TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES review_sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_notes_session ON review_notes(session_id);
CREATE INDEX idx_notes_frame ON review_notes(frame);
```

---

## UI Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Animation Lineage                                                │
├──────────────────────────────────────────────────────────────────┤
│ ┌──────────────────┐  ┌────────────────────────────────────────┐ │
│ │ Version Table    │  │ v001 | Latest | WIP                    │ │
│ │                  │  │                                         │ │
│ │ v002 | Final     │  │ ┌─────────────────────────────────────┐ │ │
│ │ v001 | WIP  ←    │  │ │        VIDEO PREVIEW                │ │ │
│ │                  │  │ │                                     │ │ │
│ │                  │  │ └─────────────────────────────────────┘ │ │
│ │                  │  │                                         │ │
│ │                  │  │  ▶ ═●═══●═════●════════════  Frame: 61  │ │
│ │                  │  │      ↑   ↑     ↑ timeline markers       │ │
│ │                  │  │                                         │ │
│ │                  │  │ ┌─────────────────────────────────────┐ │ │
│ │                  │  │ │ REVIEW NOTES (2 open)          [+]  │ │ │
│ │                  │  │ ├─────────────────────────────────────┤ │ │
│ │                  │  │ │ ● f61   test note here...           │ │ │
│ │                  │  │ │        ─────────────────────────    │ │ │
│ │                  │  │ │        Full note text expanded      │ │ │
│ │                  │  │ │        [Resolve] [Edit] [Delete]    │ │ │
│ │                  │  │ ├─────────────────────────────────────┤ │ │
│ │                  │  │ │ ○ f134  another note...             │ │ │
│ │                  │  │ └─────────────────────────────────────┘ │ │
│ └──────────────────┘  └────────────────────────────────────────┘ │
│                                                                  │
│ [Set as Latest]  [Apply This Version]  [Compare]        [Close]  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Interaction Model

### Timeline Markers
- Orange dot = unresolved note
- Green dot (dimmed) = resolved note
- Click marker → seek video + expand note in panel

### Notes Panel
- Scrollable list of notes sorted by frame
- Click timestamp → seek video
- Click row → expand/collapse (toggle)
- Only one note expanded at a time
- Expanded state shows: full text, Resolve/Edit/Delete buttons

### Add Note
- Click [+] button
- Creates note at current frame
- Inline text input (no dialog)
- Press Enter to save, Escape to cancel

---

## Data Model

```python
@dataclass
class ReviewSession:
    id: int
    animation_uuid: str
    version_label: str
    created_date: datetime
    last_activity: datetime
    status: str  # 'active', 'archived'

@dataclass
class ReviewNote:
    id: int
    session_id: int
    frame: int
    note: str
    author: str
    created_date: datetime
    modified_date: Optional[datetime]
    resolved: bool
    resolved_by: Optional[str]
    resolved_date: Optional[datetime]
```

---

## Version Binding Logic

1. When user selects a version in the dialog:
   - Look up session by (animation_uuid, version_label)
   - If no session exists, create one on first note
   - Load notes for that session

2. Notes are tied to version_label (v001, v002), not animation_uuid alone
   - Each version gets its own review session
   - Clear separation for dailies workflow

---

## Cleanup Workflow

### Automatic Cleanup
- On app startup, check for orphaned sessions:
  - Session's animation_uuid no longer exists in main DB
  - Mark as 'archived' after 30 days of no activity

### Manual Cleanup
- "Clean Old Notes" button in settings
- Archives sessions older than X days
- Option to permanently delete archived sessions

### Cleanup SQL
```sql
-- Find orphaned sessions (animation deleted)
SELECT s.* FROM review_sessions s
WHERE NOT EXISTS (
    SELECT 1 FROM animations a WHERE a.uuid = s.animation_uuid
);

-- Archive inactive sessions
UPDATE review_sessions
SET status = 'archived'
WHERE last_activity < datetime('now', '-30 days')
AND status = 'active';
```

---

## File Structure

```
animation_library/
├── services/
│   └── notes_database.py      # NEW: Separate notes DB service
├── widgets/
│   ├── review_notes_panel.py  # NEW: Inline notes panel
│   ├── note_list_item.py      # NEW: Single note row widget
│   └── timeline_markers.py    # KEEP: Timeline overlay
└── data/
    └── notes.db               # NEW: Separate database file
```

---

## Implementation Order

1. Create `notes_database.py` with NotesDatabase class
2. Create `note_list_item.py` - collapsible inline note widget
3. Create `review_notes_panel.py` - scrollable notes list
4. Update `version_history_dialog.py` - integrate panel
5. Update `timeline_markers.py` - fix interactions
6. Add cleanup logic to app startup
