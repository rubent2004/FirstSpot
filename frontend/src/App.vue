<script setup lang="ts">
import { onMounted } from "vue";
import { ElAlert } from "element-plus";
import SyncHeaderBar from "./modules/sync-controls/SyncHeaderBar.vue";
import VulnerabilityHeatmapCanvas from "./modules/map-viewer/VulnerabilityHeatmapCanvas.vue";
import PriorityQueuePanel from "./modules/priority-queue/PriorityQueuePanel.vue";
import PlaceTriageDrawer from "./modules/priority-queue/PlaceTriageDrawer.vue";
import { usePrioritizationStore } from "./stores/usePrioritizationStore";
import type { PlaceRead, PlaceTriageUpdate } from "./api/client";

const store = usePrioritizationStore();

onMounted(async () => {
  await store.initializeDashboard();
});

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
</script>

<template>
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
      @update:selected-zone-key="(val) => (store.selectedZoneKey = val)"
      @sync-zone="handleZoneSync"
      @update:custom-radius-enabled="
        (val) => (store.customRadiusMode.enabled = val)
      "
      @update:custom-radius-meters="
        (val) => (store.customRadiusMode.radiusMeters = val)
      "
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
          @select-place="handleSelectPlace"
          @map-radius-sync="handleMapRadiusSync"
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
</template>

<style scoped>
.dashboard-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: #f8fafc;
}

.error-banner {
  border-radius: 0;
}

.dashboard-workspace {
  flex: 1;
  display: grid;
  grid-template-columns: 58% 42%;
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
    grid-template-rows: 520px 600px;
  }
}
</style>
