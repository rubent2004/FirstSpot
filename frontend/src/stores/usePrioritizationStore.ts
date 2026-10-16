import { computed, reactive, ref } from "vue";
import { defineStore } from "pinia";
import {
  apiClient,
  type AttentionStatus,
  type DashboardKPIsRead,
  type HeatmapPointRead,
  type PlaceCategory,
  type PlaceRead,
  type PlaceTriageUpdate,
  type PredefinedZoneRead,
  type SyncPlacesResponse,
  type VulnerabilityGroup,
} from "../api/client";

export interface PlaceFilters {
  category: PlaceCategory | "";
  vulnerabilityGroup: VulnerabilityGroup | "";
  attentionStatus: AttentionStatus | "";
  minUrgency: number | null;
  search: string;
  includeAttendedInHeatmap: boolean;
}

export interface CustomRadiusState {
  enabled: boolean;
  latitude: number | null;
  longitude: number | null;
  radiusMeters: number;
}

const DEFAULT_KPIS: DashboardKPIsRead = {
  total_places: 0,
  pending_count: 0,
  in_progress_count: 0,
  attended_count: 0,
  critical_urgency_count: 0,
  total_estimated_vulnerable: 0,
  max_priority_score: 0,
  counts_by_group: {},
  counts_by_category: {},
};

export const usePrioritizationStore = defineStore("prioritization", () => {
  const zones = ref<PredefinedZoneRead[]>([]);
  const selectedZoneKey = ref<string>("sonsonate");
  const activeZoneName = ref<string>("Sonsonate");

  const places = ref<PlaceRead[]>([]);
  const heatmapPoints = ref<HeatmapPointRead[]>([]);
  const heatmapMatrix = ref<Array<[number, number, number]>>([]);
  const kpis = ref<DashboardKPIsRead>({ ...DEFAULT_KPIS });

  const selectedPlace = ref<PlaceRead | null>(null);
  const isTriageDrawerOpen = ref<boolean>(false);

  const filters = reactive<PlaceFilters>({
    category: "",
    vulnerabilityGroup: "",
    attentionStatus: "",
    minUrgency: null,
    search: "",
    includeAttendedInHeatmap: true,
  });

  const customRadiusMode = reactive<CustomRadiusState>({
    enabled: false,
    latitude: null,
    longitude: null,
    radiusMeters: 3000,
  });

  const isLoading = ref<boolean>(false);
  const isSyncing = ref<boolean>(false);
  const lastSyncSummary = ref<SyncPlacesResponse | null>(null);
  const error = ref<string | null>(null);

  const currentZone = computed<PredefinedZoneRead | undefined>(() =>
    zones.value.find((z) => z.key === selectedZoneKey.value),
  );

  async function loadZones(): Promise<void> {
    const fetchedZones = await apiClient.listPredefinedZones();
    zones.value = fetchedZones;
    const matched = fetchedZones.find((z) => z.key === selectedZoneKey.value);
    if (matched) {
      activeZoneName.value = matched.name;
    }
  }

  async function fetchPlacesAndHeatmap(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      const [placesList, heatmapResp] = await Promise.all([
        apiClient.listPrioritizedPlaces({
          zone_name: activeZoneName.value || null,
          category: filters.category || null,
          vulnerability_group: filters.vulnerabilityGroup || null,
          attention_status: filters.attentionStatus || null,
          min_urgency: filters.minUrgency,
          search: filters.search.trim() || null,
        }),
        apiClient.getHeatmapData({
          zone_name: activeZoneName.value || null,
          category: filters.category || null,
          vulnerability_group: filters.vulnerabilityGroup || null,
          include_attended: filters.includeAttendedInHeatmap,
        }),
      ]);

      places.value = placesList;
      heatmapPoints.value = heatmapResp.points;
      heatmapMatrix.value = heatmapResp.matrix;
      kpis.value = heatmapResp.kpis;

      if (selectedPlace.value) {
        const refreshed = placesList.find(
          (p) => p.id === selectedPlace.value?.id,
        );
        if (refreshed) {
          selectedPlace.value = refreshed;
        }
      }
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : "Failed to load geospatial data";
    } finally {
      isLoading.value = false;
    }
  }

  async function syncZone(zoneKey?: string): Promise<SyncPlacesResponse | null> {
    const targetKey = zoneKey ?? selectedZoneKey.value;
    selectedZoneKey.value = targetKey;
    const zoneObj = zones.value.find((z) => z.key === targetKey);
    if (zoneObj) {
      activeZoneName.value = zoneObj.name;
    }

    isSyncing.value = true;
    error.value = null;
    try {
      const summary = await apiClient.syncPlacesFromOverpass({
        zone_key: targetKey,
        zone_name: zoneObj?.name ?? activeZoneName.value,
      });
      lastSyncSummary.value = summary;
      activeZoneName.value = summary.zone_name;
      await fetchPlacesAndHeatmap();
      return summary;
    } catch (err) {
      error.value =
        err instanceof Error
          ? err.message
          : "Failed to synchronize with Overpass API";
      return null;
    } finally {
      isSyncing.value = false;
    }
  }

  async function syncCustomRadius(
    latitude: number,
    longitude: number,
    radiusMeters?: number,
  ): Promise<SyncPlacesResponse | null> {
    const effectiveRadius = radiusMeters ?? customRadiusMode.radiusMeters;
    customRadiusMode.latitude = latitude;
    customRadiusMode.longitude = longitude;
    customRadiusMode.radiusMeters = effectiveRadius;

    isSyncing.value = true;
    error.value = null;
    try {
      const customZoneLabel = `Custom (${latitude.toFixed(3)}, ${longitude.toFixed(3)})`;
      const summary = await apiClient.syncPlacesFromOverpass({
        zone_name: customZoneLabel,
        latitude,
        longitude,
        radius_meters: effectiveRadius,
      });
      lastSyncSummary.value = summary;
      activeZoneName.value = summary.zone_name;
      await fetchPlacesAndHeatmap();
      return summary;
    } catch (err) {
      error.value =
        err instanceof Error
          ? err.message
          : "Failed to synchronize custom radius with Overpass API";
      return null;
    } finally {
      isSyncing.value = false;
    }
  }

  async function initializeDashboard(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      await loadZones();
      await fetchPlacesAndHeatmap();
      if (kpis.value.total_places === 0) {
        await syncZone(selectedZoneKey.value);
      }
    } catch (err) {
      error.value =
        err instanceof Error
          ? err.message
          : "Failed to initialize geospatial dashboard";
    } finally {
      isLoading.value = false;
    }
  }

  function selectPlace(place: PlaceRead | null, openDrawer = false): void {
    selectedPlace.value = place;
    if (openDrawer && place) {
      isTriageDrawerOpen.value = true;
    }
  }

  async function savePlaceTriage(
    placeId: string,
    payload: PlaceTriageUpdate,
  ): Promise<PlaceRead | null> {
    error.value = null;
    try {
      const updated = await apiClient.updatePlaceTriage(placeId, payload);
      selectedPlace.value = updated;
      await fetchPlacesAndHeatmap();
      return updated;
    } catch (err) {
      error.value =
        err instanceof Error
          ? err.message
          : "Failed to update institutional triage";
      return null;
    }
  }

  function resetFilters(): void {
    filters.category = "";
    filters.vulnerabilityGroup = "";
    filters.attentionStatus = "";
    filters.minUrgency = null;
    filters.search = "";
    filters.includeAttendedInHeatmap = true;
  }

  return {
    zones,
    selectedZoneKey,
    activeZoneName,
    currentZone,
    places,
    heatmapPoints,
    heatmapMatrix,
    kpis,
    selectedPlace,
    isTriageDrawerOpen,
    filters,
    customRadiusMode,
    isLoading,
    isSyncing,
    lastSyncSummary,
    error,
    loadZones,
    fetchPlacesAndHeatmap,
    syncZone,
    syncCustomRadius,
    initializeDashboard,
    selectPlace,
    savePlaceTriage,
    resetFilters,
  };
});
