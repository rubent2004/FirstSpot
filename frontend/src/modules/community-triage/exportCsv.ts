import type { CommunityMessages } from "../../i18n/communityMessages";
import type { AppLocale } from "../../i18n/useI18n";
import type { ReportModel } from "./exportModel";
import { contextLines } from "./exportXlsx";
import type { ExportColumn } from "./exportPlan";
import { buildExportTable, type TableCell } from "./exportTable";

/** UTF-8 byte order mark: without it Excel reads accents as mojibake. */
export const CSV_BOM = "﻿";
const EOL = "\r\n";

/**
 * One CSV field. Quotes only when needed, doubles inner quotes (RFC 4180), and
 * defuses text a spreadsheet would run as a formula (CSV injection).
 */
export function csvCell(value: TableCell): string {
  if (value === null) return "";
  if (typeof value === "number") return String(value);
  let text = value;
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

const line = (cells: readonly TableCell[]): string => cells.map(csvCell).join(",");

export interface CsvOptions {
  includeContext: boolean;
}

/**
 * The file is self-describing: a short preamble (mode, event, ShakeMap time,
 * generation time, source, scope and the limits line) comes before the header,
 * and it is not optional. Dropping it would let the numbers travel without
 * their meaning. A plain-CSV reader skips it with one "skip rows" setting.
 */
export function buildCsv(
  model: ReportModel,
  columns: readonly ExportColumn[],
  t: CommunityMessages,
  locale: AppLocale,
  options: CsvOptions,
): string {
  const table = buildExportTable(model, columns, t, locale);
  const lines: string[] = [];

  const facts = [`${t.xlsx.modeRow}: ${model.modeLabel}`];
  if (model.event) {
    const magnitude =
      model.event.magnitude !== null
        ? `M${model.event.magnitude.toLocaleString(locale === "es" ? "es-SV" : "en-US")} `
        : "";
    facts.push(`${t.xlsx.eventRow}: ${magnitude}${model.event.place}`);
    facts.push(`${t.xlsx.shakemapRow}: ${model.event.shakemapLabel ?? t.event.shakemapPending}`);
    if (model.event.pagerLabel) facts.push(`${t.xlsx.pagerRow}: ${model.event.pagerLabel}`);
  }
  facts.push(`${t.xlsx.generatedRow}: ${model.generatedAtLabel}`);
  facts.push(`${t.xlsx.sourceRow}: ${model.attribution}`);
  if (model.scopeNote) facts.push(model.scopeNote);

  lines.push(line([t.sheet.reportTitle]));
  lines.push(line([facts.join(" · ")]));
  lines.push(line([`${t.xlsx.limitationsRow}: ${model.limitationsLine}`]));
  lines.push("");
  lines.push(line(table.header));
  for (const row of table.rows) lines.push(line(row));

  if (options.includeContext) {
    lines.push("");
    lines.push(line([t.xlsx.sheetContext]));
    for (const row of contextLines(model, t, locale)) {
      lines.push(
        line(row.map((cell) => (cell && typeof cell === "object" ? cell.value : (cell ?? "")))),
      );
    }
  }
  return CSV_BOM + lines.join(EOL) + EOL;
}

export function createCsvBlob(csv: string): Blob {
  return new Blob([csv], { type: "text/csv;charset=utf-8" });
}
