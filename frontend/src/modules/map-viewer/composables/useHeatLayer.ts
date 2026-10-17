import L from "leaflet";
import "leaflet.heat";
import type { HeatmapPointRead } from "../../../api/client";
import { HEAT_GRADIENT_STOPS } from "./canvasColors";
import { canUseCanvasHeatmap } from "./useLeafletMap";

/** `[latitude, longitude, intensity]`, the tuple shape `leaflet.heat` expects. */
type HeatPoint = [number, number, number];

/**
 * `leaflet.heat` augments the Leaflet namespace at runtime and ships no typed
 * factory, so the plugin surface this composable relies on is declared here and
 * the global `L` is narrowed to it once.
 */
type HeatLayerInstance = L.Layer & {
  setLatLngs: (points: HeatPoint[]) => void;
};

type HeatLayerFactory = (
  points: HeatPoint[],
  options: Record<string, unknown>,
) => HeatLayerInstance;

export interface UseHeatLayerOptions {
  getMap: () => L.Map | null;
  /** Weighted points to paint. */
  points: () => HeatmapPointRead[];
  /** Operator toggle for the heat layer. */
  enabled: () => boolean;
}

/**
 * Owns the `leaflet.heat` canvas layer.
 *
 * The layer is reused across updates whenever the plugin exposes
 * `setLatLngs`, because rebuilding it re-allocates a full-viewport canvas on
 * every data refresh. It is dropped entirely when the toggle is off, when there
 * is nothing to paint, or when no usable canvas context exists -- the same
 * probe that decides `preferCanvas` on the map, so the two cannot disagree.
 */
export function useHeatLayer(options: UseHeatLayerOptions) {
  let heatLayer: HeatLayerInstance | null = null;

  function updateHeatLayer(): void {
    const map = options.getMap();
    if (!map) return;

    const heatFactory = (L as unknown as { heatLayer?: HeatLayerFactory })
      .heatLayer;

    if (
      !options.enabled() ||
      options.points().length === 0 ||
      !canUseCanvasHeatmap() ||
      !heatFactory
    ) {
      if (heatLayer) {
        map.removeLayer(heatLayer);
        heatLayer = null;
      }
      return;
    }

    const tuples: HeatPoint[] = options
      .points()
      .map((pt) => [pt.latitude, pt.longitude, pt.intensity]);

    if (heatLayer && typeof heatLayer.setLatLngs === "function") {
      heatLayer.setLatLngs(tuples);
    } else {
      if (heatLayer) {
        map.removeLayer(heatLayer);
      }
      // blur was 22 against radius 34 — two thirds of every point was
      // diffusion, which read as an out-of-focus smear rather than a density
      // surface. Tightening it keeps concentrations legible as shapes.
      heatLayer = heatFactory(tuples, {
        radius: 28,
        blur: 14,
        maxZoom: 16,
        minOpacity: 0.22,
        gradient: HEAT_GRADIENT_STOPS,
      });
      heatLayer.addTo(map);
    }
  }

  return { updateHeatLayer };
}
