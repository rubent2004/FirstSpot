import { describe, expect, it } from "vitest";

import { COMMUNITY_EN, COMMUNITY_ES, DATA_ATTRIBUTION } from "../i18n/communityMessages";
import { CSV_BOM, buildCsv, csvCell } from "../modules/community-triage/exportCsv";
import { buildReportModel } from "../modules/community-triage/exportModel";
import { columnsFor, resolveColumns } from "../modules/community-triage/exportPlan";
import {
  REDACTED_LEAK,
  baselineIndex,
  eventIndex,
  redDistrict,
  zeroDistrict,
  withheldDistrict,
} from "./fixtures/prioFixtures";

const NOW = new Date("2026-10-17T12:30:00Z");
const allColumns = (mode: "baseline" | "event") => resolveColumns(columnsFor(mode), mode);

describe("csvCell", () => {
  it("leaves plain values alone and writes null as an empty field", () => {
    expect(csvCell("Sonsonate")).toBe("Sonsonate");
    expect(csvCell(8.4)).toBe("8.4");
    expect(csvCell(0)).toBe("0");
    expect(csvCell(null)).toBe("");
  });

  it("quotes commas, quotes and line breaks, doubling inner quotes", () => {
    expect(csvCell("San Pedro, Nonualco")).toBe('"San Pedro, Nonualco"');
    expect(csvCell('El "Rosario"')).toBe('"El ""Rosario"""');
    expect(csvCell("a\nb")).toBe('"a\nb"');
    expect(csvCell("a\r\nb")).toBe('"a\r\nb"');
  });

  it("keeps accents and ñ intact", () => {
    expect(csvCell("Cuscatancingo Ñandú Ángel")).toBe("Cuscatancingo Ñandú Ángel");
  });

  it("defuses spreadsheet formulas in text", () => {
    for (const evil of ["=SUM(A1)", "+1+1", "-2+3", "@cmd", "\tx"]) {
      expect(csvCell(evil).replace(/^"/, "")).toMatch(/^'/);
    }
  });
});

describe("buildCsv", () => {
  const build = (model = buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW), includeContext = false) =>
    buildCsv(model, allColumns(model.mode), COMMUNITY_EN, "en", { includeContext });

  it("starts with a UTF-8 BOM so Excel opens accents correctly, and uses CRLF", () => {
    const csv = build();
    expect(csv.startsWith(CSV_BOM)).toBe(true);
    expect(CSV_BOM).toBe("﻿");
    expect(csv).toContain("\r\n");
    expect(csv.replace(/\r\n/g, "")).not.toContain("\n");
  });

  it("carries mode, event, ShakeMap time, generation time, limits and attribution in the file", () => {
    const csv = build();
    expect(csv).toContain("Mode: Event");
    expect(csv).toContain("Offshore San Salvador");
    expect(csv).toContain("2023-06-30 08:15 UTC");
    expect(csv).toContain("2026-10-17 12:30 UTC");
    expect(csv).toContain("construction quality");
    expect(csv).toContain("casualties");
    expect(csv).toContain(DATA_ATTRIBUTION);
  });

  it("always carries the limits line and attribution, even for a single column", () => {
    const model = buildReportModel(baselineIndex(), COMMUNITY_EN, "en", NOW);
    const csv = buildCsv(model, ["district"], COMMUNITY_EN, "en", { includeContext: false });
    expect(csv).toContain("construction quality");
    expect(csv).toContain(DATA_ATTRIBUTION);
  });

  it("adds the context block only when asked", () => {
    expect(build()).not.toContain("Context and limits");
    expect(build(undefined, true)).toContain("Context and limits");
  });

  it("holds one header and one row per district, escaped", () => {
    const model = buildReportModel(baselineIndex(), COMMUNITY_EN, "en", NOW);
    model.rows[0] = { ...model.rows[0], name: 'Villa "El, Rosario"' };
    const csv = buildCsv(model, ["rank", "district", "prio"], COMMUNITY_EN, "en", { includeContext: false });
    const lines = csv.split("\r\n");
    const header = lines.findIndex((l) => l.startsWith("Rank,District"));
    expect(header).toBeGreaterThan(0);
    expect(lines[header + 1]).toBe('1,"Villa ""El, Rosario""",8.4');
    expect(lines[header + 2]).toBe("262,Lejos Verde,0");
  });

  it("contains nothing the API suppressed, and says 'no estimate' for a missing exposure", () => {
    const index = eventIndex();
    index.districts = [
      { ...redDistrict, estimated_exposed_population: null },
      zeroDistrict,
      withheldDistrict,
    ];
    const model = buildReportModel(index, COMMUNITY_EN, "en", NOW);
    const csv = build(model);
    expect(csv).not.toContain(String(REDACTED_LEAK));
    expect(csv).not.toContain("7.7");
    expect(csv).toContain("no estimate");
    expect(csv).toContain("Reservado Sur");
    expect(csv).toContain("Withheld");
  });

  it("writes Spanish labels for a Spanish document", () => {
    const model = buildReportModel(baselineIndex(), COMMUNITY_ES, "es", NOW);
    const csv = buildCsv(model, ["rank", "district"], COMMUNITY_ES, "es", { includeContext: false });
    expect(csv).toContain("Puesto,Distrito");
    expect(csv).toContain("Modo: Línea base");
  });
});
