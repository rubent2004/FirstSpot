import { afterEach, describe, expect, it } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import type L from "leaflet";

import type { HeatmapPointRead, PlaceRead } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import VulnerabilityHeatmapCanvas from "../modules/map-viewer/VulnerabilityHeatmapCanvas.vue";
import { useMarkerClustering } from "../modules/map-viewer/composables/useMarkerClustering";
import type { ClusterBucket } from "../modules/map-viewer/composables/useMapMarkers";

const basePlace: PlaceRead = {
  id: "dddddddd-0000-0000-0000-000000000001",
  osm_type: "way",
  osm_id: 100,
  name: "Hospital Nacional de Sonsonate",
  category: "hospital",
  vulnerability_group: "health",
  zone_name: "Sonsonate",
  latitude: 13.72,
  longitude: -89.72,
  osm_tags: {},
  attention_status: "pending",
  urgency_level: 3,
  estimated_vulnerable_count: 0,
  institution_notes: null,
  category_weight: 100,
  nearby_places_count: 2,
  priority_score: 130,
  last_osm_sync_at: "2026-10-16T11:00:00Z",
  updated_at: "2026-10-16T11:00:00Z",
};

const places: PlaceRead[] = Array.from({ length: 6 }, (_, index) => ({
  ...basePlace,
  id: `${basePlace.id}-${index}`,
  name: `Hospital ${index}`,
  latitude: 13.72 + index * 0.02,
  longitude: -89.72 + index * 0.02,
}));

const heatmapPoints: HeatmapPointRead[] = places.map((place) => ({
  id: place.id,
  name: place.name,
  category: "hospital",
  vulnerability_group: "health",
  attention_status: "pending",
  latitude: place.latitude,
  longitude: place.longitude,
  priority_score: place.priority_score,
  intensity: 1,
}));

/** Enough of a Leaflet map for the clustering passes, and nothing more. */
function fakeMap(zoomLevel: number): L.Map {
  return {
    getZoom: () => zoomLevel,
    getBounds: () => ({ pad: () => ({ contains: () => true }) }),
    latLngToContainerPoint: ([lat, lon]: [number, number]) => ({
      x: lon * 4000,
      y: lat * 4000,
    }),
  } as unknown as L.Map;
}

function recordingRenderer() {
  const singles: string[] = [];
  const clusters: number[] = [];
  return {
    singles,
    clusters,
    hasMarkerGroup: () => true,
    clearMarkers: () => {
      singles.length = 0;
      clusters.length = 0;
    },
    renderSinglePlaceMarker: (place: PlaceRead) => singles.push(place.id),
    renderClusterMarker: (bucket: ClusterBucket) =>
      clusters.push(bucket.places.length),
  };
}

afterEach(() => {
  setAppLocale("es");
});

describe("the place layer yields the map to the density surface", () => {
  it("draws only the selected place while the density surface owns the map", () => {
    const markers = recordingRenderer();
    const { updateMarkersLayer } = useMarkerClustering({
      getMap: () => fakeMap(14),
      places: () => places,
      selectedPlace: () => places[3],
      enabled: () => true,
      selectionOnly: () => true,
      markers,
    });

    updateMarkersLayer();

    // A selection must never disappear from under the operator who made it.
    expect(markers.singles).toEqual([places[3].id]);
    expect(markers.clusters).toEqual([]);
  });

  it("draws nothing at all when nothing is selected and the surface has yielded", () => {
    const markers = recordingRenderer();
    const { updateMarkersLayer } = useMarkerClustering({
      getMap: () => fakeMap(14),
      places: () => places,
      selectedPlace: () => null,
      enabled: () => true,
      selectionOnly: () => true,
      markers,
    });

    updateMarkersLayer();

    expect(markers.singles).toEqual([]);
  });

  it("draws every visible place once the place layer owns the map", () => {
    const markers = recordingRenderer();
    const { updateMarkersLayer } = useMarkerClustering({
      getMap: () => fakeMap(16),
      places: () => places,
      selectedPlace: () => null,
      enabled: () => true,
      selectionOnly: () => false,
      markers,
    });

    updateMarkersLayer();

    expect(markers.singles).toHaveLength(places.length);
  });
});

describe("the map says which surface owns it", () => {
  it("hands the overview to density and keeps only the selected pin", async () => {
    setAppLocale("es");
    const wrapper = mount(VulnerabilityHeatmapCanvas, {
      global: { plugins: [ElementPlus] },
      props: {
        places,
        heatmapPoints,
        selectedPlace: places[2],
        customRadiusEnabled: false,
        customRadiusMeters: 3000,
      },
    });
    await flushPromises();

    // Fifty pins on fifty halos was one dataset drawn twice; at the overview
    // zoom only the operator's own selection stays on the place layer.
    expect(wrapper.findAll(".tactical-map-pin")).toHaveLength(1);
    expect(wrapper.find(".tactical-map-pin.tactical-pin-selected").exists()).toBe(true);
    expect(wrapper.get('[data-testid="map-surface-mode"]').text()).toContain(
      "acerque para ver lugares",
    );

    setAppLocale("en");
    await flushPromises();
    expect(wrapper.get('[data-testid="map-surface-mode"]').text()).toContain(
      "zoom in for places",
    );
    wrapper.unmount();
  });

  it("stops explaining a handoff that no longer happens once heat is off", async () => {
    setAppLocale("es");
    const wrapper = mount(VulnerabilityHeatmapCanvas, {
      global: { plugins: [ElementPlus] },
      props: {
        places,
        heatmapPoints,
        selectedPlace: places[2],
        customRadiusEnabled: false,
        customRadiusMeters: 3000,
        showHeatmapLayer: false,
      },
    });
    await flushPromises();

    // An explicit layer decision outranks the zoom handoff, so there is no
    // caption to show. How many pins reach the map at this zoom is covered by
    // the clustering tests above: a jsdom container has no size, so Leaflet's
    // viewport clip discards everything except the selected place.
    expect(wrapper.find('[data-testid="map-surface-mode"]').exists()).toBe(false);
    expect(wrapper.find(".tactical-map-pin.tactical-pin-selected").exists()).toBe(true);
    wrapper.unmount();
  });
});
