# Preview Pane (F04, F05, F06)

The right panel — a live iframe of the target's dev server with a toolbar for device size, theme, and refresh. The preview is what the user is actually designing; everything else exists to feed this.

## Layout

```
┌─ Preview panel ──────────────────────────────────┐
│ ┌─ Toolbar (40px) ────────────────────────────┐ │
│ │ [📱][📲][💻][⛶] [☀️][🌙][🖥]  [↻]  [</>][⛶] │ │
│ │ ──────────────────────────────────────────── │ │
│ │ http://localhost:3000   (read-only pill)     │ │
│ └────────────────────────────────────────────┘ │
│                                                  │
│ ╔═══════════════════════════════════════════╗   │
│ ║                                           ║   │
│ ║   <iframe src=dev_url width=...           ║   │
│ ║                                           ║   │
│ ║                                           ║   │
│ ╚═══════════════════════════════════════════╝   │
│                                                  │
└──────────────────────────────────────────────────┘
```

## Iframe (F04)

- `<iframe data-testid="preview-iframe" name="preview" src={config.dev_url}>`.
- Sandbox: NONE in V1 (target dev server is on the same machine, same user). V2 may add sandbox attributes for hosted Frame mode.
- `onLoad` → emit a Frame-internal `iframe.loaded` event for telemetry.
- Hot reload: HMR is provided by the target's Next.js dev server; the iframe receives reloads natively. No iframe-side intervention.
- "Refresh" button forces `iframe.contentWindow.location.reload()`. Useful when HMR misses (rare but happens with config changes).

### Communication with the iframe

The Frame attempts a one-way listen on `window.message` events from the iframe (origin `dev_url`). Used for:

- Runtime error capture: a tiny script that the target's `app/layout.tsx` can opt-in to (`@/lib/set-design-bridge.ts`) — when present, it posts uncaught errors to the parent. The Frame relays them as `event.preview.error{kind: "runtime"}`.
- Element selection (V3 — out of V1). Reserved postMessage type `set-design.element.selected`.

If the bridge script is not present in the target, runtime errors are detected via the Next.js dev-server overlay scrape (orchestrator does this).

### States

| State | Visual |
|---|---|
| `up` | iframe rendered |
| `starting` | iframe replaced by skeleton with "Starting dev server…" + spinner |
| `down` | iframe replaced by empty state: "Dev server not running" + "Start dev server" button |
| `crashed` | red banner on top: "Dev server crashed — last log line: …" + "Restart" button |
| `build_failed` | overlay banner over iframe (iframe still rendered but stale): "Build failed — auto-fix attempt N/3" + Stop / Manual fix buttons (HMR feedback) |

## Device size toolbar (F05)

ToggleGroup with four options:

| testid | Width | Height policy |
|---|---|---|
| `device-toggle-mobile` | 375px | full height of pane minus toolbar |
| `device-toggle-tablet` | 768px | full height |
| `device-toggle-desktop` | 1280px | full height |
| `device-toggle-full` | 100% of pane width | full height |

- Selection persists per target in `localStorage` keyed by target_path hash.
- Default is `desktop` if pane width >= 1280px else `full`.
- Iframe is centered horizontally with a neutral viewport-frame (subtle 1px border + 8px outer padding).
- Visually: a small 1-line label "375 × auto" below the iframe shows the current size; updates on toggle.

## Theme toggle (F06)

ToggleGroup with three options:

| testid | Effect |
|---|---|
| `theme-toggle-light` | iframe receives `?set-design-theme=light` query param |
| `theme-toggle-dark` | iframe receives `?set-design-theme=dark` query param |
| `theme-toggle-system` | no query param; iframe inherits from OS `prefers-color-scheme` |

- The target app SHOULD respect the query param (read it and apply class to `<html>`). set-design provides a documented helper `lib/set-design-bridge.ts` that does this; the templates feature pre-installs it, but if not present the toggle has no visible effect.
- In V2 with chrome extension, the theme can be enforced via Playwright/CDP `Page.emulateMedia` — V1 is best-effort with query params.
- Default is `system`.

## Refresh

A button next to the toggles. Triggers `iframe.contentWindow.location.reload()`. No keyboard shortcut in V1.

## Code/Preview switcher

A toggle at the right of the toolbar:

```
[ Preview | Code ]
```

- "Preview" = iframe rendering (this feature)
- "Code" = file tree + monaco diff view (F07)

Switching mode does NOT unload the iframe; it stays mounted with `display: none` to preserve scroll/state. The iframe lifecycle remains tied to the dev server, not the pane mode.

Keyboard shortcut: `Cmd+/` toggles.

Fullscreen button at the very right: `Cmd+\` toggles. Fullscreen hides the chat panel; the preview occupies the full window. Press Esc to exit.

## URL pill

```
[ http://localhost:3000 ]
```

- Read-only (in V1).
- Click → copies URL to clipboard with a small "Copied" toast.
- Truncates with ellipsis if longer than the available width.

In V2 settings, advanced users may override `dev_url` (e.g. for non-localhost ports). For V1 the source of truth is `config.dev_url`.

## Error states

| Code | UX |
|---|---|
| `DEV_SERVER_DOWN` | replaces iframe with empty-state CTA |
| `DEV_SERVER_PORT_BUSY` | replaces iframe with error explaining; "Open settings" button |
| `BUILD_FAILED` | overlays a red banner above the (still-rendered) iframe, expandable error log |
| `RUNTIME_ERROR_OVERLAY` | overlays an orange banner with the runtime error message + stack frame |

The build/runtime error banners are non-modal — the user can still chat with claude. The HMR auto-retry loop (orchestrator F10) operates in the background; the banner updates with retry count.

## Required `data-testid`

| testid | Purpose |
|---|---|
| `preview-panel` | root container |
| `preview-toolbar` | top toolbar |
| `device-toggle-{mobile\|tablet\|desktop\|full}` | size toggles |
| `theme-toggle-{light\|dark\|system}` | theme toggles |
| `preview-refresh` | refresh button |
| `preview-fullscreen` | fullscreen toggle |
| `code-view-toggle` | preview/code switcher (controls the right pane mode) |
| `preview-url-pill` | URL display |
| `preview-iframe` | the iframe element |
| `preview-empty-down` | dev-server-down empty state |
| `preview-start-server-button` | "Start dev server" CTA |
| `preview-build-error-banner` | build error banner |
| `preview-build-error-log` | expandable log |
| `preview-runtime-error-banner` | runtime error banner |
| `preview-auto-fix-stop` | Stop button during auto-fix loop |
| `preview-auto-fix-manual` | Manual fix button |
| `viewport-size-label` | "375 × auto" label |

## Errors handled

(See state table above. All preview errors come from `event.preview.error`, `preview.status`, and orchestrator-level events.)

## Dependencies

- F14 protocol (`preview.status`, `preview.start`, `preview.stop`, `preview.reload_request`, `event.preview.*`)
- F08 orchestrator (dev server lifecycle, build error scraping, HMR retry)
- F00 open-folder (`config.dev_url`)

## Change scope (decomposition hint)

Single change: `preview-pane`. Delivers:
- Iframe component with state machine (up/starting/down/crashed/build_failed)
- Device toggle group with localStorage persistence + viewport-frame
- Theme toggle with query param injection
- Refresh + fullscreen + code/preview toggle
- URL pill (read-only)
- Build / runtime error banners (rendering only — orchestrator detects)
- Postmessage listener with the documented `set-design-bridge` API

The bridge script (`@/lib/set-design-bridge.ts`) is delivered as part of `templates` (F16) so generated targets pre-install it. Without it, the toolbar still works (theme/refresh/etc.) but runtime error capture is overlay-scrape only.
