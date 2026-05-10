# E2E Test Layering

Test your change at three levels. Each level catches different bugs — skipping a level creates blind spots.

## Level 1: Backend logic (unit/integration — no browser)

When your change introduces server-side logic (API routes, WS handlers, data processing, external service integration), test it independently with vitest/jest:
- Message parsing, routing, error handling
- Data transformations and validations
- External API response handling (mock the external service, test your handler)

These tests run fast and give precise failure messages. Do NOT test backend logic through Playwright — that's slow and hides the root cause.

## Level 2: Structural E2E (Playwright)

Verify UI elements exist and have correct attributes:
- `data-testid` presence and values
- Element visibility and enabled/disabled state
- Text content, ARIA attributes
- Responsive layout at different viewports

This is the existing pattern — keep using it for coverage of UI structure.

## Level 3: Functional E2E (Playwright — 1-2 tests per change)

Write 1-2 tests that exercise a real user flow end-to-end:
- User performs an action (click, type, upload)
- System processes it (API call, WS message, subprocess)
- Result appears in the UI (new element rendered, state updated)

Use mock backends where needed (Playwright `routeWebSocket`, `page.route`) but exercise the full UI interaction chain. Focus on the critical happy path.

## When your change has both backend and frontend

1. Write unit tests for the backend logic FIRST (Level 1)
2. Write structural E2E tests for UI presence (Level 2)
3. Write 1-2 functional E2E tests that verify the connection (Level 3)

The functional E2E tests prove the backend and frontend work together — they don't re-test backend logic through the UI.
