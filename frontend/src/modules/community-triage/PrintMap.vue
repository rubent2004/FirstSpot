<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useI18n } from "../../i18n/useI18n";
import { BASEMAP_PRESETS } from "../map-viewer/composables/useLeafletMap";
import type { ReportEvent } from "./exportModel";

const props = defineProps<{ event: ReportEvent | null }>();

const { t } = useI18n();
const container = ref<HTMLElement | null>(null);

/** El Salvador's centre; the national view used when there is no epicentre. */
const NATIONAL_CENTER: L.LatLngTuple = [13.75, -88.9];
const NATIONAL_ZOOM = 8;

let map: L.Map | null = null;

/** The sheet changes width when the print dialog opens; tiles must follow. */
function refit(): void {
  map?.invalidateSize();
}

onMounted(() => {
  if (!container.value) return;
  map = L.map(container.value, {
    zoomControl: false,
    attributionControl: true,
    scrollWheelZoom: false,
  });
  // The light Esri Canvas pair is already low-saturation, so it prints as
  // greyscale without any filter. Never a key-gated provider.
  const preset = BASEMAP_PRESETS.grayLight;
  L.tileLayer(preset.url, preset.options).addTo(map);
  if (preset.referenceUrl) L.tileLayer(preset.referenceUrl, preset.options).addTo(map);
  L.control.scale({ metric: true, imperial: false, position: "bottomleft" }).addTo(map);

  const center: L.LatLngTuple = props.event
    ? [props.event.latitude, props.event.longitude]
    : NATIONAL_CENTER;
  map.setView(center, NATIONAL_ZOOM);
  if (props.event) {
    L.marker(center, {
      keyboard: false,
      icon: L.divIcon({
        className: "epicentre-icon",
        html: '<span class="epicentre-ring"></span>',
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      }),
    }).addTo(map);
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
    <div class="north" aria-label="North">
      <svg viewBox="0 0 16 24" width="16" height="24" aria-hidden="true">
        <path d="M8 1 L14 22 L8 17 L2 22 Z" fill="currentColor" />
      </svg>
      <span>{{ t.community.sheet.north }}</span>
    </div>
    <div v-if="event" class="epicentre-key">
      <span class="epicentre-ring static"></span>
      {{ t.community.sheet.epicentre }}
    </div>
  </div>
</template>

<style>
.print-map {
  position: relative;
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  height: 100%;
  min-height: 360px;
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
.print-map .epicentre-key {
  position: absolute;
  left: var(--eoc-gap-x);
  top: var(--eoc-gap-x);
  z-index: 500;
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  padding: var(--eoc-gap-y);
  background: var(--eoc-map-ctrl-bg);
  border: var(--eoc-border-width) solid var(--eoc-map-ctrl-border);
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-primary);
}
/* Ring plus cross-hair: legible in greyscale, no colour needed */
.epicentre-ring {
  display: inline-block;
  width: 18px;
  height: 18px;
  box-sizing: border-box;
  border: 3px solid var(--eoc-text-primary);
  border-radius: var(--eoc-radius-pill);
  background: var(--eoc-bg-panel);
  position: relative;
}
.epicentre-ring::after {
  content: "";
  position: absolute;
  inset: 3px;
  background: var(--eoc-text-primary);
  border-radius: var(--eoc-radius-pill);
}
.epicentre-ring.static {
  width: 12px;
  height: 12px;
  border-width: 2px;
}
.epicentre-icon {
  background: transparent;
  border: 0;
}
</style>
