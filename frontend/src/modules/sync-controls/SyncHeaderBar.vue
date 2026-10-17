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
          <span class="brand-badge-clean eoc-label">{{ t.header.badge }}</span>
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
        <strong class="kpi-val eoc-numeric">
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
        <strong class="kpi-val text-red eoc-numeric">
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
        <strong class="kpi-val text-amber eoc-numeric">
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
        <strong class="kpi-val text-blue eoc-numeric">
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
        <strong class="kpi-val text-emerald eoc-numeric">
          <VbCountUp :value="props.kpis.attended_count" />
        </strong>
      </button>

      <span class="kpi-divider" aria-hidden="true">|</span>

      <div class="kpi-item kpi-item-static" data-testid="kpi-population">
        <span class="kpi-dot bg-purple"></span>
        <span class="kpi-label">{{ t.kpis.vulnerablePop }}:</span>
        <strong class="kpi-val eoc-numeric">
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
  background: var(--eoc-bg-header);
  color: var(--eoc-text-primary);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
  border-bottom: var(--eoc-border-width) solid var(--eoc-border);
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
  z-index: 20;
  transition: background-color var(--eoc-transition),
    border-color var(--eoc-transition);
}

.header-main-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--eoc-pad-panel);
}

.brand-block {
  display: flex;
  align-items: center;
}

.brand-identity-row {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}

/* Liveness is signalled by opacity; a glow ring would be a stray shadow */
.pulse-beacon {
  width: 6px;
  height: 6px;
  border-radius: var(--eoc-radius-pill);
  background: var(--eoc-success);
  animation: eoc-beacon-pulse 2.2s infinite;
}

.eyebrow-icon {
  color: var(--eoc-accent);
}

.brand-title {
  margin: 0;
  font-size: var(--eoc-fs-title);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-primary);
}

.coe-tag {
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-accent-text);
  background: var(--eoc-accent-glow);
  border: var(--eoc-border-width) solid var(--eoc-border);
  padding: 1px 5px;
  border-radius: var(--eoc-radius-control);
  letter-spacing: 0.09em;
}

.sync-controls-group {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
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
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
  font-weight: var(--eoc-fw-regular);
}

.zone-select {
  width: 210px;
}

.sync-btn {
  font-weight: var(--eoc-fw-semibold);
  font-size: var(--eoc-fs-body);
  height: var(--eoc-control-h);
}

.radius-mode-box {
  background: var(--eoc-bg-card);
  padding: 1px var(--eoc-gap-x);
  border-radius: var(--eoc-radius-control);
  border: var(--eoc-border-width) solid var(--eoc-border);
  transition: background-color var(--eoc-transition),
    border-color var(--eoc-transition);
}

.radius-mode-box.is-radius-active {
  border-color: var(--eoc-accent);
  background: var(--eoc-bg-selected);
}

.radius-switch-row {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
}

.radius-num-input {
  width: 88px;
}

.radius-unit {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
  font-weight: var(--eoc-fw-semibold);
}

.lang-switch-item {
  justify-content: flex-end;
}

.lang-toggle-btn,
.theme-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: var(--eoc-control-h);
  padding: var(--eoc-pad-button);
  border-radius: var(--eoc-radius-button);
  border: var(--eoc-border-width) solid var(--eoc-border);
  background: var(--eoc-bg-card);
  color: var(--eoc-text-secondary);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  cursor: pointer;
  transition: background-color var(--eoc-transition),
    border-color var(--eoc-transition), color var(--eoc-transition);
}

.lang-toggle-btn:hover,
.theme-toggle-btn:hover {
  border-color: var(--eoc-border-strong);
  color: var(--eoc-text-primary);
  background: var(--eoc-bg-hover);
}

.lang-toggle-btn .active-lang {
  color: var(--eoc-accent-text);
  font-weight: var(--eoc-fw-semibold);
}

.lang-sep {
  color: var(--eoc-text-muted);
}

/* Operational Minimalist Statusline */
.kpi-strip {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  overflow-x: auto;
  padding: 3px 0 1px;
  border-top: var(--eoc-border-width) solid var(--eoc-border-subtle);
  scrollbar-width: none;
}

.kpi-strip::-webkit-scrollbar {
  display: none;
}

.kpi-item {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  height: var(--eoc-control-h);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
  padding: var(--eoc-pad-button);
  border-radius: var(--eoc-radius-control);
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: background-color var(--eoc-transition),
    border-color var(--eoc-transition), color var(--eoc-transition);
}

.kpi-item:hover {
  background: var(--eoc-bg-hover);
  color: var(--eoc-text-primary);
  border-color: var(--eoc-border-strong);
}

.kpi-item.is-active {
  background: var(--eoc-bg-selected);
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
  border-radius: var(--eoc-radius-pill);
  flex-shrink: 0;
}

.pulse-danger {
  animation: eoc-beacon-pulse 2s infinite;
}

.kpi-label {
  color: var(--eoc-text-label);
  font-weight: var(--eoc-fw-regular);
  font-size: var(--eoc-fs-micro);
}

.kpi-item:hover .kpi-label,
.kpi-item.is-active .kpi-label {
  color: var(--eoc-text-secondary);
}

.kpi-val {
  font-weight: var(--eoc-fw-semibold);
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-primary);
}

.zone-pill {
  font-size: var(--eoc-fs-micro);
  background: var(--eoc-bg-sunken);
  color: var(--eoc-text-secondary);
  padding: 0 5px;
  border-radius: var(--eoc-radius-control);
  border: var(--eoc-border-width) solid var(--eoc-border);
  font-weight: var(--eoc-fw-semibold);
  margin-left: 2px;
}

.kpi-divider {
  display: inline-block;
  width: var(--eoc-border-width);
  height: 12px;
  background: var(--eoc-border);
  color: transparent;
  font-size: 0;
  margin: 0 2px;
  user-select: none;
}

/* Status dots map onto the semantic palette; none is decorative */
.bg-sky { background: var(--eoc-accent); }
.bg-red { background: var(--eoc-critical); }
.bg-amber { background: var(--eoc-warning); }
.bg-blue { background: var(--eoc-info); }
.bg-emerald { background: var(--eoc-success); }
.bg-purple { background: var(--eoc-text-muted); }

.text-red { color: var(--eoc-critical); }
.text-amber { color: var(--eoc-warning); }
.text-blue { color: var(--eoc-info); }
.text-emerald { color: var(--eoc-success); }
</style>

