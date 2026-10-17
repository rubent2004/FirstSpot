import type { AttentionStatus, PlaceRead } from "../../../api/client";
import type { MapPrintMessages } from "../../../i18n/communityMapPrintMessages";
import { describePlaceName, type AppLocale, type I18nMessages } from "../../../i18n/useI18n";
import { exposedPopulationState } from "../../priority-queue/populationExposure";
import type { PlaceColumn } from "./mapPrintModel";

/** Estimated residents, or the plain reason there is no figure. Never 0 for "unknown". */
export function exposureText(place: PlaceRead, m: MapPrintMessages, locale: AppLocale): string {
  const state = exposedPopulationState(place);
  if (state.kind === "estimate") {
    return Math.round(state.value).toLocaleString(locale === "es" ? "es-SV" : "en-US");
  }
  return state.kind === "withheld" ? m.exposure.withheld : m.exposure.noCoverage;
}

export interface PlacesTable {
  rows: Array<{ name: string; cells: Partial<Record<PlaceColumn, string>> }>;
  columns: PlaceColumn[];
}

/** The first N places by priority, named the way a dispatcher would say them. */
export function placesTable(
  places: readonly PlaceRead[],
  options: { topN: number; columns: readonly PlaceColumn[] },
  ui: I18nMessages,
  locale: AppLocale,
  m?: MapPrintMessages,
): PlacesTable {
  const sorted = [...places].sort(
    (a, b) => b.priority_score - a.priority_score || b.urgency_level - a.urgency_level,
  );
  const rows = sorted.slice(0, options.topN).map((place) => {
    const cells: Partial<Record<PlaceColumn, string>> = {};
    if (options.columns.includes("category")) cells.category = ui.categories[place.category];
    if (options.columns.includes("urgency")) {
      cells.urgency = ui.urgency[place.urgency_level] ?? String(place.urgency_level);
    }
    if (options.columns.includes("population") && m) cells.population = exposureText(place, m, locale);
    if (options.columns.includes("status")) cells.status = ui.statuses[place.attention_status];
    if (options.columns.includes("nearby")) cells.nearby = String(place.nearby_places_count ?? 0);
    return { name: describePlaceName(place, locale).label, cells };
  });
  return { rows, columns: [...options.columns] };
}

export function countsByUrgency(places: readonly PlaceRead[]): Record<number, number> {
  const counts: Record<number, number> = { 5: 0, 4: 0, 3: 0, 2: 0, 1: 0 };
  for (const place of places) counts[place.urgency_level] = (counts[place.urgency_level] ?? 0) + 1;
  return counts;
}

export function countsByStatus(places: readonly PlaceRead[]): Record<AttentionStatus, number> {
  const counts: Record<AttentionStatus, number> = { pending: 0, in_progress: 0, attended: 0 };
  for (const place of places) counts[place.attention_status] += 1;
  return counts;
}
