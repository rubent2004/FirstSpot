import { expect, test } from "./support/fixtures";
import {
  HISTORICAL_EVENT,
  chooseMode,
  districtButton,
  enterEventMode,
  gotoApp,
  modeRegion,
  triageList,
  visibleSurfaceText,
  widenEventCatalogue,
} from "./support/app";

test.describe("district triage on real data", () => {
  test("the list loads real districts from the running API", async ({ page }) => {
    const indexResponse = page.waitForResponse(
      (r) => r.url().includes("/api/v1/prioritization/index/districts") && r.ok(),
    );
    await gotoApp(page);
    const body = (await (await indexResponse).json()) as { districts: unknown[]; mode: string };
    expect(body.mode).toBe("baseline");
    expect(body.districts.length).toBeGreaterThan(200);

    // Default work zone is Sonsonate: the list is scoped to its 16 districts out of the national total.
    await expect(page.getByTestId("list-count")).toHaveText(
      `Mostrando 16 de ${body.districts.length} distritos`,
    );
    await expect(page.getByTestId("district-row")).toHaveCount(16);
    await expect(districtButton(page, "Acajutla")).toBeVisible();
  });

  test("mode control switches baseline and event, and the mode is always stated", async ({ page }) => {
    await widenEventCatalogue(page);
    await gotoApp(page);
    const badge = page.getByTestId("mode-badge");
    await expect(badge).toContainText("Línea base");

    // Asking for event mode without an event keeps saying what is on screen.
    await chooseMode(page, "Evento");
    await expect(badge).toContainText("Línea base");
    await expect(badge).toContainText("Elige un sismo para ver el modo Evento.");

    await enterEventMode(page);
    const facts = page.getByTestId("event-facts");
    await expect(facts).toContainText(HISTORICAL_EVENT.place);
    await expect(facts).toContainText("M5.8");
    await expect(facts).toContainText("Mapa de sacudida (ShakeMap) procesado");
    // ShakeMap grid time, as published by USGS (2025-01-31 19:37:47 UTC).
    await expect(facts).toContainText(/2025-01-31/);
    await expect(facts).not.toContainText("Sin hora de procesamiento publicada");
    await expect(facts).toContainText("Alerta PAGER (USGS)");
    await expect(facts).toContainText(/0 .*PAGER|verde/i);
    await expect(facts).toContainText("Es un rango, no un conteo");

    // The whole list re-ranks in event mode: the status says so and the list is still there.
    await expect(badge).toContainText("Evento");
    await expect(page.getByTestId("district-row").first()).toBeVisible();

    await chooseMode(page, "Línea base");
    await expect(badge).toContainText("Línea base");
    await expect(page.getByTestId("event-facts")).toHaveCount(0);
  });

  test("selecting a district opens its detail; Esc and Close return focus to the row", async ({ page }) => {
    await gotoApp(page);
    const row = districtButton(page, "Acajutla");
    await row.click();
    const detail = page.getByTestId("detail-panel");
    await expect(detail).toBeVisible();
    await expect(page.getByTestId("detail-heading")).toHaveText("Acajutla");
    await expect(page.getByTestId("detail-heading")).toBeFocused();
    await expect(detail).toContainText(/Puesto \d+ de \d+/);

    await page.keyboard.press("Escape");
    await expect(detail).toHaveCount(0);
    await expect(row).toBeFocused();

    await row.click();
    await expect(detail).toBeVisible();
    await detail.getByRole("button", { name: "Cerrar" }).click();
    await expect(detail).toHaveCount(0);
    await expect(row).toBeFocused();
  });

  test("the scope toggle changes the count", async ({ page }) => {
    await gotoApp(page);
    const count = page.getByTestId("list-count");
    await expect(count).toHaveText(/^Mostrando 16 de (\d+) distritos$/);
    const total = Number(/de (\d+)/.exec((await count.textContent()) ?? "")?.[1]);

    await triageList(page).getByRole("radiogroup", { name: "Alcance" }).getByText("Todo el país").click();
    await expect(count).toHaveText(`Mostrando ${total} de ${total} distritos`);

    await triageList(page).getByRole("radiogroup", { name: "Alcance" }).getByText("Solo Sonsonate").click();
    await expect(count).toHaveText(`Mostrando 16 de ${total} distritos`);
  });

  test("no raw ids or backend keys reach the screen", async ({ page }) => {
    await widenEventCatalogue(page);
    await gotoApp(page);
    await districtButton(page, "Acajutla").click();
    await expect(page.getByTestId("detail-panel")).toBeVisible();
    await page.getByTestId("detail-panel").getByText("Indicadores, necesidades Sphere y fuentes").click();

    const leaks = async () => {
      const text = await visibleSurfaceText(page.locator("body"));
      return {
        districtCodes: text.match(/\b\d{6}\b/g) ?? [],
        snakeCaseKeys: (text.match(/\b[a-z]+(?:_[a-z]+)+\b/g) ?? []).filter((k) => !k.startsWith("http")),
        alertClassKeys: text.match(/\b(roja|naranja|amarilla|verde)\b/g) ?? [],
        eventIds: text.match(/\bus[0-9a-z]{8}\b/g) ?? [],
        nullish: text.match(/\b(null|undefined|NaN)\b/g) ?? [],
      };
    };
    const baseline = await leaks();
    expect(baseline).toEqual({ districtCodes: [], snakeCaseKeys: [], alertClassKeys: [], eventIds: [], nullish: [] });

    await page.keyboard.press("Escape");
    await enterEventMode(page);
    await districtButton(page, "Acajutla").click();
    await expect(page.getByTestId("detail-panel")).toBeVisible();
    const event = await leaks();
    // "verde" is the legitimate Spanish PAGER level word, shown as such in event mode.
    expect({ ...event, alertClassKeys: event.alertClassKeys.filter((k) => k !== "verde") }).toEqual({
      districtCodes: [],
      snakeCaseKeys: [],
      alertClassKeys: [],
      eventIds: [],
      nullish: [],
    });
    await expect(modeRegion(page)).toBeVisible();
  });
});
