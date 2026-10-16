<script setup lang="ts">
import {
  ElButton,
  ElInput,
  ElOption,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElSwitch,
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
import type { PlaceFilters } from "../../stores/usePrioritizationStore";

const props = defineProps<{
  places: PlaceRead[];
  selectedPlace: PlaceRead | null;
  filters: PlaceFilters;
  isLoading: boolean;
}>();

const emit = defineEmits<{
  (e: "filter-change"): void;
  (e: "reset-filters"): void;
  (e: "select-place", place: PlaceRead, openDrawer: boolean): void;
}>();

const { t, localizePlaceName } = useI18n();

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
          <span class="queue-count-badge">
            {{ props.places.length }} {{ t.queue.showingCount }}
          </span>
        </div>
        <p class="queue-subtitle">
          {{ t.queue.subtitle }}
        </p>
      </div>
      <ElButton
        size="small"
        class="reset-btn"
        @click="emit('reset-filters')"
      >
        <template #icon>
          <Icon0 name="rotate_ccw" :size="13" />
        </template>
        {{ t.queue.resetFilters }}
      </ElButton>
    </div>

    <div class="filters-grid">
      <ElInput
        v-model="props.filters.search"
        :placeholder="t.queue.searchPlaceholder"
        clearable
        size="small"
        data-testid="search-input"
        @input="emit('filter-change')"
        @clear="emit('filter-change')"
      >
        <template #prefix>
          <Icon0 name="search" :size="13" />
        </template>
      </ElInput>

      <ElSelect
        v-model="props.filters.vulnerabilityGroup"
        :placeholder="t.queue.allGroups"
        clearable
        size="small"
        @change="emit('filter-change')"
      >
        <ElOption
          v-for="(label, groupKey) in t.groups"
          :key="groupKey"
          :label="label"
          :value="groupKey"
        />
      </ElSelect>

      <ElSelect
        v-model="props.filters.category"
        :placeholder="t.queue.allCategories"
        clearable
        size="small"
        @change="emit('filter-change')"
      >
        <ElOption
          v-for="(label, catKey) in t.categories"
          :key="catKey"
          :label="label"
          :value="catKey"
        />
      </ElSelect>

      <div class="status-filter-row">
        <ElRadioGroup
          v-model="props.filters.attentionStatus"
          size="small"
          @change="emit('filter-change')"
        >
          <ElRadioButton value="">{{ t.queue.statusAll }}</ElRadioButton>
          <ElRadioButton value="pending">
            {{ t.queue.statusPending }}
          </ElRadioButton>
          <ElRadioButton value="in_progress">
            {{ t.queue.statusInProgress }}
          </ElRadioButton>
          <ElRadioButton value="attended">
            {{ t.queue.statusAttended }}
          </ElRadioButton>
        </ElRadioGroup>

        <ElSwitch
          v-model="props.filters.includeAttendedInHeatmap"
          :active-text="t.queue.showAttendedHeatmap"
          size="small"
          @change="emit('filter-change')"
        />
      </div>
    </div>

    <div class="table-container">
      <ElTable
        :data="props.places"
        v-loading="props.isLoading"
        stripe
        highlight-current-row
        :row-class-name="tableRowClassName"
        height="100%"
        :empty-text="t.queue.emptyText"
        data-testid="places-table"
        @row-click="handleRowClick"
      >
        <ElTableColumn :label="t.queue.colRank" width="46" align="center">
          <template #default="{ $index }">
            <span
              class="rank-badge"
              :class="{ 'rank-top-three': $index < 3 }"
            >
              {{ $index + 1 }}
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
              class="score-pill"
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
                      '#ef4444',
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
                <ElTag size="small" effect="plain">
                  {{
                    t.categories[row.category as PlaceCategory] ?? row.category
                  }}
                </ElTag>
                <span class="cluster-badge" :title="t.drawer.clusterNeighborsText">
                  <Icon0 name="layers" :size="11" />
                  +{{ row.nearby_places_count }} {{ t.queue.clusterBadge }}
                </span>
              </div>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn :label="t.queue.colUrgency" width="125">
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
              <span class="vuln-count">
                <Icon0 name="community_centre" :size="11" />
                {{ row.estimated_vulnerable_count }} {{ t.queue.peopleAbbr }}
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
  </section>
</template>

<style scoped>
.priority-queue-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--eoc-bg-panel);
  border-left: 1px solid var(--eoc-border);
  padding: 10px 14px;
  gap: 8px;
  box-sizing: border-box;
}

.queue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.queue-title-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.queue-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.title-icon {
  color: var(--eoc-accent);
}

.queue-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--eoc-text-primary);
  letter-spacing: -0.015em;
}

.queue-count-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--eoc-accent);
  background: var(--eoc-accent-glow);
  border: 1px solid var(--eoc-border);
  padding: 1px 7px;
  border-radius: 999px;
}

.queue-subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--eoc-text-muted);
}

.reset-btn {
  background: var(--eoc-bg-card);
  border-color: var(--eoc-border);
  color: var(--eoc-text-secondary);
  border-radius: 6px;
  font-size: 12px;
}

.reset-btn:hover {
  background: var(--eoc-bg-hover);
  color: var(--eoc-text-primary);
  border-color: var(--eoc-accent);
}

.filters-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: 8px;
}

.status-filter-row {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 2px;
}

.table-container {
  flex: 1;
  min-height: 360px;
  overflow: hidden;
  border: 1px solid var(--eoc-border);
  border-radius: 8px;
  background: var(--eoc-bg-panel);
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 10.5px;
  font-weight: 700;
  color: var(--eoc-text-muted);
  background: var(--eoc-bg-card);
  border: 1px solid var(--eoc-border);
}

.rank-badge.rank-top-three {
  color: var(--eoc-critical);
  background: var(--eoc-critical-bg);
  border-color: var(--eoc-critical-border);
}

.score-pill {
  display: inline-block;
  font-weight: 700;
  font-size: 12px;
  padding: 2px 7px;
  border-radius: 5px;
  font-variant-numeric: tabular-nums;
}

.score-critical {
  color: var(--eoc-critical);
  background: var(--eoc-critical-bg);
  border: 1px solid var(--eoc-critical-border);
}

.score-high {
  color: var(--eoc-warning);
  background: var(--eoc-warning-bg);
  border: 1px solid var(--eoc-warning-border);
}

.score-medium {
  color: var(--eoc-accent);
  background: var(--eoc-accent-glow);
  border: 1px solid var(--eoc-accent);
}

.score-low {
  color: var(--eoc-info);
  background: var(--eoc-info-bg);
  border: 1px solid var(--eoc-info-border);
}

.place-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.place-title-line {
  display: flex;
  align-items: center;
  gap: 7px;
}

.category-icon-badge {
  width: 20px;
  height: 20px;
  border-radius: 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  flex-shrink: 0;
}

.place-name {
  font-size: 12.5px;
  color: var(--eoc-text-primary);
  line-height: 1.3;
  font-weight: 600;
}

.place-badges {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding-left: 27px;
}

.cluster-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10.5px;
  font-weight: 500;
  color: var(--eoc-text-secondary);
  background: var(--eoc-bg-card);
  border: 1px solid var(--eoc-border);
  padding: 1px 5px;
  border-radius: 4px;
}

.urgency-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
}

.vuln-count {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10.5px;
  font-weight: 500;
  color: var(--eoc-text-secondary);
}

.status-tag-inner {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.triage-cta-btn {
  font-weight: 600;
  font-size: 12px;
  height: 26px;
  border-radius: 6px;
  background: var(--eoc-accent-glow) !important;
  border-color: var(--eoc-border) !important;
  color: var(--eoc-accent) !important;
  transition: all 0.15s ease;
}

.triage-cta-btn:hover {
  background: var(--eoc-accent) !important;
  border-color: var(--eoc-accent) !important;
  color: var(--eoc-text-inverse) !important;
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
  background-color: var(--eoc-bg-card) !important;
  color: var(--eoc-text-secondary) !important;
  border-bottom: 1px solid var(--eoc-border) !important;
  font-weight: 600;
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

:deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid var(--eoc-border) !important;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background-color: var(--eoc-bg-card) !important;
}

:deep(.el-table__row) {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

:deep(.is-selected-place-row > td.el-table__cell) {
  background-color: var(--eoc-bg-active) !important;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  background-color: var(--eoc-bg-card) !important;
  box-shadow: 0 0 0 1px var(--eoc-border) inset !important;
  color: var(--eoc-text-primary) !important;
}

:deep(.el-input__inner) {
  color: var(--eoc-text-primary) !important;
}

:deep(.el-radio-button__inner) {
  background-color: var(--eoc-bg-card) !important;
  border-color: var(--eoc-border) !important;
  color: var(--eoc-text-secondary) !important;
}

:deep(.el-radio-button.is-active .el-radio-button__inner) {
  background-color: var(--eoc-accent) !important;
  color: var(--eoc-text-inverse) !important;
  border-color: var(--eoc-accent) !important;
  box-shadow: none !important;
}
</style>
