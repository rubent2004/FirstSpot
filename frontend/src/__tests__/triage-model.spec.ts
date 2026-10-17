import { describe, expect, it } from "vitest";

import type { DistrictPrioRead, PagerRead } from "../api/client";
import {
  ALERT_CLASS_ORDER,
  asAlertClass,
  classCounts,
  formatPagerRange,
  parsePagerRange,
  zeroedDimensionKeys,
} from "../modules/community-triage/triageModel";

function pager(level: string, band_label: string): PagerRead {
  return { level, band_label, response_implication: "x" };
}

function district(patch: Partial<DistrictPrioRead>): DistrictPrioRead {
  return {
    district_code: "060101",
    district_name: "Test",
    population: 1000,
    rank: 1,
    score: 5,
    inform_rescaled_score: 5,
    alert_class: "naranja",
    dimensions: [],
    zeroed_by: [],
    zero_reason: null,
    withheld: false,
    withheld_reason: null,
    max_mmi: null,
    estimated_exposed_population: null,
    sphere: null,
    ...patch,
  };
}

describe("PAGER band range", () => {
  it("reads a closed band as a range, never a colour alone", () => {
    const range = parsePagerRange(
      pager("orange", "100-999 estimated fatalities (PAGER orange)"),
    );
    expect(range).toEqual({ level: "orange", lower: 100, upper: 999 });
    expect(formatPagerRange(range!, "en")).toBe("100–999");
  });

  it("reads the open-ended red band and the exact-zero green band", () => {
    const red = parsePagerRange(
      pager("red", "1000 or more estimated fatalities (PAGER red)"),
    );
    expect(red).toEqual({ level: "red", lower: 1000, upper: null });
    expect(formatPagerRange(red!, "es")).toMatch(/^1\D?000 o más$/);
    const green = parsePagerRange(
      pager("green", "0 estimated fatalities (PAGER green)"),
    );
    expect(formatPagerRange(green!, "en")).toBe("0");
  });

  it("returns null when the event has no PAGER or the label is unreadable", () => {
    expect(parsePagerRange(null)).toBeNull();
    expect(parsePagerRange(pager("orange", "no numbers here"))).toBeNull();
  });
});

describe("alert classes", () => {
  it("orders the four official DGPC classes from most to least urgent", () => {
    expect(ALERT_CLASS_ORDER).toEqual(["roja", "naranja", "amarilla", "verde"]);
    expect(asAlertClass("naranja")).toBe("naranja");
    expect(asAlertClass("purple")).toBeNull();
    expect(asAlertClass(null)).toBeNull();
  });

  it("counts districts per class and ignores withheld ones", () => {
    const counts = classCounts([
      district({ alert_class: "roja" }),
      district({ alert_class: "roja" }),
      district({ alert_class: "verde" }),
      district({ alert_class: null, withheld: true, score: null }),
    ]);
    expect(counts).toEqual({ roja: 2, naranja: 0, amarilla: 0, verde: 1 });
  });
});

describe("zero scores", () => {
  it("names the dimensions that zeroed the score, without backend codes", () => {
    expect(
      zeroedDimensionKeys(
        district({ score: 0, zeroed_by: ["hazard_and_exposure"] }),
      ),
    ).toEqual(["hazard_and_exposure"]);
    expect(zeroedDimensionKeys(district({ score: 5 }))).toEqual([]);
  });
});
