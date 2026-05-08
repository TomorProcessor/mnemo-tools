# Gap Analysis — Spec ↔ Design Alignment

> Pre-handover report comparing the written spec (`v1-set-design.md` + `features/*.md`) against the v0-generated design source (referenced by `scaffold.yaml`'s `design_source`). Filled in AFTER the v0 design is generated and `set-design-import` has been run.

This file is initially a placeholder. It MUST be filled before the orchestrator runs — the planner reads it to know which gaps require agent intervention vs. design-source updates.

## Status: NOT YET COMPLETED

- [ ] v0 design source generated (run prompts in `design-direction.md` §6)
- [ ] Pushed to `<owner>/v0-set-design` GitHub repo
- [ ] `scaffold.yaml`'s `design_source.repo` updated to actual URL
- [ ] `set-design-import` run from scaffold root → `v0-export/` populated
- [ ] `v0-import-report.md` reviewed for findings
- [ ] This gap-analysis filled in (see template below)

## Template (to be completed after design generation)

### 1. Routes

| Spec route | Design page | Match? | Notes |
|---|---|---|---|
| `/` (welcome) | | | |
| `/settings` | | | |
| `/<no-target>` 404 | | | |
| Workspace shell (chat + preview, no specific URL) | | | |

For each spec-listed route, confirm a corresponding design page exists in `v0-export/app/`. List discrepancies.

### 2. Components

| Spec component | Design component | Status |
|---|---|---|
| Chat panel | | |
| Preview iframe + toolbar | | |
| Code view (file tree + diff) | | |
| Versions panel | | |
| Status bar | | |
| Settings tabs | | |

### 3. Data shapes

| Spec entity | Design fixture present? | Match? |
|---|---|---|
| `TargetConfig` | | |
| `Chat` (JSONL events) | | |
| `Message` | | |
| `Turn` | | |
| `Activity` | | |
| `Attachment` | | |

For each, confirm the design source has fixtures or sample data shaped consistently. Mismatches usually mean the design needs an update.

### 4. States

| Spec state | Design state present? | Notes |
|---|---|---|
| Welcome (no target) | | |
| Workspace — Preview mode, dev server up | | |
| Workspace — Preview mode, dev server starting | | |
| Workspace — Preview mode, dev server down | | |
| Workspace — Preview mode, build failed | | |
| Workspace — Code mode | | |
| Versions panel open | | |
| Settings page (each tab) | | |
| Empty chat | | |
| Streaming turn | | |
| Failed turn | | |
| Auto-fix loop | | |

### 5. Errors

| Error code | Surface in design? | Notes |
|---|---|---|
| `TARGET_NOT_GIT_REPO` | | |
| `TARGET_LOCKED` | | |
| `CLAUDE_NOT_FOUND` | | |
| `BUILD_FAILED` | | |
| `IMAGE_TOO_LARGE` | | |
| `WS_DISCONNECTED` | | |

### 6. Selectors / testids

Confirm the design's interactive elements expose `data-testid` attributes consistent with the spec's testid registry. Document any missing.

| testid | Present in design? |
|---|---|
| `welcome-screen` | |
| `open-folder-button` | |
| `chat-panel` | |
| `chat-composer-input` | |
| `chat-send` | |
| `preview-panel` | |
| `preview-iframe` | |
| `device-toggle-{...}` | |
| `theme-toggle-{...}` | |
| `code-view-toggle` | |
| `file-tree` | |
| `diff-viewer` | |
| `git-history-panel` | |
| `git-history-row-{sha}` | |
| `git-revert-{sha}` | |
| `status-bar` | |
| `claude-state-pill` | |
| `cost-display` | |

(Full registry in `v1-set-design.md` E2E Test Conventions section.)

### 7. Tokens

| Token category | Spec value | Design value | Match? |
|---|---|---|---|
| `--background` (light) | `0 0% 100%` | | |
| `--foreground` (light) | `220 13% 9%` | | |
| `--background` (dark) | `220 14% 8%` | | |
| `--foreground` (dark) | `220 14% 96%` | | |
| `--success` | `142 71% 45%` | | |
| `--destructive` | `0 84% 60%` | | |
| body font | `Inter` | | |
| mono font | `JetBrains Mono` | | |
| default text size | `14px` | | |
| primary radius | `rounded-sm` (2px) | | |
| card radius | `rounded-md` (6px) | | |

### 8. Conventions

- [ ] Density: design uses ≤16px gaps in normal layouts (no marketing-style breathing room)
- [ ] Borders only, no shadows except on floating elements
- [ ] Monospace strictly for paths, IDs, code, numbers
- [ ] No emojis in copy
- [ ] No Lorem Ipsum
- [ ] No login/signup pages
- [ ] No deploy/share buttons

## Severity classification

When filled in, mark each gap:

- **CRITICAL** — Spec contract violated; agent cannot proceed without fix. Must fix the design source before orchestrator runs.
- **MAJOR** — Significant deviation; agent must adapt design during implementation. Adds risk and tokens.
- **MINOR** — Cosmetic; agent ignores or adapts trivially.

The orchestrator's planner reads severity classifications and either:
- Refuses to start (any CRITICAL) — surfaces "Resolve gaps in v0-export/ before re-running".
- Proceeds with annotated input.md (MAJOR/MINOR documented for the agent).

## After completion

This file becomes input to `set-design-import` and `decompose`. Re-run gap analysis whenever the design source is updated.
