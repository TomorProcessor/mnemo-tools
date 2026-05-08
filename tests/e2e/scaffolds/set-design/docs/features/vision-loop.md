# Vision Loop (F15 — V1 stretch, opt-in)

After each successful turn, take a screenshot of the preview iframe and feed it back to claude on the next turn. Claude can see what its own change rendered as, enabling self-correction.

This is a **stretch feature** for V1: the chat-engine and orchestrator MUST work with `vision_loop: false` (the default). Enabling it is an opt-in setting.

## Why

Pure code-blind generation (the v0 default) is fast but error-prone — claude writes "use bg-blue-600 for the CTA" and never verifies the actual rendered color, contrast, or layout. A vision loop closes that gap: each turn's first action becomes "look at what you did last time".

## Behavior when enabled

```
turn N:
  user prompt
    │
    ▼
  claude -p (with --resume)
    │
    ▼
  claude edits files, commits, completes turn
    │
    ▼  (NEW STEP)
  Brain captures preview screenshot via Playwright
    │
    ├─ wait for HMR to settle (poll iframe load + 500ms quiet period)
    ├─ launch headless chromium
    ├─ navigate to dev_url
    ├─ set viewport per config.vision_viewport (default `desktop`)
    ├─ wait for networkidle + 200ms
    ├─ screenshot full-page PNG
    └─ store as attachment in chat JSONL
    │
    ▼
  attachment_id surfaces in turn footer:
    "claude saw this →  [thumbnail]"

turn N+1:
  user prompt
    │
    ▼  (NEW: auto-prepended)
  attachment_ids = [previous_screenshot_id, ...user attachments]
    │
    ▼
  claude -p sees the screenshot of the last render before working
```

The screenshot is rendered as an inline thumbnail in the turn footer (next to cost/duration). Click → lightbox.

The visual feedback loop creates a closed system: claude knows the result of its last change before making the next one.

## Configuration

`config.vision_loop` (bool, default `false`) — top-level toggle in settings → Vision feedback tab.

When true, additional config:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `vision_viewport` | enum (`mobile`/`tablet`/`desktop`/`current`) | `desktop` | which viewport to capture; `current` follows the user's device-toolbar selection |
| `vision_full_page` | bool | `true` | full-scroll capture vs above-the-fold |
| `vision_max_age_turns` | int | 1 | how many turns back the screenshot stays attached as context (default: only the last screenshot) |
| `vision_skip_when_no_changes` | bool | `true` | skip screenshot if turn produced no file changes |

## Brain implementation

- Use `playwright` (Node) — pre-installed dependency. Browser binaries fetched lazily on first vision turn.
- Headless chromium, isolated browser context per screenshot (no profile reuse).
- `dev_url` must be `up`; if not, skip silently with a log warning.
- Screenshot stored at `<target>/.set-design/attachments/<attachment_id>.png`.
- Attachment metadata: `{ kind: "screenshot", turn_id, viewport, full_page, captured_at }`.
- Cost: log a small additional cost (estimate: $0.005 per screenshot for the input image tokens on next turn). Surfaced in cost-display.

## UI surface

### Settings → Vision feedback tab

```
[ ] Enable vision feedback
    Uses Playwright to screenshot the preview after each turn for self-correction.
    Adds approximately $0.005 per turn to claude API cost.

Viewport:  [ Mobile | Tablet | Desktop | Current ]   (default: Desktop)
[ ] Full page capture (scroll-to-bottom)
[ ] Skip when no file changes

Status:  ✓ Playwright installed, chromium ready (~290 MB)
         [Reinstall] [Clear cache]
```

### Chat — turn footer

When a screenshot is attached:

```
─── $0.034 · 12s · 2 files · sha abc123f · [📷 thumbnail] ──
```

Click thumbnail → lightbox showing the full-page screenshot.

### Chat — turn header (next turn)

If the next turn includes the previous screenshot as auto-context:

```
asst  ▶ (claude saw this before working: [thumbnail])
        I'll add a hero...
```

The thumbnail is non-removable from the auto-context — claude will always see the most recent screenshot if vision_loop is on.

## Edge cases

- **Dev server crashed during screenshot** → log warning, skip screenshot, do not block next turn. Status bar shows transient "Screenshot skipped — server down".
- **Build error visible in screenshot** → captured normally; claude will see the Next.js error overlay in the image. This actually helps the auto-fix loop (F10).
- **Long full-page captures** (e.g. infinite scroll) → cap at 8000px height; truncate with a 1-line note in the screenshot bottom.
- **Multiple turns in quick succession** → only the most recent screenshot is included in next-turn context (per `vision_max_age_turns`).

## Required `data-testid`

| testid | Surface |
|---|---|
| `vision-toggle` | settings enable toggle |
| `vision-viewport-{value}` | viewport radio |
| `vision-full-page-toggle` | full-page checkbox |
| `vision-skip-no-changes-toggle` | skip checkbox |
| `vision-status` | status row |
| `vision-reinstall` | reinstall button |
| `vision-clear-cache` | clear cache button |
| `turn-screenshot-{turn_id}` | thumbnail in turn footer |
| `turn-screenshot-{turn_id}-lightbox` | lightbox container |

## Errors handled

| Code | UX |
|---|---|
| `PLAYWRIGHT_NOT_INSTALLED` | banner in settings: "Playwright not installed. [Install now]" |
| `CHROMIUM_DOWNLOAD_FAILED` | banner: "Chromium download failed. [Retry]" |
| `SCREENSHOT_TIMEOUT` | log warning, skip turn's screenshot silently (do not block) |

(All vision-loop errors are non-blocking: failures degrade gracefully to vision_loop disabled for that turn.)

## Dependencies

- F14 protocol (new types: `preview.screenshot`, `attachment.upload`)
- F08 orchestrator (turn lifecycle hook to inject post-turn screenshot)
- F04 preview-pane (dev server up)
- F00 open-folder (config.vision_loop, vision_viewport, etc.)

## Change scope (decomposition hint)

Single optional change: `vision-loop`. Delivers:
- Playwright install hook (lazy, first-use)
- Post-turn screenshot pipeline
- Auto-attach to next turn's `chat.send`
- Settings tab
- Turn footer thumbnail rendering
- Lightbox
- New WS handler `preview.screenshot`

This change MAY be implemented after V1 baseline is shipped. The value/cost ratio is "high quality boost, ~$0.005/turn" — a clean opt-in for users who care about visual fidelity.
