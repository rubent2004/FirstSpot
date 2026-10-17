import { describe, expect, it } from "vitest";
import { hasDrawableSize } from "../modules/map-viewer/composables/useLeafletMap";

/**
 * While a print sheet is open, print media hides the live map and its container
 * collapses to 0x0. Resizing Leaflet then makes leaflet.heat call
 * getImageData(0, 0, 0, 0), which throws IndexSizeError. The map must only be
 * resized when it has an area to draw into; it is resized again when it returns.
 */
describe("hasDrawableSize", () => {
  it("is false for a collapsed container", () => {
    expect(hasDrawableSize({ clientWidth: 0, clientHeight: 0 })).toBe(false);
    expect(hasDrawableSize({ clientWidth: 800, clientHeight: 0 })).toBe(false);
    expect(hasDrawableSize({ clientWidth: 0, clientHeight: 600 })).toBe(false);
  });

  it("is false without a container", () => {
    expect(hasDrawableSize(null)).toBe(false);
  });

  it("is true for a visible container", () => {
    expect(hasDrawableSize({ clientWidth: 1, clientHeight: 1 })).toBe(true);
    expect(hasDrawableSize({ clientWidth: 1918, clientHeight: 900 })).toBe(true);
  });
});
