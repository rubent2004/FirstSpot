<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { ElAlert, ElConfigProvider } from "element-plus";
import SyncHeaderBar from "./modules/sync-controls/SyncHeaderBar.vue";
import HazardTelemetryStrip from "./modules/sync-controls/HazardTelemetryStrip.vue";
import VulnerabilityHeatmapCanvas from "./modules/map-viewer/VulnerabilityHeatmapCanvas.vue";
import PriorityQueuePanel from "./modules/priority-queue/PriorityQueuePanel.vue";
import PlaceTriageDrawer from "./modules/priority-queue/PlaceTriageDrawer.vue";
import { usePrioritizationStore } from "./stores/usePrioritizationStore";
import { useI18n } from "./i18n/useI18n";
import type {
  AttentionStatus,
  HazardScenarioPreset,
  PlaceRead,
  PlaceTriageUpdate,
  VulnerabilityGroup,
} from "./api/client";

const store = usePrioritizationStore();
const { elementLocale } = useI18n();
const HAZARD_REFRESH_INTERVAL_MS = 2 * 60 * 1000;
const geocodeTarget = ref<{ lat: number; lon: number; label: string } | null>(
  null,
);
let hazardRefreshTimer: ReturnType<typeof setInterval> | null = null;

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

async function handleQuickKpiFilter(payload: {
  status: AttentionStatus | "";
  minUrgency: number | null;
}): Promise<void> {
  store.filters.attentionStatus = payload.status;
  store.filters.minUrgency = payload.minUrgency;
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
</script>

<template>
  <ElConfigProvider :locale="elementLocale">
    <div class="dashboard-shell">
      <SyncHeaderBar
        :zones="store.zones"
        :selected-zone-key="store.selectedZoneKey"
        :active-zone-name="store.activeZoneName"
        :kpis="store.kpis"
        :is-syncing="store.isSyncing"
        :custom-radius-enabled="store.customRadiusMode.enabled"
        :custom-radius-meters="store.customRadiusMode.radiusMeters"
        :last-sync-summary="store.lastSyncSummary"
        :active-status-filter="store.filters.attentionStatus"
        :active-min-urgency="store.filters.minUrgency"
        @update:selected-zone-key="(val) => (store.selectedZoneKey = val)"
        @change-zone="handleZoneChange"
        @sync-zone="handleZoneSync"
        @update:custom-radius-enabled="
          (val) => (store.customRadiusMode.enabled = val)
        "
        @update:custom-radius-meters="
          (val) => (store.customRadiusMode.radiusMeters = val)
        "
        @quick-kpi-filter="handleQuickKpiFilter"
      />

      <HazardTelemetryStrip
        :active-hazards="store.activeHazards"
        :scenario="store.hazardScenario"
        :last-checked-at="store.hazardLastCheckedAt"
        :is-refreshing="store.isRefreshingHazards"
        :refresh-error="store.hazardRefreshError"
        @change-scenario="handleScenarioChange"
        @fly-to-coordinates="handleFlyToCoordinates"
      />

      <ElAlert
        v-if="store.error"
        :title="store.error"
        type="error"
        show-icon
        closable
        class="error-banner"
        @close="store.error = null"
      />

      <main class="dashboard-workspace">
        <div class="workspace-map-col">
          <VulnerabilityHeatmapCanvas
            :places="store.places"
            :heatmap-points="store.heatmapPoints"
            :selected-place="store.selectedPlace"
            :current-zone="store.currentZone"
            :custom-radius-enabled="store.customRadiusMode.enabled"
            :custom-radius-meters="store.customRadiusMode.radiusMeters"
            :active-group-filter="store.filters.vulnerabilityGroup"
            :hazard-events="store.activeHazards?.events ?? []"
            :geocode-target="geocodeTarget"
            @select-place="handleSelectPlace"
            @map-radius-sync="handleMapRadiusSync"
            @toggle-group-filter="handleToggleGroupFilter"
          />
        </div>

        <div class="workspace-queue-col">
          <PriorityQueuePanel
            :places="store.places"
            :selected-place="store.selectedPlace"
            :filters="store.filters"
            :is-loading="store.isLoading"
            @filter-change="store.fetchPlacesAndHeatmap"
            @reset-filters="handleResetFilters"
            @select-place="handleSelectPlace"
          />
        </div>
      </main>

      <PlaceTriageDrawer
        v-model:visible="store.isTriageDrawerOpen"
        :place="store.selectedPlace"
        @save-triage="handleSaveTriage"
      />
    </div>
  </ElConfigProvider>
</template>

<style scoped>
.dashboard-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: var(--eoc-bg-canvas);
  color: var(--eoc-text-primary);
  transition: background-color 0.25s ease, color 0.25s ease;
}

.error-banner {
  border-radius: 0;
}

.dashboard-workspace {
  flex: 1;
  display: grid;
  grid-template-columns: 56% 44%;
  min-height: 0;
  overflow: hidden;
}

.workspace-map-col,
.workspace-queue-col {
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 1024px) {
  .dashboard-shell {
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }

  .dashboard-workspace {
    grid-template-columns: 1fr;
    grid-template-rows: 520px 640px;
  }
}
</style>
