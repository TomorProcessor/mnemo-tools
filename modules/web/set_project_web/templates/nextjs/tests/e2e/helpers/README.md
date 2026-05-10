# E2E Test Helpers

Shared test utilities for this project's E2E tests. Each change that introduces new test infrastructure should add helpers here rather than defining them inline in spec files.

## Convention

One file per concern. Import from here in your spec files:

```typescript
import { navigateToWorkspace, openTarget } from './helpers/navigation'
import { createMockWsServer } from './helpers/ws-mock'
import { seedChatHistory } from './helpers/seed-data'
```

## Examples of what goes here

- **navigation.ts** — Common page navigation and setup (open target, wait for ready state)
- **ws-mock.ts** — WebSocket mock server setup via Playwright `routeWebSocket`
- **seed-data.ts** — Test data seeding via API endpoints
- **auth.ts** — Authentication/session helpers
- **fixtures.ts** — Shared test data factories (users, products, configs)
- **assertions.ts** — Custom assertion helpers for domain-specific checks

## What does NOT go here

- Test-specific logic (belongs in the spec file)
- One-off setup that only one test needs
- Production code (belongs in `lib/` or `utils/`)
