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
  it("exposes OpenAPI 3.1 version and all 7 backend operationIds", () => {
    expect(OPENAPI_VERSION).toMatch(/^3\.1/);
    expect([...OPENAPI_OPERATION_IDS]).toEqual([
      "getHealthStatus",
      "getHeatmapData",
      "getPlaceById",
      "listPredefinedZones",
      "listPrioritizedPlaces",
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

    expect(wrapper.text()).toContain("Geo-Prioridad Vulnerable");
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
    setActivePinia(createPinia());
    setAppLocale("es");
    const store = usePrioritizationStore();

    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: {
        places: [sampleHospital],
        selectedPlace: null,
        filters: store.filters,
        isLoading: false,
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Cola de Despacho Institucional");
    expect(wrapper.text()).toContain("Sonsonate Regional National Hospital");
    expect(wrapper.text()).toContain("+4 en 500m");

    setAppLocale("en");
    await flushPromises();
    expect(wrapper.text()).toContain("Institutional Dispatch Queue");
    expect(wrapper.text()).toContain("+4 in 500m");
    setAppLocale("es");
  });

  it("renders a centered triage dialog and saves the edited evaluation", async () => {
    setAppLocale("es");
    const view = new DOMWrapper(document.body);
    const wrapper = mount(PlaceTriageDrawer, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
      props: { visible: true, place: sampleHospital },
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

  it("supports dark and light mode theme toggling via useTheme composable", () => {
    const { isDark, toggleTheme, setTheme } = useTheme();

    setTheme("dark");
    expect(isDark.value).toBe(true);

    toggleTheme();
    expect(isDark.value).toBe(false);

    toggleTheme();
    expect(isDark.value).toBe(true);
  });

  it("renders VulnerabilityHeatmapCanvas with layer toggles including hazards and map panel", async () => {
    setAppLocale("es");
    const wrapper = mount(VulnerabilityHeatmapCanvas, {
      global: { plugins: [ElementPlus] },
      props: {
        places: [sampleHospital],
        heatmapPoints: sampleHeatmapResponse.points,
        selectedPlace: null,
        currentZone: sampleZones[0],
        customRadiusEnabled: false,
        customRadiusMeters: 3000,
        hazardEvents: sampleHazardsResponse.events,
      },
    });
    await flushPromises();

    expect(wrapper.find('[data-testid="map-panel"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("Mapa de Calor");
    expect(wrapper.text()).toContain("Marcadores Tácticos");
    expect(wrapper.text()).toContain("Amenazas y Desastres");
    expect(wrapper.find('[data-testid="map-legend"]').exists()).toBe(true);
  });
});

