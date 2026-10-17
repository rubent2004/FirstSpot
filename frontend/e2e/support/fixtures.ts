import { test as base, expect, type Page, type TestInfo } from "@playwright/test";

/**
 * Shared fixtures for the end-to-end suite. Every test runs against the REAL
 * stack (Vite on :5173 proxying FastAPI on :8000 and PostGIS); nothing here
 * mocks the API.
 *
 * Two guards are automatic for every test:
 *  - tile guard: no request may reach a key-gated tile provider (the CARTO incident);
 *  - console hygiene: console errors and unhandled page errors fail the test
 *    unless they match an allowlist entry that states why it is acceptable.
 */

/** Hosts that serve tiles only with an API key, or under terms the project cannot meet. */
export const KEY_GATED_TILE_HOSTS: readonly RegExp[] = [
  /(^|\.)cartocdn\.com$/i,
  /(^|\.)carto\.com$/i,
  /(^|\.)mapbox\.com$/i,
  /(^|\.)maptiler\.com$/i,
  /(^|\.)thunderforest\.com$/i,
  /(^|\.)stadiamaps\.com$/i,
  /(^|\.)stadia\.com$/i,
  /(^|\.)tomtom\.com$/i,
  // Google map tiles (not fonts or other Google services)
  /^(tile|maps)\.googleapis\.com$/i,
  /^(mt|khms?)\d*\.google(apis)?\.com$/i,
  /^maps\.(google|gstatic)\.com$/i,
];

/** True when a URL points at a key-gated tile provider. Exported so the guard itself is tested. */
export function isKeyGatedTileUrl(url: string): boolean {
  let host: string;
  try {
    host = new URL(url).hostname;
  } catch {
    return false;
  }
  return KEY_GATED_TILE_HOSTS.some((pattern) => pattern.test(host));
}

interface AllowedMessage {
  pattern: RegExp;
  reason: string;
}

/**
 * Console errors that are accepted, each with the reason. Keep this list short:
 * an entry here is a known, understood message, never a way to silence a failure.
 */
export const CONSOLE_ALLOWLIST: readonly AllowedMessage[] = [
  // Empty on purpose: the first full run against the real stack produced no
  // console error that needed an exception. Add entries as { pattern, reason }.
];

export interface PageGuards {
  /** Requests that went to a key-gated provider. */
  blockedRequests: string[];
  /** Console errors and page errors not in the allowlist. */
  consoleProblems: string[];
  /** Allowlisted messages that did occur, with their reason, for the report. */
  allowed: string[];
  /** Every distinct host the page contacted, for the report. */
  hosts: Set<string>;
}

export function attachGuards(page: Page): PageGuards {
  const guards: PageGuards = { blockedRequests: [], consoleProblems: [], allowed: [], hosts: new Set() };
  page.on("request", (request) => {
    const url = request.url();
    try {
      guards.hosts.add(new URL(url).host);
    } catch {
      // data: and blob: URLs have no host worth recording
    }
    if (isKeyGatedTileUrl(url)) guards.blockedRequests.push(url);
  });
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const location = message.location();
    const text = `${message.text()}${location.url ? ` (${location.url})` : ""}`;
    const allowed = CONSOLE_ALLOWLIST.find((entry) => entry.pattern.test(text));
    if (allowed) {
      guards.allowed.push(`${text} -- allowed: ${allowed.reason}`);
      return;
    }
    guards.consoleProblems.push(`console.error: ${text}`);
  });
  page.on("pageerror", (error) => {
    const frame = error.stack?.split("\n").find((l) => l.includes("http")) ?? "";
    guards.consoleProblems.push(`pageerror: ${error.message}${frame ? ` @${frame.trim()}` : ""}`);
  });
  return guards;
}

export async function assertGuards(guards: PageGuards, testInfo: TestInfo): Promise<void> {
  await testInfo.attach("hosts-contacted", {
    body: [...guards.hosts].sort().join("\n"),
    contentType: "text/plain",
  });
  if (guards.allowed.length) {
    await testInfo.attach("allowlisted-console-errors", {
      body: guards.allowed.join("\n"),
      contentType: "text/plain",
    });
  }
  expect(guards.blockedRequests, "requests to key-gated tile providers").toEqual([]);
  expect(guards.consoleProblems, "console errors not in the allowlist").toEqual([]);
}

export type Theme = "light" | "dark";

export interface AppOptions {
  theme: Theme;
}

/** Storage keys the app reads at boot (see useTheme.ts, useI18n.ts, GeoRibbon.vue). */
const THEME_KEY = "eoc_theme";
const LOCALE_KEY = "geo_prioridad_locale";

export const test = base.extend<AppOptions & { guards: PageGuards }>({
  theme: ["dark", { option: true }],

  guards: [
    async ({ page, theme }, use, testInfo) => {
      await page.addInitScript(
        ([themeKey, themeValue, localeKey]) => {
          // Only the first load of a test is seeded: a reload must keep what the test changed.
          if (sessionStorage.getItem("__e2e_seeded")) return;
          sessionStorage.setItem("__e2e_seeded", "1");
          localStorage.clear();
          localStorage.setItem(themeKey, themeValue);
          localStorage.setItem(localeKey, "es");
        },
        [THEME_KEY, theme, LOCALE_KEY] as const,
      );
      const guards = attachGuards(page);
      await use(guards);
      await assertGuards(guards, testInfo);
    },
    { auto: true },
  ],
});

export { expect };
