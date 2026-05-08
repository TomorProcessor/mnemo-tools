# SET Handoff (F17)

set-design's primary purpose is to produce **design source input** for the SET orchestration framework. Every set-design target is, by construction, a candidate `design_source` for a SET scaffold — but the user needs an explicit handoff action to verify readiness and produce the `scaffold.yaml` stub.

This feature is what makes set-design more than "yet another v0 clone": it is **a v0 generator that knows about SET's design pipeline**.

**V1 scope:** local-only. set-design does NOT push to remotes (no GitHub/GitLab integration, no `gh` CLI, no token vaults). The user pushes their target with their own tools (`git push`, IDE, terminal) — set-design's responsibility ends at "your local repo is ready, here is the YAML stub". Remote-management UI is deferred to V2.

## What is a SET design_source?

Per `docs/guide/external-spec-author-guide.md` §6, a SET scaffold's `design_source` is a self-contained Next.js + shadcn + Tailwind TSX repo with:

- `app/` — routes (each top-level segment becomes a `design-manifest.yaml` page entry)
- `components/` — reusable components, `components/ui/` for shadcn primitives
- `lib/` — utilities, design tokens (CSS vars, theme.ts)
- `public/` — static assets (images, fonts)
- `package.json` with Next.js + shadcn + Tailwind in deps
- `tailwind.config.ts` with the project's token palette
- `globals.css` with CSS variables for tokens

set-design's target dir IS this layout (or starts as such). The handoff feature ensures the export complies with the shape SET expects.

## The handoff action

A button in the status bar / settings: **"Push to SET"**. Opens a dialog with two simple options.

### Step 1 — Validate (lint pass)

Run a structural lint pass on the target:

| Check | Severity | Auto-fixable |
|---|---|---|
| Has `package.json` with `next` in deps | error | no |
| Has `tailwind.config.{ts,js}` | warning | yes (insert default) |
| Has `app/layout.tsx` | error | no |
| Has at least one route under `app/` | error | no |
| `components/ui/` exists or shadcn imports resolved | warning | suggest `npx shadcn add` |
| No `node_modules/` committed | error | yes (`.gitignore` patch) |
| No `.env*` files staged | error | yes (`.gitignore` patch) |
| `globals.css` has `:root` CSS variables for color tokens | warning | suggest snippet |
| `.set-design/` is gitignored | error | yes (auto-patch) |
| At least one git commit exists | error | no |
| HEAD is on a branch (not detached) | error | no |

The dialog renders the lint result with error/warning/ok rows and "Apply auto-fixes" buttons. The dialog cannot proceed to Step 2 until all error-severity checks pass.

### Step 2 — Choose output

Two options only. **Both are local operations; set-design never contacts a remote.**

#### Option A — Copy `scaffold.yaml` stub (primary, default)

Renders a copy-pastable YAML block:

```yaml
project_type: web
template: nextjs
ui_library: shadcn

design_source:
  type: v0-git
  repo: <YOUR REMOTE URL HERE>
  ref: main
```

Below the block, a small note:

> *Push your target to a remote yourself when ready (`git push`). Then replace `<YOUR REMOTE URL HERE>` with the URL.*

Two action buttons:
- **Copy to clipboard** (primary) — copies the YAML to the clipboard, shows toast "Copied".
- **Save to ~/&lt;basename&gt;-scaffold.yaml** (secondary) — writes the YAML to the user's home directory.

#### Option B — Export as ZIP

Folder picker → set-design runs `git archive HEAD -o <chosen-path>/<target-basename>.zip`. The resulting ZIP is what the user can reference in `scaffold.yaml`:

```yaml
design_source:
  type: v0-zip
  path: /Users/me/exports/landing-page.zip
```

This is the local-only handoff route — useful for users who don't push to a remote at all.

## Spec-aware design mode (optional, V1)

When opening a target, set-design checks for sibling SET spec files:

- `<target>/../docs/v1-*.md` — sibling scaffold spec
- `<target>/../docs/features/*.md`
- `<target>/spec/v1-*.md` — embedded spec
- `<target>/SPEC.md`

If found, the user sees a banner: **"Spec detected. Design against it?"**

On accept:
- The spec's master file + features files are read into `design_context_blob` (in addition to design tokens).
- The **first turn** of every chat in this target gets the spec context appended to the system prompt.
- The Frame shows a "Spec mode" badge in the status bar — this means claude is designing UI to match a written spec, not free-form.

This closes a powerful loop: a SET scaffold author can run set-design against a `tests/e2e/scaffolds/<name>/` and design UIs that are pre-aligned to the master spec, dramatically reducing the gap-analysis cleanup later.

**Out of V1 (defer to V2):**
- Reading spec route lists and auto-generating placeholder routes.
- Auto-detecting design tokens *from* the spec (per-feature design contracts).
- Bidirectional sync (spec change → design suggestion).

## Required `data-testid`

| testid | Surface |
|---|---|
| `set-handoff-button` | status bar trigger |
| `set-handoff-button` | data attribute `data-handoff-ready` ("true" / "false") for E2E |
| `set-handoff-dialog` | dialog root |
| `lint-row-{check-id}` | each lint row |
| `lint-fix-{check-id}` | per-row "Apply" button |
| `handoff-option-stub` | "Copy scaffold.yaml" option |
| `handoff-option-zip` | "Export as ZIP" option |
| `handoff-yaml-copy` | copy-to-clipboard button |
| `handoff-yaml-save` | save-to-home button |
| `handoff-zip-folder-picker` | ZIP destination input |
| `handoff-zip-create` | "Export ZIP" button |
| `spec-detected-banner` | spec-mode banner (if applicable) |
| `spec-mode-badge` | status bar badge (if active) |

## Errors

| Code | Surface | When |
|---|---|---|
| `HANDOFF_LINT_FAILED` | dialog inline | one or more error-severity checks failed; dialog cannot advance |
| `ZIP_WRITE_FAILED` | toast | filesystem write error during zip export |
| `CLIPBOARD_BLOCKED` | toast | browser refused clipboard access (rare, fallback to "save to home") |

## Dependencies

- F00 open-folder (target_path, git repo, lock file)
- F08 orchestrator (git operations via `simple-git`: status, log, archive)
- F14 protocol (new request types: `handoff.lint`, `handoff.zip`, `handoff.scan_spec_context`)

## Change scope (decomposition hint)

Single change: `set-handoff`. Delivers:
- Lint pass implementation (one Zod-validated runner per check)
- "Apply auto-fix" actions for fixable checks
- `scaffold.yaml` stub generator (template literal + path-derived basename)
- ZIP export via `simple-git` `archive` (or `child_process.spawn('git', ['archive', ...])` if simple-git lacks coverage)
- Spec-aware design mode (read sibling spec, inject into design_context_blob, render banner + badge)
- New WS handlers: `handoff.lint`, `handoff.zip`, `handoff.scan_spec_context`

This is a small change relative to `chat-engine` or `orchestrator-engine`. Implemented after the core scaffold is working — i.e., near the end of the orchestration plan.

## Future (V2 — not in V1)

V2 may add a "Push to remote" pane:
- `gh` CLI integration for GitHub
- `glab` CLI integration for GitLab (and self-hosted GitLab)
- Bitbucket Cloud / Server via REST
- Generic `git push` to a configured remote
- Token-vault for credential storage

V1 deliberately omits all of the above to keep set-design installable and runnable with **zero external service dependencies**.
