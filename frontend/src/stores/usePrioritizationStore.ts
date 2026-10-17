import { computed, reactive, ref } from "vue";
import { defineStore } from "pinia";
import {
  apiClient,
  type ActiveHazardsResponse,
  type AttentionStatus,
  type DashboardKPIsRead,
  type HazardEventRead,
  type HazardScenarioPreset,
  type HeatmapPointRead,
  type PlaceCategory,
  type PlaceRead,
  type PlaceTriageUpdate,
  type PredefinedZoneRead,
  type SyncPlacesResponse,
  type VulnerabilityGroup,
  type WeatherConditionRead,
  type InstitutionAccountRead,
  type InstitutionJoinRequest,
  type InstitutionRegistrationRead,
  type InstitutionRegistrationRequest,
  type InviteCreateRead,
  type LoginRequest,
  type PlaceActivityRead,
} from "../api/client";

interface InstitutionSession {
  accessToken: string;
  expiresAt: number;
  account: InstitutionAccountRead;
}

function readStoredInstitutionSession(): InstitutionSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem("firstsopot.institution-session");
    if (!raw) return null;
    const session = JSON.parse(raw) as InstitutionSession;
    return session.expiresAt > Date.now() ? session : null;
  } catch {
    return null;
  }
}

function haversineKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const r = 6371.0;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function computeHazardBonusForPlace(
  latitude: number,
  longitude: number,
  events: HazardEventRead[],
  weather: WeatherConditionRead | null,
): number {
  let bonus = 0;
  const alertWeights: Record<string, number> = {
    green: 8,
    yellow: 18,
    orange: 35,
    red: 55,
  };
  for (const ev of events) {
    const distKm = haversineKm(latitude, longitude, ev.latitude, ev.longitude);
    const effRadius = Math.max(ev.radius_km, 1);
    if (distKm <= effRadius * 2.5) {
      const factor = Math.max(0, 1 - distKm / (effRadius * 2.5));
      const baseW = alertWeights[ev.alert_level] ?? 10;
      const magBoost =
        ev.magnitude !== null ? Math.max(0, (ev.magnitude - 4.0) * 6.0) : 5.0;
      bonus += (baseW + magBoost) * factor;
    }
  }
  if (weather) {
    if (weather.alert_level === "red") bonus += 22;
    else if (weather.alert_level === "orange") bonus += 12;
    else if (weather.alert_level === "yellow") bonus += 5;
  }
  return Math.round(bonus * 100) / 100;
}

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
  const institutionSession = ref<InstitutionSession | null>(readStoredInstitutionSession());
  const placeActivities = ref<PlaceActivityRead[]>([]);
  const arePlaceActivitiesLoading = ref(false);
  const placeActivityError = ref<string | null>(null);

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

  const hazardScenario = ref<HazardScenarioPreset>("none");
  const activeHazards = ref<ActiveHazardsResponse | null>(null);
  const hazardLastCheckedAt = ref<string | null>(null);
  const isRefreshingHazards = ref(false);
  const hazardRefreshError = ref<string | null>(null);
  let latestHazardRequest = 0;
  let latestPlacesRequest = 0;
  let latestActivityRequest = 0;

  const hasVerifiedInstitution = computed(
    () => institutionSession.value?.account.institution.verification_status === "verified",
  );

  function saveInstitutionSession(token: string, expiresIn: number, account: InstitutionAccountRead): void {
    institutionSession.value = {
      accessToken: token,
      expiresAt: Date.now() + expiresIn * 1000,
      account,
    };
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(
        "firstsopot.institution-session",
        JSON.stringify(institutionSession.value),
      );
    }
  }

  function logoutInstitution(): void {
    institutionSession.value = null;
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem("firstsopot.institution-session");
    }
  }

  async function restoreInstitutionSession(): Promise<void> {
    const existing = institutionSession.value;
    if (!existing) return;
    try {
      const account = await apiClient.getInstitutionAccount(existing.accessToken);
      institutionSession.value = { ...existing, account };
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (
        message.includes("Invalid or expired institutional session") ||
        message.includes("Institutional account is unavailable")
      ) {
        logoutInstitution();
      }
    }
  }

  async function loginInstitution(payload: LoginRequest): Promise<void> {
    const response = await apiClient.loginInstitution(payload);
    saveInstitutionSession(response.access_token, response.expires_in, response.account);
  }

  async function registerInstitution(
    payload: InstitutionRegistrationRequest,
  ): Promise<InstitutionRegistrationRead> {
    return apiClient.registerInstitution(payload);
  }

  async function joinInstitution(payload: InstitutionJoinRequest): Promise<void> {
    const response = await apiClient.joinInstitution(payload);
    saveInstitutionSession(response.access_token, response.expires_in, response.account);
  }

  async function createInstitutionInvite(): Promise<InviteCreateRead> {
    const session = institutionSession.value;
    if (!session) throw new Error("Inicia sesión con una institución verificada.");
    return apiClient.createInstitutionInvite(session.accessToken);
  }

  async function fetchPlaceActivities(placeId: string): Promise<void> {
    const requestId = ++latestActivityRequest;
    arePlaceActivitiesLoading.value = true;
    placeActivityError.value = null;
    try {
      const activities = await apiClient.listPlaceActivities(placeId);
      if (requestId === latestActivityRequest) placeActivities.value = activities;
    } catch (err) {
      if (requestId === latestActivityRequest) {
        placeActivityError.value = err instanceof Error ? err.message : "No se pudo cargar la bitácora.";
        placeActivities.value = [];
      }
    } finally {
      if (requestId === latestActivityRequest) arePlaceActivitiesLoading.value = false;
    }
  }

  const currentZone = computed<PredefinedZoneRead | undefined>(() =>
    zones.value.find((z) => z.key === selectedZoneKey.value),
  );

  const baseScoreMap = new Map<string, number>();

  function clearHazardsForZoneChange(): void {
    latestHazardRequest += 1;
    activeHazards.value = null;
    hazardLastCheckedAt.value = null;
    isRefreshingHazards.value = false;
    hazardRefreshError.value = null;
  }

  function setPredefinedZone(zoneKey: string): void {
    const targetKey = zoneKey || "sonsonate";
    if (targetKey !== selectedZoneKey.value || customRadiusMode.enabled) {
      clearHazardsForZoneChange();
    }
    selectedZoneKey.value = targetKey;
    customRadiusMode.enabled = false;
    const zoneObj = zones.value.find((z) => z.key === targetKey);
    if (zoneObj) {
      activeZoneName.value = zoneObj.name;
    }
  }

  function getPlaceHazardBonus(place: PlaceRead): number {
    if (!activeHazards.value) return 0;
    return computeHazardBonusForPlace(
      place.latitude,
      place.longitude,
      activeHazards.value.events,
      activeHazards.value.weather,
    );
  }

  function applyHazardBonuses(): void {
    if (places.value.length === 0) return;
    const updated = places.value.map((p) => {
      const baseScore = baseScoreMap.get(p.id) ?? Number(p.priority_score);
      baseScoreMap.set(p.id, baseScore);
      const bonus =
        p.attention_status === "attended"
          ? getPlaceHazardBonus(p) * 0.2
          : getPlaceHazardBonus(p);
      return {
        ...p,
        priority_score: Math.round((baseScore + bonus) * 100) / 100,
      };
    });
    updated.sort((a, b) => Number(b.priority_score) - Number(a.priority_score));
    places.value = updated;
  }

  async function fetchHazards(
    scenarioOverride?: HazardScenarioPreset,
  ): Promise<ActiveHazardsResponse | null> {
    if (scenarioOverride !== undefined) {
      hazardScenario.value = scenarioOverride;
    }
    const requestId = ++latestHazardRequest;
    const requestedZoneKey = selectedZoneKey.value || "sonsonate";
    const requestedScenario = hazardScenario.value;
    isRefreshingHazards.value = true;
    hazardRefreshError.value = null;
    try {
      const zoneObj = zones.value.find((z) => z.key === requestedZoneKey);
      const lat = customRadiusMode.enabled
        ? customRadiusMode.latitude
        : (zoneObj?.latitude ?? null);
      const lon = customRadiusMode.enabled
        ? customRadiusMode.longitude
        : (zoneObj?.longitude ?? null);

      const resp = await apiClient.getActiveHazards({
        zone_key: requestedZoneKey,
        latitude: lat,
        longitude: lon,
        scenario: requestedScenario,
      });
      if (
        requestId !== latestHazardRequest ||
        requestedZoneKey !== (selectedZoneKey.value || "sonsonate") ||
        requestedScenario !== hazardScenario.value
      ) {
        return resp;
      }
      activeHazards.value = resp;
      hazardLastCheckedAt.value = new Date().toISOString();
      hazardRefreshError.value = null;
      applyHazardBonuses();
      return resp;
    } catch (err) {
      if (requestId === latestHazardRequest) {
        hazardRefreshError.value =
          err instanceof Error ? err.message : "Hazard feed refresh failed";
      }
      return null;
    } finally {
      if (requestId === latestHazardRequest) {
        isRefreshingHazards.value = false;
      }
    }
  }

  async function loadZones(): Promise<void> {
    const fetchedZones = await apiClient.listPredefinedZones();
    zones.value = fetchedZones;
    const matched = fetchedZones.find((z) => z.key === selectedZoneKey.value);
    if (matched) {
      activeZoneName.value = matched.name;
    }
  }

  async function fetchPlacesAndHeatmap(): Promise<void> {
    const requestId = ++latestPlacesRequest;
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

      if (requestId !== latestPlacesRequest) return;

      for (const p of placesList) {
        baseScoreMap.set(p.id, Number(p.priority_score));
      }
      places.value = placesList;
      applyHazardBonuses();
      heatmapPoints.value = heatmapResp.points;
      heatmapMatrix.value = heatmapResp.matrix;
      kpis.value = heatmapResp.kpis;

      if (selectedPlace.value) {
        const refreshed = places.value.find(
          (p) => p.id === selectedPlace.value?.id,
        );
        if (refreshed) {
          selectedPlace.value = refreshed;
        }
      }
    } catch (err) {
      if (requestId === latestPlacesRequest) {
        error.value =
          err instanceof Error ? err.message : "Failed to load geospatial data";
      }
    } finally {
      if (requestId === latestPlacesRequest) isLoading.value = false;
    }
  }

  async function selectZone(zoneKey: string): Promise<void> {
    const targetKey = zoneKey || "sonsonate";
    setPredefinedZone(targetKey);
    await fetchPlacesAndHeatmap();
    await fetchHazards();
    if (kpis.value.total_places === 0) {
      await syncZone(targetKey);
    }
  }

  async function syncZone(zoneKey?: string): Promise<SyncPlacesResponse | null> {
    const targetKey = zoneKey ?? selectedZoneKey.value;
    setPredefinedZone(targetKey);
    const zoneObj = zones.value.find((z) => z.key === targetKey);

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
      await fetchHazards();
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
    clearHazardsForZoneChange();
    customRadiusMode.latitude = latitude;
    customRadiusMode.longitude = longitude;
    customRadiusMode.radiusMeters = effectiveRadius;
    selectedZoneKey.value = "";

    isSyncing.value = true;
    error.value = null;
    try {
      const customZoneLabel = `Radar (${latitude.toFixed(3)}, ${longitude.toFixed(3)})`;
      const summary = await apiClient.syncPlacesFromOverpass({
        zone_name: customZoneLabel,
        latitude,
        longitude,
        radius_meters: effectiveRadius,
      });
      lastSyncSummary.value = summary;
      activeZoneName.value = summary.zone_name;
      await fetchPlacesAndHeatmap();
      await fetchHazards();
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
      await restoreInstitutionSession();
      await loadZones();
      await fetchPlacesAndHeatmap();
      if (kpis.value.total_places === 0) {
        await syncZone(selectedZoneKey.value);
      } else {
        await fetchHazards();
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
    const session = institutionSession.value;
    if (!session || !hasVerifiedInstitution.value) {
      error.value = "Inicia sesión con una organización verificada para registrar una acción.";
      return null;
    }
    try {
      const updated = await apiClient.updatePlaceTriage(placeId, payload, session.accessToken);
      selectedPlace.value = updated;
      await fetchPlaceActivities(placeId);
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
    institutionSession,
    hasVerifiedInstitution,
    placeActivities,
    arePlaceActivitiesLoading,
    placeActivityError,
    hazardScenario,
    activeHazards,
    hazardLastCheckedAt,
    isRefreshingHazards,
    hazardRefreshError,
    loadZones,
    fetchPlacesAndHeatmap,
    fetchHazards,
    computeHazardBonusForPlace: getPlaceHazardBonus,
    selectZone,
    syncZone,
    syncCustomRadius,
    initializeDashboard,
    restoreInstitutionSession,
    loginInstitution,
    registerInstitution,
    joinInstitution,
    createInstitutionInvite,
    logoutInstitution,
    fetchPlaceActivities,
    selectPlace,
    savePlaceTriage,
    resetFilters,
  };
});

