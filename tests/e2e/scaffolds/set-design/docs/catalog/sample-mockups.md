# Sample Mockups

Reference image fixtures used by chat-engine (F03) and vision-loop (F15) E2E tests.

These images live under `<scaffold>/fixtures/mockups/` (set-design ships them, agents do NOT regenerate). E2E tests upload them via `attachment.upload` and assert the chat handles them correctly (size, mime, attachment_id propagation).

## Required fixtures

| Filename | Mime | Approximate size | Purpose |
|---|---|---|---|
| `mockup-hero-light.png` | `image/png` | ~120 KB | typical light-mode landing hero mockup; smoke test for image upload |
| `mockup-hero-dark.png` | `image/png` | ~140 KB | dark-mode variant; theme handling test |
| `mockup-pricing-table.jpg` | `image/jpeg` | ~280 KB | medium-size jpeg; jpeg path validation |
| `mockup-dashboard.webp` | `image/webp` | ~200 KB | webp format coverage |
| `oversized-mockup.png` | `image/png` | 11 MB | exceeds 10 MB limit; tests `IMAGE_TOO_LARGE` error |
| `disguised.pdf.png` | `application/pdf` (mislabeled) | ~50 KB | tests mime sniffing; should reject as `IMAGE_UNSUPPORTED_FORMAT` |
| `corrupt.png` | `image/png` (broken bytes) | ~10 KB | tests decode-check rejection |

## Image content

The mockups depict hypothetical Next.js+shadcn UIs to make the chat scenarios realistic, but their concrete pixels are not asserted on (only metadata is). Generation guidelines for the source images:

- **mockup-hero-light**: a centered hero with headline "Build faster", subheadline, primary CTA button, secondary outline button, hero image placeholder right.
- **mockup-hero-dark**: same structure as above, dark theme.
- **mockup-pricing-table**: 3-tier pricing table, monthly/yearly toggle, primary tier highlighted.
- **mockup-dashboard**: SaaS dashboard with sidebar nav, KPI cards, line chart placeholder, recent activity table.

These can be PNG screenshots of any reasonable design — including v0.app outputs, Figma exports, or hand-drawn sketches. The test harness only cares about format and bytes.

## Test scenarios using these fixtures

### `chat-engine.spec.ts`

```
- Upload mockup-hero-light.png via paperclip → thumbnail appears in staging
- Upload mockup-pricing-table.jpg via drag-drop → thumbnail appears
- Upload mockup-dashboard.webp via paste → thumbnail appears
- Upload oversized-mockup.png → IMAGE_TOO_LARGE toast, no thumbnail
- Upload disguised.pdf.png → IMAGE_UNSUPPORTED_FORMAT toast
- Upload corrupt.png → IMAGE_UNSUPPORTED_FORMAT toast (decode failed)
- Send message with mockup-hero-light → chat JSONL contains attachment_id
- Receive message with attachment_id from claude → re-render thumbnail
```

### `vision-loop.spec.ts`

```
- Enable vision_loop, run a turn → screenshot attached in turn footer
- Multi-turn — verify only the latest screenshot is auto-attached to next turn
- Vision-loop with dev_server down → screenshot skipped, log warning, no error
- Lightbox open/close on thumbnail click
```

## Generation script (optional, for maintainers)

A helper script `tools/generate-fixtures.mjs` can re-create the four primary mockups from the v0 design source repo (the same one driving design-direction.md). It's not required for E2E to pass — fixtures are checked in.

To regenerate:

```
pnpm fixtures:generate
```

This script:
1. Reads design-source TSX from `v0-export/` (assumed already imported)
2. Renders each mockup route to PNG via Playwright
3. Writes outputs to `fixtures/mockups/`

The 3 fixture variants (oversized / disguised / corrupt) are NOT auto-generated; they're crafted manually and committed.
