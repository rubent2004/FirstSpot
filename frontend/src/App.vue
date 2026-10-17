<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { ElAlert, ElConfigProvider, ElDialog } from "element-plus";
import FeedsStatusChip from "./modules/sync-controls/FeedsStatusChip.vue";
import HazardTelemetryStrip from "./modules/sync-controls/HazardTelemetryStrip.vue";
import { feedStatusKey, needsAttention } from "./modules/sync-controls/feedStatus";
import VulnerabilityHeatmapCanvas from "./modules/map-viewer/VulnerabilityHeatmapCanvas.vue";
import PriorityQueuePanel from "./modules/priority-queue/PriorityQueuePanel.vue";
import CommunityTriagePanel, {
  type TriageLevel,
} from "./modules/community-triage/CommunityTriagePanel.vue";
import PlaceTriageDrawer from "./modules/priority-queue/PlaceTriageDrawer.vue";
import GeoRibbon from "./components/GeoRibbon.vue";
import InstitutionAccessDialog from "./modules/institutions/InstitutionAccessDialog.vue";
import { usePrioritizationStore } from "./stores/usePrioritizationStore";
import { useI18n } from "./i18n/useI18n";
import { useTheme } from "./composables/useTheme";
import type { MapSnapshot } from "./modules/community-triage/mapPrint/mapSnapshot";
import type {
  HazardScenarioPreset,
  PlaceRead,
  PlaceTriageUpdate,
  VulnerabilityGroup,
} from "./api/client";

const store = usePrioritizationStore();
const { elementLocale, locale, t, toggleLocale } = useI18n();
const { isDark, toggleTheme } = useTheme();
const HAZARD_REFRESH_INTERVAL_MS = 2 * 60 * 1000;
const showHeatmapLayer = ref(true);
const showMarkersLayer = ref(true);
const showHazardsLayer = ref(true);
const showInstitutionAccess = ref(false);
/**
 * The feeds earn permanent screen space only when something is wrong (stale,
 * failing, partial) or a drill is running. Normally they are one status-bar chip.
 */
const feedsNeedAttention = computed(() =>
  needsAttention(
    feedStatusKey({
      activeHazards: store.activeHazards,
      scenario: store.hazardScenario,
      isRefreshing: store.isRefreshingHazards,
      refreshError: store.hazardRefreshError,
    }),
  ),
);

/** District ranking is the overview; the district detail opens beside it on demand. */
const triageLevel = ref<TriageLevel>("list");
const detailOpen = ref(false);
const feedsDialogOpen = ref(false);
/** A custom radius is not a predefined zone, so it never scopes the district list. */
const zoneName = computed(() =>
  store.customRadiusMode.enabled ? null : (store.currentZone?.name ?? null),
);
const zoneDepartment = computed(() =>
  store.customRadiusMode.enabled ? null : (store.currentZone?.department ?? null),
);
const tacticalBasemap = ref(isDark.value);
const geocodeTarget = ref<{ lat: number; lon: number; label: string } | null>(
  null,
);
let hazardRefreshTimer: ReturnType<typeof setInterval> | null = null;

watch(
  locale,
  (value) => {
    document.documentElement.lang = value;
  },
  { immediate: true },
);

watch(isDark, (value) => {
  tacticalBasemap.value = value;
});

watch(
  () => [store.selectedPlace?.id, store.isTriageDrawerOpen] as const,
  ([placeId, isOpen]) => {
    if (placeId && isOpen) void store.fetchPlaceActivities(placeId);
  },
);

onMounted(async () => {
  await store.initializeDashboard();
  hazardRefreshTimer = setInterval(() => {
    if (
      document.visibilityState === "hidden" ||
      store.hazardScenario !== "none" ||
      store.isRefreshingHazards
    ) {
      return;
    }
    void store.fetchHazards();
  }, HAZARD_REFRESH_INTERVAL_MS);
});

onUnmounted(() => {
  if (hazardRefreshTimer !== null) {
    clearInterval(hazardRefreshTimer);
  }
});

async function handleZoneChange(zoneKey: string): Promise<void> {
  await store.selectZone(zoneKey);
}

async function handleZoneSync(zoneKey: string): Promise<void> {
  await store.syncZone(zoneKey);
}

async function handleMapRadiusSync(
  latitude: number,
  longitude: number,
): Promise<void> {
  await store.syncCustomRadius(
    latitude,
    longitude,
    store.customRadiusMode.radiusMeters,
  );
}

function handleSelectPlace(place: PlaceRead, openDrawer: boolean): void {
  store.selectPlace(place, openDrawer);
}

async function handleSaveTriage(
  placeId: string,
  payload: PlaceTriageUpdate,
): Promise<void> {
  const updated = await store.savePlaceTriage(placeId, payload);
  if (updated) {
    store.isTriageDrawerOpen = false;
  }
}

async function handleResetFilters(): Promise<void> {
  store.resetFilters();
  await store.fetchPlacesAndHeatmap();
}

async function handleToggleGroupFilter(
  group: VulnerabilityGroup,
): Promise<void> {
  store.filters.vulnerabilityGroup =
    store.filters.vulnerabilityGroup === group ? "" : group;
  await store.fetchPlacesAndHeatmap();
}

async function handleScenarioChange(
  scenario: HazardScenarioPreset,
): Promise<void> {
  await store.fetchHazards(scenario);
}

function handleFlyToCoordinates(
  lat: number,
  lon: number,
  label: string,
): void {
  geocodeTarget.value = { lat, lon, label };
}

const heatmapCanvas = ref<InstanceType<typeof VulnerabilityHeatmapCanvas> | null>(null);

/** The live map as the operator sees it, for the printed map of the current view. */
function captureMapSnapshot(): MapSnapshot | null {
  const view = heatmapCanvas.value?.getViewState();
  if (!view) return null;
  return {
    view,
    layers: {
      heat: showHeatmapLayer.value,
      markers: showMarkersLayer.value,
      hazards: showHazardsLayer.value,
    },
    zone: { name: zoneName.value, department: zoneDepartment.value },
    places: store.places,
    heatPoints: store.heatmapPoints,
    hazards: store.activeHazards?.events ?? [],
    weather: store.activeHazards?.weather ?? null,
    selectedPlace: store.selectedPlace,
    activities: store.selectedPlace ? store.placeActivities : [],
  };
}

function handleCenterMap(): void {
  window.dispatchEvent(new CustomEvent("geo-priority:center-zone"));
}

function handleFitMap(): void {
  window.dispatchEvent(new CustomEvent("geo-priority:fit-data"));
}
</script>

<template>
  <ElConfigProvider :locale="elementLocale">
    <div class="dashboard-shell">
      <GeoRibbon
        :zones="store.zones"
        :selected-zone-key="store.selectedZoneKey"
        :active-zone-name="store.activeZoneName"
        :is-syncing="store.isSyncing"
        :is-loading="store.isLoading"
        :has-error="Boolean(store.error)"
        :radius-enabled="store.customRadiusMode.enabled"
        :radius-meters="store.customRadiusMode.radiusMeters"
        :is-dark="isDark"
        :locale="locale"
        :show-heatmap-layer="showHeatmapLayer"
        :show-markers-layer="showMarkersLayer"
        :show-hazards-layer="showHazardsLayer"
        :tactical-basemap="tacticalBasemap"
        :filters="store.filters"
        :institution-account="store.institutionSession?.account ?? null"
        @change-zone="handleZoneChange"
        @sync-zone="handleZoneSync(store.selectedZoneKey || 'sonsonate')"
        @update:radius-enabled="
          (val) => (store.customRadiusMode.enabled = val)
        "
        @update:radius-meters="
          (val) => (store.customRadiusMode.radiusMeters = val)
        "
        @reset-filters="handleResetFilters"
        @filter-change="store.fetchPlacesAndHeatmap"
        @refresh-hazards="handleScenarioChange(store.hazardScenario)"
        @center-map="handleCenterMap"
        @fit-map="handleFitMap"
        @toggle-theme="toggleTheme"
        @toggle-locale="toggleLocale"
        @update:show-heatmap-layer="showHeatmapLayer = $event"
        @update:show-markers-layer="showMarkersLayer = $event"
        @update:show-hazards-layer="showHazardsLayer = $event"
        @update:tactical-basemap="tacticalBasemap = $event"
        @open-institution-access="showInstitutionAccess = true"
      >
        <template v-if="feedsNeedAttention" #workspace-status>
          <HazardTelemetryStrip
            :active-hazards="store.activeHazards"
            :scenario="store.hazardScenario"
            :last-checked-at="store.hazardLastCheckedAt"
            :is-refreshing="store.isRefreshingHazards"
            :refresh-error="store.hazardRefreshError"
            @change-scenario="handleScenarioChange"
            @fly-to-coordinates="handleFlyToCoordinates"
          />
        </template>
      </GeoRibbon>

      <ElAlert
        v-if="store.error"
        :title="store.error"
        type="error"
        show-icon
        closable
        class="error-banner"
        @close="store.error = null"
      />

      <main class="dashboard-workspace" :class="{ 'has-detail': detailOpen }">
        <div class="workspace-map-col">
          <p v-if="triageLevel === 'list'" class="map-caption">{{ t.community.map.caption }}</p>
          <VulnerabilityHeatmapCanvas
            ref="heatmapCanvas"
            :places="store.places"
            :heatmap-points="store.heatmapPoints"
            :selected-place="store.selectedPlace"
            :current-zone="store.currentZone"
            :custom-radius-enabled="store.customRadiusMode.enabled"
            :custom-radius-meters="store.customRadiusMode.radiusMeters"
            :active-group-filter="store.filters.vulnerabilityGroup"
            :hazard-events="store.activeHazards?.events ?? []"
            :geocode-target="geocodeTarget"
            :show-heatmap-layer="showHeatmapLayer"
            :show-markers-layer="showMarkersLayer"
            :show-hazards-layer="showHazardsLayer"
            :tactical-basemap="tacticalBasemap"
            @select-place="handleSelectPlace"
            @map-radius-sync="handleMapRadiusSync"
            @toggle-group-filter="handleToggleGroupFilter"
          />
        </div>

        <CommunityTriagePanel
          :zone-name="zoneName"
          :zone-department="zoneDepartment"
          :get-map-snapshot="captureMapSnapshot"
          @level-change="triageLevel = $event"
          @detail-change="detailOpen = $event"
          @open-feeds="feedsDialogOpen = true"
        >
          <template #places>
            <PriorityQueuePanel
              :places="store.places"
              :selected-place="store.selectedPlace"
              :is-loading="store.isLoading"
              @select-place="handleSelectPlace"
            />
          </template>
        </CommunityTriagePanel>
      </main>

      <footer class="geo-statusbar">
        <FeedsStatusChip
          :active-hazards="store.activeHazards"
          :scenario="store.hazardScenario"
          :last-checked-at="store.hazardLastCheckedAt"
          :is-refreshing="store.isRefreshingHazards"
          :refresh-error="store.hazardRefreshError"
          @change-scenario="handleScenarioChange"
          @fly-to-coordinates="handleFlyToCoordinates"
        />
        <span class="status-separator"></span>
        <span>{{ store.activeZoneName || (locale === "es" ? "Área personalizada" : "Custom area") }}</span>
        <span class="status-stat eoc-numeric">{{ store.kpis.total_places }} {{ locale === "es" ? "lugares" : "places" }}</span>
        <span class="status-stat status-critical eoc-numeric">{{ store.kpis.critical_urgency_count }} {{ locale === "es" ? "críticos" : "critical" }}</span>
        <span class="status-spacer"></span>
        <span class="status-coordinates eoc-numeric">{{ locale === "es" ? "Coordenadas" : "Coordinates" }} · {{ store.currentZone?.latitude.toFixed(4) ?? "—" }}, {{ store.currentZone?.longitude.toFixed(4) ?? "—" }}</span>
        <span class="status-separator"></span>
        <span>FirstSpot</span>
      </footer>

      <PlaceTriageDrawer
        v-model:visible="store.isTriageDrawerOpen"
        :place="store.selectedPlace"
        :account="store.institutionSession?.account ?? null"
        :activities="store.placeActivities"
        :activities-loading="store.arePlaceActivitiesLoading"
        :activities-error="store.placeActivityError"
        @save-triage="handleSaveTriage"
        @request-access="showInstitutionAccess = true"
      />
      <InstitutionAccessDialog v-model:visible="showInstitutionAccess" />
      <ElDialog
        v-if="feedsDialogOpen"
        v-model="feedsDialogOpen"
        :title="t.community.nav.feeds"
        width="min(460px, 94vw)"
        align-center
        append-to-body
      >
        <HazardTelemetryStrip
          stacked
          :active-hazards="store.activeHazards"
          :scenario="store.hazardScenario"
          :last-checked-at="store.hazardLastCheckedAt"
          :is-refreshing="store.isRefreshingHazards"
          :refresh-error="store.hazardRefreshError"
          @change-scenario="handleScenarioChange"
          @fly-to-coordinates="handleFlyToCoordinates"
        />
      </ElDialog>
    </div>
  </ElConfigProvider>
</template>

<style scoped>
.dashboard-shell {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  width: 100%;
  overflow: hidden;
  background: var(--eoc-bg-canvas);
  color: var(--eoc-text-primary);
}

.error-banner {
  border-radius: 0;
}

.dashboard-workspace {
  flex: 1;
  display: grid;
  grid-template-areas: "queue map";
  grid-template-columns: minmax(420px, min(42%, 600px)) minmax(0, 1fr);
  min-height: 0;
  overflow: hidden;
  border-top: var(--eoc-border-width) solid var(--eoc-border);
}

/* The district detail is a third column only while it is open (wide screens) */
.dashboard-workspace.has-detail {
  grid-template-areas: "queue map detail";
  grid-template-columns: minmax(420px, min(34%, 520px)) minmax(0, 1fr) 360px;
}

.workspace-map-col {
  grid-area: map;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.workspace-map-col > :deep(.map-panel-wrapper) { flex: 1 1 0; min-height: 0; height: auto; }

.map-caption {
  flex: none;
  margin: 0;
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
  background: var(--eoc-bg-header);
  border-bottom: var(--eoc-border-width) solid var(--eoc-border);
  color: var(--eoc-text-secondary);
  font-size: var(--eoc-fs-micro);
}

.geo-statusbar {
  height: var(--eoc-statusbar-h);
  flex: none;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 var(--eoc-pad-panel);
  background: var(--eoc-bg-statusbar);
  border-top: var(--eoc-border-width) solid var(--eoc-border);
  color: var(--eoc-text-secondary);
  font-size: var(--eoc-fs-micro);
  white-space: nowrap;
}
.status-connection { display: inline-flex; align-items: center; gap: var(--eoc-gap-x); }
.status-connection i { width: 6px; height: 6px; border-radius: var(--eoc-radius-pill); background: var(--eoc-success); }
.status-separator { height: 12px; width: var(--eoc-border-width); background: var(--eoc-border); }
.status-stat { color: var(--eoc-text-primary); font-weight: var(--eoc-fw-semibold); }
.status-critical { color: var(--eoc-critical); }
.status-coordinates { font-family: var(--eoc-font-mono); }
.status-spacer { flex: 1; }

@media (max-width: 1100px) {
  /* Below this width the detail floats over the map instead of taking a column */
  .dashboard-workspace.has-detail {
    grid-template-areas: "queue map";
    grid-template-columns: minmax(420px, min(48%, 520px)) minmax(280px, 1fr);
  }
}

@media (max-width: 700px) {
  /* The list is a bottom sheet over the map, so the map takes the whole workspace */
  .dashboard-workspace,
  .dashboard-workspace.has-detail { grid-template-areas: "map"; grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); overflow: hidden; }
  /* Keep only the feeds chip: the popover must not be clipped by a scrolling footer */
  .geo-statusbar { overflow: visible; }
  .geo-statusbar .status-separator,
  .geo-statusbar .status-stat,
  .geo-statusbar .status-coordinates,
  .geo-statusbar > span:not(.status-spacer):not(.info) { display: none; }
}
</style>
