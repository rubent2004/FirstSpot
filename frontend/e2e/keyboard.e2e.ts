import type { Page } from "@playwright/test";
import { expect, test } from "./support/fixtures";
import { HISTORICAL_EVENT, gotoApp, widenEventCatalogue } from "./support/app";

/**
 * Keyboard only: no click, no hover. Every control is reached with Tab (or the
 * keys the control documents) from the top of the page.
 */

interface Focused {
  tag: string;
  type: string | null;
  role: string | null;
  name: string;
  testid: string | null;
  inDialog: boolean;
}

async function focused(page: Page): Promise<Focused> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    const labelled = el?.getAttribute("aria-labelledby");
    const name =
      el?.getAttribute("aria-label") ??
      (labelled ? document.getElementById(labelled)?.textContent : null) ??
      (el instanceof HTMLInputElement ? el.labels?.[0]?.textContent : null) ??
      el?.textContent ??
      "";
    return {
      tag: el?.tagName.toLowerCase() ?? "",
      type: el?.getAttribute("type") ?? null,
      role: el?.getAttribute("role") ?? null,
      name: name.replace(/\s+/g, " ").trim(),
      testid: el?.getAttribute("data-testid") ?? null,
      inDialog: Boolean(el?.closest('[role="dialog"]')),
    };
  });
}

/** Press Tab until the focused element matches, failing after `max` presses. */
async function tabTo(page: Page, match: (f: Focused) => boolean, what: string, max = 120): Promise<Focused> {
  const seen: string[] = [];
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const f = await focused(page);
    seen.push(`${f.tag}${f.role ? `[${f.role}]` : ""} "${f.name.slice(0, 40)}"`);
    if (match(f)) return f;
  }
  throw new Error(`could not Tab to ${what} in ${max} presses. Focus went through:\n${seen.join("\n")}`);
}

async function startFromTop(page: Page): Promise<void> {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.locator("body").focus();
}

test.describe("keyboard only", () => {
  test("mode control: reach it, switch to event, pick an event, and back to baseline", async ({ page }) => {
    await widenEventCatalogue(page);
    await gotoApp(page);
    await startFromTop(page);
    await tabTo(page, (f) => f.tag === "input" && /Línea base|Evento/.test(f.name), "the mode control");
    const badge = page.getByTestId("mode-badge");
    await expect(badge).toContainText("Línea base");

    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("radio", { name: "Evento" })).toBeChecked();
    // The event picker takes focus, so the next step is one key away.
    const picker = page.getByRole("region", { name: "Modo" }).getByRole("combobox", { name: "Evento" });
    await expect(picker).toBeFocused();
    await page.keyboard.press("Enter");
    await page.keyboard.type("Acajutla");
    await page.keyboard.press("ArrowDown");
    await expect(page.getByRole("option", { name: HISTORICAL_EVENT.label })).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("event-facts")).toContainText(HISTORICAL_EVENT.place, { timeout: 30_000 });
    await expect(badge).toContainText("Evento");

    // Back to baseline with Shift+Tab to the segmented control and the arrow key.
    await page.keyboard.press("Escape");
    for (let i = 0; i < 6 && (await focused(page)).type !== "radio"; i++) {
      await page.keyboard.press("Shift+Tab");
    }
    const at = await focused(page);
    expect(at, "focus is on the checked mode radio").toMatchObject({ type: "radio", name: "Evento" });
    await page.keyboard.press("ArrowLeft");
    await expect(badge).toContainText("Línea base");
  });

  test("district list and detail: open with Enter, close with Esc and with the Close button", async ({ page }) => {
    await gotoApp(page);
    await startFromTop(page);
    await tabTo(page, (f) => f.testid === "district-row", "the first district row");
    const rowName = (await focused(page)).name;
    await page.keyboard.press("Enter");
    const heading = page.getByTestId("detail-heading");
    await expect(heading).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("detail-panel")).toHaveCount(0);
    expect((await focused(page)).name).toBe(rowName);

    // The list is a single Tab stop (roving tabindex): ArrowDown, End and Home move within it.
    await page.keyboard.press("End");
    const last = await focused(page);
    expect(last.testid).toBe("district-row");
    expect(last.name).not.toBe(rowName);
    await page.keyboard.press("Home");
    expect((await focused(page)).name).toBe(rowName);
    await page.keyboard.press("ArrowDown");
    const second = await focused(page);
    expect(second.testid).toBe("district-row");
    expect(second.name).not.toBe(rowName);
    // Open it, then close it with the detail's own button.
    await page.keyboard.press("Enter");
    await expect(heading).toBeFocused();
    await tabTo(page, (f) => f.tag === "button" && f.name === "Cerrar", "the detail's Close button", 10);
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("detail-panel")).toHaveCount(0);
    expect((await focused(page)).name).toBe(second.name);
  });

  test("export dialog: focus is trapped inside, Esc closes it and returns focus to Export", async ({ page }) => {
    await gotoApp(page);
    await startFromTop(page);
    await tabTo(page, (f) => f.tag === "button" && f.name === "Exportar", "the Export button");
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Exportar" });
    await expect(dialog).toBeVisible();
    await expect.poll(async () => (await focused(page)).inDialog).toBe(true);

    // Forty Tabs and twenty Shift+Tabs never leave the dialog.
    for (let i = 0; i < 40; i++) {
      await page.keyboard.press("Tab");
      expect((await focused(page)).inDialog, `Tab #${i + 1} stays in the dialog`).toBe(true);
    }
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press("Shift+Tab");
      expect((await focused(page)).inDialog, `Shift+Tab #${i + 1} stays in the dialog`).toBe(true);
    }

    // Formats are a radio group: arrows move between them.
    await startFromDialogFormat(page);
    await page.keyboard.press("ArrowRight");
    await expect(dialog.getByRole("radio", { name: /^CSV/ })).toBeChecked();

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("button", { name: "Exportar" }).first()).toBeFocused();
  });

  test("ribbon collapses and expands with Ctrl+F1", async ({ page }) => {
    await gotoApp(page);
    const toggle = page.getByRole("button", { name: /^(Contraer|Expandir) cinta$/ });
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("tabpanel", { name: "Inicio" })).toBeVisible();

    await page.keyboard.press("Control+F1");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByRole("tabpanel", { name: "Inicio" })).toBeHidden();

    await page.keyboard.press("Control+F1");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("tabpanel", { name: "Inicio" })).toBeVisible();

    // The toggle itself is reachable and works with Enter.
    await startFromTop(page);
    await tabTo(page, (f) => f.tag === "button" && /cinta/.test(f.name), "the ribbon toggle");
    await page.keyboard.press("Enter");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await page.keyboard.press("Enter");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
  });
});

/** Move focus to the checked format radio from wherever focus is in the dialog. */
async function startFromDialogFormat(page: Page): Promise<void> {
  for (let i = 0; i < 40; i++) {
    const f = await focused(page);
    if (f.tag === "input" && /\.xlsx/.test(f.name)) return;
    await page.keyboard.press("Tab");
  }
  throw new Error("could not reach the format radios");
}
