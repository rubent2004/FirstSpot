import type { ExportColumn, ExportFormat, ExportScope } from "../modules/community-triage/exportPlan";

/** Copy for the export dialog. `{name}` tokens are filled by `fillMessage`. */
export interface ExportDialogMessages {
  open: string;
  title: string;
  formatLegend: string;
  scopeLegend: string;
  formats: Record<ExportFormat, { name: string; type: string; purpose: string }>;
  scopes: Record<ExportScope, string>;
  rows: string;
  noFilter: string;
  noSelection: string;
  mapScopeLine: string;
  mapScopeLineNoZone: string;
  mapUnavailable: string;
  fileLabel: string;
  more: string;
  columnsLegend: string;
  columns: Record<ExportColumn, string>;
  columnRequired: string;
  includeContext: string;
  alwaysIncluded: string;
  language: string;
  languageNames: { es: string; en: string };
  topNLabel: string;
  topNUnit: string;
  paper: string;
  paperNames: { a4: string; letter: string };
  orientation: string;
  orientationNames: { portrait: string; landscape: string };
  submit: string;
  busy: string;
  retry: string;
  cancel: string;
  repeat: string;
  repeatHint: string;
  unavailable: string;
  noRows: string;
  successFile: string;
  successSheet: string;
  failure: string;
  scopeNoteFiltered: string;
  scopeNoteSelected: string;
  scopeNoteTop: string;
}

export const EXPORT_ES: ExportDialogMessages = {
  open: "Exportar",
  title: "Exportar",
  formatLegend: "Formato",
  scopeLegend: "Qué incluir",
  formats: {
    xlsx: { name: "Excel", type: ".xlsx", purpose: "Hoja de cálculo con contexto y límites" },
    csv: { name: "CSV", type: ".csv", purpose: "Datos para otras herramientas; abre bien en Excel" },
    report: { name: "Ranking nacional de distritos", type: "PDF", purpose: "Informe para imprimir o guardar como PDF" },
    map: { name: "Mapa de la vista actual", type: "PDF", purpose: "Imprime lo que ves en el mapa, con la información de la zona" },
  },
  scopes: {
    filtered: "Lo que veo ahora",
    selected: "Distrito abierto: {name}",
    all: "Todos los distritos",
  },
  rows: "{n} filas",
  noFilter: "No hay filtros activos",
  noSelection: "Abre un distrito para exportarlo solo",
  mapScopeLine: "Se imprime la vista actual del mapa de {zone}: su extensión, fondo y capas visibles.",
  mapScopeLineNoZone: "Se imprime la vista actual del mapa: su extensión, fondo y capas visibles.",
  mapUnavailable: "El mapa aún no está listo",
  fileLabel: "Archivo",
  more: "Más opciones",
  columnsLegend: "Columnas",
  columns: {
    rank: "Puesto",
    district: "Distrito",
    department: "Departamento",
    class: "Nivel o clase",
    prio: "Prioridad",
    dimensions: "Dimensiones",
    population: "Población",
    exposed: "Expuestos (est.)",
    shaking: "Sacudida máx.",
    sphere: "Mínimos Sphere",
  },
  columnRequired: "siempre incluido",
  includeContext: "Hoja de contexto y límites",
  alwaysIncluded:
    "El aviso de límites y la atribución BCR/ONEC siempre se incluyen y no se pueden quitar.",
  language: "Idioma del documento",
  languageNames: { es: "Español", en: "English" },
  topNLabel: "Solo los primeros",
  topNUnit: "del ranking",
  paper: "Papel",
  paperNames: { a4: "A4", letter: "Carta" },
  orientation: "Orientación",
  orientationNames: { portrait: "Vertical", landscape: "Horizontal" },
  submit: "Exportar",
  busy: "Generando…",
  retry: "Reintentar",
  cancel: "Cancelar",
  repeat: "Repetir último",
  repeatHint: "Mismos ajustes: {file}",
  unavailable: "Aún no hay un ranking cargado para exportar.",
  noRows: "No hay filas para exportar con esta selección.",
  successFile: "Archivo listo: {file}",
  successSheet: "Vista de impresión lista. Usa Imprimir o guardar como PDF.",
  failure: "No se pudo generar el archivo. Puedes reintentar.",
  scopeNoteFiltered: "Vista filtrada: {shown} de {total} distritos",
  scopeNoteSelected: "Distrito: {name}",
  scopeNoteTop: "Primeros {n} del ranking",
};

export const EXPORT_EN: ExportDialogMessages = {
  open: "Export",
  title: "Export",
  formatLegend: "Format",
  scopeLegend: "What to include",
  formats: {
    xlsx: { name: "Excel", type: ".xlsx", purpose: "Spreadsheet with context and limits" },
    csv: { name: "CSV", type: ".csv", purpose: "Data for other tools; opens correctly in Excel" },
    report: { name: "National district ranking", type: "PDF", purpose: "Report to print or save as PDF" },
    map: { name: "Map of the current view", type: "PDF", purpose: "Prints what you see on the map, with the zone's information" },
  },
  scopes: {
    filtered: "What I see now",
    selected: "Open district: {name}",
    all: "All districts",
  },
  rows: "{n} rows",
  noFilter: "No filters are active",
  noSelection: "Open a district to export it alone",
  mapScopeLine: "Prints the current map view of {zone}: its extent, basemap and visible layers.",
  mapScopeLineNoZone: "Prints the current map view: its extent, basemap and visible layers.",
  mapUnavailable: "The map is not ready yet",
  fileLabel: "File",
  more: "More options",
  columnsLegend: "Columns",
  columns: {
    rank: "Rank",
    district: "District",
    department: "Department",
    class: "Level or class",
    prio: "Priority",
    dimensions: "Dimensions",
    population: "Population",
    exposed: "Exposed (est.)",
    shaking: "Peak shaking",
    sphere: "Sphere minimums",
  },
  columnRequired: "always included",
  includeContext: "Context and limits sheet",
  alwaysIncluded:
    "The limits notice and the BCR/ONEC attribution are always included and cannot be removed.",
  language: "Document language",
  languageNames: { es: "Español", en: "English" },
  topNLabel: "Only the first",
  topNUnit: "of the ranking",
  paper: "Paper",
  paperNames: { a4: "A4", letter: "Letter" },
  orientation: "Orientation",
  orientationNames: { portrait: "Portrait", landscape: "Landscape" },
  submit: "Export",
  busy: "Generating…",
  retry: "Retry",
  cancel: "Cancel",
  repeat: "Repeat last",
  repeatHint: "Same settings: {file}",
  unavailable: "No ranking is loaded yet, so there is nothing to export.",
  noRows: "There are no rows to export with this selection.",
  successFile: "File ready: {file}",
  successSheet: "Print view ready. Use Print or save as PDF.",
  failure: "Could not generate the file. You can retry.",
  scopeNoteFiltered: "Filtered view: {shown} of {total} districts",
  scopeNoteSelected: "District: {name}",
  scopeNoteTop: "First {n} of the ranking",
};
