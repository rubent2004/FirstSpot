import type { Locator, Page } from "@playwright/test";
import { expect, test } from "./support/fixtures";
import {
  chooseFormat,
  districtButton,
  gotoApp,
  openExportDialog,
  printSheet,
  selectZone,
  submitExport,
} from "./support/app";

/** Section checkboxes in print order, by the name the operator reads. */
const SECTIONS = {
  map: "Mapa de la vista actual",
  places: "Lugares por prioridad",
  placeDetail: "Detalle del lugar seleccionado",
  counts: "Conteos",
  districtDetail: "Detalle del distrito seleccionado",
  hazards: "Amenazas activas",
  weather: "Clima actual",
  contacts: "Líneas de emergencia",
  notes: "Notas del operador",
  limits: "Límites y atribución",
} as const;
type SectionId = keyof typeof SECTIONS;
const ALL = Object.keys(SECTIONS) as SectionId[];

const PRESETS: Record<"Resumen" | "Completo" | "Despacho de un lugar", SectionId[]> = {
  Resumen: ["map", "places", "contacts", "limits"],
  Completo: ALL,
  "Despacho de un lugar": ["map", "placeDetail", "contacts", "limits"],
};

const box = (options: Locator, id: SectionId) =>
  options.getByRole("checkbox", { name: new RegExp(`^${SECTIONS[id]}`) });

async function openMapOptions(page: Page): Promise<Locator> {
  const dialog = await openExportDialog(page);
  await chooseFormat(dialog, "Mapa de la vista actual");
  return dialog.getByTestId("map-options");
}

/** Which sections can be ticked right now: available ones, plus the two locked ones. */
async function selectable(options: Locator): Promise<Set<SectionId>> {
  const result = new Set<SectionId>();
  for (const id of ALL) {
    const checkbox = box(options, id);
    if (id === "map" || id === "limits" || (await checkbox.isEnabled())) result.add(id);
  }
  return result;
}

test.describe("print sections and presets (Acajutla, in coverage)", () => {
  test.beforeEach(async ({ page }) => {
    await gotoApp(page);
    await selectZone(page, "Acajutla", "Sonsonate");
  });

  test("each preset ticks exactly its sections that have data", async ({ page }) => {
    const options = await openMapOptions(page);
    const canTick = await selectable(options);
    for (const [preset, wanted] of Object.entries(PRESETS)) {
      await options.getByRole("group", { name: "Plantillas" }).getByRole("button", { name: preset }).click();
      const expected = wanted.filter((id) => canTick.has(id));
      for (const id of ALL) {
        const checkbox = box(options, id);
        if (expected.includes(id)) await expect(checkbox, `${preset}: ${id}`).toBeChecked();
        else await expect(checkbox, `${preset}: ${id}`).not.toBeChecked();
      }
      await expect(options.getByTestId("section-count")).toHaveText(`${expected.length} secciones seleccionadas`);
    }
  });

  test("a section without data is disabled with its reason; map and limits are locked on", async ({ page }) => {
    const options = await openMapOptions(page);
    // No place selected on the map, no district open.
    await expect(box(options, "placeDetail")).toBeDisabled();
    await expect(box(options, "placeDetail")).toHaveAccessibleDescription("Ningún lugar seleccionado");
    await expect(box(options, "districtDetail")).toBeDisabled();
    await expect(box(options, "districtDetail")).toHaveAccessibleDescription("Ningún distrito seleccionado");
    for (const id of ["map", "limits"] as const) {
      await expect(box(options, id)).toBeChecked();
      await expect(box(options, id)).toBeDisabled();
      await expect(box(options, id)).toHaveAccessibleDescription("Siempre incluido");
    }
    // Every disabled section says why.
    for (const id of ALL) {
      const checkbox = box(options, id);
      if (await checkbox.isDisabled()) {
        const description = await checkbox.evaluate((el) => {
          const ids = el.getAttribute("aria-describedby")?.split(/\s+/) ?? [];
          return ids.map((i) => document.getElementById(i)?.textContent?.trim() ?? "").join(" ");
        });
        expect(description, `${id} has a visible reason`).not.toBe("");
      }
    }
  });

  test("opening a district makes its section available", async ({ page }) => {
    await districtButton(page, "Acajutla").click();
    await expect(page.getByTestId("detail-panel")).toBeVisible();
    const options = await openMapOptions(page);
    await expect(box(options, "districtDetail")).toBeEnabled();
    await options.getByRole("button", { name: "Completo" }).click();
    await expect(box(options, "districtDetail")).toBeChecked();
    await submitExport(page.getByRole("dialog", { name: "Exportar" }));
    const body = printSheet(page).getByTestId("map-print-body");
    await expect(body.getByTestId("map-print-title")).toHaveText("Acajutla");
    await expect(body.getByTestId("section-district")).toBeVisible();
  });

  test("operator notes print verbatim, and the limits print even when nothing else is chosen", async ({ page }) => {
    const options = await openMapOptions(page);
    // Untick everything that can be unticked.
    for (const id of ALL) {
      const checkbox = box(options, id);
      if ((await checkbox.isEnabled()) && (await checkbox.isChecked())) await checkbox.uncheck();
    }
    await expect(options.getByTestId("section-count")).toHaveText("2 secciones seleccionadas");
    await box(options, "notes").check();
    const notes = '<b>Brigada</b> "Norte" & Cía.\n  línea con sangría\n\n=SUMA(A1) ñ á é í ó ú ü — 100%';
    await options.getByRole("textbox", { name: "Notas del operador" }).fill(notes);
    await submitExport(page.getByRole("dialog", { name: "Exportar" }));

    const body = printSheet(page).getByTestId("map-print-body");
    const section = body.getByTestId("section-notes");
    await expect(section).toBeVisible();
    const printed = await section.locator(".notes").evaluate((el) => el.textContent);
    expect(printed).toBe(notes);
    // Shown as text, never interpreted as markup.
    await expect(section.locator("b")).toHaveCount(0);
    await expect(body.getByTestId("section-limits")).toBeVisible();
    await expect(body.getByTestId("section-limits")).toContainText("BCR/ONEC, CPV 2024");
    for (const id of ["section-places", "section-counts", "section-contacts", "section-weather"]) {
      await expect(body.getByTestId(id)).toHaveCount(0);
    }
  });
});
