import L from "leaflet";
import type { HazardEventRead } from "../../../api/client";
import { renderIcon0SvgString } from "../../../components/icons0Registry";
import { useI18n } from "../../../i18n/useI18n";
import { formatExactTime, formatRelativeTime } from "../../../utils/date";
import { ALERT_RAMP_HEX } from "./canvasColors";
import { getHazardAgencyLabel, humanizeHazardTitle } from "./hazardPresentation";

/**
 * Tooltip glyphs. Tooltip bodies are HTML strings, so the icons are rendered
 * once here instead of using emoji, which would be the only saturated,
 * non-token color left on the map chrome.
 */
const CLOCK_TIP_ICON = renderIcon0SvgString(
  "clock",
  11,
  "var(--eoc-text-secondary)",
);
const SIREN_TIP_ICON = renderIcon0SvgString(
  "siren",
  12,
  "var(--eoc-critical)",
);
const HINT_TIP_ICON = renderIcon0SvgString(
  "chevron_right",
  11,
  "var(--eoc-text-label)",
);

/** Smallest impact radius, in metres, that stays visible at operational zoom. */
const MIN_IMPACT_RADIUS_M = 1500;

export interface UseHazardLayerOptions {
  getMap: () => L.Map | null;
  /** Active hazard events to overlay. */
  hazardEvents: () => HazardEventRead[] | undefined;
  /** Operator toggle for the hazards layer. */
  enabled: () => boolean;
  /** Called when the operator clicks an impact circle or an epicenter pin. */
  onSelectHazard: (event: HazardEventRead) => void;
}

/**
 * Owns the hazard overlay group: one dashed radar circle per event covering its
 * impact radius, plus a pulsing epicenter pin where `L.divIcon` is available.
 *
 * Both surfaces open the same hazard card, so both stop event propagation to
 * keep the click from reaching the map's own radius-selection handler.
 */
export function useHazardLayer(options: UseHazardLayerOptions) {
  const { locale, t } = useI18n();

  let hazardsGroup: L.LayerGroup | null = null;

  /** Creates the hazard group on the map. Call order decides paint order. */
  function attachTo(map: L.Map): void {
    hazardsGroup = L.layerGroup().addTo(map);
  }

  function updateHazardsLayer(): void {
    if (!hazardsGroup || !options.getMap()) return;
    hazardsGroup.clearLayers();
    const hazardEvents = options.hazardEvents();
    if (!options.enabled() || !hazardEvents || hazardEvents.length === 0) return;

    for (const ev of hazardEvents) {
      const ringColor = ALERT_RAMP_HEX[ev.alert_level] ?? ALERT_RAMP_HEX.red;
      const timeStr = formatRelativeTime(ev.occurred_at, locale.value);
      const exactTimeStr = formatExactTime(ev.occurred_at, locale.value);
      const timeDisplay = exactTimeStr ? `${timeStr} (${exactTimeStr})` : timeStr;
      const humanTitle = humanizeHazardTitle(ev.title, locale.value);
      const agencyLabel = getHazardAgencyLabel(ev.source, locale.value);

      const impactCircle = L.circle([ev.latitude, ev.longitude], {
        radius: Math.max(ev.radius_km * 1000, MIN_IMPACT_RADIUS_M),
        color: ringColor,
        weight: 2,
        dashArray: "6, 6",
        fillColor: ringColor,
        fillOpacity: 0.14,
      });
      impactCircle.bindTooltip(
        `<div class="map-tip">` +
          `<strong class="map-tip-title">${humanTitle}</strong><br/>` +
          `<span class="map-tip-meta">${agencyLabel}</span><br/>` +
          `<span class="map-tip-row">${CLOCK_TIP_ICON}<b class="eoc-numeric">${timeDisplay}</b></span><br/>` +
          `<span class="eoc-numeric">Radio: <b>${ev.radius_km} km</b>` +
          (ev.magnitude !== null ? ` • M${ev.magnitude.toFixed(1)}` : "") +
          (ev.depth_km !== null ? ` • Prof: ${ev.depth_km.toFixed(0)} km` : "") +
          `</span><br/>` +
          `<em class="map-tip-row map-tip-hint">${HINT_TIP_ICON}${t.value.hazardCard.clickToOpenCard}</em>` +
          `</div>`,
        { direction: "top" },
      );
      impactCircle.on("click", (e) => {
        if (L.DomEvent?.stopPropagation) {
          L.DomEvent.stopPropagation(e);
        }
        options.onSelectHazard(ev);
      });
      impactCircle.addTo(hazardsGroup);

      if (typeof L.divIcon === "function") {
        const svgStr = renderIcon0SvgString("siren", 16, "#ffffff");
        const hazIcon = L.divIcon({
          className: "tactical-div-icon-wrapper",
          iconSize: [32, 32],
          iconAnchor: [16, 16],
          html: `<div class="tactical-map-pin tactical-pin-pulse" style="width:32px;height:32px;background:${ringColor};border:2px solid var(--eoc-warning);cursor:pointer;">${svgStr}</div>`,
        });
        const centerMarker = L.marker([ev.latitude, ev.longitude], {
          icon: hazIcon,
        });
        centerMarker.bindTooltip(
          `<div class="map-tip">` +
            `<strong class="map-tip-row map-tip-title">${SIREN_TIP_ICON}${humanTitle}</strong><br/>` +
            `<span class="map-tip-meta">${agencyLabel}</span><br/>` +
            `<span class="map-tip-row">${CLOCK_TIP_ICON}<span class="eoc-numeric">${timeDisplay}</span></span><br/>` +
            `<em class="map-tip-row map-tip-hint">${HINT_TIP_ICON}${t.value.hazardCard.clickToOpenCard}</em>` +
            `</div>`,
          { direction: "top", offset: [0, -12] },
        );
        centerMarker.on("click", (e) => {
          if (L.DomEvent?.stopPropagation) {
            L.DomEvent.stopPropagation(e);
          }
          options.onSelectHazard(ev);
        });
        centerMarker.addTo(hazardsGroup);
      }
    }
  }

  return { attachTo, updateHazardsLayer };
}
