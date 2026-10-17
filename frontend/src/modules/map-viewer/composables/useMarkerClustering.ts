import type L from "leaflet";
import type { PlaceRead } from "../../../api/client";
import type { ClusterBucket } from "./useMapMarkers";

/**
 * Screen-space proximity threshold. Two places closer than this many pixels
 * collapse into the same bucket, so clustering follows what the operator can
 * actually distinguish on screen rather than a geographic distance that would
 * behave differently at every zoom level.
 */
const CLUSTER_RADIUS_PX = 46;

/** Above this zoom the operator is close enough that every pin stays separate. */
const CLUSTER_MAX_ZOOM = 16;

/** Below this many visible places there is nothing worth collapsing. */
const CLUSTER_MIN_PLACES = 18;

/** Viewport padding, as a fraction, kept warm outside the visible bounds. */
const VIEWPORT_CLIP_PADDING = 0.2;

/** Coalescing window for map pans and rapid prop churn. */
const MARKERS_DEBOUNCE_MS = 35;

/** The marker-rendering port this composable drives, provided by useMapMarkers. */
export interface MarkerRenderer {
  hasMarkerGroup: () => boolean;
  clearMarkers: () => void;
  renderSinglePlaceMarker: (place: PlaceRead) => void;
  renderClusterMarker: (bucket: ClusterBucket) => void;
}

export interface UseMarkerClusteringOptions {
  getMap: () => L.Map | null;
  places: () => PlaceRead[];
  selectedPlace: () => PlaceRead | null;
  /** Operator toggle for the markers layer. */
  enabled: () => boolean;
  /**
   * True while the place layer yields the map to the density surface. Only the
   * selected place is still drawn, because a selection must never disappear
   * from under the operator who made it.
   */
  selectionOnly?: () => boolean;
  markers: MarkerRenderer;
}

/**
 * Decides which markers reach the map.
 *
 * Three passes, in order: clip to the viewport, lift the selected place out so
 * a cluster can never hide it, then collapse the rest by screen-space
 * proximity. A bucket that ends up holding a single place renders as a normal
 * pin, not as a cluster of one.
 */
export function useMarkerClustering(options: UseMarkerClusteringOptions) {
  let markersDebounceTimer: ReturnType<typeof setTimeout> | null = null;

  function debouncedUpdateMarkers(): void {
    if (markersDebounceTimer) {
      clearTimeout(markersDebounceTimer);
    }
    markersDebounceTimer = setTimeout(() => {
      updateMarkersLayer();
      markersDebounceTimer = null;
    }, MARKERS_DEBOUNCE_MS);
  }

  function updateMarkersLayer(): void {
    const map = options.getMap();
    if (!options.markers.hasMarkerGroup() || !map) return;
    options.markers.clearMarkers();
    if (!options.enabled()) return;

    if (options.selectionOnly?.()) {
      const selected = options.selectedPlace();
      if (selected) options.markers.renderSinglePlaceMarker(selected);
      return;
    }

    const zoom = map.getZoom ? map.getZoom() : 14;
    const bounds = map.getBounds
      ? map.getBounds().pad(VIEWPORT_CLIP_PADDING)
      : null;
    const selectedPlaceId = options.selectedPlace()?.id;
    const places = options.places();

    // Viewport Spatial Clipping: process places visible on screen (+ selected place)
    const visiblePlaces = bounds
      ? places.filter(
          (p) =>
            bounds.contains([p.latitude, p.longitude]) ||
            p.id === selectedPlaceId,
        )
      : places;
    const selectedVisiblePlace = visiblePlaces.find(
      (place) => place.id === selectedPlaceId,
    );
    // Keep the selected place out of spatial clusters so its exact coordinates
    // remain visible as a distinct, topmost marker even in dense areas.
    const placesToCluster = selectedVisiblePlace
      ? visiblePlaces.filter((place) => place.id !== selectedVisiblePlace.id)
      : visiblePlaces;

    const shouldCluster =
      zoom < CLUSTER_MAX_ZOOM &&
      placesToCluster.length > CLUSTER_MIN_PLACES &&
      typeof map.latLngToContainerPoint === "function";

    if (shouldCluster) {
      const buckets: ClusterBucket[] = [];

      for (const place of placesToCluster) {
        const pt = map.latLngToContainerPoint([
          place.latitude,
          place.longitude,
        ]);
        let matched: ClusterBucket | null = null;
        for (const b of buckets) {
          const dist = Math.hypot(b.screenX - pt.x, b.screenY - pt.y);
          if (dist < CLUSTER_RADIUS_PX) {
            matched = b;
            break;
          }
        }
        if (matched) {
          matched.places.push(place);
          matched.centroidLat =
            (matched.centroidLat * (matched.places.length - 1) + place.latitude) /
            matched.places.length;
          matched.centroidLon =
            (matched.centroidLon * (matched.places.length - 1) + place.longitude) /
            matched.places.length;
          matched.maxUrgency = Math.max(matched.maxUrgency, place.urgency_level);
          if (
            place.urgency_level >= 4 &&
            place.attention_status !== "attended"
          ) {
            matched.hasCritical = true;
          }
        } else {
          buckets.push({
            places: [place],
            centroidLat: place.latitude,
            centroidLon: place.longitude,
            screenX: pt.x,
            screenY: pt.y,
            maxUrgency: place.urgency_level,
            hasCritical:
              place.urgency_level >= 4 &&
              place.attention_status !== "attended",
          });
        }
      }

      for (const bucket of buckets) {
        if (bucket.places.length === 1) {
          options.markers.renderSinglePlaceMarker(bucket.places[0]);
        } else {
          options.markers.renderClusterMarker(bucket);
        }
      }
    } else {
      for (const place of placesToCluster) {
        options.markers.renderSinglePlaceMarker(place);
      }
    }

    if (selectedVisiblePlace) {
      options.markers.renderSinglePlaceMarker(selectedVisiblePlace);
    }
  }

  return { updateMarkersLayer, debouncedUpdateMarkers };
}
