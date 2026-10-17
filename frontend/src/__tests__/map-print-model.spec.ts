import { beforeEach, describe, expect, it } from "vitest";

import { MESSAGES } from "../i18n/useI18n";
import { MAP_PRINT_EN, MAP_PRINT_ES } from "../i18n/communityMapPrintMessages";
import {
  DEFAULT_MAP_PREFS,
  MAP_PREFS_KEY,
  SECTION_ORDER,
  computeAvailability,
  coverageOf,
  loadMapPrefs,
  normalizeSelection,
  presetSelection,
  saveMapPrefs,
} from "../modules/community-triage/mapPrint/mapPrintModel";
import {
  countsByStatus,
  countsByUrgency,
  exposureText,
  placesTable,
} from "../modules/community-triage/mapPrint/mapPrintData";
import { redDistrict } from "./fixtures/prioFixtures";
import {
  ESCUINTLA_PLACES,
  SONSONATE_PLACES,
  escuintlaSnapshot,
  sonsonateSnapshot,
} from "./fixtures/mapPrintFixtures";

const m = MAP_PRINT_EN;

class MemoryStorage {
  private data = new Map<string, string>();
  getItem(key: string) {
    return this.data.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.data.set(key, value);
  }
}

describe("coverage", () => {
  it("knows El Salvador from Guatemala by where the view is centred", () => {
    expect(coverageOf([13.7222, -89.7236])).toBe("in");
    expect(coverageOf([13.69, -89.19])).toBe("in");
    expect(coverageOf([14.3, -90.78])).toBe("out");
    expect(coverageOf([14.63, -90.51])).toBe("out");
  });
});

describe("section availability", () => {
  const full = () =>
    computeAvailability({ snapshot: sonsonateSnapshot(), selectedDistrict: redDistrict }, m);

  it("offers every section for a Salvadoran zone with a place and a district selected", () => {
    const a = full();
    for (const id of SECTION_ORDER) expect(a[id].available, id).toBe(true);
  });

  it("locks the map and the limits block on", () => {
    const a = full();
    expect(a.map.locked).toBe(true);
    expect(a.limits.locked).toBe(true);
    expect(a.places.locked).toBe(false);
  });

  it("orders sections by what a responder needs first", () => {
    expect(SECTION_ORDER).toEqual([
      "map", "places", "placeDetail", "counts", "districtDetail", "hazards", "weather", "contacts", "notes", "limits",
    ]);
  });

  it("disables a section with no data and says why, instead of printing it empty", () => {
    const a = computeAvailability(
      {
        snapshot: sonsonateSnapshot({ selectedPlace: null, hazards: [], weather: null, places: [] }),
        selectedDistrict: null,
      },
      m,
    );
    expect(a.placeDetail).toMatchObject({ available: false, reason: m.reasons.noSelectedPlace });
    expect(a.hazards).toMatchObject({ available: false, reason: m.reasons.noHazards });
    expect(a.weather).toMatchObject({ available: false, reason: m.reasons.noWeather });
    expect(a.districtDetail).toMatchObject({ available: false, reason: m.reasons.noDistrict });
    expect(a.places).toMatchObject({ available: false, reason: m.reasons.noPlaces });
    expect(a.counts.available).toBe(false);
  });

  it("outside census coverage the population and district sections are disabled with that reason", () => {
    const a = computeAvailability(
      { snapshot: escuintlaSnapshot(), selectedDistrict: redDistrict },
      m,
    );
    expect(a.districtDetail).toMatchObject({ available: false, reason: m.reasons.noCensus });
    expect(a.placePopulation).toMatchObject({ available: false, reason: m.reasons.noCensus });
    // Salvadoran phone numbers must not be printed for a Guatemalan area
    expect(a.contacts).toMatchObject({ available: false, reason: m.reasons.notSalvadoran });
    // what does exist for the zone stays available
    expect(a.places.available).toBe(true);
    expect(a.counts.available).toBe(true);
  });

  it("keeps the place population column when the zone is covered", () => {
    expect(full().placePopulation.available).toBe(true);
  });
});

describe("presets and selection", () => {
  const a = () =>
    computeAvailability({ snapshot: sonsonateSnapshot(), selectedDistrict: redDistrict }, m);

  it("summary is the map, the top places and the contacts, plus the locked limits", () => {
    expect(presetSelection("summary", a())).toEqual(["map", "places", "contacts", "limits"]);
  });

  it("complete is every available section", () => {
    expect(presetSelection("complete", a())).toEqual([...SECTION_ORDER]);
  });

  it("dispatch for one place is the map, that place and the contacts", () => {
    expect(presetSelection("dispatch", a())).toEqual(["map", "placeDetail", "contacts", "limits"]);
  });

  it("a preset skips what has no data instead of selecting a disabled section", () => {
    const avail = computeAvailability(
      { snapshot: escuintlaSnapshot(), selectedDistrict: null },
      m,
    );
    expect(presetSelection("summary", avail)).toEqual(["map", "places", "limits"]);
    expect(presetSelection("dispatch", avail)).toEqual(["map", "limits"]);
    expect(presetSelection("complete", avail)).not.toContain("districtDetail");
    expect(presetSelection("complete", avail)).not.toContain("contacts");
  });

  it("normalising drops unavailable sections and always keeps map and limits", () => {
    const avail = computeAvailability(
      { snapshot: escuintlaSnapshot(), selectedDistrict: null },
      m,
    );
    expect(normalizeSelection(["contacts", "districtDetail", "counts"], avail)).toEqual([
      "map", "counts", "limits",
    ]);
    expect(normalizeSelection([], avail)).toEqual(["map", "limits"]);
  });
});

describe("remembered selection", () => {
  let storage: MemoryStorage;
  beforeEach(() => {
    storage = new MemoryStorage();
  });

  it("round-trips under a namespaced, versioned key", () => {
    const prefs = {
      ...DEFAULT_MAP_PREFS,
      sections: ["map", "counts", "limits"] as const,
      topPlaces: 25,
      legend: false,
    };
    saveMapPrefs({ ...prefs, sections: [...prefs.sections] }, storage);
    expect(MAP_PREFS_KEY).toMatch(/^firstspot\..*\.v1$/);
    expect(loadMapPrefs(storage)).toEqual({ ...prefs, sections: [...prefs.sections] });
  });

  it("never remembers the operator notes", () => {
    saveMapPrefs({ ...DEFAULT_MAP_PREFS, notes: "call Ana 7000-0000" } as never, storage);
    expect(storage.getItem(MAP_PREFS_KEY)).not.toContain("Ana");
  });

  it("falls back to the summary preset for nothing, junk or another version", () => {
    expect(loadMapPrefs(storage)).toEqual(DEFAULT_MAP_PREFS);
    storage.setItem(MAP_PREFS_KEY, "{oops");
    expect(loadMapPrefs(storage)).toEqual(DEFAULT_MAP_PREFS);
    storage.setItem(MAP_PREFS_KEY, JSON.stringify({ version: 7, prefs: {} }));
    expect(loadMapPrefs(storage)).toEqual(DEFAULT_MAP_PREFS);
  });

  it("repairs hand-edited values", () => {
    storage.setItem(
      MAP_PREFS_KEY,
      JSON.stringify({ version: 1, prefs: { sections: ["map", "nope"], topPlaces: 0, placeColumns: ["bogus", "urgency"] } }),
    );
    const loaded = loadMapPrefs(storage);
    expect(loaded.sections).toEqual(["map", "limits"]);
    expect(loaded.topPlaces).toBe(DEFAULT_MAP_PREFS.topPlaces);
    expect(loaded.placeColumns).toEqual(["urgency"]);
  });
});

describe("what the sections print", () => {
  const en = MESSAGES.en;

  it("lists the top N places by priority, with a plain name", () => {
    const table = placesTable(SONSONATE_PLACES, { topN: 2, columns: ["category", "urgency", "population"] }, en, "en");
    expect(table.rows.map((r) => r.name)).toEqual(["Hospital Nacional de Sonsonate", "Unidad de Salud Acajutla"]);
    expect(table.rows[0].cells.urgency).toBe(en.urgency[5]);
    expect(table.rows[0].cells.category).toBe(en.categories.hospital);
  });

  it("never turns a missing or withheld exposure into 0", () => {
    const [covered, , withheld, uncovered] = SONSONATE_PLACES;
    expect(exposureText(covered, m, "en")).toBe("12,480");
    expect(exposureText(withheld, m, "en")).toBe(m.exposure.withheld);
    expect(exposureText(uncovered, m, "en")).toBe(m.exposure.noCoverage);
    for (const text of ESCUINTLA_PLACES.map((p) => exposureText(p, m, "en"))) {
      expect(text).toBe(m.exposure.noCoverage);
      expect(text).not.toBe("0");
    }
  });

  it("counts by urgency and by attention status, only counting what is there", () => {
    expect(countsByUrgency(SONSONATE_PLACES)).toEqual({ 5: 1, 4: 1, 3: 1, 2: 1, 1: 0 });
    expect(countsByStatus(SONSONATE_PLACES)).toEqual({ pending: 2, in_progress: 1, attended: 1 });
  });

  it("has Spanish copy for every reason and section", () => {
    for (const id of SECTION_ORDER) expect(MAP_PRINT_ES.sections[id].name.length).toBeGreaterThan(2);
    for (const reason of Object.values(MAP_PRINT_ES.reasons)) expect(reason.length).toBeGreaterThan(8);
  });
});
