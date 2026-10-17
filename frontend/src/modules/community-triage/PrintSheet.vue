<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from "vue";
import { ElButton } from "element-plus";
import { communityMessages, fillMessage } from "../../i18n/communityMessages";
import type { AppLocale } from "../../i18n/useI18n";
import ClassBadge from "./ClassBadge.vue";
import type { ReportModel, ReportRow } from "./exportModel";
import { resolveColumns, type ExportColumn, type Orientation, type PaperSize } from "./exportPlan";
import { formatInteger, formatScore } from "./formatters";
import PrintMap from "./PrintMap.vue";
import "./print.css";

export type SheetVariant = "report" | "map";

const props = withDefaults(
  defineProps<{
    model: ReportModel;
    variant: SheetVariant;
    /** Document language: independent of the language the console is shown in. */
    lang?: AppLocale;
    paper?: PaperSize;
    orientation?: Orientation;
    columns?: readonly ExportColumn[];
    /** Becomes the document title, which browsers offer as the PDF file name. */
    fileName?: string;
  }>(),
  { lang: "es", paper: "a4", orientation: "portrait", columns: undefined, fileName: undefined },
);
const emit = defineEmits<{ (e: "close"): void }>();

const m = computed(() => communityMessages(props.lang));
const locale = computed(() => props.lang);
const s = computed(() => m.value.sheet);
const shown = computed(() => resolveColumns(props.columns ?? [], props.model.mode));
const has = (column: ExportColumn): boolean =>
  props.columns === undefined || shown.value.includes(column);

const reportRows = computed(() => props.model.rows);
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
  if (row.withheld) return "—";
  return row.exposed === null ? m.value.list.exposedNone : formatInteger(row.exposed, locale.value);
}

function printSheet(): void {
  window.print();
}

/** Paper and orientation are chosen per print, so @page is written when the sheet opens. */
const PAPER_MM: Record<PaperSize, { width: number; height: number }> = {
  a4: { width: 210, height: 297 },
  letter: { width: 216, height: 279 },
};
const pageWidthMm = computed(() => {
  const { width, height } = PAPER_MM[props.paper];
  return props.orientation === "landscape" ? height : width;
});

let pageStyle: HTMLStyleElement | null = null;
let previousTitle = "";

onMounted(() => {
  document.body.dataset.printSheet = props.variant;
  pageStyle = document.createElement("style");
  pageStyle.dataset.printPage = "";
  pageStyle.textContent = `@page { size: ${props.paper === "a4" ? "A4" : "letter"} ${props.orientation}; margin: 8mm; }`;
  document.head.appendChild(pageStyle);
  previousTitle = document.title;
  if (props.fileName) document.title = props.fileName.replace(/\.pdf$/, "");
});
onBeforeUnmount(() => {
  delete document.body.dataset.printSheet;
  pageStyle?.remove();
  document.title = previousTitle;
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
      :lang="lang"
      :style="{ '--sheet-width': `${pageWidthMm}mm` }"
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
              <dt class="eoc-label">{{ m.mode.label }}</dt>
              <dd>
                <strong data-testid="sheet-mode">{{ model.modeLabel }}</strong>
                — {{ model.modeMeaning }}
              </dd>
            </div>
            <div v-if="model.event">
              <dt class="eoc-label">{{ m.event.pickerLabel }}</dt>
              <dd>
                <span v-if="model.event.magnitude !== null" class="eoc-numeric">
                  M{{ model.event.magnitude.toFixed(1) }}
                </span>
                {{ model.event.place }} ·
                <span class="eoc-numeric">{{ model.event.occurredLabel ?? "—" }}</span>
              </dd>
            </div>
            <div v-if="model.event">
              <dt class="eoc-label">{{ m.event.shakemapGrid }}</dt>
              <dd class="eoc-numeric">
                {{ model.event.shakemapLabel ?? m.event.shakemapPending }}
                <small>{{ m.event.shakemapRevised }}</small>
              </dd>
            </div>
            <div v-if="model.event">
              <dt class="eoc-label">{{ m.event.pager }}</dt>
              <dd class="eoc-numeric">
                {{ model.event.pagerLabel ?? m.event.pagerNone }}
                <small v-if="model.event.pagerLabel">{{ m.event.pagerIsRange }}</small>
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
          <p v-if="model.scopeNote" class="muted" data-testid="sheet-scope">{{ model.scopeNote }}</p>
          <table class="ranking">
            <thead>
              <tr>
                <th v-if="has('rank')" class="eoc-label">{{ s.columnRank }}</th>
                <th class="eoc-label">{{ s.columnDistrict }}</th>
                <th v-if="has('department')" class="eoc-label">{{ m.xlsx.department }}</th>
                <th v-if="has('class')" class="eoc-label">{{ s.columnClass }}</th>
                <th v-if="has('prio')" class="eoc-label num">{{ s.columnScore }}</th>
                <template v-if="has('dimensions')">
                  <th v-for="key in model.dimensionKeys" :key="key" class="eoc-label num">
                    {{ m.dimensions[key].abbr }}
                  </th>
                </template>
                <th v-if="has('population')" class="eoc-label num">{{ m.xlsx.population }}</th>
                <th v-if="isEvent && has('exposed')" class="eoc-label num">{{ s.columnExposed }}</th>
                <th v-if="isEvent && has('sphere')" class="eoc-label">{{ m.detail.sphereTitle }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in reportRows" :key="`${row.rank}-${row.name}`">
                <td v-if="has('rank')" class="eoc-numeric">{{ row.rank ?? "—" }}</td>
                <td>{{ row.name }}</td>
                <td v-if="has('department')">{{ row.department ?? "" }}</td>
                <td v-if="has('class')">
                  <ClassBadge v-if="row.classKey" :alert-class="row.classKey" :mode="model.mode" />
                  <em v-else>{{ m.list.withheld }}</em>
                </td>
                <td v-if="has('prio')" class="eoc-numeric num">{{ rowScore(row) }}</td>
                <template v-if="has('dimensions')">
                  <td v-for="d in row.dimensions" :key="d.key" class="eoc-numeric num">
                    {{ d.score === null ? "—" : formatScore(d.score, locale) }}
                  </td>
                </template>
                <td v-if="has('population')" class="eoc-numeric num">
                  {{ row.population === null ? "—" : formatInteger(row.population, locale) }}
                </td>
                <td v-if="isEvent && has('exposed')" class="eoc-numeric num">{{ rowExposed(row) }}</td>
                <td v-if="isEvent && has('sphere')" class="eoc-numeric small">{{ sphereText(row) }}</td>
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
          {{ m.honesty.attributionLabel }}: {{ model.attribution }}
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
