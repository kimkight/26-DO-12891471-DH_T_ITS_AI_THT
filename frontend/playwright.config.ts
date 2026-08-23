/**
 * The accessibility run, against the built page (NFR-5).
 *
 * Against `vite preview` serving `dist/`, not against a dev server and not
 * against components in jsdom. Two reasons, and the second is the one that
 * decides it:
 *
 * 1. The built bundle is what an agent loads, so it is what should be checked.
 * 2. **axe-core cannot evaluate colour contrast without a real layout engine.**
 *    In jsdom the `color-contrast` rule reports "incomplete" rather than
 *    "pass", so a jsdom axe run would go green while never having checked the
 *    one NFR-5 criterion that is a number. A real browser is the only way to
 *    make that criterion testable rather than asserted.
 *
 * Chromium only. This is a WCAG conformance check, not a cross-browser matrix;
 * axe's results do not vary by engine in a way that would justify tripling the
 * CI time.
 */
import { defineConfig, devices } from '@playwright/test'

const PORT = 4173

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? 'list' : 'html',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // CI runs `playwright install chromium` and leaves this unset, which
        // is the ordinary path. The override exists for environments that
        // ship a Chromium already and forbid downloading another, where
        // Playwright's own build number will not match what is on disk.
        launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH
          ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
          : {},
      },
    },
  ],
  webServer: {
    command: `npm run preview -- --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
