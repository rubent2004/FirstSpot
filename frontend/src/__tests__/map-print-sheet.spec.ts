import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import ElementPlus from "element-plus";
import L from "leaflet";

import { COMMUNITY_EN, COMMUNITY_ES } from "../i18n/communityMessages";
import { setAppLocale } from "../i18n/useI18n";
import { buildReportModel } from "../modules/community-triage/exportModel";
import {
  DEFAULT_MAP_PREFS,
  printBasemap,
  type MapPrintPrefs,
  type SectionId,
} from "../modules/community-triage/mapPrint/mapPrintModel";
import type { MapSnapshot } from "../modules/community-triage/mapPrint/mapSnapshot";
import PrintSheet from "../modules/community-triage/PrintSheet.vue";
import { baselineIndex, eventIndex, redDistrict } from "./fixtures/prioFixtures";
import { SONSONATE_PLACES, escuintlaSnapshot, sonsonateSnapshot } from "./fixtures/mapPrintFixtures";

const NOW = new Date("2026-10-17T12:30:00Z");
const mounted: VueWrapper[] = [];

function sheet(
  snapshot: MapSnapshot,
  sections: SectionId[],
  extra: {
    prefs?: Partial<MapPrintPrefs>;
    notes?: string;
    district?: typeof redDistrict | null;
    lang?: "en" | "es";
    event?: boolean;
  } = {},
) {
  const lang = extra.lang ?? "en";
  const t = lang === "en" ? COMMUNITY_EN : COMMUNITY_ES;
  const model = buildReportModel(extra.event ? eventIndex() : baselineIndex(), t, lang, NOW);
  const wrapper = mount(PrintSheet, {
    props: {
      model,
      variant: "map",
      lang,
      paper: "a4",
      orientation: "landscape",
      fileName: "firstspot_prio_baseline_2026-10-17_map.pdf",
      snapshot,
      mapPrefs: { ...DEFAULT_MAP_PREFS, ...extra.prefs },
      mapSections: sections,
      notes: extra.notes ?? "",
      selectedDistrict: extra.district ?? null,
    },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  });
  mounted.push(wrapper);
  return wrapper;
}

const body = () => document.body.querySelector<HTMLElement>('[data-testid="print-sheet"]')!;
const text = () => body().textContent ?? "";

describe("printed map of the current view", () => {
  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
  });
  afterEach(() => {
    mounted.splice(0).forEach((w) => w.unmount());
    vi.restoreAllMocks();
  });

  it("is titled with the work zone, not a fixed national sheet", async () => {
    sheet(sonsonateSnapshot(), ["map", "places", "limits"]);
    await flushPromises();
    expect(body().querySelector('[data-testid="map-print-title"]')!.textContent).toBe(
      "Sonsonate — Priority map",
    );
    expect(text()).not.toContain("Escuintla");
  });

  it("is titled with the open district when a Salvadoran district is selected", async () => {
    sheet(sonsonateSnapshot(), ["map", "limits"], { district: redDistrict });
    await flushPromises();
    expect(body().querySelector('[data-testid="map-print-title"]')!.textContent).toBe("San Marcos Rojo");
  });

  it("follows another zone: Escuintla prints Escuintla, with its places", async () => {
    sheet(escuintlaSnapshot(), ["map", "places", "counts", "limits"]);
    await flushPromises();
    expect(body().querySelector('[data-testid="map-print-title"]')!.textContent).toBe(
      "Escuintla — Priority map",
    );
    expect(text()).toContain("Hospital de Escuintla");
    expect(text()).not.toContain("Hospital Nacional de Sonsonate");
  });

  it("states that Escuintla is outside census coverage and prints no ranking and no population", async () => {
    sheet(escuintlaSnapshot(), ["map", "places", "contacts", "districtDetail", "limits"], {
      prefs: { placeColumns: ["category", "population"] },
      district: redDistrict,
    });
    await flushPromises();
    const out = body().querySelector('[data-testid="coverage-out"]')!;
    expect(out.textContent).toContain("outside the coverage of the El Salvador census and district index");
    expect(out.textContent).toContain("no estimated population and no district ranking");
    // nothing national leaks in, even if it was requested and a district is open
    expect(text()).not.toContain("San Marcos Rojo");
    expect(body().querySelector('[data-testid="section-district"]')).toBeNull();
    // Salvadoran emergency numbers are not printed for a Guatemalan area
    expect(body().querySelector('[data-testid="section-contacts"]')).toBeNull();
    expect(text()).not.toContain("2281-0888");
    // no population column at all outside the census: not a zero, not a made-up figure
    const places = body().querySelector('[data-testid="section-places"]')!.textContent!;
    expect(places).not.toContain("Est. population");
    expect(places).not.toMatch(/\b0\b/);
  });

  it("prints no population even if stale data carries estimates while the view is outside El Salvador", async () => {
    const stale = escuintlaSnapshot({ places: SONSONATE_PLACES, selectedPlace: SONSONATE_PLACES[1] });
    sheet(stale, ["map", "places", "placeDetail", "limits"], { prefs: { placeColumns: ["category", "population"] } });
    await flushPromises();
    const places = body().querySelector('[data-testid="section-places"]')!.textContent!;
    expect(places).not.toContain("12,480");
    expect(places).not.toContain("Est. population");
    const detail = body().querySelector('[data-testid="section-place-detail"]')!.textContent!;
    expect(detail).not.toContain("12,480");
    expect(detail).not.toContain("Exposed population");
  });

  it("inside El Salvador says why the district ranking is not on the map", async () => {
    sheet(sonsonateSnapshot(), ["map", "limits"]);
    await flushPromises();
    expect(body().querySelector('[data-testid="coverage-out"]')).toBeNull();
    expect(body().querySelector('[data-testid="section-limits"]')!.textContent).toContain(
      "does not say which districts are inside the view",
    );
  });

  it("always prints the limits and the attribution, even if no section was chosen", async () => {
    sheet(sonsonateSnapshot(), []);
    await flushPromises();
    const limits = body().querySelector('[data-testid="section-limits"]')!.textContent!;
    expect(limits).toContain("never reports victims or casualties");
    expect(limits).toContain("construction quality");
    expect(limits).toContain("BCR/ONEC, CPV 2024");
  });

  it("carries mode, generation time and, in event mode, the event and ShakeMap time", async () => {
    sheet(sonsonateSnapshot(), ["map", "limits"], { event: true });
    await flushPromises();
    expect(text()).toContain("Event");
    expect(text()).toContain("Offshore San Salvador");
    expect(text()).toContain("2023-06-30 08:15 UTC");
    expect(text()).toContain("2026-10-17 12:30 UTC");
  });

  it("gives the print map the live centre and zoom", async () => {
    const setView = vi.spyOn(L.Map.prototype, "setView");
    sheet(sonsonateSnapshot(), ["map", "limits"]);
    await flushPromises();
    expect(setView).toHaveBeenCalledWith([13.7222, -89.7236], 13);
  });

  it("prints a fractional live zoom rounded, not as a raw float", async () => {
    const snapshot = sonsonateSnapshot();
    snapshot.view.zoom = 13.269118064090618;
    sheet(snapshot, ["map", "limits"]);
    await flushPromises();
    expect(text()).toContain("zoom 13.3");
    expect(text()).not.toContain("13.269118064090618");
  });

  it("uses a light Esri basemap on paper, never CARTO or a keyed provider", () => {
    expect(printBasemap("grayDark")).toBe("grayLight");
    expect(printBasemap("grayLight")).toBe("grayLight");
    expect(printBasemap("osmStreet")).toBe("osmStreet");
  });

  it("prints operator notes verbatim and escaped", async () => {
    const notes = "<b>Call</b> Ana & Co\nsecond line";
    sheet(sonsonateSnapshot(), ["map", "notes", "limits"], { notes });
    await flushPromises();
    const section = body().querySelector('[data-testid="section-notes"]')!;
    expect(section.querySelector(".notes")!.textContent).toBe(notes);
    expect(section.innerHTML).toContain("&lt;b&gt;Call&lt;/b&gt;");
    expect(section.querySelector("b")).toBeNull();
  });

  it("skips empty notes instead of printing an empty section", async () => {
    sheet(sonsonateSnapshot(), ["map", "notes", "limits"], { notes: "   " });
    await flushPromises();
    expect(body().querySelector('[data-testid="section-notes"]')).toBeNull();
  });

  it("never renders a section that has no data, even if it was selected", async () => {
    sheet(
      sonsonateSnapshot({ hazards: [], weather: null, selectedPlace: null, places: [] }),
      ["map", "places", "counts", "hazards", "weather", "placeDetail", "limits"],
    );
    await flushPromises();
    for (const id of ["places", "counts", "hazards", "weather", "place-detail"]) {
      expect(body().querySelector(`[data-testid="section-${id}"]`), id).toBeNull();
    }
  });

  it("lists in the legend only what is actually painted", async () => {
    sheet(
      sonsonateSnapshot({
        layers: { heat: false, markers: true, hazards: false },
        hazards: [],
        selectedPlace: null,
      }),
      ["map", "limits"],
    );
    await flushPromises();
    const legend = body().querySelector('[data-testid="map-legend"]')!.textContent!;
    expect(legend).toContain("Places, by vulnerability group");
    expect(legend).not.toContain("Heat");
    expect(legend).not.toContain("Active hazard");
    expect(legend).not.toContain("Search radius");
    expect(legend).not.toContain("Selected place");
  });

  it("turns the legend, scale and north arrow off independently", async () => {
    sheet(sonsonateSnapshot(), ["map", "limits"], { prefs: { legend: false, north: false } });
    await flushPromises();
    expect(body().querySelector('[data-testid="map-legend"]')).toBeNull();
    expect(body().querySelector(".north")).toBeNull();
  });

  it("shows the selected place with its facts, log and, outside no-coverage, its population", async () => {
    sheet(sonsonateSnapshot(), ["map", "placeDetail", "limits"]);
    await flushPromises();
    const detail = body().querySelector('[data-testid="section-place-detail"]')!.textContent!;
    expect(detail).toContain("Unidad de Salud Acajutla");
    expect(detail).toContain("MINSAL");
    expect(detail).toContain("Takes emergencies");
    expect(detail).toContain("Unit on scene");
    expect(detail).toContain("12,480");
  });

  it("sets the page size and the document title for the PDF", async () => {
    sheet(sonsonateSnapshot(), ["map", "limits"]);
    await flushPromises();
    expect(document.head.querySelector("style[data-print-page]")!.textContent).toContain("A4 landscape");
    expect(document.title).toBe("firstspot_prio_baseline_2026-10-17_map");
  });
});
