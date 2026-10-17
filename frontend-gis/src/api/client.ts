export interface PredefinedZoneRead {
  key: string;
  name: string;
  department: string;
  country?: string;
  latitude: number;
  longitude: number;
  default_radius_meters: number;
}

export type AttentionStatus = "pending" | "dispatched" | "attended";

export interface PlaceRead {
  id: string;
  osm_id: number;
  name: string;
  category: string;
  vulnerability_group: string;
  latitude: number;
  longitude: number;
  priority_score: number | string;
  urgency_level: number;
  attention_status: AttentionStatus;
  distance_to_hazard_km?: number | null;
  zone_name: string;
  department?: string | null;
  estimated_population?: number;
  assigned_brigade?: string | null;
  triage_notes?: string | null;
  updated_at?: string;
}

export interface HeatmapPoint {
  latitude: number;
  longitude: number;
  intensity: number;
}

export interface HeatmapResponse {
  zone_name: string;
  total_points: number;
  points: HeatmapPoint[];
  matrix: {
    critical: number;
    high: number;
    medium: number;
    normal: number;
  };
  kpis: {
    total_places: number;
    pending_attention: number;
    dispatched_attention: number;
    attended_attention: number;
    avg_priority_score: number;
  };
}

export interface HazardEvent {
  id: string;
  hazard_type: string;
  title: string;
  magnitude?: number | null;
  latitude: number;
  longitude: number;
  occurred_at: string;
}

export interface LiveHazardsResponse {
  overall_alert_level: "green" | "yellow" | "orange" | "red";
  zone_hazard_bonus: number;
  scenario: string;
  events: HazardEvent[];
  weather?: {
    temperature_c: number;
    precipitation_mm: number;
    wind_gusts_kmh: number;
  };
}

export interface SyncZoneParams {
  zone_name?: string;
  latitude?: number;
  longitude?: number;
  radius_meters?: number;
}

export interface SyncSummaryResponse {
  zone_name: string;
  places_created: number;
  places_updated: number;
  total_places_in_zone: number;
}

export interface PlaceTriageUpdate {
  attention_status: AttentionStatus;
  assigned_brigade?: string | null;
  triage_notes?: string | null;
}

const BASE_URL = "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error [${response.status}]: ${errorText || response.statusText}`);
  }

  return response.json();
}

export const api = {
  async getZones(): Promise<PredefinedZoneRead[]> {
    return request<PredefinedZoneRead[]>("/api/v1/zones");
  },

  async getPrioritizedPlaces(params: {
    zone_name?: string | null;
    category?: string | null;
    vulnerability_group?: string | null;
    attention_status?: string | null;
    min_urgency?: number | null;
    search?: string | null;
  } = {}): Promise<PlaceRead[]> {
    const query = new URLSearchParams();
    if (params.zone_name) query.set("zone_name", params.zone_name);
    if (params.category) query.set("category", params.category);
    if (params.vulnerability_group) query.set("vulnerability_group", params.vulnerability_group);
    if (params.attention_status) query.set("attention_status", params.attention_status);
    if (params.min_urgency !== undefined && params.min_urgency !== null) {
      query.set("min_urgency", String(params.min_urgency));
    }
    if (params.search) query.set("search", params.search);

    const qs = query.toString();
    return request<PlaceRead[]>(`/api/v1/places/prioritized${qs ? `?${qs}` : ""}`);
  },

  async getHeatmapData(params: {
    zone_name?: string | null;
    category?: string | null;
    vulnerability_group?: string | null;
    include_attended?: boolean;
  } = {}): Promise<HeatmapResponse> {
    const query = new URLSearchParams();
    if (params.zone_name) query.set("zone_name", params.zone_name);
    if (params.category) query.set("category", params.category);
    if (params.vulnerability_group) query.set("vulnerability_group", params.vulnerability_group);
    if (params.include_attended !== undefined) query.set("include_attended", String(params.include_attended));

    const qs = query.toString();
    return request<HeatmapResponse>(`/api/v1/places/heatmap${qs ? `?${qs}` : ""}`);
  },

  async getLiveHazards(zoneKey = "sonsonate", scenario = "none"): Promise<LiveHazardsResponse> {
    const query = new URLSearchParams({ zone_key: zoneKey, scenario });
    return request<LiveHazardsResponse>(`/api/v1/hazards/live?${query.toString()}`);
  },

  async syncZone(params: SyncZoneParams): Promise<SyncSummaryResponse> {
    return request<SyncSummaryResponse>("/api/v1/places/sync", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async updateTriage(placeId: string, update: PlaceTriageUpdate): Promise<PlaceRead> {
    return request<PlaceRead>(`/api/v1/places/${placeId}/triage`, {
      method: "PATCH",
      body: JSON.stringify(update),
    });
  },
};
