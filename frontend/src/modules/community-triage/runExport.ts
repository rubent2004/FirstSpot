import type { PrioIndexRead } from "../../api/client";
import { communityMessages, fillMessage } from "../../i18n/communityMessages";
import { buildCsv, createCsvBlob } from "./exportCsv";
import { saveBlob } from "./exportFiles";
import { buildReportModel, withScope, type ReportModel } from "./exportModel";
import {
  buildFileName,
  resolveColumns,
  resolveScope,
  selectRows,
  type ExportPrefs,
  type ExportScope,
  type ScopeContext,
} from "./exportPlan";
import { downloadRankingXlsx } from "./exportXlsx";
import type { SheetVariant } from "./PrintSheet.vue";

export interface ExportRequest {
  prefs: ExportPrefs;
  scope: ExportScope;
}

export type ExportOutcome =
  | { kind: "file"; fileName: string }
  | {
      kind: "sheet";
      variant: SheetVariant;
      model: ReportModel;
      prefs: ExportPrefs;
      fileName: string;
    };

export interface ExportInput {
  index: PrioIndexRead;
  request: ExportRequest;
  scopeContext: ScopeContext;
  selectedName: string | null;
  now: Date;
}

function scopeNote(
  input: ExportInput,
  shown: number,
  total: number,
  scope: ExportScope,
): string | null {
  const d = communityMessages(input.request.prefs.lang).exportDialog;
  const parts: string[] = [];
  if (scope === "filtered") parts.push(fillMessage(d.scopeNoteFiltered, { shown, total }));
  if (scope === "selected") {
    parts.push(fillMessage(d.scopeNoteSelected, { name: input.selectedName ?? "" }));
  }
  if (input.request.prefs.topN !== null) {
    parts.push(fillMessage(d.scopeNoteTop, { n: input.request.prefs.topN }));
  }
  return parts.length ? parts.join(" · ") : null;
}

/**
 * Turn one export request into a file or a print sheet. It reads only what is
 * already loaded: no request is made, so it works without a connection. The
 * model is built in the document language, which may differ from the UI's.
 */
export async function runExport(input: ExportInput): Promise<ExportOutcome> {
  const { prefs } = input.request;
  const t = communityMessages(prefs.lang);
  const full = buildReportModel(input.index, t, prefs.lang, input.now);
  const scope = resolveScope(input.request.scope, input.scopeContext);
  const rows = selectRows(full.rows, scope, input.scopeContext, prefs.topN);
  const model = withScope(full, rows, scopeNote(input, rows.length, full.rows.length, scope));
  const columns = resolveColumns(prefs.columns, model.mode);
  const fileName = buildFileName({
    mode: model.mode,
    eventId: model.event?.id ?? null,
    lang: prefs.lang,
    format: prefs.format,
    scope,
    topN: prefs.topN,
    districtName: input.selectedName,
    now: input.now,
  });

  if (prefs.format === "xlsx") {
    await downloadRankingXlsx(model, t, prefs.lang, {
      columns,
      includeContext: prefs.includeContext,
      fileName,
    });
    return { kind: "file", fileName };
  }
  if (prefs.format === "csv") {
    const csv = buildCsv(model, columns, t, prefs.lang, { includeContext: prefs.includeContext });
    saveBlob(createCsvBlob(csv), fileName);
    return { kind: "file", fileName };
  }
  return {
    kind: "sheet",
    variant: prefs.format === "map" ? "map" : "report",
    model,
    prefs,
    fileName,
  };
}
