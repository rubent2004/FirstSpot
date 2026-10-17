import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import ElementPlus from "element-plus";

import { apiClient } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import CommunityTriagePanel from "../modules/community-triage/CommunityTriagePanel.vue";
import { PREFS_KEY } from "../modules/community-triage/exportPlan";
import { useCommunityTriageStore } from "../stores/useCommunityTriageStore";
import { EVENT_ID, baselineIndex, eventIndex } from "./fixtures/prioFixtures";

const downloadRankingXlsx = vi.hoisted(() => vi.fn(async (..._args: unknown[]) => undefined));
const saveBlob = vi.hoisted(() => vi.fn());
vi.mock("../modules/community-triage/exportXlsx", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../modules/community-triage/exportXlsx")>()),
  downloadRankingXlsx,
}));
vi.mock("../modules/community-triage/exportFiles", () => ({ saveBlob }));

/** The test runtime's localStorage is not dependable; a plain in-memory one is. */
class MemoryStorage {
  private data = new Map<string, string>();
  getItem(key: string) {
    return this.data.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.data.set(key, value);
  }
  removeItem(key: string) {
    this.data.delete(key);
  }
  clear() {
    this.data.clear();
  }
}

const mounted: VueWrapper[] = [];

async function mountPanel(eventMode = true) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const wrapper = mount(CommunityTriagePanel, {
    props: { zoneName: "Sonsonate", zoneDepartment: null },
    global: { plugins: [pinia, ElementPlus] },
    attachTo: document.body,
  });
  mounted.push(wrapper);
  await flushPromises();
  if (eventMode) {
    await useCommunityTriageStore().selectEvent(EVENT_ID);
    await flushPromises();
  }
  return wrapper;
}

const openButton = (w: ReturnType<typeof mount>) =>
  w.findAll("button").find((b) => b.text() === "Export")!;
const dialog = () => document.body.querySelector<HTMLElement>('[role="dialog"]');
const pickFormat = async (label: string) => {
  const radio = Array.from(document.body.querySelectorAll<HTMLInputElement>('input[name="export-format"]')).find((r) =>
    r.closest("label")?.textContent?.includes(label),
  )!;
  radio.click();
  await flushPromises();
};
const submit = async () => {
  dialog()!.querySelector("form")!.dispatchEvent(new Event("submit", { cancelable: true }));
  await flushPromises();
};
const messages = () => Array.from(document.body.querySelectorAll(".el-message")).map((m) => m.textContent ?? "");

describe("export flow", () => {
  afterEach(() => {
    mounted.splice(0).forEach((w) => w.unmount());
    document.body.innerHTML = "";
  });

  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
    Object.defineProperty(window, "localStorage", { value: new MemoryStorage(), configurable: true });
    downloadRankingXlsx.mockReset();
    downloadRankingXlsx.mockResolvedValue(undefined);
    saveBlob.mockReset();
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getPrioIndex").mockImplementation(async (eventId) =>
      eventId ? eventIndex() : baselineIndex(),
    );
    vi.spyOn(apiClient, "listHazardEvents").mockResolvedValue({
      events: [],
      pager_alert_bands: [],
      declared_gaps: [],
      source: "x",
    });
  });

  it("is one Export button in the list header, and nothing else until it is pressed", async () => {
    const wrapper = await mountPanel();
    expect(openButton(wrapper).attributes("aria-haspopup")).toBe("dialog");
    expect(dialog()).toBeNull();
    expect(wrapper.text()).not.toContain("Excel (.xlsx)");
    expect(wrapper.text()).not.toContain("Repeat last");
  });

  it("exports an Excel file, confirms with its name and closes the dialog", async () => {
    const wrapper = await mountPanel();
    await openButton(wrapper).trigger("click");
    await flushPromises();
    await submit();
    expect(downloadRankingXlsx).toHaveBeenCalledTimes(1);
    const options = downloadRankingXlsx.mock.calls[0][3] as { fileName: string; columns: string[] };
    expect(options.fileName).toMatch(/^firstspot_prio_event_usp000a9jv_\d{4}-\d{2}-\d{2}\.xlsx$/);
    expect(messages().join(" ")).toContain(`File ready: ${options.fileName}`);
    expect(dialog()).toBeNull();
  });

  it("remembers the choices under a versioned key, and offers a one-click repeat", async () => {
    const wrapper = await mountPanel();
    await openButton(wrapper).trigger("click");
    await flushPromises();
    await pickFormat("CSV");
    await submit();
    expect(saveBlob).toHaveBeenCalledTimes(1);
    const stored = JSON.parse(window.localStorage.getItem(PREFS_KEY)!);
    expect(stored.version).toBe(1);
    expect(stored.prefs.format).toBe("csv");

    const repeat = wrapper.findAll("button").find((b) => b.text() === "Repeat last")!;
    expect(repeat.attributes("title")).toMatch(/^Same settings: firstspot_prio_event_usp000a9jv_.*\.csv$/);
    await repeat.trigger("click");
    await flushPromises();
    expect(saveBlob).toHaveBeenCalledTimes(2);
    expect(dialog()).toBeNull();
  });

  it("reopens with the remembered format and columns", async () => {
    window.localStorage.setItem(
      PREFS_KEY,
      JSON.stringify({ version: 1, prefs: { format: "csv", columns: ["rank", "district"] } }),
    );
    const wrapper = await mountPanel();
    await openButton(wrapper).trigger("click");
    await flushPromises();
    const checked = document.body.querySelector<HTMLInputElement>('input[name="export-format"]:checked')!;
    expect(checked.closest("label")!.textContent).toContain("CSV");
    expect(dialog()!.querySelector('[data-testid="export-filename"]')!.textContent).toMatch(/\.csv$/);
  });

  it("writes a CSV with the BOM and the limits, from loaded data only", async () => {
    const wrapper = await mountPanel();
    const calls = vi.mocked(apiClient.getPrioIndex).mock.calls.length;
    await openButton(wrapper).trigger("click");
    await flushPromises();
    await pickFormat("CSV");
    await submit();
    const blob = saveBlob.mock.calls[0][0] as Blob;
    const text = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(blob, "utf-8");
    });
    expect(text).toContain("construction quality");
    expect(text).toContain("BCR/ONEC, CPV 2024");
    expect(vi.mocked(apiClient.getPrioIndex).mock.calls.length).toBe(calls);
  });

  it("exports only what is filtered when a filter is active, and says so in the file", async () => {
    const wrapper = await mountPanel();
    await wrapper.get('input[aria-label="Search district"]').setValue("lejos");
    await flushPromises();
    await openButton(wrapper).trigger("click");
    await flushPromises();
    const scope = dialog()!.querySelector<HTMLInputElement>('input[name="export-scope"]:checked')!;
    expect(scope.value).toBe("filtered");
    await submit();
    const [model] = downloadRankingXlsx.mock.calls[0] as [{ rows: unknown[]; scopeNote: string }];
    expect(model.rows).toHaveLength(1);
    expect(model.scopeNote).toBe("Filtered view: 1 of 3 districts");
    const options = downloadRankingXlsx.mock.calls[0][3] as { fileName: string };
    expect(options.fileName).toMatch(/_filtered\.xlsx$/);
  });

  it("keeps the dialog open with a clear error and a Retry that works", async () => {
    downloadRankingXlsx.mockRejectedValueOnce(new Error("disk full"));
    const wrapper = await mountPanel();
    await openButton(wrapper).trigger("click");
    await flushPromises();
    await submit();
    expect(dialog()).not.toBeNull();
    expect(dialog()!.querySelector('[role="alert"]')!.textContent).toContain("Could not generate the file");
    expect(dialog()!.textContent).not.toContain("disk full");
    const primary = dialog()!.querySelector<HTMLButtonElement>('button[type="submit"]')!;
    expect(primary.textContent).toContain("Retry");
    await submit();
    expect(downloadRankingXlsx).toHaveBeenCalledTimes(2);
    expect(dialog()).toBeNull();
    expect(messages().join(" ")).toContain("File ready");
  });

  it("starts the document language as the console's language, in Spanish too", async () => {
    setAppLocale("es");
    const wrapper = await mountPanel(false);
    await wrapper.findAll("button").find((b) => b.text() === "Exportar")!.trigger("click");
    await flushPromises();
    const name = dialog()!.querySelector('[data-testid="export-filename"]')!.textContent;
    expect(name).toMatch(/^firstspot_prio_linea-base_/);
    setAppLocale("en");
  });
});
