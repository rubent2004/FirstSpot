import { defineStore } from "pinia";
import { ref, computed } from "vue";
import {
  api,
  type PredefinedZoneRead,
  type PlaceRead,
  type HeatmapPoint,
  type LiveHazardsResponse,
  type AttentionStatus,
} from "../api/client";

export const useGisStore = defineStore("gis", () => {
  // Ribbon & UI layout state
  const activeRibbonTab = ref<string>("Home");
  const isRibbonMinimized = ref<boolean>(false);
  const isLayersOpen = ref<boolean>(true);
  const isSymbologyOpen = ref<boolean>(true);
  const isTableOpen = ref<boolean>(true);
  const isAIAssistantOpen = ref<boolean>(false);
  const isCommandPaletteOpen = ref<boolean>(false);
  const isDark = ref<boolean>(false);

  // Map & GIS state
  const activeMapTab = ref<"map" | "matrix" | "ai">("map");
  const cursorCoords = ref<{ lat: number; lng: number }>({ lat: 13.7222, lng: -89.7236 });
  const mapZoom = ref<number>(13);
  const mapScale = ref<string>("1:25,000");

  // Layers & styling
  const layerVisibility = ref({
    points: true,
    heatmap: true,
    hazards: true,
    radar: true,
  });
  const basemap = ref<"carto-light" | "osm" | "carto-dark">("carto-light");
  const layerOpacity = ref<number>(100);
  const symbologyMethod = ref<"graduated" | "unique" | "single">("graduated");
  const symbologyField = ref<string>("priority_score");

  // Zones & Selection
  const zones = ref<PredefinedZoneRead[]>([]);
  const selectedZoneKey = ref<string>("sonsonate");
  const activeZoneName = ref<string>("Sonsonate");

  // Filter state
  const filters = ref({
    category: "",
    vulnerabilityGroup: "",
    attentionStatus: "",
    minUrgency: null as number | null,
    search: "",
  });

  // Data
  const places = ref<PlaceRead[]>([]);
  const heatmapPoints = ref<HeatmapPoint[]>([]);
  const heatmapMatrix = ref({
    critical: 0,
    high: 0,
    medium: 0,
    normal: 0,
  });
  const kpis = ref({
    total_places: 0,
    pending_attention: 0,
    dispatched_attention: 0,
    attended_attention: 0,
    avg_priority_score: 0,
  });

  // Hazards & Scenario Drills
  const scenario = ref<string>("none");
  const hazards = ref<LiveHazardsResponse | null>(null);

  // Selection
  const selectedPlaceId = ref<string | null>(null);

  // Loading & Syncing
  const isLoading = ref<boolean>(false);
  const isSyncing = ref<boolean>(false);
  const error = ref<string | null>(null);

  // Computeds
  const activeZone = computed(() => {
    return zones.value.find((z) => z.key === selectedZoneKey.value) ?? null;
  });

  const selectedPlace = computed(() => {
    if (!selectedPlaceId.value) return null;
    return places.value.find((p) => p.id === selectedPlaceId.value) ?? null;
  });

  const groupedZones = computed(() => {
    const map = new Map<string, PredefinedZoneRead[]>();
    for (const z of zones.value) {
      const country = z.country || "El Salvador";
      if (!map.has(country)) {
        map.set(country, []);
      }
      map.get(country)!.push(z);
    }
    return Array.from(map.entries()).map(([country, list]) => ({
      country,
      zones: list,
    }));
  });

  const filteredPlaces = computed(() => {
    return places.value.filter((p) => {
      if (filters.value.category && p.category !== filters.value.category) {
        return false;
      }
      if (filters.value.vulnerabilityGroup && p.vulnerability_group !== filters.value.vulnerabilityGroup) {
        return false;
      }
      if (filters.value.attentionStatus && p.attention_status !== filters.value.attentionStatus) {
        return false;
      }
      if (filters.value.minUrgency !== null && p.urgency_level < filters.value.minUrgency) {
        return false;
      }
      if (filters.value.search) {
        const query = filters.value.search.toLowerCase();
        const matchName = p.name.toLowerCase().includes(query);
        const matchCat = p.category.toLowerCase().includes(query);
        const matchVuln = p.vulnerability_group.toLowerCase().includes(query);
        if (!matchName && !matchCat && !matchVuln) return false;
      }
      return true;
    });
  });

  // Actions
  async function loadZones(): Promise<void> {
    try {
      zones.value = await api.getZones();
      const current = zones.value.find((z) => z.key === selectedZoneKey.value);
      if (current) {
        activeZoneName.value = current.name;
      }
    } catch (err) {
      console.error("Failed to load zones:", err);
    }
  }

  async function fetchPlacesAndHeatmap(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      const [placesList, heatmapData] = await Promise.all([
        api.getPrioritizedPlaces({
          zone_name: activeZoneName.value || null,
          category: filters.value.category || null,
          vulnerability_group: filters.value.vulnerabilityGroup || null,
          attention_status: filters.value.attentionStatus || null,
          min_urgency: filters.value.minUrgency,
          search: filters.value.search || null,
        }),
        api.getHeatmapData({
          zone_name: activeZoneName.value || null,
          category: filters.value.category || null,
          vulnerability_group: filters.value.vulnerabilityGroup || null,
          include_attended: true,
        }),
      ]);

      places.value = placesList;
      heatmapPoints.value = heatmapData.points;
      heatmapMatrix.value = heatmapData.matrix;
      kpis.value = heatmapData.kpis;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al cargar datos geoespaciales";
    } finally {
      isLoading.value = false;
    }
  }

  async function fetchHazards(): Promise<void> {
    try {
      hazards.value = await api.getLiveHazards(selectedZoneKey.value, scenario.value);
    } catch (err) {
      console.warn("Hazard feed update failed:", err);
    }
  }

  async function selectZone(zoneKey: string): Promise<void> {
    selectedZoneKey.value = zoneKey;
    const match = zones.value.find((z) => z.key === zoneKey);
    if (match) {
      activeZoneName.value = match.name;
      cursorCoords.value = { lat: match.latitude, lng: match.longitude };
    }
    await fetchPlacesAndHeatmap();
    await fetchHazards();
  }

  async function syncCurrentZone(): Promise<void> {
    const zone = activeZone.value;
    if (!zone) return;
    isSyncing.value = true;
    error.value = null;
    try {
      await api.syncZone({
        zone_name: zone.name,
        latitude: zone.latitude,
        longitude: zone.longitude,
        radius_meters: zone.default_radius_meters,
      });
      await fetchPlacesAndHeatmap();
      await fetchHazards();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al sincronizar con Overpass";
    } finally {
      isSyncing.value = false;
    }
  }

  async function changeScenario(newScenario: string): Promise<void> {
    scenario.value = newScenario;
    await fetchHazards();
  }

  async function updatePlaceTriage(placeId: string, status: AttentionStatus, brigade?: string, notes?: string): Promise<void> {
    try {
      const updated = await api.updateTriage(placeId, {
        attention_status: status,
        assigned_brigade: brigade,
        triage_notes: notes,
      });
      const idx = places.value.findIndex((p) => p.id === placeId);
      if (idx !== -1) {
        places.value[idx] = updated;
      }
      await fetchPlacesAndHeatmap();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Error al actualizar triaje";
    }
  }

  function toggleDark(): void {
    isDark.value = !isDark.value;
    if (isDark.value) {
      document.documentElement.classList.add("dark-theme");
      basemap.value = "carto-dark";
    } else {
      document.documentElement.classList.remove("dark-theme");
      basemap.value = "carto-light";
    }
  }

  async function initialize(): Promise<void> {
    await loadZones();
    await fetchPlacesAndHeatmap();
    if (kpis.value.total_places === 0) {
      await syncCurrentZone();
    } else {
      await fetchHazards();
    }
  }

  return {
    activeRibbonTab,
    isRibbonMinimized,
    isLayersOpen,
    isSymbologyOpen,
    isTableOpen,
    isAIAssistantOpen,
    isCommandPaletteOpen,
    isDark,
    activeMapTab,
    cursorCoords,
    mapZoom,
    mapScale,
    layerVisibility,
    basemap,
    layerOpacity,
    symbologyMethod,
    symbologyField,
    zones,
    selectedZoneKey,
    activeZoneName,
    filters,
    places,
    filteredPlaces,
    heatmapPoints,
    heatmapMatrix,
    kpis,
    scenario,
    hazards,
    selectedPlaceId,
    selectedPlace,
    isLoading,
    isSyncing,
    error,
    activeZone,
    groupedZones,
    loadZones,
    fetchPlacesAndHeatmap,
    fetchHazards,
    selectZone,
    syncCurrentZone,
    changeScenario,
    updatePlaceTriage,
    toggleDark,
    initialize,
  };
});
