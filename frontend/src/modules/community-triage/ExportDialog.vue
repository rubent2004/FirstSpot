<script setup lang="ts">
import { computed, ref, useId, watch } from "vue";
import { ElButton, ElDialog } from "element-plus";
import { Document, Grid, MapLocation, Printer } from "@element-plus/icons-vue";
import { fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";
import type { ReportRow } from "./exportModel";
import {
  buildFileName,
  columnsFor,
  resolveColumns,
  resolveScope,
  scopeCounts,
  type ExportColumn,
  type ExportFormat,
  type ExportPrefs,
  type ExportScope,
  type ScopeContext,
} from "./exportPlan";
import type { TriageMode } from "./triageModel";

const props = defineProps<{
  modelValue: boolean;
  prefs: ExportPrefs;
  mode: TriageMode;
  rows: ReportRow[];
  scopeContext: ScopeContext;
  selectedName: string | null;
  eventId: string | null;
  zoneName: string | null;
  isBusy: boolean;
  error: string | null;
  now: Date;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "submit", request: { prefs: ExportPrefs; scope: ExportScope }): void;
}>();

const { t } = useI18n();
const d = computed(() => t.value.community.exportDialog);
const uid = useId();

const draft = ref<ExportPrefs>({ ...props.prefs, columns: [...props.prefs.columns] });
const scope = ref<ExportScope>("all");

const FORMAT_ORDER: ExportFormat[] = ["xlsx", "csv", "report", "map"];
const FORMAT_ICON = { xlsx: Grid, csv: Document, report: Printer, map: MapLocation } as const;

/** The scope that fits the moment: the open district, else what is filtered, else all. */
function defaultScope(): ExportScope {
  if (props.scopeContext.selectedCode !== null) return "selected";
  return props.scopeContext.filteredCodes ? "filtered" : "all";
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    draft.value = { ...props.prefs, columns: [...props.prefs.columns] };
    scope.value = defaultScope();
  },
  { immediate: true },
);

const isMap = computed(() => draft.value.format === "map");
const isPrint = computed(() => draft.value.format === "map" || draft.value.format === "report");
const isFile = computed(() => draft.value.format === "xlsx" || draft.value.format === "csv");

const counts = computed(() =>
  scopeCounts(props.rows, props.scopeContext, draft.value.topN),
);
const effectiveScope = computed(() => resolveScope(scope.value, props.scopeContext));

interface ScopeOption {
  value: ExportScope;
  label: string;
  count: number;
  disabledReason: string | null;
}
const scopeOptions = computed<ScopeOption[]>(() => [
  {
    value: "filtered",
    label: d.value.scopes.filtered,
    count: counts.value.filtered,
    disabledReason: props.scopeContext.filteredCodes ? null : d.value.noFilter,
  },
  {
    value: "selected",
    label: fillMessage(d.value.scopes.selected, { name: props.selectedName ?? "" }),
    count: counts.value.selected,
    disabledReason: props.scopeContext.selectedCode !== null ? null : d.value.noSelection,
  },
  { value: "all", label: d.value.scopes.all, count: counts.value.all, disabledReason: null },
]);

const rowCount = computed(() => counts.value[effectiveScope.value]);
const hasNoRows = computed(() => !isMap.value && rowCount.value === 0);

const fileName = computed(() =>
  buildFileName({
    mode: props.mode,
    eventId: props.eventId,
    lang: draft.value.lang,
    format: draft.value.format,
    scope: isMap.value ? "all" : effectiveScope.value,
    topN: isMap.value ? null : draft.value.topN,
    districtName: props.selectedName,
    now: props.now,
  }),
);

const columnChoices = computed(() => columnsFor(props.mode));
function toggleColumn(column: ExportColumn, checked: boolean): void {
  const next = new Set(draft.value.columns);
  if (checked) next.add(column);
  else next.delete(column);
  draft.value.columns = resolveColumns([...next], props.mode);
}
const isColumnOn = (column: ExportColumn): boolean =>
  resolveColumns(draft.value.columns, props.mode).includes(column);

const topNEnabled = computed({
  get: () => draft.value.topN !== null,
  set: (on: boolean) => {
    draft.value.topN = on ? (draft.value.topN ?? 20) : null;
  },
});
function onTopN(event: Event): void {
  const n = Math.floor(Number((event.target as HTMLInputElement).value));
  draft.value.topN = Number.isFinite(n) && n > 0 ? n : 1;
}

const submitLabel = computed(() =>
  props.isBusy ? d.value.busy : props.error ? d.value.retry : d.value.submit,
);

function submit(): void {
  if (hasNoRows.value || props.isBusy) return;
  emit("submit", {
    prefs: { ...draft.value, columns: resolveColumns(draft.value.columns, props.mode) },
    scope: effectiveScope.value,
  });
}

const reasonId = (key: string) => `${uid}-${key}`;
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    :title="d.title"
    width="min(520px, 96vw)"
    align-center
    append-to-body
    class="export-dialog"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <form class="form" novalidate @submit.prevent="submit">
      <fieldset class="field">
        <legend class="eoc-label">{{ d.formatLegend }}</legend>
        <div class="cards">
          <label
            v-for="format in FORMAT_ORDER"
            :key="format"
            class="card"
            :class="{ checked: draft.format === format }"
          >
            <input v-model="draft.format" class="sr-only" type="radio" name="export-format" :value="format" />
            <component :is="FORMAT_ICON[format]" class="icon" aria-hidden="true" />
            <span class="card-text">
              <span class="card-head">
                <strong>{{ d.formats[format].name }}</strong>
                <span class="type eoc-numeric">{{ d.formats[format].type }}</span>
              </span>
              <span class="purpose">{{ d.formats[format].purpose }}</span>
            </span>
          </label>
        </div>
      </fieldset>

      <fieldset v-if="!isMap" class="field">
        <legend class="eoc-label">{{ d.scopeLegend }}</legend>
        <div class="scopes">
          <label
            v-for="option in scopeOptions"
            :key="option.value"
            class="scope"
            :class="{ disabled: option.disabledReason }"
          >
            <input
              v-model="scope"
              type="radio"
              name="export-scope"
              :value="option.value"
              :disabled="option.disabledReason !== null"
              :aria-describedby="option.disabledReason ? reasonId(`scope-${option.value}`) : undefined"
            />
            <span class="scope-label">{{ option.label }}</span>
            <span class="count eoc-numeric">{{ fillMessage(d.rows, { n: option.count }) }}</span>
            <span
              v-if="option.disabledReason"
              :id="reasonId(`scope-${option.value}`)"
              class="reason"
            >{{ option.disabledReason }}</span>
          </label>
        </div>
      </fieldset>
      <p v-else class="map-line">
        {{ zoneName ? fillMessage(d.mapScopeLine, { zone: zoneName }) : d.mapScopeLineNoZone }}
      </p>

      <details class="more">
        <summary>{{ d.more }}</summary>
        <div class="more-body">
          <fieldset v-if="!isMap" class="sub">
            <legend class="eoc-label">{{ d.columnsLegend }}</legend>
            <div class="checks">
              <label v-for="column in columnChoices" :key="column" class="check">
                <input
                  type="checkbox"
                  name="export-column"
                  :checked="isColumnOn(column)"
                  :disabled="column === 'district'"
                  @change="toggleColumn(column, ($event.target as HTMLInputElement).checked)"
                />
                <span>
                  {{ d.columns[column] }}
                  <small v-if="column === 'district'">({{ d.columnRequired }})</small>
                </span>
              </label>
            </div>
          </fieldset>

          <label v-if="isFile" class="check">
            <input v-model="draft.includeContext" type="checkbox" />
            <span>{{ d.includeContext }}</span>
          </label>

          <div v-if="!isMap" class="topn">
            <label class="check">
              <input v-model="topNEnabled" type="checkbox" />
              <span>{{ d.topNLabel }}</span>
            </label>
            <input
              v-if="topNEnabled"
              class="number eoc-numeric"
              type="number"
              min="1"
              :value="draft.topN ?? 20"
              :aria-label="d.topNLabel"
              @input="onTopN"
            />
            <span v-if="topNEnabled">{{ d.topNUnit }}</span>
          </div>

          <fieldset class="sub inline">
            <legend class="eoc-label">{{ d.language }}</legend>
            <label v-for="lang in (['es', 'en'] as const)" :key="lang" class="check">
              <input v-model="draft.lang" type="radio" name="export-lang" :value="lang" />
              <span>{{ d.languageNames[lang] }}</span>
            </label>
          </fieldset>

          <template v-if="isPrint">
            <fieldset class="sub inline">
              <legend class="eoc-label">{{ d.paper }}</legend>
              <label v-for="paper in (['a4', 'letter'] as const)" :key="paper" class="check">
                <input v-model="draft.paper" type="radio" name="export-paper" :value="paper" />
                <span>{{ d.paperNames[paper] }}</span>
              </label>
            </fieldset>
            <fieldset class="sub inline">
              <legend class="eoc-label">{{ d.orientation }}</legend>
              <label v-for="o in (['portrait', 'landscape'] as const)" :key="o" class="check">
                <input v-model="draft.orientation" type="radio" name="export-orientation" :value="o" />
                <span>{{ d.orientationNames[o] }}</span>
              </label>
            </fieldset>
          </template>
        </div>
      </details>

      <p class="always">{{ d.alwaysIncluded }}</p>

      <div class="actions">
        <p class="file">
          <span class="eoc-label">{{ d.fileLabel }}</span>
          <code class="name eoc-numeric" data-testid="export-filename">{{ fileName }}</code>
        </p>
        <p v-if="error" class="failure" role="alert">{{ error }}</p>
        <p v-if="hasNoRows" :id="reasonId('norows')" class="failure">{{ d.noRows }}</p>
        <div class="buttons">
          <ElButton native-type="button" @click="emit('update:modelValue', false)">
            {{ d.cancel }}
          </ElButton>
          <ElButton
            type="primary"
            native-type="submit"
            class="primary"
            :loading="isBusy"
            :disabled="hasNoRows"
            :aria-describedby="hasNoRows ? reasonId('norows') : undefined"
          >
            {{ submitLabel }}
          </ElButton>
        </div>
      </div>
    </form>
  </ElDialog>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-pad-panel);
}
fieldset {
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}
legend {
  padding: 0;
  margin-bottom: var(--eoc-gap-y);
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: var(--eoc-gap-x);
}
.card {
  display: flex;
  gap: var(--eoc-gap-x);
  align-items: flex-start;
  min-height: var(--eoc-target-primary);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  border-radius: var(--eoc-radius-control);
  cursor: pointer;
}
.card:hover {
  background: var(--eoc-bg-hover);
}
.card.checked {
  border-color: var(--eoc-accent);
  background: var(--eoc-bg-selected);
}
/* The visually hidden radio still takes focus; show it on the card */
.card:focus-within,
.scope:focus-within,
.check:focus-within {
  outline: 2px solid var(--eoc-border-focus);
  outline-offset: 2px;
  border-radius: var(--eoc-radius-control);
}
.icon {
  flex: none;
  width: 18px;
  height: 18px;
  color: var(--eoc-icon);
  margin-top: 2px;
}
.card-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.card-head {
  display: flex;
  gap: var(--eoc-gap-x);
  align-items: baseline;
}
.type {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
.purpose {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
  line-height: 1.35;
}
.scopes {
  display: flex;
  flex-direction: column;
}
.scope {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--eoc-gap-x);
  min-height: var(--eoc-target-min);
  padding: 2px 0;
  cursor: pointer;
}
.scope.disabled {
  cursor: not-allowed;
}
.scope-label {
  flex: 1;
}
.count {
  color: var(--eoc-text-secondary);
  font-size: var(--eoc-fs-micro);
}
.reason {
  flex-basis: 100%;
  padding-left: 22px;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
.map-line {
  margin: 0;
  color: var(--eoc-text-secondary);
}
.more > summary {
  display: flex;
  align-items: center;
  min-height: var(--eoc-target-min);
  cursor: pointer;
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-accent-text);
}
.more-body {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
  padding: var(--eoc-gap-y) 0 0;
}
.checks {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}
.check {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  min-height: var(--eoc-target-min);
}
.sub.inline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--eoc-gap-x) var(--eoc-pad-panel);
}
.sub.inline legend {
  float: left;
  margin: 0 var(--eoc-pad-panel) 0 0;
}
.topn {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}
.number {
  width: 72px;
  min-height: var(--eoc-target-min);
  padding: 0 var(--eoc-gap-x);
  background: var(--eoc-bg-sunken);
  color: var(--eoc-text-primary);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  border-radius: var(--eoc-radius-control);
  font: inherit;
}
.always {
  margin: 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
.actions {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
  padding-top: var(--eoc-pad-panel);
  border-top: var(--eoc-border-width) solid var(--eoc-border);
}
.file {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.name {
  overflow-wrap: anywhere;
  font-family: var(--eoc-font-mono);
  font-size: var(--eoc-fs-body);
}
.failure {
  margin: 0;
  padding-left: var(--eoc-gap-x);
  border-left: 3px solid var(--eoc-critical);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--eoc-gap-x);
}
.primary {
  min-height: 32px;
  min-width: 96px;
}
@media (pointer: coarse) {
  .primary,
  .buttons :deep(.el-button) {
    min-height: var(--eoc-target-primary);
  }
}
</style>
