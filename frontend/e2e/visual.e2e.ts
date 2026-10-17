import type { Page } from "@playwright/test";
import { expect, test } from "./support/fixtures";
import {
  artifactPath,
  chooseFormat,
  districtButton,
  gotoApp,
  printSheet,
  submitExport,
  waitForMapIdle,
  waitForPrintMap,
} from "./support/app";

/**
 * Screenshots for a human to review: no pixel assertions, because there is no
 * approved baseline yet. Files land in e2e-artifacts/screenshots/.
 */

const VIEWPORTS = {
  desktop: { viewport: { width: 1920, height: 1080 }, hasTouch: false, isMobile: false },
  phone: { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true },
} as const;

async function shot(page: Page, name: string): Promise<void> {
  // Let transitions and tiles settle so the picture is what a person would see.
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
  await page.screenshot({ path: artifactPath("screenshots", `${name}.png`), fullPage: true, animations: "disabled" });
}

/** Opens the export dialog from the desktop button, or from the phone's "more" menu. */
async function openExport(page: Page, phone: boolean) {
  if (phone) {
    await page.getByRole("button", { name: "Más acciones" }).tap();
    await page.getByRole("menuitem", { name: "Exportar" }).tap();
  } else {
    await page.getByRole("button", { name: "Exportar" }).first().click();
  }
  const dialog = page.getByRole("dialog", { name: "Exportar" });
  await expect(dialog).toBeVisible();
  return dialog;
}

for (const [device, options] of Object.entries(VIEWPORTS)) {
  for (const theme of ["light", "dark"] as const) {
    test.describe(`screenshots, ${device}, ${theme}`, () => {
      test.use({ ...options, theme });
      const phone = device === "phone";
      const tag = `${device}-${theme}`;

      test("main view, detail panel, export dialog, print preview", async ({ page }) => {
        await gotoApp(page);
        await waitForMapIdle(page);
        await shot(page, `${tag}-01-main`);

        if (phone) {
          // The list is a bottom sheet over the map: expanded state too.
          const handle = page.getByRole("button", { name: "Ampliar la lista" });
          await handle.tap();
          await expect(page.getByRole("button", { name: "Reducir la lista" })).toHaveAttribute("aria-expanded", "true");
          await shot(page, `${tag}-02-bottom-sheet-expanded`);
          await districtButton(page, "Acajutla").tap();
        } else {
          await districtButton(page, "Acajutla").click();
        }
        await expect(page.getByTestId("detail-panel")).toBeVisible();
        await shot(page, `${tag}-03-detail`);
        await page.keyboard.press("Escape");
        await expect(page.getByTestId("detail-panel")).toHaveCount(0);

        const dialog = await openExport(page, phone);
        await shot(page, `${tag}-04-export-dialog-xlsx`);
        await chooseFormat(dialog, "Mapa de la vista actual");
        await shot(page, `${tag}-05-export-dialog-map`);

        await submitExport(dialog);
        await expect(printSheet(page)).toBeVisible();
        await waitForPrintMap(page);
        await shot(page, `${tag}-06-print-preview`);
      });
    });
  }
}
