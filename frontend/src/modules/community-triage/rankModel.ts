import type { DistrictPrioRead } from "../../api/client";
import type { AppLocale } from "../../i18n/useI18n";
import {
  ALERT_CLASS_ORDER,
  DIMENSION_ORDER,
  asAlertClass,
  asDimensionKey,
  type AlertClassKey,
  type DimensionKey,
} from "./triageModel";

export type SortKey = "score" | "exposed" | "name";

export interface RankFilter {
  /** Two-digit department prefix, or null for the whole country. */
  departmentPrefix: string | null;
  classFilter: AlertClassKey | null;
  search: string;
}

export interface ClassGroup {
  key: AlertClassKey | "withheld";
  districts: DistrictPrioRead[];
}

/** Accent- and case-insensitive comparison key, so "canton" finds "Cantón". */
export function searchKey(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

export function filterDistricts(
  districts: readonly DistrictPrioRead[],
  filter: RankFilter,
): DistrictPrioRead[] {
  const needle = searchKey(filter.search.trim());
  return districts.filter((d) => {
    if (filter.departmentPrefix && !d.district_code.startsWith(filter.departmentPrefix)) {
      return false;
    }
    if (filter.classFilter && (d.withheld || asAlertClass(d.alert_class) !== filter.classFilter)) {
      return false;
    }
    return needle.length === 0 || searchKey(d.district_name).includes(needle);
  });
}

const collator = (locale: AppLocale) => new Intl.Collator(locale === "es" ? "es-SV" : "en-US");

/** Withheld districts sink in the figure-based sorts: they have no figure to rank by. */
export function sortDistricts(
  districts: readonly DistrictPrioRead[],
  key: SortKey,
  locale: AppLocale,
): DistrictPrioRead[] {
  const byName = collator(locale);
  const list = [...districts];
  if (key === "name") return list.sort((a, b) => byName.compare(a.district_name, b.district_name));

  const figure = (d: DistrictPrioRead): number | null => {
    if (d.withheld) return null;
    return key === "score" ? (d.rank !== null ? -d.rank : null) : d.estimated_exposed_population;
  };
  return list.sort((a, b) => {
    const fa = figure(a);
    const fb = figure(b);
    if (fa === null && fb === null) return byName.compare(a.district_name, b.district_name);
    if (fa === null) return 1;
    if (fb === null) return -1;
    return fb - fa || byName.compare(a.district_name, b.district_name);
  });
}

/** Most urgent class first; withheld districts form a last group of their own. */
export function groupByClass(districts: readonly DistrictPrioRead[]): ClassGroup[] {
  const groups: ClassGroup[] = [];
  for (const key of ALERT_CLASS_ORDER) {
    const members = districts.filter((d) => !d.withheld && asAlertClass(d.alert_class) === key);
    if (members.length) groups.push({ key, districts: members });
  }
  const withheld = districts.filter((d) => d.withheld);
  if (withheld.length) groups.push({ key: "withheld", districts: withheld });
  return groups;
}

export interface DimensionScore {
  key: DimensionKey;
  /** Null when the dimension is withheld or has no score; never 0 by default. */
  score: number | null;
}

/** The dimensions a district has in this mode, always in the same order. */
export function dimensionScores(district: DistrictPrioRead): DimensionScore[] {
  if (district.withheld) return [];
  const byKey = new Map(
    district.dimensions.map((d) => [asDimensionKey(d.dimension), d] as const),
  );
  return DIMENSION_ORDER.filter((key) => byKey.has(key)).map((key) => {
    const d = byKey.get(key)!;
    return { key, score: d.withheld_reason ? null : d.score };
  });
}
