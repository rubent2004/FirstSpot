<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  Aim, ArrowDown, ArrowUp, DataAnalysis, Files, Filter, MapLocation, Moon,
  Refresh, Search, Setting, Sunny, User, Warning, ZoomIn,
} from "@element-plus/icons-vue";
import {
  ElDropdown, ElDropdownItem, ElDropdownMenu, ElInput, ElInputNumber, ElOption,
  ElRadioButton, ElRadioGroup, ElSelect, ElSlider, ElSwitch,
} from "element-plus";
import type { InstitutionAccountRead, PredefinedZoneRead } from "../api/client";
import type { PlaceFilters } from "../stores/usePrioritizationStore";
import { useI18n } from "../i18n/useI18n";
import { formatDistance } from "../utils/formatDistance";

const props = defineProps<{
  zones: PredefinedZoneRead[];
  selectedZoneKey: string;
  activeZoneName: string;
  isSyncing: boolean;
  isLoading: boolean;
  hasError: boolean;
  radiusEnabled: boolean;
  radiusMeters: number;
  isDark: boolean;
  locale: "es" | "en";
  showHeatmapLayer: boolean;
  showMarkersLayer: boolean;
  showHazardsLayer: boolean;
  tacticalBasemap: boolean;
  filters: PlaceFilters;
  institutionAccount?: InstitutionAccountRead | null;
}>();

const emit = defineEmits<{
  (e: "change-zone", key: string): void;
  (e: "sync-zone"): void;
  (e: "update:radius-enabled", value: boolean): void;
  (e: "update:radius-meters", value: number): void;
  (e: "reset-filters"): void;
  (e: "refresh-hazards"): void;
  (e: "center-map"): void;
  (e: "fit-map"): void;
  (e: "toggle-theme"): void;
  (e: "toggle-locale"): void;
  (e: "filter-change"): void;
  (e: "update:show-heatmap-layer", value: boolean): void;
  (e: "update:show-markers-layer", value: boolean): void;
  (e: "update:show-hazards-layer", value: boolean): void;
  (e: "update:tactical-basemap", value: boolean): void;
  (e: "open-institution-access"): void;
}>();

const tabs = computed(() => props.locale === "es"
  ? ["Inicio", "Datos", "Estilo", "Analizar", "Vista"]
  : ["Home", "Data", "Style", "Analyze", "View"]);
const tabCommandIds = ["tab-home", "tab-data", "tab-style", "tab-analyze", "tab-view"];
const activeTab = ref(0);
const ribbonExpanded = ref(true);
const commandOpen = ref(false);
const commandQuery = ref("");
const commandInput = ref<HTMLInputElement | null>(null);
const commandTrigger = ref<HTMLButtonElement | null>(null);
const activeCommandIndex = ref(0);
let searchDebounceTimer: number | undefined;
const commandLabel = computed(() => props.locale === "es" ? "Buscar comandos" : "Search commands");
const radiusKilometers = computed(() => props.radiusMeters / 1000);
const radiusLabel = computed(() => formatDistance(props.radiusMeters, props.locale));
const radiusPresets = computed(() => [500, 1000, 3000, 5000, 10000, 25000].map((meters) => ({
  meters,
  label: formatDistance(meters, props.locale),
})));
const { t } = useI18n();
const hasActiveFilters = computed(() => Boolean(
  props.filters.search.trim() ||
  props.filters.category ||
  props.filters.vulnerabilityGroup ||
  props.filters.attentionStatus ||
  props.filters.minUrgency !== null ||
  !props.filters.includeAttendedInHeatmap,
));
const connectionState = computed(() => {
  if (props.hasError) return props.locale === "es" ? "Revisar datos" : "Check data";
  if (props.isLoading || props.isSyncing) return props.locale === "es" ? "Actualizando" : "Updating";
  return props.locale === "es" ? "En línea" : "Online";
});

function updateRadiusFromKilometers(value: number | number[] | undefined): void {
  if (typeof value !== "number" || !Number.isFinite(value)) return;
  const clampedKilometers = Math.min(25, Math.max(0.5, value));
  const steppedKilometers = Math.round(clampedKilometers * 2) / 2;
  emit("update:radius-meters", Math.round(steppedKilometers * 1000));
}

function openRadiusSettings(): void {
  ribbonExpanded.value = true;
  activeTab.value = 3;
}

const commands = computed(() => {
  const es = props.locale === "es";
  return [
    { id: "sync-zone", title: es ? "Sincronizar lugares de la zona" : "Sync places in this zone", group: es ? "Datos" : "Data", icon: Refresh },
    { id: "center-map", title: es ? "Centrar mapa en la zona" : "Center map on zone", group: es ? "Mapa" : "Map", icon: Aim },
    { id: "fit-map", title: es ? "Ajustar mapa a los lugares" : "Fit map to places", group: es ? "Mapa" : "Map", icon: ZoomIn },
    { id: "refresh-hazards", title: es ? "Actualizar amenazas" : "Refresh hazards", group: es ? "Análisis" : "Analysis", icon: Warning },
    { id: "reset-filters", title: es ? "Limpiar filtros" : "Clear filters", group: es ? "Datos" : "Data", icon: Filter },
    { id: "place-search", title: es ? "Buscar lugar priorizado" : "Search prioritized places", group: es ? "Datos" : "Data", icon: Search },
    { id: "tab-home", title: es ? "Abrir Inicio" : "Open Home", group: es ? "Pestañas" : "Tabs", icon: Files },
    { id: "tab-data", title: es ? "Abrir Datos" : "Open Data", group: es ? "Pestañas" : "Tabs", icon: DataAnalysis },
    { id: "tab-style", title: es ? "Abrir Estilo" : "Open Style", group: es ? "Pestañas" : "Tabs", icon: MapLocation },
    { id: "tab-analyze", title: es ? "Abrir Analizar" : "Open Analyze", group: es ? "Pestañas" : "Tabs", icon: Warning },
    { id: "tab-view", title: es ? "Abrir Vista" : "Open View", group: es ? "Pestañas" : "Tabs", icon: Setting },
    { id: "toggle-theme", title: es ? "Cambiar tema claro/oscuro" : "Toggle light/dark theme", group: es ? "Apariencia" : "Appearance", icon: props.isDark ? Sunny : Moon },
    { id: "toggle-locale", title: es ? "Cambiar idioma" : "Change language", group: es ? "Apariencia" : "Appearance", icon: Setting },
  ];
});
const filteredCommands = computed(() => {
  const query = commandQuery.value.trim().toLocaleLowerCase();
  if (!query) return commands.value;
  return commands.value.filter((command) =>
    `${command.title} ${command.group}`.toLocaleLowerCase().includes(query),
  );
});

watch(filteredCommands, () => { activeCommandIndex.value = 0; });

function focusPlaceSearch(): void {
  activeTab.value = 1;
  void nextTick(() => {
    document.querySelector<HTMLInputElement>(
      '[data-testid="ribbon-filter-search"]',
    )?.focus();
  });
}

function handlePlaceSearchInput(): void {
  window.clearTimeout(searchDebounceTimer);
  if (!props.filters.search.trim()) {
    emit("filter-change");
    return;
  }
  searchDebounceTimer = window.setTimeout(() => emit("filter-change"), 250);
}

function openCommandPalette(): void {
  commandQuery.value = "";
  activeCommandIndex.value = 0;
  commandOpen.value = true;
  void nextTick(() => commandInput.value?.focus());
}

function closeCommandPalette(restoreFocus = true): void {
  commandOpen.value = false;
  if (restoreFocus) void nextTick(() => commandTrigger.value?.focus());
}

function runCommand(id: string): void {
  if (id === "sync-zone") emit("sync-zone");
  else if (id === "center-map") emit("center-map");
  else if (id === "fit-map") emit("fit-map");
  else if (id === "refresh-hazards") emit("refresh-hazards");
  else if (id === "reset-filters") {
    if (hasActiveFilters.value) emit("reset-filters");
    else {
      closeCommandPalette();
      return;
    }
  }
  else if (id === "place-search") focusPlaceSearch();
  else if (id.startsWith("tab-")) activeTab.value = tabCommandIds.indexOf(id);
  else if (id === "toggle-theme") emit("toggle-theme");
  else if (id === "toggle-locale") emit("toggle-locale");
  closeCommandPalette(id !== "place-search");
}

function handleProjectCommand(command: string): void {
  if (command === "sync-zone") emit("sync-zone");
  else if (command === "reset-filters" && hasActiveFilters.value) emit("reset-filters");
  else openCommandPalette();
}

function handleTabKeydown(event: KeyboardEvent, index: number): void {
  let nextIndex: number;
  if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.value.length;
  else if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.value.length) % tabs.value.length;
  else if (event.key === "Home") nextIndex = 0;
  else if (event.key === "End") nextIndex = tabs.value.length - 1;
  else return;

  event.preventDefault();
  activeTab.value = nextIndex;
  void nextTick(() => document.getElementById(`geo-ribbon-tab-${nextIndex}`)?.focus());
}

function handleGlobalKeydown(event: KeyboardEvent): void {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openCommandPalette();
    return;
  }
  if (!commandOpen.value) return;

  if (event.key === "Escape") {
    event.preventDefault();
    closeCommandPalette();
  } else if (event.key === "ArrowDown" && filteredCommands.value.length > 0) {
    event.preventDefault();
    activeCommandIndex.value = (activeCommandIndex.value + 1) % filteredCommands.value.length;
  } else if (event.key === "ArrowUp" && filteredCommands.value.length > 0) {
    event.preventDefault();
    activeCommandIndex.value = (activeCommandIndex.value - 1 + filteredCommands.value.length) % filteredCommands.value.length;
  } else if (event.key === "Enter" && filteredCommands.value[activeCommandIndex.value]) {
    event.preventDefault();
    runCommand(filteredCommands.value[activeCommandIndex.value].id);
  } else if (event.key === "Tab") {
    const focusable = Array.from(
      document.querySelectorAll<HTMLElement>(".command-palette input, .command-palette button"),
    );
    if (focusable.length > 0) {
      event.preventDefault();
      const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
      const step = event.shiftKey ? -1 : 1;
      const nextIndex = (currentIndex + step + focusable.length) % focusable.length;
      focusable[nextIndex]?.focus();
    }
  }
}
onMounted(() => window.addEventListener("keydown", handleGlobalKeydown));
onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleGlobalKeydown);
  window.clearTimeout(searchDebounceTimer);
});
</script>

<template>
  <section class="geo-ribbon" :aria-label="props.locale === 'es' ? 'Cinta de herramientas del mapa' : 'Map tools ribbon'">
    <div class="geo-titlebar">
      <div class="geo-brand">
        <img class="geo-mark" src="/firstspot-logo.svg" alt="" aria-hidden="true" />
        <strong>FirstSpot</strong>
        <span class="geo-product-tag">COE</span>
      </div>
      <div class="geo-quick-access" aria-label="Acceso rápido">
        <button class="geo-quick" :title="props.locale === 'es' ? 'Actualizar lugares' : 'Refresh places'" @click="emit('sync-zone')"><Refresh /></button>
        <button class="geo-quick" :disabled="!hasActiveFilters" :title="props.locale === 'es' ? 'Limpiar filtros' : 'Clear filters'" @click="emit('reset-filters')"><Filter /></button>
      </div>
      <div class="geo-project-title">{{ props.activeZoneName || "El Salvador" }} <span>— {{ props.locale === "es" ? "Mapa de prioridad" : "Priority map" }}</span></div>
      <button ref="commandTrigger" class="geo-search" type="button" :aria-label="commandLabel" @click="openCommandPalette"><Search /><span>{{ commandLabel }}</span><kbd>Ctrl K</kbd></button>
      <button
        class="geo-account"
        type="button"
        :title="props.institutionAccount ? props.institutionAccount.institution.name : (props.locale === 'es' ? 'Acceso institucional' : 'Institutional access')"
        data-testid="institution-access-trigger"
        @click="emit('open-institution-access')"
      >
        <User />
        <span>{{ props.institutionAccount?.institution.name ?? (props.locale === 'es' ? 'Instituciones' : 'Institutions') }}</span>
        <i :class="{ verified: props.institutionAccount?.institution.verification_status === 'verified' }"></i>
      </button>
      <button class="geo-icon-btn" :title="props.locale === 'es' ? 'Cambiar tema' : 'Toggle theme'" @click="emit('toggle-theme')"><Sunny v-if="props.isDark" /><Moon v-else /></button>
      <button
        class="geo-icon-btn ribbon-expand-toggle"
        type="button"
        :aria-expanded="ribbonExpanded"
        :aria-label="ribbonExpanded ? (props.locale === 'es' ? 'Contraer cinta' : 'Collapse ribbon') : (props.locale === 'es' ? 'Expandir cinta' : 'Expand ribbon')"
        :title="ribbonExpanded ? (props.locale === 'es' ? 'Contraer cinta' : 'Collapse ribbon') : (props.locale === 'es' ? 'Expandir cinta' : 'Expand ribbon')"
        @click="ribbonExpanded = !ribbonExpanded"
      ><ArrowUp v-if="ribbonExpanded" /><ArrowDown v-else /></button>
      <button class="geo-locale" :title="props.locale === 'es' ? 'Switch to English' : 'Cambiar a español'" @click="emit('toggle-locale')">{{ props.locale.toUpperCase() }}</button>
    </div>

    <div class="geo-tabrow">
      <ElDropdown trigger="click" @command="handleProjectCommand">
        <button class="geo-project-tab" type="button" aria-haspopup="menu">
          <Files />{{ props.locale === "es" ? "Proyecto" : "Project" }}<ArrowDown class="project-caret" />
        </button>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem command="sync-zone">{{ props.locale === "es" ? "Sincronizar zona actual" : "Sync current zone" }}</ElDropdownItem>
            <ElDropdownItem command="reset-filters" :disabled="!hasActiveFilters">{{ props.locale === "es" ? "Limpiar filtros" : "Clear filters" }}</ElDropdownItem>
            <ElDropdownItem divided command="commands">{{ props.locale === "es" ? "Buscar comando…" : "Search commands…" }} <kbd class="menu-shortcut">Ctrl K</kbd></ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
      <div class="geo-tab-list" role="tablist" :aria-label="props.locale === 'es' ? 'Herramientas' : 'Tools'">
        <button
          v-for="(tab, index) in tabs"
          :id="`geo-ribbon-tab-${index}`"
          :key="tab"
          class="geo-tab"
          :class="{ selected: activeTab === index }"
          type="button"
          role="tab"
          :aria-selected="activeTab === index"
          aria-controls="geo-ribbon-panel"
          :tabindex="activeTab === index ? 0 : -1"
          @click="activeTab = index"
          @keydown="handleTabKeydown($event, index)"
        >{{ tab }}</button>
      </div>
      <div class="geo-tab-spacer"></div>
      <span class="geo-project-state" :class="{ 'is-updating': props.isLoading || props.isSyncing, 'has-error': props.hasError }"><i></i>{{ connectionState }}</span>
    </div>

    <div
      id="geo-ribbon-panel"
      class="geo-toolrow"
      role="tabpanel"
      tabindex="0"
      :aria-labelledby="`geo-ribbon-tab-${activeTab}`"
      v-show="ribbonExpanded"
    >
      <template v-if="activeTab === 0">
        <div class="geo-toolgroup geo-zone-group">
          <button class="geo-big-tool primary-tool" :disabled="props.isSyncing" @click="emit('sync-zone')"><span class="geo-tool-icon"><Refresh /></span><span>{{ props.isSyncing ? (props.locale === "es" ? "Sincronizando" : "Syncing") : (props.locale === "es" ? "Sincronizar" : "Sync places") }}</span></button>
          <div class="geo-tool-stack">
            <label>{{ props.locale === "es" ? "ZONA DE TRABAJO" : "WORKING AREA" }}</label>
            <ElSelect :model-value="props.selectedZoneKey" filterable size="small" class="geo-zone-select" @update:model-value="emit('change-zone', String($event))">
              <ElOption v-for="zone in props.zones" :key="zone.key" :label="`${zone.name} · ${zone.department}`" :value="zone.key" />
            </ElSelect>
            <div class="geo-radius-control geo-home-radius">
              <ElSwitch
                :model-value="props.radiusEnabled"
                size="small"
                :aria-label="props.locale === 'es' ? 'Activar radio personalizado' : 'Enable custom radius'"
                @update:model-value="emit('update:radius-enabled', Boolean($event))"
              />
              <span>{{ props.locale === "es" ? "Radio personalizado" : "Custom radius" }}</span>
              <button class="geo-radius-summary" type="button" @click="openRadiusSettings">
                <strong>{{ radiusLabel }}</strong>
                <span>{{ props.locale === "es" ? "Editar" : "Edit" }}</span>
              </button>
            </div>
          </div>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Área de trabajo" : "Workspace" }}</span>
        </div>
        <div class="geo-toolgroup">
          <button class="geo-big-tool" @click="emit('center-map')"><span class="geo-tool-icon teal-icon"><Aim /></span><span>{{ props.locale === "es" ? "Centrar zona" : "Center zone" }}</span></button>
          <div class="geo-tool-stack compact-stack"><button class="geo-small-tool" @click="emit('fit-map')"><ZoomIn />{{ props.locale === "es" ? "Ajustar datos" : "Fit data" }}</button><span class="geo-scale-readout">{{ props.locale === "es" ? "Cobertura" : "Coverage" }} · {{ radiusLabel }}</span></div>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Navegación" : "Navigate" }}</span>
        </div>
        <div class="geo-toolgroup">
          <button class="geo-big-tool" @click="emit('refresh-hazards')"><span class="geo-tool-icon orange-icon"><Warning /></span><span>{{ props.locale === "es" ? "Amenazas" : "Hazards" }}</span></button>
          <div class="geo-tool-stack compact-stack"><button class="geo-small-tool" :disabled="!hasActiveFilters" @click="emit('reset-filters')"><DataAnalysis />{{ props.locale === "es" ? "Restablecer filtros" : "Reset filters" }}</button><span class="geo-scale-readout">{{ props.locale === "es" ? "Datos priorizados" : "Prioritized places" }}</span></div>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Operaciones" : "Operations" }}</span>
        </div>
      </template>
      <template v-else-if="activeTab === 1">
        <div class="geo-toolgroup geo-filter-search">
          <label class="geo-filter-label">{{ props.locale === "es" ? "BUSCAR LUGAR" : "SEARCH PLACE" }}</label>
          <ElInput v-model="props.filters.search" clearable size="small" data-testid="ribbon-filter-search" :placeholder="t.queue.searchPlaceholder" :aria-label="t.queue.searchPlaceholder" @input="handlePlaceSearchInput">
            <template #prefix><Search /></template>
          </ElInput>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Búsqueda" : "Search" }}</span>
        </div>
        <div class="geo-toolgroup geo-filter-selects">
          <label class="geo-filter-label">{{ props.locale === "es" ? "EJE DE VULNERABILIDAD" : "VULNERABILITY AXIS" }}</label>
          <ElSelect v-model="props.filters.vulnerabilityGroup" clearable size="small" :placeholder="t.queue.allGroups" :aria-label="t.queue.allGroups" @change="emit('filter-change')">
            <ElOption v-for="(label, groupKey) in t.groups" :key="groupKey" :label="label" :value="groupKey" />
          </ElSelect>
          <ElSelect v-model="props.filters.category" clearable size="small" :placeholder="t.queue.allCategories" :aria-label="t.queue.allCategories" @change="emit('filter-change')">
            <ElOption v-for="(label, categoryKey) in t.categories" :key="categoryKey" :label="label" :value="categoryKey" />
          </ElSelect>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Tipo de lugar" : "Place type" }}</span>
        </div>
        <div class="geo-toolgroup geo-filter-status">
          <label class="geo-filter-label">{{ props.locale === "es" ? "ESTADO DE ATENCIÓN" : "ATTENTION STATUS" }}</label>
          <ElRadioGroup v-model="props.filters.attentionStatus" size="small" :aria-label="t.queue.statusAll" @change="emit('filter-change')">
            <ElRadioButton value="">{{ t.queue.statusAll }}</ElRadioButton>
            <ElRadioButton value="pending">{{ t.queue.statusPending }}</ElRadioButton>
            <ElRadioButton value="in_progress">{{ t.queue.statusInProgress }}</ElRadioButton>
            <ElRadioButton value="attended">{{ t.queue.statusAttended }}</ElRadioButton>
          </ElRadioGroup>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Despacho" : "Dispatch" }}</span>
        </div>
        <div class="geo-toolgroup geo-filter-heatmap">
          <label class="geo-filter-label">{{ props.locale === "es" ? "CAPA DE CALOR" : "HEATMAP" }}</label>
          <div class="geo-radius-control"><ElSwitch v-model="props.filters.includeAttendedInHeatmap" size="small" @change="emit('filter-change')" /><span>{{ t.queue.showAttendedHeatmap }}</span></div>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Visualización" : "Display" }}</span>
        </div>
        <div class="geo-toolgroup geo-filter-actions">
          <button class="geo-big-tool" type="button" :disabled="!hasActiveFilters" @click="emit('reset-filters')"><span class="geo-tool-icon teal-icon"><Filter /></span><span>{{ props.locale === "es" ? "Limpiar filtros" : "Clear filters" }}</span></button>
          <button class="geo-big-tool" type="button" :disabled="props.isSyncing" @click="emit('sync-zone')"><span class="geo-tool-icon"><Refresh /></span><span>{{ props.isSyncing ? (props.locale === "es" ? "Sincronizando" : "Syncing") : (props.locale === "es" ? "Sincronizar lugares" : "Sync places") }}</span></button>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Acciones de datos" : "Data actions" }}</span>
        </div>
      </template>
      <template v-else-if="activeTab === 2">
        <div class="geo-toolgroup geo-layer-tools">
          <button class="geo-big-tool layer-tool" :class="{ 'is-active': props.showHeatmapLayer }" type="button" :aria-pressed="props.showHeatmapLayer" @click="emit('update:show-heatmap-layer', !props.showHeatmapLayer)">
            <span class="geo-tool-icon orange-icon"><DataAnalysis /></span><span>{{ props.locale === "es" ? "Mapa de calor" : "Heatmap" }}</span>
          </button>
          <button class="geo-big-tool layer-tool" :class="{ 'is-active': props.showMarkersLayer }" type="button" :aria-pressed="props.showMarkersLayer" @click="emit('update:show-markers-layer', !props.showMarkersLayer)">
            <span class="geo-tool-icon teal-icon"><MapLocation /></span><span>{{ props.locale === "es" ? "Marcadores" : "Markers" }}</span>
          </button>
          <button class="geo-big-tool layer-tool" :class="{ 'is-active': props.showHazardsLayer }" type="button" :aria-pressed="props.showHazardsLayer" @click="emit('update:show-hazards-layer', !props.showHazardsLayer)">
            <span class="geo-tool-icon orange-icon"><Warning /></span><span>{{ props.locale === "es" ? "Amenazas" : "Hazards" }}</span>
          </button>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Capas visibles" : "Visible layers" }}</span>
        </div>
        <div class="geo-toolgroup">
          <button class="geo-big-tool layer-tool" :class="{ 'is-active': !props.tacticalBasemap }" type="button" :aria-pressed="!props.tacticalBasemap" @click="emit('update:tactical-basemap', false)">
            <span class="geo-tool-icon teal-icon"><Files /></span><span>{{ props.locale === "es" ? "Mapa claro" : "Light map" }}</span>
          </button>
          <button class="geo-big-tool layer-tool" :class="{ 'is-active': props.tacticalBasemap }" type="button" :aria-pressed="props.tacticalBasemap" @click="emit('update:tactical-basemap', true)">
            <span class="geo-tool-icon"><MapLocation /></span><span>{{ props.locale === "es" ? "Mapa táctico" : "Tactical map" }}</span>
          </button>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Mapa base" : "Basemap" }}</span>
        </div>
        <div class="geo-toolgroup">
          <button class="geo-big-tool" type="button" @click="emit('fit-map')"><span class="geo-tool-icon teal-icon"><ZoomIn /></span><span>{{ props.locale === "es" ? "Ajustar a lugares" : "Fit to places" }}</span></button>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Extensión" : "Extent" }}</span>
        </div>
      </template>
      <template v-else-if="activeTab === 3">
        <div class="geo-toolgroup"><button class="geo-big-tool" @click="emit('refresh-hazards')"><span class="geo-tool-icon orange-icon"><Warning /></span><span>{{ props.locale === "es" ? "Actualizar amenazas" : "Refresh hazards" }}</span></button><div class="geo-tool-stack compact-stack"><span class="geo-scale-readout">USGS · Open-Meteo · NASA EONET</span></div><span class="geo-group-caption">{{ props.locale === "es" ? "Monitoreo en vivo" : "Live monitoring" }}</span></div>
        <div class="geo-toolgroup geo-radius-editor">
          <div class="geo-radius-editor-heading">
            <span class="geo-tool-icon teal-icon"><Aim /></span>
            <div class="geo-radius-heading-copy">
              <strong>{{ props.locale === "es" ? "Radio de análisis" : "Analysis radius" }}</strong>
              <small>{{ props.locale === "es" ? "Activa y haz clic en el mapa para elegir el centro" : "Enable it, then click the map to set the center" }}</small>
            </div>
            <ElSwitch
              :model-value="props.radiusEnabled"
              size="small"
              :aria-label="props.locale === 'es' ? 'Activar radio personalizado' : 'Enable custom radius'"
              @update:model-value="emit('update:radius-enabled', Boolean($event))"
            />
          </div>
          <div class="geo-radius-value-row">
            <ElSlider
              :model-value="radiusKilometers"
              :min="0.5"
              :max="25"
              :step="0.5"
              :show-tooltip="false"
              :aria-label="props.locale === 'es' ? 'Ajustar radio en kilómetros' : 'Set radius in kilometers'"
              @update:model-value="updateRadiusFromKilometers"
            />
            <div class="geo-radius-number">
              <ElInputNumber
                :model-value="radiusKilometers"
                :min="0.5"
                :max="25"
                :step="0.5"
                :precision="1"
                :step-strictly="true"
                controls-position="right"
                size="small"
                :aria-label="props.locale === 'es' ? 'Radio en kilómetros' : 'Radius in kilometers'"
                @update:model-value="updateRadiusFromKilometers"
              />
              <span>km</span>
            </div>
          </div>
          <div class="geo-radius-presets" role="group" :aria-label="props.locale === 'es' ? 'Radios predefinidos' : 'Radius presets'">
            <button
              v-for="preset in radiusPresets"
              :key="preset.meters"
              type="button"
              class="geo-radius-preset"
              :class="{ 'is-selected': props.radiusMeters === preset.meters }"
              :aria-pressed="props.radiusMeters === preset.meters"
              @click="emit('update:radius-meters', preset.meters)"
            >{{ preset.label }}</button>
          </div>
          <span class="geo-group-caption">{{ props.locale === "es" ? "Análisis espacial" : "Spatial analysis" }}</span>
        </div>
      </template>
      <template v-else>
        <div class="geo-toolgroup"><button class="geo-big-tool" @click="emit('toggle-theme')"><span class="geo-tool-icon"><component :is="props.isDark ? Sunny : Moon" /></span><span>{{ props.isDark ? (props.locale === "es" ? "Modo claro" : "Light mode") : (props.locale === "es" ? "Modo oscuro" : "Dark mode") }}</span></button><span class="geo-group-caption">{{ props.locale === "es" ? "Apariencia" : "Appearance" }}</span></div>
        <div class="geo-toolgroup"><button class="geo-big-tool" @click="emit('toggle-locale')"><span class="geo-tool-icon teal-icon"><Setting /></span><span>{{ props.locale === "es" ? "English" : "Español" }}</span></button><span class="geo-group-caption">{{ props.locale === "es" ? "Idioma" : "Language" }}</span></div>
        <div class="geo-toolgroup"><span class="geo-scale-readout">{{ props.locale === "es" ? "FirstSpot · Centro de Operaciones" : "FirstSpot · Operations Center" }}</span><span class="geo-group-caption">{{ props.locale === "es" ? "Acerca del proyecto" : "About" }}</span></div>
      </template>
    </div>
    <slot name="workspace-status" />

    <Teleport to="body">
      <div v-if="commandOpen" class="command-backdrop" @click.self="closeCommandPalette()">
        <section class="command-palette" role="dialog" aria-modal="true" :aria-label="commandLabel">
          <div class="command-search-row">
            <Search aria-hidden="true" />
            <input
              ref="commandInput"
              v-model="commandQuery"
              type="search"
              autocomplete="off"
              :placeholder="props.locale === 'es' ? '¿Qué quieres hacer?' : 'What do you want to do?'"
              :aria-label="commandLabel"
              aria-controls="geo-command-list"
            />
            <button type="button" class="command-close" @click="closeCommandPalette()">Esc</button>
          </div>
          <p class="command-hint">{{ props.locale === "es" ? "Acciones rápidas" : "Quick actions" }}</p>
          <div id="geo-command-list" class="command-list" role="listbox" :aria-label="commandLabel">
            <button
              v-for="(command, index) in filteredCommands"
              :key="command.id"
              type="button"
              class="command-option"
              :class="{ active: index === activeCommandIndex }"
              role="option"
              :aria-selected="index === activeCommandIndex"
              :disabled="command.id === 'reset-filters' && !hasActiveFilters"
              @mouseenter="activeCommandIndex = index"
              @click="runCommand(command.id)"
            >
              <span class="command-option-icon"><component :is="command.icon" /></span>
              <span class="command-option-copy"><strong>{{ command.title }}</strong><small>{{ command.group }}</small></span>
              <span class="command-option-arrow">↵</span>
            </button>
            <div v-if="filteredCommands.length === 0" class="command-empty">
              {{ props.locale === "es" ? "No hay comandos que coincidan." : "No matching commands." }}
            </div>
          </div>
          <footer class="command-footer">
            <span><kbd>↑</kbd><kbd>↓</kbd> {{ props.locale === "es" ? "navegar" : "navigate" }}</span>
            <span><kbd>↵</kbd> {{ props.locale === "es" ? "ejecutar" : "run" }}</span>
            <span class="command-footer-spacer"></span>
            <span>FirstSpot</span>
          </footer>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
/* ==========================================================================
   GeoRibbon Architectural Theme:
   Refined neutral cool gray for GIS/CAD desktop ergonomics (reduces eye
   strain and establishes clear hierarchy with the map canvas), with dark
   slate graphite for dark mode and signal lime accents.
   ========================================================================== */

.geo-ribbon {
  --ribbon-bg: #eceff3;
  --ribbon-titlebar: #e5e9ef;
  --ribbon-tabrow: #dfe4eb;
  --ribbon-toolrow: #f4f6f9;
  --ribbon-telemetry: #e8ecf1;
  --ribbon-border: #cbd3de;
  --ribbon-border-subtle: #d8dfe8;
  --ribbon-surface-card: #ffffff;
  --ribbon-text-primary: #1e293b;
  --ribbon-text-secondary: #475569;
  --ribbon-text-muted: #64748b;
  --ribbon-hover: #d7e0ea;
  --ribbon-hover-tool: #e5eaf1;
  --ribbon-tab-active-bg: #f4f6f9;
  --ribbon-accent: #3d6d08;
  --ribbon-accent-glow: rgba(77, 133, 11, 0.12);
  --ribbon-focus: #5c9716;

  flex: none;
  background: var(--ribbon-bg);
  color: var(--ribbon-text-primary);
  border-bottom: 1px solid var(--ribbon-border);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
  font: 12px "Segoe UI", system-ui, sans-serif;
  z-index: 10;
}

.dark .geo-ribbon {
  --ribbon-bg: #1e2229;
  --ribbon-titlebar: #181b22;
  --ribbon-tabrow: #15181f;
  --ribbon-toolrow: #222731;
  --ribbon-telemetry: #181b22;
  --ribbon-border: #2d3440;
  --ribbon-border-subtle: #282f3a;
  --ribbon-surface-card: #191d24;
  --ribbon-text-primary: #f1f5f9;
  --ribbon-text-secondary: #cbd5e1;
  --ribbon-text-muted: #8897a8;
  --ribbon-hover: #262c37;
  --ribbon-hover-tool: #2b3341;
  --ribbon-tab-active-bg: #222731;
  --ribbon-accent: #88d623;
  --ribbon-accent-glow: rgba(136, 214, 35, 0.16);
  --ribbon-focus: #88d623;

  background: var(--ribbon-bg);
  color: var(--ribbon-text-primary);
  border-bottom-color: var(--ribbon-border);
}

/* --- Titlebar --- */
.geo-titlebar {
  height: 48px;
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 0 14px;
  background: var(--ribbon-titlebar);
  border-bottom: 1px solid var(--ribbon-border);
}

.geo-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  white-space: nowrap;
}

.geo-brand strong {
  font-size: 15px;
  font-weight: 760;
  letter-spacing: -0.025em;
  color: var(--ribbon-text-primary);
}

.dark .geo-brand strong {
  color: #f8fafc;
}

.geo-mark {
  display: block;
  flex: none;
  width: 40px;
  height: 40px;
  object-fit: contain;
}

.geo-product-tag {
  font-size: 9px;
  letter-spacing: 0.08em;
  font-weight: 800;
  background: #1e1e1e;
  color: #a9e94b;
  border: 1px solid #1e1e1e;
  padding: 3px 6px;
  border-radius: 3px;
}

.dark .geo-product-tag {
  background: #12151a;
  border-color: #2d3440;
}

.geo-quick-access {
  display: flex;
  gap: 3px;
  padding-left: 8px;
  border-left: 1px solid var(--ribbon-border);
}

.geo-quick,
.geo-icon-btn,
.geo-locale {
  display: grid;
  place-items: center;
  width: 28px;
  height: 27px;
  border-radius: 4px;
  color: var(--ribbon-text-secondary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.geo-quick:hover,
.geo-icon-btn:hover,
.geo-locale:hover {
  background: var(--ribbon-hover);
  color: var(--ribbon-text-primary);
}

.geo-quick :deep(svg),
.geo-icon-btn :deep(svg) {
  width: 15px;
}

.geo-project-title {
  flex: 1;
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--ribbon-text-primary);
  white-space: nowrap;
}

.geo-project-title span {
  font-weight: 500;
  color: var(--ribbon-text-muted);
}

.geo-search {
  height: 28px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  background: var(--ribbon-surface-card);
  border: 1px solid var(--ribbon-border);
  border-radius: 4px;
  color: var(--ribbon-text-secondary);
  font-size: 11px;
  white-space: nowrap;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.geo-search:hover {
  border-color: var(--ribbon-accent);
  color: var(--ribbon-text-primary);
}

.geo-search :deep(svg) {
  width: 13px;
}

.geo-search kbd {
  font: 10px ui-monospace, monospace;
  background: var(--ribbon-hover);
  border: 1px solid var(--ribbon-border);
  padding: 2px 4px;
  border-radius: 3px;
  color: var(--ribbon-text-secondary);
}

.geo-locale {
  font-size: 10px;
  font-weight: 800;
  width: 31px;
}

.geo-account {
  height: 28px;
  max-width: 190px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  border: 1px solid var(--ribbon-border);
  border-radius: 4px;
  background: var(--ribbon-surface-card);
  color: var(--ribbon-text-secondary);
  font: inherit;
  font-size: 10px;
  font-weight: 650;
  cursor: pointer;
  transition: all 0.15s;
}

.geo-account:hover {
  border-color: var(--ribbon-accent);
  color: var(--ribbon-text-primary);
  background: var(--ribbon-hover);
}

.dark .geo-account:hover {
  color: var(--ribbon-accent);
}

.geo-account :deep(svg) {
  width: 13px;
  flex: none;
}

.geo-account span {
  max-width: 136px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.geo-account i {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: #df9a29;
}

.geo-account i.verified {
  background: #1b9a69;
}

.ribbon-expand-toggle[aria-expanded="false"] {
  background: var(--ribbon-hover);
  color: var(--ribbon-text-primary);
}

/* --- Tab row --- */
.geo-tabrow {
  height: 32px;
  display: flex;
  align-items: stretch;
  padding: 0 9px;
  background: var(--ribbon-tabrow);
  border-bottom: 1px solid var(--ribbon-border);
}

.geo-tab-list {
  height: 100%;
  display: flex;
  align-items: stretch;
}

.geo-project-tab {
  display: flex;
  align-items: center;
  padding: 0 14px;
  font-size: 11px;
  font-weight: 700;
  background: #1e1e1e;
  color: #fff;
  border-bottom: 2px solid #88d623;
  gap: 6px;
  margin: 3px 8px 3px 0;
  border-radius: 3px;
  cursor: pointer;
}

.dark .geo-project-tab {
  background: #111419;
  border-bottom: 2px solid #88d623;
}

.geo-project-tab :deep(svg) {
  width: 14px;
  color: #a9e94b;
}

.project-caret {
  width: 10px !important;
  height: 10px;
}

.menu-shortcut {
  margin-left: 12px;
  padding: 1px 4px;
  border: 1px solid var(--ribbon-border);
  border-radius: 3px;
  color: var(--ribbon-text-muted);
  font: 10px ui-monospace, monospace;
}

.geo-tab {
  display: flex;
  align-items: center;
  padding: 0 14px;
  font-size: 11px;
  font-weight: 600;
  color: var(--ribbon-text-secondary);
  border-bottom: 3px solid transparent;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.geo-tab:hover {
  background: var(--ribbon-hover);
  color: var(--ribbon-text-primary);
}

.geo-tab.selected,
.geo-tab[aria-pressed="true"] {
  color: var(--ribbon-accent);
  border-bottom-color: var(--ribbon-accent);
  background: var(--ribbon-tab-active-bg);
  font-weight: 700;
}

.dark .geo-tab.selected,
.dark .geo-tab[aria-pressed="true"] {
  color: #a9e94b;
  border-bottom-color: #88d623;
}

.geo-tab-spacer {
  flex: 1;
}

.geo-project-state {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 11px;
  font-size: 10px;
  font-weight: 600;
  color: var(--ribbon-text-secondary);
}

.geo-project-state i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #16a34a;
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.2);
}

.geo-project-state.is-updating i {
  background: #d97706;
  box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.2);
}

.geo-project-state.has-error {
  color: #dc2626;
}

.geo-project-state.has-error i {
  background: #dc2626;
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.2);
}

/* --- Toolrow --- */
.geo-toolrow {
  height: 94px;
  display: flex;
  align-items: stretch;
  padding: 6px 10px 4px;
  background: var(--ribbon-toolrow);
  border-bottom: 1px solid var(--ribbon-border);
  overflow-x: auto;
  scrollbar-width: thin;
}

.geo-toolgroup {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 15px 13px;
  border-right: 1px solid var(--ribbon-border-subtle);
  min-width: max-content;
}

.geo-toolgroup:first-child {
  padding-left: 4px;
}

.geo-toolgroup:last-child {
  border-right: 0;
}

.geo-group-caption {
  position: absolute;
  bottom: 0;
  left: 15px;
  right: 15px;
  text-align: center;
  color: var(--ribbon-text-muted);
  font-size: 9px;
  font-weight: 700;
  line-height: 12px;
}

.geo-toolgroup:first-child .geo-group-caption {
  left: 4px;
}

.geo-tool-stack label,
.geo-filter-label {
  font-size: 9px;
  letter-spacing: 0.07em;
  color: var(--ribbon-text-muted);
  font-weight: 800;
}

.geo-big-tool {
  height: 65px;
  min-width: 62px;
  padding: 4px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border-radius: 4px;
  color: var(--ribbon-text-primary);
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.geo-big-tool:hover {
  background: var(--ribbon-hover-tool);
  color: var(--ribbon-text-primary);
}

.geo-big-tool:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.geo-big-tool.primary-tool,
.geo-tool-icon,
.geo-tool-icon.teal-icon {
  color: var(--ribbon-accent);
}

.geo-big-tool.primary-tool:hover {
  background: var(--ribbon-hover-tool);
}

.geo-tool-icon {
  display: grid;
  place-items: center;
}

.geo-tool-icon :deep(svg) {
  width: 23px;
  height: 23px;
  stroke-width: 1.8;
}

.geo-tool-icon.orange-icon {
  color: #e17816;
}

.geo-tool-stack {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 205px;
}

.geo-zone-select {
  width: 210px;
}

.geo-zone-group .geo-tool-stack {
  min-width: 260px;
}

.geo-zone-group .geo-zone-select {
  width: 250px;
}

.geo-radius-control {
  height: 22px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--ribbon-text-secondary);
  font-size: 10px;
  font-weight: 500;
}

.geo-radius-input {
  width: 59px;
  height: 21px;
  padding: 0 4px;
  border: 1px solid var(--ribbon-border);
  border-radius: 3px;
  font: 10px ui-monospace, monospace;
}

.compact-stack {
  min-width: 132px;
}

.geo-small-tool {
  height: 28px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  border: 1px solid var(--ribbon-border);
  border-radius: 4px;
  background: var(--ribbon-surface-card);
  color: var(--ribbon-text-primary);
  font-size: 10px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s;
}

.geo-small-tool:hover {
  border-color: var(--ribbon-accent);
  background: var(--ribbon-hover);
  color: var(--ribbon-text-primary);
}

.geo-small-tool :deep(svg) {
  width: 14px;
}

.geo-scale-readout {
  color: var(--ribbon-text-secondary);
  font-size: 10px;
  font-weight: 500;
}

.geo-home-radius {
  gap: 6px;
  white-space: nowrap;
}

.geo-home-radius > span {
  font-size: 10px;
  color: var(--ribbon-text-secondary);
}

.geo-radius-summary {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-left: auto;
  padding: 3px 6px;
  border: 1px solid var(--ribbon-border);
  border-radius: 4px;
  background: var(--ribbon-surface-card);
  color: var(--ribbon-text-secondary);
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.geo-radius-summary strong {
  font-variant-numeric: tabular-nums;
}

.geo-radius-summary span {
  color: var(--ribbon-accent);
  font-weight: 650;
}

.geo-radius-summary:hover {
  border-color: var(--ribbon-accent);
  background: var(--ribbon-hover);
}

/* --- Radius Editor (Tab 3) --- */
.geo-radius-editor {
  width: 390px;
  min-width: 390px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  gap: 2px;
  padding-left: 13px;
  padding-right: 13px;
}

.geo-radius-editor-heading {
  height: 21px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.geo-radius-editor-heading > .geo-tool-icon :deep(svg) {
  width: 20px;
  height: 20px;
}

.geo-radius-heading-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 9px;
}

.geo-radius-heading-copy strong {
  flex: none;
  color: var(--ribbon-text-primary);
  font-size: 11px;
}

.geo-radius-heading-copy small {
  overflow: hidden;
  color: var(--ribbon-text-muted);
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.geo-radius-value-row {
  height: 23px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.geo-radius-value-row :deep(.el-slider) {
  flex: 1;
  margin: 0 5px 0 1px;
}

.geo-radius-value-row :deep(.el-slider__runway) {
  height: 4px;
  margin: 9px 0;
  background: var(--ribbon-border);
}

.geo-radius-value-row :deep(.el-slider__bar) {
  height: 4px;
  background: var(--ribbon-accent);
}

.geo-radius-value-row :deep(.el-slider__button) {
  width: 13px;
  height: 13px;
  border: 2px solid var(--ribbon-accent);
}

.geo-radius-number {
  display: flex;
  align-items: center;
  gap: 5px;
}

.geo-radius-number :deep(.el-input-number) {
  width: 83px;
}

.geo-radius-number :deep(.el-input__wrapper) {
  min-height: 24px;
  padding-left: 7px;
  padding-right: 24px;
  background: var(--ribbon-surface-card);
  box-shadow: 0 0 0 1px var(--ribbon-border) inset;
}

.geo-radius-number :deep(.el-input__inner) {
  text-align: center;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: var(--ribbon-text-primary);
}

.geo-radius-number > span {
  color: var(--ribbon-text-secondary);
  font-size: 10px;
  font-weight: 700;
}

.geo-radius-presets {
  height: 18px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.geo-radius-preset {
  min-width: 39px;
  height: 17px;
  padding: 0 6px;
  border: 1px solid var(--ribbon-border);
  border-radius: 3px;
  background: var(--ribbon-surface-card);
  color: var(--ribbon-text-secondary);
  font-size: 9px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.15s;
}

.geo-radius-preset:hover {
  border-color: var(--ribbon-accent);
  background: var(--ribbon-hover);
}

.geo-radius-preset.is-selected {
  border-color: var(--ribbon-accent);
  background: var(--ribbon-accent-glow);
  color: var(--ribbon-accent);
  font-weight: 750;
}

.dark .geo-radius-preset.is-selected {
  background: #1b3523;
  border-color: #88d623;
  color: #a9e94b;
}

/* --- Filter & Layer Controls --- */
.geo-layer-tools {
  gap: 5px;
}

.geo-layer-tools .layer-tool {
  min-width: 76px;
  padding: 4px 7px;
  border: 1px solid transparent;
}

.geo-layer-tools .layer-tool.is-active {
  border-color: var(--ribbon-accent);
  background: var(--ribbon-hover);
  color: var(--ribbon-accent);
}

.geo-layer-tools .layer-tool.is-active .geo-tool-icon {
  color: var(--ribbon-accent);
}

.geo-filter-search,
.geo-filter-selects,
.geo-filter-status,
.geo-filter-heatmap {
  align-items: stretch;
  justify-content: center;
}

.geo-filter-search {
  width: 230px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  gap: 5px;
}

.geo-filter-search .geo-filter-label {
  height: 11px;
  line-height: 11px;
}

.geo-filter-search :deep(.el-input) {
  height: 29px;
}

.geo-filter-search :deep(.el-input__wrapper) {
  height: 29px;
  min-height: 29px;
  padding: 0 8px;
  background: var(--ribbon-surface-card);
  box-shadow: 0 0 0 1px var(--ribbon-border) inset;
}

.geo-filter-search :deep(.el-input__inner) {
  height: 27px;
  font-size: 11px;
  color: var(--ribbon-text-primary);
}

.geo-filter-search :deep(.el-input__prefix-inner svg) {
  width: 14px;
  height: 14px;
}

.geo-filter-selects {
  width: 195px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.geo-filter-selects .el-select {
  width: 100%;
}

.geo-filter-selects :deep(.el-select__wrapper) {
  min-height: 25px;
  padding: 0 7px;
  border-radius: 3px;
  background: var(--ribbon-surface-card);
  box-shadow: 0 0 0 1px var(--ribbon-border) inset;
}

.geo-filter-selects :deep(.el-select__placeholder) {
  font-size: 10px;
  color: var(--ribbon-text-primary);
}

.geo-zone-select :deep(.el-input__wrapper) {
  background: var(--ribbon-surface-card);
  box-shadow: 0 0 0 1px var(--ribbon-border) inset;
}

.geo-zone-select :deep(.el-input__inner) {
  color: var(--ribbon-text-primary);
}

.geo-filter-status {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 5px;
  min-width: max-content;
}

.geo-filter-status :deep(.el-radio-group) {
  display: flex;
  flex-wrap: nowrap;
}

.geo-filter-status :deep(.el-radio-button__inner) {
  height: 24px;
  padding: 4px 7px;
  font-size: 9px;
  white-space: nowrap;
}

.geo-filter-heatmap {
  min-width: 150px;
}

.geo-filter-heatmap .geo-radius-control {
  height: 25px;
}

.geo-filter-heatmap .geo-radius-control span {
  max-width: 128px;
  line-height: 1.2;
}

.geo-filter-actions {
  gap: 2px;
}

.geo-filter-actions .geo-big-tool {
  min-width: 72px;
  padding-left: 5px;
  padding-right: 5px;
}

.geo-filter-actions .geo-tool-icon :deep(svg) {
  width: 20px;
  height: 20px;
}

.geo-filter-actions .geo-big-tool > span:last-child {
  font-size: 9px;
}

/* --- Hazard Telemetry Strip --- */
.geo-ribbon :deep(.hazard-telemetry-strip) {
  min-height: 34px;
  padding: 3px 12px;
  background: var(--ribbon-telemetry);
  border-top: 1px solid var(--ribbon-border);
  border-bottom: 1px solid var(--ribbon-border);
  box-shadow: none;
  gap: 8px;
  flex-wrap: nowrap;
  font-size: 10px;
}

.geo-ribbon :deep(.telemetry-badge-box) {
  color: var(--ribbon-text-muted);
  font-size: 9px;
  letter-spacing: 0.045em;
  padding-right: 8px;
  border-right: 1px solid var(--ribbon-border);
}

.geo-ribbon :deep(.weather-pill),
.geo-ribbon :deep(.events-pill) {
  min-height: 25px;
  padding: 2px 8px;
  background: var(--ribbon-surface-card);
  border: 1px solid var(--ribbon-border);
  border-radius: 3px;
  white-space: nowrap;
  color: var(--ribbon-text-primary);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.geo-ribbon :deep(.telemetry-label) {
  color: var(--ribbon-text-muted);
}

.geo-ribbon :deep(.top-event-title) {
  color: var(--ribbon-text-primary);
}

.geo-ribbon :deep(.calm-text),
.geo-ribbon :deep(.feed-freshness) {
  color: var(--ribbon-text-muted);
}

.geo-ribbon :deep(.telemetry-controls) {
  flex-wrap: nowrap;
  gap: 7px;
}

.geo-ribbon :deep(.live-monitoring-badge),
.geo-ribbon :deep(.active-drill-badge) {
  border-radius: 3px;
  padding: 3px 7px;
  font-size: 10px;
}

.geo-ribbon :deep(.drill-toggle-btn) {
  border-radius: 3px;
  background: var(--ribbon-surface-card);
  border: 1px solid var(--ribbon-border);
  color: var(--ribbon-text-secondary);
}

.geo-ribbon :deep(.drill-toggle-btn:hover) {
  border-color: var(--ribbon-accent);
  color: var(--ribbon-text-primary);
  background: var(--ribbon-hover);
}

.geo-ribbon :deep(.nominatim-input-row) {
  border-radius: 3px;
  background: var(--ribbon-surface-card);
  border: 1px solid var(--ribbon-border);
}

.geo-ribbon :deep(.nominatim-input) {
  color: var(--ribbon-text-primary);
}

.geo-ribbon :deep(.nominatim-input::placeholder) {
  color: var(--ribbon-text-muted);
}

.geo-ribbon :deep(.nominatim-dropdown) {
  border-radius: 3px;
  background: var(--ribbon-surface-card);
  border: 1px solid var(--ribbon-border);
}

.geo-ribbon :deep(.nominatim-option) {
  color: var(--ribbon-text-primary);
}

.geo-ribbon :deep(.nominatim-option:hover) {
  background: var(--ribbon-hover);
}

.geo-ribbon :deep([data-testid="nominatim-search-btn"]) {
  background: #1e293b;
  border-color: #1e293b;
  color: #fff;
}

.geo-ribbon :deep([data-testid="nominatim-search-btn"]:hover) {
  background: #334155;
  border-color: #334155;
}

.dark .geo-ribbon :deep([data-testid="nominatim-search-btn"]) {
  background: #2a3240;
  border-color: #394354;
  color: #fff;
}

.dark .geo-ribbon :deep([data-testid="nominatim-search-btn"]:hover) {
  background: #384357;
  border-color: #48566d;
}

/* --- Focus rings --- */
.geo-ribbon button:focus-visible,
.command-backdrop button:focus-visible,
.command-search-row input:focus-visible,
.geo-toolrow[role="tabpanel"]:focus-visible,
.geo-radius-summary:focus-visible,
.geo-radius-preset:focus-visible,
.geo-account:focus-visible,
.geo-tab:focus-visible,
.geo-project-tab:focus-visible,
.geo-icon-btn:focus-visible,
.geo-locale:focus-visible,
.geo-quick:focus-visible {
  outline: 2px solid var(--ribbon-focus);
  outline-offset: 2px;
}

/* --- Command Palette Modal --- */
.command-backdrop {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(15, 23, 42, 0.52);
  padding: 12vh 16px 24px;
  overflow: auto;
}

.command-option:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.command-palette {
  width: min(560px, 100%);
  margin: 0 auto;
  background: var(--ribbon-surface-card);
  color: var(--ribbon-text-primary);
  border: 1px solid var(--ribbon-border);
  border-radius: 8px;
  box-shadow: 0 18px 54px rgba(15, 23, 42, 0.25);
  overflow: hidden;
}

.command-search-row {
  height: 58px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 17px;
  border-bottom: 1px solid var(--ribbon-border);
  color: var(--ribbon-accent);
}

.command-search-row > svg {
  width: 19px;
  height: 19px;
  flex: none;
}

.command-search-row input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ribbon-text-primary);
  font: 500 15px "Segoe UI", system-ui, sans-serif;
}

.command-search-row input::placeholder {
  color: var(--ribbon-text-muted);
}

.command-close {
  padding: 3px 7px;
  border: 1px solid var(--ribbon-border);
  border-radius: 4px;
  background: var(--ribbon-hover);
  color: var(--ribbon-text-secondary);
  font: 11px ui-monospace, monospace;
  cursor: pointer;
}

.command-hint {
  margin: 0;
  padding: 12px 16px 6px;
  color: var(--ribbon-text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.command-list {
  max-height: min(440px, 55vh);
  overflow: auto;
  padding: 4px 7px 8px;
}

.command-option {
  width: 100%;
  min-height: 46px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 6px 9px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--ribbon-text-secondary);
  text-align: left;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.command-option:hover,
.command-option.active {
  background: var(--ribbon-hover);
  color: var(--ribbon-accent);
}

.command-option-icon {
  width: 29px;
  height: 29px;
  display: grid;
  place-items: center;
  flex: none;
  border: 1px solid var(--ribbon-border);
  border-radius: 4px;
  background: var(--ribbon-surface-card);
  color: var(--ribbon-accent);
}

.command-option-icon :deep(svg) {
  width: 16px;
  height: 16px;
}

.command-option-copy {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.command-option-copy strong {
  font-size: 12px;
  font-weight: 650;
  color: var(--ribbon-text-primary);
}

.command-option-copy small {
  color: var(--ribbon-text-muted);
  font-size: 10px;
}

.command-option-arrow {
  color: var(--ribbon-text-muted);
  font: 12px ui-monospace, monospace;
}

.command-empty {
  padding: 22px 12px;
  color: var(--ribbon-text-muted);
  text-align: center;
  font-size: 12px;
}

.command-footer {
  min-height: 34px;
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 0 13px;
  border-top: 1px solid var(--ribbon-border);
  background: var(--ribbon-telemetry);
  color: var(--ribbon-text-muted);
  font-size: 10px;
}

.command-footer span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.command-footer kbd {
  min-width: 18px;
  padding: 1px 4px;
  border: 1px solid var(--ribbon-border);
  border-radius: 3px;
  background: var(--ribbon-surface-card);
  color: var(--ribbon-text-secondary);
  text-align: center;
  font: 10px ui-monospace, monospace;
}

.command-footer-spacer {
  flex: 1;
}

/* --- Responsive Media Queries --- */
@media (max-width: 800px) {
  .geo-titlebar {
    height: 44px;
    gap: 6px;
  }
  .geo-mark {
    width: 36px;
    height: 36px;
  }
  .geo-brand strong {
    font-size: 14px;
  }
  .geo-project-title,
  .geo-search span,
  .geo-search kbd,
  .geo-product-tag {
    display: none;
  }
  .geo-toolrow {
    height: 88px;
  }
  .geo-toolgroup {
    padding-left: 7px;
    padding-right: 7px;
  }
  .geo-tool-stack {
    min-width: 170px;
  }
  .geo-zone-select {
    width: 175px;
  }
  .geo-filter-search {
    width: 185px;
  }
  .geo-filter-selects {
    width: 180px;
  }
  .geo-radius-editor {
    width: 370px;
    min-width: 370px;
  }
  .geo-radius-heading-copy small {
    max-width: 190px;
  }
  .geo-account {
    max-width: 34px;
    padding: 0 8px;
  }
  .geo-account span {
    display: none;
  }
}

@media (max-width: 1100px) {
  .geo-ribbon :deep(.hazard-telemetry-strip) {
    overflow-x: auto;
    scrollbar-width: thin;
  }
  .geo-ribbon :deep(.telemetry-controls) {
    margin-left: auto;
  }
}
</style>
