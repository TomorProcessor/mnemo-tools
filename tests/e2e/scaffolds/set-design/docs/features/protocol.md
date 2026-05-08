# Frame ↔ Brain WS Protocol (F14)

The single contract between the UI (Frame) and the engine (Brain). In V1 both live in the same Next.js process, but communicate over a WebSocket as if separated. This is a hard rule — it makes V2 (hosted Frame at `designer.setcode.dev` + local Brain via Chrome extension + native messaging) a swap, not a rewrite.

## Overview

- **Endpoint:** `ws://127.0.0.1:7501/api/v1`
- **Transport:** WebSocket, JSON-encoded text frames (no binary in V1)
- **Protocol version:** `1.0` (semver-major locked for V1; minor bumps add fields, never remove)
- **Subprotocol header:** `set-design.v1` (sent on the WebSocket handshake)
- **Auth:** localhost-bind only; the OS-level user is the implicit principal. No tokens, no headers in V1.

## Connection lifecycle

```
client → server : Hello                         (must be first frame)
server → client : Welcome | Error               (must be first reply)
client/server   : Request / Response / Event   (any order, multiplexed)
                  ...
client → server : Goodbye (optional, then close)
```

If the first frame from the client is not a valid `Hello`, the server closes with code `4400 Bad Hello`.

If `protocol_version` major differs from server's, the server replies with `WS_VERSION_MISMATCH` and closes with code `4426 Version Mismatch`.

## Message envelope

Every frame is a JSON object with this shape:

```json
{
  "id": "01HXXX..." | null,
  "kind": "request" | "response" | "event" | "error",
  "type": "<dot.namespaced.type>",
  "payload": { ... }
}
```

- `id` — ULID, present on `request`/`response` (client-generated for requests; echoed on responses). `null` on server-pushed events.
- `kind` — one of: `request` (client→server expecting a response), `response` (server→client matched to a request id), `event` (server-pushed, no id), `error` (negative response — server→client either matched to a request id or null for connection-wide errors).
- `type` — dot-namespaced operation name (see catalog below).
- `payload` — type-specific object; may be empty `{}`.

## Connection-level message types

| Type | Direction | Purpose |
|---|---|---|
| `hello` | client→server | initial handshake |
| `welcome` | server→client | accepted handshake |
| `goodbye` | client→server | clean disconnect |
| `ping` / `pong` | both | optional keepalive (15s interval) |

`hello` payload: `{ protocol_version: "1.0", client: "frame", client_version: "<semver>" }`.

`welcome` payload: `{ protocol_version: "1.0", server: "brain", server_version: "<semver>", target_path: "<abs path>", target_locked: false, capabilities: ["chat", "preview", "git", "files", "vision_loop"?, "templates"?] }`.

## Request types (client→server)

Grouped by feature. Each row lists payload shape and response shape.

### Target / config

| Type | Request payload | Response payload |
|---|---|---|
| `target.open` | `{ path: string }` | `{ config: TargetConfig, locked_by_pid?: number }` (errors: `TARGET_NOT_FOUND`, `TARGET_LOCKED`, `TARGET_NOT_GIT_REPO`) |
| `target.close` | `{}` | `{}` |
| `config.read` | `{}` | `{ config: TargetConfig }` |
| `config.update` | `{ patch: Partial<TargetConfig> }` | `{ config: TargetConfig }` |
| `config.scan_design_context` | `{}` | `{ paths: string[] }` (autodetects design-system.md, design-brief.md, etc.) |

### Chats

| Type | Request payload | Response payload |
|---|---|---|
| `chat.list` | `{}` | `{ chats: { id, created_at, title, message_count, last_activity_at }[] }` |
| `chat.create` | `{ title?: string }` | `{ chat_id }` (no first message yet) |
| `chat.activate` | `{ chat_id }` | `{ chat_id }` (sets active chat in config) |
| `chat.history` | `{ chat_id, since_seq?: number, limit?: number }` | `{ events: ChatEvent[], has_more: boolean, last_seq: number }` |
| `chat.archive` | `{ chat_id }` | `{}` |

### Turn lifecycle (the big one)

| Type | Request payload | Response payload |
|---|---|---|
| `chat.send` | `{ chat_id, content: string, attachment_ids?: string[] }` | `{ turn_id }` (the turn now runs; server pushes events; final `event.turn.completed` carries cost+commit) |
| `chat.cancel` | `{ turn_id }` | `{}` (kills subprocess; emits `event.turn.cancelled`) |
| `chat.reset_session` | `{}` | `{ new_session_id }` ("New conversation": clears `claude_session_id` in config; next turn starts fresh) |

### Attachments

| Type | Request payload | Response payload |
|---|---|---|
| `attachment.upload` | `{ chat_id, mime, base64_bytes }` | `{ attachment_id }` (errors: `IMAGE_TOO_LARGE`, `IMAGE_UNSUPPORTED_FORMAT`) |
| `attachment.read` | `{ attachment_id }` | `{ mime, base64_bytes }` |

### Files & git

| Type | Request payload | Response payload |
|---|---|---|
| `files.tree` | `{ subpath?: string, max_depth?: number }` | `{ tree: FileNode[] }` |
| `files.read` | `{ path: string }` | `{ content: string, mime, bytes }` |
| `files.diff` | `{ path: string, base_sha?: string, head_sha?: string }` | `{ unified_diff: string, lines_added, lines_removed }` |
| `git.log` | `{ limit?: number, since?: string }` | `{ commits: { sha, short_sha, message, author, files_changed, additions, deletions, at }[] }` |
| `git.revert` | `{ sha: string }` | `{ new_sha }` (errors: `GIT_REVERT_CONFLICT`) |
| `git.head` | `{}` | `{ sha, branch, dirty: boolean }` |

### Preview & dev server

| Type | Request payload | Response payload |
|---|---|---|
| `preview.status` | `{}` | `{ url, state: "up"\|"down"\|"starting"\|"crashed", port?, pid? }` |
| `preview.start` | `{}` | `{ pid, port }` (errors: `DEV_SERVER_PORT_BUSY`) |
| `preview.stop` | `{}` | `{}` |
| `preview.reload_request` | `{}` | `{}` (instructs Frame to remount iframe) |
| `preview.screenshot` | `{ viewport: "mobile"\|"tablet"\|"desktop"\|"full" }` | `{ attachment_id }` (vision-loop feature) |

### Health & info

| Type | Request payload | Response payload |
|---|---|---|
| `system.health` | `{}` | `{ claude_ok, claude_version?, dev_server_ok, git_ok, target_ok }` |
| `system.budget` | `{}` | `{ session_cost_usd, all_time_cost_usd, model_breakdown: {...} }` |

## Server-pushed event types

Events have `id: null` and `kind: "event"`. Subscribers infer relevance from `payload.chat_id` / `payload.turn_id`.

| Type | Payload | When |
|---|---|---|
| `event.turn.started` | `{ chat_id, turn_id, model, started_at }` | after `chat.send` succeeds |
| `event.activity` | `{ chat_id, turn_id, seq, event, tool_name?, tool_input?, tool_result?, delta?, at }` | each line of `claude -p` stream-json |
| `event.files.changed` | `{ chat_id, turn_id, paths: string[], operation: "modify"\|"add"\|"delete" }` | from chokidar watcher |
| `event.git.committed` | `{ chat_id, turn_id, sha, short_sha, message, files_changed, additions, deletions }` | after auto-commit |
| `event.preview.reloaded` | `{ at }` | after dev server hot-reload detection |
| `event.preview.error` | `{ kind: "build"\|"runtime", message, stack? }` | build/runtime error in target |
| `event.turn.completed` | `{ chat_id, turn_id, cost_usd, duration_ms, files_changed, commit_sha?, exit_status: "success"\|"failed"\|"cancelled" }` | turn finalized |
| `event.turn.cancelled` | `{ chat_id, turn_id, reason }` | user cancelled or hard timeout |
| `event.budget.update` | `{ session_cost_usd, all_time_cost_usd }` | after each turn |

## Error response shape

`kind: "error"` (matched to request `id` if applicable), payload:

```json
{
  "code": "TARGET_NOT_FOUND",
  "message": "Target directory does not exist: /Users/.../app",
  "field": null,
  "details": { "path": "..." },
  "remediation_url": "/help/target-not-found"
}
```

Codes are drawn from the master spec's Error Code Catalog. New codes added by a change MUST be registered there.

## Reconnection rules

- If the WS drops, the Frame retries with exponential backoff (`1s, 2s, 4s, 8s, capped 30s`). Status bar shows `claude-state-pill` with `data-state="error"` and a tooltip "Reconnecting…".
- On reconnect, Frame issues a `chat.history` with `since_seq` to catch up. The Brain MUST guarantee monotonic `seq` within a chat JSONL.
- An in-flight turn that completes during a Frame disconnect is preserved: `event.turn.completed` is recorded in the chat JSONL even with no listener.

## V2 forward-compat notes (informative)

- In V2, the Brain runs inside a Chrome extension's native messaging host. The WS endpoint moves to a local-only port managed by the extension, but the message shape is identical.
- The Frame at `designer.setcode.dev` connects to `ws://localhost:<assigned-port>` after pairing with the extension. Pairing is one-time, persisted by the extension.
- `target_path` in V2 is selected via the Chrome extension's `chrome.fileSystem` (or a browser file-picker fallback) — the Frame does NOT see absolute paths in V2 except as opaque tokens.

V1 implementations MUST avoid baking absolute-path leaks or in-process shortcuts that would break this swap.

## Required `data-testid` (Frame contract)

This feature is server-side; it has no testids of its own beyond what already lives on the status bar. WS health is observable through `claude-state-pill` (`data-state="error"` indicates disconnected) and the toast `WS_VERSION_MISMATCH` / `WS_DISCONNECTED`.

## Dependencies

- None. This is the foundation; all other features depend on this contract.

## Change scope (decomposition hint)

This file maps to a single change: `frame-brain-protocol`. The change delivers:
- The WS server (Next.js Route Handler with `ws` library OR a custom Node server adapter).
- Zod schemas for every request/response/event payload.
- The Frame-side WS client hook (`useBrain()`).
- An end-to-end mock test that opens a connection, sends every request type, and asserts the response shape.
