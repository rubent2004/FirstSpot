<script setup lang="ts">
import { computed } from "vue";
import {
  ElButton,
  ElInputNumber,
  ElOption,
  ElOptionGroup,
  ElSelect,
  ElSwitch,
  ElTooltip,
} from "element-plus";
import type {
  AttentionStatus,
  DashboardKPIsRead,
  PredefinedZoneRead,
  SyncPlacesResponse,
} from "../../api/client";
import Icon0 from "../../components/Icon0.vue";
import VbCountUp from "../../components/vue-bits/VbCountUp.vue";
import { useI18n } from "../../i18n/useI18n";
import { useTheme } from "../../composables/useTheme";

const props = defineProps<{
  zones: PredefinedZoneRead[];
  selectedZoneKey: string;
  activeZoneName: string;
  kpis: DashboardKPIsRead;
  isSyncing: boolean;
  customRadiusEnabled: boolean;
  customRadiusMeters: number;
  lastSyncSummary: SyncPlacesResponse | null;
  activeStatusFilter?: AttentionStatus | "";
  activeMinUrgency?: number | null;
}>();

const emit = defineEmits<{
  (e: "update:selectedZoneKey", value: string): void;
  (e: "change-zone", zoneKey: string): void;
  (e: "sync-zone", zoneKey: string): void;
  (e: "update:customRadiusEnabled", value: boolean): void;
  (e: "update:customRadiusMeters", value: number): void;
  (
    e: "quick-kpi-filter",
    payload: { status: AttentionStatus | ""; minUrgency: number | null },
  ): void;
}>();

const { locale, t, toggleLocale } = useI18n();
const { isDark, toggleTheme } = useTheme();

const groupedZones = computed(() => {
  const map = new Map<string, PredefinedZoneRead[]>();
  for (const zone of props.zones) {
    const country = (zone as { country?: string }).country || "El Salvador";
    if (!map.has(country)) {
      map.set(country, []);
    }
    map.get(country)!.push(zone);
  }
  return Array.from(map.entries()).map(([country, zones]) => ({
    country,
    zones,
  }));
});

function handleZoneChange(val: string): void {
  if (!val) return;
  emit("update:selectedZoneKey", val);
  emit("change-zone", val);
}

function handleKpiClick(
  status: AttentionStatus | "",
  minUrgency: number | null = null,
): void {
  const isAlreadyActive =
    props.activeStatusFilter === status &&
    (props.activeMinUrgency ?? null) === minUrgency;
  if (isAlreadyActive) {
    emit("quick-kpi-filter", { status: "", minUrgency: null });
  } else {
    emit("quick-kpi-filter", { status, minUrgency });
  }
}
</script>

<template>
  <header class="sync-header-bar" data-testid="sync-header-bar">
    <div class="header-main-row">
      <div class="brand-block">
        <div class="brand-identity-row">
          <span class="pulse-beacon" aria-hidden="true"></span>
          <Icon0 name="shield_alert" :size="15" class="eyebrow-icon" />
          <h1 class="brand-title">{{ t.header.title }}</h1>
          <span class="coe-tag">COE 24/7</span>
          <span class="brand-badge-clean">{{ t.header.badge }}</span>
        </div>
      </div>

      <div class="sync-controls-group">
        <div class="control-item">
          <ElSelect
            :model-value="props.selectedZoneKey"
            :placeholder="t.header.zonePlaceholder"
            size="small"
            class="zone-select"
            data-testid="zone-select"
            filterable
            @update:model-value="handleZoneChange"
          >
            <template #prefix>
              <Icon0 name="compass" :size="12" />
            </template>
            <ElOptionGroup
              v-for="group in groupedZones"
              :key="group.country"
              :label="group.country"
            >
              <ElOption
                v-for="zone in group.zones"
                :key="zone.key"
                :label="`${zone.name} (${zone.department})`"
                :value="zone.key"
              />
            </ElOptionGroup>
          </ElSelect>
        </div>

        <div class="control-item">
          <ElButton
            type="primary"
            size="small"
            :loading="props.isSyncing"
            class="sync-btn"
            data-testid="sync-overpass-btn"
            @click="emit('sync-zone', props.selectedZoneKey || 'sonsonate')"
          >
            <template v-if="!props.isSyncing" #icon>
              <Icon0 name="radar" :size="13" />
            </template>
            {{ props.isSyncing ? t.header.syncingBtn : t.header.syncBtn }}
          </ElButton>
        </div>

        <div
          class="control-item radius-mode-box"
          :class="{ 'is-radius-active': props.customRadiusEnabled }"
        >
          <div class="radius-switch-row">
            <span class="control-label">
              <Icon0 name="crosshair" :size="11" />
              {{ t.header.radiusModeLabel }}
            </span>
            <ElSwitch
              :model-value="props.customRadiusEnabled"
              size="small"
              data-testid="custom-radius-switch"
              @update:model-value="
                (val) => emit('update:customRadiusEnabled', Boolean(val))
              "
            />
            <template v-if="props.customRadiusEnabled">
              <ElInputNumber
                :model-value="props.customRadiusMeters"
                :min="500"
                :max="25000"
                :step="500"
                size="small"
                controls-position="right"
                class="radius-num-input"
                @update:model-value="
                  (val) => emit('update:customRadiusMeters', Number(val ?? 3000))
                "
              />
              <span class="radius-unit">m</span>
            </template>
          </div>
        </div>

        <div class="control-item lang-switch-item">
          <ElTooltip :content="t.header.langToggleTooltip" placement="bottom">
            <button
              type="button"
              class="lang-toggle-btn"
              data-testid="lang-toggle-btn"
              @click="toggleLocale"
            >
              <Icon0 name="globe" :size="12" />
              <span :class="{ 'active-lang': locale === 'es' }">ES</span>
              <span class="lang-sep">/</span>
              <span :class="{ 'active-lang': locale === 'en' }">EN</span>
            </button>
          </ElTooltip>
        </div>

        <div class="control-item theme-switch-item">
          <ElTooltip :content="isDark ? 'Cambiar a Modo Claro' : 'Cambiar a Modo Oscuro'" placement="bottom">
            <button
              type="button"
              class="theme-toggle-btn"
              data-testid="theme-toggle-btn"
              @click="toggleTheme"
            >
              <Icon0 :name="isDark ? 'sun' : 'moon'" :size="13" />
              <span>{{ isDark ? 'Claro' : 'Oscuro' }}</span>
            </button>
          </ElTooltip>
        </div>
      </div>
    </div>

    <!-- Sleek Minimalist Operational KPI Statusline -->
    <div class="kpi-strip" data-testid="kpi-strip">
      <button
        type="button"
        class="kpi-item"
        :class="{
          'is-active':
            !props.activeStatusFilter &&
            (props.activeMinUrgency ?? null) === null,
        }"
        data-testid="kpi-total"
        @click="handleKpiClick('', null)"
      >
        <span class="kpi-dot bg-sky"></span>
        <span class="kpi-label">{{ t.kpis.activeZone }}:</span>
        <strong class="kpi-val">
          <VbCountUp
            :value="props.kpis.total_places"
            :suffix="t.kpis.placesSuffix"
          />
        </strong>
        <span class="zone-pill">{{ props.activeZoneName }}</span>
      </button>

      <span class="kpi-divider" aria-hidden="true">|</span>

      <button
        type="button"
        class="kpi-item"
        :class="{
          'is-active': props.activeMinUrgency === 4,
          'has-alert': props.kpis.critical_urgency_count > 0,
        }"
        data-testid="kpi-critical"
        @click="handleKpiClick('', 4)"
      >
        <span class="kpi-dot bg-red" :class="{ 'pulse-danger': props.kpis.critical_urgency_count > 0 }"></span>
        <span class="kpi-label">{{ t.kpis.criticalUrgency }}:</span>
        <strong class="kpi-val text-red">
          <VbCountUp :value="props.kpis.critical_urgency_count" />
        </strong>
      </button>

      <span class="kpi-divider" aria-hidden="true">|</span>

      <button
        type="button"
        class="kpi-item"
        :class="{ 'is-active': props.activeStatusFilter === 'pending' }"
        data-testid="kpi-pending"
        @click="handleKpiClick('pending', null)"
      >
        <span class="kpi-dot bg-amber"></span>
        <span class="kpi-label">{{ t.kpis.pendingTriage }}:</span>
        <strong class="kpi-val text-amber">
          <VbCountUp :value="props.kpis.pending_count" />
        </strong>
      </button>

      <span class="kpi-divider" aria-hidden="true">|</span>

      <button
        type="button"
        class="kpi-item"
        :class="{ 'is-active': props.activeStatusFilter === 'in_progress' }"
        data-testid="kpi-in-progress"
        @click="handleKpiClick('in_progress', null)"
      >
        <span class="kpi-dot bg-blue"></span>
        <span class="kpi-label">{{ t.kpis.inProgress }}:</span>
        <strong class="kpi-val text-blue">
          <VbCountUp :value="props.kpis.in_progress_count" />
        </strong>
      </button>

      <span class="kpi-divider" aria-hidden="true">|</span>

      <button
        type="button"
        class="kpi-item"
        :class="{ 'is-active': props.activeStatusFilter === 'attended' }"
        data-testid="kpi-attended"
        @click="handleKpiClick('attended', null)"
      >
        <span class="kpi-dot bg-emerald"></span>
        <span class="kpi-label">{{ t.kpis.attended }}:</span>
        <strong class="kpi-val text-emerald">
          <VbCountUp :value="props.kpis.attended_count" />
        </strong>
      </button>

      <span class="kpi-divider" aria-hidden="true">|</span>

      <div class="kpi-item kpi-item-static" data-testid="kpi-population">
        <span class="kpi-dot bg-purple"></span>
        <span class="kpi-label">{{ t.kpis.vulnerablePop }}:</span>
        <strong class="kpi-val">
          <VbCountUp
            :value="props.kpis.total_estimated_vulnerable"
            :suffix="t.kpis.peopleSuffix"
          />
        </strong>
      </div>
    </div>
  </header>
</template>

<style scoped>
.sync-header-bar {
  background: var(--eoc-bg-panel);
  color: var(--eoc-text-primary);
  padding: 8px 18px 7px;
  border-bottom: 1px solid var(--eoc-border);
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 20;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.header-main-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.brand-block {
  display: flex;
  align-items: center;
}

.brand-identity-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pulse-beacon {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--eoc-success);
  box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.6);
  animation: beacon-pulse 2.2s infinite;
}

@keyframes beacon-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.6);
  }
  70% {
    box-shadow: 0 0 0 5px rgba(52, 211, 153, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(52, 211, 153, 0);
  }
}

.eyebrow-icon {
  color: var(--eoc-accent);
}

.brand-title {
  margin: 0;
  font-size: 14.5px;
  font-weight: 700;
  letter-spacing: -0.015em;
  color: var(--eoc-text-primary);
}

.coe-tag {
  font-size: 9px;
  font-weight: 700;
  color: var(--eoc-accent);
  background: var(--eoc-accent-glow);
  border: 1px solid var(--eoc-border);
  padding: 2px 6px;
  border-radius: 4px;
  letter-spacing: 0.04em;
}

.brand-badge-clean {
  font-size: 10px;
  font-weight: 600;
  color: var(--eoc-text-muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.sync-controls-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.control-item {
  display: flex;
  align-items: center;
}

.control-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--eoc-text-secondary);
  font-weight: 500;
}

.zone-select {
  width: 210px;
}

.sync-btn {
  font-weight: 600;
  font-size: 12px;
  height: 28px;
  background: var(--eoc-accent) !important;
  border-color: var(--eoc-accent) !important;
  color: var(--eoc-text-inverse) !important;
  transition: all 0.15s ease;
}

.sync-btn:hover {
  background: var(--eoc-accent-hover) !important;
  border-color: var(--eoc-accent-hover) !important;
}

.radius-mode-box {
  background: var(--eoc-bg-card);
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid var(--eoc-border);
  transition: all 0.15s ease;
}

.radius-mode-box.is-radius-active {
  border-color: var(--eoc-accent);
  background: var(--eoc-accent-glow);
}

.radius-switch-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.radius-num-input {
  width: 90px;
}

.radius-unit {
  font-size: 11px;
  color: var(--eoc-text-secondary);
  font-weight: 600;
}

.lang-switch-item {
  justify-content: flex-end;
}

.lang-toggle-btn,
.theme-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 9px;
  border-radius: 6px;
  border: 1px solid var(--eoc-border);
  background: var(--eoc-bg-card);
  color: var(--eoc-text-secondary);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.lang-toggle-btn:hover,
.theme-toggle-btn:hover {
  border-color: var(--eoc-accent);
  color: var(--eoc-text-primary);
  background: var(--eoc-bg-hover);
}

.lang-toggle-btn .active-lang {
  color: var(--eoc-accent);
  font-weight: 700;
}

.lang-sep {
  opacity: 0.3;
}

/* Operational Minimalist Statusline */
.kpi-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  padding: 4px 0 2px;
  border-top: 1px solid var(--eoc-border-subtle);
  scrollbar-width: none;
}

.kpi-strip::-webkit-scrollbar {
  display: none;
}

.kpi-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--eoc-bg-card);
  border: 1px solid var(--eoc-border);
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 11px;
  color: var(--eoc-text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.kpi-item:hover {
  background: var(--eoc-bg-hover);
  color: var(--eoc-text-primary);
  border-color: var(--eoc-accent);
}

.kpi-item.is-active {
  background: var(--eoc-accent-glow);
  color: var(--eoc-text-primary);
  border-color: var(--eoc-accent);
}

.kpi-item.has-alert {
  border-color: var(--eoc-critical-border);
  background: var(--eoc-critical-bg);
}

.kpi-item-static {
  cursor: default;
}

.kpi-item-static:hover {
  background: var(--eoc-bg-card);
  border-color: var(--eoc-border);
  color: var(--eoc-text-secondary);
}

.kpi-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.pulse-danger {
  animation: pulse-dot-red 2s infinite;
}

@keyframes pulse-dot-red {
  0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6); }
  70% { box-shadow: 0 0 0 4px rgba(239, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

.kpi-label {
  color: var(--eoc-text-muted);
  font-weight: 500;
  font-size: 11px;
}

.kpi-item:hover .kpi-label,
.kpi-item.is-active .kpi-label {
  color: var(--eoc-text-secondary);
}

.kpi-val {
  font-weight: 700;
  font-size: 11.5px;
  color: var(--eoc-text-primary);
  font-variant-numeric: tabular-nums;
}

.zone-pill {
  font-size: 9.5px;
  background: var(--eoc-bg-panel);
  color: var(--eoc-accent);
  padding: 1px 5px;
  border-radius: 3px;
  border: 1px solid var(--eoc-border);
  font-weight: 600;
  margin-left: 2px;
}

.kpi-divider {
  display: inline-block;
  width: 1px;
  height: 12px;
  background: var(--eoc-border);
  color: transparent;
  font-size: 0;
  margin: 0 2px;
  user-select: none;
}

.bg-sky { background: var(--eoc-accent); }
.bg-red { background: var(--eoc-critical); }
.bg-amber { background: var(--eoc-warning); }
.bg-blue { background: var(--eoc-info); }
.bg-emerald { background: var(--eoc-success); }
.bg-purple { background: #a855f7; }

.text-red { color: var(--eoc-critical); }
.text-amber { color: var(--eoc-warning); }
.text-blue { color: var(--eoc-info); }
.text-emerald { color: var(--eoc-success); }
</style>

