import { readFileSync, writeFileSync } from "node:fs";
import type { Page } from "@playwright/test";
import { expect, test } from "./support/fixtures";
import {
  artifactPath,
  chooseFormat,
  enterEventMode,
  gotoApp,
  openExportDialog,
  printSheet,
  selectZone,
  submitExport,
  waitForPrintMap,
  widenEventCatalogue,
  HISTORICAL_EVENT,
} from "./support/app";
import { parseCsv, readPdfText, readXlsx, squash, type Cell } from "./support/files";

/**
 * Full export run for the Acajutla work zone (key `acajutla`, Sonsonate, inside
 * census coverage): the current-view map print with sections, the xlsx and the
 * csv, in both modes. Every file is kept under e2e-artifacts/acajutla/ for a
 * human to open, and every file is opened here and checked.
 */

const ZONE = { name: "Acajutla", department: "Sonsonate" } as const;
const ATTRIBUTION = "BCR/ONEC, CPV 2024";
const TIMESTAMP = /\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC/;
/** The first limits line, present in every output (ReportModel.limitations[0]). */
const LIMITS_LINE = "Es un ranking relativo de territorios (distritos), no de personas.";
const NOTES = 'Punto de reunión: cancha "El Progreso", 14:00.\nLlevar agua — 3 bidones; ñandú ok.';

interface ApiDistrict {
  district_code: string;
  district_name: string;
  population: number | null;
  score: number | null;
  withheld: boolean;
  estimated_exposed_population: number | null;
  max_mmi: number | null;
}

type Mode = "baseline" | "event";
const MODE_LABEL: Record<Mode, string> = { baseline: "Línea base", event: "Evento" };

async function fetchIndex(page: Page, mode: Mode): Promise<ApiDistrict[]> {
  const query = mode === "event" ? `?event_id=${HISTORICAL_EVENT.id}` : "";
  const response = await page.request.get(`/api/v1/prioritization/index/districts${query}`);
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { districts: ApiDistrict[] }).districts;
}

async function prepare(page: Page, mode: Mode): Promise<void> {
  if (mode === "event") await widenEventCatalogue(page);
  await gotoApp(page);
  await selectZone(page, ZONE.name, ZONE.department);
  if (mode === "event") await enterEventMode(page);
}

async function download(page: Page, format: "Excel" | "CSV", target: string): Promise<string> {
  const dialog = await openExportDialog(page);
  await chooseFormat(dialog, format);
  const pending = page.waitForEvent("download");
  await submitExport(dialog);
  const file = await pending;
  const path = artifactPath("acajutla", `${target}--${file.suggestedFilename()}`);
  await file.saveAs(path);
  await expect(dialog).toBeHidden();
  return path;
}

/** Each exported row against the API row for the same district: no invented 0, no leaked figure. */
function checkRowsAgainstApi(
  header: Cell[],
  rows: Cell[][],
  api: ApiDistrict[],
  mode: Mode,
): void {
  const byName = new Map(api.map((d) => [d.district_name, d]));
  const col = (name: string) => header.findIndex((h) => h === name);
  const iName = col("Distrito");
  const iPop = col("Población");
  const iShake = col("Sacudida máx.");
  const iExposed = col("Expuestos (est.)");
  expect(iName, `header ${JSON.stringify(header)}`).toBeGreaterThanOrEqual(0);
  expect(iPop).toBeGreaterThanOrEqual(0);
  if (mode === "event") {
    expect(iShake).toBeGreaterThanOrEqual(0);
    expect(iExposed).toBeGreaterThanOrEqual(0);
  }
  const empty = (v: Cell | undefined) => v === null || v === undefined || v === "";
  for (const row of rows) {
    const district = byName.get(String(row[iName]));
    expect(district, `row ${JSON.stringify(row)} matches an API district`).toBeTruthy();
    if (!district) continue;
    if (district.withheld) {
      // Suppressed: no figure of any kind may travel.
      for (const [i, cell] of row.entries()) {
        if (i === iName) continue;
        expect(typeof cell === "number" || /^\d/.test(String(cell ?? ""))).toBe(false);
      }
      continue;
    }
    if (district.population === null) expect(empty(row[iPop])).toBe(true);
    else expect(Number(row[iPop])).toBe(district.population);
    if (mode === "event") {
      if (district.max_mmi === null) {
        expect(empty(row[iShake]), `${district.district_name}: no shaking must not export as 0`).toBe(true);
      } else expect(Number(row[iShake])).toBeCloseTo(district.max_mmi, 2);
      if (district.estimated_exposed_population === null) {
        expect(row[iExposed]).toBe("sin estimación");
      } else expect(Number(row[iExposed])).toBe(district.estimated_exposed_population);
    }
  }
}

for (const mode of ["baseline", "event"] as const) {
  test.describe(`Acajutla export run, ${mode} mode`, () => {
    test(`xlsx: ${mode}`, async ({ page }) => {
      await prepare(page, mode);
      const api = await fetchIndex(page, mode);
      const file = await download(page, "Excel", `${mode}-xlsx`);
      const book = readXlsx(file);
      const sheetNames = [...book.sheets.keys()];
      expect(sheetNames).toEqual(["Ranking", "Contexto y límites"]);

      const ranking = book.sheets.get("Ranking") ?? [];
      const context = book.sheets.get("Contexto y límites") ?? [];
      const allText = [...ranking, ...context].flat().filter((c) => c !== null).join("\n");
      writeFileSync(`${file}.txt`, allText);

      expect(allText).toContain(`${MODE_LABEL[mode]}`);
      expect(allText).toMatch(TIMESTAMP);
      expect(allText).toContain(ATTRIBUTION);
      expect(allText).toContain(LIMITS_LINE);
      if (mode === "event") {
        expect(allText).toContain(HISTORICAL_EVENT.place);
        expect(allText).toContain("2025-01-31 19:37 UTC");
      }
      // Acajutla is also a district row, so look for the zone only in the context sheet.
      // The event place ("10 km E of Acajutla") would satisfy a naive search; remove it first.
      const contextText = context.flat().filter((c) => c !== null).join("\n").replaceAll(HISTORICAL_EVENT.place, "");
      expect
        .soft(contextText, "the workbook context names the work zone it was exported for")
        .toContain(ZONE.name);

      const headerIndex = ranking.findIndex((r) => r.includes("Distrito"));
      expect(headerIndex).toBeGreaterThanOrEqual(0);
      const header = ranking[headerIndex];
      const rows = ranking.slice(headerIndex + 1).filter((r) => r.some((c) => c !== null));
      // "Lo que veo ahora": the 16 districts of Sonsonate, the zone's department.
      expect(rows).toHaveLength(16);
      checkRowsAgainstApi(header, rows, api, mode);
    });

    test(`csv: ${mode}`, async ({ page }) => {
      await prepare(page, mode);
      const api = await fetchIndex(page, mode);
      const file = await download(page, "CSV", `${mode}-csv`);
      const bytes = readFileSync(file);
      expect([...bytes.subarray(0, 3)], "UTF-8 byte order mark").toEqual([0xef, 0xbb, 0xbf]);
      const text = bytes.toString("utf8");
      expect(text, "no mojibake").not.toMatch(/Ã|Â|�/);
      expect(text).toContain("Santa Isabel Ishuatán");
      expect(text).toContain("Juayúa");

      const rows = parseCsv(text);
      const preamble = rows.slice(0, 3).flat().join("\n");
      expect(rows[0][0]).toBe("Informe de priorización de territorios");
      expect(preamble).toContain(`Modo: ${MODE_LABEL[mode]}`);
      expect(preamble).toMatch(new RegExp(`Generado: ${TIMESTAMP.source}`));
      expect(preamble).toContain(`Datos: ${ATTRIBUTION}`);
      expect(preamble).toContain(`Límites: ${LIMITS_LINE}`);
      if (mode === "event") {
        expect(preamble).toContain(HISTORICAL_EVENT.place);
        expect(preamble).toContain("Mapa de sacudida procesado: 2025-01-31 19:37 UTC");
        expect(preamble).toContain("Alerta PAGER (rango)");
      }
      expect
        .soft(preamble.replaceAll(HISTORICAL_EVENT.place, ""), "the file names the work zone it was exported for")
        .toContain(ZONE.name);

      const headerIndex = rows.findIndex((r) => r.includes("Distrito"));
      const header = rows[headerIndex];
      const blank = rows.findIndex((r, i) => i > headerIndex && r.length === 1 && r[0] === "");
      const body = rows.slice(headerIndex + 1, blank < 0 ? undefined : blank);
      expect(body).toHaveLength(16);
      const cells: Cell[][] = body.map((r) => r.map((c) => (c === "" ? null : c)));
      checkRowsAgainstApi(header, cells, api, mode);
    });

    test(`current-view map print with sections, saved as PDF: ${mode}`, async ({ page }) => {
      await prepare(page, mode);
      const dialog = await openExportDialog(page);
      await chooseFormat(dialog, "Mapa de la vista actual");
      await expect(dialog).toContainText("Se imprime la vista actual del mapa de Acajutla");
      await dialog.getByRole("group", { name: "Plantillas" }).getByRole("button", { name: "Completo" }).click();
      await dialog.getByRole("checkbox", { name: /^Notas del operador/ }).check();
      await dialog.getByRole("textbox", { name: "Notas del operador" }).fill(NOTES);
      const filename = (await dialog.getByTestId("export-filename").textContent()) ?? "map.pdf";
      await submitExport(dialog);

      const sheet = printSheet(page);
      await expect(sheet).toBeVisible();
      await waitForPrintMap(page);
      const body = sheet.getByTestId("map-print-body");
      await expect(body.getByTestId("map-print-title")).toHaveText("Acajutla — Mapa de prioridad");
      await expect(body.getByTestId("sheet-mode")).toHaveText(MODE_LABEL[mode]);
      await expect(body.getByTestId("coverage-out")).toHaveCount(0);
      await expect(body.getByTestId("section-places")).toBeVisible();
      await expect(body.getByTestId("section-counts")).toBeVisible();
      await expect(body.getByTestId("section-contacts")).toBeVisible();
      await expect(body.getByTestId("section-notes")).toBeVisible();
      await expect(body.getByTestId("section-limits")).toBeVisible();

      await page.screenshot({ path: artifactPath("acajutla", `${mode}-map-print-screen.png`), fullPage: true });
      await page.emulateMedia({ media: "print" });
      const pdfPath = artifactPath("acajutla", `${mode}-map-print--${filename}`);
      await page.pdf({ path: pdfPath, printBackground: true, preferCSSPageSize: true });
      await page.emulateMedia({ media: "screen" });

      const pdf = await readPdfText(pdfPath);
      writeFileSync(`${pdfPath}.txt`, pdf.text);
      const text = squash(pdf.text);
      expect(pdf.pages).toBeGreaterThanOrEqual(1);
      expect(text).toContain("Acajutla — Mapa de prioridad");
      expect(text).toContain(MODE_LABEL[mode]);
      expect(text).toMatch(TIMESTAMP);
      expect(text).toContain(LIMITS_LINE);
      expect(text).toContain(ATTRIBUTION);
      expect(text, "operator notes print verbatim").toContain(squash(NOTES));
      if (mode === "event") {
        expect(text).toContain(HISTORICAL_EVENT.place);
        expect(text).toContain("2025-01-31 19:37 UTC");
      }
      // No suppressed figure and no placeholder leaks into the paper.
      expect(text).not.toMatch(/\b(null|undefined|NaN)\b/);
      // Every chosen section reaches the paper, not just what fits on page one.
      const upper = text.toUpperCase();
      for (const heading of ["LUGARES POR PRIORIDAD", "CONTEOS", "LÍNEAS DE EMERGENCIA", "NOTAS DEL OPERADOR", "LÍMITES Y ATRIBUCIÓN"]) {
        expect(upper, `section "${heading}" printed`).toContain(heading);
      }
      // Screen-only chrome stays off the paper: the toolbar and the "print view ready" toast.
      expect(text).not.toContain("Imprimir / guardar PDF");
      expect(text).not.toContain("Vista de impresión lista");
    });
  });
}
