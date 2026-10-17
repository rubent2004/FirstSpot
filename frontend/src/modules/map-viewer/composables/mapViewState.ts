import type { BasemapPresetId } from "./useLeafletMap";

/**
 * What the operator is looking at right now, for a printout that must match it:
 * the live centre, zoom, extent and basemap, and the radius circle if one is drawn.
 */
export interface MapViewState {
  center: [number, number];
  zoom: number;
  bounds: { south: number; west: number; north: number; east: number };
  basemap: BasemapPresetId;
  radius: { latitude: number; longitude: number; meters: number } | null;
}
