<script setup lang="ts">
import { ref } from "vue";
import { useGisStore } from "../stores/useGisStore";
import {
  Compass,
  Radar,
  Activity,
  AlertTriangle,
  Flame,
  Table,
  SlidersHorizontal,
  Sparkles,
  Bot,
  MapPin,
  RefreshCw,
  Eye,
  Layers,
  ZoomIn,
  ZoomOut,
  Maximize2,
  FileSpreadsheet,
  Download,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  CloudRain,
  Wind,
  Thermometer,
} from "lucide-vue-next";

const store = useGisStore();

const isProjectMenuOpen = ref(false);

const tabs = [
  { id: "Home", label: "Home" },
  { id: "Data", label: "Data" },
  { id: "Style", label: "Style" },
  { id: "Analyze", label: "Analyze" },
  { id: "Simulacros", label: "Simulacros" },
  { id: "View", label: "View" },
];

function setTab(tabId: string) {
  store.activeRibbonTab = tabId;
  store.isRibbonMinimized = false;
}

function toggleMinimize() {
  store.isRibbonMinimized = !store.isRibbonMinimized;
}

function handleZoneChange(event: Event) {
  const select = event.target as HTMLSelectElement;
  store.selectZone(select.value);
}

function handleDrill(scenario: string) {
  store.changeScenario(scenario);
}

function openAIAssistant() {
  store.isAIAssistantOpen = true;
}

function exportGeoJSON() {
  const geojson = {
    type: "FeatureCollection",
    features: store.places.map((p) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [p.longitude, p.latitude],
      },
      properties: {
        id: p.id,
        name: p.name,
        category: p.category,
        vulnerability_group: p.vulnerability_group,
        priority_score: p.priority_score,
        urgency_level: p.urgency_level,
        attention_status: p.attention_status,
        zone_name: p.zone_name,
      },
    })),
  };
  const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `geo_prioridad_${store.selectedZoneKey}_${Date.now()}.geojson`;
  a.click();
  URL.revokeObjectURL(url);
}

function exportCSV() {
  const headers = ["id", "name", "category", "vulnerability_group", "priority_score", "urgency_level", "attention_status", "latitude", "longitude"];
  const rows = store.places.map((p) => [
    p.id,
    `"${p.name.replace(/"/g, '""')}"`,
    p.category,
    p.vulnerability_group,
    p.priority_score,
    p.urgency_level,
    p.attention_status,
    p.latitude,
    p.longitude,
  ]);
  const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `geo_prioridad_${store.selectedZoneKey}_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <div class="gis-ribbon-container">
    <!-- Tab Strip -->
    <div class="ribbon-tab-strip">
      <div class="tab-strip-left">
        <!-- RustGIS Brand Project Button -->
        <button
          class="project-tab-btn"
          @click="isProjectMenuOpen = !isProjectMenuOpen"
        >
          Project
          <ChevronDown :size="11" class="caret" />
        </button>

        <!-- Main Ribbon Tabs -->
        <button
          v-for="t in tabs"
          :key="t.id"
          class="ribbon-tab"
          :class="{ active: store.activeRibbonTab === t.id && !store.isRibbonMinimized }"
          @click="setTab(t.id)"
        >
          {{ t.label }}
        </button>
      </div>

      <div class="tab-strip-right">
        <button class="minimize-btn" title="Minimizar / Expandir Ribbon" @click="toggleMinimize">
          <ChevronUp v-if="!store.isRibbonMinimized" :size="13" />
          <ChevronDown v-else :size="13" />
        </button>
      </div>
    </div>

    <!-- Ribbon Body -->
    <div v-show="!store.isRibbonMinimized" class="ribbon-body">
      <!-- HOME TAB -->
      <div v-if="store.activeRibbonTab === 'Home'" class="ribbon-tab-content">
        <!-- Group: Operaciones COE -->
        <div class="ribbon-group">
          <div class="group-controls">
            <!-- Big Button: Sync Overpass -->
            <button
              class="ribbon-big-btn"
              :class="{ loading: store.isSyncing }"
              title="Sincronizar infraestructura y vulnerabilidades con Overpass API"
              @click="store.syncCurrentZone()"
            >
              <Radar :size="24" class="btn-icon text-accent" />
              <span class="btn-label">Sincronizar<br />Radar</span>
            </button>

            <!-- Dual stack: Zone Selector & Refresh -->
            <div class="control-col">
              <div class="field-row">
                <span class="field-label">Zona LATAM:</span>
                <select
                  class="gis-select zone-dropdown"
                  :value="store.selectedZoneKey"
                  @change="handleZoneChange"
                >
                  <optgroup
                    v-for="grp in store.groupedZones"
                    :key="grp.country"
                    :label="grp.country"
                  >
                    <option
                      v-for="z in grp.zones"
                      :key="z.key"
                      :value="z.key"
                    >
                      {{ z.name }} ({{ z.department }})
                    </option>
                  </optgroup>
                </select>
              </div>

              <div class="field-row">
                <span class="field-label">Radio Cobertura:</span>
                <span class="badge-pill">
                  {{ ((store.activeZone?.default_radius_meters ?? 8000) / 1000).toFixed(0) }} km
                </span>
                <button
                  class="icon-btn-micro"
                  title="Recargar datos de zona"
                  @click="store.fetchPlacesAndHeatmap()"
                >
                  <RefreshCw :size="11" />
                </button>
              </div>
            </div>
          </div>
          <span class="group-title">Operaciones EOC</span>
        </div>

        <!-- Group: Navegación Espacial -->
        <div class="ribbon-group">
          <div class="group-controls">
            <button class="ribbon-big-btn" title="Centrar mapa en la zona activa" @click="store.selectZone(store.selectedZoneKey)">
              <Compass :size="24" class="btn-icon text-teal" />
              <span class="btn-label">Centrar<br />Zona</span>
            </button>

            <div class="control-col">
              <button class="ribbon-small-btn" title="Zoom Acercar" @click="store.mapZoom = Math.min(18, store.mapZoom + 1)">
                <ZoomIn :size="14" />
                <span>Acercar</span>
              </button>
              <button class="ribbon-small-btn" title="Zoom Alejar" @click="store.mapZoom = Math.max(4, store.mapZoom - 1)">
                <ZoomOut :size="14" />
                <span>Alejar</span>
              </button>
            </div>

            <button class="ribbon-big-btn" title="Extensión completa del país" @click="store.mapZoom = 9">
              <Maximize2 :size="22" class="btn-icon" />
              <span class="btn-label">Extensión<br />Total</span>
            </button>
          </div>
          <span class="group-title">Navegación</span>
        </div>

        <!-- Group: Capas & Tablas -->
        <div class="ribbon-group">
          <div class="group-controls">
            <button
              class="ribbon-big-btn"
              :class="{ checked: store.isTableOpen }"
              title="Abrir / Cerrar tabla de atributos de lugares"
              @click="store.isTableOpen = !store.isTableOpen"
            >
              <Table :size="24" class="btn-icon text-blue" />
              <span class="btn-label">Tabla de<br />Atributos</span>
            </button>

            <button
              class="ribbon-big-btn"
              :class="{ checked: store.isLayersOpen }"
              title="Abrir / Cerrar panel de capas"
              @click="store.isLayersOpen = !store.isLayersOpen"
            >
              <Layers :size="24" class="btn-icon" />
              <span class="btn-label">Panel de<br />Capas</span>
            </button>
          </div>
          <span class="group-title">Capas y Datos</span>
        </div>

        <!-- Group: Telemetría de Amenazas -->
        <div class="ribbon-group">
          <div class="group-controls telemetry-group">
            <div class="telemetry-box" :class="`alert-${store.hazards?.overall_alert_level ?? 'green'}`">
              <div class="telemetry-header">
                <ShieldAlert :size="14" />
                <span>Alerta {{ (store.hazards?.overall_alert_level ?? 'Normal').toUpperCase() }}</span>
              </div>
              <div class="telemetry-data">
                <span class="telemetry-badge" title="Temperatura">
                  <Thermometer :size="11" />
                  {{ store.hazards?.weather?.temperature_c?.toFixed(1) ?? '24.5' }}°C
                </span>
                <span class="telemetry-badge" title="Precipitación">
                  <CloudRain :size="11" />
                  {{ store.hazards?.weather?.precipitation_mm?.toFixed(1) ?? '0.0' }} mm
                </span>
                <span class="telemetry-badge" title="Ráfagas de viento">
                  <Wind :size="11" />
                  {{ store.hazards?.weather?.wind_gusts_kmh?.toFixed(0) ?? '15' }} km/h
                </span>
              </div>
            </div>
          </div>
          <span class="group-title">Telemetría MARN/USGS</span>
        </div>
      </div>

      <!-- STYLE TAB -->
      <div v-else-if="store.activeRibbonTab === 'Style'" class="ribbon-tab-content">
        <!-- Group: Simbología -->
        <div class="ribbon-group">
          <div class="group-controls">
            <button
              class="ribbon-big-btn"
              :class="{ checked: store.symbologyMethod === 'graduated' }"
              @click="store.symbologyMethod = 'graduated'"
            >
              <SlidersHorizontal :size="24" class="btn-icon text-teal" />
              <span class="btn-label">Simbología<br />Graduada</span>
            </button>

            <div class="control-col">
              <div class="field-row">
                <span class="field-label">Campo:</span>
                <select v-model="store.symbologyField" class="gis-select">
                  <option value="priority_score">Score Multicriterio</option>
                  <option value="urgency_level">Nivel de Urgencia</option>
                  <option value="vulnerability_group">Grupo Vulnerable</option>
                  <option value="category">Categoría</option>
                </select>
              </div>
              <div class="field-row">
                <span class="field-label">Método:</span>
                <span class="badge-pill">Jenks (PostGIS)</span>
              </div>
            </div>
          </div>
          <span class="group-title">Simbología Primaria</span>
        </div>

        <!-- Group: Efectos y Transparencia -->
        <div class="ribbon-group">
          <div class="group-controls">
            <div class="control-col">
              <div class="field-row">
                <span class="field-label">Transparencia:</span>
                <input
                  v-model.number="store.layerOpacity"
                  type="range"
                  min="20"
                  max="100"
                  class="gis-slider"
                />
                <span class="slider-val">{{ store.layerOpacity }}%</span>
              </div>
              <div class="field-row check-row">
                <label class="check-label">
                  <input v-model="store.layerVisibility.heatmap" type="checkbox" />
                  <span>KDE Heatmap</span>
                </label>
                <label class="check-label">
                  <input v-model="store.layerVisibility.points" type="checkbox" />
                  <span>Puntos EOC</span>
                </label>
              </div>
            </div>
          </div>
          <span class="group-title">Efectos y Transparencia</span>
        </div>

        <!-- Group: Mapa Base -->
        <div class="ribbon-group">
          <div class="group-controls">
            <div class="control-col">
              <button
                class="ribbon-small-btn"
                :class="{ checked: store.basemap === 'carto-light' }"
                @click="store.basemap = 'carto-light'"
              >
                <span>Carto Positron</span>
              </button>
              <button
                class="ribbon-small-btn"
                :class="{ checked: store.basemap === 'osm' }"
                @click="store.basemap = 'osm'"
              >
                <span>OpenStreetMap</span>
              </button>
              <button
                class="ribbon-small-btn"
                :class="{ checked: store.basemap === 'carto-dark' }"
                @click="store.basemap = 'carto-dark'"
              >
                <span>Carto Dark Matter</span>
              </button>
            </div>
          </div>
          <span class="group-title">Mapa Base</span>
        </div>
      </div>

      <!-- ANALYZE TAB -->
      <div v-else-if="store.activeRibbonTab === 'Analyze'" class="ribbon-tab-content">
        <!-- Group: AI Assistant (Matching RustGIS Analyze Tab) -->
        <div class="ribbon-group">
          <div class="group-controls">
            <button
              class="ribbon-big-btn special-ai-btn"
              title="Abrir Asistente Táctico de IA para despacho"
              @click="openAIAssistant"
            >
              <Sparkles :size="24" class="btn-icon text-accent" />
              <span class="btn-label">AI Assistant<br />Despacho</span>
            </button>
          </div>
          <span class="group-title">Inteligencia Artificial</span>
        </div>

        <!-- Group: Geoprocesamiento -->
        <div class="ribbon-group">
          <div class="group-controls">
            <button
              class="ribbon-big-btn"
              title="Activar / Desactivar radio de buffer radar"
              :class="{ checked: store.layerVisibility.radar }"
              @click="store.layerVisibility.radar = !store.layerVisibility.radar"
            >
              <Radar :size="24" class="btn-icon text-amber" />
              <span class="btn-label">Buffer<br />Radar</span>
            </button>

            <button
              class="ribbon-big-btn"
              title="Activar capa de densidad PostGIS Kernel"
              :class="{ checked: store.layerVisibility.heatmap }"
              @click="store.layerVisibility.heatmap = !store.layerVisibility.heatmap"
            >
              <Flame :size="24" class="btn-icon text-red" />
              <span class="btn-label">Densidad<br />Kernel KDE</span>
            </button>
          </div>
          <span class="group-title">Geoprocesamiento</span>
        </div>

        <!-- Group: Exportar Resultados -->
        <div class="ribbon-group">
          <div class="group-controls">
            <button class="ribbon-big-btn" title="Descargar capa en formato GeoJSON estándar" @click="exportGeoJSON">
              <Download :size="24" class="btn-icon text-teal" />
              <span class="btn-label">Exportar<br />GeoJSON</span>
            </button>
            <button class="ribbon-big-btn" title="Descargar tabla en formato CSV estructurado" @click="exportCSV">
              <FileSpreadsheet :size="24" class="btn-icon text-green" />
              <span class="btn-label">Exportar<br />CSV</span>
            </button>
          </div>
          <span class="group-title">Exportación</span>
        </div>
      </div>

      <!-- SIMULACROS TAB -->
      <div v-else-if="store.activeRibbonTab === 'Simulacros'" class="ribbon-tab-content">
        <!-- Group: Iniciar Simulacro -->
        <div class="ribbon-group">
          <div class="group-controls">
            <button
              class="ribbon-big-btn drill-btn red"
              :class="{ checked: store.scenario === 'sonsonate_earthquake_m64' }"
              title="Simular terremoto M6.4 cercano a la costa"
              @click="handleDrill('sonsonate_earthquake_m64')"
            >
              <AlertTriangle :size="24" class="btn-icon text-red" />
              <span class="btn-label">Sismo M6.4<br />Sonsonate</span>
            </button>

            <button
              class="ribbon-big-btn drill-btn blue"
              :class="{ checked: store.scenario === 'pacific_tropical_storm' }"
              title="Simular tormenta tropical con precipitaciones intensas"
              @click="handleDrill('pacific_tropical_storm')"
            >
              <CloudRain :size="24" class="btn-icon text-blue" />
              <span class="btn-label">Tormenta<br />Pacífico</span>
            </button>

            <button
              class="ribbon-big-btn drill-btn amber"
              :class="{ checked: store.scenario === 'volcano_ash_ilamatepec' }"
              title="Simular caída de ceniza volcánica"
              @click="handleDrill('volcano_ash_ilamatepec')"
            >
              <Flame :size="24" class="btn-icon text-amber" />
              <span class="btn-label">Ceniza Volcánica<br />Ilamatepec</span>
            </button>

            <button
              class="ribbon-big-btn drill-btn green"
              :class="{ checked: store.scenario === 'none' }"
              title="Restablecer a monitoreo oficial en vivo"
              @click="handleDrill('none')"
            >
              <ShieldAlert :size="24" class="btn-icon text-green" />
              <span class="btn-label">Monitoreo<br />En Vivo</span>
            </button>
          </div>
          <span class="group-title">Simulador de Desastres COE</span>
        </div>

        <div class="ribbon-group">
          <div class="group-controls">
            <div class="drill-impact-panel">
              <span class="drill-impact-title">Estado de Simulación:</span>
              <strong v-if="store.scenario !== 'none'" class="impact-active">
                Simulacro Activo (+{{ store.hazards?.zone_hazard_bonus?.toFixed(1) ?? '0.0' }} pts de impacto)
              </strong>
              <strong v-else class="impact-live">
                Alimentación de sensores oficiales activa
              </strong>
            </div>
          </div>
          <span class="group-title">Impacto en Score</span>
        </div>
      </div>

      <!-- DATA TAB -->
      <div v-else-if="store.activeRibbonTab === 'Data'" class="ribbon-tab-content">
        <div class="ribbon-group">
          <div class="group-controls">
            <div class="control-col">
              <div class="field-row">
                <span class="field-label">Categoría:</span>
                <select v-model="store.filters.category" class="gis-select">
                  <option value="">Todas las categorías</option>
                  <option value="salud">Salud / Hospitales</option>
                  <option value="educacion">Educación / Escuelas</option>
                  <option value="comunidad">Comunidad</option>
                  <option value="albergue">Albergues Potenciales</option>
                </select>
              </div>
              <div class="field-row">
                <span class="field-label">Vulnerabilidad:</span>
                <select v-model="store.filters.vulnerabilityGroup" class="gis-select">
                  <option value="">Todos los grupos</option>
                  <option value="adultos_mayores">Adultos Mayores</option>
                  <option value="ninez">Primera Infancia / Niñez</option>
                  <option value="salud_critica">Salud Crítica</option>
                  <option value="general">Población General</option>
                </select>
              </div>
            </div>

            <div class="control-col">
              <div class="field-row">
                <span class="field-label">Estado:</span>
                <select v-model="store.filters.attentionStatus" class="gis-select">
                  <option value="">Cualquier estado</option>
                  <option value="pending">Pendiente de atención</option>
                  <option value="dispatched">En camino / Despachado</option>
                  <option value="attended">Atendido / Seguro</option>
                </select>
              </div>
              <div class="field-row">
                <span class="field-label">Filtrar texto:</span>
                <input
                  v-model="store.filters.search"
                  type="text"
                  placeholder="Buscar nombre..."
                  class="gis-input-text"
                />
              </div>
            </div>
          </div>
          <span class="group-title">Filtros de Atributos</span>
        </div>
      </div>

      <!-- VIEW TAB -->
      <div v-else-if="store.activeRibbonTab === 'View'" class="ribbon-tab-content">
        <div class="ribbon-group">
          <div class="group-controls">
            <button
              class="ribbon-big-btn"
              :class="{ checked: store.isLayersOpen }"
              @click="store.isLayersOpen = !store.isLayersOpen"
            >
              <Layers :size="24" class="btn-icon" />
              <span class="btn-label">Capas<br />(TOC)</span>
            </button>
            <button
              class="ribbon-big-btn"
              :class="{ checked: store.isTableOpen }"
              @click="store.isTableOpen = !store.isTableOpen"
            >
              <Table :size="24" class="btn-icon" />
              <span class="btn-label">Tabla de<br />Atributos</span>
            </button>
            <button
              class="ribbon-big-btn"
              :class="{ checked: store.isSymbologyOpen }"
              @click="store.isSymbologyOpen = !store.isSymbologyOpen"
            >
              <SlidersHorizontal :size="24" class="btn-icon" />
              <span class="btn-label">Panel de<br />Simbología</span>
            </button>
          </div>
          <span class="group-title">Disposición de Paneles</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gis-ribbon-container {
  display: flex;
  flex-direction: column;
  background-color: var(--gis-tab-strip);
  border-bottom: 1px solid var(--gis-border);
  user-select: none;
}

/* Tab Strip */
.ribbon-tab-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 30px;
  padding: 0 6px;
  background-color: var(--gis-header);
}

.tab-strip-left {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 100%;
}

/* RustGIS Brand Project Button */
.project-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 12px;
  background-color: var(--gis-brand);
  color: #ffffff;
  font-weight: 700;
  font-size: 11.5px;
  border-radius: 4px 4px 0 0;
  cursor: pointer;
  margin-right: 6px;
  transition: background-color 0.12s ease;
}

.project-tab-btn:hover {
  background-color: var(--gis-brand-dark);
}

.ribbon-tab {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  color: var(--gis-text);
  font-size: 11.5px;
  font-weight: 500;
  border-radius: 4px 4px 0 0;
  transition: all 0.12s ease;
}

.ribbon-tab:hover {
  background-color: var(--gis-hover);
}

.ribbon-tab.active {
  background-color: var(--gis-ribbon);
  color: var(--gis-accent-text);
  font-weight: 600;
  border: 1px solid var(--gis-border);
  border-bottom: 1px solid var(--gis-ribbon);
  margin-bottom: -1px;
  z-index: 2;
}

.tab-strip-right {
  display: flex;
  align-items: center;
}

.minimize-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 3px;
  color: var(--gis-text-dim);
}

.minimize-btn:hover {
  background: var(--gis-hover);
  color: var(--gis-text);
}

/* Ribbon Body */
.ribbon-body {
  height: 92px;
  background-color: var(--gis-ribbon);
  border-top: 1px solid var(--gis-border);
  padding: 4px 8px 2px 8px;
  overflow-x: auto;
  overflow-y: hidden;
  z-index: 1;
}

.ribbon-tab-content {
  display: flex;
  align-items: stretch;
  height: 100%;
  gap: 6px;
}

/* Ribbon Group */
.ribbon-group {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 2px 8px 3px 8px;
  border-right: 1px solid var(--gis-border);
  min-width: 80px;
}

.group-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
}

.group-title {
  text-align: center;
  font-size: 10px;
  color: var(--gis-group-label);
  margin-top: 2px;
  white-space: nowrap;
}

/* Ribbon Big Button */
.ribbon-big-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4px 8px;
  min-width: 54px;
  height: 64px;
  border-radius: 4px;
  color: var(--gis-text);
  transition: all 0.12s ease;
}

.ribbon-big-btn:hover {
  background-color: var(--gis-hover);
}

.ribbon-big-btn.checked {
  background-color: var(--gis-checked);
  border: 1px solid var(--gis-accent);
}

.btn-icon {
  margin-bottom: 3px;
  color: var(--gis-icon);
}

.btn-label {
  font-size: 10px;
  line-height: 1.15;
  text-align: center;
  color: var(--gis-text);
  font-weight: 500;
}

/* Small Buttons & Stacked Controls */
.control-col {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
}

.ribbon-small-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 6px;
  border-radius: 3px;
  font-size: 11px;
  color: var(--gis-text);
  transition: all 0.1s ease;
}

.ribbon-small-btn:hover {
  background: var(--gis-hover);
}

.ribbon-small-btn.checked {
  background: var(--gis-checked);
  font-weight: 600;
}

.field-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.field-label {
  color: var(--gis-text-dim);
  font-size: 10.5px;
  white-space: nowrap;
}

.gis-select {
  padding: 2px 4px;
  font-size: 11px;
  background: var(--gis-input);
  border: 1px solid var(--gis-input-border);
  border-radius: 3px;
}

.zone-dropdown {
  max-width: 175px;
  font-weight: 500;
}

.gis-input-text {
  padding: 2px 6px;
  font-size: 11px;
  width: 130px;
}

.badge-pill {
  padding: 1px 5px;
  background: var(--gis-hover);
  border: 1px solid var(--gis-border);
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  color: var(--gis-accent-text);
}

.icon-btn-micro {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 3px;
  color: var(--gis-text-dim);
}

.icon-btn-micro:hover {
  background: var(--gis-hover);
  color: var(--gis-text);
}

.gis-slider {
  width: 70px;
  height: 4px;
}

.slider-val {
  font-size: 10px;
  font-family: var(--gis-mono);
  color: var(--gis-text-dim);
  width: 28px;
}

.check-row {
  gap: 12px;
}

.check-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10.5px;
  cursor: pointer;
}

/* AI Button Glow */
.special-ai-btn {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(14, 147, 132, 0.08) 100%);
  border: 1px solid rgba(37, 99, 235, 0.25);
}

.special-ai-btn:hover {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.16) 0%, rgba(14, 147, 132, 0.16) 100%);
}

/* Telemetry box */
.telemetry-group {
  display: flex;
  align-items: center;
}

.telemetry-box {
  display: flex;
  flex-direction: column;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--gis-border);
  gap: 3px;
  min-width: 165px;
}

.telemetry-box.alert-green {
  background: #f0fdf4;
  border-color: #bbf7d0;
  color: #166534;
}

.telemetry-box.alert-yellow {
  background: #fefce8;
  border-color: #fef08a;
  color: #854d0e;
}

.telemetry-box.alert-orange {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #9a3412;
}

.telemetry-box.alert-red {
  background: #fef2f2;
  border-color: #fecaca;
  color: #991b1b;
}

.telemetry-header {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: 700;
  font-size: 10.5px;
}

.telemetry-data {
  display: flex;
  align-items: center;
  gap: 6px;
}

.telemetry-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  font-weight: 600;
}

/* Drill Impact */
.drill-impact-panel {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
}

.drill-impact-title {
  color: var(--gis-text-dim);
  font-size: 10px;
}

.impact-active {
  color: var(--gis-red);
  font-weight: 700;
}

.impact-live {
  color: var(--gis-green);
  font-weight: 600;
}

/* Colors */
.text-accent { color: var(--gis-accent); }
.text-teal { color: var(--gis-context); }
.text-amber { color: var(--gis-amber); }
.text-red { color: var(--gis-red); }
.text-blue { color: var(--gis-blue); }
.text-green { color: var(--gis-green); }
</style>
