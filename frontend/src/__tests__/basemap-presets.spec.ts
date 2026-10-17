import { describe, expect, it } from "vitest";

import { BASEMAP_PRESETS } from "../modules/map-viewer/composables/useLeafletMap";

/**
 * Regression guard for silent basemap failure.
 *
 * This project shipped CARTO basemaps (basemaps.cartocdn.com), which later
 * began requiring an API key. CARTO does not fail loudly: it answers HTTP 200
 * with a ~2 KB "API KEY REQUIRED" placeholder tile. No status-code check, no
 * build step and no test caught it, so the operator map rendered placeholder
 * text across every tile until a human looked at the screen.
 *
 * Tile providers are therefore held to one rule: a basemap URL may only point
 * at a provider that serves tiles without credentials. Esri's Canvas rasters
 * and openstreetmap.org both qualify; anything key-gated does not.
 */

/**
 * Hosts known to answer HTTP 200 with a placeholder tile once a key is
 * required, which makes their failure mode invisible to runtime checks.
 */
const KEY_GATED_TILE_HOSTS = [
  "cartocdn.com",
  "api.mapbox.com",
  "maptiler.com",
  "thunderforest.com",
  "stadiamaps.com",
  "api.tomtom.com",
  "googleapis.com",
];

/** Every tile URL the map can request, base layers plus reference overlays. */
function collectPresetUrls(): Array<{ id: string; role: string; url: string }> {
  return Object.entries(BASEMAP_PRESETS).flatMap(([id, preset]) => {
    const urls = [{ id, role: "url", url: preset.url }];
    if (preset.referenceUrl) {
      urls.push({ id, role: "referenceUrl", url: preset.referenceUrl });
    }
    return urls;
  });
}

describe("BASEMAP_PRESETS", () => {
  it("declares at least one preset with a tile URL", () => {
    const urls = collectPresetUrls();
    expect(urls.length).toBeGreaterThan(0);
    for (const { id, role, url } of urls) {
      expect(
        url,
        `Basemap preset "${id}.${role}" has an empty tile URL, so the map would render blank tiles.`,
      ).toBeTruthy();
    }
  });

  it("never points at a tile provider that requires an API key", () => {
    for (const { id, role, url } of collectPresetUrls()) {
      const host = new URL(url.replace("{s}.", "")).hostname;
      const offender = KEY_GATED_TILE_HOSTS.find(
        (gated) => host === gated || host.endsWith(`.${gated}`),
      );

      expect(
        offender,
        [
          `Basemap preset "${id}.${role}" points at ${host}, a tile provider that requires an API key.`,
          "",
          "This exact regression already shipped once: the map used CARTO",
          "(basemaps.cartocdn.com), which started requiring a key and then answered",
          'HTTP 200 with a ~2 KB "API KEY REQUIRED" placeholder tile. Because the',
          "response was a successful image, nothing detected it -- not a status-code",
          "check, not the build, not a single test. Every tile on the operator map",
          "silently rendered placeholder text until a human noticed on screen.",
          "",
          "Use a provider that serves tiles without credentials (Esri Canvas,",
          "openstreetmap.org). If a key-gated provider is genuinely required, it needs",
          "a real tile-content health check first -- HTTP 200 does not mean a map.",
        ].join("\n"),
      ).toBeUndefined();
    }
  });

  it("requests every tile over https", () => {
    for (const { id, role, url } of collectPresetUrls()) {
      expect(
        url.startsWith("https://"),
        `Basemap preset "${id}.${role}" is not https. Plain-http tiles are blocked as mixed content on an https deployment, which blanks the map.`,
      ).toBe(true);
    }
  });
});
