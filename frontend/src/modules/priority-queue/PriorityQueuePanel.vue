<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  ElButton,
  ElInput,
  ElSkeleton,
  ElTable,
  ElTableColumn,
  ElTag,
} from "element-plus";
import {
  GROUP_COLORS,
  type AttentionStatus,
  type PlaceCategory,
  type PlaceRead,
  type VulnerabilityGroup,
} from "../../api/client";
import Icon0 from "../../components/Icon0.vue";
import { CATEGORY_ICON_MAP } from "../../components/icons0Registry";
import { useI18n } from "../../i18n/useI18n";
import {
  exposedPopulationState,
  formatExposureValue,
} from "./populationExposure";

const props = defineProps<{
  places: PlaceRead[];
  selectedPlace: PlaceRead | null;
  isLoading: boolean;
}>();

const emit = defineEmits<{
  (e: "select-place", place: PlaceRead, openDrawer: boolean): void;
}>();

const { t, locale, describePlace } = useI18n();

/**
 * How many rows reach the DOM before the operator asks for more.
 *
 * Twenty-nine pages of ten rows was unusable: nobody pages through a disaster.
 * A deep single list is the right shape, but an unbounded one is a liability on
 * the hardware this runs on, so the queue reveals itself in slices as the
 * operator scrolls, with an explicit control for keyboard and screen-reader
 * users who never fire a scroll event.
 */
const REVEAL_CHUNK = 50;

/** Distance from the bottom, in pixels, at which the next slice is revealed. */
const REVEAL_TRIGGER_PX = 280;

/** Steps in the urgency meter; mirrors the 1..5 scale the API accepts. */
const URGENCY_STEPS = [1, 2, 3, 4, 5] as const;

const queueFilter = ref<string>("");
const revealLimit = ref<number>(REVEAL_CHUNK);
const panelRoot = ref<HTMLElement | null>(null);

/** Accent-insensitive comparison key, so "clinica" finds "Clínica". */
function searchKey(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

/**
 * Every string a row shows that an operator might type to find it again.
 * Matching the rendered label rather than the stored name means an unnamed
 * place is findable by the wording actually on screen.
 */
function rowSearchKey(place: PlaceRead): string {
  const described = describePlace(place);
  return searchKey(
    [
      described.label,
      described.hint ?? "",
      t.value.categories[place.category as PlaceCategory] ?? place.category,
      t.value.groups[place.vulnerability_group as VulnerabilityGroup] ?? "",
      place.zone_name,
    ].join(" "),
  );
}

const filteredPlaces = computed<PlaceRead[]>(() => {
  const needle = searchKey(queueFilter.value.trim());
  if (needle.length === 0) return props.places;
  return props.places.filter((place) => rowSearchKey(place).includes(needle));
});

const visiblePlaces = computed<PlaceRead[]>(() =>
  filteredPlaces.value.slice(0, revealLimit.value),
);

const hasMoreToReveal = computed(
  () => revealLimit.value < filteredPlaces.value.length,
);

const isFilterActive = computed(() => queueFilter.value.trim().length > 0);

/** Nothing has arrived yet, so structure is more useful than a spinner. */
const isFirstLoad = computed(() => props.isLoading && props.places.length === 0);

/**
 * Rank in the whole queue, not in the filtered view.
 *
 * "#7" has to mean the same thing before and after someone narrows the list,
 * because it is what one coordinator says to another over the radio.
 */
const rankByPlaceId = computed(
  () => new Map(props.places.map((place, index) => [place.id, index + 1])),
);

const countSummary = computed(() => {
  const total = props.places.length;
  if (!isFilterActive.value) return String(total);
  return locale.value === "es"
    ? `${filteredPlaces.value.length} de ${total}`
    : `${filteredPlaces.value.length} of ${total}`;
});

function revealMore(): void {
  if (!hasMoreToReveal.value) return;
  revealLimit.value = Math.min(
    revealLimit.value + REVEAL_CHUNK,
    filteredPlaces.value.length,
  );
}

/**
 * The scrolling element Element Plus puts inside the table body.
 *
 * Reaching for it by class is a soft coupling, so a miss degrades to the
 * explicit "show more" control rather than to a queue that cannot grow.
 */
function queueScrollElement(): HTMLElement | null {
  return (
    panelRoot.value?.querySelector<HTMLElement>(
      ".el-table__body-wrapper .el-scrollbar__wrap",
    ) ?? null
  );
}

function handleQueueScroll(): void {
  const host = queueScrollElement();
  if (!host) {
    revealMore();
    return;
  }
  const remaining = host.scrollHeight - host.scrollTop - host.clientHeight;
  if (remaining <= REVEAL_TRIGGER_PX) revealMore();
}

// A new result set or a new filter starts the queue at its top again.
watch(
  () => [props.places, queueFilter.value] as const,
  () => {
    revealLimit.value = REVEAL_CHUNK;
  },
);

// The selected place must always be on screen, even deep in a long queue.
watch(
  () => [filteredPlaces.value, props.selectedPlace?.id] as const,
  ([places, selectedPlaceId]) => {
    if (!selectedPlaceId) return;
    const index = places.findIndex((place) => place.id === selectedPlaceId);
    if (index >= revealLimit.value) {
      revealLimit.value = Math.min(index + REVEAL_CHUNK, places.length);
    }
  },
  { immediate: true },
);

function getStatusTagType(
  status: AttentionStatus,
): "warning" | "primary" | "success" {
  if (status === "attended") return "success";
  if (status === "in_progress") return "primary";
  return "warning";
}

/**
 * Severity tone for an urgency level.
 *
 * A low level is muted rather than green: nothing in this queue is "all clear",
 * it is only less urgent than the rest, and green would say otherwise.
 */
function getUrgencyTone(level: number): string {
  if (level >= 5) return "urgency-critical";
  if (level === 4) return "urgency-high";
  if (level === 3) return "urgency-medium";
  return "urgency-low";
}

/**
 * Highest score in the current result set, which is the only reference an
 * absolute score has. The API sorts by score, so this is the first row, but
 * reducing over the list keeps the bar honest if that ever stops being true.
 */
const topPriorityScore = computed(() =>
  props.places.reduce(
    (highest, place) => Math.max(highest, Number(place.priority_score)),
    0,
  ),
);

/**
 * How long a row's priority bar is, as a fraction of the top of the queue.
 *
 * The useful signal in this column is relative position, not the absolute
 * figure: identical scores in ten consecutive rows carry no information, and
 * with a hazard bonus folded in, a fixed red/amber threshold would tell the
 * operator nothing except that the whole zone is alarming. A floor keeps the
 * lowest row visible as a bar rather than as nothing.
 */
function priorityShare(score: number): number {
  const top = topPriorityScore.value;
  if (!(top > 0)) return 0;
  return Math.min(1, Math.max(0.05, Number(score) / top));
}

/** How many other vulnerable places sit inside the same 500 m. */
function nearbyLabel(count: number): string {
  return `${count} ${count === 1 ? t.value.queue.nearbyOne : t.value.queue.nearbyMany}`;
}

/** False while the census figure is unknown, which is never the same as zero. */
function isExposureKnown(place: PlaceRead): boolean {
  return exposedPopulationState(place).kind === "estimate";
}

/**
 * Estimated exposed residents, or the reason the figure is unavailable.
 *
 * The unit lives in the column header rather than in all 288 cells; the three
 * readings an operator must keep apart — a figure, a withheld figure and no
 * census coverage at all — each keep their own wording.
 */
function exposureText(place: PlaceRead): string {
  const state = exposedPopulationState(place);
  if (state.kind === "estimate") {
    return formatExposureValue(state.value, locale.value);
  }
  const reason =
    state.kind === "withheld"
      ? t.value.exposure.withheld
      : t.value.exposure.noCoverage;
  return `— ${reason}`;
}

/** Selecting a row moves the map; opening the name opens the record. */
function handleRowClick(row: PlaceRead): void {
  emit("select-place", row, false);
}

function tableRowClassName({ row }: { row: PlaceRead }): string {
  if (props.selectedPlace?.id === row.id) {
    return "is-selected-place-row";
  }
  return "";
}
</script>

<template>
  <section
    ref="panelRoot"
    class="priority-queue-panel"
    data-testid="priority-queue-panel"
    data-tour="places-queue"
  >
    <div class="queue-header">
      <div class="queue-title-block">
        <div class="queue-title-row">
          <Icon0 name="activity" :size="18" class="title-icon" />
          <h2 class="queue-title">{{ t.queue.title }}</h2>
          <span class="queue-count-badge eoc-numeric" data-testid="queue-count">
            {{ countSummary }} {{ t.queue.showingCount }}
          </span>
          <span
            v-if="props.isLoading && props.places.length > 0"
            class="queue-updating"
            role="status"
          >
            {{ t.queue.updating }}
          </span>
        </div>
        <p class="queue-subtitle">
          {{ t.queue.subtitle }}
        </p>
      </div>
    </div>

    <ElInput
      v-model="queueFilter"
      class="queue-filter"
      size="small"
      clearable
      :placeholder="t.queue.filterPlaceholder"
      :aria-label="t.queue.filterPlaceholder"
      data-testid="queue-filter-input"
    >
      <template #prefix>
        <Icon0 name="search" :size="12" />
      </template>
    </ElInput>

    <div class="table-container">
      <ElSkeleton
        v-if="isFirstLoad"
        class="queue-skeleton"
        animated
        :rows="8"
        data-testid="queue-skeleton"
      />
      <ElTable
        v-else
        :data="visiblePlaces"
        stripe
        highlight-current-row
        row-key="id"
        :row-class-name="tableRowClassName"
        height="100%"
        data-testid="places-table"
        @row-click="handleRowClick"
        @scroll="handleQueueScroll"
      >
        <template #empty>
          <div class="queue-empty">
            <p>{{ isFilterActive ? t.queue.filterEmpty : t.queue.emptyText }}</p>
            <ElButton
              v-if="isFilterActive"
              size="small"
              data-testid="queue-filter-clear"
              @click="queueFilter = ''"
            >
              {{ t.queue.clearFilter }}
            </ElButton>
          </div>
        </template>

        <ElTableColumn :label="t.queue.colRank" width="34" align="center">
          <template #default="{ row }">
            <span
              class="rank-badge eoc-numeric"
              :class="{ 'rank-top-three': (rankByPlaceId.get(row.id) ?? 99) <= 3 }"
            >
              {{ rankByPlaceId.get(row.id) ?? "—" }}
            </span>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colScore" width="84" prop="priority_score">
          <template #default="{ row }">
            <div
              class="priority-cell"
              :title="t.queue.priorityHint"
              data-testid="row-priority-score"
            >
              <span class="priority-figure eoc-numeric">
                {{ Math.round(Number(row.priority_score)) }}
              </span>
              <span class="priority-bar" aria-hidden="true">
                <i
                  :style="{
                    width: `${priorityShare(Number(row.priority_score)) * 100}%`,
                  }"
                ></i>
              </span>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colPlace" min-width="164">
          <template #default="{ row }">
            <div class="place-cell">
              <div class="place-title-line">
                <span
                  class="category-icon-badge"
                  :style="{
                    backgroundColor:
                      GROUP_COLORS[row.vulnerability_group as VulnerabilityGroup] ??
                      'var(--eoc-text-muted)',
                  }"
                >
                  <Icon0
                    :name="
                      CATEGORY_ICON_MAP[row.category as PlaceCategory] ??
                      'map_pin'
                    "
                    :size="13"
                  />
                </span>
                <button
                  type="button"
                  class="place-name"
                  :title="t.queue.triageAction"
                  data-testid="open-triage-btn"
                  @click.stop="emit('select-place', row as PlaceRead, true)"
                >
                  {{ describePlace(row as PlaceRead).label }}
                </button>
              </div>
              <p
                v-if="describePlace(row as PlaceRead).hint"
                class="place-hint"
                data-testid="row-place-hint"
              >
                <Icon0 name="map_pin" :size="11" />
                {{ describePlace(row as PlaceRead).hint }}
              </p>
              <div class="place-badges">
                <span
                  v-if="props.selectedPlace?.id === row.id"
                  class="selected-place-indicator"
                  data-testid="selected-place-indicator"
                  :aria-label="locale === 'es' ? 'Lugar marcado en el mapa' : 'Place marked on the map'"
                >
                  <Icon0 name="locate_fixed" :size="11" />
                  {{ locale === "es" ? "En el mapa" : "On map" }}
                </span>
                <ElTag size="small" effect="plain">
                  {{
                    t.categories[row.category as PlaceCategory] ?? row.category
                  }}
                </ElTag>
                <span
                  v-if="row.nearby_places_count > 0"
                  class="nearby-badge eoc-numeric"
                  :title="t.queue.nearbyHint"
                  data-testid="row-nearby-places"
                >
                  <Icon0 name="layers" :size="11" />
                  {{ nearbyLabel(row.nearby_places_count) }}
                </span>
              </div>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colUrgency" width="84">
          <template #default="{ row }">
            <div
              class="urgency-reading"
              :class="getUrgencyTone(row.urgency_level)"
              role="img"
              :aria-label="`${t.urgency[row.urgency_level] ?? ''} · ${row.urgency_level} ${t.queue.urgencyScaleSuffix}`"
              data-testid="row-urgency"
            >
              <span class="urgency-meter" aria-hidden="true">
                <i
                  v-for="step in URGENCY_STEPS"
                  :key="step"
                  :class="{ 'is-reached': step <= row.urgency_level }"
                ></i>
              </span>
              <span class="urgency-word">
                {{ t.urgency[row.urgency_level] ?? row.urgency_level }}
              </span>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colExposed" width="112">
          <template #default="{ row }">
            <span
              class="exposed-population eoc-numeric"
              :class="{ 'is-unknown': !isExposureKnown(row as PlaceRead) }"
              :title="
                isExposureKnown(row as PlaceRead)
                  ? t.exposure.methodNote
                  : t.exposure.unknownHint
              "
              data-testid="row-exposed-population"
            >
              {{ exposureText(row as PlaceRead) }}
            </span>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colStatus" width="88">
          <template #default="{ row }">
            <ElTag
              size="small"
              :type="getStatusTagType(row.attention_status)"
              class="status-tag"
            >
              {{
                t.statuses[row.attention_status as AttentionStatus] ??
                row.attention_status
              }}
            </ElTag>
          </template>
        </ElTableColumn>
      </ElTable>
    </div>

    <div v-if="hasMoreToReveal" class="queue-reveal">
      <ElButton
        size="small"
        data-testid="queue-reveal-more"
        @click="revealMore"
      >
        {{ t.queue.revealMore }}
      </ElButton>
      <span class="queue-reveal-count eoc-numeric">
        {{ visiblePlaces.length }} / {{ filteredPlaces.length }}
      </span>
    </div>
  </section>
</template>

<style scoped>
.priority-queue-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  background: var(--eoc-bg-panel);
  border-left: var(--eoc-border-width) solid var(--eoc-border);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
  gap: var(--eoc-gap-y);
  box-sizing: border-box;
}

.queue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--eoc-gap-x);
}

.queue-title-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.queue-title-row {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}

.title-icon {
  color: var(--eoc-accent);
}

.queue-title {
  margin: 0;
  font-size: var(--eoc-fs-title);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-primary);
}

.queue-count-badge {
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-secondary);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
  padding: 0 var(--eoc-gap-x);
  border-radius: var(--eoc-radius-pill);
}

/* A refresh keeps the previous rows on screen, so it only needs a quiet word */
.queue-updating {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-muted);
}

.queue-subtitle {
  margin: 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-muted);
}

.queue-filter :deep(.el-input__wrapper) {
  background-color: var(--eoc-bg-sunken) !important;
  box-shadow: inset 0 0 0 var(--eoc-border-width) var(--eoc-border) !important;
}

.queue-filter :deep(.el-input__prefix-inner svg) {
  color: var(--eoc-text-muted);
}

/* Elevation is the 1px frame, not a shadow */
.table-container {
  flex: 1;
  min-width: 0;
  min-height: 240px;
  overflow: hidden;
  border: var(--eoc-border-width) solid var(--eoc-border);
  border-radius: var(--eoc-radius-control);
  background: var(--eoc-bg-panel);
}

.queue-skeleton {
  padding: var(--eoc-pad-panel);
}

.queue-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--eoc-gap-x);
  padding: var(--eoc-pad-panel);
}

.queue-empty p {
  margin: 0;
  font-size: var(--eoc-fs-body);
  color: var(--eoc-text-secondary);
}

.queue-reveal {
  min-height: var(--eoc-icon-btn);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--eoc-gap-x);
  padding: 0 2px;
}

.queue-reveal-count {
  color: var(--eoc-text-muted);
  font-size: var(--eoc-fs-micro);
  white-space: nowrap;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 3px;
  border-radius: var(--eoc-radius-pill);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-muted);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
}

.rank-badge.rank-top-three {
  color: var(--eoc-critical);
  background: var(--eoc-critical-bg);
  border-color: var(--eoc-critical-border);
}

.priority-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-right: var(--eoc-gap-x);
}

.priority-figure {
  font-size: var(--eoc-fs-body);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-primary);
  line-height: 1.2;
}

/* Magnitude, not severity: the bar stays neutral so the only severity ramp in
   the row is the urgency meter, and the two never argue about "how bad" */
.priority-bar {
  display: block;
  height: 3px;
  border-radius: var(--eoc-radius-pill);
  background: var(--eoc-bg-sunken);
  border: var(--eoc-border-width) solid var(--eoc-border);
  overflow: hidden;
}

.priority-bar > i {
  display: block;
  height: 100%;
  background: var(--eoc-text-muted);
}

.place-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.place-title-line {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
}

/* Group color is data, so the glyph stays white in both themes */
.category-icon-badge {
  width: 20px;
  height: 20px;
  border-radius: var(--eoc-radius-control);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--eoc-on-accent);
  flex-shrink: 0;
}

/* The name is the way into a place's record: one target, no extra column of
   288 repeated buttons, and focusable so the queue stays keyboard-operable */
.place-name {
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  font: inherit;
  font-size: var(--eoc-fs-body);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-primary);
  line-height: 1.3;
  cursor: pointer;
  overflow-wrap: anywhere;
}

.place-name:hover {
  color: var(--eoc-accent-text);
  text-decoration: underline;
}

/* A locating hint only exists for a place with no name, so it carries the
   quiet weight of supporting information rather than competing with the label */
.place-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0;
  padding-left: 26px;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
  line-height: 1.3;
}

.place-badges {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
  padding-left: 26px;
}

.nearby-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-regular);
  color: var(--eoc-text-secondary);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
  padding: 0 5px;
  border-radius: var(--eoc-radius-control);
}

/* Five steps read as a level at a glance; the word keeps it from being a
   colour-only encoding, and the tone is semantic because urgency is severity */
.urgency-reading {
  --urgency-tone: var(--eoc-text-muted);
  display: flex;
  align-items: center;
  gap: 5px;
}

.urgency-reading.urgency-critical {
  --urgency-tone: var(--eoc-critical);
}

.urgency-reading.urgency-high {
  --urgency-tone: var(--eoc-warning);
}

.urgency-reading.urgency-medium {
  --urgency-tone: var(--eoc-info);
}

.urgency-meter {
  display: inline-flex;
  align-items: flex-end;
  gap: 1.5px;
  flex-shrink: 0;
}

.urgency-meter > i {
  width: 3px;
  height: 11px;
  border-radius: 1px;
  background: var(--eoc-bg-sunken);
  border: var(--eoc-border-width) solid var(--eoc-border);
}

.urgency-meter > i.is-reached {
  background: var(--urgency-tone);
  border-color: var(--urgency-tone);
}

.urgency-word {
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  color: var(--urgency-tone);
  line-height: 1.2;
  white-space: nowrap;
}

/* A merely-less-urgent row must not read as resolved, so its word stays in the
   body colour while the meter carries the muted level */
.urgency-reading.urgency-low .urgency-word {
  color: var(--eoc-text-secondary);
}

.exposed-population {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-regular);
  line-height: 1.35;
  color: var(--eoc-text-secondary);
}

/* An unknown figure reads quieter than a real one, and never as a zero */
.exposed-population.is-unknown {
  color: var(--eoc-text-muted);
}

:deep(.el-table) {
  --el-table-bg-color: var(--eoc-bg-panel);
  --el-table-tr-bg-color: var(--eoc-bg-panel);
  --el-table-header-bg-color: var(--eoc-bg-card);
  --el-table-border-color: var(--eoc-border);
  --el-table-text-color: var(--eoc-text-primary);
  --el-table-header-text-color: var(--eoc-text-secondary);
  --el-table-row-hover-bg-color: var(--eoc-bg-hover);
  background-color: var(--eoc-bg-panel);
}

:deep(.el-table .cell) {
  padding: 0 8px;
}

/* A header that outgrows its column must shorten sideways, never get sliced in
   half by the 24px header row: that vertical clip is how "5496 pob. estimada"
   became unreadable. Cells keep wrapping, because an unknown exposure reading
   needs its full reason */
:deep(.el-table th.el-table__cell .cell) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

:deep(.el-table th.el-table__cell) {
  height: var(--eoc-table-header-h);
  background-color: var(--eoc-bg-card) !important;
  color: var(--eoc-text-label) !important;
  border-bottom: var(--eoc-border-width) solid var(--eoc-border-strong) !important;
  font-weight: var(--eoc-fw-semibold);
  font-size: var(--eoc-fs-micro);
  text-transform: uppercase;
  letter-spacing: 0.09em;
}

:deep(.el-table td.el-table__cell) {
  border-bottom: var(--eoc-border-width) solid var(--eoc-border) !important;
  padding: 4px 0;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background-color: var(--eoc-bg-card) !important;
}

:deep(.el-table__row) {
  cursor: pointer;
  transition: background-color var(--eoc-transition);
}

:deep(.is-selected-place-row > td.el-table__cell) {
  background-color: var(--eoc-bg-active) !important;
}

:deep(.is-selected-place-row > td:first-child) {
  box-shadow: inset 3px 0 0 var(--eoc-accent);
}

/* Selection is operational, so it reads in accent and never in brand lime */
.selected-place-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 18px;
  padding: 1px 5px;
  border: var(--eoc-border-width) solid var(--eoc-accent);
  border-radius: var(--eoc-radius-control);
  background: var(--eoc-bg-selected);
  color: var(--eoc-text-primary);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  line-height: 1;
  white-space: nowrap;
}

:deep(.el-input__inner) {
  color: var(--eoc-text-primary) !important;
}
</style>
