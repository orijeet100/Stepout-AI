---
date: 2026-10-07
kind: note
lane: ui
status: accepted
title: Test tooling added to web: Vitest, jsdom, Testing Library
tags: [deps,testing,u2]
refs: [web/package.json, web/vite.config.ts, web/src/test-setup.ts]
---

**What.** Four dev dependencies, all MIT: `vitest` 5.0.3 (test runner; declares support for Vite 8), `jsdom` 30.1.2 (the DOM it runs in), `@testing-library/react` 16.3.3 and its required peer `@testing-library/dom` 10.4.2 (render and query components). `npm test` runs `vitest run`. `npm audit`: 0 vulnerabilities.

**Why.** U2 requires `npm test`. Vitest reuses the Vite config and transform, so there is no second build setup.

**Alternatives.** Jest (needs its own transform setup next to Vite). `happy-dom` instead of jsdom (faster, but less complete). `@testing-library/user-event` and `jest-dom` were left out: `fireEvent` and plain `expect` cover what the tests need, so two fewer packages. Vitest globals are off, so `src/test-setup.ts` registers Testing Library's cleanup by hand.

**Evidence.** `npm test` passes; `npm audit` clean. No dependency has an install script that was approved (none was asked for).
