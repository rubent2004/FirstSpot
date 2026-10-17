// AUTO-GENERATED FROM ../backend/openapi.json — DO NOT EDIT MANUALLY
export const OPENAPI_VERSION = "3.1.0" as const;

export interface ActivityOrganizationRead {
  id: string;
  name: string;
  country: string;
  sector: string;
  verification_status: string;
}

export interface AlertClassRead {
  alert_class: string;
  floor: number;
  ceiling: number;
  inform_class: string;
  meaning: string;
}

export type AttentionStatus = "pending" | "in_progress" | "attended";

export interface CopingMethodologyRead {
  dimension: string;
  method: string;
  percentile_formula: string;
  tie_rule: string;
  aggregation_rule: string;
  population_weighting_rule: string;
  unit_of_analysis: string;
  interpretation: string;
  uses_principal_components?: boolean;
  uses_network_routing?: boolean;
  scored_unit_count: number;
  withheld_unit_count: number;
  scored_sub_dimension_count: number;
  declared_gap_sub_dimension_count: number;
  access_threshold_metres: number;
  suppression_threshold: number;
  suppression_reference: string;
  osm_source: string;
  osm_licence: string;
}

export interface CopingRankingRead {
  districts: Array<DistrictCopingRead>;
  scored_unit_count: number;
  withheld_unit_count: number;
  methodology: CopingMethodologyRead;
  distance_basis: string;
  variables: Array<CopingVariableRead>;
  declared_gaps: Array<app__modules__prioritization__infrastructure__coping_router__DeclaredGapRead>;
  source: string;
  disclaimer: string;
  computed_at: string;
}

export interface CopingThemeRead {
  theme: string;
  variable_count: number;
  declared_gap: boolean;
  percentile_sum: number | null;
  percentile_rank: number | null;
  score: number | null;
}

export interface CopingVariableRead {
  variable: string;
  label: string;
  theme: string;
  in_index: boolean;
  exclusion_reason?: string | null;
  numerator: string;
  denominator: string;
  measure: string;
  inform_equivalent?: string | null;
  higher_is_worse: boolean;
  estimate: number | null;
  universe: number | null;
  rate: number | null;
  percentile: number | null;
  suppressed: boolean;
  suppression_reason?: string | null;
  inputs_incomplete: boolean;
  maximum_undercount: number;
}

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

export interface DimensionRead {
  dimension: string;
  score: number | null;
  rank: number | null;
  withheld_reason?: string | null;
}

export interface DistrictCopingAuditRead {
  district_code: string;
  district_name: string;
  population: number | null;
  rank: number | null;
  score: number | null;
  cdc_score: number | null;
  theme_percentile_sum: number | null;
  theme_percentile_rank: number | null;
  themes: Array<CopingThemeRead>;
  inputs_incomplete: boolean;
  withheld: boolean;
  withheld_reason?: string | null;
  variables: Array<CopingVariableRead>;
  methodology: CopingMethodologyRead;
  distance_basis: string;
  declared_gaps: Array<app__modules__prioritization__infrastructure__coping_router__DeclaredGapRead>;
  source: string;
  disclaimer: string;
  computed_at: string;
}

export interface DistrictCopingRead {
  district_code: string;
  district_name: string;
  population: number | null;
  rank: number | null;
  score: number | null;
  cdc_score: number | null;
  theme_percentile_sum: number | null;
  theme_percentile_rank: number | null;
  themes: Array<CopingThemeRead>;
  inputs_incomplete: boolean;
  withheld: boolean;
  withheld_reason?: string | null;
}

export interface DistrictHazardRead {
  district_code: string;
  district_name: string;
  population: number | null;
  rank: number | null;
  score: number;
  shaken: boolean;
  max_mmi: number | null;
  mean_mmi: number | null;
  estimated_exposed_population: number;
  themes: Record<string, number>;
  variables: Array<HazardVariableRead>;
}

export interface DistrictPrioRead {
  district_code: string;
  district_name: string;
  population: number | null;
  rank: number | null;
  score: number | null;
  inform_rescaled_score: number | null;
  alert_class: string | null;
  dimensions: Array<DimensionRead>;
  zeroed_by: Array<string>;
  zero_reason: string | null;
  withheld: boolean;
  withheld_reason: string | null;
  max_mmi: number | null;
  estimated_exposed_population: number | null;
  sphere?: SphereRead | null;
}

export interface DistrictVulnerabilityAuditRead {
  district_code: string;
  district_name: string;
  population: number | null;
  rank: number | null;
  score: number | null;
  cdc_score: number | null;
  theme_percentile_sum: number | null;
  theme_percentile_rank: number | null;
  themes: Array<VulnerabilityThemeRead>;
  inputs_incomplete: boolean;
  withheld: boolean;
  withheld_reason?: string | null;
  variables: Array<VulnerabilityVariableRead>;
  methodology: VulnerabilityMethodologyRead;
  declared_gaps: Array<app__modules__prioritization__infrastructure__router__DeclaredGapRead>;
  source: string;
  disclaimer: string;
  computed_at: string;
}

export interface DistrictVulnerabilityRead {
  district_code: string;
  district_name: string;
  population: number | null;
  rank: number | null;
  score: number | null;
  cdc_score: number | null;
  theme_percentile_sum: number | null;
  theme_percentile_rank: number | null;
  themes: Array<VulnerabilityThemeRead>;
  inputs_incomplete: boolean;
  withheld: boolean;
  withheld_reason?: string | null;
}

export interface EventCatalogueRead {
  events: Array<EventSummaryRead>;
  pager_alert_bands: Array<PagerRead>;
  declared_gaps: Array<GapRead>;
  source: string;
}

export interface EventRead {
  event_id: string;
  magnitude: number | null;
  place: string;
  latitude: number;
  longitude: number;
  depth_km: number | null;
  occurred_at: string;
  shakemap_grid_processed_at: string | null;
  shakemap_version: string | null;
  shakemap_declared_max_mmi: number | null;
  contour_max_mmi: number | null;
  contour_interval: number | null;
  pager: PagerRead | null;
}

export interface EventSummaryRead {
  event_id: string;
  magnitude: number | null;
  place: string;
  latitude: number;
  longitude: number;
  depth_km: number | null;
  occurred_at: string;
  has_shakemap: boolean;
  has_pager: boolean;
  url: string | null;
}

export interface GapRead {
  dimension: string;
  subject: string;
  reason: string;
  consequence: string;
}

export interface HazardRankingRead {
  event: EventRead;
  districts: Array<DistrictHazardRead>;
  scored_unit_count: number;
  shaken_unit_count: number;
  exposed_unit_count: number;
  total_exposed_population: number;
  method: string;
  fixed_bounds_rationale: string;
  contour_discretisation_rule: string;
  uniform_density_assumption: string;
  interpretation: string;
  uses_percentile_normalisation: boolean;
  declared_gaps: Array<GapRead>;
  casualty_reporting_prohibition: string;
  shakemap_revision_warning: string;
  source: string;
  computed_at: string;
}

export interface HazardVariableRead {
  variable: string;
  label: string;
  theme: string;
  in_index: boolean;
  measure: string;
  fixed_floor: number;
  fixed_ceiling: number;
  bound_source: string;
  estimate?: number | null;
  universe?: number | null;
  rate?: number | null;
  score?: number | null;
  exclusion_reason?: string | null;
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

export interface PagerRead {
  level: string | null;
  band_label: string | null;
  response_implication: string | null;
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

export interface PlaceExposureEstimateRead {
  radius_meters: number;
  estimated_exposed_population?: number | null;
  estimated_exposed_older_adults?: number | null;
  estimated_exposed_young_children?: number | null;
  estimated_exposed_persons_with_disability?: number | null;
  suppressed?: boolean;
  suppression_reason?: string | null;
  estimated_at?: string | null;
}

export interface PlaceExposureMethodologyRead {
  radius_meters: number;
  estimated_exposed_population?: number | null;
  estimated_exposed_older_adults?: number | null;
  estimated_exposed_young_children?: number | null;
  estimated_exposed_persons_with_disability?: number | null;
  suppressed?: boolean;
  suppression_reason?: string | null;
  estimated_at?: string | null;
  estimation_method: string;
  spatial_assignment_rule: string;
  metric_projection_srid: number;
  metric_projection_name: string;
  uniform_density_assumption: string;
  uniform_district_rate_assumption: string;
  reference_period: string;
  contributing_unit_count: number;
  census_unit_id?: number | null;
  source: string;
  disclaimer: string;
}

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
  census_unit_id?: number | null;
  population_exposure?: PlaceExposureEstimateRead | null;
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

export interface PopulationUnitAccessRead {
  unit_id: number;
  district_code: string;
  district_name: string;
  dug_level: number;
  dug_class: string;
  dug_code?: number | null;
  population: number;
  geodesic_metres_to_nearest_health: number | null;
  geodesic_metres_to_nearest_road: number | null;
  geodesic_metres_to_nearest_fire_station: number | null;
  shelter_facility_count: number;
  score: number | null;
  rank: number | null;
  withheld: boolean;
}

export interface PopulationUnitAccessResponse {
  units: Array<PopulationUnitAccessRead>;
  unit_count: number;
  distance_basis: string;
  population_weighting_rule: string;
  uniform_district_score_assumption: string;
  methodology: CopingMethodologyRead;
  source: string;
  disclaimer: string;
  computed_at: string;
}

export interface PopulationUnitVulnerabilityRead {
  unit_id: number;
  district_code: string;
  district_name: string;
  dug_level: number;
  dug_class: string;
  dug_code?: number | null;
  population: number;
  households: number;
  score: number | null;
  rank: number | null;
  withheld: boolean;
}

export interface PopulationUnitVulnerabilityResponse {
  units: Array<PopulationUnitVulnerabilityRead>;
  unit_count: number;
  unit_of_analysis: string;
  uniform_district_score_assumption: string;
  methodology: VulnerabilityMethodologyRead;
  source: string;
  disclaimer: string;
  computed_at: string;
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

export interface PrioIndexAuditRead {
  district_code: string;
  district_name: string;
  population: number | null;
  rank: number | null;
  score: number | null;
  inform_rescaled_score: number | null;
  alert_class: string | null;
  dimensions: Array<DimensionRead>;
  zeroed_by: Array<string>;
  zero_reason: string | null;
  withheld: boolean;
  withheld_reason: string | null;
  max_mmi: number | null;
  estimated_exposed_population: number | null;
  sphere?: SphereRead | null;
  mode: string;
  mode_meaning: string;
  dimension_keys: Array<string>;
  event: EventRead | null;
  methodology: PrioMethodologyRead;
  declared_gaps: Array<GapRead>;
  ecological_fallacy: string;
  modifiable_areal_unit_problem: string;
  casualty_reporting_prohibition: string;
  computed_at: string;
}

export interface PrioIndexRead {
  mode: string;
  mode_meaning: string;
  dimension_keys: Array<string>;
  event: EventRead | null;
  districts: Array<DistrictPrioRead>;
  class_distribution: Record<string, number>;
  alert_classes: Array<AlertClassRead>;
  total_exposed_population: number | null;
  methodology: PrioMethodologyRead;
  declared_gaps: Array<GapRead>;
  ecological_fallacy: string;
  modifiable_areal_unit_problem: string;
  casualty_reporting_prohibition: string;
  shakemap_revision_warning: string;
  source: string;
  computed_at: string;
}

export interface PrioMethodologyRead {
  composition_rule: string;
  rescaled_composition_exclusion: string;
  percentile_floor_zero_meaning: string;
  hazard_zero_meaning: string;
  dgpc_class_source: string;
  triage_colour_analogy: string;
  class_distribution_caveat: string;
  declared_scale: string;
  interpretation: string;
  uses_principal_components?: boolean;
  scored_unit_count: number;
  withheld_unit_count: number;
  zeroed_by_hazard_count: number;
  zeroed_by_percentile_floor_count: number;
  suppression_threshold: number;
  suppression_reference: string;
}

export interface SphereRead {
  label: string;
  exposed_population: number;
  water_litres_per_day: number;
  water_litres_per_day_extreme_heat: number;
  water_taps_minimum: number;
  water_point_maximum_distance_metres: number;
  food_kcal_per_day: number;
  shelter_area_m2: number;
  shelter_basis: string;
  population_basis: string;
  caveat: string;
  source: string;
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

export interface VulnerabilityMethodologyRead {
  dimension: string;
  method: string;
  percentile_formula: string;
  tie_rule: string;
  aggregation_rule: string;
  unit_of_analysis: string;
  interpretation: string;
  uses_principal_components?: boolean;
  scored_unit_count: number;
  withheld_unit_count: number;
  suppression_threshold: number;
  suppression_reference: string;
  reference_period: string;
}

export interface VulnerabilityRankingRead {
  districts: Array<DistrictVulnerabilityRead>;
  scored_unit_count: number;
  withheld_unit_count: number;
  methodology: VulnerabilityMethodologyRead;
  variables: Array<VulnerabilityVariableRead>;
  declared_gaps: Array<app__modules__prioritization__infrastructure__router__DeclaredGapRead>;
  source: string;
  disclaimer: string;
  computed_at: string;
}

export interface VulnerabilityThemeRead {
  theme: string;
  variable_count: number;
  percentile_sum: number | null;
  percentile_rank: number | null;
  score: number | null;
}

export interface VulnerabilityVariableRead {
  variable: string;
  label: string;
  theme: string;
  in_index: boolean;
  exclusion_reason?: string | null;
  numerator: string;
  denominator: string;
  measure: string;
  svi_equivalent?: string | null;
  higher_is_worse: boolean;
  estimate: number | null;
  universe: number | null;
  rate: number | null;
  percentile: number | null;
  suppressed: boolean;
  suppression_reason?: string | null;
  inputs_incomplete: boolean;
  maximum_undercount: number;
}

export interface app__modules__prioritization__infrastructure__coping_router__DeclaredGapRead {
  subject: string;
  reason: string;
  consequence: string;
}

export interface app__modules__prioritization__infrastructure__router__DeclaredGapRead {
  subject: string;
  reason: string;
  consequence: string;
}

export const OPENAPI_OPERATION_IDS = [
  "createInstitutionInvite",
  "createPlaceActivity",
  "getDistrictCopingCapacityAudit",
  "getDistrictPrioIndexAudit",
  "getDistrictVulnerabilityAudit",
  "getHealthStatus",
  "getHeatmapData",
  "getInstitutionAccount",
  "getPlaceById",
  "getPlacePopulationExposure",
  "joinInstitution",
  "listDistrictCopingCapacity",
  "listDistrictHazardExposure",
  "listDistrictPrioIndex",
  "listDistrictVulnerability",
  "listHazardExposureEvents",
  "listPlaceActivities",
  "listPopulationUnitCopingAccess",
  "listPopulationUnitVulnerability",
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
