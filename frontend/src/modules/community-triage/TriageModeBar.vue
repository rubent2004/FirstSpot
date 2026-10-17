<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { ElOption, ElSegmented, ElSelect } from "element-plus";
import type { EventSummaryRead, PrioIndexRead } from "../../api/client";
import { useI18n } from "../../i18n/useI18n";
import { describePager, formatUtcTimestamp } from "./formatters";
import { resolveMode, type TriageMode } from "./triageModel";

const props = defineProps<{
  index: PrioIndexRead | null;
  requestedEventId: string | null;
  events: EventSummaryRead[];
  isLoadingEvents: boolean;
  eventsError: string | null;
}>();

const emit = defineEmits<{ (e: "select-event", eventId: string | null): void }>();

const { t, locale } = useI18n();

/**
 * The status line reads the RESPONSE's mode. While a switch is in flight the
 * numbers on screen still belong to the previous mode, and the line must say so.
 */
const displayedMode = computed(() =>
  resolveMode(props.index?.mode, props.requestedEventId),
);

const pickerOpen = ref(false);
const picker = ref<InstanceType<typeof ElSelect> | null>(null);
const showPicker = computed(() => pickerOpen.value || props.requestedEventId !== null);

/** The control follows what was asked for; the status line follows what is shown. */
const segmentValue = computed<TriageMode>(() => (showPicker.value ? "event" : "baseline"));
const segmentOptions = computed(() => [
  { value: "baseline", label: t.value.community.mode.baseline },
  { value: "event", label: t.value.community.mode.event },
]);

const displayedEventId = computed(() =>
  displayedMode.value === "event" ? (props.index?.event?.event_id ?? null) : null,
);
const isSwitching = computed(() => props.requestedEventId !== displayedEventId.value);
const awaitingEvent = computed(() => pickerOpen.value && props.requestedEventId === null);

const event = computed(() => (displayedMode.value === "event" ? props.index?.event ?? null : null));
const shakemapTime = computed(
  () => formatUtcTimestamp(event.value?.shakemap_grid_processed_at) ?? t.value.community.event.shakemapPending,
);
const occurredAt = computed(() => formatUtcTimestamp(event.value?.occurred_at));
const pagerText = computed(() => describePager(event.value?.pager, t.value.community, locale.value));

function eventLabel(item: EventSummaryRead): string {
  const day = item.occurred_at.slice(0, 10);
  const magnitude = item.magnitude !== null ? `M${item.magnitude.toFixed(1)}` : "M ?";
  const suffix = item.has_shakemap ? "" : ` (${t.value.community.event.noShakemap})`;
  return `${magnitude} · ${item.place} · ${day}${suffix}`;
}

function onModeChange(value: string | number | boolean): void {
  if (value === "baseline") {
    pickerOpen.value = false;
    if (props.requestedEventId !== null) emit("select-event", null);
    return;
  }
  pickerOpen.value = true;
  void nextTick(() => picker.value?.focus());
}
</script>

<template>
  <section class="mode-bar" data-tour="mode" :aria-label="t.community.mode.label">
    <ElSegmented
      size="small"
      class="mode-switch"
      :model-value="segmentValue"
      :options="segmentOptions"
      :aria-label="t.community.mode.label"
      @change="onModeChange"
    />

    <p class="meaning" role="status" aria-live="polite" data-testid="mode-badge">
      <strong class="mode-name" :class="displayedMode === 'event' ? 'is-event' : 'is-baseline'">
        {{ displayedMode === "event" ? t.community.mode.event : t.community.mode.baseline }}
      </strong>
      <span aria-hidden="true"> · </span>
      {{ displayedMode === "event" ? t.community.mode.eventShort : t.community.mode.baselineShort }}
      <span v-if="isSwitching" class="pending"> {{ t.community.mode.updating }}</span>
      <span v-else-if="awaitingEvent" class="pending"> {{ t.community.mode.pickEvent }}</span>
    </p>
    <p class="sr-only">{{ displayedMode === "event" ? t.community.mode.eventMeaning : t.community.mode.baselineMeaning }}</p>

    <div v-if="showPicker" class="picker">
      <ElSelect
        ref="picker"
        size="small"
        filterable
        clearable
        :model-value="requestedEventId ?? undefined"
        :loading="isLoadingEvents"
        :placeholder="t.community.event.pickerPlaceholder"
        :aria-label="t.community.event.pickerLabel"
        @change="(value: string | undefined) => emit('select-event', value ?? null)"
      >
        <ElOption
          v-for="item in events"
          :key="item.event_id"
          :value="item.event_id"
          :label="eventLabel(item)"
          :disabled="!item.has_shakemap"
        />
      </ElSelect>
      <p v-if="eventsError" class="error" role="alert">{{ t.community.event.loadFailed }}</p>
    </div>

    <dl v-if="event" class="facts" data-testid="event-facts">
      <div class="fact wide">
        <dt class="eoc-label">{{ t.community.event.pickerLabel }}</dt>
        <dd>
          <span v-if="event.magnitude !== null" class="eoc-numeric">M{{ event.magnitude.toFixed(1) }}</span>
          {{ event.place }}
        </dd>
      </div>
      <div class="fact">
        <dt class="eoc-label">{{ t.community.event.occurredAt }}</dt>
        <dd class="eoc-numeric">{{ occurredAt ?? "—" }}</dd>
      </div>
      <div class="fact">
        <dt class="eoc-label">{{ t.community.event.shakemapGrid }}</dt>
        <dd class="eoc-numeric">{{ shakemapTime }}</dd>
      </div>
      <div class="fact wide">
        <dt class="eoc-label">{{ t.community.event.pager }}</dt>
        <dd>
          <span v-if="pagerText" class="eoc-numeric">{{ pagerText }}</span>
          <span v-else>{{
            event.pager ? t.community.event.pagerUnreadable : t.community.event.pagerNone
          }}</span>
          <small v-if="pagerText">{{ t.community.event.pagerIsRange }}</small>
        </dd>
      </div>
      <p class="revised wide">{{ t.community.event.shakemapRevised }}</p>
    </dl>
  </section>
</template>

<style scoped>
.mode-bar {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
}
.mode-switch {
  align-self: flex-start;
  --el-border-radius-base: var(--eoc-radius-control);
}
.mode-switch :deep(.el-segmented__item) {
  min-height: var(--eoc-target-min);
  min-width: var(--eoc-target-min);
  font-size: var(--eoc-fs-body);
}
/* Mode is identity, not severity: text weight and the accent, never a status hue */
.mode-name {
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-primary);
}
.mode-name.is-event {
  color: var(--eoc-accent-text);
}
.pending {
  color: var(--eoc-text-secondary);
}
.meaning,
.error,
.revised {
  margin: 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
  line-height: 1.4;
}
.error {
  color: var(--eoc-critical);
}
.picker :deep(.el-select) {
  width: 100%;
}
.facts {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--eoc-gap-y) var(--eoc-pad-panel);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
  border-radius: var(--eoc-radius-control);
}
.fact dt {
  margin: 0;
}
.fact dd {
  margin: 0;
  font-size: var(--eoc-fs-body);
  color: var(--eoc-text-primary);
  display: flex;
  flex-direction: column;
}
.fact dd small {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
.wide {
  grid-column: 1 / -1;
}
</style>
