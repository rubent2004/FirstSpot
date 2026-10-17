import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { ARTIFACTS_DIR } from "./support/app";

/**
 * Records the guided tour (`?tour=1` flow, 14 steps) as the 2-minute demo video,
 * paced by the narrator script in docs/demo/guion-video.md. Run it with
 * `pnpm record:tour` (playwright.record.config.ts); the normal suite skips it.
 *
 * Output: e2e-artifacts/video/{firstspot-tour.raw.webm,firstspot-tour.mp4,timings.json,frames/}.
 */
test.skip(process.env.RECORD_TOUR !== "1", "recording only runs from playwright.record.config.ts");

const VIEWPORT = { width: 1920, height: 1080 };
const VIDEO_DIR = path.join(ARTIFACTS_DIR, "video");
const RAW_DIR = path.join(VIDEO_DIR, "raw");
const MAX_TOTAL_S = 115;
const CLOSING_HOLD_S = Number(process.env.CLOSING_HOLD_S ?? 4);
const STEP_TIMEOUT_MS = 20_000;
const WRITE_METHODS = new Set(["POST", "PATCH", "PUT", "DELETE"]);

/** Seconds per step from docs/demo/guion-video.md (0-9, 9-17, ... 110-120). */
const SCRIPT_STEPS = [
  { id: "opening", seconds: 9 },
  { id: "zone", seconds: 8 },
  { id: "baseline", seconds: 9 },
  { id: "mode", seconds: 9 },
  { id: "eventTop", seconds: 8 },
  { id: "detail", seconds: 8 },
  { id: "sphere", seconds: 8 },
  { id: "places", seconds: 8 },
  { id: "placeSummary", seconds: 8 },
  { id: "placeLog", seconds: 9 },
  { id: "placeAccess", seconds: 7 },
  { id: "exportFormat", seconds: 9 },
  { id: "exportMap", seconds: 10 },
  { id: "closing", seconds: 10 },
] as const;

/** The closing card is held CLOSING_HOLD_S; scale everything if the result is still too long. */
function plannedDurations(): number[] {
  const raw = SCRIPT_STEPS.map((step, i) => (i === SCRIPT_STEPS.length - 1 ? CLOSING_HOLD_S : step.seconds));
  const total = raw.reduce((a, b) => a + b, 0);
  const scale = total > MAX_TOTAL_S ? MAX_TOTAL_S / total : 1;
  return raw.map((s) => s * scale);
}

interface StepCheck {
  index: number;
  id: string;
  title: string;
  skipped: boolean;
  reason: string | null;
}

const popover = (page: Page) => page.locator(".driver-popover.firstspot-tour");

/** Waits for step `index` (1-based) to be on screen and reports whether it fell back. */
async function waitForStep(page: Page, index: number): Promise<StepCheck> {
  const id = SCRIPT_STEPS[index - 1].id;
  const box = popover(page);
  await expect(box, `step ${index} (${id}) popover`).toBeVisible({ timeout: STEP_TIMEOUT_MS });
  await expect(box.locator(".driver-popover-progress-text"), `step ${index} (${id}) progress`).toHaveText(
    `${index} / ${SCRIPT_STEPS.length}`,
    { timeout: STEP_TIMEOUT_MS },
  );
  const title = ((await box.locator(".driver-popover-title").textContent()) ?? "").trim();
  const skipped = (await box.evaluate((el) => el.classList.contains("is-skipped"))) || title === "Paso no disponible";
  const reason = skipped ? ((await box.locator(".driver-popover-description").textContent()) ?? "").trim() : null;
  if (!skipped && id !== "opening" && id !== "closing") {
    await expect(page.locator(".driver-active-element").first(), `step ${index} (${id}) highlight`).toBeVisible({
      timeout: STEP_TIMEOUT_MS,
    });
  }
  return { index, id, title, skipped, reason };
}

function failOnFallback(checks: StepCheck[], phase: string): void {
  const fallen = checks.filter((c) => c.skipped);
  if (fallen.length === 0) return;
  const detail = fallen.map((c) => `step ${c.index} (${c.id}): ${c.reason}`).join("\n");
  throw new Error(`[${phase}] the tour showed "Paso no disponible":\n${detail}`);
}

/** Fails the run on any backend write; the tour must only read. */
function watchWrites(context: BrowserContext, writes: string[]): void {
  context.on("request", (request) => {
    if (WRITE_METHODS.has(request.method()) && new URL(request.url()).pathname.startsWith("/api/")) {
      writes.push(`${request.method()} ${request.url()}`);
    }
  });
}

/** Data loaded: district rows rendered, network quiet, map camera still, every tile loaded. */
async function waitForDataAndTiles(page: Page): Promise<void> {
  await expect(page.getByTestId("district-row").first()).toBeVisible({ timeout: 30_000 });
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(
    () => {
      const w = window as unknown as { __recSamples?: string[] };
      const map = document.querySelector('[data-testid="map-panel"]');
      const pane = map?.querySelector<HTMLElement>(".leaflet-map-pane");
      if (!map || !pane) return false;
      const tiles = [...map.querySelectorAll("img.leaflet-tile")];
      const loading = tiles.some((t) => !t.classList.contains("leaflet-tile-loaded"));
      const animating = map.querySelector(".leaflet-zoom-anim") !== null;
      const sample = `${pane.style.transform}|${tiles.length}|${loading}|${animating}`;
      const samples = (w.__recSamples = [...(w.__recSamples ?? []), sample].slice(-4));
      return tiles.length > 0 && !loading && !animating && samples.length === 4 && samples.every((s) => s === samples[0]);
    },
    undefined,
    { polling: 250, timeout: 30_000 },
  );
}

async function startTour(page: Page): Promise<void> {
  await page.goto("/");
  await waitForDataAndTiles(page);
  await page.keyboard.press("Shift+Alt+KeyT");
}

/** Untimed pass: warms the backend caches (the 2001 ShakeMap) and fails fast on a fallback. */
async function rehearse(browser: Browser, writes: string[]): Promise<void> {
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  watchWrites(context, writes);
  const page = await context.newPage();
  const checks: StepCheck[] = [];
  await startTour(page);
  for (let i = 1; i <= SCRIPT_STEPS.length; i++) {
    if (i > 1) await page.keyboard.press("ArrowRight");
    checks.push(await waitForStep(page, i));
    await page.waitForTimeout(400);
  }
  await page.keyboard.press("Escape");
  await expect(popover(page)).toBeHidden();
  await context.close();
  failOnFallback(checks, "rehearsal");
}

function ffmpegAvailable(): boolean {
  try {
    execFileSync("ffmpeg", ["-version"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

test("record the guided tour video", async ({ browser }) => {
  const writes: string[] = [];
  const durations = plannedDurations();
  rmSync(RAW_DIR, { recursive: true, force: true });
  mkdirSync(RAW_DIR, { recursive: true });

  await rehearse(browser, writes);
  expect(writes, "backend writes during the rehearsal").toEqual([]);

  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 1,
    reducedMotion: "no-preference",
    recordVideo: { dir: RAW_DIR, size: VIEWPORT },
  });
  watchWrites(context, writes);
  const page = await context.newPage();
  // The video's clock starts with the page; every mark below is relative to it.
  const videoStart = Date.now();
  const at = () => (Date.now() - videoStart) / 1000;

  await startTour(page);
  const checks: StepCheck[] = [];
  const starts: number[] = [];

  checks.push(await waitForStep(page, 1));
  starts.push(at());
  const tourZero = starts[0];
  let target = 0;
  for (let i = 2; i <= SCRIPT_STEPS.length; i++) {
    // Absolute schedule: a slow step never pushes the rest of the narration late.
    target += durations[i - 2];
    await page.waitForTimeout(Math.max(0, (tourZero + target - at()) * 1000));
    await page.keyboard.press("ArrowRight");
    checks.push(await waitForStep(page, i));
    starts.push(at());
  }
  target += durations[durations.length - 1];
  await page.waitForTimeout(Math.max(0, (tourZero + target - at()) * 1000));
  const end = at();
  await page.keyboard.press("Escape");
  await expect(popover(page)).toBeHidden();
  await page.waitForTimeout(300);

  const video = page.video();
  await context.close();
  const rawPath = await video!.path();

  failOnFallback(checks, "recording");
  expect(writes, "backend writes during the recording").toEqual([]);

  // Trim so the video opens on step 1 already painted (popover fade-in done).
  const trimStart = tourZero + 0.4;
  const length = end - trimStart;
  // The raw recording (load included, untrimmed) is kept next to the mp4.
  copyFileSync(rawPath, path.join(VIDEO_DIR, "firstspot-tour.raw.webm"));

  const timings = {
    source: "docs/demo/guion-video.md",
    closingHoldSeconds: CLOSING_HOLD_S,
    maxTotalSeconds: MAX_TOTAL_S,
    plannedTotalSeconds: Number(durations.reduce((a, b) => a + b, 0).toFixed(3)),
    rawTrimStartSeconds: Number(trimStart.toFixed(3)),
    videoDurationSeconds: Number(length.toFixed(3)),
    steps: checks.map((c, i) => ({
      step: c.index,
      id: c.id,
      title: c.title,
      scriptSeconds: SCRIPT_STEPS[i].seconds,
      plannedSeconds: Number(durations[i].toFixed(3)),
      plannedStart: Number(durations.slice(0, i).reduce((a, b) => a + b, 0).toFixed(3)),
      start: Number(Math.max(0, starts[i] - trimStart).toFixed(3)),
      fellBack: c.skipped,
    })),
  };
  writeFileSync(path.join(VIDEO_DIR, "timings.json"), `${JSON.stringify(timings, null, 2)}\n`);

  if (!ffmpegAvailable()) {
    console.warn("[record-tour] ffmpeg not found: kept the untrimmed firstspot-tour.raw.webm only");
    return;
  }
  const ff = (args: string[]) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...args], { stdio: "inherit" });
  const trim = ["-ss", trimStart.toFixed(3), "-i", rawPath, "-t", length.toFixed(3), "-an"];
  const mp4 = path.join(VIDEO_DIR, "firstspot-tour.mp4");
  ff([
    ...trim,
    "-vf",
    `scale=${VIEWPORT.width}:${VIEWPORT.height}`,
    "-c:v",
    "libx264",
    "-crf",
    "18",
    "-preset",
    "slow",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    mp4,
  ]);

  const frames = path.join(VIDEO_DIR, "frames");
  rmSync(frames, { recursive: true, force: true });
  mkdirSync(frames, { recursive: true });
  for (const step of timings.steps) {
    const next = timings.steps[step.step]?.start ?? timings.videoDurationSeconds;
    const mid = Math.min(step.start + (next - step.start) / 2, timings.videoDurationSeconds - 0.1);
    const name = `${String(step.step).padStart(2, "0")}-${step.id}.png`;
    ff(["-ss", mid.toFixed(3), "-i", mp4, "-frames:v", "1", path.join(frames, name)]);
  }
});
