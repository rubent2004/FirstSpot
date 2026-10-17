<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  ElButton,
  ElPagination,
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
import {
  CATEGORY_ICON_MAP,
  STATUS_ICON_MAP,
} from "../../components/icons0Registry";
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

const { t, locale, localizePlaceName } = useI18n();
const currentPage = ref(1);
const pageSize = 10;
const visiblePlaces = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return props.places.slice(start, start + pageSize);
});
const pageSummary = computed(() => {
  const total = props.places.length;
  if (total === 0) return "0";
  const first = (currentPage.value - 1) * pageSize + 1;
  const last = Math.min(currentPage.value * pageSize, total);
  return locale.value === "es"
    ? `${first}–${last} de ${total}`
    : `${first}–${last} of ${total}`;
});

watch(
  () => [props.places, props.selectedPlace?.id] as const,
  ([places, selectedPlaceId]) => {
    const selectedIndex = selectedPlaceId
      ? places.findIndex((place) => place.id === selectedPlaceId)
      : -1;
    currentPage.value = selectedIndex >= 0
      ? Math.floor(selectedIndex / pageSize) + 1
      : 1;
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

function getUrgencyTagType(
  level: number,
): "info" | "warning" | "danger" | "primary" {
  if (level >= 5) return "danger";
  if (level === 4) return "warning";
  if (level === 3) return "primary";
  return "info";
}

function getScoreSeverityClass(score: number): string {
  if (score >= 130) return "score-critical";
  if (score >= 110) return "score-high";
  if (score >= 85) return "score-medium";
  return "score-low";
}

/** False while the census figure is unknown, which is never the same as zero. */
function isExposureKnown(place: PlaceRead): boolean {
  return exposedPopulationState(place).kind === "estimate";
}

/** Estimated exposed residents, or the reason the figure is unavailable. */
function exposureText(place: PlaceRead): string {
  const state = exposedPopulationState(place);
  if (state.kind === "estimate") {
    return `${formatExposureValue(state.value, locale.value)} ${t.value.exposure.queueLabel}`;
  }
  const reason =
    state.kind === "withheld"
      ? t.value.exposure.withheld
      : t.value.exposure.noCoverage;
  return `— ${reason}`;
}

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
  <section class="priority-queue-panel" data-testid="priority-queue-panel">
    <div class="queue-header">
      <div class="queue-title-block">
        <div class="queue-title-row">
          <Icon0 name="activity" :size="18" class="title-icon" />
          <h2 class="queue-title">{{ t.queue.title }}</h2>
          <span class="queue-count-badge eoc-numeric">
            {{ props.places.length }} {{ t.queue.showingCount }}
          </span>
        </div>
        <p class="queue-subtitle">
          {{ t.queue.subtitle }}
        </p>
      </div>
    </div>

    <div class="table-container">
      <ElTable
        :data="visiblePlaces"
        v-loading="props.isLoading"
        stripe
        highlight-current-row
        row-key="id"
        :row-class-name="tableRowClassName"
        height="100%"
        :empty-text="t.queue.emptyText"
        data-testid="places-table"
        @row-click="handleRowClick"
      >
        <ElTableColumn :label="t.queue.colRank" width="46" align="center">
          <template #default="{ $index }">
            <span
              class="rank-badge eoc-numeric"
              :class="{ 'rank-top-three': $index < 3 }"
            >
              {{ (currentPage - 1) * pageSize + $index + 1 }}
            </span>
          </template>
        </ElTableColumn>

        <ElTableColumn
          :label="t.queue.colScore"
          width="90"
          sortable
          prop="priority_score"
        >
          <template #default="{ row }">
            <span
              class="score-pill eoc-numeric"
              :class="getScoreSeverityClass(Number(row.priority_score))"
              data-testid="row-priority-score"
            >
              {{ Number(row.priority_score).toFixed(1) }}
            </span>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colPlace" min-width="210">
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
                <strong class="place-name">
                  {{ localizePlaceName(row as PlaceRead) }}
                </strong>
              </div>
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
                <span class="cluster-badge eoc-numeric" :title="t.drawer.clusterNeighborsText">
                  <Icon0 name="layers" :size="11" />
                  +{{ row.nearby_places_count }} {{ t.queue.clusterBadge }}
                </span>
              </div>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colUrgency" width="142">
          <template #default="{ row }">
            <div class="urgency-cell">
              <ElTag
                size="small"
                :type="getUrgencyTagType(row.urgency_level)"
                effect="dark"
              >
                {{
                  t.urgencyShort[row.urgency_level] ?? `L${row.urgency_level}`
                }}
              </ElTag>
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
                <Icon0 name="community_centre" :size="11" />
                {{ exposureText(row as PlaceRead) }}
              </span>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colStatus" width="122">
          <template #default="{ row }">
            <ElTag
              size="small"
              :type="getStatusTagType(row.attention_status)"
              class="status-tag"
            >
              <span class="status-tag-inner">
                <Icon0
                  :name="STATUS_ICON_MAP[row.attention_status as AttentionStatus]"
                  :size="12"
                />
                <span>
                  {{
                    t.statuses[row.attention_status as AttentionStatus] ??
                    row.attention_status
                  }}
                </span>
              </span>
            </ElTag>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colAction" width="108" fixed="right">
          <template #default="{ row }">
            <ElButton
              type="primary"
              plain
              size="small"
              class="triage-cta-btn"
              data-testid="open-triage-btn"
              @click.stop="emit('select-place', row as PlaceRead, true)"
            >
              <span>{{ t.queue.triageAction }}</span>
              <Icon0 name="chevron_right" :size="13" />
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </div>
    <div class="queue-pagination">
      <span class="queue-page-range eoc-numeric">{{ pageSummary }}</span>
      <ElPagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="props.places.length"
        :pager-count="5"
        layout="prev, pager, next"
        background
        size="small"
        :hide-on-single-page="true"
        :aria-label="locale === 'es' ? 'Paginación de lugares priorizados' : 'Prioritized places pagination'"
        data-testid="places-pagination"
      />
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

.queue-subtitle {
  margin: 0;
  font-size: var(--eoc-fs-micro);
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

.queue-pagination {
  min-height: var(--eoc-icon-btn);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--eoc-gap-x);
  padding: 0 2px;
}

.queue-page-range {
  color: var(--eoc-text-muted);
  font-size: var(--eoc-fs-micro);
  white-space: nowrap;
}

.queue-pagination :deep(.el-pagination) {
  --el-pagination-button-bg-color: var(--eoc-bg-card);
  --el-pagination-hover-color: var(--eoc-accent);
  --el-pagination-text-color: var(--eoc-text-secondary);
  padding: 0;
}

.queue-pagination :deep(.el-pager li.is-active) {
  background-color: var(--eoc-accent) !important;
  color: var(--eoc-on-accent) !important;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
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

.score-pill {
  display: inline-block;
  font-weight: var(--eoc-fw-semibold);
  font-size: var(--eoc-fs-body);
  padding: 1px var(--eoc-gap-x);
  border-radius: var(--eoc-radius-control);
}

.score-critical {
  color: var(--eoc-critical);
  background: var(--eoc-critical-bg);
  border: var(--eoc-border-width) solid var(--eoc-critical-border);
}

.score-high {
  color: var(--eoc-warning);
  background: var(--eoc-warning-bg);
  border: var(--eoc-border-width) solid var(--eoc-warning-border);
}

.score-medium {
  color: var(--eoc-text-secondary);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
}

.score-low {
  color: var(--eoc-text-muted);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
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

.place-name {
  font-size: var(--eoc-fs-body);
  color: var(--eoc-text-primary);
  line-height: 1.3;
  font-weight: var(--eoc-fw-semibold);
}

.place-badges {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
  padding-left: 26px;
}

.cluster-badge {
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

.urgency-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
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

.status-tag-inner {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.triage-cta-btn {
  font-weight: var(--eoc-fw-semibold);
  font-size: var(--eoc-fs-micro);
  height: var(--eoc-control-h);
  border-radius: var(--eoc-radius-button);
  background: var(--eoc-bg-card) !important;
  border-color: var(--eoc-border) !important;
  color: var(--eoc-text-primary) !important;
  transition: background-color var(--eoc-transition),
    border-color var(--eoc-transition), color var(--eoc-transition);
}

.triage-cta-btn:hover {
  background: var(--eoc-accent) !important;
  border-color: var(--eoc-accent) !important;
  color: var(--eoc-on-accent) !important;
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

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  background-color: var(--eoc-bg-sunken) !important;
  box-shadow: inset 0 0 0 var(--eoc-border-width) var(--eoc-border) !important;
  color: var(--eoc-text-primary) !important;
}

:deep(.el-input__inner) {
  color: var(--eoc-text-primary) !important;
}

:deep(.el-pagination button:focus-visible),
:deep(.el-pager li:focus-visible) {
  outline: 2px solid var(--eoc-accent);
  outline-offset: 1px;
}

:deep(.el-radio-button__inner) {
  background-color: var(--eoc-bg-card) !important;
  border-color: var(--eoc-border) !important;
  color: var(--eoc-text-secondary) !important;
}

:deep(.el-radio-button.is-active .el-radio-button__inner) {
  background-color: var(--eoc-accent) !important;
  color: var(--eoc-on-accent) !important;
  border-color: var(--eoc-accent) !important;
  box-shadow: none !important;
}
</style>
