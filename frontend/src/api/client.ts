import {
  getHealthStatus,
  getHeatmapData,
  getPlaceById,
  listPredefinedZones,
  listPrioritizedPlaces,
  OPENAPI_OPERATION_IDS,
  OPENAPI_VERSION,
  syncPlacesFromOverpass,
  updatePlaceTriage,
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
  updatePlaceTriage,
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
};

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

export const apiClient = {
  getHealthStatus,
  listPredefinedZones,
  syncPlacesFromOverpass,
  listPrioritizedPlaces,
  getHeatmapData,
  getPlaceById,
  updatePlaceTriage,
};
