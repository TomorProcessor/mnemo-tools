# set-design v1 — Local Screen/UI Designer for Next.js+shadcn

> Business specification — set-design is a desktop-class web app that lets a developer iterate on the UI of a target Next.js+shadcn project via a chat-driven loop with Claude. **No database. No auth. File-based persistence. Single-user, localhost-only.** The target directory is the source of truth; chat history lives next to it under `.set-design/`.

## Spec Structure

This spec is modular. The main file (this one) contains the overview, cross-feature contracts, and verification checklist. Detailed specs live in subdirectories:

- `features/` — one file per feature domain (chat-engine, preview-pane, orchestrator, etc.)
- `catalog/` — seed/fixture data (default target boilerplate, sample mockups, claude models reference)
- `design-direction.md` — brand/aesthetic narrative (drives the v0 design source generation)
- `design-brief.md` — non-authoritative tone note
- `content-fixtures.yaml` — design-fidelity gate seed
- `gap-analysis.md` — pre-handover spec ↔ design alignment report

## Shared Domain Models (data shapes)

set-design has **no database**. All persisted state lives in files under `<target>/.set-design/`. The shapes below are TypeScript interfaces and JSON line formats. Agents may add fields, but MUST NOT rename listed ones.

| Entity | Persisted as | Key fields |
|---|---|---|
| `TargetConfig` | `<target>/.set-design/config.json` (single object) | `version` (semver), `target_path`, `dev_url`, `dev_command` (default `pnpm dev`), `model` (`opus`\|`sonnet`\|`haiku`), `claude_session_id?`, `mcp_config_path?`, `design_tokens_paths[]`, `vision_loop` (bool), `auto_commit` (bool, default `true`), `commit_message_template?`, `created_at`, `updated_at` |
| `Chat` | `<target>/.set-design/chats/<chat_id>.jsonl` (append-only, one JSON event per line) | events of type `Message` \| `Turn` \| `Activity` \| `Error` |
| `Message` | line in chat JSONL, `kind: "message"` | `id` (ULID), `role` (`user`\|`assistant`\|`system`), `content` (text), `attachment_ids[]`, `created_at` |
| `Turn` | line in chat JSONL, `kind: "turn"` (one row per state change) | `id` (ULID), `prompt_message_id`, `state` (`PENDING`\|`RUNNING`\|`COMPLETED`\|`FAILED`\|`CANCELLED`), `started_at`, `completed_at?`, `commit_sha?`, `files_changed[]`, `cost_usd?`, `model`, `cancel_reason?` |
| `Activity` | line in chat JSONL, `kind: "activity"` (turn streaming events) | `turn_id`, `seq` (int), `event` (`tool_use_start`\|`tool_use_end`\|`text_delta`\|`build_error`\|`hmr_reload`), `tool_name?` (e.g. `Read`/`Edit`/`Bash`), `tool_input?` (truncated), `tool_result?` (truncated), `delta?`, `at` |
| `Attachment` | file at `<target>/.set-design/attachments/<id>.<ext>` + metadata in `<target>/.set-design/attachments/index.json` | `id` (ULID), `mime` (`image/png`\|`image/jpeg`\|`image/webp`), `path` (relative), `bytes`, `chat_id`, `message_id`, `created_at` |
| `LockFile` | `<target>/.set-design/.lock` (PID + start time) | `pid`, `started_at`, `host` |

**Rules for chat JSONL:**
- Append-only. Never rewrite lines. Compaction is a future concern.
- One file per chat (`<chat_id>.jsonl`). One target dir may contain multiple chats; the active chat id is stored in `config.json`.
- Activity events are coalesced for display (multiple consecutive `Read` tool uses from the same turn render as one collapsible row).

**Rules for changes:**
- A change that introduces a new entity or persisted file SHALL add it to this index in the same PR.
- ULIDs are used for all IDs (sortable, monotonic, no collision risk for single-user local app).
- Timestamps are ISO-8601 UTC.
- File-locking: a single set-design instance per target dir; second instance MUST refuse to start with `TARGET_LOCKED` error showing the existing `pid`.

## Error Code Catalog

User-facing errors return a stable machine-readable `code` (UPPER_SNAKE_CASE). The `code` is what E2E tests assert on (via `data-testid="error-banner"` + `data-error-code`); the message is what the user sees.

UI shape:
```json
{ "error": { "code": "CLAUDE_NOT_FOUND", "message": "claude CLI not found in PATH.", "field": null, "remediation_url": "/help/install-claude" } }
```

### Subprocess / Claude errors

| Code | Surface | When |
|---|---|---|
| `CLAUDE_NOT_FOUND` | banner | `claude` binary not in `PATH` on startup |
| `CLAUDE_VERSION_TOO_OLD` | banner | `claude --version` < required minimum |
| `CLAUDE_AUTH_REQUIRED` | banner | first `claude -p` call returns auth error |
| `CLAUDE_SUBPROCESS_CRASHED` | toast + chat | claude exited non-zero mid-turn; surface stderr tail |
| `CLAUDE_SESSION_LOST` | banner | `--resume <id>` failed; offer "Start fresh session" action |
| `CLAUDE_RATE_LIMITED` | banner | API rate-limit response; show retry timer |
| `CLAUDE_BUDGET_EXCEEDED` | banner | session cost passed configured cap |

### Target / filesystem errors

| Code | Surface | When |
|---|---|---|
| `TARGET_NOT_FOUND` | dialog | `target_path` missing |
| `TARGET_NOT_GIT_REPO` | dialog | `.git` missing; offer "Initialize git" action |
| `TARGET_DIRTY_ON_OPEN` | banner | uncommitted changes when opening; offer "Stash" or "Continue" |
| `TARGET_LOCKED` | dialog | another set-design instance owns the lock file |
| `CONFIG_INVALID` | dialog | `config.json` parse/schema failure |
| `CONFIG_VERSION_MISMATCH` | banner | major version diff with running app; offer migrate action |

### Dev server / preview errors

| Code | Surface | When |
|---|---|---|
| `DEV_SERVER_DOWN` | preview-banner | `target.dev_url` not responding within startup grace period |
| `DEV_SERVER_PORT_BUSY` | dialog | another process listening on `dev_url` port |
| `BUILD_FAILED` | preview-banner | Next.js dev process emits compile error; show stack frame |
| `RUNTIME_ERROR_OVERLAY` | preview-banner | iframe postMessage reports an unhandled runtime error |

### Git errors

| Code | Surface | When |
|---|---|---|
| `GIT_COMMIT_FAILED` | toast | `git commit` returned non-zero |
| `GIT_NOTHING_TO_COMMIT` | (silent) | empty stage after a turn — log only, no UI |
| `GIT_REVERT_CONFLICT` | dialog | `git revert` produced merge conflicts; offer abort |
| `GIT_NOT_HEAD` | banner | repo HEAD moved between turns (external edit) — offer reload |

### Image / attachment errors

| Code | Surface | When |
|---|---|---|
| `IMAGE_TOO_LARGE` | toast | upload > 10 MB |
| `IMAGE_UNSUPPORTED_FORMAT` | toast | mime type not in allowed list (`image/png`, `image/jpeg`, `image/webp`) |
| `ATTACHMENT_WRITE_FAILED` | toast | filesystem write error |

### WS protocol / Frame↔Brain errors

| Code | Surface | When |
|---|---|---|
| `WS_VERSION_MISMATCH` | dialog | Frame and Brain protocol versions diverge |
| `WS_HANDSHAKE_FAILED` | dialog | initial Hello message rejected |
| `WS_DISCONNECTED` | banner | reconnect ladder; auto-retry with backoff |

## E2E Test Conventions

### Selector strategy (priority order)

1. `data-testid="<kebab-case-name>"` — preferred for all interactive controls and assertion targets.
2. ARIA role + accessible name — for menus, dialogs, banners (when `data-testid` would be redundant).
3. Text content — only for static labels never expected to change (e.g. "Open folder…").

NEVER use class selectors or DOM-position selectors. Tailwind classes are not stable.

### Required `data-testid` registry

Cross-feature critical IDs (full registry per feature in `features/*.md`):

| testid | Surface | Notes |
|---|---|---|
| `app-shell` | root container | wraps everything |
| `chat-panel` | left panel root | |
| `preview-panel` | right panel root | |
| `status-bar` | bottom bar | |
| `chat-message-{n}` | each message bubble | n = sequence index in active chat |
| `chat-composer-input` | textarea | |
| `chat-send` | send button | |
| `chat-attach-image` | paperclip button | |
| `device-toggle-{mobile\|tablet\|desktop\|full}` | preview toolbar | |
| `theme-toggle-{light\|dark\|system}` | preview toolbar | |
| `preview-iframe` | iframe element | `name="preview"` also set |
| `code-view-toggle` | preview/code switcher | |
| `file-tree` | code view tree | |
| `file-tree-item-{path}` | tree row | path slugified |
| `diff-viewer` | monaco container | |
| `git-history-list` | versions panel | |
| `git-history-row-{sha}` | each commit row | first 7 chars of sha |
| `git-revert-{sha}` | revert button on commit row | |
| `error-banner` | top-of-pane error | `data-error-code` MUST be set |
| `toast-{code}` | toast notification | `data-error-code` MUST be set |
| `claude-state-pill` | status bar state | `data-state` ∈ `idle\|thinking\|tool-use\|error` |
| `cost-display` | status bar cost | `data-cost-usd` raw value |
| `git-branch-display` | status bar branch | `data-dirty` ∈ `0\|1` |

### Test data conventions

- Tests run against an ephemeral target dir under `tmp-e2e-target/` (gitignored).
- Each test seeds the target with the `nextjs-shadcn-starter` from `catalog/default-target.md`.
- Claude is **mocked at the subprocess boundary** for E2E (a fake `claude` shim emits canned `stream-json` lines). Real `claude` is only used in manual smoke runs.
- The mock shim lives at `tools/mock-claude.mjs` and is selected via the `SET_DESIGN_CLAUDE_BIN` env var.

## Business Conventions

### Single-user, localhost-only

- The HTTP server binds to `127.0.0.1` only — never `0.0.0.0`. This is enforced as a hard guard at startup.
- No login, no users, no sessions. The OS user is the implicit owner.
- The app refuses to start if `process.env.SET_DESIGN_PUBLIC === 'true'` is missing AND the bind address is non-localhost.

### File-based persistence

- All state under `<target>/.set-design/` — git-ignored by default (set-design's installer adds the entry to `.gitignore`).
- Chat JSONL is append-only. Compaction is a manual action ("Archive chat") that moves the file to `<target>/.set-design/chats/archive/`.
- Attachments are write-once; never mutated.

### "One target dir = one app instance"

- The Frame UI represents a single open target dir. Multi-target = multi-window (browser tab or separate process). No multi-target switcher.
- "Open folder…" replaces the current target — chat history of the previous target remains on disk.

### Resume semantics

- On startup with a target arg: read `config.json`, load active chat JSONL, render last 100 messages, restore preview iframe URL.
- Claude session: if `claude_session_id` exists in config, the next `claude -p` call uses `--resume <id>`. If `--resume` fails with `CLAUDE_SESSION_LOST`, prompt user; on confirm, generate fresh session id, persist, and continue.

### Auto-commit policy

- Default: every successful turn that modified files results in `git add -A && git commit -m "<message>"`.
- Commit message template: `<verb> <scope> [<turn_id_short>]\n\n<turn_summary>` where `<verb>` ∈ `Add`/`Update`/`Refactor`/`Style`/`Fix` (claude is asked to choose).
- Turns with no file changes do NOT create a commit (`GIT_NOTHING_TO_COMMIT` is suppressed silently).
- "Undo last" → `git revert HEAD --no-edit` (creates a new revert commit; never destructive).
- Disabling auto-commit (`auto_commit: false`) makes the UI show a "Save" button per turn that the user clicks manually.

### Streaming and activity feed

- The Brain spawns `claude -p` with `--output-format stream-json --include-partial-messages`.
- Each line of stdout is parsed into an `Activity` event and pushed to the Frame via WS as `event.activity`.
- Tool-use events are coalesced for display: consecutive `Read`/`Glob`/`Grep` calls within a single turn render as one collapsed row "Read 8 files / Searched 3 patterns" expandable on click.
- `Edit`/`Write`/`Bash` events render as individual rows with status pill (spinner → check / cross).

## Project-Wide Directives (orchestrator instructions)

These directives apply to ALL changes implementing set-design. They are framework-level rules; agents MUST honor them.

### Stack lock

- **Frame**: Next.js 14+ App Router, TypeScript strict, shadcn/ui, Tailwind. Runtime port: `7500`.
- **Brain**: Same Next.js process — API routes + a thin WS server. **No separate Express daemon for V1**; this keeps the V1 deployable as `pnpm dev` only.
- **Persistence**: filesystem only. NO Prisma, NO SQLite, NO Postgres, NO Redis. If a feature seems to need a DB, store it as JSON file in `.set-design/`.
- **Auth**: NONE. Refuse PRs that add NextAuth, JWT, password handling.
- **Styling**: shadcn primitives only — Button, Input, Textarea, Select, Card, Tabs, ScrollArea, Resizable, Toggle, ToggleGroup, Dialog, Sheet, Toast, Tooltip, Popover, Command (cmdk).

### Subprocess management

- `claude -p` invocations always use: `--output-format stream-json --include-partial-messages --input-format text` and `--add-dir <target>`.
- Sessions: first turn omits `--resume`; subsequent turns pass `--resume <session_id>`. The `session_id` is captured from the `system` event's `session_id` field on the first turn.
- Spawn lifecycle is owned by the Brain: spawn at `chat.send`, kill on user-cancel or 5-minute hard timeout, drain stderr on exit.
- Working directory: `target_path`. PATH is inherited unmodified.

### WS protocol versioning

- Every WS connection begins with a `Hello` message containing `{ protocol_version: "1.0", client: "frame" }`. Brain refuses incompatible majors (`WS_VERSION_MISMATCH`).
- Adding a new event type is a minor bump; renaming/removing is a major bump.

### Git interaction

- Use `simple-git` (npm) — never shell out to `git` directly except where simple-git lacks coverage (e.g. `revert`).
- All commits authored as `set-design <auto@set-design.local>`.
- Repos in detached-HEAD state at startup → refuse to operate; user must check out a branch.

### Logging

- Structured logs (JSON-lines) to `<target>/.set-design/logs/set-design-<date>.jsonl`.
- Levels: `debug`, `info`, `warn`, `error`. Default `info`.
- Every state transition (turn lifecycle, subprocess lifecycle, dev server lifecycle, git operations) logs at `info` with old→new value.

### Hooks (optional, narrow scope)

- The Brain MAY install a scoped `~/.claude/settings.json` (or per-spawn override via `--settings`) with:
  - `PreToolUse(Bash)` → `bash-guard.sh` blocks parameters that escape the target dir or match destructive patterns (`rm -rf`, `sudo`, `git push --force`).
  - `Stop` → posts to `http://localhost:7501/internal/hook/stop` to confirm turn finalization.
- No other hooks. The activity feed reads `stream-json` directly.

### V2 forward-compat

- The Frame ↔ Brain WS protocol is designed to be swappable. In V2, the Brain may live behind a Chrome extension + native messaging host instead of a same-process module. V1 implementations MUST keep all chat / git / file / preview operations behind the WS contract — no in-process shortcuts.

### Forbidden patterns (review-gate enforces)

- `import { PrismaClient }` — anywhere in the codebase.
- `next-auth` / `bcrypt` / `argon2` — anywhere.
- `process.env.DATABASE_URL` — anywhere.
- HTTP server bound to non-`127.0.0.1` host without `SET_DESIGN_PUBLIC=true`.
- `child_process.exec` (use `spawn` for safety).
- Direct shell-string git commands; use `simple-git`.

## Verification Checklist

Before merging set-design changes, the following must hold:

- [ ] `pnpm build` passes with no TypeScript errors at the strict level.
- [ ] `pnpm lint` passes with the shared ESLint config.
- [ ] `pnpm test` passes (vitest, `passWithNoTests` allowed only in foundation phase).
- [ ] `pnpm test:e2e` passes against the mock claude shim.
- [ ] No forbidden imports (Prisma, NextAuth, bcrypt) — review-gate verifies.
- [ ] HTTP server binding is `127.0.0.1` — review-gate verifies.
- [ ] Every new persisted file shape is documented in this master spec's Shared Domain Models table.
- [ ] Every new error code is in the Error Code Catalog.
- [ ] Every new `data-testid` is in the testid registry section above.
- [ ] WS message types added are versioned and documented in `features/protocol.md`.
- [ ] No `--no-verify` commits, no skipped pre-commit hooks.
- [ ] All claude subprocess invocations include `--add-dir <target>` and stream-json flags.
- [ ] Git operations go through `simple-git` (or documented exception).
- [ ] Logs cover every state transition and subprocess lifecycle event.
- [ ] design-fidelity gate passes against the v0 reference (where UI features apply).
