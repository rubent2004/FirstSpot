<script setup lang="ts">
import { ref } from "vue";
import { useGisStore } from "../stores/useGisStore";
import {
  Layers,
  X,
  ChevronRight,
  ChevronDown,
  MapPin,
  Flame,
  Activity,
  Globe,
  Circle,
  Eye,
  EyeOff,
} from "lucide-vue-next";

const store = useGisStore();

const isPointsExpanded = ref(true);
const isHeatmapExpanded = ref(true);
const isHazardsExpanded = ref(true);
</script>

<template>
  <aside class="gis-layers-panel">
    <!-- Panel Header -->
    <div class="panel-header">
      <div class="panel-title">
        <Layers :size="13" class="panel-icon" />
        <span>Layers</span>
      </div>
      <button class="close-btn" title="Cerrar panel de capas" @click="store.isLayersOpen = false">
        <X :size="13" />
      </button>
    </div>

    <!-- Tree View -->
    <div class="layers-tree-container">
      <div class="tree-category-title">Drawing Order</div>

      <!-- Root Map Group -->
      <div class="tree-group">
        <div class="tree-item root-item">
          <Globe :size="13" class="item-icon text-teal" />
          <span class="item-name font-semibold">Geo-Prioridad LATAM</span>
          <span class="feature-count-badge">{{ store.places.length }}</span>
        </div>

        <!-- Layer 1: Centros Priorizados -->
        <div class="layer-block">
          <div class="tree-item layer-header-item">
            <button
              class="expand-toggle"
              @click="isPointsExpanded = !isPointsExpanded"
            >
              <ChevronDown v-if="isPointsExpanded" :size="12" />
              <ChevronRight v-else :size="12" />
            </button>

            <input
              v-model="store.layerVisibility.points"
              type="checkbox"
              class="gis-checkbox"
            />

            <MapPin :size="13" class="item-icon text-accent" />
            <span class="item-name">Centros Priorizados</span>
            <span class="feature-count-badge">{{ store.filteredPlaces.length }}</span>
          </div>

          <!-- Legend Sub-items -->
          <div v-show="isPointsExpanded" class="legend-list">
            <div class="legend-item">
              <span class="legend-swatch swatch-critical"></span>
              <span class="legend-label">Prioridad Crítica (&ge; 80)</span>
              <span class="legend-count">{{ store.heatmapMatrix.critical }}</span>
            </div>
            <div class="legend-item">
              <span class="legend-swatch swatch-high"></span>
              <span class="legend-label">Prioridad Alta (60 - 79)</span>
              <span class="legend-count">{{ store.heatmapMatrix.high }}</span>
            </div>
            <div class="legend-item">
              <span class="legend-swatch swatch-medium"></span>
              <span class="legend-label">Prioridad Media (40 - 59)</span>
              <span class="legend-count">{{ store.heatmapMatrix.medium }}</span>
            </div>
            <div class="legend-item">
              <span class="legend-swatch swatch-normal"></span>
              <span class="legend-label">Prioridad Normal (&lt; 40)</span>
              <span class="legend-count">{{ store.heatmapMatrix.normal }}</span>
            </div>
          </div>
        </div>

        <!-- Layer 2: PostGIS Heatmap (Kernel Density) -->
        <div class="layer-block">
          <div class="tree-item layer-header-item">
            <button
              class="expand-toggle"
              @click="isHeatmapExpanded = !isHeatmapExpanded"
            >
              <ChevronDown v-if="isHeatmapExpanded" :size="12" />
              <ChevronRight v-else :size="12" />
            </button>

            <input
              v-model="store.layerVisibility.heatmap"
              type="checkbox"
              class="gis-checkbox"
            />

            <Flame :size="13" class="item-icon text-red" />
            <span class="item-name">Densidad KDE (PostGIS)</span>
          </div>

          <div v-show="isHeatmapExpanded" class="legend-list">
            <div class="heatmap-ramp-container">
              <div class="heatmap-ramp-bar"></div>
              <div class="ramp-labels">
                <span>Baja</span>
                <span>Media</span>
                <span>Severa</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Layer 3: Amenazas Sísmicas y Meteorológicas -->
        <div class="layer-block">
          <div class="tree-item layer-header-item">
            <button
              class="expand-toggle"
              @click="isHazardsExpanded = !isHazardsExpanded"
            >
              <ChevronDown v-if="isHazardsExpanded" :size="12" />
              <ChevronRight v-else :size="12" />
            </button>

            <input
              v-model="store.layerVisibility.hazards"
              type="checkbox"
              class="gis-checkbox"
            />

            <Activity :size="13" class="item-icon text-amber" />
            <span class="item-name">Amenazas USGS / MARN</span>
            <span
              class="hazard-status-tag"
              :class="`tag-${store.hazards?.overall_alert_level ?? 'green'}`"
            >
              {{ store.hazards?.overall_alert_level ?? 'Normal' }}
            </span>
          </div>

          <div v-show="isHazardsExpanded" class="legend-list">
            <div
              v-for="evt in store.hazards?.events ?? []"
              :key="evt.id"
              class="hazard-event-row"
            >
              <span class="event-bullet">•</span>
              <span class="event-title">{{ evt.title }}</span>
            </div>
            <div v-if="(store.hazards?.events?.length ?? 0) === 0" class="no-events-text">
              Sin eventos sísmicos críticos activos en radio
            </div>
          </div>
        </div>

        <!-- Layer 4: Radio Buffer Radar -->
        <div class="layer-block">
          <div class="tree-item layer-header-item">
            <span class="expand-spacer"></span>
            <input
              v-model="store.layerVisibility.radar"
              type="checkbox"
              class="gis-checkbox"
            />
            <Circle :size="13" class="item-icon text-teal" />
            <span class="item-name">Radio Radar EOC</span>
            <span class="legend-count">
              {{ ((store.activeZone?.default_radius_meters ?? 8000) / 1000).toFixed(0) }} km
            </span>
          </div>
        </div>

        <!-- Layer 5: Basemap -->
        <div class="layer-block">
          <div class="tree-item layer-header-item">
            <span class="expand-spacer"></span>
            <Globe :size="13" class="item-icon text-dim" />
            <span class="item-name">Mapa Base: {{ store.basemap }}</span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.gis-layers-panel {
  display: flex;
  flex-direction: column;
  width: 250px;
  background-color: var(--gis-pane);
  border-right: 1px solid var(--gis-border);
  height: 100%;
  user-select: none;
  font-size: 11.5px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 28px;
  padding: 0 8px;
  background-color: var(--gis-pane-header);
  border-bottom: 1px solid var(--gis-border);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: var(--gis-text);
}

.panel-icon {
  color: var(--gis-icon);
}

.close-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 3px;
  color: var(--gis-text-dim);
}

.close-btn:hover {
  background: var(--gis-hover);
  color: var(--gis-text);
}

.layers-tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px 6px;
}

.tree-category-title {
  font-size: 10px;
  color: var(--gis-group-label);
  margin-bottom: 6px;
  padding-left: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tree-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tree-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px;
  border-radius: 3px;
  transition: background-color 0.1s ease;
}

.tree-item:hover {
  background-color: var(--gis-hover);
}

.root-item {
  font-weight: 600;
  padding-bottom: 4px;
}

.layer-block {
  margin-left: 6px;
  margin-top: 2px;
}

.layer-header-item {
  font-weight: 500;
}

.expand-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  color: var(--gis-text-dim);
}

.expand-spacer {
  width: 14px;
}

.gis-checkbox {
  width: 13px;
  height: 13px;
  accent-color: var(--gis-accent);
  cursor: pointer;
}

.item-icon {
  flex-shrink: 0;
}

.item-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feature-count-badge {
  font-size: 9.5px;
  font-weight: 600;
  background: var(--gis-hover);
  border: 1px solid var(--gis-border);
  border-radius: 9px;
  padding: 0 5px;
  color: var(--gis-accent-text);
}

.legend-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-left: 28px;
  margin-top: 3px;
  margin-bottom: 5px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
  color: var(--gis-text-dim);
}

.legend-swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}

.swatch-critical {
  background: #dc2626;
}

.swatch-high {
  background: #ea580c;
}

.swatch-medium {
  background: #d97706;
}

.swatch-normal {
  background: #16a34a;
}

.legend-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legend-count {
  font-family: var(--gis-mono);
  font-size: 10px;
  color: var(--gis-text-dim);
}

.heatmap-ramp-container {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
}

.heatmap-ramp-bar {
  height: 8px;
  border-radius: 2px;
  background: linear-gradient(90deg, #3b82f6 0%, #06b6d4 30%, #eab308 60%, #ef4444 100%);
  border: 1px solid var(--gis-border);
}

.ramp-labels {
  display: flex;
  justify-content: space-between;
  font-size: 9.5px;
  color: var(--gis-text-dim);
}

.hazard-status-tag {
  font-size: 9.5px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 600;
  text-transform: capitalize;
}

.tag-green { background: #dcfce7; color: #166534; }
.tag-yellow { background: #fef9c3; color: #854d0e; }
.tag-orange { background: #ffedd5; color: #9a3412; }
.tag-red { background: #fee2e2; color: #991b1b; }

.hazard-event-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--gis-text-dim);
}

.event-bullet {
  color: var(--gis-red);
}

.event-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-events-text {
  font-size: 10px;
  color: var(--gis-text-disabled);
  font-style: italic;
}

.text-teal { color: var(--gis-context); }
.text-accent { color: var(--gis-accent); }
.text-red { color: var(--gis-red); }
.text-amber { color: var(--gis-amber); }
.text-dim { color: var(--gis-text-dim); }
</style>
