// Flat ESLint config deployed by the web project type.
//
// Two rule blocks:
//   1. Project-wide: forbid raw <img> via @next/next/no-img-element.
//   2. Locale-routed pages only: forbid hardcoded user-visible JSX strings
//      via i18next/no-literal-string.
//
// The locale-scope keeps the no-literal-string rule from firing on API
// routes, server actions outside [locale], or test fixtures. The attribute
// ignore list keeps it quiet for non-UI props that legitimately carry
// string literals (className, ids, ARIA labels, test ids).

import nextPlugin from "@next/eslint-plugin-next";
import i18nextPlugin from "eslint-plugin-i18next";

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
  // 1) Project-wide Next.js rules — applies to every TS/TSX under src/.
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: {
      "@next/next": nextPlugin,
    },
    rules: {
      ...nextPlugin.configs["core-web-vitals"].rules,
      "@next/next/no-img-element": "error",
    },
  },

  // 2) Locale-routed pages only — forbid hardcoded user-visible JSX strings.
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
            exclude: ["i18n(ext)?", "t", "require", "addEventListener", "removeEventListener", "postMessage", "getElementById", "dispatch", "commit", "includes", "indexOf", "endsWith", "startsWith"],
          },
        },
      ],
    },
  },

  // 3) Ignore generated and vendored output.
  {
    ignores: [".next/**", "node_modules/**", "out/**", "build/**", "coverage/**"],
  },
];
