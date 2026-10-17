<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import L from "leaflet";
import "leaflet.heat";
import "leaflet/dist/leaflet.css";
import { GROUP_COLORS, GROUP_COLOR_FALLBACK } from "../../../api/client";
import { useI18n } from "../../../i18n/useI18n";
import {
  ACCENT_HEX,
  ALERT_RAMP_HEX,
  HEAT_GRADIENT_STOPS,
} from "../../map-viewer/composables/canvasColors";
import { BASEMAP_PRESETS, canUseCanvasHeatmap } from "../../map-viewer/composables/useLeafletMap";
import { printBasemap } from "./mapPrintModel";
import type { MapSnapshot } from "./mapSnapshot";

const props = defineProps<{
  snapshot: MapSnapshot;
  scale: boolean;
  north: boolean;
}>();

const { t } = useI18n();
const container = ref<HTMLElement | null>(null);
let map: L.Map | null = null;

function refit(): void {
  map?.invalidateSize();
}

type HeatFactory = (points: Array<[number, number, number]>, options: Record<string, unknown>) => L.Layer;

onMounted(() => {
  if (!container.value) return;
  const { view, layers } = props.snapshot;
  map = L.map(container.value, {
    zoomControl: false,
    attributionControl: true,
    scrollWheelZoom: false,
    dragging: false,
    keyboard: false,
  });

  // Same Esri Canvas presets as the live map. Never a key-gated provider.
  const preset = BASEMAP_PRESETS[printBasemap(view.basemap)];
  L.tileLayer(preset.url, preset.options).addTo(map);
  if (preset.referenceUrl) L.tileLayer(preset.referenceUrl, preset.options).addTo(map);

  // The live centre and zoom, not a rebuilt view.
  map.setView(view.center, view.zoom);

  const heatFactory = (L as unknown as { heatLayer?: HeatFactory }).heatLayer;
  if (layers.heat && props.snapshot.heatPoints.length > 0 && canUseCanvasHeatmap() && heatFactory) {
    heatFactory(
      props.snapshot.heatPoints.map((p) => [p.latitude, p.longitude, p.intensity]),
      { radius: 28, blur: 14, maxZoom: 16, minOpacity: 0.22, gradient: HEAT_GRADIENT_STOPS },
    ).addTo(map);
  }

  if (layers.markers) {
    for (const place of props.snapshot.places) {
      const selected = props.snapshot.selectedPlace?.id === place.id;
      L.circleMarker([place.latitude, place.longitude], {
        radius: selected ? 9 : 4 + place.urgency_level,
        color: selected ? ACCENT_HEX : "#ffffff",
        weight: selected ? 3 : 1.5,
        fillColor: GROUP_COLORS[place.vulnerability_group] ?? GROUP_COLOR_FALLBACK,
        fillOpacity: 0.95,
      }).addTo(map);
    }
  }

  if (layers.hazards) {
    for (const event of props.snapshot.hazards) {
      const color = ALERT_RAMP_HEX[event.alert_level] ?? ALERT_RAMP_HEX.red;
      L.circle([event.latitude, event.longitude], {
        radius: Math.max(event.radius_km * 1000, 1500),
        color,
        weight: 2,
        dashArray: "6, 6",
        fillColor: color,
        fillOpacity: 0.14,
      }).addTo(map);
      L.circleMarker([event.latitude, event.longitude], {
        radius: 6,
        color: "#ffffff",
        weight: 2,
        fillColor: color,
        fillOpacity: 1,
      }).addTo(map);
    }
  }

  if (view.radius) {
    L.circle([view.radius.latitude, view.radius.longitude], {
      radius: view.radius.meters,
      color: ACCENT_HEX,
      weight: 1.5,
      fillColor: ACCENT_HEX,
      fillOpacity: 0.14,
    }).addTo(map);
  }

  if (props.scale) {
    L.control.scale({ metric: true, imperial: false, position: "bottomleft" }).addTo(map);
  }
  window.addEventListener("beforeprint", refit);
  window.addEventListener("afterprint", refit);
});

onBeforeUnmount(() => {
  window.removeEventListener("beforeprint", refit);
  window.removeEventListener("afterprint", refit);
  map?.remove();
  map = null;
});
</script>

<template>
  <div class="print-map" data-testid="print-map">
    <div ref="container" class="map-canvas"></div>
    <div v-if="north" class="north" :aria-label="t.community.sheet.north">
      <svg viewBox="0 0 16 24" width="16" height="24" aria-hidden="true">
        <path d="M8 1 L14 22 L8 17 L2 22 Z" fill="currentColor" />
      </svg>
      <span>{{ t.community.sheet.north }}</span>
    </div>
  </div>
</template>

<style>
.print-map {
  position: relative;
  height: 100%;
  min-height: 240px;
}
.print-map .map-canvas {
  position: absolute;
  inset: 0;
}
.print-map .north {
  position: absolute;
  top: var(--eoc-gap-x);
  right: var(--eoc-gap-x);
  z-index: 500;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--eoc-gap-y);
  background: var(--eoc-map-ctrl-bg);
  border: var(--eoc-border-width) solid var(--eoc-map-ctrl-border);
  color: var(--eoc-text-primary);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
}
</style>
