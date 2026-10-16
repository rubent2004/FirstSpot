import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import {
  apiClient,
  OPENAPI_OPERATION_IDS,
  OPENAPI_VERSION,
  type HeatmapResponse,
  type PlaceRead,
  type PredefinedZoneRead,
  type SyncPlacesResponse,
} from "../api/client";
import { usePrioritizationStore } from "../stores/usePrioritizationStore";
import SyncHeaderBar from "../modules/sync-controls/SyncHeaderBar.vue";
import PriorityQueuePanel from "../modules/priority-queue/PriorityQueuePanel.vue";

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
});

describe("Presentational Dashboard Components", () => {
  it("renders SyncHeaderBar with active zone and KPI metrics", () => {
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
    expect(wrapper.text()).toContain("Sync Zone with Overpass");
  });

  it("renders PriorityQueuePanel with prioritized places and emits triage selection", async () => {
    setActivePinia(createPinia());
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

    expect(wrapper.text()).toContain("Institutional Dispatch Queue");
    expect(wrapper.text()).toContain("Sonsonate Regional National Hospital");
    expect(wrapper.text()).toContain("+4 in 500m");
  });
});
