import type { CommunityMessages } from "../../i18n/communityMessages";
import type { AppLocale } from "../../i18n/useI18n";
import type { ReportModel } from "./exportModel";
import type { ExportColumn } from "./exportPlan";
import { columnsFor, resolveColumns } from "./exportPlan";
import { buildExportTable } from "./exportTable";
import { saveBlob } from "./exportFiles";
import { formatInteger } from "./formatters";

type SheetCell = string | number | null | { value: string; fontWeight: "bold" };

export interface WorkbookSheet {
  sheet: string;
  data: SheetCell[][];
  columns?: Array<{ width: number }>;
}

const bold = (value: string): SheetCell => ({ value, fontWeight: "bold" });

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
  if (model.scopeNote) parts.push(model.scopeNote);
  return [
    [bold(t.sheet.reportTitle)],
    [parts.join(" · ")],
    [`${t.xlsx.limitationsRow}: ${model.limitationsLine}`],
    [],
  ];
}

function rankingSheet(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
  columns: readonly ExportColumn[],
): WorkbookSheet {
  const table = buildExportTable(model, columns, t, locale);
  const header: SheetCell[] = table.header.map((label) => bold(label));
  const widths = [8, 30, 12, 14];
  return {
    sheet: t.xlsx.sheetRanking,
    data: [...bannerRows(model, t, locale), header, ...table.rows],
    columns: header.map((_, i) => ({ width: widths[i] ?? 18 })),
  };
}

/** Mode, event, ShakeMap time, limits and sources as label/value lines. */
export function contextLines(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
): SheetCell[][] {
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
  return rows;
}

function contextSheet(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
): WorkbookSheet {
  return {
    sheet: t.xlsx.sheetContext,
    data: contextLines(model, t, locale),
    columns: [{ width: 28 }, { width: 110 }],
  };
}

export interface WorkbookOptions {
  columns?: readonly ExportColumn[];
  /** The context sheet. The limits line on the ranking sheet is always there. */
  includeContext?: boolean;
}

/** The sheets, as plain data. Pure, so the content is testable without a file. */
export function buildWorkbookSheets(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
  options: WorkbookOptions = {},
): WorkbookSheet[] {
  const columns = options.columns ?? resolveColumns(columnsFor(model.mode), model.mode);
  const sheets = [rankingSheet(model, t, locale, columns)];
  if (options.includeContext !== false) sheets.push(contextSheet(model, t, locale));
  return sheets;
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
  options: WorkbookOptions = {},
): Promise<Blob> {
  const { default: writeXlsxFile } = await import("write-excel-file/browser");
  const sheets = buildWorkbookSheets(model, t, locale, options);
  return writeXlsxFile(
    sheets as unknown as Parameters<typeof writeXlsxFile>[0],
  ).toBlob();
}

export async function downloadRankingXlsx(
  model: ReportModel,
  t: CommunityMessages,
  locale: AppLocale,
  options: WorkbookOptions & { fileName: string },
): Promise<void> {
  const blob = await createWorkbookBlob(model, t, locale, options);
  saveBlob(blob, options.fileName);
}
