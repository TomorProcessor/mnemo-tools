# Default Target — `nextjs-shadcn-starter`

The reference target dir that set-design's Templates feature (F16) materializes. This is also the canonical fixture E2E tests use to populate `tmp-e2e-target/`.

## Purpose

Two roles:
1. **For users**: a zero-config Next.js + shadcn starter usable as the design surface.
2. **For E2E tests**: a stable, minimal target whose initial state and dev-server output are well-known. Tests assert against rendered text from this scaffold.

## File listing

```
nextjs-shadcn-starter/
├── app/
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   └── ui/                 (empty — shadcn primitives added on demand)
├── lib/
│   ├── set-design-bridge.ts
│   └── utils.ts
├── public/
│   └── favicon.ico
├── .gitignore
├── components.json
├── next.config.mjs
├── package.json
├── postcss.config.mjs
├── tailwind.config.ts
├── tsconfig.json
└── README.md
```

## File contents

### `package.json`

```json
{
  "name": "set-design-target",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "lucide-react": "^0.400.0",
    "tailwind-merge": "^2.3.0"
  },
  "devDependencies": {
    "@types/node": "^20.12.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "autoprefixer": "^10.4.19",
    "eslint": "^8.57.0",
    "eslint-config-next": "^14.2.0",
    "postcss": "^8.4.38",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0"
  }
}
```

### `app/page.tsx`

```tsx
export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="text-center">
        <h1 className="mb-2 text-3xl font-bold">Hello, set-design</h1>
        <p className="text-muted-foreground">
          Edit <code className="rounded bg-muted px-2 py-1 font-mono text-sm">app/page.tsx</code> — or ask Claude.
        </p>
      </div>
    </main>
  );
}
```

The placeholder text `Hello, set-design` is asserted on by E2E tests as a baseline render.

### `app/layout.tsx`

```tsx
import "./globals.css";
import "@/lib/set-design-bridge";

export const metadata = {
  title: "set-design target",
  description: "A Next.js + shadcn project designed with set-design",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
```

### `app/globals.css`

Includes Tailwind base + the standard shadcn CSS variable palette under `:root` and `.dark`. The full content matches shadcn's recommended `globals.css` for v0.4 style.

### `tailwind.config.ts`

Full shadcn-recommended config with the CSS-variable-based color palette and `darkMode: ["class"]`.

### `components.json`

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "app/globals.css",
    "baseColor": "neutral",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui"
  }
}
```

### `lib/utils.ts`

The standard shadcn `cn()` helper:

```ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### `lib/set-design-bridge.ts`

See `features/templates.md` — the bridge script applying theme query params and relaying runtime errors.

### `tsconfig.json`

Standard strict Next.js tsconfig with `paths: { "@/*": ["./*"] }`.

### `.gitignore`

Standard Next.js gitignore plus:

```
.set-design/
```

### `README.md`

Brief instructions:

```markdown
# Target — designed with set-design

Run:
\`\`\`
pnpm install
pnpm dev
\`\`\`

Open set-design and point it at this folder. Ask Claude to design.
```

## E2E test usage

E2E tests for set-design itself MUST:

1. Copy `default-target` to `tmp-e2e-target/<test-id>/` before each test that opens a target.
2. Run `pnpm install` (cached in CI).
3. Use `SET_DESIGN_CLAUDE_BIN=$(pwd)/tools/mock-claude.mjs` so the orchestrator drives a deterministic shim.
4. Assert that `Hello, set-design` is visible in the iframe at first load.

After each test, the temp dir is destroyed.

## Versioning

This catalog file is treated as a contract for E2E. Changes to `app/page.tsx` content, `app/layout.tsx` shape, or `components.json` aliases require updating dependent test assertions.
