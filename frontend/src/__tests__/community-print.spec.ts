import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import { apiClient } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import CommunityTriagePanel from "../modules/community-triage/CommunityTriagePanel.vue";
import { useCommunityTriageStore } from "../stores/useCommunityTriageStore";
import { BASEMAP_PRESETS } from "../modules/map-viewer/composables/useLeafletMap";
import {
  EVENT_ID,
  REDACTED_LEAK,
  baselineIndex,
  eventIndex,
} from "./fixtures/prioFixtures";

const downloadRankingXlsx = vi.hoisted(() => vi.fn(async () => undefined));
vi.mock("../modules/community-triage/exportXlsx", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../modules/community-triage/exportXlsx")>()),
  downloadRankingXlsx,
}));

async function mountPanel(eventMode: boolean) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const wrapper = mount(CommunityTriagePanel, {
    global: { plugins: [pinia, ElementPlus] },
    attachTo: document.body,
  });
  await flushPromises();
  if (eventMode) {
    await useCommunityTriageStore().selectEvent(EVENT_ID);
    await flushPromises();
  }
  return wrapper;
}

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const found = wrapper.findAll("button").find((b) => b.text().includes(text));
  if (!found) throw new Error(`no button "${text}"`);
  return found;
}

describe("exports from the triage panel", () => {
  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
    delete document.body.dataset.printSheet;
    downloadRankingXlsx.mockClear();
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

  it("opens a printable report that carries mode, event, ShakeMap time, limits and attribution", async () => {
    const wrapper = await mountPanel(true);
    await buttonByText(wrapper, "Printable report").trigger("click");
    await flushPromises();

    const sheet = document.body.querySelector('[data-testid="print-sheet"]');
    expect(sheet).not.toBeNull();
    expect(document.body.dataset.printSheet).toBe("report");
    const text = sheet!.textContent ?? "";
    expect(text).toContain("Event");
    expect(text).toContain("Offshore San Salvador");
    expect(text).toContain("2023-06-30 08:15 UTC");
    expect(text).toContain("orange 100–999");
    expect(text).toContain("never reports victims or casualties");
    expect(text).toContain("construction quality");
    expect(text).toContain("BCR/ONEC, CPV 2024");
    expect(text).toMatch(/Generated\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC/);
  });

  it("prints nothing the API withheld and no internal identifiers", async () => {
    const wrapper = await mountPanel(true);
    await buttonByText(wrapper, "Printable report").trigger("click");
    await flushPromises();
    const html = document.body.querySelector('[data-testid="print-sheet"]')!.innerHTML;
    expect(html).not.toContain(String(REDACTED_LEAK));
    expect(html).not.toContain("777,777");
    for (const forbidden of ["060101", "090909", EVENT_ID]) {
      expect(html).not.toContain(forbidden);
    }
  });

  it("states baseline mode on a baseline report", async () => {
    const wrapper = await mountPanel(false);
    await buttonByText(wrapper, "Printable report").trigger("click");
    await flushPromises();
    expect(document.body.querySelector('[data-testid="sheet-mode"]')!.textContent).toBe(
      "Baseline",
    );
  });

  it("opens the map sheet with legend, mode and a notice that no polygons exist", async () => {
    const wrapper = await mountPanel(true);
    await buttonByText(wrapper, "Printable map").trigger("click");
    await flushPromises();
    expect(document.body.dataset.printSheet).toBe("map");
    const sheet = document.body.querySelector('[data-testid="print-sheet"]')!;
    expect(sheet.querySelector('[data-testid="print-map"]')).not.toBeNull();
    const text = sheet.textContent ?? "";
    for (const name of ["Red", "Orange", "Yellow", "Green"]) expect(text).toContain(name);
    expect(text).toContain("does not provide district polygons");
    expect(text).toContain("Epicentre");
  });

  it("closing the sheet removes it and the print flag", async () => {
    const wrapper = await mountPanel(true);
    await buttonByText(wrapper, "Printable report").trigger("click");
    await flushPromises();
    const close = [...document.body.querySelectorAll("button")].find(
      (b) => b.textContent?.trim() === "Close",
    )!;
    close.click();
    await flushPromises();
    expect(document.body.querySelector('[data-testid="print-sheet"]')).toBeNull();
    expect(document.body.dataset.printSheet).toBeUndefined();
  });

  it("downloads the workbook from loaded data without calling the API again", async () => {
    const wrapper = await mountPanel(true);
    const calls = vi.mocked(apiClient.getPrioIndex).mock.calls.length;
    await buttonByText(wrapper, "Excel").trigger("click");
    await flushPromises();
    expect(downloadRankingXlsx).toHaveBeenCalledTimes(1);
    expect(vi.mocked(apiClient.getPrioIndex).mock.calls.length).toBe(calls);
  });
});

describe("print basemap", () => {
  it("never uses a key-gated or CARTO provider for the printed map", () => {
    const preset = BASEMAP_PRESETS.grayLight;
    expect(preset.url).toContain("services.arcgisonline.com");
    expect(preset.url).not.toMatch(/carto/i);
  });
});
