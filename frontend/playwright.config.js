import { defineConfig, devices } from '@playwright/test'

// Registry-claimed Vite dev port — never the shared default (5173).
const PORT = 5186

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  // Playwright starts the dev server itself and reuses one that is
  // already running locally. No backend is needed: every /api call is
  // stubbed per-spec (see e2e/_helpers.js).
  webServer: {
    command: 'corepack pnpm dev',
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
