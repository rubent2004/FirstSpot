import { describe, expect, it } from "vitest";

import { departmentName, departmentPrefix } from "../modules/community-triage/departments";
import {
  filterDistricts,
  groupByClass,
  sortDistricts,
} from "../modules/community-triage/rankModel";
import {
  redDistrict,
  withheldDistrict,
  zeroDistrict,
} from "./fixtures/prioFixtures";
import type { DistrictPrioRead } from "../api/client";

const withExposure = (d: DistrictPrioRead, value: number | null, name: string, code = d.district_code) => ({
  ...d,
  district_code: code,
  district_name: name,
  estimated_exposed_population: value,
});

describe("departments", () => {
  it("names the department from the first two digits of the district code", () => {
    expect(departmentName("060101")).toBe("San Salvador");
    expect(departmentName("030402")).toBe("Sonsonate");
    expect(departmentName("140101")).toBe("La Unión");
  });

  it("returns null for a code it does not know instead of guessing", () => {
    expect(departmentName("990101")).toBeNull();
    expect(departmentName("")).toBeNull();
  });

  it("resolves a zone's department name to its prefix, ignoring accents and case", () => {
    expect(departmentPrefix("Sonsonate")).toBe("03");
    expect(departmentPrefix("la union")).toBe("14");
    expect(departmentPrefix("Ahuachapan")).toBe("01");
    expect(departmentPrefix("Atlantis")).toBeNull();
    expect(departmentPrefix(null)).toBeNull();
  });
});

describe("filterDistricts", () => {
  const all = [redDistrict, zeroDistrict, withheldDistrict];

  it("scopes to one department by code prefix", () => {
    const out = filterDistricts(all, { departmentPrefix: "06", classFilter: null, search: "" });
    expect(out.map((d) => d.district_name)).toEqual(["San Marcos Rojo"]);
  });

  it("combines class and accent-insensitive search", () => {
    const out = filterDistricts(all, { departmentPrefix: null, classFilter: "verde", search: "lejos" });
    expect(out.map((d) => d.district_name)).toEqual(["Lejos Verde"]);
  });

  it("a withheld district has no class, so a class filter never lists it", () => {
    const out = filterDistricts(all, { departmentPrefix: null, classFilter: "roja", search: "" });
    expect(out.map((d) => d.district_name)).toEqual(["San Marcos Rojo"]);
  });
});

describe("sortDistricts", () => {
  const a = withExposure(redDistrict, 500, "Alfa", "060001");
  const b = withExposure(redDistrict, null, "Beta", "060002");
  const c = withExposure(redDistrict, 9000, "Ñandú", "060003");
  const zero = withExposure(redDistrict, 0, "Cero", "060004");

  it("sorts by exposed population, largest first, with no estimate after real numbers", () => {
    const out = sortDistricts([a, b, c, zero, withheldDistrict], "exposed", "es");
    expect(out.map((d) => d.district_name)).toEqual(["Ñandú", "Alfa", "Cero", "Beta", "Reservado Sur"]);
  });

  it("treats a missing estimate as unknown, never as zero", () => {
    const out = sortDistricts([b, zero], "exposed", "es");
    expect(out.map((d) => d.district_name)).toEqual(["Cero", "Beta"]);
  });

  it("sorts by name with Spanish collation, withheld districts keep their place by name", () => {
    const out = sortDistricts([c, a, zero], "name", "es");
    expect(out.map((d) => d.district_name)).toEqual(["Alfa", "Cero", "Ñandú"]);
  });

  it("sorts by score as the official rank, with withheld districts last", () => {
    const out = sortDistricts([zeroDistrict, withheldDistrict, redDistrict], "score", "es");
    expect(out.map((d) => d.district_name)).toEqual(["San Marcos Rojo", "Lejos Verde", "Reservado Sur"]);
  });
});

describe("groupByClass", () => {
  it("groups most urgent first and puts withheld districts in their own last group", () => {
    const groups = groupByClass([zeroDistrict, withheldDistrict, redDistrict]);
    expect(groups.map((g) => g.key)).toEqual(["roja", "verde", "withheld"]);
    expect(groups.map((g) => g.districts.length)).toEqual([1, 1, 1]);
  });

  it("omits empty groups", () => {
    expect(groupByClass([])).toEqual([]);
  });
});
