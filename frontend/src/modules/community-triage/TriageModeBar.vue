<script setup lang="ts">
import { computed, ref } from "vue";
import { ElButton, ElOption, ElSelect } from "element-plus";
import type { EventSummaryRead, PrioIndexRead } from "../../api/client";
import { useI18n } from "../../i18n/useI18n";
import { describePager, formatUtcTimestamp } from "./formatters";
import { resolveMode } from "./triageModel";

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
 * The badge reads the RESPONSE's mode. While a switch is in flight the numbers
 * on screen still belong to the previous mode, and the badge must say so.
 */
const displayedMode = computed(() =>
  resolveMode(props.index?.mode, props.requestedEventId),
);

const pickerOpen = ref(false);
const showPicker = computed(() => pickerOpen.value || props.requestedEventId !== null);

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

function chooseBaseline(): void {
  pickerOpen.value = false;
  if (props.requestedEventId !== null) emit("select-event", null);
}
</script>

<template>
  <section class="mode-bar">
    <div class="mode-row">
      <span class="eoc-label">{{ t.community.mode.label }}</span>
      <span
        class="mode-badge"
        :class="displayedMode === 'event' ? 'is-event' : 'is-baseline'"
        data-testid="mode-badge"
      >
        {{ displayedMode === "event" ? t.community.mode.event : t.community.mode.baseline }}
      </span>
      <span class="spacer"></span>
      <ElButton
        size="small"
        :type="displayedMode === 'baseline' && !showPicker ? 'primary' : 'default'"
        @click="chooseBaseline"
      >
        {{ t.community.mode.baseline }}
      </ElButton>
      <ElButton
        size="small"
        :type="showPicker ? 'primary' : 'default'"
        @click="pickerOpen = true"
      >
        {{ t.community.mode.event }}
      </ElButton>
    </div>

    <p class="meaning">
      {{ displayedMode === "event" ? t.community.mode.eventMeaning : t.community.mode.baselineMeaning }}
    </p>

    <div v-if="showPicker" class="picker">
      <ElSelect
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
      <p v-if="eventsError" class="error">{{ t.community.event.loadFailed }}</p>
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
  border: var(--eoc-border-width) solid var(--eoc-border);
  border-radius: var(--eoc-radius-control);
  background: var(--eoc-bg-card);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
}
.mode-row {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
}
.spacer {
  flex: 1;
}
/* Mode is identity, not severity: the operational accent, never a status hue */
.mode-badge {
  height: 18px;
  display: inline-flex;
  align-items: center;
  padding: 0 var(--eoc-gap-x);
  border-radius: var(--eoc-radius-control);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.mode-badge.is-event {
  background: var(--eoc-accent);
  border-color: var(--eoc-accent);
  color: var(--eoc-on-accent);
}
.mode-badge.is-baseline {
  background: var(--eoc-bg-sunken);
  color: var(--eoc-text-primary);
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
  padding-top: var(--eoc-gap-y);
  border-top: var(--eoc-border-width) solid var(--eoc-border);
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
  color: var(--eoc-text-muted);
}
.wide {
  grid-column: 1 / -1;
}
</style>
