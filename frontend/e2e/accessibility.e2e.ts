import { writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import type { Page, TestInfo } from "@playwright/test";
import { expect, test, type Theme } from "./support/fixtures";
import {
  artifactPath,
  chooseFormat,
  districtButton,
  gotoApp,
  openExportDialog,
  printSheet,
  submitExport,
  waitForPrintMap,
} from "./support/app";

/**
 * axe-core scan (WCAG 2.0/2.1/2.2 A and AA rules) of the four states an operator
 * works in, in both themes. Each state's full result is saved to
 * e2e-artifacts/axe/<theme>-<state>.json; violations are reported per state
 * (soft), so one run lists all of them.
 */

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

interface Summary {
  id: string;
  impact: string | null | undefined;
  help: string;
  nodes: number;
  targets: string[];
}

async function scan(page: Page, testInfo: TestInfo, theme: Theme, state: string, include?: string) {
  let builder = new AxeBuilder({ page }).withTags(TAGS);
  if (include) builder = builder.include(include);
  const results = await builder.analyze();
  const summary: Summary[] = results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.length,
    targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
  }));
  const file = artifactPath("axe", `${theme}-${state}.json`);
  writeFileSync(file, JSON.stringify({ state, theme, url: page.url(), violations: results.violations }, null, 2));
  await testInfo.attach(`axe-${theme}-${state}`, {
    body: JSON.stringify(summary, null, 2),
    contentType: "application/json",
  });
  expect.soft(summary, `axe violations: ${theme} / ${state}`).toEqual([]);
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`axe, ${theme} theme`, () => {
    test.use({ theme });

    test("main view", async ({ page }, testInfo) => {
      await gotoApp(page);
      await scan(page, testInfo, theme, "main");
    });

    test("detail panel open", async ({ page }, testInfo) => {
      await gotoApp(page);
      await districtButton(page, "Acajutla").click();
      await expect(page.getByTestId("detail-panel")).toBeVisible();
      await scan(page, testInfo, theme, "detail");
    });

    test("export dialog (file and map formats)", async ({ page }, testInfo) => {
      await gotoApp(page);
      const dialog = await openExportDialog(page);
      await scan(page, testInfo, theme, "export-dialog-xlsx", ".export-dialog");
      await chooseFormat(dialog, "Mapa de la vista actual");
      await scan(page, testInfo, theme, "export-dialog-map", ".export-dialog");
    });

    test("print view", async ({ page }, testInfo) => {
      await gotoApp(page);
      const dialog = await openExportDialog(page);
      await chooseFormat(dialog, "Mapa de la vista actual");
      await submitExport(dialog);
      await expect(printSheet(page)).toBeVisible();
      await waitForPrintMap(page);
      await scan(page, testInfo, theme, "print-view", '[data-testid="print-sheet"]');
    });
  });
}
