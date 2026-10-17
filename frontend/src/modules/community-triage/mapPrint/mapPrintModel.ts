import type { DistrictPrioRead } from "../../../api/client";
import type { MapPrintMessages } from "../../../i18n/communityMapPrintMessages";
import { exposedPopulationState } from "../../priority-queue/populationExposure";
import type { BasemapPresetId } from "../../map-viewer/composables/useLeafletMap";
import type { MapSnapshot } from "./mapSnapshot";

/**
 * The content model of the "map of the current view" printout: which sections
 * exist, which ones have data right now, the presets, and what is remembered.
 * Pure, so the rules are tested without a dialog or a map.
 */

/** In the order a responder reads them: map, places, counts, hazards, contacts, notes, limits. */
export const SECTION_ORDER = [
  "map",
  "places",
  "placeDetail",
  "counts",
  "districtDetail",
  "hazards",
  "weather",
  "contacts",
  "notes",
  "limits",
] as const;
export type SectionId = (typeof SECTION_ORDER)[number];

export type PresetId = "summary" | "complete" | "dispatch";

export const PLACE_COLUMNS = ["category", "urgency", "population", "status", "nearby"] as const;
export type PlaceColumn = (typeof PLACE_COLUMNS)[number];

export interface SectionState {
  available: boolean;
  /** Why it is off, shown next to it; null when available. */
  reason: string | null;
  /** On and not removable: the map and the limits block. */
  locked: boolean;
}

export type Availability = Record<SectionId | "placePopulation", SectionState>;

/** Paper wants a light ground: a dark basemap would print as a black slab. */
export function printBasemap(live: BasemapPresetId): BasemapPresetId {
  return live === "grayDark" ? "grayLight" : live;
}

// ---- coverage ----

/** El Salvador's extent. The census and the district index stop at the border. */
const EL_SALVADOR = { south: 13.15, north: 14.45, west: -90.13, east: -87.68 };

/**
 * Whether the view is centred inside El Salvador. Outside it there is no census
 * and no district index, so no population estimate may be printed for the area.
 */
export function coverageOf(center: readonly [number, number]): "in" | "out" {
  const [lat, lon] = center;
  const inside =
    lat >= EL_SALVADOR.south &&
    lat <= EL_SALVADOR.north &&
    lon >= EL_SALVADOR.west &&
    lon <= EL_SALVADOR.east;
  return inside ? "in" : "out";
}

// ---- availability ----

export interface PrintContext {
  snapshot: MapSnapshot;
  /** Only a Salvadoran district can be selected, and only when one is open. */
  selectedDistrict: DistrictPrioRead | null;
}

const on = (locked = false): SectionState => ({ available: true, reason: null, locked });
const off = (reason: string): SectionState => ({ available: false, reason, locked: false });

export function computeAvailability(ctx: PrintContext, m: MapPrintMessages): Availability {
  const { snapshot, selectedDistrict } = ctx;
  const inCoverage = coverageOf(snapshot.view.center) === "in";
  const hasPlaces = snapshot.places.length > 0;
  const hasPopulation =
    inCoverage && snapshot.places.some((p) => exposedPopulationState(p).kind !== "no-coverage");

  return {
    map: on(true),
    places: hasPlaces ? on() : off(m.reasons.noPlaces),
    placeDetail: snapshot.selectedPlace ? on() : off(m.reasons.noSelectedPlace),
    counts: hasPlaces ? on() : off(m.reasons.noPlaces),
    districtDetail: !inCoverage
      ? off(m.reasons.noCensus)
      : selectedDistrict
        ? on()
        : off(m.reasons.noDistrict),
    hazards: snapshot.hazards.length > 0 ? on() : off(m.reasons.noHazards),
    weather: snapshot.weather ? on() : off(m.reasons.noWeather),
    contacts: inCoverage ? on() : off(m.reasons.notSalvadoran),
    notes: on(),
    limits: on(true),
    placePopulation: hasPopulation ? on() : off(m.reasons.noCensus),
  };
}

// ---- presets and selection ----

const PRESETS: Record<Exclude<PresetId, "complete">, readonly SectionId[]> = {
  summary: ["map", "places", "contacts", "limits"],
  dispatch: ["map", "placeDetail", "contacts", "limits"],
};

/** A one-click starting point, which never selects a section that has no data. */
export function presetSelection(preset: PresetId, availability: Availability): SectionId[] {
  const wanted = preset === "complete" ? SECTION_ORDER : PRESETS[preset];
  return SECTION_ORDER.filter(
    (id) => wanted.includes(id) && (availability[id].available || availability[id].locked),
  );
}

/** Drop what is unavailable; the map and the limits block always stay. */
export function normalizeSelection(
  selection: readonly SectionId[],
  availability: Availability,
): SectionId[] {
  return SECTION_ORDER.filter(
    (id) =>
      availability[id].locked || (selection.includes(id) && availability[id].available),
  );
}

// ---- remembered choices ----

export interface MapPrintPrefs {
  sections: SectionId[];
  /** How many places the priority list shows. */
  topPlaces: number;
  placeColumns: PlaceColumn[];
  legend: boolean;
  scale: boolean;
  north: boolean;
}

export const DEFAULT_MAP_PREFS: MapPrintPrefs = {
  sections: [...PRESETS.summary],
  topPlaces: 10,
  placeColumns: ["category", "urgency", "population"],
  legend: true,
  scale: true,
  north: true,
};

export const MAP_PREFS_KEY = "firstspot.mapPrint.v1";
const VERSION = 1;

interface Storage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function defaultStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

const fresh = (): MapPrintPrefs => ({
  ...DEFAULT_MAP_PREFS,
  sections: [...DEFAULT_MAP_PREFS.sections],
  placeColumns: [...DEFAULT_MAP_PREFS.placeColumns],
});

/** Operator notes are deliberately not remembered: they belong to one print. */
export function loadMapPrefs(storage: Storage | null = defaultStorage()): MapPrintPrefs {
  try {
    const text = storage?.getItem(MAP_PREFS_KEY);
    if (!text) return fresh();
    const parsed = JSON.parse(text) as { version?: number; prefs?: Record<string, unknown> };
    if (parsed.version !== VERSION || !parsed.prefs) return fresh();
    const raw = parsed.prefs;
    const sections = SECTION_ORDER.filter(
      (id) =>
        id === "map" ||
        id === "limits" ||
        (Array.isArray(raw.sections) && (raw.sections as unknown[]).includes(id)),
    );
    const topPlaces =
      typeof raw.topPlaces === "number" && Number.isInteger(raw.topPlaces) && raw.topPlaces > 0
        ? Math.min(raw.topPlaces, 200)
        : DEFAULT_MAP_PREFS.topPlaces;
    const placeColumns = Array.isArray(raw.placeColumns)
      ? PLACE_COLUMNS.filter((c) => (raw.placeColumns as unknown[]).includes(c))
      : [...DEFAULT_MAP_PREFS.placeColumns];
    const flag = (v: unknown, fallback: boolean) => (typeof v === "boolean" ? v : fallback);
    return {
      sections,
      topPlaces,
      placeColumns,
      legend: flag(raw.legend, true),
      scale: flag(raw.scale, true),
      north: flag(raw.north, true),
    };
  } catch {
    return fresh();
  }
}

export function saveMapPrefs(prefs: MapPrintPrefs, storage: Storage | null = defaultStorage()): void {
  try {
    const remembered: MapPrintPrefs = {
      sections: prefs.sections,
      topPlaces: prefs.topPlaces,
      placeColumns: prefs.placeColumns,
      legend: prefs.legend,
      scale: prefs.scale,
      north: prefs.north,
    };
    storage?.setItem(MAP_PREFS_KEY, JSON.stringify({ version: VERSION, prefs: remembered }));
  } catch {
    // A full or blocked storage must never stop a print.
  }
}
