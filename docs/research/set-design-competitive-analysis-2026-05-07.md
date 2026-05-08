# set-design — Competitive Analysis & Strategic Positioning

> **Status:** Research complete · Strategic direction confirmed · 2026-05-07
> **Author:** synthesis from `set-design` scaffold authoring session
> **Companion artifacts:** `tests/e2e/scaffolds/set-design/` (19-file spec)
> **Decision:** Build set-design as a real product, not just a SET test target.

---

## TL;DR

set-design fills a **specific, unoccupied market intersection**: a free + browser-native + Next.js+shadcn-output + BYO-Claude + git-first + SET-design-pipeline-compatible design tool. No existing product (paid or open-source, hosted or local) sits in this exact niche. The 30k-star **Open Design** project initially looked like prior art, but a closer look at its output format (sandboxed HTML artifacts, not Next.js projects) reveals it occupies an adjacent but non-overlapping niche. Building set-design is justified both as a SET orchestration test target and as a standalone open-source product.

---

## 1. Problem statement

The SET orchestration framework consumes a **`design_source`** — a real Next.js + shadcn + Tailwind TSX repository — to drive its design-fidelity gate, design-manifest extraction, and per-change `design.md` generation (see `docs/guide/external-spec-author-guide.md` §6). Today, scaffold authors are expected to generate this repo using **v0.app** (Vercel), which is paid above a small free tier and lives in a closed-source vendor sandbox.

Two questions emerged:

1. **Tactical**: How does the user generate set-design's *own* `design_source` (a v0-style export of set-design's UI) without hitting v0.app paywalls?
2. **Strategic**: Is there a viable open-source / browser-native / BYO-Claude alternative we should build (or adopt) for this and future SET scaffolds?

Both questions converged on the same competitive landscape research, summarised here.

---

## 2. v0.app feature taxonomy and what we'd keep

v0.app (2026 generation) offers ~46 distinct features. From the systematic review (full table in scaffold's master spec):

**Kept for set-design V1 (16 features):**
- Chat-driven generation
- Live preview iframe (real `pnpm dev`, not sandbox)
- Responsive views (mobile/tablet/desktop/full)
- Theme toggle (light/dark/system)
- File tree + diff viewer (read-only)
- Image / mockup upload (PNG/JPEG/WebP)
- Auto-commit per turn + git history view + revert
- HMR / build error feedback loop with auto-fix
- MCP servers passthrough
- Design tokens / system auto-context
- Status bar (cost telemetry, claude state, branch + dirty)
- Frame ↔ Brain WS protocol (V2 forward-compat)
- Vision-loop (opt-in) — Playwright screenshot self-correction
- Templates (opt-in) — `nextjs-shadcn-starter`
- SET handoff — `scaffold.yaml` stub generation, lint, GitHub push

**Deliberately rejected:**
- Database integrations
- Auth / user accounts / team collab
- Sandbox runtime (we use real `pnpm dev`)
- Folders / multi-chat-per-project / branch-per-chat
- Templates marketplace
- Slack / pre-installed agents
- Deploy / custom domains
- Visual click-to-edit (deferred to V3+)
- Figma / URL import

The carve-out emphasises **low-feature-count, focused screen-design tool** rather than full-stack agentic platform.

---

## 3. Competitive landscape — full enumeration

Sources gathered 2026-05-06: GitHub repos, npm registry, official product docs, comparison reviews.

### 3.1 Hosted / closed-source (paid)

| Product | Model | Cost | Output | Notes |
|---|---|---|---|---|
| **v0.app** (Vercel) | proprietary v0 Mini/Pro/Max | free tier ~5–10 prompts/day; paid above | real Next.js+shadcn TSX, GitHub push | best-in-class quality; agentic, MCP, deploy |
| **bolt.new** (StackBlitz) | mixed (Claude/GPT) | free tier with monthly token budget | full-stack via WebContainer | hosted sandbox, less shadcn-pure |
| **lovable.dev** | mixed | free tier limited | full-stack, GitHub sync | marketing-heavy positioning |
| **a0.dev** | mixed | unclear | sandbox | smaller v0 fork |
| **same.new** | proprietary | unclear | site clone | clones existing sites |
| **claude.site** (Anthropic) | claude | requires subscription | artifact share | not a designer, just renders |
| **tempo.new** | mixed | unclear | sandbox | visual editor + AI |

### 3.2 Anthropic-hosted (April 2026 launch)

| Product | Status | Notes |
|---|---|---|
| **Claude Design** (Anthropic Labs) | research preview, Claude Pro/Max/Team/Enterprise only | chat-left + canvas-right; turns prompts into prototypes / decks / UI mockups; "handoff bundle to Claude Code" closes their ecosystem loop |

This launched 2026-04-17, **before** our research started. It is *the* official Anthropic offering. Its existence rules out claiming "first AI-design-tool from the Claude family", but its closed nature and subscription requirement leave the **free + open-source** lane wide open.

### 3.3 Open-source / desktop

| Product | Stars | Stack | Output | Notes |
|---|---:|---|---|---|
| **Open Design** (nexu-io) | 30.2k | web + Express daemon, better-sqlite3, Apache-2.0 | sandboxed HTML artifacts (vendored React 18 + Babel) | 16 CLI agents (Claude Code, Codex, Cursor, …); 31 skills; 72 design systems; **NOT Next.js TSX output** |
| **Dyad** | 20.3k | Electron desktop, multi-LLM | varies | BYO key; Mac/Windows |
| **Open-codesign** | 3.1k | Electron, React 19 + Vite | sandboxed iframe | streaming artifact loop |
| **Onlook.dev** | growing | Electron desktop | local Next.js | visual editor + AI; closest to set-design in spirit |
| **bolt.diy** (StackBlitz Labs) | large | Node, BYO key | varies | open source bolt.new, BYO Anthropic/OpenAI/etc. |
| **December** | small | local | varies | BYO LLM key |
| **GPT Engineer** | early | CLI | varies | predecessor to Lovable |
| **v0.diy** (SujalXplores) | 0.14k | Next.js + Drizzle | depends on v0 SDK | requires paid v0 API key — NOT actually free |

### 3.4 Claude Code GUI wrappers (tangential)

| Product | Notes |
|---|---|
| **Claudia GUI** | Claude Code visual workspace |
| **Opcode** | minimalist Claude Code GUI |
| **claudecodeui** (siteboon) | web/mobile Claude Code session manager |
| **claude-code-webui** (sugyan) | streaming chat web UI |
| **claude-code-openai-wrapper** | OpenAI-API-compatible wrapper for Claude Code |

These are **terminal-replacements**, not design tools. Adjacent ecosystem, not direct competition.

---

## 4. Open Design — deep-dive (the closest-looking competitor)

Open Design (nexu-io/open-design) initially looked like our exact V2 architecture: web frontend + local daemon + BYO CLI agent (incl. Claude Code) + sandboxed iframe preview. 30.2k stars, Apache-2.0, mature. The natural assumption was we should fork it, not build from scratch.

### Architecture (verified)

- **Frontend:** Next.js 16, web app at `localhost`
- **Daemon:** Node.js + Express + better-sqlite3, spawns 16 different CLI agents via `child_process.spawn`
- **Streaming:** unified SSE protocol normalizing Claude stream-json + ACP + plain JSON
- **Persistence:** `.od/` SQLite per project (NOT git)
- **Skills:** 31 composable skills (web prototypes, mobile apps, decks, documents, slides, images, video, audio)
- **Design systems:** 72 pre-loaded (Linear, Stripe, Vercel, Apple, Material, etc.)
- **Output formats:** HTML, PDF, PPTX, ZIP, Markdown
- **Preview:** sandboxed `srcdoc` iframe with vendored React 18 + Babel (in-browser JSX)

### Why it doesn't fit our pipeline

Open Design's **web-prototype output is a single-file HTML artifact rendered in a srcdoc iframe**, NOT a standalone Next.js project. Concretely:

- ❌ No `app/` router structure
- ❌ No `components/ui/` shadcn primitives folder
- ❌ No `tailwind.config.ts` token palette
- ❌ No `package.json` with Next.js dependencies
- ❌ Cannot be opened with `pnpm install && pnpm dev`
- ❌ Not git-pushable as a development codebase

The SET design pipeline (`set-design-import`, `design-manifest.yaml` generation, per-change `design.md`, design-fidelity gate) **structurally requires** a real Next.js + shadcn TSX repo. Open Design's HTML artifacts would fail at the import step.

### What Open Design IS great for

- Quick standalone prototypes for pitch decks, customer demos, internal one-pagers
- Single-file HTML mockups portable across teams without a build step
- Design exploration phase before committing to a real codebase
- Output formats that target presentation (PPTX, PDF) rather than codebase

These use cases are **legitimate and valuable** — hence its 30k stars. They are **orthogonal to** SET's "spec → real Next.js+shadcn build" workflow.

### Strategic implication

Open Design occupies the **"prototype rendered in browser"** quadrant. set-design occupies the **"design source of truth for a Next.js+shadcn build pipeline"** quadrant. These are different products with different target users. The fork-or-build question resolves to **build**, because adapting Open Design to emit Next.js would essentially be a rewrite of its core artifact protocol.

---

## 5. Market gap analysis (matrix)

The decisive comparison axis is the intersection of *all five* of these requirements:

|  | Free | Browser-native (zero install) | Real Next.js+shadcn TSX output | BYO Claude (host doesn't pay) | Git-first workflow |
|---|:-:|:-:|:-:|:-:|:-:|
| v0.app | partial | ✅ | ✅ | ❌ | ✅ |
| bolt.new | partial | ✅ | partial | ❌ | partial |
| lovable.dev | partial | ✅ | partial | ❌ | ✅ |
| Claude Design | ❌ | ✅ | partial (handoff bundle) | ❌ | partial |
| bolt.diy | ✅ | ❌ (local) | partial | ✅ | ✅ |
| Open Design | ✅ | ⚠️ web app + local daemon | ❌ (HTML only) | ✅ | ❌ (`.od/` SQLite) |
| Onlook.dev | ✅ | ❌ (Electron desktop) | ✅ | ✅ | ✅ |
| Dyad | ✅ | ❌ (Electron desktop) | partial | ✅ | partial |
| **set-design (V1 local)** | ✅ | ⚠️ V1 local; ✅ V2 hosted | ✅ | ✅ | ✅ |
| **set-design (V2 hosted)** | ✅ | ✅ | ✅ | ✅ | ✅ |

**No existing product hits all five in V2 mode.** Every competitor compromises on one or two axes:

- v0/bolt/lovable: not free, not BYO Claude
- Claude Design: not free, requires Anthropic subscription
- bolt.diy / Onlook / Dyad: free + BYO Claude, but local install required
- Open Design: free + browser, but wrong output format

set-design's V2 architecture (hosted UI at `designer.setcode.dev` + Chrome extension + native messaging host running user's local Claude) **uniquely** sits in the all-five intersection.

---

## 6. set-design positioning

### Marketing tagline (proposed)

> *"v0.app, but free, runs your Claude, ships real Next.js+shadcn code to your GitHub."*

### Target audiences

1. **Open-source / indie developers** who don't want a Vercel subscription and prefer ergonomic chat → preview UX over CLI-only Claude Code workflow.
2. **SET framework users** for whom scaffold-design is part of the spec authoring workflow — they get tight integration as a bonus.
3. **Small teams self-hosting design tooling** who want privacy (code never leaves their machine) and BYO LLM cost control.

### Honest competitive moats

| Moat | Strength |
|---|---|
| Real Next.js+shadcn TSX output (not HTML artifacts) | strong vs Open Design |
| Browser-native (no install) in V2 | strong vs Onlook / Dyad / bolt.diy |
| Free + BYO Claude | strong vs v0 / bolt / lovable / Claude Design |
| SET design-pipeline integration | unique (no competitor) |
| Open source | matches Open Design / bolt.diy / Onlook / Dyad |

### Honest competitive weaknesses

| Weakness | Mitigation |
|---|---|
| Single-claude-at-a-time (no parallel agents in V1) | future feature using SET's worktree orchestration |
| No skills library / design systems library | users bring their own design tokens (consistent with SET pipeline) |
| Bound to Next.js+shadcn (no Svelte/Vue/HTML) | deliberate scope — see master spec stack lock |
| No deploy / preview-share | out of scope by design |
| No DB / auth scaffolding | out of scope by design |

The narrowness is the feature. We are not building a v0 replacement; we are building a focused designer for a specific stack and pipeline.

---

## 7. Strategic decision

**Build set-design.** Both as a SET orchestration test target and as a standalone open-source product.

- **V1 (local):** chat + preview + claude subprocess + git, all in the user's terminal. Implemented via the existing 19-file scaffold spec. ~7-8 changes, 1.5–2 hour sentinel run.
- **V2 (hosted shell):** static SPA at `designer.setcode.dev` + Chrome extension MV3 + native messaging host. The shell is cheap to host (Cloudflare Pages free tier); user's Claude does the work locally. Implemented as a separate later change.

### Why not fork Open Design

- Output format incompatibility (HTML artifacts vs Next.js TSX) requires rewriting their core artifact protocol — saves no real work.
- Their daemon has 16 CLI integrations we don't need; maintenance overhead.
- Their skills/design-systems system overlaps with SET's design-tokens pipeline (`design-system.md`, `design-brief.md`).
- Frame UX is opinionated for their multi-skill workflow, not focused-screen-designer UX.
- Apache-2.0 fork would require attribution + maintenance burden for a codebase whose direction diverges from ours.

### Why not adopt v0 SDK

The `v0-sdk` npm package is a Vercel-cloud API client. Using it would (a) cost per generation, (b) tie us to closed model, (c) defeat the BYO-Claude positioning.

---

## 8. Concrete next actions

### Immediate (tactical)

1. User generates set-design's own UI design source via **v0.app free tier** (6 prompts in `tests/e2e/scaffolds/set-design/docs/design-direction.md` §6). 6 prompts comfortably fit under the daily free-tier limit.
2. User pushes generated design to a GitHub repo.
3. We update `tests/e2e/scaffolds/set-design/scaffold.yaml`'s `design_source.repo` to that URL.
4. We run `tests/e2e/runners/run-set-design.sh` → `set-design-import` materialises `v0-export/`.
5. Sentinel orchestrates the build per the spec.

### Short term (V1 implementation)

The 8-step decomposition is in the master spec. Estimate: 1.5–2 hour sentinel run.

### Mid term (V2 hosted)

After V1 baseline ships:
- Define `set-design-bridge` Chrome extension (MV3, native messaging host)
- Migrate Brain to native-host process
- Static Frame deployable to Cloudflare Pages free tier
- Pairing flow: extension prompts user once on first connect to `designer.setcode.dev`

### Long term (community / GTM)

- Open-source on GitHub under MIT or Apache-2.0
- Show HN with the tagline above
- Documentation site emphasising the BYO-Claude / privacy / open-source story
- Reference SET-pipeline integration as advanced use case for power users
- Track Open Design / Onlook for cross-pollination opportunities (skills library, visual editor pieces)

---

## 9. Future research (to revisit)

- **Parallel-agent design exploration**: SET's worktree orchestration could uniquely enable "generate 4 variants of this hero" as a built-in feature. Differentiation vs every competitor. Defer to V3+.
- **Spec-aware design mode**: detect a SET spec in a sibling directory and design *against* it (already in `set-handoff.md` as an opt-in). Quantify token-savings vs free-form.
- **Visual click-to-edit**: most direct UX competitor of v0's "Design mode". Significant build cost; defer.
- **Multi-target Frame**: open-folder swap is V1; tab-based multi-target is a UX upgrade.
- **MCP integration story**: today we passthrough target's `.mcp.json`. Tomorrow we could ship a `set-design-mcp` server for component catalogs / design tokens lookup.
- **Onlook desktop competitive watch**: their Electron-as-desktop is a different distribution model that might have lessons for V2 native-host architecture.

---

## 10. Sources consulted

- [Open Design — nexu-io GitHub](https://github.com/nexu-io/open-design) — 30.2k stars, Apache-2.0
- [v0.app official](https://v0.app/) and [v0.app docs](https://v0.app/docs)
- [Vercel — Introducing the new v0](https://vercel.com/blog/introducing-the-new-v0)
- [v0.app Changelog](https://v0.app/changelog)
- [v0-sdk npm package](https://www.npmjs.com/package/v0-sdk) (closed-source API client)
- [Anthropic — Introducing Claude Design](https://www.anthropic.com/news/claude-design-anthropic-labs) (April 2026)
- [Dyad GitHub](https://github.com/dyad-sh/dyad) — 20.3k stars
- [v0.diy GitHub](https://github.com/SujalXplores/v0.diy)
- [bolt.diy on Railway](https://railway.com/deploy/boltdiy)
- [siteboon/claudecodeui](https://github.com/siteboon/claudecodeui)
- [winfunc/opcode](https://github.com/winfunc/opcode)
- [sugyan/claude-code-webui](https://github.com/sugyan/claude-code-webui)
- [Claudia GUI](https://claudia.so/)
- [Best Claude Code GUI Tools in 2026 — Nimbalyst](https://nimbalyst.com/blog/best-claude-code-gui-tools-2026/)

---

## Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-06 | Build set-design as scratch scaffold (not fork Open Design) | output-format incompatibility |
| 2026-05-06 | Drop database, drop auth from V1 scope | "screen designer, file-only" user directive |
| 2026-05-06 | Add F17 set-handoff feature | "we need to produce SET v0 design input" — primary purpose |
| 2026-05-07 | Confirm strategic positioning | competitive landscape research validated unique niche |
| 2026-05-07 | Confirm V1 local + V2 hosted-with-extension trajectory | matches uniquely-occupied all-five-axes intersection |
