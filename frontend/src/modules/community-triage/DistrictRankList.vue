<script setup lang="ts">
import { computed, ref } from "vue";
import { ElButton, ElInput, ElSkeleton } from "element-plus";
import type { DistrictPrioRead } from "../../api/client";
import { useI18n } from "../../i18n/useI18n";
import ClassBadge from "./ClassBadge.vue";
import { formatInteger, formatScore } from "./formatters";
import {
  ALERT_CLASS_ORDER,
  asAlertClass,
  classCounts,
  type AlertClassKey,
} from "./triageModel";

const props = defineProps<{
  districts: DistrictPrioRead[];
  selectedCode: string | null;
  isLoading: boolean;
  error: string | null;
  showExposed: boolean;
}>();

const emit = defineEmits<{
  (e: "select", code: string): void;
  (e: "retry"): void;
}>();

const { t, locale } = useI18n();

/** Rows revealed per step; the full ranking is 262 rows on modest hardware. */
const REVEAL_CHUNK = 60;

const search = ref("");
const classFilter = ref<AlertClassKey | null>(null);
const revealLimit = ref(REVEAL_CHUNK);

function searchKey(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

const counts = computed(() => classCounts(props.districts));

const filtered = computed(() => {
  const needle = searchKey(search.value.trim());
  return props.districts.filter((d) => {
    if (classFilter.value && asAlertClass(d.alert_class) !== classFilter.value) return false;
    return needle.length === 0 || searchKey(d.district_name).includes(needle);
  });
});

const visible = computed(() => filtered.value.slice(0, revealLimit.value));
const hasMore = computed(() => revealLimit.value < filtered.value.length);
const isFirstLoad = computed(() => props.isLoading && props.districts.length === 0);

function toggleClass(key: AlertClassKey): void {
  classFilter.value = classFilter.value === key ? null : key;
  revealLimit.value = REVEAL_CHUNK;
}

function exposedText(d: DistrictPrioRead): string {
  return d.estimated_exposed_population === null
    ? t.value.community.list.exposedUnknown
    : formatInteger(d.estimated_exposed_population, locale.value);
}
</script>

<template>
  <section class="rank-list" :aria-label="t.community.list.ariaLabel">
    <div class="class-chips" role="group">
      <button
        v-for="key in ALERT_CLASS_ORDER"
        :key="key"
        type="button"
        class="chip"
        :class="[`eoc-class-${key}`, { active: classFilter === key }]"
        :aria-pressed="classFilter === key"
        :title="t.community.classes[key].meaning"
        @click="toggleClass(key)"
      >
        <span class="swatch" aria-hidden="true"></span>
        {{ t.community.classes[key].name }}
        <span class="eoc-numeric count">{{ counts[key] }}</span>
      </button>
    </div>

    <ElInput
      v-model="search"
      size="small"
      clearable
      :placeholder="t.community.list.search"
      :aria-label="t.community.list.search"
    />

    <div v-if="error" class="state error" role="alert">
      {{ t.community.list.loadFailed }}
      <ElButton size="small" @click="emit('retry')">{{ t.community.list.retry }}</ElButton>
    </div>
    <ElSkeleton v-else-if="isFirstLoad" animated :rows="6" class="state" />

    <ol v-else class="rows" :class="{ refreshing: isLoading }">
      <li v-if="visible.length === 0" class="state">{{ t.community.list.empty }}</li>
      <li v-for="district in visible" :key="district.district_code">
        <button
          type="button"
          class="row"
          :class="[
            asAlertClass(district.alert_class) ? `eoc-class-${asAlertClass(district.alert_class)}` : '',
            { selected: district.district_code === selectedCode, withheld: district.withheld },
          ]"
          @click="emit('select', district.district_code)"
        >
          <span class="rank eoc-numeric">{{ district.withheld ? "—" : district.rank }}</span>
          <span class="name">{{ district.district_name }}</span>
          <template v-if="district.withheld">
            <span class="withheld-note" :title="t.community.list.withheldHint">
              {{ t.community.list.withheld }}
            </span>
          </template>
          <template v-else>
            <ClassBadge v-if="asAlertClass(district.alert_class)" :alert-class="asAlertClass(district.alert_class)!" />
            <span class="score eoc-numeric">
              {{ district.score === null ? "—" : formatScore(district.score, locale) }}
            </span>
            <span v-if="district.score === 0" class="zero-hint">{{ t.community.list.scoreZero }}</span>
            <span v-if="showExposed" class="exposed eoc-numeric">
              {{ exposedText(district) }}
              <template v-if="district.estimated_exposed_population !== null">
                {{ t.community.list.exposed }}
              </template>
            </span>
          </template>
        </button>
      </li>
      <li v-if="hasMore" class="more">
        <ElButton size="small" @click="revealLimit += REVEAL_CHUNK">
          {{ t.community.list.showMore }}
        </ElButton>
      </li>
    </ol>
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
.class-chips {
  display: flex;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  height: var(--eoc-control-h);
  padding: 0 var(--eoc-gap-x);
  background: var(--eoc-bg-sunken);
  border: var(--eoc-border-width) solid var(--eoc-border);
  border-radius: var(--eoc-radius-control);
  color: var(--eoc-text-secondary);
  font: inherit;
  font-size: var(--eoc-fs-micro);
  cursor: pointer;
}
.chip .swatch {
  width: 8px;
  height: 8px;
  background: var(--class-color);
}
.chip .count {
  color: var(--eoc-text-primary);
  font-weight: var(--eoc-fw-semibold);
}
.chip.active {
  border-color: var(--class-color);
  background: var(--class-bg);
  color: var(--eoc-text-primary);
}
.rows {
  list-style: none;
  margin: 0;
  padding: 0;
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
.row {
  width: 100%;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto 36px;
  align-items: center;
  column-gap: var(--eoc-gap-x);
  padding: var(--eoc-gap-y) var(--eoc-gap-x);
  background: transparent;
  border: 0;
  border-bottom: var(--eoc-border-width) solid var(--eoc-border);
  border-left: 3px solid var(--class-color, var(--eoc-border));
  color: var(--eoc-text-primary);
  font: inherit;
  font-size: var(--eoc-fs-body);
  text-align: left;
  cursor: pointer;
}
.row:hover {
  background: var(--eoc-bg-hover);
}
.row.selected {
  background: var(--eoc-bg-selected);
}
.rank {
  color: var(--eoc-text-muted);
  text-align: right;
}
.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.score {
  font-weight: var(--eoc-fw-semibold);
  text-align: right;
}
.zero-hint {
  grid-column: 2 / -1;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-muted);
}
.exposed {
  grid-column: 2 / -1;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
.withheld-note {
  grid-column: 3 / -1;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-muted);
  font-style: italic;
}
.state {
  padding: var(--eoc-pad-panel);
  font-size: var(--eoc-fs-body);
  color: var(--eoc-text-secondary);
  list-style: none;
}
.state.error {
  color: var(--eoc-critical);
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
}
.more {
  padding: var(--eoc-gap-y);
  text-align: center;
  list-style: none;
}
</style>
