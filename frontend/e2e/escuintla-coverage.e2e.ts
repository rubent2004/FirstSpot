import { writeFileSync } from "node:fs";
import { expect, test } from "./support/fixtures";
import {
  artifactPath,
  chooseFormat,
  gotoApp,
  openExportDialog,
  printSheet,
  selectZone,
  submitExport,
  waitForPrintMap,
} from "./support/app";
import { readPdfText, squash } from "./support/files";

/**
 * Escuintla (Guatemala) is outside the Salvadoran census: the current-view print
 * must say so, and must carry no district ranking and no population figure.
 */

const NO_CENSUS = "Sin cobertura censal en esta zona";
const COVERAGE_OUT =
  "Esta zona está fuera de la cobertura del censo y del índice de distritos de El Salvador: no hay población estimada ni ranking de distritos para ella.";

test.describe("Escuintla, outside census coverage", () => {
  test("population and district sections are disabled, each with its reason", async ({ page }) => {
    await gotoApp(page);
    await selectZone(page, "Escuintla", "Escuintla");
    const dialog = await openExportDialog(page);
    await chooseFormat(dialog, "Mapa de la vista actual");
    const options = dialog.getByTestId("map-options");

    const district = options.getByRole("checkbox", { name: /^Detalle del distrito seleccionado/ });
    await expect(district).toBeDisabled();
    await expect(district).not.toBeChecked();
    await expect(district).toHaveAccessibleDescription(NO_CENSUS);

    const contacts = options.getByRole("checkbox", { name: /^Líneas de emergencia/ });
    await expect(contacts).toBeDisabled();
    await expect(contacts).toHaveAccessibleDescription("Los números disponibles son de El Salvador");

    // The places list is available (the zone has places), but not their population.
    const places = options.getByRole("checkbox", { name: /^Lugares por prioridad/ });
    await expect(places).toBeEnabled();
    await places.check();
    const population = options.getByRole("checkbox", { name: "Población est." });
    await expect(population).toBeDisabled();
    await expect(population).not.toBeChecked();
    await expect(population).toHaveAccessibleDescription(NO_CENSUS);

    // "Completo" never selects a section without data.
    await options.getByRole("button", { name: "Completo" }).click();
    await expect(district).not.toBeChecked();
    await expect(contacts).not.toBeChecked();
  });

  test("the current-view print states there is no census coverage, with no ranking and no population", async ({ page }) => {
    await gotoApp(page);
    await selectZone(page, "Escuintla", "Escuintla");
    const dialog = await openExportDialog(page);
    await chooseFormat(dialog, "Mapa de la vista actual");
    await dialog.getByRole("button", { name: "Completo" }).click();
    const filename = (await dialog.getByTestId("export-filename").textContent()) ?? "map.pdf";
    await submitExport(dialog);

    const sheet = printSheet(page);
    await expect(sheet).toBeVisible();
    await waitForPrintMap(page);
    const body = sheet.getByTestId("map-print-body");
    await expect(body.getByTestId("map-print-title")).toHaveText("Escuintla — Mapa de prioridad");
    await expect(body.getByTestId("coverage-out")).toHaveText(COVERAGE_OUT);
    await expect(body.getByTestId("section-district")).toHaveCount(0);
    await expect(body.getByTestId("section-contacts")).toHaveCount(0);
    await expect(body.getByTestId("section-limits")).toContainText(COVERAGE_OUT);
    const places = body.getByTestId("section-places");
    await expect(places).toBeVisible();
    await expect(places.getByRole("columnheader", { name: /Población/i })).toHaveCount(0);

    await page.screenshot({ path: artifactPath("escuintla", "map-print-screen.png"), fullPage: true });
    await page.emulateMedia({ media: "print" });
    const pdfPath = artifactPath("escuintla", `map-print--${filename}`);
    await page.pdf({ path: pdfPath, printBackground: true, preferCSSPageSize: true });
    await page.emulateMedia({ media: "screen" });

    const pdf = readPdfText(pdfPath);
    writeFileSync(`${pdfPath}.txt`, pdf.text);
    const text = squash(pdf.text);
    expect(text).toContain("Escuintla — Mapa de prioridad");
    expect(text).toContain(squash(COVERAGE_OUT));
    expect(text).toContain("BCR/ONEC, CPV 2024");
    // No national ranking: no rank/score vocabulary and no Salvadoran district names.
    expect(text).not.toMatch(/Puesto \d+|Prioridad \(0-10\)|Ranking nacional/);
    for (const name of ["Acajutla", "Sonsonate", "San Salvador", "Victoria", "Lislique"]) {
      expect(text, `no Salvadoran district (${name})`).not.toContain(name);
    }
    // No population figure of any kind.
    expect(text.toUpperCase()).not.toContain("POBLACIÓN EST.");
    expect(text).not.toMatch(/Población expuesta|Adultos mayores|Niñez pequeña/);
  });
});
