import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import ElementPlus from "element-plus";

import {
  apiClient,
  type ActiveHazardsResponse,
  type HeatmapResponse,
  type PredefinedZoneRead,
} from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import App from "../App.vue";
import { baselineIndex, eventIndex } from "./fixtures/prioFixtures";
import { SONSONATE_PLACES, WEATHER } from "./fixtures/mapPrintFixtures";

const zones: PredefinedZoneRead[] = [
  { key: "sonsonate", name: "Sonsonate", department: "Sonsonate", latitude: 13.7222, longitude: -89.7236, default_radius_meters: 10000 },
];

const heatmap: HeatmapResponse = {
  points: [],
  matrix: [],
  kpis: {
    total_places: 4,
    pending_count: 2,
    in_progress_count: 1,
    attended_count: 1,
    critical_urgency_count: 1,
    total_estimated_vulnerable: 0,
    max_priority_score: 95,
    counts_by_group: { health: 2, education: 2, shelter: 0, concurrency: 0 },
    counts_by_category: { hospital: 1 },
  },
};

const hazards = (sources: string[]): ActiveHazardsResponse => ({
  zone_name: "Sonsonate",
  latitude: 13.7222,
  longitude: -89.7236,
  scenario: "none",
  overall_alert_level: "green",
  zone_hazard_bonus: 0,
  active_sources: sources,
  weather: WEATHER,
  events: [],
});

let wrapper: VueWrapper | null = null;

async function mountApp(): Promise<VueWrapper> {
  const pinia = createPinia();
  setActivePinia(pinia);
  wrapper = mount(App, { global: { plugins: [pinia, ElementPlus] }, attachTo: document.body });
  await flushPromises();
  return wrapper;
}

describe("application shell", () => {
  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "listPredefinedZones").mockResolvedValue(zones);
    vi.spyOn(apiClient, "listPrioritizedPlaces").mockResolvedValue(SONSONATE_PLACES);
    vi.spyOn(apiClient, "getHeatmapData").mockResolvedValue(heatmap);
    vi.spyOn(apiClient, "getActiveHazards").mockResolvedValue(hazards(["USGS", "Open-Meteo"]));
    vi.spyOn(apiClient, "syncPlacesFromOverpass").mockResolvedValue({
      zone_name: "Sonsonate",
      latitude: 13.7,
      longitude: -89.7,
      radius_meters: 10000,
      fetched_elements_count: 0,
      synced_places_count: 0,
      used_fallback: false,
      source_endpoint: "x",
    });
    vi.spyOn(apiClient, "getPrioIndex").mockImplementation(async (id) => (id ? eventIndex() : baselineIndex()));
    vi.spyOn(apiClient, "listHazardEvents").mockResolvedValue({ events: [], pager_alert_bands: [], declared_gaps: [], source: "x" });
  });
  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    document.body.innerHTML = "";
  });

  it("opens on the district ranking with no peer tabs for territories and places", async () => {
    const app = await mountApp();
    expect(app.text()).toContain("Priority by district");
    expect(app.findAll('[role="tab"]').map((t) => t.text())).not.toContain("Places");
    expect(app.findAll('[role="tab"]').map((t) => t.text())).not.toContain("Territories");
  });

  it("scopes the ranking to the work zone's department and says how many of the country it shows", async () => {
    const app = await mountApp();
    // the fixture districts are in San Salvador and Ahuachapán, not in the Sonsonate zone
    expect(app.get('[data-testid="list-count"]').text()).toBe("Showing 0 of 2 districts");
    expect(app.get(".state.empty").text()).toContain("No district matches.");
    const wide = app.get('[aria-label="Scope"]').findAll('input[type="radio"]')[1];
    await wide.setValue(true);
    await flushPromises();
    expect(app.get('[data-testid="list-count"]').text()).toBe("Showing 2 of 2 districts");
    expect(app.findAll('[data-testid="district-row"]')).toHaveLength(2);
  });

  it("follows the interface language in the document's lang attribute", async () => {
    await mountApp();
    expect(document.documentElement.lang).toBe("en");
    setAppLocale("es");
    await flushPromises();
    expect(document.documentElement.lang).toBe("es");
    setAppLocale("en");
  });

  it("tells the operator the map shows places, not districts, while the ranking is open", async () => {
    const app = await mountApp();
    expect(app.get(".map-caption").text()).toContain("not districts");
  });

  it("keeps the feeds to one status-bar chip when they are healthy", async () => {
    const app = await mountApp();
    expect(app.find('.geo-ribbon [data-testid="hazard-telemetry-strip"]').exists()).toBe(false);
    const chip = app.get('[data-testid="feeds-chip"]');
    expect(chip.text()).toContain("Feeds OK");
    // closed: nothing of the strip is in the page
    expect(document.body.querySelector('[data-testid="hazard-telemetry-strip"]')).toBeNull();
  });

  it("opens the full feeds panel from the chip, one click away", async () => {
    const app = await mountApp();
    await app.get('[data-testid="feeds-chip"]').trigger("click");
    await flushPromises();
    const panel = document.body.querySelector('[role="dialog"] [data-testid="hazard-telemetry-strip"]');
    expect(panel).not.toBeNull();
    expect(panel!.textContent).toContain("Open-Meteo");
    // drill scenarios and the address search stay reachable
    expect(panel!.querySelector('[data-testid="drill-toggle-btn"]')).not.toBeNull();
    expect(panel!.querySelector('[data-testid="nominatim-search-input"]')).not.toBeNull();
  });

  it("expands the feeds into the ribbon only when a feed is stale or failing", async () => {
    vi.mocked(apiClient.getActiveHazards).mockResolvedValue(hazards(["fallback://sonsonate-seed"]));
    const app = await mountApp();
    expect(app.find('.geo-ribbon [data-testid="hazard-telemetry-strip"]').exists()).toBe(true);
    const chip = app.get('[data-testid="feeds-chip"]');
    expect(chip.text()).toContain("Fallback data");
    expect(chip.classes()).toContain("attention");
  });
});
