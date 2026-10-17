import type { AppLocale } from "./useI18n";

/**
 * Copy for the presenter-driven guided tour. It is projected while someone
 * narrates, so every step is a short title and at most two short sentences.
 * Every claim here must be backed by the system; see docs/demo/guion-video.md.
 */
export type TourStepId =
  | "opening"
  | "zone"
  | "baseline"
  | "mode"
  | "eventTop"
  | "detail"
  | "sphere"
  | "places"
  | "placeSummary"
  | "placeLog"
  | "placeAccess"
  | "exportFormat"
  | "exportMap"
  | "closing";

export type TourSkipReason = "anchor" | "data" | "event" | "district" | "sphere" | "zone" | "place";

interface StepCopy {
  title: string;
  body: string;
}

export interface TourMessages {
  next: string;
  previous: string;
  done: string;
  close: string;
  /** "{{current}} / {{total}}" is filled in by Driver.js. */
  progress: string;
  steps: Record<TourStepId, StepCopy>;
  /** Said instead of the step body when the shown data calls for it. */
  variants: { placeLogEmpty: string };
  /** Shown centred, in place of a step that cannot be shown right now. */
  skipped: { title: string; reasons: Record<TourSkipReason, string> };
}

const ES: TourMessages = {
  next: "Siguiente",
  previous: "Anterior",
  done: "Terminar",
  close: "Cerrar el recorrido",
  progress: "{{current}} / {{total}}",
  steps: {
    opening: {
      title: "FirstSpot",
      body: "Ordena territorios y lugares después de un desastre para decidir a quién atender primero. Usa datos públicos y un método citado: INFORM.",
    },
    zone: {
      title: "Zona de trabajo",
      body: "Primero se elige el área de operación. Aquí, Sonsonate.",
    },
    baseline: {
      title: "Línea base y sus límites",
      body: "Antes de un evento, los distritos se ordenan por vulnerabilidad y falta de capacidad de respuesta, con el Censo 2024 y OpenStreetMap. Es un orden relativo, nunca un conteo de víctimas.",
    },
    mode: {
      title: "Modo evento",
      body: "Pasamos a un sismo histórico real, el del 13 de febrero de 2001 (M6,6), y a la vista nacional. El orden se recalcula con el ShakeMap de USGS.",
    },
    eventTop: {
      title: "Quién va primero",
      body: "Suben los distritos cercanos al epicentro. Los colores de alerta, por niveles de Protección Civil, aparecen solo ahora.",
    },
    detail: {
      title: "Por qué es el primero",
      body: "El detalle separa tres dimensiones: amenaza y exposición, vulnerabilidad y falta de capacidad de respuesta. Cada posición queda justificada.",
    },
    sphere: {
      title: "Qué enviar",
      body: "Requerimiento mínimo Esfera de agua, alimento y refugio para la población expuesta estimada. Es una referencia mínima, no una entrega.",
    },
    places: {
      title: "Lugares de la zona",
      body: "La cola indica qué lugares concretos atender y el mapa lleva al lugar marcado. Lo desconocido se muestra como desconocido, nunca como cero.",
    },
    placeSummary: {
      title: "Ficha del lugar",
      body: "Población estimada alrededor, con adultos mayores, niñez y discapacidad, y su estado de atención: pendiente, en atención o atendido. Un dato desconocido aparece con guion, nunca como cero.",
    },
    placeLog: {
      title: "Bitácora de coordinación",
      body: "Cada acción queda con su autor y su organización: unidad en camino, en el lugar, solicitar apoyo, atención resuelta. Todas las organizaciones ven la misma bitácora y saben quién ya va en camino.",
    },
    placeAccess: {
      title: "Quién puede registrar",
      body: "Registrar exige iniciar sesión con una organización verificada. La verificación identifica a la organización; no confirma la exactitud del reporte.",
    },
    exportFormat: {
      title: "Exportar",
      body: "Cuatro formatos: Excel, CSV, ranking en PDF y mapa de la vista actual. El alcance muestra cuántas filas salen, y el nombre del archivo lleva modo, fecha y evento.",
    },
    exportMap: {
      title: "Mapa para el equipo de campo",
      body: "Plantillas Resumen, Completo o Despacho de un lugar, con vista previa en vivo; los límites y la atribución BCR/ONEC siempre van. Se genera en el navegador, listo para entregar.",
    },
    closing: {
      title: "Listo para operar",
      body: "Funciona en el teléfono, con contraste y teclado probados. Datos: BCR/ONEC CPV 2024, USGS y OpenStreetMap.",
    },
  },
  variants: {
    placeLogEmpty:
      "Cada acción queda con su autor y su organización: unidad en camino, en el lugar, solicitar apoyo, atención resuelta. Este lugar aún no tiene acciones registradas.",
  },
  skipped: {
    title: "Paso no disponible",
    reasons: {
      anchor: "Esta parte de la interfaz no está visible en esta pantalla.",
      data: "Los datos de este paso no están disponibles ahora; el servidor no respondió.",
      event: "El sismo histórico de demostración no está disponible ahora, o no tiene ShakeMap.",
      district: "No hay un distrito priorizado que abrir con los datos actuales.",
      sphere: "Este distrito no tiene requerimiento Esfera calculado: solo se calcula para niveles roja y naranja.",
      zone: "La zona de demostración Sonsonate no está disponible ahora.",
      place: "No hay lugares cargados en esta zona; el servidor no devolvió ninguno.",
    },
  },
};

const EN: TourMessages = {
  next: "Next",
  previous: "Previous",
  done: "Finish",
  close: "Close the tour",
  progress: "{{current}} / {{total}}",
  steps: {
    opening: {
      title: "FirstSpot",
      body: "It ranks territories and places after a disaster so coordinators decide whom to attend first. It uses public data and a cited method: INFORM.",
    },
    zone: {
      title: "Work zone",
      body: "First, choose the area of operation. Here, Sonsonate.",
    },
    baseline: {
      title: "Baseline and its limits",
      body: "Before an event, districts are ranked by vulnerability and lack of coping capacity, from the 2024 census and OpenStreetMap. It is a relative ranking, never a count of victims.",
    },
    mode: {
      title: "Event mode",
      body: "We switch to a real historical earthquake, 13 February 2001 (M6.6), and to the national view. The ranking is recomputed from the USGS ShakeMap.",
    },
    eventTop: {
      title: "Who goes first",
      body: "Districts near the epicentre rise. The alert colours, by Civil Protection level, appear only now.",
    },
    detail: {
      title: "Why it ranks first",
      body: "The detail splits three dimensions: hazard and exposure, vulnerability and lack of coping capacity. Every position is justified.",
    },
    sphere: {
      title: "What to send",
      body: "Sphere minimum requirement for water, food and shelter for the estimated exposed population. It is a minimum reference, not a delivery.",
    },
    places: {
      title: "Places in the zone",
      body: "The queue shows which concrete places to attend, and the map goes to the marked place. Unknown is shown as unknown, never as zero.",
    },
    placeSummary: {
      title: "Place record",
      body: "Estimated population around it, with older adults, young children and disability, and its response status: pending, in progress or attended. An unknown figure shows a dash, never a zero.",
    },
    placeLog: {
      title: "Coordination log",
      body: "Every action keeps its author and organization: unit en route, unit on scene, request support, response resolved. Every organization sees the same log and knows who is already on the way.",
    },
    placeAccess: {
      title: "Who can record",
      body: "Recording requires signing in with a verified organization. Verification identifies the organization; it does not confirm the report is accurate.",
    },
    exportFormat: {
      title: "Export",
      body: "Four formats: Excel, CSV, the ranking as PDF and the map of the current view. The scope shows how many rows go out, and the file name carries mode, date and event.",
    },
    exportMap: {
      title: "A map for the field team",
      body: "Summary, Complete or Single-place dispatch templates, with a live preview; the limits and the BCR/ONEC attribution always travel. It is generated in the browser, ready to hand over.",
    },
    closing: {
      title: "Ready to operate",
      body: "It works on a phone, with tested contrast and keyboard use. Data: BCR/ONEC CPV 2024, USGS and OpenStreetMap.",
    },
  },
  variants: {
    placeLogEmpty:
      "Every action keeps its author and organization: unit en route, unit on scene, request support, response resolved. This place has no recorded actions yet.",
  },
  skipped: {
    title: "Step not available",
    reasons: {
      anchor: "This part of the interface is not visible on this screen.",
      data: "The data for this step is not available right now; the server did not answer.",
      event: "The historical demo earthquake is not available right now, or it has no ShakeMap.",
      district: "There is no prioritized district to open with the current data.",
      sphere: "This district has no Sphere requirement: it is computed only for red and orange levels.",
      zone: "The Sonsonate demo zone is not available right now.",
      place: "No places are loaded for this zone; the server returned none.",
    },
  },
};

export function tourMessages(locale: AppLocale): TourMessages {
  return locale === "es" ? ES : EN;
}
