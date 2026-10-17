import type {
  PlaceColumn,
  PresetId,
  SectionId,
} from "../modules/community-triage/mapPrint/mapPrintModel";

/** Copy for the "map of the current view" printout and its content options. */
export interface MapPrintMessages {
  title: string;
  titleNoZone: string;
  contentLegend: string;
  presetsLabel: string;
  presets: Record<PresetId, string>;
  sections: Record<SectionId, { name: string; description: string }>;
  placePopulationName: string;
  reasons: {
    noPlaces: string;
    noSelectedPlace: string;
    noHazards: string;
    noWeather: string;
    noDistrict: string;
    noCensus: string;
    notSalvadoran: string;
    locked: string;
  };
  exposure: { noCoverage: string; withheld: string };
  placeColumns: Record<PlaceColumn, string>;
  topPlaces: string;
  placesUnit: string;
  columnsLegend: string;
  mapToggles: { legend: string; scale: string; north: string };
  notesLabel: string;
  notesPlaceholder: string;
  selectedCount: string;
  previewLabel: string;
  previewMapPlaceholder: string;
  sheet: {
    placesHeading: string;
    rank: string;
    place: string;
    countsHeading: string;
    byUrgency: string;
    byStatus: string;
    placeDetailHeading: string;
    exposedHeading: string;
    olderAdults: string;
    youngChildren: string;
    disability: string;
    activityHeading: string;
    noActivity: string;
    activityTypes: Record<string, string>;
    hazardsHeading: string;
    radius: string;
    weatherHeading: string;
    temperature: string;
    precipitation: string;
    wind: string;
    gusts: string;
    districtHeading: string;
    contactsHeading: string;
    contactNames: Record<"national" | "civilProtection" | "redCross" | "fire", string>;
    notesHeading: string;
    limitsHeading: string;
    coverageOut: string;
    rankingNote: string;
    legendHeading: string;
    legendHeat: string;
    legendPlaces: string;
    legendHazards: string;
    legendRadius: string;
    legendSelected: string;
    scale: string;
    basemapNote: string;
    viewLine: string;
    people: string;
  };
}

export const MAP_PRINT_ES: MapPrintMessages = {
  title: "{zone} — Mapa de prioridad",
  titleNoZone: "Mapa de prioridad",
  contentLegend: "Contenido de la impresión",
  presetsLabel: "Plantillas",
  presets: { summary: "Resumen", complete: "Completo", dispatch: "Despacho de un lugar" },
  sections: {
    map: { name: "Mapa de la vista actual", description: "Siempre incluido" },
    places: { name: "Lugares por prioridad", description: "Los primeros N, con las columnas que elijas" },
    placeDetail: { name: "Detalle del lugar seleccionado", description: "Datos, población estimada y bitácora" },
    counts: { name: "Conteos", description: "Por urgencia y por estado de atención" },
    districtDetail: { name: "Detalle del distrito seleccionado", description: "Dimensiones y mínimos Sphere" },
    hazards: { name: "Amenazas activas", description: "USGS y EONET cerca de la zona" },
    weather: { name: "Clima actual", description: "Open-Meteo" },
    contacts: { name: "Líneas de emergencia", description: "911, Protección Civil, Cruz Roja, Bomberos" },
    notes: { name: "Notas del operador", description: "Se imprimen tal como las escribes" },
    limits: { name: "Límites y atribución", description: "Siempre incluido" },
  },
  placePopulationName: "Población estimada",
  reasons: {
    noPlaces: "No hay lugares en esta vista",
    noSelectedPlace: "Ningún lugar seleccionado",
    noHazards: "Sin amenazas activas cerca de esta zona",
    noWeather: "Sin datos de clima",
    noDistrict: "Ningún distrito seleccionado",
    noCensus: "Sin cobertura censal en esta zona",
    notSalvadoran: "Los números disponibles son de El Salvador",
    locked: "Siempre incluido",
  },
  exposure: { noCoverage: "sin cobertura censal", withheld: "dato reservado" },
  placeColumns: {
    category: "Categoría",
    urgency: "Urgencia",
    population: "Población est.",
    status: "Atención",
    nearby: "Lugares cerca",
  },
  topPlaces: "Mostrar los primeros",
  placesUnit: "lugares",
  columnsLegend: "Columnas de la lista",
  mapToggles: { legend: "Leyenda", scale: "Escala", north: "Norte" },
  notesLabel: "Notas del operador",
  notesPlaceholder: "Se imprimen tal como las escribes",
  selectedCount: "{n} secciones seleccionadas",
  previewLabel: "Vista previa",
  previewMapPlaceholder: "Mapa de la vista actual",
  sheet: {
    placesHeading: "Lugares por prioridad",
    rank: "N.º",
    place: "Lugar",
    countsHeading: "Conteos",
    byUrgency: "Por urgencia",
    byStatus: "Por estado de atención",
    placeDetailHeading: "Lugar seleccionado",
    exposedHeading: "Población expuesta (estimación)",
    olderAdults: "Adultos mayores",
    youngChildren: "Niñez pequeña",
    disability: "Personas con discapacidad",
    activityHeading: "Bitácora de coordinación",
    noActivity: "Aún no hay acciones registradas.",
    activityTypes: {
      reported: "Condición reportada",
      en_route: "Unidad en camino",
      on_scene: "Unidad en el lugar",
      needs_support: "Apoyo solicitado",
      resource_available: "Recurso disponible",
      update: "Evaluación actualizada",
      resolved: "Atención resuelta",
    },
    hazardsHeading: "Amenazas activas cerca de la zona",
    radius: "radio {km} km",
    weatherHeading: "Clima actual",
    temperature: "Temperatura",
    precipitation: "Precipitación",
    wind: "Viento",
    gusts: "Ráfagas",
    districtHeading: "Distrito seleccionado",
    contactsHeading: "Líneas de emergencia (El Salvador)",
    contactNames: {
      national: "Emergencias Nacionales",
      civilProtection: "Protección Civil",
      redCross: "Cruz Roja Salvadoreña",
      fire: "Cuerpo de Bomberos",
    },
    notesHeading: "Notas del operador",
    limitsHeading: "Límites y atribución",
    coverageOut:
      "Esta zona está fuera de la cobertura del censo y del índice de distritos de El Salvador: no hay población estimada ni ranking de distritos para ella.",
    rankingNote:
      "El ranking de distritos no se imprime en este mapa: los datos no indican qué distritos están dentro de la vista. Está en «Ranking nacional de distritos».",
    legendHeading: "Leyenda",
    legendHeat: "Calor: concentración de vulnerabilidad",
    legendPlaces: "Lugares, por grupo de vulnerabilidad",
    legendHazards: "Amenaza activa y su radio",
    legendRadius: "Radio de búsqueda",
    legendSelected: "Lugar seleccionado",
    scale: "Escala",
    basemapNote: "Fondo claro para imprimir",
    viewLine: "Centro {lat}, {lon} · zoom {zoom}",
    people: "personas",
  },
};

export const MAP_PRINT_EN: MapPrintMessages = {
  title: "{zone} — Priority map",
  titleNoZone: "Priority map",
  contentLegend: "Print contents",
  presetsLabel: "Templates",
  presets: { summary: "Summary", complete: "Complete", dispatch: "Single-place dispatch" },
  sections: {
    map: { name: "Map of the current view", description: "Always included" },
    places: { name: "Places by priority", description: "The first N, with the columns you pick" },
    placeDetail: { name: "Selected place detail", description: "Facts, estimated population and log" },
    counts: { name: "Counts", description: "By urgency and by attention status" },
    districtDetail: { name: "Selected district detail", description: "Dimensions and Sphere minimums" },
    hazards: { name: "Active hazards", description: "USGS and EONET near the zone" },
    weather: { name: "Current weather", description: "Open-Meteo" },
    contacts: { name: "Emergency lines", description: "911, Civil Protection, Red Cross, Fire" },
    notes: { name: "Operator notes", description: "Printed exactly as you type them" },
    limits: { name: "Limits and attribution", description: "Always included" },
  },
  placePopulationName: "Estimated population",
  reasons: {
    noPlaces: "No places in this view",
    noSelectedPlace: "No place selected",
    noHazards: "No active hazards near this zone",
    noWeather: "No weather data",
    noDistrict: "No district selected",
    noCensus: "No census coverage in this area",
    notSalvadoran: "The numbers available are for El Salvador",
    locked: "Always included",
  },
  exposure: { noCoverage: "no census coverage", withheld: "withheld" },
  placeColumns: {
    category: "Category",
    urgency: "Urgency",
    population: "Est. population",
    status: "Status",
    nearby: "Nearby places",
  },
  topPlaces: "Show the first",
  placesUnit: "places",
  columnsLegend: "List columns",
  mapToggles: { legend: "Legend", scale: "Scale", north: "North" },
  notesLabel: "Operator notes",
  notesPlaceholder: "Printed exactly as you type them",
  selectedCount: "{n} sections selected",
  previewLabel: "Preview",
  previewMapPlaceholder: "Map of the current view",
  sheet: {
    placesHeading: "Places by priority",
    rank: "No.",
    place: "Place",
    countsHeading: "Counts",
    byUrgency: "By urgency",
    byStatus: "By attention status",
    placeDetailHeading: "Selected place",
    exposedHeading: "Exposed population (estimate)",
    olderAdults: "Older adults",
    youngChildren: "Young children",
    disability: "People with disability",
    activityHeading: "Coordination log",
    noActivity: "No actions have been recorded yet.",
    activityTypes: {
      reported: "Condition reported",
      en_route: "Unit en route",
      on_scene: "Unit on scene",
      needs_support: "Support requested",
      resource_available: "Resource available",
      update: "Assessment updated",
      resolved: "Response resolved",
    },
    hazardsHeading: "Active hazards near the zone",
    radius: "radius {km} km",
    weatherHeading: "Current weather",
    temperature: "Temperature",
    precipitation: "Precipitation",
    wind: "Wind",
    gusts: "Gusts",
    districtHeading: "Selected district",
    contactsHeading: "Emergency lines (El Salvador)",
    contactNames: {
      national: "National emergencies",
      civilProtection: "Civil Protection",
      redCross: "Salvadoran Red Cross",
      fire: "Fire and Rescue",
    },
    notesHeading: "Operator notes",
    limitsHeading: "Limits and attribution",
    coverageOut:
      "This area is outside the coverage of the El Salvador census and district index: there is no estimated population and no district ranking for it.",
    rankingNote:
      "The district ranking is not printed on this map: the data does not say which districts are inside the view. It is in “National district ranking”.",
    legendHeading: "Legend",
    legendHeat: "Heat: concentration of vulnerability",
    legendPlaces: "Places, by vulnerability group",
    legendHazards: "Active hazard and its radius",
    legendRadius: "Search radius",
    legendSelected: "Selected place",
    scale: "Scale",
    basemapNote: "Light basemap for printing",
    viewLine: "Centre {lat}, {lon} · zoom {zoom}",
    people: "people",
  },
};
