import type { AppLocale } from "../../../i18n/useI18n";

/**
 * Locale-aware hazard text formatting.
 *
 * These helpers are pure: they turn raw agency feed strings (USGS titles,
 * source identifiers, magnitudes, depths) into operator-readable copy. They are
 * shared by the hazard modal in the template and by the map tooltips built in
 * `useHazardLayer`, so they intentionally carry no reactive state and take the
 * locale as an argument instead of reading it from `useI18n`.
 */

const COMPASS_MAP_ES: Record<string, string> = {
  N: "Norte",
  S: "Sur",
  E: "Este",
  W: "Oeste",
  NE: "Noreste",
  NW: "Noroeste",
  SE: "Sureste",
  SW: "Suroeste",
  NNE: "Nor-Noreste",
  NNW: "Nor-Noroeste",
  SSE: "Sur-Sureste",
  SSW: "Sur-Suroeste",
  ENE: "Este-Noreste",
  WNW: "Oeste-Noroeste",
  ESE: "Este-Sureste",
  WSW: "Oeste-Suroeste",
};

export function humanizeHazardTitle(rawTitle: string, loc: AppLocale): string {
  if (!rawTitle) return "";
  const cleaned = rawTitle
    .replace(/\s*\((?:Simulacro|Simulation Drill)\)/gi, "")
    .replace(/\s*-\s*(?:Simulacro|Simulation Drill)/gi, "")
    .trim();
  const m = cleaned.match(
    /^M\s*([\d.]+)\s*-\s*(\d+(?:\.\d+)?\s*km)\s+([A-Za-z]+)\s+of\s+(.+)$/i,
  );
  if (m) {
    const [, mag, dist, dirCode, place] = m;
    const cleanPlace = place.trim();
    if (loc === "es") {
      const dirEs = COMPASS_MAP_ES[dirCode.toUpperCase()] ?? dirCode;
      return `Sismo M ${mag} • ${dist} al ${dirEs} de ${cleanPlace}`;
    }
    return `M ${mag} Earthquake • ${dist} ${dirCode.toUpperCase()} of ${cleanPlace}`;
  }
  const mSimple = cleaned.match(/^M\s*([\d.]+)\s*-\s*(.+)$/i);
  if (mSimple) {
    const [, mag, rest] = mSimple;
    return loc === "es"
      ? `Sismo M ${mag} • ${rest.trim()}`
      : `M ${mag} Earthquake • ${rest.trim()}`;
  }
  return cleaned.replace(/USGS|API|NASA|EONET/gi, "").trim();
}

export function getHazardAgencyLabel(source: string, loc: AppLocale): string {
  const s = (source || "").toLowerCase();
  let agency =
    loc === "es" ? "Red de Monitoreo Oficial" : "Official Monitoring Network";
  if (s.includes("usgs") || s.includes("earthquake") || s.includes("sismo")) {
    agency =
      loc === "es" ? "Red Sismológica Oficial" : "Official Seismic Network";
  } else if (
    s.includes("meteo") ||
    s.includes("weather") ||
    s.includes("clima")
  ) {
    agency =
      loc === "es"
        ? "Servicio Meteorológico Nacional"
        : "National Weather Service";
  } else if (
    s.includes("nasa") ||
    s.includes("eonet") ||
    s.includes("satelital")
  ) {
    agency =
      loc === "es"
        ? "Vigilancia Satelital de Emergencias"
        : "Emergency Satellite Surveillance";
  }
  return agency;
}

export function getMagnitudeLabel(mag: number | null, loc: AppLocale): string {
  if (mag === null) return "";
  if (mag >= 7.0)
    return loc === "es"
      ? "Terremoto Mayor / Destructivo"
      : "Major Earthquake";
  if (mag >= 6.0)
    return loc === "es"
      ? "Sismo Fuerte (Riesgo Estructural)"
      : "Strong (Structural Risk)";
  if (mag >= 5.0)
    return loc === "es"
      ? "Sismo Moderado (Ampliamente Sentido)"
      : "Moderate (Widely Felt)";
  if (mag >= 4.0)
    return loc === "es" ? "Sismo Leve (Perceptible)" : "Light (Noticeable)";
  return loc === "es" ? "Microsismo Menor" : "Minor tremor";
}

export function getDepthLabel(depth: number | null, loc: AppLocale): string {
  if (depth === null) return "";
  if (depth <= 60)
    return loc === "es"
      ? "Superficial (<60 km - Mayor impacto)"
      : "Shallow (<60 km)";
  if (depth <= 300)
    return loc === "es"
      ? "Intermedio (60-300 km)"
      : "Intermediate (60-300 km)";
  return loc === "es" ? "Profundo (>300 km)" : "Deep (>300 km)";
}
