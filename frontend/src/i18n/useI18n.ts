import { computed, ref } from "vue";
import esLocale from "element-plus/es/locale/lang/es";
import enLocale from "element-plus/es/locale/lang/en";
import type {
  AttentionStatus,
  PlaceCategory,
  VulnerabilityGroup,
} from "../api/client";
import {
  containsOsmIdentifier,
  isSynthesisedPlaceName,
  placeLocatingHint,
  stripOsmIdentifier,
} from "../utils/placeName";

export type AppLocale = "es" | "en";

const STORAGE_KEY = "geo_prioridad_locale";

function resolveInitialLocale(): AppLocale {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "es" || saved === "en") {
        return saved;
      }
    }
  } catch {
    // Ignore storage errors in restricted environments
  }
  return "es";
}

const currentLocale = ref<AppLocale>(resolveInitialLocale());

export interface I18nMessages {
  header: {
    badge: string;
    title: string;
    subtitle: string;
    zoneLabel: string;
    zonePlaceholder: string;
    syncBtn: string;
    syncingBtn: string;
    radiusModeLabel: string;
    radiusActive: string;
    radiusOff: string;
    radiusHint: string;
    langToggleTooltip: string;
    liveSource: string;
    fallbackSource: string;
    syncedSuffix: string;
    allZonesFilter: string;
  };
  kpis: {
    activeZone: string;
    placesSuffix: string;
    criticalUrgency: string;
    criticalSub: string;
    pendingTriage: string;
    pendingSub: string;
    inProgress: string;
    inProgressSub: string;
    attended: string;
    attendedSub: string;
    vulnerablePop: string;
    peopleSuffix: string;
    clickToFilter: string;
  };
  map: {
    radiusBannerPrefix: string;
    radiusBannerSuffix: string;
    heatmapLayer: string;
    markersLayer: string;
    hazardsLayer: string;
    recenterZone: string;
    streetTiles: string;
    tacticalTiles: string;
    legendTitle: string;
    legendGradientTitle: string;
    legendLow: string;
    legendMedium: string;
    legendHigh: string;
    legendCritical: string;
    legendAxesTitle: string;
    legendStatusTitle: string;
    tooltipScore: string;
    tooltipStatus: string;
    tooltipCluster: string;
    tooltipClickHint: string;
  };
  hazardCard: {
    alertTitle: string;
    seismicEvent: string;
    weatherEvent: string;
    generalEvent: string;
    drillBadge: string;
    realBadge: string;
    criticalAlert: string;
    highAlert: string;
    mediumAlert: string;
    infoAlert: string;
    magnitude: string;
    depth: string;
    radius: string;
    elapsed: string;
    agencyLabel: string;
    guidanceTitle: string;
    guidanceText: string;
    hotlinesTitle: string;
    hotline911: string;
    hotlineCivilProtection: string;
    hotlineRedCross: string;
    hotlineFirefighters: string;
    focusEpicenterBtn: string;
    copyReportBtn: string;
    reportCopied: string;
    closeBtn: string;
    clickToOpenCard: string;
  };
  queue: {
    title: string;
    subtitle: string;
    resetFilters: string;
    searchPlaceholder: string;
    allGroups: string;
    allCategories: string;
    statusAll: string;
    statusPending: string;
    statusInProgress: string;
    statusAttended: string;
    showAttendedHeatmap: string;
    emptyText: string;
    colRank: string;
    colScore: string;
    colPlace: string;
    colUrgency: string;
    colExposed: string;
    colStatus: string;
    colAction: string;
    triageAction: string;
    quickDispatch: string;
    showingCount: string;
    /** Explains that the priority figure only means anything relatively. */
    priorityHint: string;
    /** Completes an urgency reading for assistive technology, e.g. "4 of 5". */
    urgencyScaleSuffix: string;
    /** Narrows the queue that is already on screen, without a round trip. */
    filterPlaceholder: string;
    clearFilter: string;
    filterEmpty: string;
    /** Reveals the next slice of the queue. */
    revealMore: string;
    updating: string;
    /** Nearby vulnerable places, said in words rather than as "+16 en 500m". */
    nearbyOne: string;
    nearbyMany: string;
    nearbyHint: string;
  };
  exposure: {
    queueLabel: string;
    panelTitle: string;
    radiusLabel: string;
    noCoverage: string;
    withheld: string;
    unknownHint: string;
    methodNote: string;
    olderAdults: string;
    youngChildren: string;
    personsWithDisability: string;
  };
  drawer: {
    title: string;
    subtitle: string;
    projectedScore: string;
    currentScore: string;
    scoreDelta: string;
    formulaBreakdown: string;
    weightBase: string;
    urgencyMult: string;
    popBonus: string;
    clusterBonus: string;
    attendedAttenuation: string;
    metadataTitle: string;
    fieldName: string;
    fieldCategory: string;
    fieldGroup: string;
    fieldZoneCoords: string;
    fieldCluster: string;
    clusterNeighborsText: string;
    formStatusLabel: string;
    statusPendingBtn: string;
    statusInProgressBtn: string;
    statusAttendedBtn: string;
    formUrgencyLabel: string;
    formPopulationLabel: string;
    populationPresets: string;
    formNotesLabel: string;
    notesPlaceholder: string;
    quickNotesLabel: string;
    quickNotes: string[];
    cancelBtn: string;
    saveBtn: string;
    rawTagsTitle: string;
    navigateMaps: string;
    navigateWaze: string;
    copyCoords: string;
    coordsCopied: string;
    openRouteTitle: string;
    severityCritical: string;
    severityHigh: string;
    severityMedium: string;
    severityLow: string;
  };
  categories: Record<PlaceCategory, string>;
  groups: Record<VulnerabilityGroup, string>;
  statuses: Record<AttentionStatus, string>;
  urgency: Record<number, string>;
  /**
   * What to call a place the map has no name for. The backend substitutes the
   * raw OSM identifier here; these read as something a dispatcher would say out
   * loud over the radio.
   */
  unnamedPlaces: Record<PlaceCategory, string>;
  /** Used when the category itself is unrecognised. */
  unnamedPlaceFallback: string;
}

export const MESSAGES: Record<AppLocale, I18nMessages> = {
  es: {
    header: {
      badge: "PROTECCIÓN CIVIL • EL SALVADOR",
      title: "FirstSpot",
      subtitle:
        "Centro de Mando Geoespacial para Triaje Humanitario y Despacho Institucional",
      zoneLabel: "Zona Operativa (El Salvador)",
      zonePlaceholder: "Seleccionar municipio",
      syncBtn: "Sincronizar con Overpass",
      syncingBtn: "Sincronizando OSM...",
      radiusModeLabel: "Escaneo por Radio en Mapa",
      radiusActive: "Activo",
      radiusOff: "Inactivo",
      radiusHint: "Haga clic en el mapa para escanear radio",
      langToggleTooltip: "Cambiar idioma (ES / EN)",
      liveSource: "Overpass en Vivo",
      fallbackSource: "Semilla Local Resiliente",
      syncedSuffix: "puntos sincronizados",
      allZonesFilter: "Filtro activo",
    },
    kpis: {
      activeZone: "Lugares",
      placesSuffix: "lugares",
      criticalUrgency: "Críticos",
      criticalSub: "Prioridad inmediata",
      pendingTriage: "Pendientes",
      pendingSub: "Sin brigada asignada",
      inProgress: "En Atención",
      inProgressSub: "Brigadas en terreno",
      attended: "Atendidos",
      attendedSub: "Asegurados",
      vulnerablePop: "Pob. Est.",
      peopleSuffix: "pers.",
      clickToFilter: "Clic para filtrar cola",
    },
    map: {
      radiusBannerPrefix:
        "MODO RADAR ACTIVO: Haga clic en cualquier punto del mapa para sincronizar lugares en un radio de",
      radiusBannerSuffix: "en la zona seleccionada.",
      heatmapLayer: "Mapa de Calor",
      markersLayer: "Marcadores Tácticos",
      hazardsLayer: "Amenazas y Desastres",
      recenterZone: "Centrar Zona",
      streetTiles: "Mapa Claro",
      tacticalTiles: "Modo Oscuro",
      legendTitle: "Leyenda Cartográfica",
      legendGradientTitle: "Gradiente de Prioridad (Mapa de Calor)",
      legendLow: "Baja",
      legendMedium: "Media",
      legendHigh: "Alta",
      legendCritical: "Crítica",
      legendAxesTitle: "Ejes de Vulnerabilidad",
      legendStatusTitle: "Borde de Estado Operativo",
      tooltipScore: "Puntaje",
      tooltipStatus: "Estado",
      tooltipCluster: "Clúster 500m",
      tooltipClickHint: "Clic para abrir triaje y despacho",
    },
    hazardCard: {
      alertTitle: "Ficha de Emergencia y Desastre",
      seismicEvent: "Evento Sísmico",
      weatherEvent: "Alerta Meteorológica",
      generalEvent: "Alerta de Fenómeno Natural",
      drillBadge: "Simulacro Institucional",
      realBadge: "Evento Sísmico Activo",
      criticalAlert: "Alerta Roja • Nivel Crítico",
      highAlert: "Alerta Naranja • Riesgo Alto",
      mediumAlert: "Alerta Amarilla • Precaución",
      infoAlert: "Alerta Verde • Informativo",
      magnitude: "Magnitud Richter",
      depth: "Profundidad Focal",
      radius: "Radio de Afectación",
      elapsed: "Tiempo Transcurrido",
      agencyLabel: "Organismo de Monitoreo Oficial",
      guidanceTitle: "Protocolo para Instituciones, ONGs y Comunidad",
      guidanceText:
        "Verificar centros de salud, escuelas y albergues dentro del radio de afectación. Desplegar brigadas de auxilio, mantener despejadas vías de evacuación y utilizar canales oficiales de comunicación.",
      hotlinesTitle: "Líneas Directas de Auxilio Inmediato",
      hotline911: "Emergencias Nacionales",
      hotlineCivilProtection: "Protección Civil",
      hotlineRedCross: "Cruz Roja Salvadoreña",
      hotlineFirefighters: "Cuerpo de Bomberos",
      focusEpicenterBtn: "Centrar Epicentro",
      copyReportBtn: "Copiar Reporte",
      reportCopied: "¡Reporte Copiado al Portapapeles!",
      closeBtn: "Cerrar Ficha",
      clickToOpenCard: "Haz clic para abrir ficha de emergencia y protocolos",
    },
    queue: {
      title: "Cola de Despacho Institucional",
      subtitle:
        "Lugares priorizados por nivel de urgencia, población vulnerable y concentración de riesgo en el sector",
      resetFilters: "Limpiar Filtros",
      searchPlaceholder: "Buscar hospital, escuela, albergue...",
      allGroups: "Todos los ejes de vulnerabilidad",
      allCategories: "Todas las categorías",
      statusAll: "Todos",
      statusPending: "Pendientes",
      statusInProgress: "En Atención",
      statusAttended: "Atendidos",
      showAttendedHeatmap: "Incluir atendidos en calor",
      emptyText:
        "No se encontraron lugares vulnerables con los filtros actuales.",
      colRank: "#",
      colScore: "Prioridad",
      colPlace: "Lugar y Categoría",
      colUrgency: "Urgencia",
      colExposed: "Pob. estimada",
      colStatus: "Estado",
      colAction: "Acción",
      triageAction: "Evaluar",
      quickDispatch: "Despachar",
      showingCount: "lugares priorizados",
      priorityHint:
        "Puntaje de prioridad, comparado con el más alto de la cola actual.",
      urgencyScaleSuffix: "de 5",
      filterPlaceholder: "Filtrar esta cola",
      clearFilter: "Limpiar el filtro",
      filterEmpty: "Ningún lugar de la cola coincide con ese filtro.",
      revealMore: "Mostrar más lugares",
      updating: "Actualizando…",
      nearbyOne: "lugar cerca",
      nearbyMany: "lugares cerca",
      nearbyHint:
        "Otros lugares vulnerables a menos de 500 metros de este punto: una sola salida puede cubrirlos.",
    },
    exposure: {
      queueLabel: "pob. estimada",
      panelTitle: "Población Expuesta Estimada",
      radiusLabel: "Radio",
      noCoverage: "sin cobertura censal",
      withheld: "dato reservado",
      unknownHint: "Valor desconocido, no cero.",
      methodNote:
        "Estimación por ponderación areal de polígonos censales; se asume densidad uniforme dentro de cada unidad.",
      olderAdults: "65 y más",
      youngChildren: "Menores de 5",
      personsWithDisability: "Con discapacidad",
    },
    drawer: {
      title: "Ficha de Despacho y Evaluación Operativa",
      subtitle:
        "Registro oficial de respuesta de emergencia y triaje de protección civil",
      projectedScore: "Índice de Prioridad de Respuesta",
      currentScore: "Score Inicial",
      scoreDelta: "Variación",
      formulaBreakdown: "Factores Clave de Vulnerabilidad y Riesgo",
      weightBase: "Tipo de Establecimiento",
      urgencyMult: "Nivel de Urgencia",
      popBonus: "Población a Proteger",
      clusterBonus: "Entorno Crítico (500m)",
      attendedAttenuation: "Atenuación por Aseguramiento",
      metadataTitle: "Ubicación e Información del Establecimiento",
      fieldName: "Nombre",
      fieldCategory: "Clasificación",
      fieldGroup: "Población Objetivo",
      fieldZoneCoords: "Municipio y Coordenadas",
      fieldCluster: "Concentración en Entorno",
      clusterNeighborsText: "lugares vulnerables en radio de impacto inmediato (500m)",
      formStatusLabel: "Estado de Despacho y Operación en Terreno",
      statusPendingBtn: "Pendiente de Despacho",
      statusInProgressBtn: "Unidad en Camino / Terreno",
      statusAttendedBtn: "Atendido y Asegurado",
      formUrgencyLabel: "Nivel de Urgencia de la Emergencia",
      formPopulationLabel: "Población Estimada a Resguardar / Evacuar",
      populationPresets: "Incrementos rápidos:",
      formNotesLabel: "Bitácora Operativa de Incidente",
      notesPlaceholder:
        "Describa unidad o brigada asignada, estado de las vías, necesidades médicas, víveres o rescate...",
      quickNotesLabel: "Reportes rápidos de terreno:",
      quickNotes: [
        "Unidad de rescate despachada",
        "Evacuación urgente requerida",
        "Sin energía eléctrica ni agua",
        "Albergue verificado y operativo",
        "Vía de acceso parcialmente bloqueada",
        "Sector atendido y seguro",
      ],
      cancelBtn: "Cerrar",
      saveBtn: "Guardar Evaluación y Despacho",
      rawTagsTitle: "Detalles Técnicos Adicionales (OSM)",
      navigateMaps: "Google Maps",
      navigateWaze: "Waze",
      copyCoords: "Copiar GPS",
      coordsCopied: "¡Copiado!",
      openRouteTitle: "Navegar hacia el lugar:",
      severityCritical: "Prioridad 1 - Crítica Vital",
      severityHigh: "Prioridad 2 - Alta",
      severityMedium: "Prioridad 3 - Moderada",
      severityLow: "Prioridad 4 - Preventiva",
    },
    categories: {
      hospital: "Hospital",
      clinic: "Clínica / Unidad de Salud",
      social_facility: "Albergue / Asilo / Centro Social",
      kindergarten: "Kínder / Parvularia",
      school: "Centro Escolar",
      community_centre: "Casa Comunal / Centro Comunitario",
      university: "Universidad",
      pharmacy: "Farmacia",
      commercial_hub: "Mercado / Centro Comercial",
      place_of_worship: "Templo / Centro Religioso",
    },
    groups: {
      health: "Salud Crítica",
      education: "Educación y Niñez",
      shelter: "Albergues y Asistencia",
      concurrency: "Alta Concurrencia",
    },
    statuses: {
      pending: "Pendiente",
      in_progress: "En Atención",
      attended: "Atendido",
    },
    urgency: {
      1: "Baja",
      2: "Moderada",
      3: "Media",
      4: "Alta",
      5: "Crítica",
    },
    unnamedPlaces: {
      hospital: "Hospital sin nombre",
      clinic: "Clínica sin nombre",
      social_facility: "Albergue sin nombre",
      kindergarten: "Parvularia sin nombre",
      school: "Centro escolar sin nombre",
      community_centre: "Casa comunal sin nombre",
      university: "Universidad sin nombre",
      pharmacy: "Farmacia sin nombre",
      commercial_hub: "Centro comercial sin nombre",
      place_of_worship: "Templo sin nombre",
    },
    unnamedPlaceFallback: "Lugar sin nombre",
  },
  en: {
    header: {
      badge: "CIVIL DEFENSE • EL SALVADOR",
      title: "FirstSpot",
      subtitle:
        "Humanitarian Geospatial Prioritization & Institutional Dispatch Command",
      zoneLabel: "Target Zone (El Salvador)",
      zonePlaceholder: "Select municipality",
      syncBtn: "Sync Zone with Overpass",
      syncingBtn: "Syncing OSM...",
      radiusModeLabel: "Map Click Radius Sync",
      radiusActive: "Active",
      radiusOff: "Off",
      radiusHint: "Click anywhere on map to scan radius",
      langToggleTooltip: "Switch language (ES / EN)",
      liveSource: "Live Overpass",
      fallbackSource: "Offline Seed",
      syncedSuffix: "synced",
      allZonesFilter: "Active filter",
    },
    kpis: {
      activeZone: "Places",
      placesSuffix: "places",
      criticalUrgency: "Critical",
      criticalSub: "Immediate priority",
      pendingTriage: "Pending",
      pendingSub: "Awaiting assignment",
      inProgress: "In Progress",
      inProgressSub: "Units deployed",
      attended: "Attended",
      attendedSub: "Secured",
      vulnerablePop: "Est. Pop.",
      peopleSuffix: "ppl",
      clickToFilter: "Click to filter queue",
    },
    map: {
      radiusBannerPrefix:
        "RADAR MODE ACTIVE: Click anywhere on the map to sync places within a",
      radiusBannerSuffix: "radius in the selected zone.",
      heatmapLayer: "Priority Heatmap Layer",
      markersLayer: "Location Markers",
      hazardsLayer: "Hazards & Disasters",
      recenterZone: "Center Zone",
      streetTiles: "Light Map",
      tacticalTiles: "Dark Mode",
      legendTitle: "Map Legend",
      legendGradientTitle: "Heatmap Priority Gradient",
      legendLow: "Low",
      legendMedium: "Medium",
      legendHigh: "High",
      legendCritical: "Critical",
      legendAxesTitle: "Vulnerability Axes",
      legendStatusTitle: "Operational Status Ring",
      tooltipScore: "Score",
      tooltipStatus: "Status",
      tooltipCluster: "500m Cluster",
      tooltipClickHint: "Click to open triage & dispatch",
    },
    hazardCard: {
      alertTitle: "Emergency & Hazard Assessment",
      seismicEvent: "Seismic Event",
      weatherEvent: "Severe Weather Alert",
      generalEvent: "Natural Hazard Alert",
      drillBadge: "Institutional Drill",
      realBadge: "Active Natural Event",
      criticalAlert: "Red Alert • Critical Level",
      highAlert: "Orange Alert • High Risk",
      mediumAlert: "Yellow Alert • Caution",
      infoAlert: "Green Alert • Informational",
      magnitude: "Richter Magnitude",
      depth: "Focal Depth",
      radius: "Impact Radius",
      elapsed: "Elapsed Time",
      agencyLabel: "Official Monitoring Agency",
      guidanceTitle: "Response Protocol for NGOs & First Responders",
      guidanceText:
        "Check health facilities, schools, and temporary shelters inside the impact radius. Mobilize rapid response brigades, clear evacuation routes, and follow verified emergency protocols.",
      hotlinesTitle: "Immediate Emergency Dispatch Hotlines",
      hotline911: "National 911 Emergency",
      hotlineCivilProtection: "Civil Protection",
      hotlineRedCross: "Red Cross",
      hotlineFirefighters: "Fire & Rescue Department",
      focusEpicenterBtn: "Center Epicenter",
      copyReportBtn: "Copy Report",
      reportCopied: "Report copied to clipboard!",
      closeBtn: "Close Card",
      clickToOpenCard: "Click to view emergency protocol card",
    },
    queue: {
      title: "Institutional Dispatch Queue",
      subtitle:
        "Places prioritized by urgency level, vulnerable population, and local risk concentration",
      resetFilters: "Reset Filters",
      searchPlaceholder: "Search location by name...",
      allGroups: "All Vulnerability Groups",
      allCategories: "All Categories",
      statusAll: "All",
      statusPending: "Pending",
      statusInProgress: "In Progress",
      statusAttended: "Attended",
      showAttendedHeatmap: "Show Attended in Heatmap",
      emptyText: "No vulnerable places match the current filters.",
      colRank: "#",
      colScore: "Priority",
      colPlace: "Place & Category",
      colUrgency: "Urgency",
      colExposed: "Exposed pop.",
      colStatus: "Status",
      colAction: "Action",
      triageAction: "Triage",
      quickDispatch: "Dispatch",
      showingCount: "prioritized places",
      priorityHint:
        "Priority score, compared with the highest in the current queue.",
      urgencyScaleSuffix: "of 5",
      filterPlaceholder: "Filter this queue",
      clearFilter: "Clear the filter",
      filterEmpty: "No place in the queue matches that filter.",
      revealMore: "Show more places",
      updating: "Updating…",
      nearbyOne: "place nearby",
      nearbyMany: "places nearby",
      nearbyHint:
        "Other vulnerable places within 500 metres of this point: one trip can cover them.",
    },
    exposure: {
      queueLabel: "est. population",
      panelTitle: "Estimated Exposed Population",
      radiusLabel: "Radius",
      noCoverage: "no census coverage",
      withheld: "figure withheld",
      unknownHint: "Value unknown, not zero.",
      methodNote:
        "Estimate by areal weighting of census polygons; uniform density assumed within a unit.",
      olderAdults: "65 and over",
      youngChildren: "Under 5",
      personsWithDisability: "With disability",
    },
    drawer: {
      title: "Emergency Dispatch & Operational Triage",
      subtitle:
        "Official civil defense response log and humanitarian triage assessment",
      projectedScore: "Response Priority Index",
      currentScore: "Initial Score",
      scoreDelta: "Score Delta",
      formulaBreakdown: "Core Vulnerability & Risk Factors",
      weightBase: "Facility Type",
      urgencyMult: "Urgency Level",
      popBonus: "Population at Risk",
      clusterBonus: "Critical Surroundings (500m)",
      attendedAttenuation: "Attended Attenuation",
      metadataTitle: "Location & Facility Information",
      fieldName: "Name",
      fieldCategory: "Facility Category",
      fieldGroup: "Target Population",
      fieldZoneCoords: "Municipality & Coordinates",
      fieldCluster: "Cluster Concentration",
      clusterNeighborsText: "vulnerable facilities within immediate impact radius (500m)",
      formStatusLabel: "Dispatch Status & Field Operations",
      statusPendingBtn: "Pending Dispatch",
      statusInProgressBtn: "Units En Route / On Site",
      statusAttendedBtn: "Attended & Secured",
      formUrgencyLabel: "Emergency Urgency Level",
      formPopulationLabel: "Estimated People to Shelter / Evacuate",
      populationPresets: "Quick increments:",
      formNotesLabel: "Operational Incident Log",
      notesPlaceholder:
        "Describe assigned unit, road conditions, medical supply needs, food or rescue status...",
      quickNotesLabel: "Quick field status reports:",
      quickNotes: [
        "Rescue brigade dispatched",
        "Urgent evacuation required",
        "Power and water outages",
        "Shelter verified and active",
        "Access road partially blocked",
        "Sector secured and cleared",
      ],
      cancelBtn: "Close",
      saveBtn: "Save Assessment & Dispatch",
      rawTagsTitle: "Additional Technical Details (OSM)",
      navigateMaps: "Google Maps",
      navigateWaze: "Waze",
      copyCoords: "Copy GPS",
      coordsCopied: "Copied!",
      openRouteTitle: "Navigate to site:",
      severityCritical: "Priority 1 - Life Critical",
      severityHigh: "Priority 2 - High",
      severityMedium: "Priority 3 - Moderate",
      severityLow: "Priority 4 - Preventive",
    },
    categories: {
      hospital: "Hospital",
      clinic: "Medical Clinic",
      social_facility: "Social Facility / Shelter",
      kindergarten: "Kindergarten",
      school: "School",
      community_centre: "Community Center",
      university: "University",
      pharmacy: "Pharmacy",
      commercial_hub: "Commercial Hub / Market",
      place_of_worship: "Place of Worship",
    },
    groups: {
      health: "Critical Health",
      education: "Education & Children",
      shelter: "Shelters & Care",
      concurrency: "High Concurrency",
    },
    statuses: {
      pending: "Pending",
      in_progress: "In Progress",
      attended: "Attended",
    },
    urgency: {
      1: "Low",
      2: "Moderate",
      3: "Medium",
      4: "High",
      5: "Critical",
    },
    unnamedPlaces: {
      hospital: "Unnamed hospital",
      clinic: "Unnamed clinic",
      social_facility: "Unnamed shelter",
      kindergarten: "Unnamed kindergarten",
      school: "Unnamed school",
      community_centre: "Unnamed community centre",
      university: "Unnamed university",
      pharmacy: "Unnamed pharmacy",
      commercial_hub: "Unnamed commercial hub",
      place_of_worship: "Unnamed place of worship",
    },
    unnamedPlaceFallback: "Unnamed place",
  },
};

export function setAppLocale(locale: AppLocale): void {
  currentLocale.value = locale;
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(STORAGE_KEY, locale);
    }
  } catch {
    // Ignore storage errors
  }
}

export function toggleAppLocale(): void {
  setAppLocale(currentLocale.value === "es" ? "en" : "es");
}

/** The minimum a place has to carry for its name to be resolved. */
export interface PlaceNameSource {
  name: string;
  category?: string;
  osm_tags?: Record<string, unknown>;
}

/** A place name split into what to show and how to locate it. */
export interface PlaceNameDescription {
  /** Human-facing label. Never contains a raw OSM identifier. */
  readonly label: string;
  /** Where to find an unnamed place, when the tags say; otherwise null. */
  readonly hint: string | null;
  /** True when the label is our wording rather than a real place name. */
  readonly isUnnamed: boolean;
}

/** Localized name straight from the OSM tags, when the data carries one. */
function taggedPlaceName(
  place: PlaceNameSource,
  locale: AppLocale,
): string | null {
  const tags = place.osm_tags;
  if (!tags || typeof tags !== "object") return null;
  const tag = tags[locale === "es" ? "name:es" : "name:en"];
  if (typeof tag !== "string") return null;
  const trimmed = tag.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/**
 * Resolve what to call a place.
 *
 * Preference order is the localized OSM tag, then the stored name, then our own
 * wording for an unnamed place of that category. Every branch is checked for a
 * raw OSM identifier before it is returned, so no data shape — present or
 * future — can put a database key in front of an operator.
 */
export function describePlaceName(
  place: PlaceNameSource,
  locale: AppLocale = currentLocale.value,
): PlaceNameDescription {
  const messages = MESSAGES[locale];
  const category = place.category as PlaceCategory | undefined;
  const unnamedLabel =
    (category && messages.unnamedPlaces[category]) ||
    messages.unnamedPlaceFallback;

  for (const candidate of [taggedPlaceName(place, locale), place.name?.trim()]) {
    if (!candidate) continue;
    if (isSynthesisedPlaceName(candidate)) break;
    if (!containsOsmIdentifier(candidate)) {
      return { label: candidate, hint: null, isUnnamed: false };
    }
    const stripped = stripOsmIdentifier(candidate);
    if (stripped.length > 0) {
      return { label: stripped, hint: null, isUnnamed: false };
    }
    break;
  }

  return {
    label: unnamedLabel,
    hint: placeLocatingHint(place),
    isUnnamed: true,
  };
}

/** The label alone, for the many call sites that only render a string. */
export function getLocalizedPlaceName(
  place: PlaceNameSource,
  locale: AppLocale = currentLocale.value,
): string {
  return describePlaceName(place, locale).label;
}

export function useI18n() {
  const t = computed<I18nMessages>(() => MESSAGES[currentLocale.value]);
  const elementLocale = computed(() =>
    currentLocale.value === "es" ? esLocale : enLocale,
  );

  return {
    locale: currentLocale,
    t,
    elementLocale,
    setLocale: setAppLocale,
    toggleLocale: toggleAppLocale,
    localizePlaceName: (place: PlaceNameSource) =>
      getLocalizedPlaceName(place, currentLocale.value),
    describePlace: (place: PlaceNameSource) =>
      describePlaceName(place, currentLocale.value),
  };
}
