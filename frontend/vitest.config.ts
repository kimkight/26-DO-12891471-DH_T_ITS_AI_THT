/**
 * Component tests: jsdom, React Testing Library, no browser.
 *
 * This config covers the component tier only. The accessibility run is a
 * separate Playwright project (playwright.config.ts) against the built page,
 * because axe-core cannot evaluate colour contrast without a real layout
 * engine, and NFR-5 sets a contrast requirement. Running axe in jsdom would
 * report a pass on a rule it never actually ran.
 *
 * `tests/` is excluded so `vitest` does not try to collect the Playwright spec,
 * whose `test` import is a different runner's.
 */
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['tests/**', 'node_modules/**', 'dist/**'],
  },
})
