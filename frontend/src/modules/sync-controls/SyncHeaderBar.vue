<script setup lang="ts">
import {
  ElButton,
  ElInputNumber,
  ElOption,
  ElSelect,
  ElStatistic,
  ElSwitch,
  ElTag,
} from "element-plus";
import type {
  DashboardKPIsRead,
  PredefinedZoneRead,
  SyncPlacesResponse,
} from "../../api/client";

const props = defineProps<{
  zones: PredefinedZoneRead[];
  selectedZoneKey: string;
  activeZoneName: string;
  kpis: DashboardKPIsRead;
  isSyncing: boolean;
  customRadiusEnabled: boolean;
  customRadiusMeters: number;
  lastSyncSummary: SyncPlacesResponse | null;
}>();

const emit = defineEmits<{
  (e: "update:selectedZoneKey", value: string): void;
  (e: "sync-zone", zoneKey: string): void;
  (e: "update:customRadiusEnabled", value: boolean): void;
  (e: "update:customRadiusMeters", value: number): void;
}>();

function handleZoneChange(val: string): void {
  emit("update:selectedZoneKey", val);
  emit("sync-zone", val);
}
</script>

<template>
  <header class="sync-header-bar" data-testid="sync-header-bar">
    <div class="header-top-row">
      <div class="brand-block">
        <div class="brand-badge">POSTGIS + OVERPASS QL</div>
        <h1 class="brand-title">Geo-Prioridad Vulnerable</h1>
        <p class="brand-subtitle">
          Humanitarian Geospatial Prioritization &amp; Institutional Dispatch
        </p>
      </div>

      <div class="sync-controls-group">
        <div class="control-item">
          <span class="control-label">Target Zone (El Salvador)</span>
          <ElSelect
            :model-value="props.selectedZoneKey"
            placeholder="Select zone"
            size="default"
            class="zone-select"
            data-testid="zone-select"
            @update:model-value="handleZoneChange"
          >
            <ElOption
              v-for="zone in props.zones"
              :key="zone.key"
              :label="`${zone.name} (${zone.department})`"
              :value="zone.key"
            />
          </ElSelect>
        </div>

        <div class="control-item">
          <span class="control-label">Overpass Ingestion</span>
          <ElButton
            type="primary"
            :loading="props.isSyncing"
            data-testid="sync-overpass-btn"
            @click="emit('sync-zone', props.selectedZoneKey)"
          >
            {{ props.isSyncing ? "Syncing OSM..." : "Sync Zone with Overpass" }}
          </ElButton>
        </div>

        <div class="control-item radius-mode-box">
          <div class="radius-switch-row">
            <span class="control-label">Map Click Radius Sync</span>
            <ElSwitch
              :model-value="props.customRadiusEnabled"
              active-text="Active"
              inactive-text="Off"
              size="small"
              data-testid="custom-radius-switch"
              @update:model-value="
                (val) => emit('update:customRadiusEnabled', Boolean(val))
              "
            />
          </div>
          <ElInputNumber
            :model-value="props.customRadiusMeters"
            :min="500"
            :max="25000"
            :step="500"
            size="small"
            :disabled="!props.customRadiusEnabled"
            @update:model-value="
              (val) => emit('update:customRadiusMeters', Number(val ?? 3000))
            "
          />
        </div>
      </div>
    </div>

    <div class="kpi-strip" data-testid="kpi-strip">
      <div class="kpi-card">
        <ElStatistic
          title="Active Zone"
          :value="props.kpis.total_places"
          suffix="places"
        >
          <template #prefix>
            <ElTag size="small" type="info" effect="dark">
              {{ props.activeZoneName }}
            </ElTag>
          </template>
        </ElStatistic>
      </div>

      <div class="kpi-card kpi-critical">
        <ElStatistic
          title="Critical Urgency (L4-L5)"
          :value="props.kpis.critical_urgency_count"
        />
      </div>

      <div class="kpi-card kpi-pending">
        <ElStatistic title="Pending Triage" :value="props.kpis.pending_count" />
      </div>

      <div class="kpi-card kpi-progress">
        <ElStatistic
          title="In Progress (Dispatched)"
          :value="props.kpis.in_progress_count"
        />
      </div>

      <div class="kpi-card kpi-attended">
        <ElStatistic title="Attended" :value="props.kpis.attended_count" />
      </div>

      <div class="kpi-card kpi-population">
        <ElStatistic
          title="Est. Vulnerable Population"
          :value="props.kpis.total_estimated_vulnerable"
          suffix="people"
        />
      </div>

      <div v-if="props.lastSyncSummary" class="sync-status-pill">
        <ElTag
          :type="props.lastSyncSummary.used_fallback ? 'warning' : 'success'"
          size="small"
        >
          {{
            props.lastSyncSummary.used_fallback
              ? `Offline Seed (${props.lastSyncSummary.synced_places_count} synced)`
              : `Live Overpass (${props.lastSyncSummary.synced_places_count} synced)`
          }}
        </ElTag>
      </div>
    </div>
  </header>
</template>

<style scoped>
.sync-header-bar {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: #f8fafc;
  padding: 12px 20px;
  border-bottom: 1px solid #334155;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.header-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.brand-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-badge {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #38bdf8;
  text-transform: uppercase;
}

.brand-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
}

.brand-subtitle {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
}

.sync-controls-group {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  flex-wrap: wrap;
}

.control-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.control-label {
  font-size: 11px;
  color: #cbd5e1;
  font-weight: 600;
}

.zone-select {
  width: 220px;
}

.radius-mode-box {
  background: rgba(255, 255, 255, 0.05);
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.radius-switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  align-items: center;
}

.kpi-card {
  background: rgba(30, 41, 59, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  padding: 8px 12px;
}

.kpi-critical {
  border-left: 3px solid #ef4444;
}

.kpi-pending {
  border-left: 3px solid #f59e0b;
}

.kpi-progress {
  border-left: 3px solid #3b82f6;
}

.kpi-attended {
  border-left: 3px solid #10b981;
}

.kpi-population {
  border-left: 3px solid #a855f7;
}

:deep(.el-statistic__head) {
  color: #94a3b8;
  font-size: 11px;
  margin-bottom: 2px;
}

:deep(.el-statistic__content) {
  color: #f8fafc;
  font-size: 18px;
  font-weight: 700;
}

.sync-status-pill {
  display: flex;
  justify-content: flex-end;
}
</style>
