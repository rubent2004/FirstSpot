import { expect, test } from "./support/fixtures";
import { isKeyGatedTileUrl } from "./support/fixtures";
import {
  chooseFormat,
  gotoApp,
  openExportDialog,
  printSheet,
  selectZone,
  submitExport,
  waitForMapIdle,
  waitForPrintMap,
} from "./support/app";

/**
 * The CARTO incident: a basemap that needs an API key (or forbids this use)
 * slipped in. The guard fixture watches every request in every test; this spec
 * also proves the guard can see a violation and drives every basemap the UI offers.
 */

test.describe("tile guard", () => {
  test("the matcher flags key-gated providers and lets the keyless ones through", () => {
    const gated = [
      "https://a.basemaps.cartocdn.com/light_all/12/1000/2000.png",
      "https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/1/2/3",
      "https://api.maptiler.com/maps/streets/256/1/2/3.png?key=x",
      "https://tile.thunderforest.com/cycle/1/2/3.png?apikey=x",
      "https://tiles.stadiamaps.com/tiles/alidade_smooth/1/2/3.png",
      "https://api.tomtom.com/map/1/tile/basic/main/1/2/3.png?key=x",
      "https://mt1.google.com/vt/lyrs=m&x=1&y=2&z=3",
      "https://tile.googleapis.com/v1/2dtiles/1/2/3?key=x",
    ];
    for (const url of gated) expect(isKeyGatedTileUrl(url), url).toBe(true);
    const allowed = [
      "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/1/2/3",
      "https://a.tile.openstreetmap.org/1/2/3.png",
      "http://localhost:5173/api/v1/zones",
      "https://fonts.googleapis.com/css2?family=Inter",
    ];
    for (const url of allowed) expect(isKeyGatedTileUrl(url), url).toBe(false);
  });

  test("every basemap, zone change and the print map load tiles only from keyless providers", async ({ page, guards }) => {
    const tileHosts = new Set<string>();
    page.on("request", (request) => {
      if (request.resourceType() === "image" && /\/tile|\.png/.test(request.url())) {
        tileHosts.add(new URL(request.url()).host);
      }
    });
    await gotoApp(page);
    await waitForMapIdle(page);

    await page.getByRole("tab", { name: "Estilo" }).click();
    for (const basemap of ["Mapa táctico", "Mapa claro"]) {
      await page.getByRole("button", { name: basemap }).click();
      await expect(page.getByRole("button", { name: basemap })).toHaveAttribute("aria-pressed", "true");
      await page.waitForLoadState("networkidle");
    }
    await page.getByRole("tab", { name: "Inicio" }).click();
    await page.getByRole("button", { name: "Zoom in" }).click();
    await page.getByRole("button", { name: "Zoom out" }).click();
    await selectZone(page, "Escuintla", "Escuintla");

    const dialog = await openExportDialog(page);
    await chooseFormat(dialog, "Mapa de la vista actual");
    await submitExport(dialog);
    await expect(printSheet(page)).toBeVisible();
    await waitForPrintMap(page);

    // The guard must not pass vacuously: tiles were requested, all from keyless hosts.
    expect(tileHosts.size).toBeGreaterThan(0);
    expect([...tileHosts].filter((host) => isKeyGatedTileUrl(`https://${host}/`))).toEqual([]);
    expect(guards.blockedRequests).toEqual([]);
  });
});
