# Design Direction — set-design

> The brand vibe and per-page direction that drives the v0.app design source. The TSX repo referenced by `scaffold.yaml`'s `design_source` is generated from v0 prompts derived from this file.

## Brand vibe

set-design is a **calm IDE-class tool**. Not a marketing site. Not a flashy creative app. The user spends hours here doing focused work; the chrome should fade.

| Axis | Direction |
|---|---|
| Personality | technical, precise, confident; no playful tone |
| Density | dense — IDE-comparable; favor small, tight UI over breathing room |
| Color | neutral-heavy palette (zinc/slate/stone); accent only for state (running/error/success) |
| Typography | sans-serif for body (Inter or system-ui); monospace (JetBrains Mono or system-mono) for paths, IDs, code, numbers |
| Borders | 1px subtle borders, no shadows except for floating elements (popovers, dialogs, dropdowns) |
| Radii | small — `rounded-sm` (2px) for buttons / inputs; `rounded-md` (6px) for cards; nothing more |
| Motion | minimal — only state transitions (loading → done), no decorative animations |
| Iconography | lucide-react; line-style only; consistent stroke weight |

## Reference apps for visual cues

- **VS Code** — panel layout, hover states, subtle borders
- **Linear** — typography rhythm, status pills, density
- **Cursor** — chat interaction patterns, diff displays
- **Sentry / Datadog** — status bar, monospace metadata

NOT v0.app's marketing surface (gradient hero, floating panels). Functional editor instead.

## Color palette

Use shadcn CSS variables. Two themes: light + dark.

### Light

```
--background: 0 0% 100%
--foreground: 220 13% 9%
--muted: 220 14% 96%
--muted-foreground: 220 8% 46%
--border: 220 13% 91%
--accent: 220 14% 96%
--ring: 217 19% 27%
```

### Dark

```
--background: 220 14% 8%
--foreground: 220 14% 96%
--muted: 220 14% 14%
--muted-foreground: 220 9% 60%
--border: 220 13% 18%
--accent: 220 14% 14%
--ring: 220 9% 60%
```

### State colors (semantic)

| Token | Light | Dark | When |
|---|---|---|---|
| `--success` | `142 71% 45%` | `142 60% 50%` | success pills, committed checkmarks |
| `--warning` | `38 92% 50%` | `38 92% 60%` | dirty git state, auto-fix in progress |
| `--destructive` | `0 84% 60%` | `0 70% 50%` | errors, failed turns, revert prompts |
| `--info` | `217 91% 60%` | `217 91% 70%` | thinking/streaming spinner |

## Typography

```
--font-sans: "Inter", system-ui, -apple-system, sans-serif
--font-mono: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace

text-xs:   12px / 16px line-height
text-sm:   13px / 20px
text-base: 14px / 22px (default)
text-lg:   16px / 24px
```

set-design uses 14px as default body — tighter than typical web (which is 16px). This is intentional IDE-like density.

## Spacing scale

Tighter than shadcn's defaults.

```
0.5: 2px
1:   4px
2:   8px
3:   12px
4:   16px (most common gap)
6:   24px
8:   32px
```

Rarely > 32px between elements. The product is dense.

## Per-page direction

Each surface below corresponds to a v0.app prompt (full prompts in this section). The user generates all from a single v0 chat in sequence; v0 builds incrementally.

### 1. Welcome screen

Single hero state, pre-target. Prompt:

> Create the welcome screen for "set-design", a developer tool. IDE-aesthetic, dark theme by default with light option. Center of screen: tight stacked composition — "set-design" wordmark (text only, no logo, font-mono medium weight) above subtitle "Design Next.js + shadcn UIs with Claude. Locally." (font-sans, muted color). Below subtitle, two buttons stacked: primary "Open folder…" (default shadcn Button), secondary "New from template" (variant outline). Below the buttons, a "Recent" link that toggles a dropdown listing 5 recent target paths in monospace, each row shows the path and last-opened relative timestamp. At the bottom of viewport, in muted small text: "What you need: Claude CLI · Node 18+ · An empty or existing Next.js folder". Use shadcn Button, DropdownMenu primitives. No marketing copy, no illustration, no gradient. Just the centered composition on a clean background.

### 2. Main shell — split layout with status bar

The default workspace state. Prompt:

> Build the main workspace shell for set-design. Layout: top header (60px), main area split into left chat panel (40% width) and right preview panel (60% width) with a draggable resizable handle between them, and a bottom status bar (28px, persistent). Top header content: project switcher dropdown left (target folder name + chevron), Claude model selector center (Opus/Sonnet/Haiku as ToggleGroup with cost hints in tooltip), and right-side icons for Settings (gear), Help (?), and Toggle theme (sun/moon). Status bar: left segment with target path (monospace, truncated) and git branch + dirty dot; center segment with claude state pill (ready/thinking/error) and optional mode badge (Spec mode / Auto-fix N/3); right segment with running cost ($0.42), undo button (↶), and "Push to SET" button. Whole shell uses subtle 1px borders between regions, no shadows. Dark theme primary, monospace for paths and IDs, sans for everything else. Density tight — no padding > 16px.

### 3. Chat panel

The left half of the workspace. Prompt:

> Inside the left chat panel: top bar with active chat title dropdown (truncated first user message) and "+ New chat" button (small, ghost). Scrollable message list below: user messages right-aligned in subtle gray bubbles max-width 70%, assistant messages full-width with avatar + timestamp + model badge in header row, then content body. Inside assistant body: streaming text (with blinking cursor at end while running) interleaved with "activity feed" rows. Activity feed row format: icon + verb + target + status pill. Examples: "📖 Read 8 files (collapsed)", "✏️ Editing app/page.tsx" with green checkmark and +12 -4 diff badge, "🔧 $ pnpm typecheck" with running spinner. Status pills use semantic state colors. Each turn ends with a thin separator row showing "$0.034 · 12s · 2 files · sha abc123f" in muted small text — sha is monospace and clickable. Composer at bottom: textarea (auto-grow), paperclip icon left, send button right (becomes red Cancel button with ⏹ icon when turn is running), drag-drop overlay with dashed border when image is being dragged onto the panel, image thumbnails appear as 80×80 chips above the textarea before send. Empty state for new chats: centered icon, heading "Start designing", subtitle "Describe a component or paste a mockup", three example chips below.

### 4. Preview panel + toolbar

The right half of the workspace. Prompt:

> Inside the right preview panel: top toolbar (40px) with three groups — left: device size ToggleGroup (Mobile 375 / Tablet 768 / Desktop 1280 / Full); middle: theme ToggleGroup (Sun/Moon/System icons); right: refresh icon button, code/preview Toggle pair, fullscreen icon. Below toolbar: read-only URL pill (`http://localhost:3000` in monospace, truncates with ellipsis, click-to-copy with toast confirmation). Main area: iframe centered horizontally with a neutral viewport-frame around it (1px border, 8px outer padding). Below the iframe: small caption "375 × auto" showing current viewport. States to render: (a) iframe up — normal state; (b) starting — replace iframe with skeleton + spinner + "Starting dev server…"; (c) down — replace iframe with empty state showing "Dev server not running" + "Start dev server" CTA button; (d) build_failed — overlay red banner ABOVE the (still-rendered) iframe: "Build failed — auto-fix attempt 1/3" + expandable error log + Stop / Manual fix buttons.

### 5. Code mode + git history

The right panel's alternate state. Prompt:

> When user toggles "Code" mode, replace the iframe with a vertical split: left narrow panel (240px, file tree) and right wider panel (diff viewer). File tree: search input at top (filter by name), folder rows collapsible (chevron icons), file rows show file icon by extension, modified files mark with a yellow dot, deleted strikethrough. Diff viewer: top breadcrumb showing file path, "Compare" pickers (`HEAD~1 ▾  →  HEAD ▾` two dropdowns), Side-by-side / Unified toggle, Prev/Next file arrows. Body: line-numbered diff with syntax highlighting (use shadcn-compatible neutral palette, only red/green for diff hunks). Add a Versions panel slidable from the right edge: vertical list of commits, each row with green/gray indicator dot, monospace short SHA, relative timestamp, commit message (first line bold), +N -M stats badge, files-changed count, "$0.034" cost (when turn-derived), Revert and "Open in code view" buttons. Filter dropdown at the top: All / Set-design turns only / External commits only / Reverts only. Search input above filter.

### 6. Settings, modals, and polish

Closing prompt for v0. Prompt:

> Add a Settings page (route `/settings`) with vertical Tabs on the left and content area on the right. Tabs: General, Git, MCP, Design context, Vision feedback, Budget. Each tab content uses a stack of Card-wrapped form sections with shadcn Input/Select/Toggle/Textarea primitives, with per-tab Save buttons in the footer. Add Toast notifications top-right for events ("Committed abc123f", "Build failed", "Reverted to def456g"). Add a 404 page IDE-styled (just a monospace "404" wordmark and "Folder or page not found" subtitle + "Back to set-design" link). Add a global keyboard shortcuts modal triggered by Cmd+K (or Ctrl+K) listing: ⌘+Enter (Send), ⌘+/ (Toggle code/preview), ⌘+Z (Undo last commit), ⌘+G (Open versions), ⌘+, (Settings), ⌘+\ (Fullscreen preview), Esc (Exit fullscreen / close dialog). All modal/dialog/dropdown surfaces use subtle elevated shadow only when floating; everything else stays flat with 1px borders.

## What v0 should NOT generate

To keep the design source aligned with the spec:

- No "Login" / "Sign up" pages — set-design has no auth.
- No "Projects" / "Create project" page — set-design has no project entity (just a target folder).
- No deploy / publish buttons — out of scope.
- No team / collaboration UI.
- No marketing landing page outside the welcome screen.
- No splash screens longer than the welcome screen above.
- No drag-and-drop file tree with rename/move — code view is read-only.

## Handoff workflow

1. Run prompts 1–6 in v0.app sequentially in a single chat.
2. Push the resulting Next.js+shadcn project to GitHub: `<your-username>/v0-set-design`.
3. Update `scaffold.yaml`'s `design_source.repo` to that URL.
4. Run `set-design-import` from the scaffold root → it clones into `v0-export/`, generates `design-manifest.yaml`.
5. Review `v0-import-report.md` for findings; address any.
6. Run the orchestrator (`run-set-design.sh`) which dispatches changes to agents using the design source.

## Open items for v0 generation

- Empty state illustrations should be minimal — line-icon size, no characters/scenes.
- Lucide-react icons preferred for everything: chat (`message-square`), preview (`monitor`), code (`code-2`), git (`git-branch`), undo (`undo-2`), settings (`settings`), template (`layout-template`), screenshot (`camera`).
- Tooltips everywhere: every icon-only button MUST have a tooltip with shortcut (where applicable).
