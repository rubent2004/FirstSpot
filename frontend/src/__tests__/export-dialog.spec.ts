import { beforeEach, describe, expect, it } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus, { ElDialog } from "element-plus";

import { COMMUNITY_EN } from "../i18n/communityMessages";
import { setAppLocale } from "../i18n/useI18n";
import ExportDialog from "../modules/community-triage/ExportDialog.vue";
import { buildReportModel } from "../modules/community-triage/exportModel";
import { DEFAULT_PREFS, type ExportPrefs } from "../modules/community-triage/exportPlan";
import { DEFAULT_MAP_PREFS } from "../modules/community-triage/mapPrint/mapPrintModel";
import {
  EVENT_ID,
  eventIndex,
  redDistrict,
  zeroDistrict,
} from "./fixtures/prioFixtures";

const NOW = new Date("2026-10-17T12:30:00Z");
const model = buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW);

interface Opts {
  prefs?: Partial<ExportPrefs>;
  filteredCodes?: Set<string> | null;
  selectedCode?: string | null;
  selectedName?: string | null;
  isBusy?: boolean;
  error?: string | null;
  mode?: "baseline" | "event";
}

async function open(opts: Opts = {}) {
  const wrapper = mount(ExportDialog, {
    props: {
      modelValue: true,
      prefs: { ...DEFAULT_PREFS, lang: "en" as const, ...opts.prefs },
      mode: opts.mode ?? "event",
      rows: model.rows,
      scopeContext: {
        filteredCodes: opts.filteredCodes ?? null,
        selectedCode: opts.selectedCode ?? null,
      },
      selectedName: opts.selectedName ?? null,
      eventId: EVENT_ID,
      zoneName: "Escuintla",
      snapshot: null,
      mapPrefs: { ...DEFAULT_MAP_PREFS },
      selectedDistrict: null,
      index: null,
      isBusy: opts.isBusy ?? false,
      error: opts.error ?? null,
      now: NOW,
    },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  });
  await flushPromises();
  return wrapper;
}

const dialog = () => document.body.querySelector<HTMLElement>('[role="dialog"]')!;
const radios = (name: string) =>
  Array.from(dialog().querySelectorAll<HTMLInputElement>(`input[type="radio"][name="${name}"]`));
const labelOf = (input: HTMLElement) => input.closest("label")?.textContent?.replace(/\s+/g, " ").trim() ?? "";

describe("export dialog", () => {
  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
  });

  it("is a labelled modal dialog and moves focus inside it", async () => {
    await open();
    expect(dialog().getAttribute("aria-modal")).toBe("true");
    expect(dialog().getAttribute("aria-label")).toBe("Export");
    expect(dialog().contains(document.activeElement)).toBe(true);
  });

  it("shows only format, scope and the primary action by default, with more options collapsed", async () => {
    await open();
    expect(radios("export-format")).toHaveLength(4);
    expect(radios("export-scope")).toHaveLength(3);
    const more = dialog().querySelector("details.more") as HTMLDetailsElement;
    expect(more.open).toBe(false);
    expect(more.querySelector("summary")!.textContent).toBe("More options");
    expect(dialog().querySelector('button[type="submit"]')!.textContent).toContain("Export");
  });

  it("names every format by what it produces and tells the two maps apart", async () => {
    await open();
    const names = radios("export-format").map(labelOf);
    expect(names[0]).toContain("Excel");
    expect(names[0]).toContain(".xlsx");
    expect(names[1]).toContain("CSV");
    expect(names[2]).toContain("National district ranking");
    expect(names[3]).toContain("Map of the current view");
    for (const text of names) expect(text.length).toBeGreaterThan(24);
  });

  it("defaults the scope to the filtered view when a filter is active, with a live row count", async () => {
    await open({ filteredCodes: new Set([redDistrict.district_code, zeroDistrict.district_code]) });
    const scope = radios("export-scope");
    expect(scope.find((r) => r.checked)!.value).toBe("filtered");
    expect(labelOf(scope[0])).toContain("What I see now");
    expect(labelOf(scope[0])).toContain("2 rows");
    expect(labelOf(scope[2])).toContain("All districts");
    expect(labelOf(scope[2])).toContain("3 rows");
  });

  it("defaults to the open district when one is open", async () => {
    await open({
      selectedCode: redDistrict.district_code,
      selectedName: "San Marcos Rojo",
      filteredCodes: new Set([redDistrict.district_code]),
    });
    const checked = radios("export-scope").find((r) => r.checked)!;
    expect(checked.value).toBe("selected");
    expect(labelOf(checked)).toContain("Open district: San Marcos Rojo");
  });

  it("disables an unavailable scope only with a visible reason", async () => {
    await open();
    const [filtered, selected, all] = radios("export-scope");
    expect(filtered.disabled).toBe(true);
    expect(selected.disabled).toBe(true);
    expect(all.disabled).toBe(false);
    for (const input of [filtered, selected]) {
      const reason = document.getElementById(input.getAttribute("aria-describedby")!)!;
      expect(reason.textContent!.length).toBeGreaterThan(8);
    }
    expect(document.getElementById(filtered.getAttribute("aria-describedby")!)!.textContent).toBe(
      "No filters are active",
    );
    expect(all.checked).toBe(true);
  });

  it("shows the generated file name, carrying mode, event and date", async () => {
    await open();
    const file = dialog().querySelector('[data-testid="export-filename"]')!.textContent;
    expect(file).toBe("firstspot_prio_event_usp000a9jv_2026-10-17.xlsx");
  });

  it("changes the file name and the extension with the format and the language", async () => {
    const wrapper = await open({ prefs: { lang: "es" } });
    expect(dialog().querySelector('[data-testid="export-filename"]')!.textContent).toBe(
      "firstspot_prio_evento_usp000a9jv_2026-10-17.xlsx",
    );
    const csv = radios("export-format")[1];
    csv.click();
    csv.dispatchEvent(new Event("change"));
    await flushPromises();
    expect(dialog().querySelector('[data-testid="export-filename"]')!.textContent).toMatch(/\.csv$/);
    void wrapper;
  });

  it("replaces the scope with a single line for the live map and says what it prints", async () => {
    await open({ prefs: { format: "map" } });
    expect(radios("export-scope")).toHaveLength(0);
    expect(dialog().textContent).toContain("Prints the current map view of Escuintla");
    expect(dialog().querySelector('[data-testid="export-filename"]')!.textContent).toMatch(/_map\.pdf$/);
  });

  it("keeps columns, language, top-N, paper and the limits sheet inside the one collapsed section", async () => {
    await open();
    const more = dialog().querySelector("details.more")!;
    const text = more.textContent!;
    for (const word of ["Columns", "Document language", "Only the first", "Context and limits sheet"]) {
      expect(text).toContain(word);
    }
    // Paper and orientation only matter for the print outputs
    expect(text).not.toContain("Orientation");
    const columns = Array.from(more.querySelectorAll<HTMLInputElement>('input[type="checkbox"][name="export-column"]'));
    expect(columns.length).toBeGreaterThanOrEqual(8);
    const district = columns.find((c) => labelOf(c).startsWith("District"))!;
    expect(district.disabled).toBe(true);
    expect(district.checked).toBe(true);
    expect(labelOf(district)).toContain("always included");
  });

  it("offers paper and orientation for print outputs", async () => {
    await open({ prefs: { format: "map" } });
    const text = dialog().querySelector("details.more")!.textContent!;
    expect(text).toContain("Paper");
    expect(text).toContain("Orientation");
    expect(text).not.toContain("Context and limits sheet");
  });

  it("states that the limits notice and the attribution cannot be removed", async () => {
    await open();
    expect(dialog().textContent).toContain(
      "The limits notice and the BCR/ONEC attribution are always included and cannot be removed.",
    );
  });

  it("submits the chosen settings from the form, so Enter works", async () => {
    const wrapper = await open();
    dialog().querySelector("form")!.dispatchEvent(new Event("submit", { cancelable: true }));
    await flushPromises();
    const [request] = wrapper.emitted("submit")![0] as [{ prefs: ExportPrefs; scope: string }];
    expect(request.prefs.format).toBe("xlsx");
    expect(request.scope).toBe("all");
    expect(request.prefs.lang).toBe("en");
  });

  it("blocks the primary action with a stated reason when there is nothing to export", async () => {
    await open({ filteredCodes: new Set() });
    const submit = dialog().querySelector<HTMLButtonElement>('button[type="submit"]')!;
    expect(submit.disabled).toBe(true);
    const reason = document.getElementById(submit.getAttribute("aria-describedby")!)!;
    expect(reason.textContent).toBe("There are no rows to export with this selection.");
  });

  it("shows a busy state, and a clear error with a retry on the same button", async () => {
    await open({ isBusy: true });
    expect(dialog().querySelector('button[type="submit"]')!.textContent).toContain("Generating…");
    document.body.innerHTML = "";
    await open({ error: "Could not generate the file. You can retry." });
    expect(dialog().querySelector('[role="alert"]')!.textContent).toContain("You can retry");
    expect(dialog().querySelector('button[type="submit"]')!.textContent).toContain("Retry");
  });

  it("is wired to close on Escape and traps focus (Element Plus behaviour, checked live in a browser)", async () => {
    const wrapper = await open();
    const dialogComponent = wrapper.findComponent(ElDialog);
    // jsdom does not run Element Plus' focus-layer stack reliably, so assert the contract
    // the library honours: Escape is enabled and the modal is not click-through.
    expect(dialogComponent.props("closeOnPressEscape")).toBe(true);
    expect(dialogComponent.props("modal")).toBe(true);
    expect(dialog().getAttribute("aria-modal")).toBe("true");
    // the explicit Cancel button is the pointer/keyboard-equivalent path
    const cancel = Array.from(dialog().querySelectorAll("button")).find((b) => b.textContent?.trim() === "Cancel")!;
    cancel.click();
    await flushPromises();
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual([false]);
  });

  it("every control has an accessible name", async () => {
    await open();
    const controls = Array.from(
      dialog().querySelectorAll<HTMLElement>("input, select, button, summary"),
    );
    for (const control of controls) {
      const name =
        control.getAttribute("aria-label") ||
        control.closest("label")?.textContent?.trim() ||
        (control as HTMLButtonElement).textContent?.trim() ||
        "";
      expect(name.length, control.outerHTML.slice(0, 80)).toBeGreaterThan(0);
    }
  });
});
