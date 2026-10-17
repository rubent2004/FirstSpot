import type { AppLocale } from "../../i18n/useI18n";
import type { ReportRow } from "./exportModel";
import type { TriageMode } from "./triageModel";

/**
 * The selection logic of the export flow, kept pure so it is testable without
 * a dialog: scope -> rows, column choice, file name, remembered choices.
 */

export type ExportFormat = "xlsx" | "csv" | "report" | "map";
/** What part of the ranking: what the operator is looking at, the open district, or all. */
export type ExportScope = "filtered" | "selected" | "all";
export type PaperSize = "a4" | "letter";
export type Orientation = "portrait" | "landscape";

export type ExportColumn =
  | "rank"
  | "district"
  | "department"
  | "class"
  | "prio"
  | "dimensions"
  | "population"
  | "exposed"
  | "shaking"
  | "sphere";

/** Canonical order: whatever order boxes are ticked in, files read the same. */
export const EXPORT_COLUMNS: readonly ExportColumn[] = [
  "rank",
  "district",
  "department",
  "class",
  "prio",
  "dimensions",
  "population",
  "exposed",
  "shaking",
  "sphere",
];

/** A row without its district name is meaningless, so that column is not optional. */
export const REQUIRED_COLUMNS: readonly ExportColumn[] = ["district"];

const EVENT_ONLY: readonly ExportColumn[] = ["exposed", "shaking", "sphere"];

export function columnsFor(mode: TriageMode): ExportColumn[] {
  return EXPORT_COLUMNS.filter((c) => mode === "event" || !EVENT_ONLY.includes(c));
}

export function resolveColumns(selected: readonly ExportColumn[], mode: TriageMode): ExportColumn[] {
  const allowed = columnsFor(mode);
  return allowed.filter((c) => REQUIRED_COLUMNS.includes(c) || selected.includes(c));
}

export interface ExportPrefs {
  format: ExportFormat;
  columns: ExportColumn[];
  /** Limit to the first N of the ranking; null means no limit. */
  topN: number | null;
  /** The "context and limits" sheet/block. The limits line itself is never optional. */
  includeContext: boolean;
  lang: AppLocale;
  paper: PaperSize;
  orientation: Orientation;
}

export const DEFAULT_PREFS: ExportPrefs = {
  format: "xlsx",
  columns: [...EXPORT_COLUMNS],
  topN: null,
  includeContext: true,
  lang: "es",
  paper: "a4",
  orientation: "landscape",
};

// ---- scope -> rows ----

export interface ScopeContext {
  /** Codes of the districts currently listed, or null when nothing narrows the list. */
  filteredCodes: ReadonlySet<string> | null;
  selectedCode: string | null;
}

export function selectRows(
  rows: readonly ReportRow[],
  scope: ExportScope,
  ctx: ScopeContext,
  topN: number | null,
): ReportRow[] {
  let picked: ReportRow[];
  if (scope === "selected") {
    picked = rows.filter((r) => ctx.selectedCode !== null && r.code === ctx.selectedCode);
  } else if (scope === "filtered") {
    picked = rows.filter((r) => ctx.filteredCodes?.has(r.code) ?? true);
  } else {
    picked = [...rows];
  }
  return topN !== null ? picked.slice(0, topN) : picked;
}

export function scopeCounts(
  rows: readonly ReportRow[],
  ctx: ScopeContext,
  topN: number | null,
): Record<ExportScope, number> {
  return {
    all: selectRows(rows, "all", ctx, topN).length,
    filtered: selectRows(rows, "filtered", ctx, topN).length,
    selected: selectRows(rows, "selected", ctx, topN).length,
  };
}

/** A remembered scope that no longer exists gives way to one that does. */
export function resolveScope(scope: ExportScope, ctx: ScopeContext): ExportScope {
  if (scope === "selected" && ctx.selectedCode === null) {
    return ctx.filteredCodes ? "filtered" : "all";
  }
  if (scope === "filtered" && !ctx.filteredCodes) return "all";
  return scope;
}

// ---- file name ----

export interface FileNameInput {
  mode: TriageMode;
  eventId: string | null;
  lang: AppLocale;
  format: ExportFormat;
  scope: ExportScope;
  topN: number | null;
  districtName: string | null;
  now: Date;
}

const MODE_SLUG: Record<AppLocale, Record<TriageMode, string>> = {
  es: { baseline: "linea-base", event: "evento" },
  en: { baseline: "baseline", event: "event" },
};
const SCOPE_SLUG: Record<AppLocale, string> = { es: "filtrado", en: "filtered" };
const MAP_SLUG: Record<AppLocale, string> = { es: "mapa", en: "map" };
const EXTENSION: Record<ExportFormat, string> = {
  xlsx: "xlsx",
  csv: "csv",
  report: "pdf",
  map: "pdf",
};

/** Lowercase ASCII with hyphens: safe on every file system and easy to sort. */
export function slugify(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function buildFileName(input: FileNameInput): string {
  const parts = ["firstspot", "prio", MODE_SLUG[input.lang][input.mode]];
  if (input.mode === "event" && input.eventId) parts.push(slugify(input.eventId));
  parts.push(input.now.toISOString().slice(0, 10));
  if (input.format === "map") parts.push(MAP_SLUG[input.lang]);
  if (input.scope === "filtered") parts.push(SCOPE_SLUG[input.lang]);
  if (input.scope === "selected" && input.districtName) {
    const slug = slugify(input.districtName);
    if (slug) parts.push(slug);
  }
  if (input.topN !== null) parts.push(`top-${input.topN}`);
  return `${parts.join("_")}.${EXTENSION[input.format]}`;
}

// ---- remembered choices ----

export const PREFS_KEY = "firstspot.communityExport.v1";
const PREFS_VERSION = 1;

export interface PrefsStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function defaultStorage(): PrefsStorage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

const FORMATS: readonly ExportFormat[] = ["xlsx", "csv", "report", "map"];
const PAPERS: readonly PaperSize[] = ["a4", "letter"];
const ORIENTATIONS: readonly Orientation[] = ["portrait", "landscape"];

function pick<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

/** Field-by-field repair: a hand-edited or older value never breaks the dialog. */
function sanitise(raw: Record<string, unknown>, lang: AppLocale): ExportPrefs {
  const columns = Array.isArray(raw.columns)
    ? EXPORT_COLUMNS.filter((c) => (raw.columns as unknown[]).includes(c))
    : DEFAULT_PREFS.columns;
  const topN =
    typeof raw.topN === "number" && Number.isInteger(raw.topN) && raw.topN > 0 ? raw.topN : null;
  return {
    format: pick(raw.format, FORMATS, DEFAULT_PREFS.format),
    columns,
    topN,
    includeContext:
      typeof raw.includeContext === "boolean" ? raw.includeContext : DEFAULT_PREFS.includeContext,
    lang,
    paper: pick(raw.paper, PAPERS, DEFAULT_PREFS.paper),
    orientation: pick(raw.orientation, ORIENTATIONS, DEFAULT_PREFS.orientation),
  };
}

/**
 * The document language is not remembered: it always starts as the language the
 * console is shown in, so a bilingual team never prints in the wrong one by habit.
 */
export function loadPrefs(
  storage: PrefsStorage | null = defaultStorage(),
  lang: AppLocale = DEFAULT_PREFS.lang,
): ExportPrefs {
  const fresh = (): ExportPrefs => ({ ...DEFAULT_PREFS, columns: [...DEFAULT_PREFS.columns], lang });
  try {
    const text = storage?.getItem(PREFS_KEY);
    if (!text) return fresh();
    const parsed = JSON.parse(text) as { version?: number; prefs?: Record<string, unknown> };
    if (parsed.version !== PREFS_VERSION || !parsed.prefs) return fresh();
    return sanitise(parsed.prefs, lang);
  } catch {
    return fresh();
  }
}

export function hasSavedPrefs(storage: PrefsStorage | null = defaultStorage()): boolean {
  try {
    return Boolean(storage?.getItem(PREFS_KEY));
  } catch {
    return false;
  }
}

export function savePrefs(
  prefs: ExportPrefs,
  storage: PrefsStorage | null = defaultStorage(),
): void {
  try {
    const { lang: _lang, ...remembered } = prefs;
    storage?.setItem(PREFS_KEY, JSON.stringify({ version: PREFS_VERSION, prefs: remembered }));
  } catch {
    // A full or blocked storage must never stop an export.
  }
}
