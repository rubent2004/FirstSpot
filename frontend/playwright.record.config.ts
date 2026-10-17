import { defineConfig, devices } from "@playwright/test";

/**
 * Records the guided-tour demo video (`pnpm record:tour`). Separate from
 * playwright.config.ts: the recording spec is skipped unless RECORD_TOUR=1,
 * which only this config sets, so the normal e2e suite never runs it.
 *
 * Needs the real stack (`just up2`). HEADLESS=1 forces a headless browser when
 * no display is available.
 */
process.env.RECORD_TOUR = "1";

const ARTIFACTS = "./e2e-artifacts";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "record-tour.e2e.ts",
  globalSetup: "./e2e/support/global-setup.ts",
  outputDir: `${ARTIFACTS}/record-results`,
  fullyParallel: false,
  workers: 1,
  timeout: 6 * 60_000,
  expect: { timeout: 15_000 },
  retries: 0,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://localhost:5173",
    locale: "es-SV",
    timezoneId: "America/El_Salvador",
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    headless: process.env.HEADLESS === "1" || !(process.env.DISPLAY || process.env.WAYLAND_DISPLAY),
    trace: "off",
    video: "off",
  },
  projects: [{ name: "record-chromium" }],
  webServer: {
    command: "pnpm dev --port 5173",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
