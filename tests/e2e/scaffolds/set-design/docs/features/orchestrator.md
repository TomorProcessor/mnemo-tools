# Orchestrator Engine (F08, F10, F11, F12)

The Brain-side engine that drives the chat → claude-subprocess → file-edits → git-commit → preview-reload loop. This is the heart of set-design — when this works, the rest is shell.

## Responsibilities

1. Spawn and supervise `claude -p` subprocesses (one per turn).
2. Stream stdout (`stream-json` lines) to the chat JSONL and emit WS `event.activity` frames.
3. Watch the target filesystem; emit `event.files.changed`.
4. Manage the target dev server lifecycle (`pnpm dev`).
5. Auto-commit at end of each successful turn (`simple-git`).
6. Detect build/runtime errors in the dev server; trigger HMR error feedback loop.
7. Inject design-context (design tokens, design-brief) into the system prompt on **first turn of a session**.
8. Pass through MCP servers configured in the target.

## Lifecycle of a turn

```
chat.send (WS request)
   │
   ▼
1. Validate target_path, claude binary, dev server up
2. Append Message{role: "user", ...} to chat JSONL
3. Append Turn{state: PENDING} to chat JSONL
4. Emit event.turn.started
   │
   ▼
5. Build claude command:
     claude -p
       --output-format stream-json
       --include-partial-messages
       --add-dir <target_path>
       --model <config.model>
       [--resume <claude_session_id> | (omitted on first turn)]
       [--mcp-config <config.mcp_config_path> | (omitted if absent)]
       [--append-system-prompt <design_context_blob>] (only on first turn of session)
   │
   ▼
6. spawn() with cwd = target_path, stdin = piped, stdout = piped, stderr = piped
7. Write the user prompt to stdin (single text frame), then close stdin
   │
   ▼
8. For each line of stdout:
     - parse JSON
     - if first 'system' event: capture session_id, persist to config.json
     - convert to Activity event, append to chat JSONL, emit WS event.activity
     - if 'result' event: capture cost_usd, exit reason
   │
   ▼
9. Watch target/ via chokidar (gitignore-aware, debounce 200ms)
   - Emit event.files.changed for each batch
   - Track which paths claude touched in this turn
   │
   ▼
10. On subprocess exit (code 0):
      - run `git status --porcelain`; if dirty:
        - if config.auto_commit: `git add -A && git commit -m <msg>` via simple-git
          → emit event.git.committed
        - else: stage the changes only, no commit
      - update Turn{state: COMPLETED, commit_sha, cost_usd, files_changed}
      - emit event.turn.completed
    On exit (code != 0):
      - drain stderr, log
      - update Turn{state: FAILED, exit_status: "failed"}
      - emit event.turn.completed with exit_status: "failed"
    On user cancel (chat.cancel):
      - SIGTERM, then SIGKILL after 3s if still alive
      - update Turn{state: CANCELLED}
      - emit event.turn.cancelled
   │
   ▼
11. Wait for HMR settle (350ms after last file change)
    - poll dev server `/__nextjs_original-stack-frame` or homepage for build errors
    - if BUILD_FAILED: emit event.preview.error{kind:"build"}, trigger auto-fix loop (see below)
    - else: emit event.preview.reloaded
```

## Subprocess invariants

- Always set `--add-dir <target_path>` so claude can read/write target files.
- Always pass `--output-format stream-json` (parsing depends on it).
- NEVER pass `--dangerously-skip-permissions` (subprocess must respect tool guards).
- Working directory is `target_path`; PATH is unmodified inheritance.
- Hard timeout: 5 minutes per turn. After 5min, SIGTERM, then SIGKILL after 3s.
- Drain stderr on exit; if non-empty and exit != 0, log at WARN.
- On crash (SIGSEGV/SIGABRT etc.): log ERROR, mark turn FAILED, emit `CLAUDE_SUBPROCESS_CRASHED` toast.

## Session management

- On the **first** turn for a target: omit `--resume`. Capture `session_id` from the `system` stream-json event. Persist to `config.json` immediately.
- On every **subsequent** turn: pass `--resume <claude_session_id>`.
- On `chat.reset_session`: clear `claude_session_id` from config; next turn starts fresh (treated as "first turn").
- On `--resume` failure (claude exits with auth/expired error in the first 2s): emit `CLAUDE_SESSION_LOST`, do NOT auto-recover — let the user choose `chat.reset_session`.

## File watcher (chokidar)

- Watch `target_path` recursively.
- Honor `.gitignore` (use chokidar's `ignored` option with a parser).
- Debounce 200ms, batch into change events.
- During a turn: tag changes as `turn_id` so the Frame can render them as part of that turn's activity.
- Outside a turn: emit `event.files.changed` with `turn_id: null` (rare; means user externally edited files).

## Dev server lifecycle

- Spawned on `preview.start` request OR auto-spawned on `target.open` if `config.auto_start_dev_server: true` (default).
- Command from `config.dev_command` (default `pnpm dev`).
- Working directory: `target_path`.
- Stdout/stderr captured to `<target>/.set-design/logs/dev-server-<date>.log`.
- Health check: poll `config.dev_url` GET `/` until 200 OR 30-second timeout (`DEV_SERVER_DOWN`).
- On port conflict: emit `DEV_SERVER_PORT_BUSY` (don't try alternate ports — confusing for user).
- On unexpected exit: log ERROR, emit `event.preview.error{kind:"crashed"}`, surface "Restart dev server" CTA in UI.
- On `target.close`: SIGTERM the dev server, wait 5s, SIGKILL.

## HMR error feedback loop (F10)

When a turn completes and a build error is detected:

```
1. Capture build error from:
     a. Dev server stderr (Next.js prints compile errors here)
     b. iframe postMessage hook (Frame relays runtime errors via WS)
     c. fetching the dev URL and parsing the Next.js error overlay HTML
2. Append a synthetic system Message:
     "Build failed after your change:\n\n<error_text>\n\nPlease fix and try again."
3. Spawn another claude turn with this synthetic prompt.
   Mark this turn as auto_retry: true and retry_count: 1.
4. If the auto-retry also fails:
     retry_count++; if retry_count >= 3: emit BUILD_FAILED with "auto-fix exhausted",
     surface "Stop" / "Manual fix" buttons in the preview banner.
   Else: continue retrying.
5. The user can disable auto-retry at any time via "Stop" button → emit chat.cancel
   for the auto-retry turn.
```

The auto-retry chain is visible in the chat: each retry is a new Turn with `auto_retry: true` and a special UI rendering (orange border, "Auto-fix attempt N/3" badge).

## MCP passthrough (F11)

- `config.mcp_config_path` (default: auto-detect `<target>/.mcp.json` if present).
- If set, pass `--mcp-config <path>` to every claude invocation.
- The Brain itself does NOT parse MCP config beyond existence/path validity. Claude handles MCP loading.
- The UI in `features/open-folder.md` displays a read-only list of MCP servers detected (parsed from the `.mcp.json`) for transparency.
- Per-server enable/disable in V1 is **out of scope** — claude loads what's in the file. (V2 will add an override layer.)

## Design tokens / context auto-injection (F12)

On `target.open`, scan for these files in the target:
- `docs/design-system.md` or `docs/design-tokens.md`
- `docs/design-brief.md`
- `design.md` (root level)
- `<target>/.set-design/design-context.md` (user-curated extras)

Files that exist are concatenated (with header separators) into the `design_context_blob`. On the **first turn of a claude session only**, the blob is passed via `--append-system-prompt`. Subsequent turns inherit via `--resume`, so re-injection is unnecessary.

If a design context file changes between turns: do nothing automatically (claude already saw it). On `chat.reset_session`, the next first-turn re-reads everything fresh.

The Frame UI shows the auto-detected paths as a read-only list in settings; the user can manually add additional paths (config.design_tokens_paths[]).

## Logging

Structured JSON-lines to `<target>/.set-design/logs/orchestrator-<date>.jsonl`. Every:

- subprocess spawn (PID, args)
- subprocess exit (code, signal, runtime ms)
- session_id capture (first turn)
- file watcher batch (paths, count)
- dev server lifecycle (start, exit, port)
- HMR error detection (kind, retry count)
- git operation (op, sha-before, sha-after)

## Required `data-testid` (no UI of its own)

This feature is engine-side. UI testids come from the chat-engine, preview-pane, and status-bar features. Engine state surfaces via WS events.

## Dependencies

- F14 protocol (this engine talks to the Frame via WS only)
- F00 open-folder (target_path, dev_url, config must exist)

## Change scope (decomposition hint)

Single change: `orchestrator-engine`. Delivers:
- Subprocess pool with stream-json parser.
- chokidar file watcher with gitignore parsing.
- simple-git wrapper for log/commit/revert/status.
- Dev server lifecycle manager.
- HMR error scraper + auto-retry loop.
- MCP path passthrough.
- Design context auto-detection + blob assembly.
- Comprehensive logger with JSONL output.

This is the largest single change in the scaffold. May benefit from being split into `orchestrator-core` (subprocess + git + watcher) and `orchestrator-feedback` (HMR auto-retry) if the planner thinks parallelism helps — but they share so many internals that one change is simpler.
