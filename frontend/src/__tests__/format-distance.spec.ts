import { describe, expect, it } from "vitest";
import { formatDistance } from "../utils/formatDistance";

describe("formatDistance", () => {
  it("formats common analysis radii using readable units", () => {
    expect(formatDistance(500, "es")).toBe("500 m");
    expect(formatDistance(1000, "es")).toBe("1 km");
    expect(formatDistance(3000, "es")).toBe("3 km");
    expect(formatDistance(1500, "en")).toBe("1.5 km");
    expect(formatDistance(1500, "es")).toBe("1,5 km");
  });

  it("handles invalid distances without showing a misleading value", () => {
    expect(formatDistance(0, "es")).toBe("—");
    expect(formatDistance(Number.NaN, "en")).toBe("—");
  });
});
