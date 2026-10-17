import L from "leaflet";
import {
  GROUP_COLORS,
  GROUP_COLOR_FALLBACK,
  type PlaceCategory,
  type PlaceRead,
} from "../../../api/client";
import {
  CATEGORY_ICON_MAP,
  renderIcon0SvgString,
} from "../../../components/icons0Registry";
import { useI18n } from "../../../i18n/useI18n";
import { STATUS_RING } from "./canvasColors";

/**
 * A group of places collapsed into one pin, as produced by
 * `useMarkerClustering`. It carries both the geographic centroid used to place
 * the pin and the screen-space anchor the proximity pass matched against.
 */
export interface ClusterBucket {
  places: PlaceRead[];
  centroidLat: number;
  centroidLon: number;
  screenX: number;
  screenY: number;
  maxUrgency: number;
  hasCritical: boolean;
}

/**
 * Tooltip bodies are HTML strings handed to Leaflet, so place names coming from
 * OSM data are escaped before interpolation.
 */
const escapeHtml = (value: string) =>
  value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character] ?? character);

export interface UseMapMarkersOptions {
  getMap: () => L.Map | null;
  /** Currently selected place, which renders larger and keeps a pinned tooltip. */
  selectedPlace: () => PlaceRead | null;
  /** Called when the operator clicks a single-place pin. */
  onSelectPlace: (place: PlaceRead) => void;
}

/**
 * Owns the marker layer group and how a marker looks.
 *
 * Pins are `divIcon` markers so the CSS token system and the pulse animations
 * apply, with a `circleMarker` fallback for environments without `L.divIcon`.
 * That fallback is canvas-rendered, which is why the status ring needs a hex
 * literal there but may use a `var()` token in the HTML pin.
 *
 * Deciding *which* markers to draw belongs to `useMarkerClustering`; this
 * composable only renders what it is handed.
 */
export function useMapMarkers(options: UseMapMarkersOptions) {
  const { locale, t, localizePlaceName } = useI18n();

  let markersGroup: L.LayerGroup | null = null;

  /** Creates the marker group on the map. Call order decides paint order. */
  function attachTo(map: L.Map): void {
    markersGroup = L.layerGroup().addTo(map);
  }

  function clearMarkers(): void {
    markersGroup?.clearLayers();
  }

  function hasMarkerGroup(): boolean {
    return markersGroup !== null;
  }

  function renderSinglePlaceMarker(place: PlaceRead): void {
    if (!markersGroup) return;
    const isSelected = options.selectedPlace()?.id === place.id;
    const fillColor = GROUP_COLORS[place.vulnerability_group] ?? GROUP_COLOR_FALLBACK;
    const statusRing = STATUS_RING[place.attention_status];
    const isCriticalPending =
      place.urgency_level >= 4 && place.attention_status !== "attended";

    const hasDivIcon = typeof L.divIcon === "function";
    let marker: L.Layer & {
      bindTooltip: L.CircleMarker["bindTooltip"];
      on: L.CircleMarker["on"];
      addTo: L.CircleMarker["addTo"];
      setZIndexOffset?: (offset: number) => unknown;
      bringToFront?: () => unknown;
    };

    if (hasDivIcon) {
      const iconKey =
        CATEGORY_ICON_MAP[place.category as PlaceCategory] ?? "map_pin";
      const svgStr = renderIcon0SvgString(
        iconKey,
        isSelected ? 16 : 13,
        "#ffffff",
      );
      const sizePx = isSelected ? 38 : 26;
      const opacity = place.attention_status === "attended" ? 0.55 : 0.96;
      const markerClasses = [
        isCriticalPending ? "tactical-pin-pulse" : "",
        isSelected ? "tactical-pin-selected" : "",
      ].filter(Boolean).join(" ");

      const divIcon = L.divIcon({
        className: "tactical-div-icon-wrapper",
        iconSize: [sizePx, sizePx],
        iconAnchor: [sizePx / 2, sizePx / 2],
        html: `<div class="tactical-map-pin ${markerClasses}" style="width:${sizePx}px;height:${sizePx}px;background:${fillColor};border:2px solid ${statusRing.token};opacity:${opacity};">${svgStr}</div>`,
      });

      marker = L.marker([place.latitude, place.longitude], {
        icon: divIcon,
        zIndexOffset: isSelected ? 1000 : 0,
      }) as unknown as typeof marker;
    } else {
      marker = L.circleMarker([place.latitude, place.longitude], {
        radius: isSelected ? 11 : 7,
        fillColor,
        color: statusRing.hex,
        weight: isSelected ? 3 : 2,
        opacity: 1,
        fillOpacity: place.attention_status === "attended" ? 0.45 : 0.9,
      });
    }
    if (isSelected) {
      marker.setZIndexOffset?.(1000);
      marker.bringToFront?.();
    }

    const displayName = localizePlaceName(place);
    const categoryLabel =
      t.value.categories[place.category as PlaceCategory] ?? place.category;
    const statusLabel =
      t.value.statuses[place.attention_status] ?? place.attention_status;
    const selectedBadge = isSelected
      ? `<span class="map-tip-badge">${renderIcon0SvgString("locate_fixed", 11, "var(--eoc-accent-text)")}${locale.value === "es" ? "LUGAR SELECCIONADO" : "SELECTED PLACE"}</span><br/>`
      : "";

    marker.bindTooltip(
      `<div class="map-tip">` +
        selectedBadge +
        `<strong class="map-tip-title">${escapeHtml(displayName)}</strong><br/>` +
        `<span class="map-tip-meta">${escapeHtml(categoryLabel)}</span> • ${t.value.map.tooltipScore}: <b class="eoc-numeric">${place.priority_score.toFixed(1)}</b><br/>` +
        `${t.value.map.tooltipStatus}: <b>${escapeHtml(statusLabel)}</b> • ${t.value.map.tooltipCluster}: <b class="eoc-numeric">+${place.nearby_places_count}</b><br/>` +
        `<em class="map-tip-hint">${t.value.map.tooltipClickHint}</em>` +
        `</div>`,
      {
        direction: "top",
        offset: [0, isSelected ? -18 : -10],
        permanent: isSelected,
        className: isSelected ? "selected-place-tooltip" : "",
      },
    );

    marker.on("click", () => {
      options.onSelectPlace(place);
    });

    marker.addTo(markersGroup);
  }

  function renderClusterMarker(bucket: ClusterBucket): void {
    if (!markersGroup || !options.getMap()) return;
    const count = bucket.places.length;
    const isSelectedCluster = bucket.places.some(
      (p) => p.id === options.selectedPlace()?.id,
    );
    // Semantic ladder only: blue stays reserved for selection, so the calmest
    // bucket reads as "all clear" instead of borrowing the operational accent.
    const clusterColor = bucket.hasCritical
      ? "var(--eoc-critical)"
      : bucket.maxUrgency >= 4
        ? "var(--eoc-warning)"
        : bucket.maxUrgency >= 3
          ? "var(--eoc-info)"
          : "var(--eoc-success)";
    const size = Math.min(26 + Math.log2(count) * 4.5, 42);

    const divIcon = L.divIcon({
      className: "tactical-cluster-icon-wrapper",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      html: `<div class="tactical-cluster-pin ${bucket.hasCritical ? 'cluster-pulse-critical' : ''} ${isSelectedCluster ? 'cluster-selected' : ''}" style="width:${size}px;height:${size}px;background:${clusterColor};"><span class="cluster-count eoc-numeric">${count}</span></div>`,
    });

    const marker = L.marker([bucket.centroidLat, bucket.centroidLon], {
      icon: divIcon,
    });

    const topNames = bucket.places
      .slice(0, 3)
      .map((p) => localizePlaceName(p))
      .join("<br/>• ");

    marker.bindTooltip(
      `<div class="map-tip">` +
        `<strong class="map-tip-title">Cluster: <span class="eoc-numeric">${count}</span> ${t.value.kpis.placesSuffix}</strong><br/>` +
        `<span class="map-tip-meta">• ${topNames}${count > 3 ? `<br/><em>(+${count - 3} más)</em>` : ""}</span><br/>` +
        `<em class="map-tip-hint">${locale.value === 'es' ? 'Clic para acercar' : 'Click to zoom in'}</em>` +
        `</div>`,
      { direction: "top", offset: [0, -10] },
    );

    marker.on("click", () => {
      const map = options.getMap();
      const curZoom = map?.getZoom() ?? 14;
      map?.setView(
        [bucket.centroidLat, bucket.centroidLon],
        Math.min(curZoom + 2, 17),
        { animate: true },
      );
    });

    marker.addTo(markersGroup);
  }

  return {
    attachTo,
    clearMarkers,
    hasMarkerGroup,
    renderSinglePlaceMarker,
    renderClusterMarker,
  };
}
