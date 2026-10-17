<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from "vue";
import { ElButton } from "element-plus";
import { fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";
import ClassBadge from "./ClassBadge.vue";
import type { ReportModel, ReportRow } from "./exportModel";
import { formatInteger, formatScore } from "./formatters";
import PrintMap from "./PrintMap.vue";
import "./print.css";

export type SheetVariant = "report" | "map";

const props = defineProps<{ model: ReportModel; variant: SheetVariant }>();
const emit = defineEmits<{ (e: "close"): void }>();

const { t, locale } = useI18n();
const s = computed(() => t.value.community.sheet);

/** A full ranking is 262 rows; the printed report carries the head of it. */
const REPORT_ROWS = 50;

const reportRows = computed(() => props.model.rows.slice(0, REPORT_ROWS));
const priorityRows = computed(() =>
  props.model.rows.filter((row) => row.classKey === "roja" || row.classKey === "naranja"),
);
const isEvent = computed(() => props.model.mode === "event");

function sphereText(row: ReportRow): string {
  if (!row.sphere) return "";
  return fillMessage(s.value.sphereCompact, {
    water: formatInteger(row.sphere.water_litres_per_day, locale.value),
    food: formatInteger(row.sphere.food_kcal_per_day, locale.value),
    shelter: formatInteger(row.sphere.shelter_area_m2, locale.value),
  });
}

function rowScore(row: ReportRow): string {
  return row.score === null ? "—" : formatScore(row.score, locale.value);
}

function rowExposed(row: ReportRow): string {
  return row.exposed === null ? "—" : formatInteger(row.exposed, locale.value);
}

function printSheet(): void {
  window.print();
}

onMounted(() => {
  document.body.dataset.printSheet = props.variant;
});
onBeforeUnmount(() => {
  delete document.body.dataset.printSheet;
});
</script>

<template>
  <Teleport to="body">
    <div
      class="print-sheet theme-light"
      :class="`print-sheet--${variant}`"
      role="dialog"
      aria-modal="true"
      data-testid="print-sheet"
      :aria-label="variant === 'map' ? s.mapTitle : s.reportTitle"
    >
      <div class="sheet-toolbar no-print">
        <ElButton size="small" type="primary" @click="printSheet">
          {{ s.print }}
        </ElButton>
        <ElButton size="small" @click="emit('close')">{{ s.close }}</ElButton>
      </div>

      <div class="sheet-page">
        <header class="sheet-head keep-together">
          <h1>{{ variant === "map" ? s.mapTitle : s.reportTitle }}</h1>
          <dl class="meta">
            <div>
              <dt class="eoc-label">{{ t.community.mode.label }}</dt>
              <dd>
                <strong data-testid="sheet-mode">{{ model.modeLabel }}</strong>
                — {{ model.modeMeaning }}
              </dd>
            </div>
            <div v-if="model.event">
              <dt class="eoc-label">{{ t.community.event.pickerLabel }}</dt>
              <dd>
                <span v-if="model.event.magnitude !== null" class="eoc-numeric">
                  M{{ model.event.magnitude.toFixed(1) }}
                </span>
                {{ model.event.place }} ·
                <span class="eoc-numeric">{{ model.event.occurredLabel ?? "—" }}</span>
              </dd>
            </div>
            <div v-if="model.event">
              <dt class="eoc-label">{{ t.community.event.shakemapGrid }}</dt>
              <dd class="eoc-numeric">
                {{ model.event.shakemapLabel ?? t.community.event.shakemapPending }}
                <small>{{ t.community.event.shakemapRevised }}</small>
              </dd>
            </div>
            <div v-if="model.event">
              <dt class="eoc-label">{{ t.community.event.pager }}</dt>
              <dd class="eoc-numeric">
                {{ model.event.pagerLabel ?? t.community.event.pagerNone }}
                <small v-if="model.event.pagerLabel">{{ t.community.event.pagerIsRange }}</small>
              </dd>
            </div>
            <div>
              <dt class="eoc-label">{{ s.generatedAt }}</dt>
              <dd class="eoc-numeric">{{ model.generatedAtLabel }}</dd>
            </div>
          </dl>
        </header>

        <section class="legend keep-together" :aria-label="s.legend">
          <h2 class="eoc-label">{{ s.legend }}</h2>
          <ul>
            <li v-for="cls in model.classes" :key="cls.key">
              <ClassBadge :alert-class="cls.key" :mode="model.mode" />
              <span class="eoc-numeric range">{{ cls.floor }}–{{ cls.ceiling }}</span>
            </li>
          </ul>
        </section>

        <section class="limits keep-together" data-testid="sheet-limits">
          <ul>
            <li v-for="line in model.limitations" :key="line">{{ line }}</li>
          </ul>
        </section>

        <template v-if="variant === 'report'">
          <p class="muted">
            {{ fillMessage(s.topNote, { shown: reportRows.length, total: model.total }) }}
          </p>
          <table class="ranking">
            <thead>
              <tr>
                <th class="eoc-label">{{ s.columnRank }}</th>
                <th class="eoc-label">{{ s.columnDistrict }}</th>
                <th class="eoc-label">{{ s.columnClass }}</th>
                <th class="eoc-label num">{{ s.columnScore }}</th>
                <th v-if="isEvent" class="eoc-label num">{{ s.columnExposed }}</th>
                <th v-if="isEvent" class="eoc-label">{{ t.community.detail.sphereTitle }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in reportRows" :key="`${row.rank}-${row.name}`">
                <td class="eoc-numeric">{{ row.rank ?? "—" }}</td>
                <td>{{ row.name }}</td>
                <td>
                  <ClassBadge v-if="row.classKey" :alert-class="row.classKey" :mode="model.mode" />
                  <em v-else>{{ t.community.list.withheld }}</em>
                </td>
                <td class="eoc-numeric num">{{ rowScore(row) }}</td>
                <td v-if="isEvent" class="eoc-numeric num">{{ rowExposed(row) }}</td>
                <td v-if="isEvent" class="eoc-numeric small">{{ sphereText(row) }}</td>
              </tr>
            </tbody>
          </table>
        </template>

        <template v-else>
          <div class="map-layout">
            <PrintMap :event="model.event" />
            <aside class="map-side">
              <p class="muted">{{ s.noGeometry }}</p>
              <p v-if="!model.event" class="muted">{{ s.baselineMapNote }}</p>
              <h2 class="eoc-label">{{ s.priorityList }}</h2>
              <ol class="priority">
                <li v-for="row in priorityRows" :key="`${row.rank}-${row.name}`">
                  <span class="eoc-numeric rank">{{ row.rank }}</span>
                  <span class="name">{{ row.name }}</span>
                  <ClassBadge v-if="row.classKey" :alert-class="row.classKey" :mode="model.mode" />
                  <span class="eoc-numeric">{{ rowScore(row) }}</span>
                </li>
              </ol>
            </aside>
          </div>
        </template>

        <footer class="sheet-footer">
          {{ model.modeLabel }} · {{ s.generatedAt }} {{ model.generatedAtLabel }} ·
          {{ t.community.honesty.attributionLabel }}: {{ model.attribution }}
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
h1 {
  margin: 0 0 var(--eoc-gap-y);
  font-size: var(--eoc-fs-heading);
}
h2 {
  margin: 0 0 var(--eoc-gap-x);
}
.meta {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--eoc-gap-y) var(--eoc-pad-panel);
}
.meta dt {
  margin: 0;
}
.meta dd {
  margin: 0;
}
.meta small {
  display: block;
  color: var(--eoc-text-muted);
  font-size: var(--eoc-fs-micro);
}
.legend,
.limits {
  margin-top: var(--eoc-pad-panel);
}
.legend ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  gap: var(--eoc-pad-panel);
  flex-wrap: wrap;
}
.legend li {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
}
.range {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
.limits {
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
}
.limits ul {
  margin: 0;
  padding-left: 14px;
  font-size: var(--eoc-fs-micro);
  line-height: 1.4;
}
.muted {
  color: var(--eoc-text-secondary);
  font-size: var(--eoc-fs-micro);
}
.ranking {
  width: 100%;
  border-collapse: collapse;
}
.ranking th,
.ranking td {
  text-align: left;
  padding: 2px var(--eoc-gap-x);
  border-bottom: var(--eoc-border-width) solid var(--eoc-border);
  font-size: var(--eoc-fs-body);
}
.ranking .num {
  text-align: right;
}
.ranking .small {
  font-size: var(--eoc-fs-micro);
}
.map-layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--eoc-pad-panel);
  height: 150mm;
  margin-top: var(--eoc-pad-panel);
}
.map-side {
  overflow: hidden;
}
.priority {
  list-style: none;
  margin: 0;
  padding: 0;
}
.priority li {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) auto 32px;
  gap: var(--eoc-gap-x);
  align-items: center;
  padding: 2px 0;
  border-bottom: var(--eoc-border-width) solid var(--eoc-border);
  font-size: var(--eoc-fs-micro);
}
.priority .name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sheet-footer {
  margin-top: var(--eoc-pad-panel);
  padding-top: var(--eoc-gap-y);
  border-top: var(--eoc-border-width) solid var(--eoc-border);
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
</style>
