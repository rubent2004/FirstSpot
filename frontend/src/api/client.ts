import {
  getHealthStatus,
  getHeatmapData,
  getPlaceById,
  listPredefinedZones,
  listPrioritizedPlaces,
  OPENAPI_OPERATION_IDS,
  OPENAPI_VERSION,
  syncPlacesFromOverpass,
} from "./generated";
import type {
  AttentionStatus,
  DashboardKPIsRead,
  GetHeatmapDataParams,
  HealthResponse,
  HeatmapPointRead,
  HeatmapResponse,
  ListPrioritizedPlacesParams,
  OpenApiOperationId,
  PlaceCategory,
  PlaceExposureEstimateRead,
  PlaceRead,
  PlaceTriageUpdate,
  PredefinedZoneRead,
  SyncPlacesResponse,
  SyncZoneRequest,
  VulnerabilityGroup,
  InstitutionAccountRead,
  InstitutionJoinRequest,
  InstitutionRegistrationRead,
  InstitutionRegistrationRequest,
  InviteCreateRead,
  LoginRequest,
  LoginResponse,
  PlaceActivityRead,
  AlertClassRead,
  DimensionRead,
  DistrictPrioRead,
  EventCatalogueRead,
  EventRead,
  EventSummaryRead,
  PagerRead,
  PrioIndexAuditRead,
  PrioIndexRead,
  SphereRead,
} from "./generated";

export {
  getHealthStatus,
  getHeatmapData,
  getPlaceById,
  listPredefinedZones,
  listPrioritizedPlaces,
  OPENAPI_OPERATION_IDS,
  OPENAPI_VERSION,
  syncPlacesFromOverpass,
};

export type {
  AttentionStatus,
  DashboardKPIsRead,
  GetHeatmapDataParams,
  HealthResponse,
  HeatmapPointRead,
  HeatmapResponse,
  ListPrioritizedPlacesParams,
  OpenApiOperationId,
  PlaceCategory,
  PlaceExposureEstimateRead,
  PlaceRead,
  PlaceTriageUpdate,
  PredefinedZoneRead,
  SyncPlacesResponse,
  SyncZoneRequest,
  VulnerabilityGroup,
  InstitutionAccountRead,
  InstitutionJoinRequest,
  InstitutionRegistrationRead,
  InstitutionRegistrationRequest,
  InviteCreateRead,
  LoginRequest,
  LoginResponse,
  PlaceActivityRead,
  AlertClassRead,
  DimensionRead,
  DistrictPrioRead,
  EventCatalogueRead,
  EventRead,
  EventSummaryRead,
  PagerRead,
  PrioIndexAuditRead,
  PrioIndexRead,
  SphereRead,
};

async function requestInstitutionApi<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string } = {},
): Promise<T> {
  const baseUrl = import.meta.env?.VITE_API_BASE_URL ?? "";
  const response = await globalThis.fetch(`${baseUrl}/api/v1${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
    ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
      else if (Array.isArray(payload.detail)) {
        detail = payload.detail
          .map((item) => typeof item === "object" && item && "msg" in item ? String(item.msg) : "")
          .filter(Boolean)
          .join("; ") || detail;
      }
    } catch {
      // Keep the HTTP status when the API returns a non-JSON error.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function registerInstitution(
  body: InstitutionRegistrationRequest,
): Promise<InstitutionRegistrationRead> {
  return requestInstitutionApi("/institutions/register", { method: "POST", body });
}

export function loginInstitution(body: LoginRequest): Promise<LoginResponse> {
  return requestInstitutionApi("/institutions/login", { method: "POST", body });
}

export function joinInstitution(body: InstitutionJoinRequest): Promise<LoginResponse> {
  return requestInstitutionApi("/institutions/join", { method: "POST", body });
}

export function getInstitutionAccount(token: string): Promise<InstitutionAccountRead> {
  return requestInstitutionApi("/institutions/me", { token });
}

export function createInstitutionInvite(token: string): Promise<InviteCreateRead> {
  return requestInstitutionApi("/institutions/invites", { method: "POST", token });
}

export function listPlaceActivities(placeId: string): Promise<PlaceActivityRead[]> {
  return requestInstitutionApi(`/places/${encodeURIComponent(placeId)}/activities?limit=50`);
}

export function updatePlaceTriage(
  placeId: string,
  body: PlaceTriageUpdate,
  token: string,
): Promise<PlaceRead> {
  return requestInstitutionApi(`/places/${encodeURIComponent(placeId)}`, {
    method: "PATCH",
    body,
    token,
  });
}

function eventQuery(eventId: string | null | undefined): string {
  return eventId ? `?event_id=${encodeURIComponent(eventId)}` : "";
}

/** Ranked districts. No event id means BASELINE mode; an id means EVENT mode. */
export function getPrioIndex(eventId?: string | null): Promise<PrioIndexRead> {
  return requestInstitutionApi(
    `/prioritization/index/districts${eventQuery(eventId)}`,
  );
}

/** One district with its audit breakdown, in the same mode as the list. */
export function getPrioAudit(
  districtCode: string,
  eventId?: string | null,
): Promise<PrioIndexAuditRead> {
  return requestInstitutionApi(
    `/prioritization/index/districts/${encodeURIComponent(districtCode)}${eventQuery(eventId)}`,
  );
}

/** Recent earthquakes the operator may switch the index to. */
export function listHazardEvents(
  params: { limit?: number; minMagnitude?: number } = {},
): Promise<EventCatalogueRead> {
  const qs = new URLSearchParams();
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.minMagnitude !== undefined) {
    qs.set("min_magnitude", String(params.minMagnitude));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return requestInstitutionApi(`/prioritization/hazard-exposure/events${suffix}`);
}

/**
 * Categorical palette for vulnerability groups.
 *
 * These identify *what kind of place* this is. They must never reuse the
 * severity ramp (red / amber / green) or the operational accent (blue), or a
 * red pin becomes ambiguous between "this is a health facility" and "this is
 * critical" — two different facts an operator must not have to disambiguate.
 *
 * Four desaturated hues from opposite sides of the wheel: teal, terracotta,
 * violet and slate. Literals rather than tokens because Leaflet paints these
 * onto a canvas, which cannot resolve CSS custom properties.
 */
export const GROUP_COLORS: Record<VulnerabilityGroup, string> = {
  health: "#3f8f85",
  shelter: "#b06a4a",
  education: "#7d6fa8",
  concurrency: "#5f7a94",
};

/** Neutral fallback for an unrecognised group — never a severity colour. */
export const GROUP_COLOR_FALLBACK = "#6e7884";

export type HazardType =
  | "earthquake"
  | "severe_storm"
  | "volcano"
  | "flood"
  | "wildfire";

export type HazardAlertLevel = "green" | "yellow" | "orange" | "red";

export type HazardScenarioPreset =
  | "none"
  | "sonsonate_earthquake_m64"
  | "pacific_tropical_storm"
  | "izalco_volcanic_ash";

export interface HazardEventRead {
  id: string;
  hazard_type: HazardType;
  title: string;
  source: string;
  alert_level: HazardAlertLevel;
  latitude: number;
  longitude: number;
  radius_km: number;
  magnitude: number | null;
  depth_km: number | null;
  occurred_at: string;
  url: string | null;
  is_simulated: boolean;
}

export interface WeatherConditionRead {
  temperature_c: number;
  precipitation_mm: number;
  rain_mm: number;
  wind_speed_kmh: number;
  wind_gusts_kmh: number;
  weather_code: number;
  weather_label: string;
  alert_level: HazardAlertLevel;
  source: string;
  is_simulated: boolean;
}

export interface ActiveHazardsResponse {
  zone_name: string;
  latitude: number;
  longitude: number;
  scenario: HazardScenarioPreset;
  overall_alert_level: HazardAlertLevel;
  zone_hazard_bonus: number;
  active_sources: string[];
  weather: WeatherConditionRead;
  events: HazardEventRead[];
}

export interface GeocodeResultRead {
  display_name: string;
  latitude: number;
  longitude: number;
  place_type: string;
  importance: number;
}

export async function getActiveHazards(params?: {
  zone_key?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  scenario?: HazardScenarioPreset;
}): Promise<ActiveHazardsResponse> {
  const qs = new URLSearchParams();
  if (params?.zone_key) qs.set("zone_key", params.zone_key);
  if (params?.latitude !== undefined && params?.latitude !== null) {
    qs.set("latitude", String(params.latitude));
  }
  if (params?.longitude !== undefined && params?.longitude !== null) {
    qs.set("longitude", String(params.longitude));
  }
  if (params?.scenario) qs.set("scenario", params.scenario);

  const baseUrl = import.meta.env?.VITE_API_BASE_URL ?? "";
  const url = `${baseUrl}/api/v1/hazards/active${qs.toString() ? `?${qs.toString()}` : ""}`;
  const resp = await globalThis.fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  return (await resp.json()) as ActiveHazardsResponse;
}

export async function geocodeLocation(
  query: string,
  limit = 5,
): Promise<GeocodeResultRead[]> {
  const qs = new URLSearchParams({ q: query, limit: String(limit) });
  const baseUrl = import.meta.env?.VITE_API_BASE_URL ?? "";
  const url = `${baseUrl}/api/v1/hazards/geocode?${qs.toString()}`;
  const resp = await globalThis.fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  return (await resp.json()) as GeocodeResultRead[];
}

export const apiClient = {
  getHealthStatus,
  listPredefinedZones,
  syncPlacesFromOverpass,
  listPrioritizedPlaces,
  getHeatmapData,
  getPlaceById,
  updatePlaceTriage,
  getActiveHazards,
  geocodeLocation,
  registerInstitution,
  loginInstitution,
  joinInstitution,
  getInstitutionAccount,
  createInstitutionInvite,
  listPlaceActivities,
  getPrioIndex,
  getPrioAudit,
  listHazardEvents,
};
