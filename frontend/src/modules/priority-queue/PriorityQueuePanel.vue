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
  CATEGORY_LABELS,
  GROUP_LABELS,
  STATUS_LABELS,
  type AttentionStatus,
  type PlaceCategory,
  type PlaceRead,
} from "../../api/client";
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

function handleRowClick(row: PlaceRead): void {
  emit("select-place", row, false);
}
</script>

<template>
  <section class="priority-queue-panel" data-testid="priority-queue-panel">
    <div class="queue-header">
      <div>
        <h2 class="queue-title">Institutional Dispatch Queue</h2>
        <p class="queue-subtitle">
          Ordered by multi-criteria <code>priority_score</code> (PostGIS 500m
          cluster density)
        </p>
      </div>
      <ElButton size="small" @click="emit('reset-filters')">
        Reset Filters
      </ElButton>
    </div>

    <div class="filters-grid">
      <ElInput
        v-model="props.filters.search"
        placeholder="Search location by name..."
        clearable
        size="small"
        data-testid="search-input"
        @input="emit('filter-change')"
        @clear="emit('filter-change')"
      />

      <ElSelect
        v-model="props.filters.vulnerabilityGroup"
        placeholder="All Vulnerability Groups"
        clearable
        size="small"
        @change="emit('filter-change')"
      >
        <ElOption
          v-for="(label, groupKey) in GROUP_LABELS"
          :key="groupKey"
          :label="label"
          :value="groupKey"
        />
      </ElSelect>

      <ElSelect
        v-model="props.filters.category"
        placeholder="All OSM Categories"
        clearable
        size="small"
        @change="emit('filter-change')"
      >
        <ElOption
          v-for="(label, catKey) in CATEGORY_LABELS"
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
          <ElRadioButton value="">All</ElRadioButton>
          <ElRadioButton value="pending">Pending</ElRadioButton>
          <ElRadioButton value="in_progress">In Progress</ElRadioButton>
          <ElRadioButton value="attended">Attended</ElRadioButton>
        </ElRadioGroup>

        <ElSwitch
          v-model="props.filters.includeAttendedInHeatmap"
          active-text="Show Attended in Heatmap"
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
        height="100%"
        empty-text="No vulnerable places match the current filters."
        data-testid="places-table"
        @row-click="handleRowClick"
      >
        <ElTableColumn label="Score" width="82" sortable prop="priority_score">
          <template #default="{ row }">
            <span class="score-pill" data-testid="row-priority-score">
              {{ Number(row.priority_score).toFixed(1) }}
            </span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="Place & Category" min-width="190">
          <template #default="{ row }">
            <div class="place-cell">
              <strong class="place-name">{{ row.name }}</strong>
              <div class="place-badges">
                <ElTag size="small" effect="plain">
                  {{
                    CATEGORY_LABELS[row.category as PlaceCategory] ??
                    row.category
                  }}
                </ElTag>
                <span class="cluster-badge" title="Places within 500m">
                  +{{ row.nearby_places_count }} in 500m
                </span>
              </div>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn label="Urgency / Vuln." width="120">
          <template #default="{ row }">
            <div class="urgency-cell">
              <ElTag
                size="small"
                :type="getUrgencyTagType(row.urgency_level)"
                effect="dark"
              >
                L{{ row.urgency_level }}
              </ElTag>
              <span class="vuln-count">
                {{ row.estimated_vulnerable_count }} ppl
              </span>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn label="Status" width="110">
          <template #default="{ row }">
            <ElTag
              size="small"
              :type="getStatusTagType(row.attention_status)"
            >
              {{
                STATUS_LABELS[row.attention_status as AttentionStatus] ??
                row.attention_status
              }}
            </ElTag>
          </template>
        </ElTableColumn>

        <ElTableColumn label="Action" width="90" fixed="right">
          <template #default="{ row }">
            <ElButton
              type="primary"
              link
              size="small"
              data-testid="open-triage-btn"
              @click.stop="emit('select-place', row as PlaceRead, true)"
            >
              Triage
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
  background: #ffffff;
  border-left: 1px solid #e2e8f0;
  padding: 14px 16px;
  gap: 12px;
  box-sizing: border-box;
}

.queue-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.queue-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.queue-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #64748b;
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.status-filter-row {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.table-container {
  flex: 1;
  min-height: 360px;
  overflow: hidden;
}

.score-pill {
  display: inline-block;
  font-weight: 700;
  font-size: 13px;
  color: #0f172a;
  background: #f1f5f9;
  padding: 2px 7px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
}

.place-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.place-name {
  font-size: 13px;
  color: #1e293b;
  line-height: 1.25;
}

.place-badges {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.cluster-badge {
  font-size: 11px;
  color: #475569;
  background: #e2e8f0;
  padding: 1px 6px;
  border-radius: 4px;
}

.urgency-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.vuln-count {
  font-size: 11px;
  color: #475569;
}
</style>
