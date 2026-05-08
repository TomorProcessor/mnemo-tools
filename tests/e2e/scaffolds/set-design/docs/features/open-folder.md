# Open Folder + Target Config (F00)

The entry point. set-design is a single-target app: one running instance owns one target dir. This feature handles target selection, config bootstrap, and the lock file.

## Behaviors

### Startup paths

set-design can be launched in three ways. All three converge on the same flow.

1. **Explicit target arg**: `pnpm start <target_path>` — Brain immediately tries to open `<target_path>`.
2. **Last target arg**: `pnpm start --last` — Brain reads `~/.config/set-design/last-target.txt` and opens that path.
3. **No arg**: Frame renders the "Welcome" screen with a folder picker. User picks → Brain runs target.open.

### `target.open` behavior

```
Input: { path: string }

1. Resolve to absolute path (expand ~, resolve symlinks).
2. Check directory exists → else TARGET_NOT_FOUND.
3. Check `<path>/.git` exists → else surface TARGET_NOT_GIT_REPO with "Initialize git" action.
4. Check for existing lock file at `<path>/.set-design/.lock`:
     - If lock owner PID is alive → return TARGET_LOCKED with PID/start time.
     - If lock is stale (PID dead) → log WARN, remove, continue.
5. Acquire lock: write { pid, started_at, host } to .lock.
6. Read or initialize `<path>/.set-design/config.json`:
     - If missing: create with defaults (see schema below).
     - If exists: parse + validate via JSON schema → CONFIG_INVALID on failure.
     - If version mismatch (major): emit CONFIG_VERSION_MISMATCH banner with "Migrate" action.
7. Run config.scan_design_context to detect design files.
8. If config.auto_start_dev_server (default true): spawn dev server (see orchestrator).
9. Persist target_path to ~/.config/set-design/last-target.txt.
10. Return { config, locked: false }.
```

### `target.close`

- Release the lock file.
- SIGTERM the dev server.
- Drain any in-flight turn (cancel if running > 5s).
- Frame returns to the Welcome screen.

### Switching targets

The Frame's "Open folder…" command runs `target.close` then `target.open` in sequence. The chat history of the previous target stays on disk (file-only persistence).

## Config schema

`<target>/.set-design/config.json`:

```json
{
  "version": "1.0",
  "target_path": "/abs/path/to/target",
  "dev_url": "http://localhost:3000",
  "dev_command": "pnpm dev",
  "auto_start_dev_server": true,
  "model": "opus",
  "claude_session_id": null,
  "active_chat_id": null,
  "mcp_config_path": null,
  "design_tokens_paths": [],
  "vision_loop": false,
  "auto_commit": true,
  "commit_message_template": null,
  "budget_cap_usd": null,
  "created_at": "2026-05-06T12:00:00Z",
  "updated_at": "2026-05-06T12:00:00Z"
}
```

**Field rules:**
- `version` — semver string. Major bump = breaking config schema change. Major mismatch triggers CONFIG_VERSION_MISMATCH.
- `target_path` — must equal the directory containing the `.set-design/` folder. If they diverge (e.g., user renamed the folder), Brain rewrites this field on next open.
- `dev_url` — full URL including protocol and port. Default `http://localhost:3000`. Frame's iframe `src` derives from this.
- `dev_command` — shell command run via `spawn` (split-args, no shell). Default `pnpm dev`. Allow `npm run dev`, `yarn dev`, `bun dev`.
- `model` — one of `opus`, `sonnet`, `haiku`. Maps to `claude -p --model <full-id>` (full IDs in `catalog/claude-models.md`).
- `claude_session_id` — null until first turn; populated from claude's `system` event.
- `active_chat_id` — null until first chat created; the chat shown on resume.
- `mcp_config_path` — auto-detected (`<target>/.mcp.json` if present) but user-overridable.
- `design_tokens_paths` — list of absolute or relative-to-target paths. Auto-populated on `target.open` from scan; user can add/remove.
- `vision_loop` — opt-in stretch feature (F15).
- `auto_commit` — true means each successful turn → git commit. False means user clicks "Save".
- `commit_message_template` — null = use claude-generated messages. String value with placeholders `{verb}`, `{summary}`, `{turn_id}` overrides.
- `budget_cap_usd` — null = no cap. Numeric = abort turn if cumulative session cost exceeds.

**Validation:**
- A JSON Schema for the config lives in `<target>/.set-design/config.schema.json` (auto-written on init).
- Brain refuses to start without a valid config; the user must pick "Repair" (resets to defaults preserving target_path) or "Cancel".

## Lock file format

`<target>/.set-design/.lock`:

```json
{
  "pid": 12345,
  "started_at": "2026-05-06T12:00:00Z",
  "host": "hostname",
  "version": "1.0"
}
```

- Stale-detection: `pid` not alive (POSIX `kill -0`) OR `host` mismatch (running on a different machine, e.g. NFS mount).
- Stale lock removal logs at WARN with the previous owner's pid + started_at.
- Lock is removed cleanly on `target.close` and on graceful shutdown (SIGTERM handler).
- Process crash leaves a stale lock — the next start removes it.

## UI surface (Frame)

### Welcome screen

When no target is open. Renders at `/welcome` (or `/` redirects there).

- Heading: "set-design"
- Subhead: "Design Next.js + shadcn UIs with Claude. Locally."
- Primary button: "Open folder…" → invokes browser's file-picker (or Frame-side native dialog in V2)
- Secondary button: "Recent" → dropdown of last 5 targets (read from `~/.config/set-design/recent.json`)
- Footer: "What you need" — bullet list: claude CLI, Node 18+, an empty or existing Next.js folder

```
┌────────────────────────────────────────────────┐
│                                                │
│           set-design                            │
│           Design Next.js + shadcn UIs           │
│           with Claude. Locally.                 │
│                                                │
│           [Open folder…]                        │
│                                                │
│           Recent ▾                              │
│             • ~/work/landing-page               │
│             • ~/work/dashboard-redesign         │
│                                                │
│           — — —                                 │
│           What you need:                        │
│           • Claude CLI installed                │
│           • Node 18+                            │
│           • Empty or existing Next.js folder    │
│                                                │
└────────────────────────────────────────────────┘
```

### "Initialize git" flow

If `target.open` returns `TARGET_NOT_GIT_REPO`:

- Dialog: "This folder is not a git repository. set-design needs git to track changes."
- Two buttons: "Initialize git here" (runs `git init` + creates `.gitignore` with `.set-design/`) and "Cancel"
- After init, retries `target.open`.

### "Stash uncommitted changes" flow

If `target.open` finds the repo dirty:

- Banner: "Uncommitted changes detected. set-design will commit your work for you. What should happen to existing changes?"
- Three options: "Commit now (recommended)" | "Stash" | "Continue (changes will be mixed into the first set-design commit)"

### Settings page (`/projects/<not-applicable>/settings` actually just `/settings` since one target)

Tabs:
1. **General** — name (display only, derived from path), target path (display, "Open different folder" button), dev URL, dev command, model select, auto_start_dev_server toggle.
2. **Git** — auto_commit toggle, commit_message_template (with placeholder hints), "Open in terminal" button.
3. **MCP** — mcp_config_path (auto-detected, override option), parsed list of MCP servers (read-only).
4. **Design context** — design_tokens_paths list (auto-detected items + manual add).
5. **Vision feedback** — vision_loop toggle with help text "Uses Playwright to screenshot the preview after each turn for self-correction. Adds ~$0.005 per turn."
6. **Budget** — budget_cap_usd input, all-time cost display (read from session JSONLs).

Each tab has a "Save" button. Validation errors render inline.

## Error handling

| Error | Surface | Action |
|---|---|---|
| `TARGET_NOT_FOUND` | dialog | "Pick another folder" |
| `TARGET_NOT_GIT_REPO` | dialog | "Initialize git here" or "Cancel" |
| `TARGET_LOCKED` | dialog | "Open as read-only", "Force unlock", "Cancel" — Force unlock requires typing the PID |
| `CONFIG_INVALID` | dialog | "Repair" (reset to defaults) or "Cancel" |
| `CONFIG_VERSION_MISMATCH` | banner | "Migrate" button if migration available, else "Pick another folder" |

## Required `data-testid`

| testid | Surface |
|---|---|
| `welcome-screen` | root container |
| `open-folder-button` | primary CTA |
| `recent-target-{n}` | each recent row, n = index |
| `settings-tab-{name}` | tab triggers (`general`/`git`/`mcp`/`design`/`vision`/`budget`) |
| `setting-input-{key}` | each form field, key = config field name |
| `settings-save-{tab}` | save button per tab |
| `target-locked-dialog` | locked dialog |
| `target-locked-pid` | PID display |
| `target-locked-force-input` | type-PID-to-confirm input |

## Dependencies

- F14 protocol (uses `target.open`, `target.close`, `config.read`, `config.update`, `config.scan_design_context`)

## Change scope (decomposition hint)

Single change: `open-folder-and-config`. Delivers:
- Welcome screen + folder picker
- Lock file lifecycle (acquire, stale detection, release)
- Config JSON schema + read/write/validate
- Settings page with 6 tabs and per-tab Save
- Recent targets persistence (`~/.config/set-design/recent.json`)
- Initialize-git and stash flows
- All `target.*` and `config.*` WS handlers
