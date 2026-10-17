<script setup lang="ts">
import { computed, ref } from "vue";
import { ElButton, ElInput, ElSegmented, ElSkeleton } from "element-plus";
import type { DistrictPrioRead } from "../../api/client";
import { fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";
import ClassPips from "./ClassPips.vue";
import DistrictRow from "./DistrictRow.vue";
import HonestyNotice from "./HonestyNotice.vue";
import { groupByClass, type SortKey } from "./rankModel";
import {
  ALERT_CLASS_ORDER,
  classCarrier,
  classLabels,
  type AlertClassKey,
  type ClassCounts,
  type TriageMode,
} from "./triageModel";
import { REVEAL_CHUNK, type ScopeKey } from "./useDistrictFilters";

const props = defineProps<{
  /** Already scoped, filtered and sorted by the panel. */
  shown: DistrictPrioRead[];
  counts: ClassCounts;
  nationalTotal: number;
  selectedCode: string | null;
  isLoading: boolean;
  error: string | null;
  mode: TriageMode;
  classFilter: AlertClassKey | null;
  sort: SortKey;
  scopeAvailable: boolean;
  department: string | null;
  scope: ScopeKey;
}>();

const emit = defineEmits<{
  (e: "select", code: string): void;
  (e: "retry"): void;
  (e: "update:classFilter", value: AlertClassKey | null): void;
  (e: "clear-filters"): void;
  (e: "update:scope", value: ScopeKey): void;
  (e: "update:sort", value: SortKey): void;
}>();

const search = defineModel<string>("search", { required: true });
const revealLimit = defineModel<number>("revealLimit", { required: true });

const { t } = useI18n();
const c = computed(() => t.value.community);

const isFirstLoad = computed(() => props.isLoading && props.shown.length === 0 && !props.error);
const showExposed = computed(() => props.mode === "event");
const grouped = computed(() => props.sort === "score");
const hasMore = computed(() => revealLimit.value < props.shown.length);
const hasNarrowing = computed(() => props.classFilter !== null || search.value.trim() !== "");

const sortOptions = computed(() => [
  { value: "score", label: c.value.list.sortScore },
  ...(showExposed.value ? [{ value: "exposed", label: c.value.list.sortExposed }] : []),
  { value: "name", label: c.value.list.sortName },
]);

const scopeOptions = computed(() => [
  { value: "zone", label: fillMessage(c.value.list.scopeZone, { department: props.department ?? "" }) },
  { value: "country", label: c.value.list.scopeCountry },
]);

/** One control that filters AND explains: pips, name and count per level. */
const levelOptions = computed(() => [
  {
    value: "all",
    label: c.value.list.classFilterAll,
    count: ALERT_CLASS_ORDER.reduce((sum, key) => sum + props.counts[key], 0),
    key: null as AlertClassKey | null,
  },
  ...ALERT_CLASS_ORDER.map((key) => ({
    value: key,
    label: classLabels(c.value, props.mode, key).name,
    count: props.counts[key],
    key: key as AlertClassKey | null,
  })),
]);

function onLevelChange(value: string | number | boolean): void {
  emit("update:classFilter", value === "all" ? null : (value as AlertClassKey));
}

const countText = computed(() =>
  fillMessage(c.value.list.showing, { shown: props.shown.length, total: props.nationalTotal }),
);

/** Groups of the districts currently within the reveal budget; headings keep full counts. */
const visibleGroups = computed(() => {
  let budget = revealLimit.value;
  const source = grouped.value
    ? groupByClass(props.shown)
    : [{ key: "flat" as const, districts: props.shown }];
  const out: Array<{ key: string; total: number; districts: DistrictPrioRead[] }> = [];
  for (const group of source) {
    if (budget <= 0) break;
    out.push({
      key: group.key,
      total: group.districts.length,
      districts: group.districts.slice(0, budget),
    });
    budget -= group.districts.length;
  }
  return out;
});

function groupLabel(key: string): string {
  if (key === "withheld") return c.value.list.withheld;
  const level = key as AlertClassKey;
  return props.mode === "event" ? c.value.classes[level].name : c.value.levels[level].group;
}

// Roving tab stop: one row is tabbable, arrows move between rows.
const focusCode = ref<string | null>(null);
const container = ref<HTMLElement | null>(null);
const rowRefs = new Map<string, { focus: () => void }>();

const tabbableCode = computed(() => {
  const codes = visibleGroups.value.flatMap((g) => g.districts.map((d) => d.district_code));
  if (focusCode.value && codes.includes(focusCode.value)) return focusCode.value;
  return props.selectedCode && codes.includes(props.selectedCode) ? props.selectedCode : (codes[0] ?? null);
});

function setRowRef(code: string, instance: unknown): void {
  if (instance) rowRefs.set(code, instance as { focus: () => void });
  else rowRefs.delete(code);
}

function onKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement;
  if (!target.classList.contains("row")) return;
  const rows = Array.from(container.value?.querySelectorAll<HTMLElement>("button.row") ?? []);
  const at = rows.indexOf(target);
  const next: Record<string, number> = {
    ArrowDown: Math.min(at + 1, rows.length - 1),
    ArrowUp: Math.max(at - 1, 0),
    Home: 0,
    End: rows.length - 1,
  };
  if (!(event.key in next)) return;
  event.preventDefault();
  rows[next[event.key]]?.focus();
}

defineExpose({
  focusRow(code: string): void {
    const row = rowRefs.get(code);
    if (row) row.focus();
    else container.value?.focus();
  },
});
</script>

<template>
  <section class="rank-list" :aria-label="c.list.ariaLabel" :aria-busy="isLoading">
    <div class="controls">
      <div class="search-row">
        <ElInput
          v-model="search"
          size="small"
          clearable
          class="search"
          :placeholder="c.list.search"
          :aria-label="c.list.search"
        />
        <ElSegmented
          size="small"
          class="sort"
          :model-value="sort"
          :options="sortOptions"
          :aria-label="c.list.sortLabel"
          @change="(value: string | number | boolean) => emit('update:sort', value as SortKey)"
        />
      </div>

      <ElSegmented
        size="small"
        class="levels"
        :model-value="classFilter ?? 'all'"
        :options="levelOptions"
        :aria-label="c.list.classFilterLabel"
        @change="onLevelChange"
      >
        <template #default="{ item }">
          <span class="level" :class="item.key ? classCarrier(mode, item.key) : ''" :title="item.key ? classLabels(c, mode, item.key).meaning : undefined">
            <ClassPips v-if="item.key" :alert-class="item.key" />
            {{ item.label }}
            <span class="eoc-numeric count">{{ item.count }}</span>
          </span>
        </template>
      </ElSegmented>

      <div class="scope-row">
        <ElSegmented
          v-if="scopeAvailable"
          size="small"
          :model-value="scope"
          :options="scopeOptions"
          :aria-label="c.list.scopeLabel"
          @change="(value: string | number | boolean) => emit('update:scope', value as ScopeKey)"
        />
        <span v-else class="scope-label" data-testid="scope-label">{{ c.list.scopeCountry }}</span>
        <span class="eoc-numeric count-line" data-testid="list-count" role="status" aria-live="polite">{{ countText }}</span>
      </div>
    </div>

    <div v-if="error" class="state error" role="alert">
      <span>{{ c.list.loadFailed }}</span>
      <ElButton size="small" @click="emit('retry')">{{ c.list.retry }}</ElButton>
    </div>
    <div v-else-if="isFirstLoad" class="state" role="status">
      <span class="sr-only">{{ c.list.loading }}</span>
      <ElSkeleton animated :rows="6" />
    </div>

    <template v-else>
      <div class="columns eoc-label">
        <span :title="fillMessage(c.list.nationalRank, { total: nationalTotal })">
          <span aria-hidden="true">#</span>
          <span class="sr-only">{{ c.list.columnRank }}</span>
        </span>
        <span>{{ c.list.columnDistrict }}</span>
        <span class="score-head">
          {{ c.list.columnScore }}
          <HonestyNotice :district-count="nationalTotal" />
        </span>
      </div>

      <div
        ref="container"
        class="rows"
        :class="{ refreshing: isLoading }"
        tabindex="-1"
        @keydown="onKeydown"
      >
        <p v-if="shown.length === 0" class="state empty">
          {{ c.list.empty }}
          <button v-if="hasNarrowing" type="button" class="link" @click="emit('clear-filters')">
            {{ c.list.clearFilters }}
          </button>
          <button
            v-else-if="scopeAvailable && scope === 'zone'"
            type="button"
            class="link"
            @click="emit('update:scope', 'country')"
          >
            {{ c.list.scopeCountry }}
          </button>
        </p>

        <section v-for="group in visibleGroups" :key="group.key" class="group">
          <h3
            v-if="grouped"
            class="group-head"
            data-testid="group-head"
            :class="group.key === 'withheld' ? '' : classCarrier(mode, group.key as AlertClassKey)"
          >
            <ClassPips v-if="group.key !== 'withheld'" :alert-class="group.key as AlertClassKey" />
            <span>{{ groupLabel(group.key) }}</span>
            <span aria-hidden="true">·</span>
            <span class="eoc-numeric">{{ group.total }}</span>
          </h3>
          <ul class="group-rows">
            <li v-for="district in group.districts" :key="district.district_code">
              <DistrictRow
                :ref="(instance) => setRowRef(district.district_code, instance)"
                :district="district"
                :mode="mode"
                :tabbable="district.district_code === tabbableCode"
                :selected="district.district_code === selectedCode"
                @select="emit('select', district.district_code)"
                @focus="focusCode = district.district_code"
              />
            </li>
          </ul>
        </section>

        <div v-if="hasMore" class="more">
          <ElButton size="small" @click="revealLimit += REVEAL_CHUNK">
            {{ c.list.showMore }}
          </ElButton>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.rank-list {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
  min-height: 0;
  flex: 1;
}
.controls {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
}
.search-row,
.scope-row {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}
.search {
  flex: 1 1 140px;
  min-width: 0;
}
.sort :deep(.el-segmented__item),
.rank-list :deep(.el-segmented__item) {
  min-height: var(--eoc-target-min);
  font-size: var(--eoc-fs-micro);
}
.levels {
  align-self: stretch;
  --el-border-radius-base: var(--eoc-radius-control);
}
.level {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  white-space: nowrap;
}
.level .count {
  color: var(--eoc-text-secondary);
}
.scope-label {
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-primary);
}
.count-line {
  margin-left: auto;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
.columns {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 84px;
  column-gap: var(--eoc-gap-x);
  align-items: center;
  padding: 0 var(--eoc-pad-panel) 0 calc(var(--eoc-gap-x) + 4px);
}
.columns > :first-child {
  text-align: right;
}
.score-head {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  white-space: nowrap;
}
.link {
  background: transparent;
  border: 0;
  padding: 0 var(--eoc-gap-x);
  min-height: var(--eoc-target-min);
  color: var(--eoc-accent-text);
  font: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
}
.rows {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  border: var(--eoc-border-width) solid var(--eoc-border);
  border-radius: var(--eoc-radius-control);
  background: var(--eoc-bg-panel);
}
.rows.refreshing {
  opacity: 0.6;
}
.group-head {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  margin: 0;
  min-height: var(--eoc-target-min);
  padding: 0 var(--eoc-gap-x);
  background: var(--eoc-bg-header);
  border-bottom: var(--eoc-border-width) solid var(--eoc-border-strong);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--eoc-text-primary);
}
.group-rows {
  list-style: none;
  margin: 0;
  padding: 0;
}
.state {
  padding: var(--eoc-pad-panel);
  font-size: var(--eoc-fs-body);
  color: var(--eoc-text-secondary);
}
.state p {
  margin: 0 0 var(--eoc-gap-y);
}
.state.error {
  color: var(--eoc-text-primary);
  border-left: 3px solid var(--eoc-critical);
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}
.more {
  padding: var(--eoc-gap-y);
  text-align: center;
}
</style>
