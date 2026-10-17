import type { CommunityMessages } from "../../i18n/communityMessages";
import type { AppLocale } from "../../i18n/useI18n";
import type { ReportModel, ReportRow } from "./exportModel";
import type { ExportColumn } from "./exportPlan";
import { classLabels } from "./triageModel";

export type TableCell = string | number | null;

export interface ExportTable {
  header: string[];
  rows: TableCell[][];
}

/** Two decimals is plenty for a 0-10 relative score and keeps the file tidy. */
const round2 = (value: number | null): number | null =>
  value === null ? null : Math.round(value * 100) / 100;

function sphereValue(
  row: ReportRow,
  pick: (s: NonNullable<ReportRow["sphere"]>) => number,
): number | null {
  return row.sphere ? pick(row.sphere) : null;
}

/**
 * The one place a table is assembled, for Excel, CSV and the print report.
 *
 * Suppression holds here because the rows come from the report model, where a
 * withheld district already has no figures. A missing exposure is an explicit
 * "no estimate" and never 0; a real 0 stays 0.
 */
export function buildExportTable(
  model: ReportModel,
  columns: readonly ExportColumn[],
  t: CommunityMessages,
  _locale: AppLocale,
): ExportTable {
  const has = (c: ExportColumn) => columns.includes(c);
  const isEvent = model.mode === "event";
  const showSphere = has("sphere") && isEvent && model.rows.some((r) => r.sphere !== null);
  const sphereTitle = t.detail.sphereTitle;

  const header: string[] = [];
  if (has("rank")) header.push(t.sheet.columnRank);
  header.push(t.sheet.columnDistrict);
  if (has("department")) header.push(t.xlsx.department);
  if (has("class")) header.push(t.sheet.columnClass);
  if (has("prio")) header.push(t.sheet.columnScore);
  if (has("dimensions")) header.push(...model.dimensionKeys.map((k) => t.dimensions[k].name));
  if (has("population")) header.push(t.xlsx.population);
  if (has("exposed") && isEvent) header.push(t.sheet.columnExposed);
  if (has("shaking") && isEvent) header.push(t.xlsx.maxShaking);
  if (showSphere) {
    header.push(
      `${sphereTitle}: ${t.detail.waterPerDay} (L)`,
      `${sphereTitle}: ${t.detail.waterHeat} (L)`,
      `${sphereTitle}: ${t.detail.taps}`,
      `${sphereTitle}: ${t.detail.food} (kcal)`,
      `${sphereTitle}: ${t.detail.shelter} (m²)`,
    );
  }

  const rows = model.rows.map((row): TableCell[] => {
    const cells: TableCell[] = [];
    if (has("rank")) cells.push(row.rank);
    cells.push(row.name);
    if (has("department")) cells.push(row.department);
    if (has("class")) {
      cells.push(
        row.withheld
          ? t.xlsx.withheldRow
          : row.classKey
            ? classLabels(t, model.mode, row.classKey).name
            : null,
      );
    }
    if (has("prio")) cells.push(round2(row.score));
    if (has("dimensions")) cells.push(...row.dimensions.map((d) => round2(d.score)));
    if (has("population")) cells.push(row.population);
    if (has("exposed") && isEvent) {
      cells.push(row.withheld ? null : (row.exposed ?? t.list.exposedNone));
    }
    if (has("shaking") && isEvent) cells.push(round2(row.maxShaking));
    if (showSphere) {
      cells.push(
        sphereValue(row, (s) => s.water_litres_per_day),
        sphereValue(row, (s) => s.water_litres_per_day_extreme_heat),
        sphereValue(row, (s) => s.water_taps_minimum),
        sphereValue(row, (s) => s.food_kcal_per_day),
        sphereValue(row, (s) => s.shelter_area_m2),
      );
    }
    return cells;
  });

  return { header, rows };
}
