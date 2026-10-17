import type { AlertClassKey, DimensionKey } from "../modules/community-triage/triageModel";
import { EXPORT_EN, EXPORT_ES, type ExportDialogMessages } from "./communityExportMessages";

/**
 * Copy for the community triage view and its exports.
 *
 * Every sentence here is written for an operator under pressure: no backend
 * field names, no INFORM jargon. `{name}` tokens are filled by `fillMessage`.
 */
export interface CommunityMessages {
  nav: {
    label: string;
    districts: string;
    places: string;
    breadcrumb: string;
    closeDetail: string;
    placesIn: string;
    openZonePlaces: string;
    announceDetail: string;
    announceList: string;
    announcePlaces: string;
  };
  map: { caption: string };
  title: string;
  subtitle: string;
  mode: {
    label: string;
    baseline: string;
    event: string;
    baselineMeaning: string;
    eventMeaning: string;
    switchToBaseline: string;
    baselineShort: string;
    eventShort: string;
    updating: string;
    pickEvent: string;
  };
  event: {
    pickerLabel: string;
    pickerPlaceholder: string;
    noShakemap: string;
    loadFailed: string;
    magnitude: string;
    occurredAt: string;
    shakemapGrid: string;
    shakemapPending: string;
    shakemapRevised: string;
    pager: string;
    pagerNone: string;
    pagerUnreadable: string;
    pagerIsRange: string;
    pagerLevels: Record<string, string>;
    maxShaking: string;
  };
  classes: Record<AlertClassKey, { name: string; meaning: string }>;
  /** Baseline's neutral structural scale: never an alert, never a status hue. */
  levels: Record<AlertClassKey, { name: string; meaning: string; group: string }>;
  levelsNote: string;
  dimensions: Record<DimensionKey, { name: string; short: string; abbr: string }>;
  honesty: {
    title: string;
    ranking: string;
    noVictims: string;
    exposure: string;
    gaps: string;
    relative: string;
    attributionLabel: string;
    more: string;
  };
  list: {
    ariaLabel: string;
    search: string;
    districts: string;
    exposed: string;
    exposedUnknown: string;
    withheld: string;
    withheldHint: string;
    empty: string;
    loading: string;
    loadFailed: string;
    retry: string;
    showMore: string;
    scoreZero: string;
    classFilterAll: string;
    classFilterLabel: string;
    sortLabel: string;
    sortScore: string;
    sortExposed: string;
    sortName: string;
    scopeLabel: string;
    scopeZone: string;
    scopeCountry: string;
    showing: string;
    nationalRank: string;
    columnRank: string;
    columnDistrict: string;
    columnScore: string;
    clearFilters: string;
    rankLabel: string;
    exposedNone: string;
    zeroShort: string;
  };
  detail: {
    rankOf: string;
    score: string;
    driversTitle: string;
    technicalTitle: string;
    dimensionRank: string;
    dimensionAbsent: string;
    baselineNoHazard: string;
    withheldDimension: string;
    zeroTitle: string;
    zeroHazard: string;
    zeroFloor: string;
    zeroGeneric: string;
    auditTitle: string;
    auditRule: string;
    auditReference: string;
    auditLoading: string;
    auditFailed: string;
    exposedTitle: string;
    exposedNote: string;
    sphereTitle: string;
    sphereNote: string;
    sphereNotComputed: string;
    waterPerDay: string;
    waterHeat: string;
    taps: string;
    waterDistance: string;
    food: string;
    shelter: string;
    withheldWhole: string;
    placesTitle: string;
    placesBody: string;
    placesOpen: string;
  };
  exportDialog: ExportDialogMessages;
  sheet: {
    reportTitle: string;
    mapTitle: string;
    print: string;
    close: string;
    generatedAt: string;
    columnRank: string;
    columnDistrict: string;
    columnClass: string;
    columnScore: string;
    columnExposed: string;
    columnSphere: string;
    legend: string;
    north: string;
    sphereCompact: string;
  };
  xlsx: {
    sheetRanking: string;
    sheetContext: string;
    population: string;
    department: string;
    maxShaking: string;
    withheldRow: string;
    modeRow: string;
    eventRow: string;
    shakemapRow: string;
    pagerRow: string;
    generatedRow: string;
    sourceRow: string;
    limitationsRow: string;
    fileStem: string;
  };
}

export const COMMUNITY_ES: CommunityMessages = {
  nav: {
    label: "Prioridad por distrito",
    districts: "Distritos",
    places: "Lugares",
    breadcrumb: "Dónde estás",
    closeDetail: "Cerrar",
    placesIn: "Lugares en {zone}",
    openZonePlaces: "Ver lugares de {zone}",
    announceDetail: "Detalle abierto: {name}",
    announceList: "Lista de distritos",
    announcePlaces: "Lugares de la zona {zone}",
  },
  map: {
    caption:
      "El mapa muestra lugares y su calor de vulnerabilidad, no distritos: los datos no incluyen los límites de cada distrito.",
  },
  title: "Territorios prioritarios",
  subtitle: "Distritos ordenados por prioridad relativa",
  mode: {
    label: "Modo",
    baseline: "Línea base",
    event: "Evento",
    baselineMeaning:
      "Sin sismo: combina vulnerabilidad y falta de capacidad de respuesta. Muestra dónde el país está más frágil, no qué ocurrió hoy.",
    eventMeaning:
      "Con sismo: suma la sacudida medida de este evento. Vale solo para esa versión del mapa de sacudida.",
    switchToBaseline: "Volver a línea base",
    baselineShort: "Sin sismo: dónde el país es más frágil, no qué pasó hoy.",
    eventShort: "Con sismo: suma la sacudida medida de este evento.",
    updating: "Actualizando…",
    pickEvent: "Elige un sismo para ver el modo Evento.",
  },
  event: {
    pickerLabel: "Evento",
    pickerPlaceholder: "Elegir un sismo reciente",
    noShakemap: "sin mapa de sacudida",
    loadFailed: "No se pudieron cargar los sismos recientes.",
    magnitude: "Magnitud",
    occurredAt: "Ocurrió",
    shakemapGrid: "Mapa de sacudida (ShakeMap) procesado",
    shakemapPending: "Sin hora de procesamiento publicada",
    shakemapRevised:
      "El mapa de sacudida se revisa: estas cifras valen solo para esa hora.",
    pager: "Alerta PAGER (USGS)",
    pagerNone: "El evento no tiene alerta PAGER",
    pagerUnreadable: "Rango no legible",
    pagerIsRange:
      "Rango de fallecidos estimado por USGS PAGER. Es un rango, no un conteo, y FirstSpot no lo calcula.",
    maxShaking: "Sacudida máxima",
    pagerLevels: { green: "verde", yellow: "amarilla", orange: "naranja", red: "roja" },
  },
  classes: {
    roja: { name: "Roja", meaning: "Prioridad más alta entre los distritos" },
    naranja: { name: "Naranja", meaning: "Prioridad alta" },
    amarilla: { name: "Amarilla", meaning: "Prioridad media" },
    verde: { name: "Verde", meaning: "Prioridad más baja. No significa que nadie necesite ayuda" },
  },
  levels: {
    roja: {
      name: "Muy alto",
      group: "Riesgo estructural muy alto",
      meaning: "Mayor fragilidad estructural entre los distritos. No es una alerta.",
    },
    naranja: {
      name: "Alto",
      group: "Riesgo estructural alto",
      meaning: "Fragilidad estructural alta. No es una alerta.",
    },
    amarilla: {
      name: "Medio",
      group: "Riesgo estructural medio",
      meaning: "Fragilidad estructural media. No es una alerta.",
    },
    verde: {
      name: "Bajo",
      group: "Riesgo estructural bajo",
      meaning: "Menor fragilidad estructural. No significa que nadie necesite ayuda.",
    },
  },
  levelsNote: "Sin sismo no hay alerta: esta escala es de fragilidad, no de emergencia.",
  dimensions: {
    hazard_and_exposure: { name: "Amenaza y exposición", short: "Amenaza", abbr: "AyE" },
    vulnerability: { name: "Vulnerabilidad", short: "Vulnerab.", abbr: "V" },
    lack_of_coping_capacity: {
      name: "Falta de capacidad de respuesta",
      short: "Capacidad",
      abbr: "FCR",
    },
  },
  honesty: {
    title: "Cómo leer esto",
    ranking:
      "Es un ranking relativo de territorios (distritos), no de personas.",
    noVictims: "No informa víctimas ni fallecidos.",
    exposure:
      "La población expuesta es una estimación de residentes en la zona, no de afectados.",
    gaps:
      "Vacíos declarados: no mide la calidad de la construcción; la pobreza urbana está subrepresentada; solo considera sismos.",
    relative:
      "Un puntaje es una posición entre {total} distritos, no una medida de daño.",
    attributionLabel: "Datos",
    more: "Cómo leer esto y sus límites",
  },
  list: {
    ariaLabel: "Distritos ordenados por prioridad",
    search: "Buscar distrito",
    districts: "distritos",
    exposed: "expuestos (est.)",
    exposedUnknown: "sin estimación",
    withheld: "Dato reservado",
    withheldHint: "Reservado por secreto estadístico; no se publica.",
    empty: "Ningún distrito coincide.",
    loading: "Calculando prioridades…",
    loadFailed: "No se pudo cargar el ranking de distritos.",
    retry: "Reintentar",
    showMore: "Mostrar más",
    scoreZero: "0 · ver motivo",
    classFilterAll: "Todas",
    classFilterLabel: "Filtrar por nivel",
    sortLabel: "Ordenar por",
    sortScore: "Prioridad",
    sortExposed: "Expuestos",
    sortName: "Nombre",
    scopeLabel: "Alcance",
    scopeZone: "Solo {department}",
    scopeCountry: "Todo el país",
    showing: "Mostrando {shown} de {total} distritos",
    nationalRank: "El puesto es nacional, entre {total} distritos.",
    columnRank: "Puesto",
    columnDistrict: "Distrito",
    columnScore: "Prioridad relativa",
    clearFilters: "Quitar filtros",
    rankLabel: "puesto {rank}",
    exposedNone: "sin estimación",
    zeroShort: "0 · ver motivo",
  },
  detail: {
    rankOf: "Puesto {rank} de {total}",
    score: "Prioridad",
    driversTitle: "Qué más pesa en la prioridad",
    technicalTitle: "Indicadores, necesidades Sphere y fuentes",
    dimensionRank: "puesto {rank}",
    dimensionAbsent: "no entra en este modo",
    baselineNoHazard:
      "En línea base no hay sismo, por eso no se mide amenaza.",
    withheldDimension: "Reservado",
    zeroTitle: "Por qué el puntaje es 0",
    zeroHazard:
      "El sismo no alcanzó este distrito con intensidad relevante. La amenaza es 0 y, como las dimensiones se multiplican, el puntaje es 0. No lo dice pobre ni bien preparado.",
    zeroFloor:
      "Quedó en el último lugar entre los distritos en «{dimension}». Eso lo ubica como el mejor de {total} en ese aspecto; no significa «sin riesgo». Como las dimensiones se multiplican, un 0 anula el puntaje.",
    zeroGeneric:
      "Una de las dimensiones vale 0 y anula el puntaje. Un 0 aquí es una posición relativa, no ausencia de riesgo.",
    auditTitle: "Auditoría",
    auditRule:
      "El puntaje compuesto es la media geométrica de las {count} dimensiones, con el mismo peso; va de 0 a 10.",
    auditReference: "Puntaje con reescalado INFORM (solo referencia, no ordena)",
    auditLoading: "Cargando auditoría…",
    auditFailed: "No se pudo cargar la auditoría de este distrito.",
    exposedTitle: "Población expuesta (estimación)",
    exposedNote:
      "Residentes estimados en zonas con sacudida fuerte. No son víctimas ni afectados.",
    sphereTitle: "Requerimiento mínimo Sphere",
    sphereNote:
      "Es el mínimo que establece Sphere para esa población estimada. No es lo que hay que entregar ni se compara con recursos disponibles, que no se miden.",
    sphereNotComputed:
      "Los requerimientos mínimos Sphere se calculan solo para distritos naranja o rojo y necesitan la población expuesta a un evento.",
    waterPerDay: "Agua por día",
    waterHeat: "Agua por día (calor extremo)",
    taps: "Grifos mínimos",
    waterDistance: "Punto de agua a menos de",
    food: "Alimento por día",
    shelter: "Área de albergue",
    withheldWhole:
      "Este distrito no se publica: sus datos están reservados por secreto estadístico.",
    placesTitle: "Lugares",
    placesBody:
      "Los datos aún no asignan lugares (escuelas, clínicas, albergues) a un distrito. Puedes ver los lugares de la zona de trabajo.",
    placesOpen: "Ver lugares de {zone}",
  },
  exportDialog: EXPORT_ES,
  sheet: {
    reportTitle: "Informe de priorización de territorios",
    mapTitle: "Mapa de distritos prioritarios",
    print: "Imprimir / guardar PDF",
    close: "Cerrar",
    generatedAt: "Generado",
    columnRank: "Puesto",
    columnDistrict: "Distrito",
    columnClass: "Clase",
    columnScore: "Prioridad (0-10)",
    columnExposed: "Expuestos (est.)",
    columnSphere: "Mínimo Sphere",
    legend: "Leyenda",
    north: "N",
    sphereCompact: "{water} L de agua/día · {food} kcal/día · {shelter} m² de albergue",
  },
  xlsx: {
    sheetRanking: "Ranking",
    sheetContext: "Contexto y límites",
    population: "Población",
    department: "Departamento",
    maxShaking: "Sacudida máx.",
    withheldRow: "Reservado",
    modeRow: "Modo",
    eventRow: "Evento",
    shakemapRow: "Mapa de sacudida procesado",
    pagerRow: "Alerta PAGER (rango)",
    generatedRow: "Generado",
    sourceRow: "Datos",
    limitationsRow: "Límites",
    fileStem: "priorizacion-distritos",
  },
};

export const COMMUNITY_EN: CommunityMessages = {
  nav: {
    label: "Priority by district",
    districts: "Districts",
    places: "Places",
    breadcrumb: "Where you are",
    closeDetail: "Close",
    placesIn: "Places in {zone}",
    openZonePlaces: "See places in {zone}",
    announceDetail: "Detail opened: {name}",
    announceList: "District list",
    announcePlaces: "Places in the {zone} zone",
  },
  map: {
    caption:
      "The map shows places and their vulnerability heat, not districts: the data does not include district boundaries.",
  },
  title: "Priority territories",
  subtitle: "Districts ordered by relative priority",
  mode: {
    label: "Mode",
    baseline: "Baseline",
    event: "Event",
    baselineMeaning:
      "No earthquake: combines vulnerability and lack of coping capacity. Shows where the country is most fragile, not what happened today.",
    eventMeaning:
      "With an earthquake: adds the measured shaking of this event. Valid only for that version of the shaking map.",
    switchToBaseline: "Back to baseline",
    baselineShort: "No earthquake: where the country is most fragile, not what happened today.",
    eventShort: "With an earthquake: adds the measured shaking of this event.",
    updating: "Updating…",
    pickEvent: "Pick an earthquake to see Event mode.",
  },
  event: {
    pickerLabel: "Event",
    pickerPlaceholder: "Pick a recent earthquake",
    noShakemap: "no shaking map",
    loadFailed: "Could not load recent earthquakes.",
    magnitude: "Magnitude",
    occurredAt: "Occurred",
    shakemapGrid: "Shaking map (ShakeMap) processed",
    shakemapPending: "No processing time published",
    shakemapRevised:
      "The shaking map is revised: these figures are valid only for that time.",
    pager: "PAGER alert (USGS)",
    pagerNone: "This event has no PAGER alert",
    pagerUnreadable: "Range not readable",
    pagerIsRange:
      "Fatality range estimated by USGS PAGER. It is a range, not a count, and FirstSpot does not compute it.",
    maxShaking: "Peak shaking",
    pagerLevels: { green: "green", yellow: "yellow", orange: "orange", red: "red" },
  },
  classes: {
    roja: { name: "Red", meaning: "Highest priority among districts" },
    naranja: { name: "Orange", meaning: "High priority" },
    amarilla: { name: "Yellow", meaning: "Medium priority" },
    verde: { name: "Green", meaning: "Lowest priority. It does not mean nobody needs help" },
  },
  levels: {
    roja: {
      name: "Very high",
      group: "Very high structural risk",
      meaning: "Highest structural fragility among districts. Not an alert.",
    },
    naranja: {
      name: "High",
      group: "High structural risk",
      meaning: "High structural fragility. Not an alert.",
    },
    amarilla: {
      name: "Medium",
      group: "Medium structural risk",
      meaning: "Medium structural fragility. Not an alert.",
    },
    verde: {
      name: "Low",
      group: "Low structural risk",
      meaning: "Lowest structural fragility. It does not mean nobody needs help.",
    },
  },
  levelsNote: "With no earthquake there is no alert: this scale measures fragility, not emergency.",
  dimensions: {
    hazard_and_exposure: { name: "Hazard and exposure", short: "Hazard", abbr: "H&E" },
    vulnerability: { name: "Vulnerability", short: "Vulnerab.", abbr: "V" },
    lack_of_coping_capacity: { name: "Lack of coping capacity", short: "Capacity", abbr: "LCC" },
  },
  honesty: {
    title: "How to read this",
    ranking: "This is a relative ranking of territories (districts), not of people.",
    noVictims: "It never reports victims or casualties.",
    exposure:
      "Exposed population is an estimate of residents in the area, not of people affected.",
    gaps:
      "Declared gaps: it does not measure construction quality; urban poverty is under-captured; it covers earthquakes only.",
    relative:
      "A score is a position among {total} districts, not a measure of damage.",
    attributionLabel: "Data",
    more: "How to read this and its limits",
  },
  list: {
    ariaLabel: "Districts ordered by priority",
    search: "Search district",
    districts: "districts",
    exposed: "exposed (est.)",
    exposedUnknown: "no estimate",
    withheld: "Withheld",
    withheldHint: "Withheld under statistical secrecy; not published.",
    empty: "No district matches.",
    loading: "Computing priorities…",
    loadFailed: "Could not load the district ranking.",
    retry: "Retry",
    showMore: "Show more",
    scoreZero: "0 · see why",
    classFilterAll: "All",
    classFilterLabel: "Filter by level",
    sortLabel: "Sort by",
    sortScore: "Priority",
    sortExposed: "Exposed",
    sortName: "Name",
    scopeLabel: "Scope",
    scopeZone: "{department} only",
    scopeCountry: "Whole country",
    showing: "Showing {shown} of {total} districts",
    nationalRank: "Rank is national, among {total} districts.",
    columnRank: "Rank",
    columnDistrict: "District",
    columnScore: "Relative priority",
    clearFilters: "Clear filters",
    rankLabel: "rank {rank}",
    exposedNone: "no estimate",
    zeroShort: "0 · see why",
  },
  detail: {
    rankOf: "Rank {rank} of {total}",
    score: "Priority",
    driversTitle: "What weighs most in the priority",
    technicalTitle: "Indicators, Sphere needs and sources",
    dimensionRank: "rank {rank}",
    dimensionAbsent: "not used in this mode",
    baselineNoHazard: "Baseline has no earthquake, so no hazard is measured.",
    withheldDimension: "Withheld",
    zeroTitle: "Why the score is 0",
    zeroHazard:
      "The earthquake did not reach this district with relevant intensity. Hazard is 0 and, because dimensions are multiplied, the score is 0. It does not say the district is poor or well prepared.",
    zeroFloor:
      "It ranked last among districts on \"{dimension}\". That makes it the best of {total} on that aspect; it does not mean \"no risk\". Because dimensions are multiplied, a 0 cancels the score.",
    zeroGeneric:
      "One dimension is 0 and cancels the score. A 0 here is a relative position, not an absence of risk.",
    auditTitle: "Audit",
    auditRule:
      "The composed score is the geometric mean of the {count} dimensions, equally weighted; it runs from 0 to 10.",
    auditReference: "Score with INFORM rescaling (reference only, does not rank)",
    auditLoading: "Loading audit…",
    auditFailed: "Could not load the audit for this district.",
    exposedTitle: "Exposed population (estimate)",
    exposedNote:
      "Estimated residents in strongly shaken areas. Not victims and not people affected.",
    sphereTitle: "Sphere minimum requirement",
    sphereNote:
      "This is the minimum Sphere sets for that estimated population. It is not what must be delivered and is not compared with available resources, which are not measured.",
    sphereNotComputed:
      "Sphere minimum requirements are computed only for orange and red districts and need the population exposed to an event.",
    waterPerDay: "Water per day",
    waterHeat: "Water per day (extreme heat)",
    taps: "Minimum taps",
    waterDistance: "Water point within",
    food: "Food per day",
    shelter: "Shelter area",
    withheldWhole:
      "This district is not published: its data is withheld under statistical secrecy.",
    placesTitle: "Places",
    placesBody:
      "The data does not yet assign places (schools, clinics, shelters) to a district. You can see the places of the work zone.",
    placesOpen: "See places in {zone}",
  },
  exportDialog: EXPORT_EN,
  sheet: {
    reportTitle: "Territory prioritization report",
    mapTitle: "Priority districts map",
    print: "Print / save as PDF",
    close: "Close",
    generatedAt: "Generated",
    columnRank: "Rank",
    columnDistrict: "District",
    columnClass: "Class",
    columnScore: "Priority (0-10)",
    columnExposed: "Exposed (est.)",
    columnSphere: "Sphere minimum",
    legend: "Legend",
    north: "N",
    sphereCompact: "{water} L water/day · {food} kcal/day · {shelter} m² shelter",
  },
  xlsx: {
    sheetRanking: "Ranking",
    sheetContext: "Context and limits",
    population: "Population",
    department: "Department",
    maxShaking: "Peak shaking",
    withheldRow: "Withheld",
    modeRow: "Mode",
    eventRow: "Event",
    shakemapRow: "Shaking map processed",
    pagerRow: "PAGER alert (range)",
    generatedRow: "Generated",
    sourceRow: "Data",
    limitationsRow: "Limits",
    fileStem: "district-prioritization",
  },
};

/** Fill `{name}` tokens; an unknown token is left visible rather than dropped. */
export function fillMessage(
  template: string,
  values: Record<string, string | number>,
): string {
  return template.replace(/\{(\w+)\}/g, (token, key: string) =>
    key in values ? String(values[key]) : token,
  );
}

/** Statement of provenance every export and view carries. */
export const DATA_ATTRIBUTION = "BCR/ONEC, CPV 2024";

/** Copy for a document language, which an export may choose independently of the UI. */
export function communityMessages(lang: "es" | "en"): CommunityMessages {
  return lang === "es" ? COMMUNITY_ES : COMMUNITY_EN;
}
