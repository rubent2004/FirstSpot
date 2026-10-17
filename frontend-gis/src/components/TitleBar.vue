<script setup lang="ts">
import { computed } from "vue";
import { useGisStore } from "../stores/useGisStore";
import {
  FilePlus,
  FolderOpen,
  Save,
  Undo2,
  Redo2,
  Search,
  Moon,
  Sun,
  Layers,
  Table,
  SlidersHorizontal,
} from "lucide-vue-next";

const store = useGisStore();

const projectTitle = computed(() => {
  return `Geo-Prioridad LATAM • — ${store.activeZoneName || "Sonsonate"}`;
});

function handleSave() {
  store.syncCurrentZone();
}

function handleOpenCommand() {
  store.isCommandPaletteOpen = true;
}
</script>

<template>
  <header class="gis-titlebar">
    <!-- Left: Brand Logo & Quick Access -->
    <div class="titlebar-left">
      <div class="brand-badge">
        <svg class="brand-logo" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="12" cy="12" r="10" stroke="#B84A2C" stroke-width="2.2" />
          <polygon points="12,4 15,12 12,20 9,12" fill="#B84A2C" opacity="0.85" />
          <polygon points="4,12 12,9 20,12 12,15" fill="#0E9384" opacity="0.75" />
          <circle cx="12" cy="12" r="2.5" fill="#FFFFFF" />
        </svg>
        <span class="brand-text">RustGIS</span>
        <span class="brand-subtext">COE Pro</span>
      </div>

      <div class="quick-access-tools">
        <button class="qa-btn" title="Nuevo proyecto / Limpiar filtros" @click="store.initialize()">
          <FilePlus :size="13" />
        </button>
        <button class="qa-btn" title="Cargar capa / Recargar datos" @click="store.fetchPlacesAndHeatmap()">
          <FolderOpen :size="13" />
        </button>
        <button class="qa-btn" title="Sincronizar PostGIS con Overpass OSM" @click="handleSave">
          <Save :size="13" />
        </button>
        <span class="qa-sep"></span>
        <button class="qa-btn" title="Deshacer" disabled>
          <Undo2 :size="13" />
        </button>
        <button class="qa-btn" title="Rehacer" disabled>
          <Redo2 :size="13" />
        </button>
      </div>
    </div>

    <!-- Center: Project Title -->
    <div class="titlebar-center">
      <span class="project-title">{{ projectTitle }}</span>
    </div>

    <!-- Right: Command Search & Panel Toggles -->
    <div class="titlebar-right">
      <div class="command-search-box" @click="handleOpenCommand">
        <Search :size="12" class="search-icon" />
        <span class="search-placeholder">Command Search</span>
        <kbd class="shortcut-badge">Ctrl+K</kbd>
      </div>

      <div class="window-toggles">
        <button
          class="toggle-btn"
          :class="{ active: store.isLayersOpen }"
          title="Panel de Capas (TOC)"
          @click="store.isLayersOpen = !store.isLayersOpen"
        >
          <Layers :size="13" />
        </button>
        <button
          class="toggle-btn"
          :class="{ active: store.isTableOpen }"
          title="Tabla de Atributos"
          @click="store.isTableOpen = !store.isTableOpen"
        >
          <Table :size="13" />
        </button>
        <button
          class="toggle-btn"
          :class="{ active: store.isSymbologyOpen }"
          title="Panel de Simbología y Triaje"
          @click="store.isSymbologyOpen = !store.isSymbologyOpen"
        >
          <SlidersHorizontal :size="13" />
        </button>
        <button
          class="toggle-btn"
          :title="store.isDark ? 'Tema Claro' : 'Tema Oscuro'"
          @click="store.toggleDark()"
        >
          <Sun v-if="store.isDark" :size="13" />
          <Moon v-else :size="13" />
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.gis-titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  background-color: var(--gis-header);
  border-bottom: 1px solid var(--gis-border);
  padding: 0 8px;
  font-size: 11.5px;
  user-select: none;
}

.titlebar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.brand-logo {
  width: 17px;
  height: 17px;
}

.brand-text {
  font-weight: 700;
  font-size: 12.5px;
  letter-spacing: -0.2px;
  color: var(--gis-brand);
}

.brand-subtext {
  font-size: 10px;
  padding: 1px 4px;
  background: var(--gis-border);
  color: var(--gis-text-dim);
  border-radius: 3px;
  font-weight: 600;
}

.quick-access-tools {
  display: flex;
  align-items: center;
  gap: 2px;
}

.qa-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 3px;
  color: var(--gis-icon);
  transition: all 0.12s ease;
}

.qa-btn:hover:not(:disabled) {
  background: var(--gis-hover);
  color: var(--gis-text);
}

.qa-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.qa-sep {
  width: 1px;
  height: 14px;
  background: var(--gis-border);
  margin: 0 3px;
}

.titlebar-center {
  flex: 1;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 16px;
}

.project-title {
  font-weight: 600;
  color: var(--gis-text);
  font-size: 11.5px;
  letter-spacing: 0.1px;
}

.titlebar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.command-search-box {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--gis-input);
  border: 1px solid var(--gis-input-border);
  border-radius: 3px;
  padding: 2px 7px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.command-search-box:hover {
  border-color: var(--gis-accent);
}

.search-icon {
  color: var(--gis-text-dim);
}

.search-placeholder {
  color: var(--gis-text-dim);
  font-size: 11px;
}

.shortcut-badge {
  font-family: var(--gis-mono);
  font-size: 9.5px;
  background: var(--gis-header);
  border: 1px solid var(--gis-border);
  border-radius: 2px;
  padding: 1px 3px;
  color: var(--gis-text-dim);
}

.window-toggles {
  display: flex;
  align-items: center;
  gap: 2px;
}

.toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 3px;
  color: var(--gis-icon);
  transition: all 0.12s ease;
}

.toggle-btn:hover {
  background: var(--gis-hover);
}

.toggle-btn.active {
  background: var(--gis-checked);
  color: var(--gis-accent-text);
}
</style>
