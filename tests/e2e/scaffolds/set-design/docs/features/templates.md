# Templates (F16 — V1 stretch, opt-in)

Bootstrap a fresh target dir from a curated starter template — Next.js + shadcn pre-configured, set-design bridge script pre-installed, gitignore set up correctly.

This is a **stretch feature** for V1. The default flow assumes the user has an existing Next.js+shadcn folder. Templates make set-design viable for users starting from zero.

## Why

A new set-design user faces friction: install Next.js, install shadcn, configure tailwind, add the optional `set-design-bridge` script, set up gitignore. The template solves this in one click.

## Behavior

In the welcome screen (`features/open-folder.md`), next to "Open folder…":

```
[Open folder…]      [New from template…]
```

"New from template" → dialog:

```
┌─ New from template ──────────────────────────────────┐
│  Choose a template:                                  │
│                                                      │
│  ⚪  Next.js + shadcn (recommended)                   │
│      App Router · TypeScript · Tailwind · shadcn UI  │
│      Includes set-design bridge script.              │
│                                                      │
│  ⚪  Next.js + shadcn (Pages Router)                  │
│      For legacy projects.                            │
│                                                      │
│  Target folder:  [/Users/me/work/new-project    ⌹]  │
│                                                      │
│                            [Cancel]  [Create]        │
└──────────────────────────────────────────────────────┘
```

V1 ships with **one template** (the App Router variant). The dialog shows additional placeholder slots for V2 templates.

## Template — `nextjs-shadcn-starter`

Files materialized into the target folder:

```
<target>/
├── app/
│   ├── layout.tsx              # imports globals.css; injects set-design-bridge
│   ├── page.tsx                # placeholder home: "Hello, set-design"
│   └── globals.css             # CSS vars for colors, radii, etc.
├── components/
│   └── ui/                     # empty; user runs `npx shadcn add` per primitive
├── lib/
│   ├── utils.ts                # cn() helper from shadcn
│   └── set-design-bridge.ts    # bridge script (runtime error capture, theme query param)
├── public/
│   └── favicon.ico
├── .gitignore                  # standard Next.js + .set-design/ + node_modules
├── components.json             # shadcn config
├── next.config.mjs
├── package.json                # deps: next, react, react-dom, tailwindcss, class-variance-authority, clsx, lucide-react
├── postcss.config.mjs
├── tailwind.config.ts          # full token palette using CSS variables
├── tsconfig.json
└── README.md                   # tells user to: pnpm install, pnpm dev
```

## Materialization steps

```
1. Validate target folder is empty OR doesn't exist (else TARGET_NOT_EMPTY).
   - Allow only ".git" presence (user pre-init'd).
2. Create folder if missing.
3. Copy template files from `set-design/templates/nextjs-shadcn-starter/` into target.
4. Run `git init` if not already a repo.
5. Run `pnpm install` (or `npm install` if pnpm not found, log warning).
   - Surface install logs in a streaming overlay.
6. Run initial commit: "Initialize from set-design template".
7. Bootstrap config.json with sensible defaults (target_path, dev_url=localhost:3000, model=opus, vision_loop=false).
8. Open the new target (transition to main app view).
```

## set-design-bridge.ts content

A small ESM script the template includes. Imported by `app/layout.tsx`:

```typescript
// lib/set-design-bridge.ts (template-installed)
//
// This script is OPTIONAL but recommended. set-design uses it to:
//   1. apply theme query param (?set-design-theme=light|dark) to <html>
//   2. relay runtime errors via postMessage to the parent (set-design Frame)
//
// You can remove this script — set-design will fall back to overlay-scrape error detection.

if (typeof window !== "undefined") {
  // Theme override from query param
  const theme = new URLSearchParams(window.location.search).get("set-design-theme");
  if (theme === "light" || theme === "dark") {
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(theme);
  }

  // Runtime error relay
  window.addEventListener("error", (e) => {
    try {
      window.parent?.postMessage(
        {
          type: "set-design.preview.error",
          kind: "runtime",
          message: e.message,
          filename: e.filename,
          lineno: e.lineno,
          colno: e.colno,
          stack: e.error?.stack ?? null,
        },
        "*"
      );
    } catch {
      // If we're not in an iframe or origins don't match, fail silently.
    }
  });

  window.addEventListener("unhandledrejection", (e) => {
    try {
      window.parent?.postMessage(
        {
          type: "set-design.preview.error",
          kind: "runtime",
          message: String(e.reason),
          stack: e.reason?.stack ?? null,
        },
        "*"
      );
    } catch {}
  });
}

export {};
```

The user is free to delete this file; set-design degrades to overlay-scrape error detection in `features/orchestrator.md`.

## Layout.tsx integration

The template's `app/layout.tsx` includes a single import:

```tsx
import "./globals.css";
import "@/lib/set-design-bridge";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

## Required `data-testid`

| testid | Surface |
|---|---|
| `welcome-template-button` | "New from template" button |
| `template-dialog` | dialog root |
| `template-option-{slug}` | each template radio |
| `template-target-input` | folder path input |
| `template-create-button` | Create button |
| `template-install-overlay` | install streaming overlay |
| `template-install-log` | log content |

## Errors handled

| Code | UX |
|---|---|
| `TARGET_NOT_EMPTY` | dialog inline: "Folder is not empty. Pick another or use 'Open folder' for an existing project." |
| `TEMPLATE_INSTALL_FAILED` | overlay shows error tail + "Retry" / "Cancel & cleanup" |
| `PNPM_NOT_FOUND` | warning toast: "Falling back to npm" |

## Dependencies

- F00 open-folder (target.open after materialization)
- F14 protocol (new request types: `template.list`, `template.create`)
- F08 orchestrator (git init + commit)

## Change scope (decomposition hint)

Single optional change: `templates`. Delivers:
- Template directory shipped with set-design
- New from template dialog
- Materialization pipeline with streaming install overlay
- Bridge script
- New WS handlers `template.*`

Implemented after the V1 baseline. Without it, users start from existing folders or hand-bootstrap. With it, set-design becomes truly zero-friction for new projects.
