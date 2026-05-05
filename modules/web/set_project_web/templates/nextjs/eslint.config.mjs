// Flat ESLint config deployed by the web project type.
//
// Uses FlatCompat to bring in `next/core-web-vitals` (which carries the
// TypeScript parser, plugins, and Next.js rule set) into the flat-config
// world. Then layers two scoped overrides:
//   1. Project-wide: bump @next/next/no-img-element to error.
//   2. Locale-routed pages only: i18next/no-literal-string to catch
//      hardcoded JSX strings that should go through useTranslations().

import { FlatCompat } from "@eslint/eslintrc";
import i18nextPlugin from "eslint-plugin-i18next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const IGNORED_ATTRIBUTES = [
  "className",
  "id",
  "key",
  "name",
  "type",
  "role",
  "htmlFor",
  "data-testid",
];

export default [
  // 1) Bring in Next.js's full TypeScript-aware config (parser + rules).
  ...compat.extends("next/core-web-vitals"),

  // 2) Project-wide override — raw <img> is a hard error, not a warning.
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "@next/next/no-img-element": "error",
    },
  },

  // 3) Locale-routed pages only — forbid hardcoded user-visible JSX strings.
  {
    files: ["src/app/[locale]/**/*.{ts,tsx}"],
    plugins: {
      i18next: i18nextPlugin,
    },
    rules: {
      "i18next/no-literal-string": [
        "error",
        {
          mode: "jsx-text-only",
          "jsx-attributes": {
            include: ["alt", "aria-label", "title", "placeholder"],
            exclude: IGNORED_ATTRIBUTES,
          },
          words: {
            exclude: ["[0-9!-/:-@[-`{-~]+", "[A-Z_-]+"],
          },
          callees: {
            exclude: [
              "i18n(ext)?",
              "t",
              "require",
              "addEventListener",
              "removeEventListener",
              "postMessage",
              "getElementById",
              "dispatch",
              "commit",
              "includes",
              "indexOf",
              "endsWith",
              "startsWith",
            ],
          },
        },
      ],
    },
  },

  // 4) Ignore generated and vendored output.
  {
    ignores: [".next/**", "node_modules/**", "out/**", "build/**", "coverage/**"],
  },
];
