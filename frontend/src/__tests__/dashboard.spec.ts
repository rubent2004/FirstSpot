import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { DOMWrapper, flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import {
  apiClient,
  OPENAPI_OPERATION_IDS,
  OPENAPI_VERSION,
  type ActiveHazardsResponse,
  type HeatmapResponse,
  type PlaceRead,
  type PredefinedZoneRead,
  type SyncPlacesResponse,
  type InstitutionAccountRead,
  type PlaceActivityRead,
} from "../api/client";
import { usePrioritizationStore } from "../stores/usePrioritizationStore";
import { setAppLocale } from "../i18n/useI18n";
import SyncHeaderBar from "../modules/sync-controls/SyncHeaderBar.vue";
import HazardTelemetryStrip from "../modules/sync-controls/HazardTelemetryStrip.vue";
import PriorityQueuePanel from "../modules/priority-queue/PriorityQueuePanel.vue";
import PlaceTriageDrawer from "../modules/priority-queue/PlaceTriageDrawer.vue";
import VulnerabilityHeatmapCanvas from "../modules/map-viewer/VulnerabilityHeatmapCanvas.vue";
import { useTheme } from "../composables/useTheme";

const sampleZones: PredefinedZoneRead[] = [
  {
    key: "sonsonate",
    name: "Sonsonate",
    department: "Sonsonate",
    latitude: 13.7222,
    longitude: -89.7236,
    default_radius_meters: 10000,
  },
  {
    key: "san_salvador",
    name: "San Salvador",
    department: "San Salvador",
    latitude: 13.6929,
    longitude: -89.2182,
    default_radius_meters: 8000,
  },
];

const sampleHospital: PlaceRead = {
  id: "11111111-2222-3333-4444-555555555555",
  osm_type: "way",
  osm_id: 248190101,
  name: "Sonsonate Regional National Hospital",
  category: "hospital",
  vulnerability_group: "health",
  zone_name: "Sonsonate",
  latitude: 13.7203,
  longitude: -89.7248,
  osm_tags: { amenity: "hospital", emergency: "yes" },
  attention_status: "pending",
  urgency_level: 3,
  estimated_vulnerable_count: 0,
  institution_notes: null,
  category_weight: 100,
  nearby_places_count: 4,
  priority_score: 120.0,
  last_osm_sync_at: "2026-10-16T11:00:00Z",
  updated_at: "2026-10-16T11:00:00Z",
};

const sampleInstitutionAccount: InstitutionAccountRead = {
  id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  display_name: "Ana Respuesta",
  email: "ana@example.org",
  role: "owner",
  institution: {
    id: "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
    name: "Bomberos de Sonsonate",
    country: "El Salvador",
    sector: "Bomberos",
    registration_code: "FSP-ABCDEF123456",
    verification_status: "verified",
    created_at: "2026-10-16T11:00:00Z",
    verified_at: "2026-10-16T12:00:00Z",
  },
};

const sampleHeatmapResponse: HeatmapResponse = {
  points: [
    {
      id: sampleHospital.id,
      name: sampleHospital.name,
      category: "hospital",
      vulnerability_group: "health",
      attention_status: "pending",
      latitude: 13.7203,
      longitude: -89.7248,
      priority_score: 120.0,
      intensity: 1.0,
    },
  ],
  matrix: [[13.7203, -89.7248, 1.0]],
  kpis: {
    total_places: 1,
    pending_count: 1,
    in_progress_count: 0,
    attended_count: 0,
    critical_urgency_count: 0,
    total_estimated_vulnerable: 0,
    max_priority_score: 120.0,
    counts_by_group: { health: 1, education: 0, shelter: 0, concurrency: 0 },
    counts_by_category: { hospital: 1 },
  },
};

const sampleHazardsResponse: ActiveHazardsResponse = {
  zone_name: "Sonsonate",
  latitude: 13.7222,
  longitude: -89.7236,
  scenario: "sonsonate_earthquake_m64",
  overall_alert_level: "red",
  zone_hazard_bonus: 35.0,
  active_sources: ["USGS", "Open-Meteo", "NASA EONET v3"],
  weather: {
    temperature_c: 29.2,
    precipitation_mm: 2.4,
    rain_mm: 2.4,
    wind_speed_kmh: 18.5,
    wind_gusts_kmh: 31.0,
    weather_code: 61,
    weather_label: "Lluvia moderada",
    alert_level: "green",
    source: "Open-Meteo",
    is_simulated: true,
  },
  events: [
    {
      id: "usgs-sim-sv-2026-m64",
      hazard_type: "earthquake",
      title: "M 6.4 - 18 km SSW of Acajutla, Sonsonate, El Salvador",
      source: "USGS Earthquake API (Simulacro)",
      alert_level: "red",
      latitude: 13.56,
      longitude: -89.83,
      radius_km: 85.0,
      magnitude: 6.4,
      depth_km: 32.5,
      occurred_at: "2026-10-16T11:30:00Z",
      url: "https://earthquake.usgs.gov/earthquakes/map/",
      is_simulated: true,
    },
  ],
};

describe("OpenAPI 3.1 Generated Contract & SDK", () => {
  it("exposes OpenAPI 3.1 version and inter-agency operations", () => {
    expect(OPENAPI_VERSION).toMatch(/^3\.1/);
    expect([...OPENAPI_OPERATION_IDS]).toEqual([
      "createInstitutionInvite",
      "createPlaceActivity",
      "getHealthStatus",
      "getHeatmapData",
      "getInstitutionAccount",
      "getPlaceById",
      "getPlacePopulationExposure",
      "joinInstitution",
      "listPlaceActivities",
      "listPredefinedZones",
      "listPrioritizedPlaces",
      "loginInstitutionUser",
      "registerInstitution",
      "reviewInstitutionRegistration",
      "syncPlacesFromOverpass",
      "updatePlaceTriage",
    ]);
  });
});

describe("usePrioritizationStore (Pinia)", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("auto-triggers syncZone('sonsonate') during initializeDashboard when database is empty", async () => {
    const emptyHeatmap: HeatmapResponse = {
      points: [],
      matrix: [],
      kpis: {
        total_places: 0,
        pending_count: 0,
        in_progress_count: 0,
        attended_count: 0,
        critical_urgency_count: 0,
        total_estimated_vulnerable: 0,
        max_priority_score: 0,
        counts_by_group: {},
        counts_by_category: {},
      },
    };

    const syncSummary: SyncPlacesResponse = {
      zone_name: "Sonsonate",
      latitude: 13.7222,
      longitude: -89.7236,
      radius_meters: 10000,
      fetched_elements_count: 12,
      synced_places_count: 1,
      used_fallback: true,
      source_endpoint: "fallback://sonsonate-seed",
    };

    vi.spyOn(apiClient, "listPredefinedZones").mockResolvedValue(sampleZones);
    vi.spyOn(apiClient, "getActiveHazards").mockResolvedValue(
      sampleHazardsResponse,
    );
    const listPlacesSpy = vi
      .spyOn(apiClient, "listPrioritizedPlaces")
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([sampleHospital]);
    const getHeatmapSpy = vi
      .spyOn(apiClient, "getHeatmapData")
      .mockResolvedValueOnce(emptyHeatmap)
      .mockResolvedValueOnce(sampleHeatmapResponse);
    const syncSpy = vi
      .spyOn(apiClient, "syncPlacesFromOverpass")
      .mockResolvedValue(syncSummary);

    const store = usePrioritizationStore();
    await store.initializeDashboard();

    expect(syncSpy).toHaveBeenCalledTimes(1);
    expect(listPlacesSpy).toHaveBeenCalledTimes(2);
    expect(getHeatmapSpy).toHaveBeenCalledTimes(2);
    expect(store.places).toHaveLength(1);
    expect(store.places[0].name).toBe("Sonsonate Regional National Hospital");
    expect(store.kpis.total_places).toBe(1);
    expect(store.computeHazardBonusForPlace(sampleHospital)).toBeGreaterThan(20);
  });

  it("keeps the newest response when filter requests finish out of order", async () => {
    let resolveStalePlaces!: (places: PlaceRead[]) => void;
    let resolveStaleHeatmap!: (response: HeatmapResponse) => void;
    const stalePlaces = new Promise<PlaceRead[]>((resolve) => {
      resolveStalePlaces = resolve;
    });
    const staleHeatmap = new Promise<HeatmapResponse>((resolve) => {
      resolveStaleHeatmap = resolve;
    });
    const latestPlace = { ...sampleHospital, name: "Latest filtered hospital" };
    const latestHeatmap = {
      ...sampleHeatmapResponse,
      kpis: { ...sampleHeatmapResponse.kpis, total_places: 7 },
    };
    const listSpy = vi
      .spyOn(apiClient, "listPrioritizedPlaces")
      .mockReturnValueOnce(stalePlaces)
      .mockResolvedValueOnce([latestPlace]);
    vi.spyOn(apiClient, "getHeatmapData")
      .mockReturnValueOnce(staleHeatmap)
      .mockResolvedValueOnce(latestHeatmap);

    const store = usePrioritizationStore();
    store.filters.search = "older query";
    const staleRequest = store.fetchPlacesAndHeatmap();
    store.filters.search = "latest query";
    const latestRequest = store.fetchPlacesAndHeatmap();
    await latestRequest;

    expect(listSpy.mock.calls.map(([params]) => params?.search)).toEqual([
      "older query",
      "latest query",
    ]);
    expect(store.places[0].name).toBe("Latest filtered hospital");
    expect(store.kpis.total_places).toBe(7);
    expect(store.isLoading).toBe(false);

    resolveStalePlaces([sampleHospital]);
    resolveStaleHeatmap(sampleHeatmapResponse);
    await staleRequest;
    expect(store.places[0].name).toBe("Latest filtered hospital");
    expect(store.kpis.total_places).toBe(7);
  });

  it("resets every queue and heatmap filter to its default", () => {
    const store = usePrioritizationStore();
    store.filters.category = "hospital";
    store.filters.vulnerabilityGroup = "health";
    store.filters.attentionStatus = "pending";
    store.filters.minUrgency = 4;
    store.filters.search = "clinic";
    store.filters.includeAttendedInHeatmap = false;

    store.resetFilters();

    expect(store.filters).toEqual({
      category: "",
      vulnerabilityGroup: "",
      attentionStatus: "",
      minUrgency: null,
      search: "",
      includeAttendedInHeatmap: true,
    });
  });

  it("updates institutional triage and refreshes prioritized queue", async () => {
    const updatedHospital: PlaceRead = {
      ...sampleHospital,
      attention_status: "in_progress",
      urgency_level: 5,
      estimated_vulnerable_count: 220,
      institution_notes: "Mobile surgical unit deployed",
      priority_score: 261.0,
    };

    vi.spyOn(apiClient, "updatePlaceTriage").mockResolvedValue(updatedHospital);
    vi.spyOn(apiClient, "listPrioritizedPlaces").mockResolvedValue([
      updatedHospital,
    ]);
    vi.spyOn(apiClient, "getHeatmapData").mockResolvedValue({
      ...sampleHeatmapResponse,
      kpis: {
        ...sampleHeatmapResponse.kpis,
        pending_count: 0,
        in_progress_count: 1,
        critical_urgency_count: 1,
        total_estimated_vulnerable: 220,
        max_priority_score: 261.0,
      },
    });

    const store = usePrioritizationStore();
    store.institutionSession = {
      accessToken: "test-access-token",
      expiresAt: Date.now() + 60_000,
      account: sampleInstitutionAccount,
    };
    vi.spyOn(apiClient, "listPlaceActivities").mockResolvedValue([]);
    const res = await store.savePlaceTriage(sampleHospital.id, {
      attention_status: "in_progress",
      urgency_level: 5,
      estimated_vulnerable_count: 220,
      institution_notes: "Mobile surgical unit deployed",
    });

    expect(res).not.toBeNull();
    expect(store.selectedPlace?.attention_status).toBe("in_progress");
    expect(store.selectedPlace?.priority_score).toBe(261.0);
    expect(store.kpis.in_progress_count).toBe(1);
    expect(store.kpis.total_estimated_vulnerable).toBe(220);
  });

  it("requires a verified institutional session before saving a public field action", async () => {
    const updateSpy = vi.spyOn(apiClient, "updatePlaceTriage");
    const store = usePrioritizationStore();

    const result = await store.savePlaceTriage(sampleHospital.id, {
      activity_type: "on_scene",
      institution_notes: "Unit is on site",
    });

    expect(result).toBeNull();
    expect(updateSpy).not.toHaveBeenCalled();
    expect(store.error).toContain("organización verificada");
  });

  it("switches zone instantly with selectZone without triggering Overpass sync if places exist", async () => {
    const listSpy = vi.spyOn(apiClient, "listPrioritizedPlaces").mockResolvedValue([sampleHospital]);
    const heatmapSpy = vi.spyOn(apiClient, "getHeatmapData").mockResolvedValue(sampleHeatmapResponse);
    const hazardsSpy = vi.spyOn(apiClient, "getActiveHazards").mockResolvedValue(sampleHazardsResponse);
    const syncSpy = vi.spyOn(apiClient, "syncPlacesFromOverpass");

    const store = usePrioritizationStore();
    store.zones = sampleZones;

    await store.selectZone("san_salvador");
    expect(store.selectedZoneKey).toBe("san_salvador");
    expect(store.activeZoneName).toBe("San Salvador");
    expect(listSpy).toHaveBeenCalled();
    expect(heatmapSpy).toHaveBeenCalled();
    expect(hazardsSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        zone_key: "san_salvador",
        latitude: 13.6929,
        longitude: -89.2182,
      }),
    );
    expect(store.hazardLastCheckedAt).not.toBeNull();
    // Since kpis.total_places > 0, syncPlacesFromOverpass should NOT be called!
    expect(syncSpy).not.toHaveBeenCalled();
  });

  it("keeps the last hazard response visible and exposes refresh failures", async () => {
    const hazardsSpy = vi
      .spyOn(apiClient, "getActiveHazards")
      .mockResolvedValueOnce(sampleHazardsResponse)
      .mockRejectedValueOnce(new Error("network unavailable"));
    const store = usePrioritizationStore();

    await store.fetchHazards();
    const lastSuccessfulCheck = store.hazardLastCheckedAt;
    await store.fetchHazards();

    expect(store.activeHazards).toEqual(sampleHazardsResponse);
    expect(store.hazardLastCheckedAt).toBe(lastSuccessfulCheck);
    expect(store.hazardRefreshError).toBe("network unavailable");
    expect(store.isRefreshingHazards).toBe(false);
    expect(hazardsSpy).toHaveBeenCalledTimes(2);
  });

  it("clears the previous zone's hazards while the newly selected zone loads", async () => {
    let resolveHazards!: (value: ActiveHazardsResponse) => void;
    const pendingHazards = new Promise<ActiveHazardsResponse>((resolve) => {
      resolveHazards = resolve;
    });
    vi.spyOn(apiClient, "getActiveHazards")
      .mockResolvedValueOnce(sampleHazardsResponse)
      .mockReturnValueOnce(pendingHazards);
    vi.spyOn(apiClient, "listPrioritizedPlaces").mockResolvedValue([sampleHospital]);
    vi.spyOn(apiClient, "getHeatmapData").mockResolvedValue(sampleHeatmapResponse);

    const store = usePrioritizationStore();
    store.zones = sampleZones;
    await store.fetchHazards();
    expect(store.activeHazards).toEqual(sampleHazardsResponse);

    const selectingZone = store.selectZone("san_salvador");
    await flushPromises();
    expect(store.selectedZoneKey).toBe("san_salvador");
    expect(store.activeHazards).toBeNull();
    expect(store.hazardLastCheckedAt).toBeNull();
    expect(store.isRefreshingHazards).toBe(true);

    resolveHazards({
      ...sampleHazardsResponse,
      zone_name: "San Salvador",
      latitude: 13.6929,
      longitude: -89.2182,
    });
    await selectingZone;
    expect(store.activeHazards?.zone_name).toBe("San Salvador");
  });
});

describe("Presentational Dashboard Components (Bilingual i18n ES/EN)", () => {
  it("renders SyncHeaderBar in Spanish by default and switches to English via toggle", async () => {
    setAppLocale("es");
    const wrapper = mount(SyncHeaderBar, {
      global: { plugins: [ElementPlus] },
      props: {
        zones: sampleZones,
        selectedZoneKey: "sonsonate",
        activeZoneName: "Sonsonate",
        kpis: sampleHeatmapResponse.kpis,
        isSyncing: false,
        customRadiusEnabled: false,
        customRadiusMeters: 3000,
        lastSyncSummary: null,
      },
    });

    expect(wrapper.text()).toContain("FirstSpot");
    expect(wrapper.text()).toContain("Sonsonate");
    expect(wrapper.text()).toContain("Sincronizar con Overpass");

    await wrapper.find('[data-testid="lang-toggle-btn"]').trigger("click");
    expect(wrapper.text()).toContain("Sync Zone with Overpass");
    setAppLocale("es");
  });

  it("renders HazardTelemetryStrip with live Open-Meteo weather and USGS seismic alerts", async () => {
    setAppLocale("es");
    const wrapper = mount(HazardTelemetryStrip, {
      global: { plugins: [ElementPlus] },
      props: {
        activeHazards: sampleHazardsResponse,
        scenario: "sonsonate_earthquake_m64",
        lastCheckedAt: "2026-10-16T12:00:00Z",
      },
    });

    expect(wrapper.text()).toContain("FEEDS MULTI-AGENCIA EN VIVO");
    expect(wrapper.text()).toContain("29.2°C");
    expect(wrapper.text()).toContain("M 6.4 - 18 km SSW of Acajutla");
    expect(wrapper.get('[data-testid="hazard-feed-status"]').text()).toContain(
      "Simulacro activo",
    );
  });

  it("shows zone-scoped events, cache freshness, and refresh failures", async () => {
    const liveCachedHazards: ActiveHazardsResponse = {
      ...sampleHazardsResponse,
      scenario: "none",
      active_sources: [
        "cache://open-meteo",
        "cache://usgs-earthquakes",
        "cache://nasa-eonet",
      ],
      events: sampleHazardsResponse.events.map((event) => ({
        ...event,
        is_simulated: false,
      })),
    };
    const wrapper = mount(HazardTelemetryStrip, {
      global: { plugins: [ElementPlus] },
      props: {
        activeHazards: liveCachedHazards,
        scenario: "none",
        lastCheckedAt: "2026-10-16T12:00:00Z",
      },
    });

    expect(wrapper.text()).toContain("Filtrado por zona");
    expect(wrapper.get('[data-testid="hazard-feed-status"]').text()).toContain(
      "Caché reciente",
    );
    expect(wrapper.get('[data-testid="hazard-feed-status"]').text()).toContain(
      "consulta",
    );

    await wrapper.setProps({ refreshError: "network unavailable" });
    expect(wrapper.get('[data-testid="hazard-feed-status"]').text()).toContain(
      "No se pudo actualizar",
    );
  });

  it("renders PriorityQueuePanel with prioritized places in Spanish and English", async () => {
    setAppLocale("es");

    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: {
        places: [sampleHospital],
        selectedPlace: null,
        isLoading: false,
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Cola de Despacho Institucional");
    expect(wrapper.text()).toContain("Sonsonate Regional National Hospital");
    // "+4 en 500m" was unexplained notation; the badge now says it in words.
    expect(wrapper.get('[data-testid="row-nearby-places"]').text()).toBe(
      "4 lugares cerca",
    );
    expect(wrapper.get('[data-testid="row-nearby-places"]').attributes("title")).toContain(
      "500 metros",
    );

    setAppLocale("en");
    await flushPromises();
    expect(wrapper.text()).toContain("Institutional Dispatch Queue");
    expect(wrapper.get('[data-testid="row-nearby-places"]').text()).toBe(
      "4 places nearby",
    );
    setAppLocale("es");
  });

  it("hides the nearby badge when a place has no vulnerable neighbours", async () => {
    setAppLocale("es");
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: {
        places: [{ ...sampleHospital, nearby_places_count: 0 }],
        selectedPlace: null,
        isLoading: false,
      },
    });
    await flushPromises();

    expect(wrapper.find('[data-testid="row-nearby-places"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("encodes priority as a whole number plus a relative bar, and urgency as a level meter", async () => {
    setAppLocale("es");
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: {
        places: [
          { ...sampleHospital, id: "top", priority_score: 130.0, urgency_level: 5 },
          { ...sampleHospital, id: "half", priority_score: 65.0, urgency_level: 1 },
        ],
        selectedPlace: null,
        isLoading: false,
      },
    });
    await flushPromises();

    // The ".0" was noise and the bare figure did not discriminate between rows.
    expect(wrapper.findAll(".priority-figure").map((cell) => cell.text())).toEqual([
      "130",
      "65",
    ]);
    expect(wrapper.text()).not.toMatch(/\d\.0(?!\d)/);
    expect(
      wrapper.findAll(".priority-bar > i").map((bar) => bar.attributes("style")),
    ).toEqual([
      expect.stringContaining("width: 100%"),
      expect.stringContaining("width: 50%"),
    ]);

    const readings = wrapper.findAll('[data-testid="row-urgency"]');
    expect(readings[0].attributes("aria-label")).toBe("Crítica · 5 de 5");
    expect(readings[0].findAll(".urgency-meter > i.is-reached")).toHaveLength(5);
    expect(readings[0].text()).toBe("Crítica");
    expect(readings[1].findAll(".urgency-meter > i.is-reached")).toHaveLength(1);
    expect(readings[1].text()).toBe("Baja");
    expect(wrapper.text()).not.toMatch(/\bN[1-5]\b/);
    wrapper.unmount();
  });

  it("labels the selected place explicitly instead of relying only on row color", async () => {
    setAppLocale("es");
    const places = Array.from({ length: 12 }, (_, index) => ({
      ...sampleHospital,
      id: `${sampleHospital.id}-${index + 1}`,
      name: `Hospital prioritario ${index + 1}`,
    }));
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: {
        places,
        selectedPlace: places[11],
        isLoading: false,
      },
    });
    await flushPromises();

    // No pages to turn: all twelve places are on screen at once.
    expect(wrapper.findAll("tbody tr")).toHaveLength(12);
    const selectedRow = wrapper
      .findAll("tbody tr")
      .find((row) => row.find('[data-testid="selected-place-indicator"]').exists());
    expect(selectedRow).toBeDefined();
    expect(selectedRow!.classes()).toContain("is-selected-place-row");
    expect(wrapper.get('[data-testid="selected-place-indicator"]').text()).toContain(
      "En el mapa",
    );
    wrapper.unmount();
  });

  it("replaces pagination with one deep queue revealed in slices", async () => {
    setAppLocale("es");
    const places = Array.from({ length: 120 }, (_, index) => ({
      ...sampleHospital,
      id: `${sampleHospital.id}-${index + 1}`,
      name: `Hospital prioritario ${index + 1}`,
      priority_score: 300 - index,
    }));
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: { places, selectedPlace: null, isLoading: false },
    });
    await flushPromises();

    // Twenty-nine pages of ten became one list, bounded on first paint.
    expect(wrapper.find('[data-testid="places-pagination"]').exists()).toBe(false);
    expect(wrapper.find(".el-pagination").exists()).toBe(false);
    expect(wrapper.findAll("tbody tr")).toHaveLength(50);
    expect(wrapper.get('[data-testid="queue-count"]').text()).toContain("120");

    await wrapper.get('[data-testid="queue-reveal-more"]').trigger("click");
    await flushPromises();
    expect(wrapper.findAll("tbody tr")).toHaveLength(100);

    await wrapper.get('[data-testid="queue-reveal-more"]').trigger("click");
    await flushPromises();
    expect(wrapper.findAll("tbody tr")).toHaveLength(120);
    expect(wrapper.find('[data-testid="queue-reveal-more"]').exists()).toBe(false);

    // Rank is the position in the whole queue, which is what gets said aloud.
    expect(wrapper.findAll(".rank-badge").at(119)!.text()).toBe("120");
    wrapper.unmount();
  });

  it("reveals the next slice when the operator scrolls toward the bottom", async () => {
    setAppLocale("es");
    const places = Array.from({ length: 120 }, (_, index) => ({
      ...sampleHospital,
      id: `${sampleHospital.id}-${index + 1}`,
      name: `Hospital prioritario ${index + 1}`,
    }));
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
      props: { places, selectedPlace: null, isLoading: false },
    });
    await flushPromises();

    // The scroll host is reached by class name, so the coupling is asserted.
    const scrollHost = wrapper.element.querySelector(
      ".el-table__body-wrapper .el-scrollbar__wrap",
    );
    expect(scrollHost).not.toBeNull();
    expect(wrapper.findAll("tbody tr")).toHaveLength(50);

    scrollHost!.dispatchEvent(new Event("scroll"));
    await flushPromises();
    expect(wrapper.findAll("tbody tr")).toHaveLength(100);
    wrapper.unmount();
  });

  it("keeps a selected place on screen even past the revealed slice", async () => {
    setAppLocale("es");
    const places = Array.from({ length: 120 }, (_, index) => ({
      ...sampleHospital,
      id: `${sampleHospital.id}-${index + 1}`,
      name: `Hospital prioritario ${index + 1}`,
    }));
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: { places, selectedPlace: places[99], isLoading: false },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Hospital prioritario 100");
    expect(wrapper.find('[data-testid="selected-place-indicator"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it("narrows the queue in place instead of making the operator page for it", async () => {
    setAppLocale("es");
    const places = [
      { ...sampleHospital, id: "q-1", name: "Hospital Nacional de Sonsonate" },
      {
        ...sampleHospital,
        id: "q-2",
        name: "Clínica Comunal Acajutla",
        category: "clinic" as const,
      },
      { ...sampleHospital, id: "q-3", name: "Centro Escolar Izalco", category: "school" as const },
    ];
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: { places, selectedPlace: null, isLoading: false },
    });
    await flushPromises();

    // Accent-insensitive, so a radio spelling still finds the place.
    await wrapper.get('[data-testid="queue-filter-input"]').setValue("clinica");
    await flushPromises();
    expect(wrapper.findAll("tbody tr")).toHaveLength(1);
    expect(wrapper.text()).toContain("Clínica Comunal Acajutla");
    expect(wrapper.get('[data-testid="queue-count"]').text()).toContain("1 de 3");

    await wrapper.get('[data-testid="queue-filter-input"]').setValue("maternidad");
    await flushPromises();
    expect(wrapper.findAll("tbody tr")).toHaveLength(0);
    expect(wrapper.text()).toContain("Ningún lugar de la cola coincide");

    await wrapper.get('[data-testid="queue-filter-clear"]').trigger("click");
    await flushPromises();
    expect(wrapper.findAll("tbody tr")).toHaveLength(3);
    wrapper.unmount();
  });

  it("shows queue structure while the first result set is still loading", async () => {
    setAppLocale("es");
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: { places: [], selectedPlace: null, isLoading: true },
    });
    await flushPromises();

    expect(wrapper.find('[data-testid="queue-skeleton"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="places-table"]').exists()).toBe(false);

    // A refresh keeps the previous rows visible rather than blanking the queue.
    await wrapper.setProps({ places: [sampleHospital], isLoading: true });
    await flushPromises();
    expect(wrapper.find('[data-testid="queue-skeleton"]').exists()).toBe(false);
    expect(wrapper.findAll("tbody tr")).toHaveLength(1);
    expect(wrapper.text()).toContain("Actualizando");
    wrapper.unmount();
  });

  it("renders a centered triage dialog and saves the edited evaluation", async () => {
    setAppLocale("es");
    const view = new DOMWrapper(document.body);
    const wrapper = mount(PlaceTriageDrawer, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
      props: { visible: true, place: sampleHospital, account: sampleInstitutionAccount },
    });
    await flushPromises();

    const dialog = wrapper.findComponent({ name: "ElDialog" });
    expect(dialog.props("alignCenter")).toBe(true);
    expect(dialog.props("appendToBody")).toBe(true);
    expect(dialog.props("closeOnClickModal")).toBe(false);
    expect(view.find('[data-testid="triage-drawer"]').exists()).toBe(true);
    expect(view.text()).toContain("Sonsonate Regional National Hospital");
    expect(view.text()).toContain("Google Maps");
    expect(view.text()).toContain("Waze");
    expect(view.find(".landscape-section").exists()).toBe(false);
    expect(view.get('[data-testid="priority-breakdown"]').attributes("open")).toBeUndefined();
    const initialScore = view.get('[data-testid="preview-priority-score"]').text();

    await view.get('input[value="in_progress"]').setValue();
    await view.findAll("button").find((button) => button.text() === "+25")!.trigger("click");
    await view.get('[data-testid="triage-notes-input"]').setValue("Brigada asignada");
    expect(view.get('[data-testid="preview-priority-score"]').text()).not.toBe(initialScore);
    await view.get('[data-testid="save-triage-btn"]').trigger("click");
    expect(wrapper.emitted("save-triage")?.[0]).toEqual([
      sampleHospital.id,
      {
        attention_status: "in_progress",
        activity_type: "update",
        urgency_level: sampleHospital.urgency_level,
        estimated_vulnerable_count: sampleHospital.estimated_vulnerable_count + 25,
        institution_notes: "Brigada asignada",
      },
    ]);
    wrapper.unmount();
  });

  it("discards unsaved edits when reopened and supports cancel and English labels", async () => {
    setAppLocale("en");
    const view = new DOMWrapper(document.body);
    const wrapper = mount(PlaceTriageDrawer, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
      props: { visible: true, place: sampleHospital },
    });
    await flushPromises();
    expect(view.text()).toContain("Assessment & dispatch");
    await view.get('[data-testid="triage-notes-input"]').setValue("Unsaved note");
    await view.findAll("button").find((button) => button.text() === "Cancel")!.trigger("click");
    expect(wrapper.emitted("update:visible")?.[0]).toEqual([false]);
    expect(wrapper.emitted("save-triage")).toBeUndefined();
    await wrapper.setProps({ visible: false });
    await flushPromises();
    await wrapper.setProps({ visible: true });
    await flushPromises();
    expect((view.get('[data-testid="triage-notes-input"]').element as HTMLTextAreaElement).value).toBe(sampleHospital.institution_notes ?? "");
    wrapper.unmount();
    setAppLocale("es");
  });

  it("shows public activity attribution and routes anonymous users to institutional access", async () => {
    setAppLocale("es");
    const activity: PlaceActivityRead = {
      id: "cccccccc-dddd-eeee-ffff-000000000000",
      place_id: sampleHospital.id,
      activity_type: "on_scene",
      attention_status: "in_progress",
      urgency_level: 4,
      estimated_vulnerable_count: 12,
      notes: "Unidad en el lugar evaluando daños",
      actor_name: "Ana Respuesta",
      organization: {
        id: sampleInstitutionAccount.institution.id,
        name: sampleInstitutionAccount.institution.name,
        country: "El Salvador",
        sector: "Bomberos",
        verification_status: "verified",
      },
      created_at: "2026-10-16T12:30:00Z",
    };
    const view = new DOMWrapper(document.body);
    const verified = mount(PlaceTriageDrawer, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
      props: {
        visible: true,
        place: sampleHospital,
        account: sampleInstitutionAccount,
        activities: [activity],
      },
    });
    await flushPromises();
    expect(view.text()).toContain("Bitácora de coordinación");
    expect(view.text()).toContain("Bomberos de Sonsonate");
    expect(view.text()).toContain("Ana Respuesta");
    expect(view.text()).toContain("Unidad en el lugar evaluando daños");
    verified.unmount();

    const anonymous = mount(PlaceTriageDrawer, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
      props: { visible: true, place: sampleHospital },
    });
    await flushPromises();
    const anonymousView = new DOMWrapper(document.body);
    expect(anonymousView.find('[data-testid="institution-access-btn"]').exists()).toBe(true);
    await anonymousView.find('[data-testid="institution-access-btn"]').trigger("click");
    expect(anonymous.emitted("request-access")).toHaveLength(1);
    anonymous.unmount();
    setAppLocale("es");
  });

  it("supports dark and light mode theme toggling via useTheme composable", () => {
    const { isDark, toggleTheme, setTheme } = useTheme();

    setTheme("dark");
    expect(isDark.value).toBe(true);

    toggleTheme();
    expect(isDark.value).toBe(false);

    toggleTheme();
    expect(isDark.value).toBe(true);
  });

  it("renders the map canvas without duplicating ribbon layer controls", async () => {
    setAppLocale("es");
    const wrapper = mount(VulnerabilityHeatmapCanvas, {
      global: { plugins: [ElementPlus] },
      props: {
        places: [sampleHospital],
        heatmapPoints: sampleHeatmapResponse.points,
        selectedPlace: sampleHospital,
        currentZone: sampleZones[0],
        customRadiusEnabled: false,
        customRadiusMeters: 3000,
        hazardEvents: sampleHazardsResponse.events,
      },
    });
    await flushPromises();

    expect(wrapper.find('[data-testid="map-panel"]').exists()).toBe(true);
    expect(wrapper.find(".map-layer-toggles").exists()).toBe(false);
    expect(wrapper.find('[data-testid="map-legend"]').exists()).toBe(true);
    expect(wrapper.find(".tactical-map-pin.tactical-pin-selected").exists()).toBe(true);
    expect(wrapper.find(".leaflet-tooltip.selected-place-tooltip").text()).toContain(
      "LUGAR SELECCIONADO",
    );
  });
});

