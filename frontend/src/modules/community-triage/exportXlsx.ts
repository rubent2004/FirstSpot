import type { CommunityMessages } from "../../i18n/communityMessages";
import type { AppLocale } from "../../i18n/useI18n";
import type { ReportModel, ReportRow } from "./exportModel";
import { formatInteger } from "./formatters";
import { classLabels } from "./triageModel";

type SheetCell = string | number | null | { value: string; fontWeight: "bold" };

export interface WorkbookSheet {
  sheet: string;
  data: SheetCell[][];
  columns?: Array<{ width: number }>;
}

const bold = (value: string): SheetCell => ({ value, fontWeight: "bold" });

/** Two decimals is plenty for a 0-10 relative score and keeps the sheet tidy. */
const round2 = (value: number | null): number | null =>
  value === null ? null : Math.round(value * 100) / 100;

function eventSummary(model: ReportModel, locale: AppLocale): string {
  const event = model.event;
  if (!event) return "";
  const magnitude =
    event.magnitude !== null ? `M${event.magnitude.toLocaleString(locale === "es" ? "es-SV" : "en-US")} ` : "";
  return `${magnitude}${event.place}`;
}

function bannerRows(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
): SheetCell[][] {
  const parts = [`${t.xlsx.modeRow}: ${model.modeLabel}`];
  if (model.event) {
    parts.push(`${t.xlsx.eventRow}: ${eventSummary(model, locale)}`);
    parts.push(
      `${t.xlsx.shakemapRow}: ${model.event.shakemapLabel ?? t.event.shakemapPending}`,
    );
  }
  parts.push(`${t.xlsx.generatedRow}: ${model.generatedAtLabel}`);
  parts.push(`${t.xlsx.sourceRow}: ${model.attribution}`);
  return [
    [bold(t.sheet.reportTitle)],
    [parts.join(" · ")],
    [`${t.xlsx.limitationsRow}: ${model.limitationsLine}`],
    [],
  ];
}

function sphereCell(row: ReportRow, pick: (s: NonNullable<ReportRow["sphere"]>) => number) {
  return row.sphere ? pick(row.sphere) : null;
}

function rankingSheet(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
): WorkbookSheet {
  const hasSphere = model.rows.some((row) => row.sphere !== null);
  const isEvent = model.mode === "event";
  const sphereTitle = t.detail.sphereTitle;

  const header: SheetCell[] = [
    t.sheet.columnRank,
    t.sheet.columnDistrict,
    t.sheet.columnClass,
    t.sheet.columnScore,
    ...model.dimensionKeys.map((key) => t.dimensions[key].name),
    t.xlsx.population,
    ...(isEvent ? [t.sheet.columnExposed, t.xlsx.maxShaking] : []),
    ...(hasSphere
      ? [
          `${sphereTitle}: ${t.detail.waterPerDay} (L)`,
          `${sphereTitle}: ${t.detail.waterHeat} (L)`,
          `${sphereTitle}: ${t.detail.taps}`,
          `${sphereTitle}: ${t.detail.food} (kcal)`,
          `${sphereTitle}: ${t.detail.shelter} (m²)`,
        ]
      : []),
  ].map((label) => (typeof label === "string" ? bold(label) : label));

  const body = model.rows.map((row): SheetCell[] => [
    row.rank,
    row.name,
    row.withheld
      ? t.xlsx.withheldRow
      : row.classKey
        ? classLabels(t, model.mode, row.classKey).name
        : null,
    round2(row.score),
    ...row.dimensions.map((d) => round2(d.score)),
    row.population,
    ...(isEvent ? [row.exposed, round2(row.maxShaking)] : []),
    ...(hasSphere
      ? [
          sphereCell(row, (s) => s.water_litres_per_day),
          sphereCell(row, (s) => s.water_litres_per_day_extreme_heat),
          sphereCell(row, (s) => s.water_taps_minimum),
          sphereCell(row, (s) => s.food_kcal_per_day),
          sphereCell(row, (s) => s.shelter_area_m2),
        ]
      : []),
  ]);

  const banner = bannerRows(model, t, locale);
  const widths = [8, 30, 12, 14];
  return {
    sheet: t.xlsx.sheetRanking,
    data: [...banner, header, ...body],
    columns: header.map((_, i) => ({ width: widths[i] ?? 18 })),
  };
}

function contextSheet(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
): WorkbookSheet {
  const rows: SheetCell[][] = [
    [bold(t.sheet.reportTitle)],
    [],
    [bold(t.xlsx.modeRow), model.modeLabel],
    ["", model.modeMeaning],
  ];
  if (model.event) {
    rows.push([bold(t.xlsx.eventRow), eventSummary(model, locale)]);
    rows.push([bold(t.event.occurredAt), model.event.occurredLabel]);
    rows.push([
      bold(t.xlsx.shakemapRow),
      model.event.shakemapLabel ?? t.event.shakemapPending,
    ]);
    rows.push([bold(t.xlsx.pagerRow), model.event.pagerLabel ?? t.event.pagerNone]);
    rows.push(["", t.event.pagerIsRange]);
  }
  rows.push([bold(t.xlsx.generatedRow), model.generatedAtLabel]);
  rows.push([bold(t.xlsx.sourceRow), model.attribution]);
  rows.push([bold(t.sheet.columnDistrict), formatInteger(model.total, locale)]);
  rows.push([]);
  rows.push([bold(t.xlsx.limitationsRow)]);
  for (const line of model.limitations) rows.push(["", line]);
  rows.push(["", t.detail.sphereNote]);
  return {
    sheet: t.xlsx.sheetContext,
    data: rows,
    columns: [{ width: 28 }, { width: 110 }],
  };
}

/** The two sheets, as plain data. Pure, so the content is testable without a file. */
export function buildWorkbookSheets(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
): WorkbookSheet[] {
  return [rankingSheet(model, t, locale), contextSheet(model, t, locale)];
}

/**
 * Build the .xlsx in memory. The writer is imported on demand, so it is a
 * separate chunk that never enters the initial bundle, and once that chunk is
 * cached nothing here touches the network.
 */
export async function createWorkbookBlob(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
): Promise<Blob> {
  const { default: writeXlsxFile } = await import("write-excel-file/browser");
  const sheets = buildWorkbookSheets(model, t, locale);
  return writeXlsxFile(
    sheets as unknown as Parameters<typeof writeXlsxFile>[0],
  ).toBlob();
}

function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function downloadRankingXlsx(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
): Promise<void> {
  const blob = await createWorkbookBlob(model, t, locale);
  const stamp = model.generatedAtIso.slice(0, 16).replace(/[-:]/g, "").replace("T", "-");
  saveBlob(blob, `${t.xlsx.fileStem}-${model.mode}-${stamp}.xlsx`);
}
