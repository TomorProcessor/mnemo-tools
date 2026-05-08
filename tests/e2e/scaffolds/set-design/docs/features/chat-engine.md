# Chat Engine (F02, F03)

The left panel of set-design — message list, composer, image attachments, activity feed inside assistant turns. The visible UX of the chat → claude loop.

## Overview

The chat is a JSONL log on disk plus a streaming UI. There is no database; the JSONL IS the source of truth. The Frame reads it via `chat.history` and stays live via `event.activity` / `event.turn.*` pushes.

A target dir may have many chats over time. Only one is "active" at a time (set in `config.active_chat_id`). Switching active chat is rare in V1 (no multi-chat UI prominence) — primarily exposed via a "+ New chat" action and a dropdown listing recent.

## JSONL event model

Each line in `<target>/.set-design/chats/<chat_id>.jsonl` is one of:

```jsonc
// Message
{ "kind": "message", "id": "01H...", "role": "user", "content": "Add a hero with CTA", "attachment_ids": [], "created_at": "..." }

// Turn lifecycle (one row per state transition)
{ "kind": "turn", "id": "01H...", "prompt_message_id": "01H...", "state": "PENDING", "model": "opus", "started_at": "..." }
{ "kind": "turn", "id": "01H...", "state": "RUNNING", "started_at": "...", "session_id": "..." }
{ "kind": "turn", "id": "01H...", "state": "COMPLETED", "completed_at": "...", "commit_sha": "abc123", "files_changed": ["app/page.tsx"], "cost_usd": 0.034, "duration_ms": 12300 }

// Activity (one row per stream-json event)
{ "kind": "activity", "turn_id": "01H...", "seq": 1, "event": "tool_use_start", "tool_name": "Read", "tool_input": {"file_path": "app/page.tsx"}, "at": "..." }
{ "kind": "activity", "turn_id": "01H...", "seq": 2, "event": "tool_use_end", "tool_name": "Read", "tool_result": "(truncated)", "at": "..." }
{ "kind": "activity", "turn_id": "01H...", "seq": 3, "event": "text_delta", "delta": "I'll add a hero...", "at": "..." }

// Error (out-of-band; usually accompanies a FAILED turn)
{ "kind": "error", "turn_id": "01H...", "code": "CLAUDE_SUBPROCESS_CRASHED", "message": "exit 139", "at": "..." }
```

**Append-only invariant:** lines are never edited or deleted. To "edit" a Message, the user sends a new Message; the old one is kept in history. The UI may de-emphasize older versions visually, but the log is the truth.

**Coalescing for display** (Frame-side):
- Consecutive `tool_use_start`+`tool_use_end` pairs of `Read`/`Glob`/`Grep` from the same turn render as one collapsed row "Read 8 files / Searched 3 patterns" (expandable).
- `Edit`/`Write`/`Bash` always render as their own row with status pill.
- `text_delta` events accumulate into an inline streaming text region.

## Composer (input bar)

```
┌──────────────────────────────────────────────────────────────┐
│ [📎] [textarea — Cmd+Enter to send] ........... [Send →]   │
│ ┌─────┐ ┌─────┐                                             │
│ │ img │ │ img │ ← attachment thumbnails (preview before send) │
│ └─────┘ └─────┘                                             │
└──────────────────────────────────────────────────────────────┘
```

- Textarea auto-grows up to 6 lines, then internal scroll.
- Cmd/Ctrl+Enter sends.
- Plain Enter inserts newline.
- Shift+Enter inserts newline (alias).
- Send button disabled when textarea empty AND no attachments.
- Send button enters "thinking" state when a turn is running; it becomes "Cancel" with a stop icon (Cmd+. shortcut).

### Image upload (F03)

- Three input methods, all lead to the same flow:
  1. Click the paperclip → file picker (filter: `image/png`, `image/jpeg`, `image/webp`).
  2. Drag image onto the chat panel → the whole panel shows a dashed-border drop overlay.
  3. Paste image from clipboard (Cmd+V on focused composer or anywhere in panel).
- Validation: max 10 MB (`IMAGE_TOO_LARGE`); allowed mimes only (`IMAGE_UNSUPPORTED_FORMAT`); decode-check (must be a valid image, not a renamed file).
- On accept: `attachment.upload` WS request → returns `attachment_id` → thumbnail rendered above textarea.
- Removable: hover thumbnail → X button → removes from staging (does NOT delete the file from disk; it just won't be attached to the next message).
- Sent attachments are referenced by `attachment_ids` on the Message.

**No PDF, no video, no audio in V1.** The error code `IMAGE_UNSUPPORTED_FORMAT` is shown on attempt.

## Message list

### Layout

```
┌─ Chat panel ─────────────────────────────┐
│ [active chat: "Hero & nav"  ▾] [+ New]  │
│ ─────────────────────────────────────── │
│  user  ▶ Add hero with CTA       ←── │
│         [thumbnail][thumbnail]         │
│                                         │
│  asst  ▶ I'll add a hero...            │ ← streaming text (live)
│         📖 Read 3 files                 │ ← coalesced tool-use
│         ✏️ Editing app/page.tsx +12 -4  │ ← Edit row with diff badge
│         ✏️ Editing components/Hero.tsx +28 -0
│         🔧 $ pnpm typecheck             │ ← Bash row
│         ✓ exit 0                        │ ← tool_result success
│         💾 Committed abc123f             │ ← git event
│         ─── $0.034 · 12s · 2 files ─── │ ← turn footer
│                                         │
│  user  ▶ Make the CTA blue              │
│  asst  ▶ ...                            │
│                                         │
│  [composer]                              │
└──────────────────────────────────────────┘
```

### Message rendering

**User messages:**
- Right-aligned bubble, max-width 70%.
- Image thumbnails below text, 80px square, click to open lightbox.
- Timestamp on hover.
- Right-click menu: "Copy text", "Resend" (treats as new message — no edit-in-place).

**Assistant messages:**
- Full-width.
- Header row: avatar (claude logo), small timestamp, model badge ("opus").
- Body: text + activity feed interleaved per chronological `seq`.
- Footer when turn complete: cost + duration + files-changed count.
- Auto-retry turns: orange left border + "Auto-fix attempt N/3" badge.
- Failed turns: red left border + error message inline.

### Activity feed rows

Each row is `<icon> <verb> <target> <status> <accessory>`:

| Tool | Icon | Verb | Target | Accessory |
|---|---|---|---|---|
| `Read` | 📖 | Read | (file path) | (collapsed in group) |
| `Glob`/`Grep` | 🔍 | Searched | (pattern) | (collapsed in group) |
| `Edit` | ✏️ | Editing | (file path) | `+N -M` diff badge → click to open file in code view |
| `Write` | 📝 | Created | (file path) | `+N` diff badge |
| `Bash` | 🔧 | $ | (command, monospace) | output preview (last 3 lines) on click expand |
| `TodoWrite` | ✅ | Planning | (count of items) | expand to see todos |

**Status pill** at the right end of each row:
- Spinner — running
- Green check — completed successfully
- Red X — completed with error (click to see stderr/error_text)

**Coalescing:**
- All `Read`/`Glob`/`Grep` rows from one turn collapse into a single row "Read 8 files / Searched 3 patterns" expandable to the full list.
- After the first `Edit`/`Write`/`Bash`, no more coalescing — each is its own row.

### Streaming text

- `text_delta` events append to an inline streaming region.
- Cursor blink at the end during streaming.
- Markdown rendering: code blocks (with copy button), inline code, bold/italic, lists, links. NO HTML rendering (escape).

### Turn footer (when state = COMPLETED)

```
─── $0.034 · 12s · 2 files · sha abc123f ──
```

The sha is clickable → opens the diff view in the code panel.

### Empty state

When no messages exist in the active chat:

```
┌──────────────────────┐
│                      │
│      🎨              │
│                      │
│    Start designing    │
│  Describe a component │
│   or paste a mockup   │
│                      │
│  Try one of these:   │
│  ┌─────────────────┐ │
│  │ Add a hero      │ │
│  └─────────────────┘ │
│  ┌─────────────────┐ │
│  │ Build a pricing │ │
│  │ page            │ │
│  └─────────────────┘ │
│  ┌─────────────────┐ │
│  │ Make a dashboard│ │
│  └─────────────────┘ │
│                      │
└──────────────────────┘
```

Clicking a chip pre-fills the composer (does not auto-send).

## Chat list / switcher

A small dropdown at the top of the chat panel:

```
[active chat title  ▾]   [+ New chat]
```

Open dropdown shows last 10 chats from this target, with title (first user prompt truncated) and last activity time. "View all" goes to a `/chats` page listing every chat for the target.

`+ New chat` → creates an empty chat (`chat.create`), sets it active, focuses the composer.

## Cancel and reset

- **Cancel turn**: while a turn is RUNNING, "Send" button becomes "Cancel" → `chat.cancel`. The current activity row gets a red X status; turn footer shows "Cancelled".
- **New conversation** (claude session reset): action in settings or via the chat dropdown menu. Confirm dialog: "Start fresh — claude will not remember previous turns. Chat history is preserved." On confirm: `chat.reset_session`.

## Required `data-testid`

| testid | Surface |
|---|---|
| `chat-panel` | root |
| `chat-active-title` | active chat title in header |
| `chat-switcher-trigger` | dropdown trigger |
| `chat-switcher-item-{n}` | dropdown row |
| `chat-new` | + New chat button |
| `chat-empty-state` | empty state container |
| `chat-empty-chip-{n}` | example prompt chip |
| `chat-message-{n}` | each message bubble (n = sequence index) |
| `chat-message-{n}-role` | data-role attr `user`\|`assistant`\|`system` |
| `chat-message-{n}-attachment-{i}` | attachment thumbnail |
| `activity-row-{turn_id}-{seq}` | activity feed row |
| `activity-row-{turn_id}-{seq}-status` | status pill (`spinner`\|`success`\|`error`) |
| `activity-row-{turn_id}-{seq}-expand` | expand toggle for collapsed groups |
| `turn-footer-{turn_id}` | footer row |
| `turn-cost-{turn_id}` | cost display |
| `turn-sha-{turn_id}` | commit sha link |
| `chat-composer-input` | textarea |
| `chat-attach-image` | paperclip button |
| `chat-send` | Send button (also = Cancel during turn) |
| `chat-attachment-staged-{i}` | staged thumbnail before send |

## Errors handled

| Code | UX |
|---|---|
| `IMAGE_TOO_LARGE` | toast on the chat panel |
| `IMAGE_UNSUPPORTED_FORMAT` | toast |
| `ATTACHMENT_WRITE_FAILED` | toast |
| `CLAUDE_SUBPROCESS_CRASHED` | red bordered turn + inline error + retry button |
| `CLAUDE_SESSION_LOST` | inline message: "Lost connection to claude session. Click to start a fresh conversation." → `chat.reset_session` |
| `CLAUDE_BUDGET_EXCEEDED` | banner above composer with cost cap info |

## Edge cases

- **Long-running turn**: if a turn has no activity for > 60s, render a "claude is taking longer than usual…" hint below the streaming text region. Not an error — just a UX cue.
- **Empty assistant response**: if a turn completes with no `text_delta` events (only tool uses + commit), render the activity feed and footer normally; there's no "main text" but the UI still shows the work done.
- **External commits during turn**: if `git.head` SHA changes outside this turn (user committed manually in another terminal), the watcher logs WARN and the next turn footer shows "Note: external commits detected".

## Dependencies

- F14 protocol (`chat.list`, `chat.create`, `chat.activate`, `chat.history`, `chat.send`, `chat.cancel`, `chat.reset_session`, `attachment.upload`, `event.turn.*`, `event.activity`, `event.git.committed`)
- F08 orchestrator (drives the lifecycle events)
- F00 open-folder (target must be open)

## Change scope (decomposition hint)

Single change: `chat-engine`. Delivers:
- JSONL writer/reader with append-only guarantees
- Composer with image upload (drag/paste/click)
- Message list rendering with markdown
- Activity feed with coalescing logic
- Empty state + switcher + chat list
- Cancel + reset-session flows
- All `chat.*` and `attachment.*` WS handlers

This is a medium-large change. Splitting into `chat-storage` and `chat-ui` is possible but the tight coupling on JSONL shape makes one change cleaner.
