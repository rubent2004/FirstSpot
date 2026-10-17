import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import ElementPlus from "element-plus";

import { apiClient } from "../api/client";
import { COMMUNITY_EN } from "../i18n/communityMessages";
import { setAppLocale } from "../i18n/useI18n";
import CommunityTriagePanel from "../modules/community-triage/CommunityTriagePanel.vue";
import ExportDialog from "../modules/community-triage/ExportDialog.vue";
import { buildReportModel } from "../modules/community-triage/exportModel";
import { DEFAULT_PREFS } from "../modules/community-triage/exportPlan";
import {
  DEFAULT_MAP_PREFS,
  MAP_PREFS_KEY,
  type MapPrintPrefs,
} from "../modules/community-triage/mapPrint/mapPrintModel";
import type { MapSnapshot } from "../modules/community-triage/mapPrint/mapSnapshot";
import { useCommunityTriageStore } from "../stores/useCommunityTriageStore";
import { baselineIndex, eventIndex, redDistrict } from "./fixtures/prioFixtures";
import { escuintlaSnapshot, sonsonateSnapshot } from "./fixtures/mapPrintFixtures";

const NOW = new Date("2026-10-17T12:30:00Z");
const mounted: VueWrapper[] = [];

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

async function openDialog(snapshot: MapSnapshot, mapPrefs: Partial<MapPrintPrefs> = {}, district = null as typeof redDistrict | null) {
  const index = eventIndex();
  const model = buildReportModel(index, COMMUNITY_EN, "en", NOW);
  const wrapper = mount(ExportDialog, {
    props: {
      modelValue: true,
      prefs: { ...DEFAULT_PREFS, lang: "en" as const, format: "map" as const },
      mode: "event" as const,
      rows: model.rows,
      scopeContext: { filteredCodes: null, selectedCode: null },
      selectedName: district?.district_name ?? null,
      eventId: "usp000a9jv",
      zoneName: snapshot.zone.name,
      isBusy: false,
      error: null,
      now: NOW,
      snapshot,
      mapPrefs: { ...DEFAULT_MAP_PREFS, ...mapPrefs },
      selectedDistrict: district,
      index,
    },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  });
  mounted.push(wrapper);
  await flushPromises();
  return wrapper;
}

const dialog = () => document.body.querySelector<HTMLElement>('[role="dialog"]')!;
const box = (id: string) =>
  dialog().querySelector<HTMLInputElement>(`input[name="print-section"][value="${id}"]`)!;
const checked = () =>
  Array.from(dialog().querySelectorAll<HTMLInputElement>('input[name="print-section"]:checked')).map((i) => i.value);
const preset = async (id: string) => {
  dialog().querySelector<HTMLButtonElement>(`button[data-preset="${id}"]`)!.click();
  await flushPromises();
};
const describedBy = (input: HTMLElement) =>
  document.getElementById(input.getAttribute("aria-describedby")!)?.textContent ?? null;

describe("map print content options", () => {
  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
  });
  afterEach(() => {
    mounted.splice(0).forEach((w) => w.unmount());
  });

  it("offers the sections as real, labelled checkboxes in responder order", async () => {
    await openDialog(sonsonateSnapshot(), {}, redDistrict);
    const ids = Array.from(dialog().querySelectorAll<HTMLInputElement>('input[name="print-section"]')).map((i) => i.value);
    expect(ids).toEqual([
      "map", "places", "placeDetail", "counts", "districtDetail", "hazards", "weather", "contacts", "notes", "limits",
    ]);
    for (const input of dialog().querySelectorAll<HTMLInputElement>('input[name="print-section"]')) {
      expect(input.closest("label")!.textContent!.trim().length).toBeGreaterThan(10);
    }
  });

  it("starts from the remembered selection, with the map and the limits locked on", async () => {
    await openDialog(sonsonateSnapshot(), { sections: ["map", "counts", "limits"] });
    expect(checked()).toEqual(["map", "counts", "limits"]);
    for (const id of ["map", "limits"]) {
      expect(box(id).disabled).toBe(true);
      expect(describedBy(box(id))).toBe("Always included");
    }
  });

  it("applies each preset and keeps to what has data", async () => {
    await openDialog(sonsonateSnapshot(), {}, redDistrict);
    await preset("summary");
    expect(checked()).toEqual(["map", "places", "contacts", "limits"]);
    await preset("dispatch");
    expect(checked()).toEqual(["map", "placeDetail", "contacts", "limits"]);
    await preset("complete");
    expect(checked()).toHaveLength(10);
  });

  it("disables a section with no data and says why, via aria-describedby", async () => {
    await openDialog(sonsonateSnapshot({ selectedPlace: null, hazards: [], weather: null }));
    expect(box("placeDetail").disabled).toBe(true);
    expect(describedBy(box("placeDetail"))).toBe("No place selected");
    expect(describedBy(box("hazards"))).toBe("No active hazards near this zone");
    expect(describedBy(box("weather"))).toBe("No weather data");
    expect(describedBy(box("districtDetail"))).toBe("No district selected");
    await preset("complete");
    expect(checked()).not.toContain("placeDetail");
    expect(checked()).not.toContain("hazards");
  });

  it("for Escuintla disables the population, district and contact sections with the reason", async () => {
    await openDialog(escuintlaSnapshot(), { sections: ["map", "places", "limits"] }, redDistrict);
    expect(describedBy(box("districtDetail"))).toBe("No census coverage in this area");
    expect(box("districtDetail").disabled).toBe(true);
    expect(describedBy(box("contacts"))).toBe("The numbers available are for El Salvador");
    const population = dialog().querySelector<HTMLInputElement>(
      'input[name="print-place-column"]:disabled',
    )!;
    expect(population.closest("label")!.textContent).toContain("Est. population");
    expect(describedBy(population)).toBe("No census coverage in this area");
    await preset("complete");
    expect(checked()).not.toContain("districtDetail");
    expect(checked()).not.toContain("contacts");
  });

  it("reveals the top-N and column choices only under a ticked places section", async () => {
    await openDialog(sonsonateSnapshot(), { sections: ["map", "limits"] });
    expect(dialog().querySelector('input[type="number"][aria-label="Show the first"]')).toBeNull();
    box("places").click();
    await flushPromises();
    const top = dialog().querySelector<HTMLInputElement>('input[type="number"][aria-label="Show the first"]')!;
    expect(top.value).toBe("10");
    expect(dialog().querySelectorAll('input[name="print-place-column"]').length).toBe(5);
  });

  it("shows the notes field only when notes are ticked, and keeps what is typed", async () => {
    const wrapper = await openDialog(sonsonateSnapshot(), { sections: ["map", "limits"] });
    expect(dialog().querySelector("textarea")).toBeNull();
    box("notes").click();
    await flushPromises();
    const area = dialog().querySelector<HTMLTextAreaElement>("textarea")!;
    area.value = "Entrada norte cerrada";
    area.dispatchEvent(new Event("input"));
    await flushPromises();
    dialog().querySelector("form")!.dispatchEvent(new Event("submit", { cancelable: true }));
    await flushPromises();
    const [request] = wrapper.emitted("submit")![0] as [{ map: { notes: string; sections: string[] } }];
    expect(request.map.notes).toBe("Entrada norte cerrada");
    expect(request.map.sections).toContain("notes");
  });

  it("announces only the section count, not the preview, and hides the preview from assistive tech", async () => {
    await openDialog(sonsonateSnapshot(), { sections: ["map", "limits"] });
    const status = dialog().querySelector('[data-testid="section-count"]')!;
    expect(status.getAttribute("aria-live")).toBe("polite");
    expect(status.textContent).toBe("2 sections selected");
    box("counts").click();
    await flushPromises();
    expect(status.textContent).toBe("3 sections selected");
    expect(dialog().querySelector('[data-testid="map-preview"]')!.getAttribute("aria-hidden")).toBe("true");
  });

  it("shows a live preview that follows the choices", async () => {
    await openDialog(sonsonateSnapshot(), { sections: ["map", "limits"] });
    const preview = () => dialog().querySelector('[data-testid="map-preview"]')!.textContent!;
    expect(preview()).not.toContain("Counts");
    box("counts").click();
    await flushPromises();
    expect(preview()).toContain("Counts");
  });

  it("paper and orientation live under More options, defaulting the map to landscape", async () => {
    await openDialog(sonsonateSnapshot());
    const more = dialog().querySelector("details.more")!;
    expect((more as HTMLDetailsElement).open).toBe(false);
    expect(more.textContent).toContain("Paper");
    expect(more.textContent).toContain("Orientation");
  });
});

describe("map print through the panel", () => {
  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
    Object.defineProperty(window, "localStorage", { value: new MemoryStorage(), configurable: true });
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getPrioIndex").mockImplementation(async (id) => (id ? eventIndex() : baselineIndex()));
    vi.spyOn(apiClient, "listHazardEvents").mockResolvedValue({
      events: [],
      pager_alert_bands: [],
      declared_gaps: [],
      source: "x",
    });
  });
  afterEach(() => {
    mounted.splice(0).forEach((w) => w.unmount());
    document.body.innerHTML = "";
  });

  async function panel(snapshot: MapSnapshot) {
    const pinia = createPinia();
    setActivePinia(pinia);
    const wrapper = mount(CommunityTriagePanel, {
      props: { zoneName: snapshot.zone.name, zoneDepartment: snapshot.zone.department, getMapSnapshot: () => snapshot },
      global: { plugins: [pinia, ElementPlus] },
      attachTo: document.body,
    });
    mounted.push(wrapper);
    await flushPromises();
    return { wrapper, store: useCommunityTriageStore() };
  }

  it("prints the zone the operator is looking at and remembers the chosen sections", async () => {
    const { wrapper } = await panel(sonsonateSnapshot());
    await wrapper.findAll("button").find((b) => b.text() === "Export")!.trigger("click");
    await flushPromises();
    const mapRadio = Array.from(document.body.querySelectorAll<HTMLInputElement>('input[name="export-format"]')).find(
      (r) => r.closest("label")!.textContent!.includes("Map of the current view"),
    )!;
    mapRadio.click();
    await flushPromises();
    await preset("complete");
    dialog().querySelector("form")!.dispatchEvent(new Event("submit", { cancelable: true }));
    await flushPromises();

    const sheet = document.body.querySelector('[data-testid="print-sheet"]')!;
    expect(sheet.querySelector('[data-testid="map-print-title"]')!.textContent).toBe("Sonsonate — Priority map");
    expect(sheet.querySelector('[data-testid="section-counts"]')).not.toBeNull();
    const stored = JSON.parse(window.localStorage.getItem(MAP_PREFS_KEY)!);
    expect(stored.version).toBe(1);
    expect(stored.prefs.sections).toContain("counts");
    expect(Object.keys(stored.prefs)).not.toContain("notes");
  });

  it("offers no map format while the map is not ready, and says so", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const wrapper = mount(CommunityTriagePanel, {
      props: { zoneName: "Sonsonate", zoneDepartment: "Sonsonate", getMapSnapshot: () => null },
      global: { plugins: [pinia, ElementPlus] },
      attachTo: document.body,
    });
    mounted.push(wrapper);
    await flushPromises();
    await wrapper.findAll("button").find((b) => b.text() === "Export")!.trigger("click");
    await flushPromises();
    const radio = Array.from(document.body.querySelectorAll<HTMLInputElement>('input[name="export-format"]')).find(
      (r) => r.closest("label")!.textContent!.includes("Map of the current view"),
    )!;
    expect(radio.disabled).toBe(true);
    expect(document.getElementById(radio.getAttribute("aria-describedby")!)!.textContent).toBe(
      "The map is not ready yet",
    );
  });
});
