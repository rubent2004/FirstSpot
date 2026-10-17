import { watch } from "vue";
import L from "leaflet";
import { ACCENT_HEX } from "./canvasColors";

export interface UseRadiusSelectionOptions {
  getMap: () => L.Map | null;
  /** Whether click-to-place-radius mode is active. */
  enabled: () => boolean;
  /** Radius of the selection circle, in metres. */
  radiusMeters: () => number;
  /** Called with the picked center so the host can sync its own radius state. */
  onPick: (latitude: number, longitude: number) => void;
}

/**
 * Owns the operator's custom radius circle: the map click that places it, the
 * live radius updates, and the two different ways it gets cleared.
 *
 * The picked center is remembered after the circle is gone so a "center zone"
 * command returns to where the operator was last working rather than snapping
 * back to the zone centroid.
 */
export function useRadiusSelection(options: UseRadiusSelectionOptions) {
  let radiusCircle: L.Circle | null = null;
  let lastRadiusCenter: [number, number] | null = null;

  /** Last picked center, or null when the operator has not picked one. */
  function getLastCenter(): [number, number] | null {
    return lastRadiusCenter;
  }

  /** Registers the click handler that places the circle. */
  function attachTo(map: L.Map): void {
    map.on("click", (evt: L.LeafletMouseEvent) => {
      const liveMap = options.getMap();
      if (!options.enabled() || !liveMap) return;
      const { lat, lng } = evt.latlng;
      lastRadiusCenter = [lat, lng];
      if (radiusCircle) {
        liveMap.removeLayer(radiusCircle);
      }
      radiusCircle = L.circle([lat, lng], {
        radius: options.radiusMeters(),
        color: ACCENT_HEX,
        weight: 1.5,
        fillColor: ACCENT_HEX,
        fillOpacity: 0.14,
      }).addTo(liveMap);

      options.onPick(lat, lng);
    });
  }

  /**
   * Forgets the remembered center and drops any circle.
   *
   * Used when the operator switches zone: the previous pick belongs to the
   * previous zone, so the center is forgotten even if no circle was drawn.
   */
  function resetForZoneChange(): void {
    const map = options.getMap();
    if (!map) return;
    lastRadiusCenter = null;
    if (radiusCircle) {
      map.removeLayer(radiusCircle);
      radiusCircle = null;
    }
  }

  watch(
    () => options.radiusMeters(),
    (newRadius) => {
      if (radiusCircle && typeof radiusCircle.setRadius === "function") {
        radiusCircle.setRadius(newRadius);
      }
    },
  );

  // Leaving radius mode tears down the circle. The remembered center is only
  // forgotten alongside a circle that actually existed, so toggling the mode
  // off and on again returns to the same spot.
  watch(
    () => options.enabled(),
    (enabled) => {
      const map = options.getMap();
      if (!enabled && radiusCircle && map) {
        map.removeLayer(radiusCircle);
        radiusCircle = null;
        lastRadiusCenter = null;
      }
    },
  );

  return { attachTo, getLastCenter, resetForZoneChange };
}
