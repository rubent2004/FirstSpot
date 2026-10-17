import type { AlertClassKey, DimensionKey } from "../modules/community-triage/triageModel";

/**
 * Copy for the community triage view and its exports.
 *
 * Every sentence here is written for an operator under pressure: no backend
 * field names, no INFORM jargon. `{name}` tokens are filled by `fillMessage`.
 */
export interface CommunityMessages {
  tabs: { label: string; territories: string; places: string };
  title: string;
  subtitle: string;
  mode: {
    label: string;
    baseline: string;
    event: string;
    baselineMeaning: string;
    eventMeaning: string;
    switchToBaseline: string;
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
  dimensions: Record<DimensionKey, { name: string; short: string }>;
  honesty: {
    title: string;
    ranking: string;
    noVictims: string;
    exposure: string;
    gaps: string;
    relative: string;
    attributionLabel: string;
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
  };
  detail: {
    back: string;
    rankOf: string;
    score: string;
    dimensionsTitle: string;
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
  };
  exports: {
    menu: string;
    excel: string;
    report: string;
    map: string;
    offlineNote: string;
    excelFailed: string;
    unavailable: string;
  };
  sheet: {
    reportTitle: string;
    mapTitle: string;
    print: string;
    close: string;
    generatedAt: string;
    topNote: string;
    columnRank: string;
    columnDistrict: string;
    columnClass: string;
    columnScore: string;
    columnExposed: string;
    columnSphere: string;
    legend: string;
    north: string;
    noGeometry: string;
    epicentre: string;
    priorityList: string;
    baselineMapNote: string;
    sphereCompact: string;
  };
  xlsx: {
    sheetRanking: string;
    sheetContext: string;
    population: string;
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
  tabs: { label: "Vista", territories: "Territorios", places: "Lugares" },
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
  dimensions: {
    hazard_and_exposure: { name: "Amenaza y exposición", short: "Amenaza" },
    vulnerability: { name: "Vulnerabilidad", short: "Vulnerab." },
    lack_of_coping_capacity: { name: "Falta de capacidad de respuesta", short: "Capacidad" },
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
  },
  detail: {
    back: "Volver a la lista",
    rankOf: "Puesto {rank} de {total}",
    score: "Prioridad",
    dimensionsTitle: "Puntaje por dimensión",
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
  },
  exports: {
    menu: "Exportar",
    excel: "Excel (.xlsx)",
    report: "Informe para imprimir o PDF",
    map: "Mapa para imprimir",
    offlineNote: "Se generan en este equipo, sin conexión.",
    excelFailed: "No se pudo generar el archivo Excel.",
    unavailable: "Aún no hay un ranking cargado para exportar.",
  },
  sheet: {
    reportTitle: "Informe de priorización de territorios",
    mapTitle: "Mapa de distritos prioritarios",
    print: "Imprimir / guardar PDF",
    close: "Cerrar",
    generatedAt: "Generado",
    topNote: "Primeros {shown} de {total} distritos. La lista completa está en el Excel.",
    columnRank: "Puesto",
    columnDistrict: "Distrito",
    columnClass: "Clase",
    columnScore: "Prioridad (0-10)",
    columnExposed: "Expuestos (est.)",
    columnSphere: "Mínimo Sphere",
    legend: "Leyenda",
    north: "N",
    noGeometry:
      "La API no entrega polígonos de distritos, por eso el mapa no pinta territorios: muestra el epicentro (modo evento) y la lista de distritos prioritarios.",
    epicentre: "Epicentro",
    priorityList: "Distritos de clase roja y naranja",
    baselineMapNote: "Línea base: no hay epicentro que ubicar.",
    sphereCompact: "{water} L de agua/día · {food} kcal/día · {shelter} m² de albergue",
  },
  xlsx: {
    sheetRanking: "Ranking",
    sheetContext: "Contexto y límites",
    population: "Población",
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
  tabs: { label: "View", territories: "Territories", places: "Places" },
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
  dimensions: {
    hazard_and_exposure: { name: "Hazard and exposure", short: "Hazard" },
    vulnerability: { name: "Vulnerability", short: "Vulnerab." },
    lack_of_coping_capacity: { name: "Lack of coping capacity", short: "Capacity" },
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
  },
  detail: {
    back: "Back to list",
    rankOf: "Rank {rank} of {total}",
    score: "Priority",
    dimensionsTitle: "Score by dimension",
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
  },
  exports: {
    menu: "Export",
    excel: "Excel (.xlsx)",
    report: "Printable report / PDF",
    map: "Printable map",
    offlineNote: "Generated on this device, no connection needed.",
    excelFailed: "Could not generate the Excel file.",
    unavailable: "No ranking is loaded yet, so there is nothing to export.",
  },
  sheet: {
    reportTitle: "Territory prioritization report",
    mapTitle: "Priority districts map",
    print: "Print / save as PDF",
    close: "Close",
    generatedAt: "Generated",
    topNote: "First {shown} of {total} districts. The full list is in the Excel export.",
    columnRank: "Rank",
    columnDistrict: "District",
    columnClass: "Class",
    columnScore: "Priority (0-10)",
    columnExposed: "Exposed (est.)",
    columnSphere: "Sphere minimum",
    legend: "Legend",
    north: "N",
    noGeometry:
      "The API does not provide district polygons, so the map does not paint territories: it shows the epicentre (event mode) and the list of priority districts.",
    epicentre: "Epicentre",
    priorityList: "Red and orange districts",
    baselineMapNote: "Baseline: there is no epicentre to locate.",
    sphereCompact: "{water} L water/day · {food} kcal/day · {shelter} m² shelter",
  },
  xlsx: {
    sheetRanking: "Ranking",
    sheetContext: "Context and limits",
    population: "Population",
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
