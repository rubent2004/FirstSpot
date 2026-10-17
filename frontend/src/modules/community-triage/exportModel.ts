import type { PrioIndexRead, SphereRead } from "../../api/client";
import {
  DATA_ATTRIBUTION,
  fillMessage,
  type CommunityMessages,
} from "../../i18n/communityMessages";
import type { AppLocale } from "../../i18n/useI18n";
import { describePager, formatUtcTimestamp } from "./formatters";
import {
  ALERT_CLASS_ORDER,
  DIMENSION_ORDER,
  asAlertClass,
  asDimensionKey,
  type AlertClassKey,
  type DimensionKey,
} from "./triageModel";

export interface ReportRow {
  rank: number | null;
  name: string;
  classKey: AlertClassKey | null;
  score: number | null;
  dimensions: Array<{ key: DimensionKey; score: number | null }>;
  population: number | null;
  exposed: number | null;
  maxShaking: number | null;
  sphere: SphereRead | null;
  withheld: boolean;
}

export interface ReportEvent {
  place: string;
  magnitude: number | null;
  latitude: number;
  longitude: number;
  occurredLabel: string | null;
  shakemapLabel: string | null;
  pagerLabel: string | null;
}

export interface ReportClass {
  key: AlertClassKey;
  name: string;
  floor: number;
  ceiling: number;
}

/**
 * Everything an export or print view shows, built once from the loaded index.
 *
 * This is the single place where suppression is enforced for output: a
 * withheld district keeps its name and nothing else, whatever the payload
 * carried. Excel, the printed report and the printed map all read this model,
 * so no output can drift from the rule.
 */
export interface ReportModel {
  generatedAtIso: string;
  generatedAtLabel: string;
  mode: "baseline" | "event";
  modeLabel: string;
  modeMeaning: string;
  event: ReportEvent | null;
  dimensionKeys: DimensionKey[];
  classes: ReportClass[];
  limitations: string[];
  limitationsLine: string;
  attribution: string;
  total: number;
  rows: ReportRow[];
}

function limitationLines(t: CommunityMessages, total: number): string[] {
  return [
    t.honesty.ranking,
    t.honesty.noVictims,
    t.honesty.exposure,
    t.honesty.gaps,
    fillMessage(t.honesty.relative, { total }),
  ];
}

function buildRow(
  district: PrioIndexRead["districts"][number],
  dimensionKeys: DimensionKey[],
): ReportRow {
  if (district.withheld) {
    return {
      rank: null,
      name: district.district_name,
      classKey: null,
      score: null,
      dimensions: dimensionKeys.map((key) => ({ key, score: null })),
      population: null,
      exposed: null,
      maxShaking: null,
      sphere: null,
      withheld: true,
    };
  }
  const byKey = new Map(
    district.dimensions.map((d) => [asDimensionKey(d.dimension), d.score] as const),
  );
  return {
    rank: district.rank,
    name: district.district_name,
    classKey: asAlertClass(district.alert_class),
    score: district.score,
    dimensions: dimensionKeys.map((key) => ({ key, score: byKey.get(key) ?? null })),
    population: district.population,
    exposed: district.estimated_exposed_population,
    maxShaking: district.max_mmi,
    sphere: district.sphere ?? null,
    withheld: false,
  };
}

export function buildReportModel(
  index: PrioIndexRead,
  t: CommunityMessages,
  locale: AppLocale,
  now: Date = new Date(),
): ReportModel {
  const isEvent = index.mode === "event";
  const event = index.event;
  const dimensionKeys = DIMENSION_ORDER.filter((key) =>
    index.dimension_keys.includes(key),
  );
  const rows = [...index.districts]
    .map((district) => buildRow(district, dimensionKeys))
    .sort((a, b) => (a.rank ?? Infinity) - (b.rank ?? Infinity));
  const limitations = limitationLines(t, index.districts.length);
  const floors = new Map(index.alert_classes.map((c) => [c.alert_class, c]));

  return {
    generatedAtIso: now.toISOString(),
    generatedAtLabel: formatUtcTimestamp(now.toISOString()) ?? now.toISOString(),
    mode: isEvent ? "event" : "baseline",
    modeLabel: isEvent ? t.mode.event : t.mode.baseline,
    modeMeaning: isEvent ? t.mode.eventMeaning : t.mode.baselineMeaning,
    event:
      isEvent && event
        ? {
            place: event.place,
            magnitude: event.magnitude,
            latitude: event.latitude,
            longitude: event.longitude,
            occurredLabel: formatUtcTimestamp(event.occurred_at),
            shakemapLabel: formatUtcTimestamp(event.shakemap_grid_processed_at),
            pagerLabel: describePager(event.pager, t, locale),
          }
        : null,
    dimensionKeys,
    classes: ALERT_CLASS_ORDER.map((key) => ({
      key,
      name: t.classes[key].name,
      floor: floors.get(key)?.floor ?? 0,
      ceiling: floors.get(key)?.ceiling ?? 0,
    })),
    limitations,
    limitationsLine: limitations.join(" "),
    attribution: DATA_ATTRIBUTION,
    total: index.districts.length,
    rows,
  };
}
