/// <reference types="vite/client" />

declare module "leaflet.heat" {
  import * as L from "leaflet";

  export type HeatLatLngTuple = [number, number, number?];

  export interface HeatMapOptions {
    minOpacity?: number;
    maxZoom?: number;
    max?: number;
    radius?: number;
    blur?: number;
    gradient?: Record<number, string>;
  }

  export interface HeatLayer extends L.Layer {
    setLatLngs(latlngs: HeatLatLngTuple[]): this;
    addLatLng(latlng: HeatLatLngTuple): this;
    setOptions(options: HeatMapOptions): this;
    redraw(): this;
  }
}
