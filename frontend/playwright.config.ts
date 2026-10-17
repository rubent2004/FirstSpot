import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end suite against the REAL running stack: Vite on :5173 proxying the
 * FastAPI backend on :8000 with PostGIS behind it. Start it with `just up2`;
 * Playwright reuses the running Vite and never mocks the API.
 *
 * Specs are named *.e2e.ts so Vitest's default *.spec.ts / *.test.ts glob never
 * picks them up.
 */
const ARTIFACTS = "./e2e-artifacts";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  globalSetup: "./e2e/support/global-setup.ts",
  outputDir: `${ARTIFACTS}/test-results`,
  fullyParallel: false,
  workers: 2,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: `${ARTIFACTS}/report`, open: "never" }],
    ["json", { outputFile: `${ARTIFACTS}/results.json` }],
  ],
  use: {
    baseURL: "http://localhost:5173",
    locale: "es-SV",
    timezoneId: "America/El_Salvador",
    acceptDownloads: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
    viewport: { width: 1920, height: 1080 },
  },
  projects: [{ name: "chromium" }],
  webServer: {
    command: "pnpm dev --port 5173",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
