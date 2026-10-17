<script setup lang="ts">
import { computed } from "vue";
import type { ActiveHazardsResponse, HazardScenarioPreset } from "../../api/client";
import InfoPopover from "../../components/InfoPopover.vue";
import { useI18n } from "../../i18n/useI18n";
import { formatRelativeTime } from "../../utils/date";
import { FEED_LABELS, feedStatusKey, needsAttention } from "./feedStatus";
import HazardTelemetryStrip from "./HazardTelemetryStrip.vue";

const props = defineProps<{
  activeHazards: ActiveHazardsResponse | null;
  scenario: HazardScenarioPreset;
  lastCheckedAt: string | null;
  isRefreshing: boolean;
  refreshError: string | null;
}>();

const emit = defineEmits<{
  (e: "change-scenario", scenario: HazardScenarioPreset): void;
  (e: "fly-to-coordinates", lat: number, lon: number, label: string): void;
}>();

const { locale } = useI18n();
const labels = computed(() => FEED_LABELS[locale.value]);
const key = computed(() =>
  feedStatusKey({
    activeHazards: props.activeHazards,
    scenario: props.scenario,
    isRefreshing: props.isRefreshing,
    refreshError: props.refreshError,
  }),
);
const attention = computed(() => needsAttention(key.value));
const hazardCount = computed(() => props.activeHazards?.events.length ?? 0);
const checked = computed(() =>
  props.lastCheckedAt ? formatRelativeTime(props.lastCheckedAt, locale.value) : null,
);
const summary = computed(() => {
  const parts: string[] = [labels.value[key.value]];
  if (hazardCount.value > 0) parts.push(`${hazardCount.value} ${labels.value.hazards}`);
  if (checked.value) parts.push(checked.value);
  return parts.join(" · ");
});
</script>

<template>
  <InfoPopover :label="`${labels.title}: ${summary}`" placement="top" align="start">
    <template #trigger>
      <span class="chip" :class="[`is-${key}`, { attention }]" data-testid="feeds-chip">
        <i class="dot" aria-hidden="true"></i>
        <span class="text">{{ summary }}</span>
        <span aria-hidden="true">▾</span>
      </span>
    </template>
    <HazardTelemetryStrip
      stacked
      :active-hazards="activeHazards"
      :scenario="scenario"
      :last-checked-at="lastCheckedAt"
      :is-refreshing="isRefreshing"
      :refresh-error="refreshError"
      @change-scenario="emit('change-scenario', $event)"
      @fly-to-coordinates="(lat, lon, label) => emit('fly-to-coordinates', lat, lon, label)"
    />
  </InfoPopover>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
  white-space: nowrap;
}
/* A status dot is never the only signal: the words beside it carry the state */
.dot {
  width: 6px;
  height: 6px;
  border-radius: var(--eoc-radius-pill);
  background: var(--eoc-success);
}
.is-refreshing .dot {
  background: var(--eoc-info);
}
.attention .dot {
  background: var(--eoc-warning);
}
.is-error .dot {
  background: var(--eoc-critical);
}
.attention .text {
  color: var(--eoc-text-primary);
  font-weight: var(--eoc-fw-semibold);
}
</style>
