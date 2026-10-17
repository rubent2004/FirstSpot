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

export const CATEGORY_LABELS: Record<PlaceCategory, string> = {
  hospital: "Hospital",
  clinic: "Medical Clinic",
  social_facility: "Social Facility / Shelter",
  kindergarten: "Kindergarten",
  school: "School",
  community_centre: "Community Center",
  university: "University",
  pharmacy: "Pharmacy",
  commercial_hub: "Commercial Hub / Market",
  place_of_worship: "Place of Worship",
};

export const GROUP_LABELS: Record<VulnerabilityGroup, string> = {
  health: "Critical Health",
  education: "Education & Children",
  shelter: "Shelters & Care",
  concurrency: "High Concurrency",
};

export const GROUP_COLORS: Record<VulnerabilityGroup, string> = {
  health: "#ef4444",
  shelter: "#f97316",
  education: "#eab308",
  concurrency: "#3b82f6",
};

export const STATUS_LABELS: Record<AttentionStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  attended: "Attended",
};

export const URGENCY_LABELS: Record<number, string> = {
  1: "1 - Low (0.6x)",
  2: "2 - Moderate (0.8x)",
  3: "3 - Standard (1.0x)",
  4: "4 - High (1.3x)",
  5: "5 - Critical (1.6x)",
};

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
};
