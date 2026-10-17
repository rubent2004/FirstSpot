import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export type BasemapPresetId = "grayDark" | "grayLight" | "osmStreet";

interface BasemapPreset {
  url: string;
  /** Label overlay for providers whose base tiles ship without place names. */
  referenceUrl?: string;
  options: L.TileLayerOptions;
}

const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const ESRI_ATTRIBUTION = "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ";

const SHARED_TILE_OPTIONS = {
  maxZoom: 19,
  updateWhenIdle: true,
  updateWhenZooming: false,
  keepBuffer: 3,
} as const;

/** Sonsonate, the operational default zone, used before any zone is selected. */
export const DEFAULT_MAP_CENTER: L.LatLngTuple = [13.7222, -89.7236];

/** Zoom the map opens at, before any camera command runs. */
export const DEFAULT_MAP_ZOOM = 14;

/**
 * Basemap providers. The two Esri Canvas rasters are low-saturation at the
 * source, which is why the tiles are never touched with a CSS filter: a
 * grayscale() or saturate() pass over Leaflet tiles washes out labels and
 * leaves the operator with an illegible map.
 *
 * Each gray preset pairs a Base layer with its Reference overlay, so place
 * labels and roads stay crisp above the muted terrain.
 */
export const BASEMAP_PRESETS: Record<BasemapPresetId, BasemapPreset> = {
  // Esri Canvas tiles need no API key. CARTO's basemaps.cartocdn.com now
  // requires one and answers HTTP 200 with an "API KEY REQUIRED" placeholder
  // tile, so a failure there is invisible to status-code checks.
  // Note the {z}/{y}/{x} order: Esri inverts y and x relative to OSM/CARTO.
  grayDark: {
    url: "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    referenceUrl:
      "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    options: {
      ...SHARED_TILE_OPTIONS,
      attribution: ESRI_ATTRIBUTION,
      maxNativeZoom: 16,
    },
  },
  grayLight: {
    url: "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    referenceUrl:
      "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    options: {
      ...SHARED_TILE_OPTIONS,
      attribution: ESRI_ATTRIBUTION,
      maxNativeZoom: 16,
    },
  },
  osmStreet: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: {
      ...SHARED_TILE_OPTIONS,
      attribution: OSM_ATTRIBUTION,
    },
  },
};

/**
 * Whether a usable 2D canvas context exists.
 *
 * This single probe decides both `preferCanvas` on the map and whether the
 * `leaflet.heat` layer may be built, so the two can never disagree. jsdom
 * reports a canvas it cannot actually paint, hence the explicit user-agent
 * bail-out.
 */
export function canUseCanvasHeatmap(): boolean {
  if (typeof document === "undefined") return false;
  if (
    typeof navigator !== "undefined" &&
    navigator.userAgent &&
    navigator.userAgent.includes("jsdom")
  ) {
    return false;
  }
  try {
    const canvas = document.createElement("canvas");
    if (!canvas || typeof canvas.getContext !== "function") return false;
    const ctx = canvas.getContext("2d");
    return Boolean(ctx);
  } catch {
    return false;
  }
}

export interface UseLeafletMapOptions {
  /** Explicit basemap override; when absent the theme flag picks the default. */
  basemapPreset: () => BasemapPresetId | undefined;
  /** Dark shell flag coming from the app theme. */
  tacticalBasemap: () => boolean;
  /** Center for the first paint, before any camera command runs. */
  initialCenter: () => L.LatLngTuple;
}

/**
 * Owns the Leaflet map instance: creation, basemap tiles, container resize,
 * camera moves and teardown.
 *
 * The map is created in `onMounted` and destroyed in `onBeforeUnmount`. Because
 * composables register their hooks in call order, calling this first in `setup`
 * guarantees the map exists before any layer composable attaches to it, and is
 * torn down before the component's own cleanup runs.
 */
export function useLeafletMap(options: UseLeafletMapOptions) {
  const mapContainer = ref<HTMLElement | null>(null);

  /**
   * Current zoom, mirrored into a ref so layer decisions can be computed
   * properties rather than imperative callbacks. Leaflet owns the value; this
   * only follows it.
   */
  const zoom = ref<number>(DEFAULT_MAP_ZOOM);

  let mapInstance: L.Map | null = null;
  let tileLayerInstance: L.TileLayer | null = null;
  let tacticalRefLayerInstance: L.TileLayer | null = null;
  let resizeObserver: ResizeObserver | null = null;

  // Dark shell gets Dark Matter, light shell gets Positron. Both are muted at
  // the source, so the heat layer and the markers stay the only saturated ink.
  const activeBasemapPreset = computed<BasemapPresetId>(() => {
    const explicit = options.basemapPreset();
    if (explicit) return explicit;
    return options.tacticalBasemap() ? "grayDark" : "grayLight";
  });

  function getMap(): L.Map | null {
    return mapInstance;
  }

  function detachTileLayers(map: L.Map): void {
    if (tileLayerInstance) {
      map.removeLayer(tileLayerInstance);
      tileLayerInstance = null;
    }
    if (tacticalRefLayerInstance) {
      map.removeLayer(tacticalRefLayerInstance);
      tacticalRefLayerInstance = null;
    }
  }

  function applyTileLayer(): void {
    if (!mapInstance) return;
    detachTileLayers(mapInstance);

    const preset = BASEMAP_PRESETS[activeBasemapPreset.value];
    tileLayerInstance = L.tileLayer(preset.url, preset.options).addTo(mapInstance);

    if (preset.referenceUrl) {
      tacticalRefLayerInstance = L.tileLayer(
        preset.referenceUrl,
        preset.options,
      ).addTo(mapInstance);
    }
  }

  /** Animated camera move. No-ops while the map does not exist. */
  function flyTo(
    center: L.LatLngTuple,
    zoom: number,
    flyOptions?: L.ZoomPanOptions,
  ): void {
    if (!mapInstance) return;
    mapInstance.flyTo(center, zoom, flyOptions);
  }

  /** Animated camera move framing every supplied coordinate. */
  function flyToBounds(
    coordinates: L.LatLngTuple[],
    fitOptions?: L.FitBoundsOptions,
  ): void {
    if (!mapInstance) return;
    mapInstance.flyToBounds(L.latLngBounds(coordinates), fitOptions);
  }

  onMounted(() => {
    if (!mapContainer.value) return;

    const [initialLat, initialLon] = options.initialCenter();

    mapInstance = L.map(mapContainer.value, {
      center: [initialLat, initialLon],
      zoom: DEFAULT_MAP_ZOOM,
      zoomControl: true,
      preferCanvas: canUseCanvasHeatmap(),
      zoomAnimation: true,
      fadeAnimation: true,
      markerZoomAnimation: true,
      wheelPxPerZoomLevel: 120,
      wheelDebounceTime: 40,
    });

    zoom.value = mapInstance.getZoom?.() ?? DEFAULT_MAP_ZOOM;
    mapInstance.on("zoomend", () => {
      zoom.value = mapInstance?.getZoom?.() ?? zoom.value;
    });

    applyTileLayer();

    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => {
        mapInstance?.invalidateSize();
      });
      resizeObserver.observe(mapContainer.value);
    }
  });

  watch(
    () => activeBasemapPreset.value,
    () => {
      applyTileLayer();
    },
  );

  onBeforeUnmount(() => {
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
    if (mapInstance) {
      detachTileLayers(mapInstance);
      mapInstance.remove();
      mapInstance = null;
    }
  });

  return {
    mapContainer,
    getMap,
    activeBasemapPreset,
    flyTo,
    flyToBounds,
    zoom,
  };
}
