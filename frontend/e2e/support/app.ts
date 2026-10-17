import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Locator, type Page, type Route } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));

/** Everything a human should look at after a run lands under this folder. */
export const ARTIFACTS_DIR = path.resolve(here, "..", "..", "e2e-artifacts");

export function artifactPath(...parts: string[]): string {
  const target = path.join(ARTIFACTS_DIR, ...parts);
  mkdirSync(path.dirname(target), { recursive: true });
  return target;
}

/**
 * A real USGS event that has a ShakeMap and a PAGER alert: M5.8, 10 km E of
 * Acajutla, 2025-01-09. The live catalogue only lists recent events, and none of
 * them has a ShakeMap today, so event mode cannot be reached from the picker.
 */
export const HISTORICAL_EVENT = {
  id: "us6000pixh",
  label: /M5\.8 · 10 km E of Acajutla/,
  place: "10 km E of Acajutla, El Salvador",
} as const;

/**
 * Widen the REAL event catalogue request to a longer window, so the picker
 * offers historical events with a ShakeMap. The request still goes to the real
 * backend; only its query string changes. This is not a mock.
 */
export async function widenEventCatalogue(page: Page): Promise<void> {
  await page.route("**/api/v1/prioritization/hazard-exposure/events**", async (route: Route) => {
    const url = new URL(route.request().url());
    url.searchParams.set("start_time", "2025-01-01");
    url.searchParams.set("min_magnitude", "5.5");
    url.searchParams.set("limit", "50");
    await route.continue({ url: url.toString() });
  });
}

export async function gotoApp(page: Page): Promise<void> {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Prioridad por distrito" })).toBeVisible();
  // The list is the first thing that needs the real API: wait until it has rows.
  await expect(page.getByTestId("district-row").first()).toBeVisible({ timeout: 30_000 });
}

export function triageList(page: Page): Locator {
  return page.getByRole("region", { name: "Distritos ordenados por prioridad" });
}

export function modeRegion(page: Page): Locator {
  return page.getByRole("region", { name: "Modo" });
}

export function districtButton(page: Page, name: string): Locator {
  return triageList(page).getByRole("button", { name: new RegExp(`^${name}, `) });
}

/** Choose a predefined work zone from the ribbon, by its visible name. */
export async function selectZone(page: Page, zoneName: string, department: string): Promise<void> {
  const select = page.locator(".geo-zone-select");
  await select.click();
  await page.keyboard.type(zoneName);
  await page.getByRole("option", { name: `${zoneName} · ${department}`, exact: true }).click();
  await expect(page.locator(".geo-zone-select")).toContainText(`${zoneName} · ${department}`);
  // The zone change reloads places for the new area; give the map its data.
  await page.waitForLoadState("networkidle");
  await waitForMapIdle(page);
}

/**
 * Waits until the live map's camera stops moving (a zone change flies the map).
 * Leaflet moves the map pane with a CSS transform; when it holds still across
 * several samples, the fly is over.
 */
export async function waitForMapIdle(page: Page): Promise<void> {
  await page.waitForFunction(
    () => {
      const w = window as unknown as { __e2eMapSamples?: string[] };
      const pane = document.querySelector<HTMLElement>('[data-testid="map-panel"] .leaflet-map-pane');
      if (!pane) return false;
      const animating = document.querySelector('[data-testid="map-panel"] .leaflet-zoom-anim');
      const sample = `${pane.style.transform}|${animating ? "anim" : ""}`;
      const samples = (w.__e2eMapSamples = [...(w.__e2eMapSamples ?? []), sample].slice(-4));
      return samples.length === 4 && !animating && samples.every((s) => s === samples[0]);
    },
    undefined,
    { polling: 250, timeout: 20_000 },
  );
}

export async function chooseMode(page: Page, mode: "Línea base" | "Evento"): Promise<void> {
  await page.getByRole("radiogroup", { name: "Modo" }).getByText(mode, { exact: true }).click();
}

/** Switch to event mode on the historical event (needs widenEventCatalogue first). */
export async function enterEventMode(page: Page): Promise<void> {
  await chooseMode(page, "Evento");
  const picker = modeRegion(page).getByRole("combobox", { name: "Evento" });
  await picker.click();
  await page.getByRole("option", { name: HISTORICAL_EVENT.label }).click();
  await expect(page.getByTestId("event-facts")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("mode-badge")).toContainText("Evento");
  await expect(page.getByTestId("mode-badge")).not.toContainText("Actualizando");
}

export async function openExportDialog(page: Page): Promise<Locator> {
  await page.getByRole("button", { name: "Exportar" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Exportar" });
  await expect(dialog).toBeVisible();
  return dialog;
}

export type FormatName = "Excel" | "CSV" | "Ranking nacional de distritos" | "Mapa de la vista actual";

export async function chooseFormat(dialog: Locator, format: FormatName): Promise<void> {
  const cards = dialog.getByRole("group", { name: "Formato" }).locator("label.card");
  await cards.filter({ has: dialog.page().locator("strong", { hasText: new RegExp(`^${format}$`) }) }).click();
  await expect(dialog.getByRole("radio", { name: new RegExp(`^${format}`) })).toBeChecked();
}

export async function submitExport(dialog: Locator): Promise<void> {
  await dialog.getByRole("button", { name: "Exportar", exact: true }).click();
}

export function printSheet(page: Page): Locator {
  return page.getByTestId("print-sheet");
}

/** Waits for the printed map's tiles, so a screenshot or PDF is not blank grey. */
export async function waitForPrintMap(page: Page): Promise<void> {
  const map = page.getByTestId("print-map");
  await expect(map).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page
    .waitForFunction(
      () => {
        const tiles = [...document.querySelectorAll<HTMLImageElement>('[data-testid="print-map"] img.leaflet-tile')];
        return tiles.length > 0 && tiles.every((img) => img.complete);
      },
      undefined,
      { timeout: 20_000 },
    )
    .catch(() => undefined);
}

/** Visible text plus accessible-name attributes, the surface a raw id could leak through. */
export async function visibleSurfaceText(scope: Locator): Promise<string> {
  return scope.evaluate((root) => {
    const parts = [(root as HTMLElement).innerText];
    for (const el of root.querySelectorAll("[aria-label], [title], [alt], [placeholder]")) {
      for (const attr of ["aria-label", "title", "alt", "placeholder"]) {
        const value = el.getAttribute(attr);
        if (value) parts.push(value);
      }
    }
    return parts.join("\n");
  });
}
