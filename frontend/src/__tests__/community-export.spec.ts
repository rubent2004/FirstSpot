import { describe, expect, it } from "vitest";

import { COMMUNITY_EN, COMMUNITY_ES, DATA_ATTRIBUTION } from "../i18n/communityMessages";
import { buildReportModel } from "../modules/community-triage/exportModel";
import {
  buildWorkbookSheets,
  createWorkbookBlob,
} from "../modules/community-triage/exportXlsx";
import {
  REDACTED_LEAK,
  baselineIndex,
  eventIndex,
} from "./fixtures/prioFixtures";

const NOW = new Date("2026-10-17T12:30:00Z");

function allCells(sheets: ReturnType<typeof buildWorkbookSheets>): unknown[] {
  return sheets.flatMap((sheet) =>
    sheet.data.flat().map((cell) =>
      cell && typeof cell === "object" && "value" in cell ? cell.value : cell,
    ),
  );
}

describe("report model", () => {
  it("carries timestamp, mode, event, ShakeMap time, PAGER range and attribution", () => {
    const model = buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW);
    expect(model.generatedAtIso).toBe("2026-10-17T12:30:00.000Z");
    expect(model.mode).toBe("event");
    expect(model.modeLabel).toBe("Event");
    expect(model.event?.shakemapLabel).toBe("2023-06-30 08:15 UTC");
    expect(model.event?.pagerLabel).toContain("100–999");
    expect(model.attribution).toBe(DATA_ATTRIBUTION);
    expect(model.limitationsLine).toContain("construction quality");
    expect(model.limitationsLine).toContain("casualties");
  });

  it("states baseline mode with no event", () => {
    const model = buildReportModel(baselineIndex(), COMMUNITY_ES, "es", NOW);
    expect(model.mode).toBe("baseline");
    expect(model.modeLabel).toBe("Línea base");
    expect(model.event).toBeNull();
  });

  it("blanks every figure of a withheld district even if the payload leaks them", () => {
    const model = buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW);
    const withheld = model.rows.find((row) => row.withheld);
    expect(withheld).toBeDefined();
    expect(withheld).toMatchObject({
      rank: null,
      score: null,
      population: null,
      exposed: null,
      sphere: null,
      classKey: null,
    });
    expect(withheld?.dimensions.every((d) => d.score === null)).toBe(true);
  });
});

describe("Excel workbook", () => {
  it("has a context sheet with mode, event, ShakeMap time, limits and attribution", () => {
    const model = buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW);
    const sheets = buildWorkbookSheets(model, COMMUNITY_EN, "en");
    expect(sheets.map((s) => s.sheet)).toEqual(["Ranking", "Context and limits"]);
    const text = allCells([sheets[1]]).join("\n");
    expect(text).toContain("Event");
    expect(text).toContain("2023-06-30 08:15 UTC");
    expect(text).toContain("100–999");
    expect(text).toContain("2026-10-17");
    expect(text).toContain(DATA_ATTRIBUTION);
    expect(text).toContain("construction quality");
  });

  it("repeats mode and limits on the ranking sheet itself", () => {
    const model = buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW);
    const [ranking] = buildWorkbookSheets(model, COMMUNITY_EN, "en");
    const text = allCells([ranking]).join("\n");
    expect(text).toContain("Event");
    expect(text).toContain(DATA_ATTRIBUTION);
    expect(text).toContain("construction quality");
  });

  it("contains nothing the API suppressed", () => {
    const model = buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW);
    const cells = allCells(buildWorkbookSheets(model, COMMUNITY_EN, "en"));
    expect(cells).not.toContain(REDACTED_LEAK);
    expect(cells.join("\n")).not.toContain(String(REDACTED_LEAK));
    expect(cells).not.toContain(7.7);
    // the district still appears, as withheld, so it is not silently dropped
    expect(cells).toContain("Reservado Sur");
    expect(cells).toContain("Withheld");
  });

  it("includes Sphere minimums labelled as such, only for districts that have them", () => {
    const model = buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW);
    const [ranking] = buildWorkbookSheets(model, COMMUNITY_EN, "en");
    const header = ranking.data.find((row) =>
      row.some((c) => typeof c === "object" && c && "value" in c && c.value === "Rank"),
    );
    const headerText = (header ?? []).map((c) => (c && typeof c === "object" && "value" in c ? c.value : c)).join("|");
    expect(headerText).toContain("Sphere minimum requirement");
    expect(headerText).not.toMatch(/deliver/i);
  });

  it("omits the hazard column in baseline mode", () => {
    const model = buildReportModel(baselineIndex(), COMMUNITY_EN, "en", NOW);
    const [ranking] = buildWorkbookSheets(model, COMMUNITY_EN, "en");
    const text = allCells([ranking]).join("\n");
    expect(text).not.toContain("Hazard and exposure");
    expect(text).toContain("Vulnerability");
  });

  it("builds a real .xlsx (zip) blob without a server round trip", async () => {
    const model = buildReportModel(eventIndex(), COMMUNITY_EN, "en", NOW);
    const blob = await createWorkbookBlob(model, COMMUNITY_EN, "en");
    // jsdom's Blob has no arrayBuffer(); FileReader is the portable way to read it.
    const bytes = await new Promise<Uint8Array>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(blob);
    });
    expect(bytes.length).toBeGreaterThan(500);
    expect(String.fromCharCode(bytes[0], bytes[1])).toBe("PK");
  });
});
