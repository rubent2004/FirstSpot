import { beforeEach, describe, expect, it } from "vitest";

import { COMMUNITY_EN, COMMUNITY_ES } from "../i18n/communityMessages";
import { buildReportModel } from "../modules/community-triage/exportModel";
import {
  DEFAULT_PREFS,
  PREFS_KEY,
  buildFileName,
  columnsFor,
  loadPrefs,
  resolveColumns,
  resolveScope,
  savePrefs,
  scopeCounts,
  selectRows,
} from "../modules/community-triage/exportPlan";
import { buildExportTable } from "../modules/community-triage/exportTable";
import {
  EVENT_ID,
  REDACTED_LEAK,
  baselineIndex,
  eventIndex,
  redDistrict,
  withheldDistrict,
  zeroDistrict,
} from "./fixtures/prioFixtures";

const NOW = new Date("2026-10-17T12:30:00Z");
const eventModel = () => buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW);
const baselineModel = () => buildReportModel(baselineIndex(), COMMUNITY_EN, "en", NOW);

class MemoryStorage {
  private data = new Map<string, string>();
  getItem(key: string) {
    return this.data.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.data.set(key, value);
  }
}

describe("scope -> rows", () => {
  const ctx = {
    filteredCodes: new Set([redDistrict.district_code, zeroDistrict.district_code]),
    selectedCode: redDistrict.district_code,
  };

  it("counts every scope, live, for the current choice", () => {
    expect(scopeCounts(eventModel().rows, ctx, null)).toEqual({ all: 3, filtered: 2, selected: 1 });
  });

  it("applies the top-N limit after the scope and never exceeds what the scope holds", () => {
    expect(scopeCounts(eventModel().rows, ctx, 1)).toEqual({ all: 1, filtered: 1, selected: 1 });
    expect(scopeCounts(eventModel().rows, ctx, 50)).toEqual({ all: 3, filtered: 2, selected: 1 });
  });

  it("selects all rows in rank order with the withheld district last", () => {
    const names = selectRows(eventModel().rows, "all", ctx, null).map((r) => r.name);
    expect(names).toEqual(["San Marcos Rojo", "Lejos Verde", "Reservado Sur"]);
  });

  it("selects only the filtered view, or only the open district", () => {
    expect(selectRows(eventModel().rows, "filtered", ctx, null).map((r) => r.name)).toEqual([
      "San Marcos Rojo",
      "Lejos Verde",
    ]);
    expect(selectRows(eventModel().rows, "selected", ctx, null).map((r) => r.name)).toEqual([
      "San Marcos Rojo",
    ]);
    expect(selectRows(eventModel().rows, "selected", { ...ctx, selectedCode: null }, null)).toEqual([]);
  });

  it("falls back to a scope that exists instead of exporting nothing silently", () => {
    expect(resolveScope("selected", { filteredCodes: null, selectedCode: null })).toBe("all");
    expect(resolveScope("filtered", { filteredCodes: null, selectedCode: null })).toBe("all");
    expect(resolveScope("selected", { filteredCodes: new Set(["x"]), selectedCode: null })).toBe("filtered");
    expect(resolveScope("all", ctx)).toBe("all");
  });
});

describe("column selection", () => {
  it("offers exposure, shaking and Sphere only when an event exists", () => {
    expect(columnsFor("baseline")).not.toContain("exposed");
    expect(columnsFor("baseline")).not.toContain("sphere");
    expect(columnsFor("event")).toEqual(expect.arrayContaining(["exposed", "shaking", "sphere"]));
  });

  it("always keeps the district name and drops columns that do not apply", () => {
    expect(resolveColumns(["rank", "exposed"], "baseline")).toEqual(["rank", "district"]);
    expect(resolveColumns([], "event")).toEqual(["district"]);
  });

  it("keeps the canonical column order whatever order was chosen", () => {
    expect(resolveColumns(["prio", "rank", "district"], "event")).toEqual(["rank", "district", "prio"]);
  });

  it("builds a table with only the chosen columns", () => {
    const table = buildExportTable(eventModel(), ["district", "prio"], COMMUNITY_EN, "en");
    expect(table.header).toEqual(["District", "Priority (0-10)"]);
    expect(table.rows[0]).toEqual(["San Marcos Rojo", 8.4]);
  });

  it("adds the department and the three dimensions when asked", () => {
    const table = buildExportTable(
      eventModel(),
      ["district", "department", "dimensions"],
      COMMUNITY_EN,
      "en",
    );
    expect(table.header).toEqual([
      "District",
      "Department",
      "Hazard and exposure",
      "Vulnerability",
      "Lack of coping capacity",
    ]);
    expect(table.rows[0]).toEqual(["San Marcos Rojo", "San Salvador", 9.1, 8.2, 7.9]);
  });
});

describe("integrity of the table", () => {
  it("never carries a value the API suppressed", () => {
    const table = buildExportTable(
      eventModel(),
      resolveColumns(columnsFor("event"), "event"),
      COMMUNITY_EN,
      "en",
    );
    const cells = table.rows.flat();
    expect(cells).not.toContain(REDACTED_LEAK);
    expect(cells).not.toContain(7.7);
    const withheld = table.rows.find((r) => r.includes("Reservado Sur"))!;
    expect(withheld.filter((c) => typeof c === "number")).toEqual([]);
  });

  it("writes a missing exposure as an explicit 'no estimate', never 0, and keeps a real 0", () => {
    const index = eventIndex();
    index.districts = [
      { ...redDistrict, estimated_exposed_population: null },
      { ...zeroDistrict, estimated_exposed_population: 0 },
      withheldDistrict,
    ];
    const model = buildReportModel(index, COMMUNITY_EN, "en", NOW);
    const table = buildExportTable(model, ["district", "exposed"], COMMUNITY_EN, "en");
    expect(table.rows.find((r) => r[0] === "San Marcos Rojo")![1]).toBe("no estimate");
    expect(table.rows.find((r) => r[0] === "Lejos Verde")![1]).toBe(0);
    expect(table.rows.find((r) => r[0] === "Reservado Sur")![1]).toBeNull();
  });
});

describe("file name", () => {
  const base = {
    mode: "baseline" as const,
    eventId: null,
    lang: "es" as const,
    format: "xlsx" as const,
    scope: "all" as const,
    topN: null,
    districtName: null,
    now: NOW,
  };

  it("carries tool, mode and date, lowercase with no spaces", () => {
    expect(buildFileName(base)).toBe("firstspot_prio_linea-base_2026-10-17.xlsx");
    expect(buildFileName({ ...base, lang: "en" })).toBe("firstspot_prio_baseline_2026-10-17.xlsx");
  });

  it("carries the event for event mode", () => {
    expect(buildFileName({ ...base, mode: "event", eventId: EVENT_ID, format: "csv" })).toBe(
      "firstspot_prio_evento_usp000a9jv_2026-10-17.csv",
    );
    expect(buildFileName({ ...base, mode: "event", eventId: "US7000ABC", lang: "en", format: "csv" })).toBe(
      "firstspot_prio_event_us7000abc_2026-10-17.csv",
    );
  });

  it("says what part of the ranking it holds, so two exports never collide", () => {
    expect(buildFileName({ ...base, scope: "filtered" })).toBe(
      "firstspot_prio_linea-base_2026-10-17_filtrado.xlsx",
    );
    expect(buildFileName({ ...base, scope: "selected", districtName: "San Pedro Nonualco" })).toBe(
      "firstspot_prio_linea-base_2026-10-17_san-pedro-nonualco.xlsx",
    );
    expect(buildFileName({ ...base, topN: 20 })).toBe("firstspot_prio_linea-base_2026-10-17_top-20.xlsx");
  });

  it("uses a pdf name for the print outputs and folds accents away", () => {
    expect(buildFileName({ ...base, format: "report" })).toMatch(/\.pdf$/);
    expect(buildFileName({ ...base, format: "map" })).toMatch(/_mapa\.pdf$|_map\.pdf$/);
    expect(buildFileName({ ...base, scope: "selected", districtName: "Cuscatancingo Ñ" })).toMatch(
      /_cuscatancingo-n\.xlsx$/,
    );
    expect(buildFileName({ ...base, scope: "selected", districtName: "Ñ A" })).not.toMatch(/[\sÑñ]/);
  });
});

describe("remembered choices", () => {
  let storage: MemoryStorage;
  beforeEach(() => {
    storage = new MemoryStorage();
  });

  it("round-trips through a namespaced, versioned key", () => {
    const prefs = {
      ...DEFAULT_PREFS,
      format: "csv" as const,
      columns: ["rank" as const, "district" as const],
      topN: 25,
      paper: "letter" as const,
      orientation: "landscape" as const,
      includeContext: false,
    };
    savePrefs(prefs, storage);
    expect(PREFS_KEY).toMatch(/^firstspot\..*\.v1$/);
    expect(storage.getItem(PREFS_KEY)).not.toBeNull();
    expect(loadPrefs(storage)).toEqual(prefs);
  });

  it("does not remember the document language: it follows the console's language", () => {
    savePrefs({ ...DEFAULT_PREFS, lang: "en" }, storage);
    expect(storage.getItem(PREFS_KEY)).not.toContain('"lang"');
    expect(loadPrefs(storage, "es").lang).toBe("es");
    expect(loadPrefs(storage, "en").lang).toBe("en");
  });

  it("falls back to defaults for nothing saved, corrupt JSON or another version", () => {
    expect(loadPrefs(storage)).toEqual(DEFAULT_PREFS);
    storage.setItem(PREFS_KEY, "{not json");
    expect(loadPrefs(storage)).toEqual(DEFAULT_PREFS);
    storage.setItem(PREFS_KEY, JSON.stringify({ version: 99, prefs: { format: "csv" } }));
    expect(loadPrefs(storage)).toEqual(DEFAULT_PREFS);
  });

  it("repairs a hand-edited value instead of trusting it", () => {
    storage.setItem(
      PREFS_KEY,
      JSON.stringify({
        version: 1,
        prefs: { format: "docx", columns: ["rank", "bogus"], topN: -3, paper: "a3" },
      }),
    );
    const loaded = loadPrefs(storage);
    expect(loaded.format).toBe(DEFAULT_PREFS.format);
    expect(loaded.columns).toEqual(["rank"]);
    expect(loaded.topN).toBeNull();
    expect(loaded.paper).toBe(DEFAULT_PREFS.paper);
  });

  it("survives a storage that throws", () => {
    const hostile = {
      getItem() {
        throw new Error("denied");
      },
      setItem() {
        throw new Error("denied");
      },
    };
    expect(loadPrefs(hostile)).toEqual(DEFAULT_PREFS);
    expect(() => savePrefs(DEFAULT_PREFS, hostile)).not.toThrow();
  });
});

describe("model additions", () => {
  it("rows know their department and the event keeps its id for the file name only", () => {
    const model = baselineModel();
    expect(model.rows[0].department).toBe("San Salvador");
    expect(eventModel().event?.id).toBe(EVENT_ID);
    void COMMUNITY_ES;
  });
});
