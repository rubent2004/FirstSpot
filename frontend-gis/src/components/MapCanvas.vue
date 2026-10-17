<script setup lang="ts">
import { ref, onMounted, watch, nextTick, computed } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";
import { useGisStore } from "../stores/useGisStore";
import {
  Compass,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Crosshair,
  Layers,
  Sparkles,
  BarChart3,
  Map as MapIcon,
  Plus,
} from "lucide-vue-next";

const store = useGisStore();

const mapContainer = ref<HTMLDivElement | null>(null);
let map: L.Map | null = null;
let baseTileLayer: L.TileLayer | null = null;
let placesLayerGroup: L.LayerGroup | null = null;
let radarCircle: L.Circle | null = null;
let heatmapLayer: L.Layer | null = null;
let hazardsLayerGroup: L.LayerGroup | null = null;

const basemapUrls = {
  "carto-light": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  "osm": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  "carto-dark": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
};

function getMarkerColor(priorityScore: number | string): string {
  const score = Number(priorityScore);
  if (score >= 80) return "#dc2626";
  if (score >= 60) return "#ea580c";
  if (score >= 40) return "#d97706";
  return "#16a34a";
}

function updateBasemap() {
  if (!map) return;
  if (baseTileLayer) {
    map.removeLayer(baseTileLayer);
  }
  const url = basemapUrls[store.basemap] || basemapUrls["carto-light"];
  baseTileLayer = L.tileLayer(url, {
    maxZoom: 19,
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap',
  }).addTo(map);
  baseTileLayer.bringToBack();
}

function renderRadar() {
  if (!map) return;
  if (radarCircle) {
    map.removeLayer(radarCircle);
    radarCircle = null;
  }
  if (!store.layerVisibility.radar) return;

  const zone = store.activeZone;
  if (!zone) return;

  radarCircle = L.circle([zone.latitude, zone.longitude], {
    radius: zone.default_radius_meters,
    color: "#0E9384",
    weight: 1.5,
    dashArray: "6, 6",
    fillColor: "#0E9384",
    fillOpacity: 0.05 * (store.layerOpacity / 100),
  }).addTo(map);
}

function renderHeatmap() {
  if (!map) return;
  if (heatmapLayer) {
    map.removeLayer(heatmapLayer);
    heatmapLayer = null;
  }
  if (!store.layerVisibility.heatmap || store.heatmapPoints.length === 0) return;

  const points: [number, number, number][] = store.heatmapPoints.map((p) => [
    p.latitude,
    p.longitude,
    p.intensity,
  ]);

  // @ts-expect-error leaflet.heat types
  heatmapLayer = L.heatLayer(points, {
    radius: 35,
    blur: 25,
    maxZoom: 16,
    max: 1.0,
    gradient: {
      0.2: "#3b82f6",
      0.4: "#06b6d4",
      0.6: "#eab308",
      0.8: "#f97316",
      1.0: "#ef4444",
    },
  }).addTo(map);
}

function renderPlaces() {
  if (!map || !placesLayerGroup) return;
  placesLayerGroup.clearLayers();

  if (!store.layerVisibility.points) return;

  const opacity = store.layerOpacity / 100;

  for (const place of store.filteredPlaces) {
    const isSelected = store.selectedPlaceId === place.id;
    const color = getMarkerColor(place.priority_score);

    const marker = L.circleMarker([place.latitude, place.longitude], {
      radius: isSelected ? 9 : 6.5,
      fillColor: color,
      color: isSelected ? "#2563eb" : "#ffffff",
      weight: isSelected ? 2.5 : 1.2,
      opacity: 1,
      fillOpacity: 0.85 * opacity,
    });

    const popupHtml = `
      <div style="font-family: var(--gis-font, sans-serif); font-size: 11.5px; min-width: 170px;">
        <div style="font-weight: 700; margin-bottom: 3px; color: ${color};">${place.name}</div>
        <div style="color: #64748b; font-size: 10px;">${place.category.toUpperCase()} • ${place.vulnerability_group}</div>
        <div style="margin-top: 5px; display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: 600;">Score: ${Number(place.priority_score).toFixed(1)}</span>
          <span style="font-size: 10px; padding: 1px 5px; border-radius: 3px; background: #e2e8f0; font-weight: 600;">
            ${place.attention_status.toUpperCase()}
          </span>
        </div>
      </div>
    `;

    marker.bindTooltip(place.name, {
      permanent: false,
      direction: "top",
      offset: [0, -6],
    });

    marker.on("click", () => {
      store.selectedPlaceId = place.id;
      store.isSymbologyOpen = true;
    });

    placesLayerGroup.addLayer(marker);
  }
}

function renderHazards() {
  if (!map || !hazardsLayerGroup) return;
  hazardsLayerGroup.clearLayers();

  if (!store.layerVisibility.hazards || !store.hazards) return;

  for (const evt of store.hazards.events) {
    const mag = evt.magnitude ?? 5.0;
    const hazardMarker = L.circleMarker([evt.latitude, evt.longitude], {
      radius: 12 + mag * 2,
      fillColor: "#dc2626",
      color: "#991b1b",
      weight: 2,
      dashArray: "3, 3",
      fillOpacity: 0.25,
    });

    hazardMarker.bindTooltip(`⚠️ ${evt.title}`, {
      direction: "top",
      permanent: true,
      className: "hazard-tooltip",
    });

    hazardsLayerGroup.addLayer(hazardMarker);
  }
}

function centerToZone() {
  const zone = store.activeZone;
  if (zone && map) {
    map.setView([zone.latitude, zone.longitude], 13, { animate: true });
  }
}

function fullExtent() {
  if (!map) return;
  map.setView([13.7222, -89.7236], 9, { animate: true });
}

onMounted(() => {
  if (!mapContainer.value) return;

  const initialLat = store.activeZone?.latitude ?? 13.7222;
  const initialLng = store.activeZone?.longitude ?? -89.7236;

  map = L.map(mapContainer.value, {
    center: [initialLat, initialLng],
    zoom: store.mapZoom,
    zoomControl: false,
  });

  updateBasemap();

  placesLayerGroup = L.layerGroup().addTo(map);
  hazardsLayerGroup = L.layerGroup().addTo(map);

  renderRadar();
  renderHeatmap();
  renderPlaces();
  renderHazards();

  map.on("mousemove", (e: L.LeafletMouseEvent) => {
    store.cursorCoords = { lat: e.latlng.lat, lng: e.latlng.lng };
  });

  map.on("zoomend", () => {
    if (!map) return;
    store.mapZoom = map.getZoom();
    const z = map.getZoom();
    store.mapScale = z >= 15 ? "1:10,000" : z >= 13 ? "1:25,000" : z >= 11 ? "1:50,000" : "1:100,000";
  });
});

watch(() => store.basemap, updateBasemap);
watch([() => store.layerVisibility.radar, () => store.selectedZoneKey], renderRadar);
watch([() => store.layerVisibility.heatmap, () => store.heatmapPoints, () => store.layerOpacity], renderHeatmap);
watch([() => store.layerVisibility.points, () => store.filteredPlaces, () => store.selectedPlaceId, () => store.layerOpacity], renderPlaces);
watch([() => store.layerVisibility.hazards, () => store.hazards], renderHazards);

watch(() => store.selectedZoneKey, () => {
  nextTick(() => {
    centerToZone();
  });
});

watch(() => store.mapZoom, (newZoom) => {
  if (map && map.getZoom() !== newZoom) {
    map.setZoom(newZoom);
  }
});

watch(() => store.selectedPlaceId, (newId) => {
  if (!newId || !map) return;
  const place = store.places.find((p) => p.id === newId);
  if (place) {
    map.panTo([place.latitude, place.longitude], { animate: true });
  }
});
</script>

<template>
  <div class="gis-map-canvas-wrapper">
    <!-- Map Canvas Tab Header (RustGIS World + style) -->
    <div class="map-view-tabs">
      <div class="tabs-left">
        <button
          class="map-tab"
          :class="{ active: store.activeMapTab === 'map' }"
          @click="store.activeMapTab = 'map'"
        >
          <MapIcon :size="12" />
          <span>{{ store.activeZoneName || 'World Atlas' }}</span>
        </button>

        <button
          class="map-tab"
          :class="{ active: store.activeMapTab === 'matrix' }"
          @click="store.activeMapTab = 'matrix'"
        >
          <BarChart3 :size="12" />
          <span>Matriz de Vulnerabilidad</span>
        </button>

        <button
          class="map-tab"
          :class="{ active: store.activeMapTab === 'ai' }"
          @click="store.activeMapTab = 'ai'"
        >
          <Sparkles :size="12" class="text-accent" />
          <span>Asistente Táctico</span>
        </button>

        <button class="add-tab-btn" title="Nueva pestaña de mapa">
          <Plus :size="12" />
        </button>
      </div>

      <div class="tabs-right">
        <span class="active-layer-indicator">
          Capa Activa: <b>Centros Priorizados ({{ store.filteredPlaces.length }})</b>
        </span>
      </div>
    </div>

    <!-- Map Canvas Body -->
    <div class="map-viewport-container">
      <!-- Leaflet Container -->
      <div v-show="store.activeMapTab === 'map'" ref="mapContainer" class="leaflet-map-element"></div>

      <!-- Matrix Alternative View -->
      <div v-if="store.activeMapTab === 'matrix'" class="matrix-view-container">
        <div class="matrix-card">
          <h3>Matriz Multicriterio EOC PostGIS</h3>
          <p class="matrix-desc">Distribución espacial y clasificación por severidad multicriterio para {{ store.activeZoneName }}.</p>
          <div class="matrix-grid">
            <div class="matrix-stat stat-critica">
              <span class="stat-number">{{ store.heatmapMatrix.critical }}</span>
              <span class="stat-label">Prioridad Crítica (>= 80)</span>
            </div>
            <div class="matrix-stat stat-alta">
              <span class="stat-number">{{ store.heatmapMatrix.high }}</span>
              <span class="stat-label">Prioridad Alta (60 - 79)</span>
            </div>
            <div class="matrix-stat stat-media">
              <span class="stat-number">{{ store.heatmapMatrix.medium }}</span>
              <span class="stat-label">Prioridad Media (40 - 59)</span>
            </div>
            <div class="matrix-stat stat-normal">
              <span class="stat-number">{{ store.heatmapMatrix.normal }}</span>
              <span class="stat-label">Prioridad Normal (&lt; 40)</span>
            </div>
          </div>
        </div>
      </div>

      <!-- AI View -->
      <div v-if="store.activeMapTab === 'ai'" class="ai-view-container">
        <div class="ai-panel-card">
          <div class="ai-header">
            <Sparkles :size="18" class="text-accent" />
            <h3>Asistente de Despacho Operativo EOC</h3>
          </div>
          <p class="ai-desc">
            Análisis de optimización logística para la zona de <strong>{{ store.activeZoneName }}</strong> considerando eventos sísmicos y meteorológicos.
          </p>
          <div class="ai-recommendations">
            <div class="ai-rec-item">
              <span class="rec-badge red">Despacho Urgente</span>
              <p>Desplegar Unidad Médica Móvil hacia centros con score &ge; 80 y presencia de adultos mayores en el radio del radar.</p>
            </div>
            <div class="ai-rec-item">
              <span class="rec-badge amber">Monitoreo Estructural</span>
              <p>Activar brigada de inspección municipal en centros educativos clasificados como vulnerables.</p>
            </div>
          </div>
        </div>
      </div>

      <!-- In-Map Overlays (Floating North Arrow, Zoom & Extent controls) -->
      <div v-show="store.activeMapTab === 'map'" class="map-overlay-north">
        <div class="compass-rose" title="Norte geográfico WGS 84">
          <Compass :size="22" />
          <span class="north-letter">N</span>
        </div>
      </div>

      <div v-show="store.activeMapTab === 'map'" class="map-overlay-tools">
        <button class="map-tool-btn" title="Acercar" @click="store.mapZoom = Math.min(18, store.mapZoom + 1)">
          <ZoomIn :size="14" />
        </button>
        <button class="map-tool-btn" title="Alejar" @click="store.mapZoom = Math.max(4, store.mapZoom - 1)">
          <ZoomOut :size="14" />
        </button>
        <button class="map-tool-btn" title="Centrar en Zona" @click="centerToZone">
          <Crosshair :size="14" />
        </button>
        <button class="map-tool-btn" title="Extensión Total" @click="fullExtent">
          <Maximize2 :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gis-map-canvas-wrapper {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  position: relative;
  background-color: var(--gis-canvas);
  overflow: hidden;
}

/* Map View Tab Strip */
.map-view-tabs {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 27px;
  background-color: var(--gis-pane-header);
  border-bottom: 1px solid var(--gis-border);
  padding: 0 6px;
  user-select: none;
}

.tabs-left {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 100%;
}

.map-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
  font-weight: 500;
  color: var(--gis-text-dim);
  border-radius: 4px 4px 0 0;
  background-color: transparent;
  transition: all 0.12s ease;
}

.map-tab:hover {
  background-color: var(--gis-hover);
  color: var(--gis-text);
}

.map-tab.active {
  background-color: var(--gis-pane);
  color: var(--gis-text);
  font-weight: 600;
  border: 1px solid var(--gis-border);
  border-bottom: 1px solid var(--gis-pane);
  margin-bottom: -1px;
  z-index: 2;
}

.add-tab-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 3px;
  color: var(--gis-text-dim);
}

.add-tab-btn:hover {
  background-color: var(--gis-hover);
  color: var(--gis-text);
}

.tabs-right {
  font-size: 10.5px;
  color: var(--gis-text-dim);
}

.active-layer-indicator b {
  color: var(--gis-text);
}

/* Map Viewport */
.map-viewport-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.leaflet-map-element {
  width: 100%;
  height: 100%;
  background-color: #dbeafe;
}

/* In-Map Overlays */
.map-overlay-north {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 1000;
}

.compass-rose {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(4px);
  border: 1px solid var(--gis-border);
  border-radius: 4px;
  padding: 4px 6px;
  color: #B84A2C;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
}

.north-letter {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: -0.5px;
}

.map-overlay-tools {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(4px);
  border: 1px solid var(--gis-border);
  border-radius: 4px;
  padding: 2px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
}

.map-tool-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 3px;
  color: var(--gis-icon);
  transition: all 0.1s ease;
}

.map-tool-btn:hover {
  background: var(--gis-hover);
  color: var(--gis-text);
}

/* Matrix & AI Alternative Views */
.matrix-view-container,
.ai-view-container {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
  background: var(--gis-canvas);
}

.matrix-card,
.ai-panel-card {
  background: var(--gis-pane);
  border: 1px solid var(--gis-border);
  border-radius: 6px;
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
  box-shadow: 0 2px 8px var(--gis-shadow);
}

.matrix-desc,
.ai-desc {
  color: var(--gis-text-dim);
  margin-top: 4px;
  margin-bottom: 16px;
}

.matrix-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.matrix-stat {
  display: flex;
  flex-direction: column;
  padding: 14px;
  border-radius: 5px;
  border: 1px solid var(--gis-border);
}

.stat-critica { background: #fee2e2; border-color: #fca5a5; color: #991b1b; }
.stat-alta { background: #ffedd5; border-color: #fdba74; color: #9a3412; }
.stat-media { background: #fef9c3; border-color: #fde047; color: #854d0e; }
.stat-normal { background: #dcfce7; border-color: #86efac; color: #166534; }

.stat-number {
  font-size: 26px;
  font-weight: 800;
  font-family: var(--gis-mono);
}

.stat-label {
  font-size: 11px;
  font-weight: 600;
}

.ai-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-recommendations {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.ai-rec-item {
  padding: 12px;
  background: var(--gis-hover);
  border: 1px solid var(--gis-border);
  border-radius: 4px;
}

.rec-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 700;
  margin-bottom: 6px;
}

.rec-badge.red { background: #fee2e2; color: #991b1b; }
.rec-badge.amber { background: #fef9c3; color: #854d0e; }

.text-accent { color: var(--gis-accent); }
</style>
