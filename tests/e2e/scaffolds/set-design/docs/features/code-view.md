# Code View + Git History (F07, F09)

The "Code" mode of the right panel and the Versions panel. Read-only in V1 — set-design's principle is that **claude writes code, the user reviews diffs**, so the panel never lets you type into a file.

## Mode switcher

When the user clicks `code-view-toggle` in the preview toolbar, the right pane swaps content (iframe stays mounted with `display: none`):

```
┌─ Code mode of right pane ─────────────────────────┐
│ ┌─ Toolbar (40px, shared with Preview) ──────────┐│
│ │ same toolbar, "Code" highlighted in switcher   ││
│ └────────────────────────────────────────────────┘│
│ ┌─ File tree (240px) ─┬─ Diff viewer (flex) ────┐│
│ │ ▼ app                │ app/page.tsx             ││
│ │   ▶ (api)            │ ┌──────────────────────┐ ││
│ │   ▼ blog             │ │ -import { ... }      │ ││
│ │     page.tsx ●       │ │ +import { Hero }     │ ││
│ │   layout.tsx         │ │  ...                 │ ││
│ │   page.tsx ●         │ │                      │ ││
│ │ ▼ components         │ │ Side-by-side / unified│ ││
│ │   ▼ ui               │ │  +12 -4              │ ││
│ │     button.tsx       │ └──────────────────────┘ ││
│ │   Hero.tsx ●         │                           ││
│ │ ...                  │                           ││
│ └──────────────────────┴───────────────────────────┘│
└────────────────────────────────────────────────────┘
```

## File tree (left of code mode)

- Reads `files.tree` once on mode-enter, then patches incrementally on `event.files.changed`.
- Folders collapsible; state persisted per target in localStorage.
- File icons by extension (a small shadcn-compatible icon set — no full IDE icon-themes).
- Modified-files marker: yellow dot (●) on rows where the file changed in the most recent turn (or selected commit, see below).
- Deleted files appear with strikethrough; remain visible until next turn.
- Search box at the top of the tree: filters tree by file name (substring, case-insensitive). No content search in V1.
- Click a file → loads its diff in the right pane.

The tree respects `.gitignore` AND additional patterns from `<target>/.set-design/.viewignore` (an optional file the user can curate to hide noise like `pnpm-lock.yaml`).

## Diff viewer

- Reads `files.diff { path, base_sha?, head_sha? }`.
- Default view: `head_sha = HEAD`, `base_sha = HEAD~1`. Shows the most recent change to the file.
- Toggle: `Side-by-side | Unified`. Persisted in localStorage. Default `Unified` (matches typical PR review UX).
- Syntax highlighting via Prism or Shiki (target file extensions: `.ts`, `.tsx`, `.js`, `.jsx`, `.css`, `.json`, `.md`, `.yaml`, `.svg`).
- Line numbers shown.
- File path breadcrumb at the top (clickable segments to file tree filter).
- Prev/Next file arrows: navigate to the prev/next file in the current commit's `files_changed` list.

### "Compare to" picker

Above the diff viewer:

```
[ HEAD~1 ▾  →  HEAD ▾ ]
```

Two dropdowns let the user compare any two SHAs from `git.log`. Default is `HEAD~1 → HEAD`. Selecting `working tree → HEAD` shows uncommitted local edits (rare in set-design's auto-commit world, but handles the `auto_commit: false` case).

A small button `Reset → latest turn` snaps back to the most recent turn's diff range.

### Empty / error states

| State | Visual |
|---|---|
| File never changed | "No changes for this file" |
| File doesn't exist (deleted) | "Deleted in {commit}" with link |
| Diff viewer crashed | error toast + falls back to plain unified text |

## Git history view (F09)

A separate panel slidable from the right edge or accessed via `Cmd+G`. Renders a list of commits.

```
┌─ Versions ───────────────────────────────────┐
│ [ Search messages…             ] [Filter ▾]  │
│ ─────────────────────────────────────────────│
│ ● abc123f  2 minutes ago                     │
│   Add hero with CTA  +12 -4 (2 files)        │
│   $0.034 · turn 01HXY                        │
│   [Revert to this]    [Open in code view]    │
│ ─────────────────────────────────────────────│
│ ● def456g  5 minutes ago                     │
│   Update header layout  +8 -2 (1 file)       │
│   $0.018 · turn 01HXX                        │
│   [Revert to this]    [Open in code view]    │
│ ...                                          │
└──────────────────────────────────────────────┘
```

### Row content

- Commit indicator dot (color: green if turn succeeded, gray if external commit, red if turn was a revert).
- Short SHA (monospace, 7 chars).
- Relative timestamp ("2 minutes ago"), tooltip = absolute.
- First line of commit message (bold).
- Body of message (collapsed, expand on click).
- `+N -M` stats badge.
- Files-changed count.
- Cost (if turn-derived; absent for external commits).
- Turn id (small, gray).
- Two action buttons:
  - **Revert to this** → confirmation dialog → `git.revert { sha }` → emits new revert commit, shifts HEAD, triggers preview reload. Errors: `GIT_REVERT_CONFLICT` (dialog with "Abort" button).
  - **Open in code view** → switches the right pane to Code mode with `base_sha = parent_of_this`, `head_sha = this`.

### Filter

The filter dropdown:

- All commits (default)
- Only set-design turns (commits with a turn_id mapping)
- Only manual / external commits (no turn_id)
- Reverts only

### "Undo last" shortcut

A button in the status bar (and `Cmd+Z`, intercepted globally when chat composer is not focused): runs `git revert HEAD --no-edit`. Requires confirmation if the previous commit was a revert (avoid revert-of-revert footgun).

## Read-only enforcement

The code view is **strictly read-only** in V1. No textarea, no inline edit, no "save" button, no clipboard-write. The only way to change code is to ask claude. This is a deliberate UX constraint — set-design is a designer tool, not an IDE.

If a user wants to edit by hand, they open the file in their own editor. The file watcher will detect the change and emit `event.files.changed { turn_id: null }`. The next turn footer will note "External edits detected".

## Required `data-testid`

| testid | Surface |
|---|---|
| `code-view-mode` | root container of code mode |
| `file-tree` | tree root |
| `file-tree-search` | search input |
| `file-tree-item-{slug-of-path}` | each row |
| `file-tree-item-{slug}-modified` | dot present when file modified |
| `diff-viewer` | diff container |
| `diff-toggle-{side-by-side\|unified}` | view toggle |
| `diff-prev-file` / `diff-next-file` | nav arrows |
| `diff-compare-base` / `diff-compare-head` | dropdowns |
| `diff-compare-reset` | snap-back button |
| `git-history-panel` | versions panel root |
| `git-history-search` | search input |
| `git-history-filter` | filter dropdown |
| `git-history-row-{short-sha}` | each row |
| `git-history-row-{short-sha}-message` | message |
| `git-history-row-{short-sha}-stats` | +N -M badge |
| `git-revert-{short-sha}` | Revert button |
| `git-revert-confirm-dialog` | confirmation dialog |
| `git-revert-confirm-button` | confirm button |
| `git-revert-conflict-dialog` | conflict dialog |
| `git-revert-conflict-abort` | abort button |
| `undo-last-button` | status bar undo |

## Errors handled

| Code | UX |
|---|---|
| `GIT_REVERT_CONFLICT` | dialog with conflict files listed + "Abort" button (runs `git revert --abort`) |
| `GIT_NOT_HEAD` | banner above git-history-panel: "Repo HEAD changed externally" + "Reload" button |

## Dependencies

- F14 protocol (`files.tree`, `files.read`, `files.diff`, `git.log`, `git.revert`, `git.head`)
- F08 orchestrator (file watcher pushes incremental tree updates; git operations)
- F00 open-folder (target_path)

## Change scope (decomposition hint)

Single change: `code-view-and-history`. Delivers:
- Code mode shell with file tree + diff viewer
- Tree component with collapsible folders, gitignore filtering, modified-marker, search
- Diff viewer with monaco/shiki-based rendering, side-by-side/unified toggle, compare-pickers, prev/next nav
- Git history panel with filtering, search, row actions
- Revert flow with conflict handling
- Undo-last shortcut
- New WS handlers if needed (most are reads of existing types)

Medium-large change. Could be split into `code-view` (tree + diff) and `git-history` (versions panel + revert) if planner wants parallel agents — these have low coupling.
