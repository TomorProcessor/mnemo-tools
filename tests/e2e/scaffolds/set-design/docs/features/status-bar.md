# Status Bar (F13)

A 28px persistent bar at the bottom of the app. Always visible. Shows what set-design is doing right now and the operational state at a glance.

## Layout

```
┌─ Status bar (28px) ─────────────────────────────────────────────────────┐
│ [target-pill] [git-pill] [.set-design]    [claude-pill]    [cost-pill] │
│ ~/work/landing  main ●           Spec mode     thinking…        $0.42   │
└────────────────────────────────────────────────────────────────────────┘
```

Three regions: left (target/git), center (mode/state), right (cost). Each region collapses gracefully when window is narrow.

## Pills (left region)

### Target path pill

- Shows truncated target path (with `~` expansion for home).
- Icon: a small folder icon.
- Click → menu: "Open folder…", "Open in terminal", "Reveal in file manager".
- Tooltip: full absolute path.
- testid: `status-target-pill`

### Git pill

- Shows current branch name.
- Dirty indicator: orange dot (●) if `git.head.dirty === true` (uncommitted changes); green when clean.
- Click → opens git history panel (`Cmd+G` equivalent).
- Tooltip: full SHA + dirty status.
- testid: `git-branch-display`, with `data-dirty` attr `0` or `1`.

### Mode pill (only when relevant)

- Hidden in default mode.
- "Spec mode" — shown when set-handoff F17's spec-aware design mode is active. Clicking jumps to settings → Design context tab.
- "Auto-fix N/3" — shown during HMR error feedback loop.
- testid: `status-mode-pill` with `data-mode` attr `default`/`spec`/`auto-fix`.

## Pills (center region)

### Claude state pill

- Five visual states keyed by `data-state`:
  | data-state | Visual | When |
  |---|---|---|
  | `idle` | gray dot + "ready" | no active turn |
  | `thinking` | blue spinner + "thinking…" | turn streaming text |
  | `tool-use` | blue spinner + "using {tool}…" | turn currently in a tool call |
  | `error` | red dot + "error" | last turn failed OR WS disconnected |
  | `disconnected` | red dot + "reconnecting…" | WS dropped, attempting reconnect |
- Hover tooltip: detail. For `tool-use`, show the tool name + target. For `error`, show error code.
- Click during `error` or `disconnected`: triggers retry / reconnect.
- testid: `claude-state-pill` with `data-state` attr.

## Pills (right region)

### Cost pill

- Shows running session cost: `$0.42`.
- Two scopes accessible via dropdown:
  - **This session** — sum of cost from turns in the current claude session (since `session_id` was set).
  - **All time** (this target) — sum across all chats and sessions for this target dir.
- Click → opens budget tab in settings.
- Right-click → "Reset session cost display" (does not affect actual cost; just zeroes the displayed counter).
- testid: `cost-display` with `data-cost-usd` attr (raw float).
- Format: `$0.00` for 0–9.99, `$0.0` for 10–99.9, `$0` for 100+. Tooltip always shows full precision.

### "Undo last" button

- A small ghost button next to the cost pill: `↶ Undo`.
- Triggers `git.revert HEAD --no-edit` after confirmation if the previous commit was a revert.
- Disabled when `git.log` is empty or HEAD is the initial commit.
- testid: `undo-last-button`

### "Set handoff" button

- Right-most pill: a small button labeled "Push to SET" or just a small SET icon.
- Click → opens the set-handoff dialog (F17).
- testid: `set-handoff-button`

## Connection state

The whole status bar gets a 1px top-border colored by connection state:

| State | Color |
|---|---|
| WS connected | neutral border |
| WS reconnecting | orange border + subtle pulse animation |
| WS error / failed | red border |

This is a glanceable signal that the engine is reachable.

## Responsive behavior

- Below 1024px width: target pill truncates harder (last segment only); mode pill hidden when "default".
- Below 800px: cost pill collapses to icon only; tooltip shows the value.
- The status bar is NEVER hidden, even in fullscreen preview mode.

## Required `data-testid`

| testid | Purpose |
|---|---|
| `status-bar` | root |
| `status-target-pill` | target path |
| `git-branch-display` | branch + dirty |
| `status-mode-pill` | mode pill (spec / auto-fix) |
| `claude-state-pill` | claude state |
| `cost-display` | cost pill |
| `undo-last-button` | undo |
| `set-handoff-button` | handoff trigger |
| `status-bar-conn-{connected\|reconnecting\|error}` | data attribute on root |

## Errors handled

The status bar surfaces error state but does not handle them itself; click-through delegates:

| Code | Click action |
|---|---|
| `WS_DISCONNECTED` | trigger reconnect |
| `CLAUDE_BUDGET_EXCEEDED` | open budget settings tab |
| `CLAUDE_SUBPROCESS_CRASHED` | scroll chat to last failed turn |

## Dependencies

- F14 protocol (`event.activity`, `event.turn.*`, `event.budget.update`, `git.head`, `system.budget`)
- F00 open-folder (target_path, branch)
- F08 orchestrator (turn / claude state)

## Change scope (decomposition hint)

Single change: `status-bar`. Small change. Often bundled with `polish` or `foundation-setup` (the layout shell). May be implemented as part of the foundation change since the bar is part of the core layout, but logic-wise it has its own concerns.
