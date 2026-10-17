import type { ActiveHazardsResponse, HazardScenarioPreset } from "../../api/client";

export type FeedStatusKey =
  | "refreshing"
  | "error"
  | "simulation"
  | "unavailable"
  | "fallback"
  | "cached"
  | "partial"
  | "live";

export interface FeedInput {
  activeHazards: ActiveHazardsResponse | null;
  scenario: HazardScenarioPreset;
  isRefreshing: boolean;
  refreshError: string | null;
}

/** How trustworthy the incoming feeds are right now, from the sources the API reports. */
export function feedStatusKey(input: FeedInput): FeedStatusKey {
  if (input.isRefreshing) return "refreshing";
  if (input.refreshError) return "error";
  if (input.scenario !== "none") return "simulation";
  const sources = input.activeHazards?.active_sources ?? [];
  if (sources.length === 0) return "unavailable";
  if (sources.some((s) => s.startsWith("fallback://") || s.startsWith("stale-cache://"))) {
    return "fallback";
  }
  if (sources.every((s) => s.startsWith("cache://"))) return "cached";
  if (sources.some((s) => s.startsWith("cache://"))) return "partial";
  return "live";
}

/**
 * The abnormal states: stale, failing, partial or a drill that could be mistaken
 * for the real thing. Only these earn permanent screen space; the normal state
 * is one chip in the status bar.
 */
export function needsAttention(key: FeedStatusKey): boolean {
  return key === "error" || key === "fallback" || key === "partial" || key === "unavailable" || key === "simulation";
}

export const FEED_LABELS = {
  es: {
    title: "Fuentes de datos",
    refreshing: "Actualizando",
    live: "Fuentes OK",
    cached: "Fuentes OK (caché)",
    partial: "Fuentes parciales",
    fallback: "Datos de respaldo",
    error: "Falla al actualizar",
    simulation: "Simulacro activo",
    unavailable: "Sin datos",
    checked: "consulta",
    hazards: "amenazas",
  },
  en: {
    title: "Data sources",
    refreshing: "Refreshing",
    live: "Feeds OK",
    cached: "Feeds OK (cached)",
    partial: "Partial feeds",
    fallback: "Fallback data",
    error: "Refresh failed",
    simulation: "Drill active",
    unavailable: "No data",
    checked: "checked",
    hazards: "hazards",
  },
} as const;
