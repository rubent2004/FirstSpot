import type { DistrictPrioRead, PagerRead } from "../../api/client";
import type { CommunityMessages } from "../../i18n/communityMessages";

/** The four official DGPC alert classes, most urgent first. */
export const ALERT_CLASS_ORDER = ["roja", "naranja", "amarilla", "verde"] as const;
export type AlertClassKey = (typeof ALERT_CLASS_ORDER)[number];

/** Classes for which the API publishes Sphere minimum requirements. */
export const SPHERE_CLASSES: readonly AlertClassKey[] = ["roja", "naranja"];

export function asAlertClass(value: string | null | undefined): AlertClassKey | null {
  return (ALERT_CLASS_ORDER as readonly string[]).includes(value ?? "")
    ? (value as AlertClassKey)
    : null;
}

/** The three INFORM dimensions, in the order they are always shown. */
export const DIMENSION_ORDER = [
  "hazard_and_exposure",
  "vulnerability",
  "lack_of_coping_capacity",
] as const;
export type DimensionKey = (typeof DIMENSION_ORDER)[number];

export function asDimensionKey(value: string): DimensionKey | null {
  return (DIMENSION_ORDER as readonly string[]).includes(value)
    ? (value as DimensionKey)
    : null;
}

/**
 * Which scale names the four classes. The official DGPC alert colours declare
 * an emergency, so they appear only when an event exists; baseline has no
 * emergency and uses a neutral structural-risk scale instead.
 */
export function classCarrier(mode: TriageMode, key: AlertClassKey): string {
  return mode === "event" ? `eoc-class-${key}` : `eoc-level-${key}`;
}

export function classLabels(
  t: CommunityMessages,
  mode: TriageMode,
  key: AlertClassKey,
): { name: string; meaning: string } {
  return mode === "event" ? t.classes[key] : t.levels[key];
}

export type ClassCounts = Record<AlertClassKey, number>;

/** Districts per class. A withheld district has no class and counts nowhere. */
export function classCounts(districts: readonly DistrictPrioRead[]): ClassCounts {
  const counts: ClassCounts = { roja: 0, naranja: 0, amarilla: 0, verde: 0 };
  for (const district of districts) {
    const alertClass = asAlertClass(district.alert_class);
    if (alertClass && !district.withheld) counts[alertClass] += 1;
  }
  return counts;
}

/** Dimensions that drove a composed score to zero, as known dimension keys. */
export function zeroedDimensionKeys(district: DistrictPrioRead): DimensionKey[] {
  if (district.score !== 0) return [];
  return district.zeroed_by
    .map(asDimensionKey)
    .filter((key): key is DimensionKey => key !== null);
}

export interface PagerRange {
  level: string | null;
  lower: number;
  /** Null for an open-ended band ("1000 or more"). */
  upper: number | null;
}

const PAGER_LABEL = /^\s*(\d[\d,]*)(?:\s*-\s*(\d[\d,]*))?/;

/**
 * Read the band's numeric range out of the API label.
 *
 * The range is the figure: a PAGER level shown without it invites a reader to
 * substitute a point estimate. Returns null when there is no PAGER or the
 * label carries no readable range, so the UI can say so instead of guessing.
 */
export function parsePagerRange(pager: PagerRead | null | undefined): PagerRange | null {
  if (!pager?.band_label) return null;
  const match = PAGER_LABEL.exec(pager.band_label);
  if (!match) return null;
  const lower = Number(match[1].replace(/,/g, ""));
  if (match[2] !== undefined) {
    return { level: pager.level, lower, upper: Number(match[2].replace(/,/g, "")) };
  }
  const isOpenEnded = /or more/i.test(pager.band_label);
  return { level: pager.level, lower, upper: isOpenEnded ? null : lower };
}

export function formatPagerRange(range: PagerRange, locale: "es" | "en"): string {
  const tag = locale === "es" ? "es-SV" : "en-US";
  const fmt = (n: number) => n.toLocaleString(tag);
  if (range.upper === null) {
    return locale === "es" ? `${fmt(range.lower)} o más` : `${fmt(range.lower)}+`;
  }
  if (range.upper === range.lower) return fmt(range.lower);
  return `${fmt(range.lower)}–${fmt(range.upper)}`;
}

export type TriageMode = "baseline" | "event";

/**
 * The mode to display: the loaded response's own, falling back to the request
 * only before anything has loaded.
 */
export function resolveMode(
  responseMode: string | undefined,
  requestedEventId: string | null,
): TriageMode {
  const mode = responseMode ?? (requestedEventId ? "event" : "baseline");
  return mode === "event" ? "event" : "baseline";
}
