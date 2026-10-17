// AUTO-GENERATED FROM ../backend/openapi.json — DO NOT EDIT MANUALLY
export const OPENAPI_VERSION = "3.1.0" as const;

export interface ActivityOrganizationRead {
  id: string;
  name: string;
  country: string;
  sector: string;
  verification_status: string;
}

export type AttentionStatus = "pending" | "in_progress" | "attended";

export interface DashboardKPIsRead {
  total_places: number;
  pending_count: number;
  in_progress_count: number;
  attended_count: number;
  critical_urgency_count: number;
  total_estimated_vulnerable: number;
  max_priority_score: number;
  counts_by_group: Record<string, number>;
  counts_by_category: Record<string, number>;
}

export interface HealthResponse {
  status?: string;
  service?: string;
  version?: string;
}

export interface HeatmapPointRead {
  id: string;
  name: string;
  category: PlaceCategory;
  vulnerability_group: VulnerabilityGroup;
  attention_status: AttentionStatus;
  latitude: number;
  longitude: number;
  priority_score: number;
  intensity: number;
}

export interface HeatmapResponse {
  points: Array<HeatmapPointRead>;
  matrix: Array<[number, number, number]>;
  kpis: DashboardKPIsRead;
}

export interface InstitutionAccountRead {
  id: string;
  display_name: string;
  email: string;
  role: "owner" | "member";
  institution: InstitutionPublicRead;
}

export interface InstitutionJoinRequest {
  invite_code: string;
  display_name: string;
  email: string;
  password: string;
}

export interface InstitutionPublicRead {
  id: string;
  name: string;
  country: string;
  sector: string;
  registration_code: string;
  verification_status: "pending" | "verified" | "rejected";
  created_at: string;
  verified_at: string | null;
}

export interface InstitutionRegistrationRead {
  registration_code: string;
  verification_status: string;
  message: string;
}

export interface InstitutionRegistrationRequest {
  name: string;
  country: string;
  sector: string;
  contact_name: string;
  email: string;
  password: string;
}

export interface InviteCreateRead {
  invite_code: string;
  expires_at: string;
  message: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type?: string;
  expires_in: number;
  account: InstitutionAccountRead;
}

export interface PlaceActivityCreate {
  activity_type?: PlaceActivityType;
  attention_status?: AttentionStatus | null;
  urgency_level?: number | null;
  estimated_vulnerable_count?: number | null;
  notes?: string | null;
}

export interface PlaceActivityRead {
  id: string;
  place_id: string;
  activity_type: PlaceActivityType;
  attention_status: AttentionStatus | null;
  urgency_level: number | null;
  estimated_vulnerable_count: number | null;
  notes: string | null;
  actor_name: string;
  organization: ActivityOrganizationRead;
  created_at: string;
}

export type PlaceActivityType = "reported" | "en_route" | "on_scene" | "needs_support" | "resource_available" | "update" | "resolved";

export type PlaceCategory = "hospital" | "clinic" | "social_facility" | "kindergarten" | "school" | "community_centre" | "university" | "pharmacy" | "commercial_hub" | "place_of_worship";

export interface PlaceRead {
  id: string;
  osm_type: string;
  osm_id: number;
  name: string;
  category: PlaceCategory;
  vulnerability_group: VulnerabilityGroup;
  zone_name: string;
  latitude: number;
  longitude: number;
  osm_tags: Record<string, unknown>;
  attention_status: AttentionStatus;
  urgency_level: number;
  estimated_vulnerable_count: number;
  institution_notes?: string | null;
  category_weight: number;
  nearby_places_count?: number;
  priority_score: number;
  last_osm_sync_at: string;
  updated_at: string;
}

export interface PlaceTriageUpdate {
  attention_status?: AttentionStatus | null;
  urgency_level?: number | null;
  estimated_vulnerable_count?: number | null;
  institution_notes?: string | null;
  activity_type?: PlaceActivityType;
}

export interface PredefinedZoneRead {
  key: string;
  name: string;
  department: string;
  country?: string;
  latitude: number;
  longitude: number;
  default_radius_meters: number;
}

export interface SyncPlacesResponse {
  zone_name: string;
  latitude: number;
  longitude: number;
  radius_meters: number;
  fetched_elements_count: number;
  synced_places_count: number;
  used_fallback: boolean;
  source_endpoint: string;
}

export interface SyncZoneRequest {
  zone_key?: string | null;
  zone_name?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  radius_meters?: number | null;
}

export interface VerificationDecision {
  registration_code: string;
  decision: "verify" | "reject";
  reviewer_note?: string | null;
}

export type VulnerabilityGroup = "health" | "education" | "shelter" | "concurrency";

export const OPENAPI_OPERATION_IDS = [
  "createInstitutionInvite",
  "createPlaceActivity",
  "getHealthStatus",
  "getHeatmapData",
  "getInstitutionAccount",
  "getPlaceById",
  "joinInstitution",
  "listPlaceActivities",
  "listPredefinedZones",
  "listPrioritizedPlaces",
  "loginInstitutionUser",
  "registerInstitution",
  "reviewInstitutionRegistration",
  "syncPlacesFromOverpass",
  "updatePlaceTriage",
] as const;

export type OpenApiOperationId = (typeof OPENAPI_OPERATION_IDS)[number];

export interface ListPrioritizedPlacesParams {
  zone_name?: string | null;
  category?: PlaceCategory | null;
  vulnerability_group?: VulnerabilityGroup | null;
  attention_status?: AttentionStatus | null;
  min_urgency?: number | null;
  search?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  radius_meters?: number | null;
  limit?: number;
}

export interface GetHeatmapDataParams {
  zone_name?: string | null;
  category?: PlaceCategory | null;
  vulnerability_group?: VulnerabilityGroup | null;
  include_attended?: boolean;
}
