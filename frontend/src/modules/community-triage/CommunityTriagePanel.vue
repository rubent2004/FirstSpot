<script setup lang="ts">
import { computed, nextTick, onMounted, ref, toRef, watch } from "vue";
import { useCommunityTriageStore } from "../../stores/useCommunityTriageStore";
import { fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";
import ExportMenu from "./ExportMenu.vue";
import DistrictDetail from "./DistrictDetail.vue";
import DistrictRankList from "./DistrictRankList.vue";
import PrintSheet, { type SheetVariant } from "./PrintSheet.vue";
import TriageBreadcrumb from "./TriageBreadcrumb.vue";
import TriageModeBar from "./TriageModeBar.vue";
import { departmentPrefix } from "./departments";
import { buildReportModel, type ReportModel } from "./exportModel";
import { downloadRankingXlsx } from "./exportXlsx";
import { resolveMode } from "./triageModel";
import { useDistrictFilters } from "./useDistrictFilters";

export type TriageLevel = "list" | "places";

const props = defineProps<{
  /** Name of the current predefined work zone; null for a custom area. */
  zoneName?: string | null;
  /** That zone's department, used to scope the list when it can be resolved. */
  zoneDepartment?: string | null;
}>();
const emit = defineEmits<{
  (e: "level-change", level: TriageLevel): void;
  (e: "detail-change", open: boolean): void;
}>();

const store = useCommunityTriageStore();
const { t, locale } = useI18n();

onMounted(() => {
  if (!store.index && !store.isLoading) void store.initialize();
});

const mode = computed(() => resolveMode(store.index?.mode, store.requestedEventId));
const prefix = computed(() => departmentPrefix(props.zoneDepartment));
const filters = useDistrictFilters(
  toRef(store, "districts"),
  prefix,
  mode,
  locale,
);

// ---- Hierarchy: districts (overview) -> district (detail) -> zone places ----
const placesOpen = ref(false);
const level = computed<TriageLevel>(() => (placesOpen.value ? "places" : "list"));
const detailOpen = computed(() => store.selectedDistrict !== null);
watch(level, (value) => emit("level-change", value), { immediate: true });
watch(detailOpen, (value) => emit("detail-change", value), { immediate: true });

const announcement = ref("");
const listRef = ref<InstanceType<typeof DistrictRankList> | null>(null);
const detailRef = ref<InstanceType<typeof DistrictDetail> | null>(null);
const placesHeading = ref<HTMLElement | null>(null);
/** The district that was open, so focus can return to its row. */
let lastOpenedCode: string | null = null;

const placesLabel = computed(() =>
  props.zoneName
    ? fillMessage(t.value.community.nav.placesIn, { zone: props.zoneName })
    : t.value.community.nav.places,
);
const openPlacesLabel = computed(() =>
  props.zoneName
    ? fillMessage(t.value.community.nav.openZonePlaces, { zone: props.zoneName })
    : t.value.community.nav.places,
);

async function openDistrict(code: string): Promise<void> {
  lastOpenedCode = code;
  const pending = store.selectDistrict(code);
  const name = store.selectedDistrict?.district_name ?? "";
  announcement.value = fillMessage(t.value.community.nav.announceDetail, { name });
  await nextTick();
  detailRef.value?.focusHeading();
  await pending;
}

/** Close the detail panel and put focus back on the row that opened it. */
async function closeDetail(): Promise<void> {
  void store.selectDistrict(null);
  announcement.value = t.value.community.nav.announceList;
  await nextTick();
  if (lastOpenedCode) listRef.value?.focusRow(lastOpenedCode);
}

async function backToList(): Promise<void> {
  placesOpen.value = false;
  announcement.value = t.value.community.nav.announceList;
  await nextTick();
  if (lastOpenedCode) listRef.value?.focusRow(lastOpenedCode);
}

async function openPlaces(): Promise<void> {
  placesOpen.value = true;
  void store.selectDistrict(null);
  announcement.value = fillMessage(t.value.community.nav.announcePlaces, {
    zone: props.zoneName ?? "",
  });
  await nextTick();
  placesHeading.value?.focus();
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== "Escape" || event.defaultPrevented) return;
  if (detailOpen.value) void closeDetail();
  else if (level.value === "places") void backToList();
}

// ---- Exports (read what is loaded; no request is made) ----
const sheet = ref<{ variant: SheetVariant; model: ReportModel } | null>(null);
const isExporting = ref(false);
const exportError = ref<string | null>(null);

function currentModel(): ReportModel | null {
  return store.index
    ? buildReportModel(store.index, t.value.community, locale.value)
    : null;
}

function openSheet(variant: SheetVariant): void {
  const model = currentModel();
  if (model) sheet.value = { variant, model };
}

async function exportExcel(): Promise<void> {
  const model = currentModel();
  if (!model) return;
  isExporting.value = true;
  exportError.value = null;
  try {
    await downloadRankingXlsx(model, t.value.community, locale.value);
  } catch {
    exportError.value = t.value.community.exports.excelFailed;
  } finally {
    isExporting.value = false;
  }
}

const crumbParent = computed(() => t.value.community.nav.districts);

</script>

<template>
  <div class="triage-shell" :data-level="level" @keydown="onKeydown">
    <section class="triage-panel">
      <header class="head">
        <h2 class="title">{{ t.community.nav.label }}</h2>
      </header>

      <TriageBreadcrumb
        v-if="level === 'places'"
        :parent="crumbParent"
        :current="placesLabel"
        @navigate-parent="backToList"
      />

      <TriageModeBar
        :index="store.index"
        :requested-event-id="store.requestedEventId"
        :events="store.events"
        :is-loading-events="store.isLoadingEvents"
        :events-error="store.eventsError"
        @select-event="store.selectEvent"
      />

      <p class="sr-only" role="status" aria-live="polite" data-testid="announcer">{{ announcement }}</p>

      <template v-if="level === 'list'">
        <ExportMenu
          :disabled="!store.index"
          :is-busy="isExporting"
          :error="exportError"
          @excel="exportExcel"
          @report="openSheet('report')"
          @map="openSheet('map')"
        />
        <DistrictRankList
          ref="listRef"
          v-model:search="filters.search.value"
          v-model:reveal-limit="filters.revealLimit.value"
          :shown="filters.shown.value"
          :counts="filters.counts.value"
          :national-total="store.districts.length"
          :selected-code="store.selectedCode ?? null"
          :is-loading="store.isLoading"
          :error="store.error"
          :mode="mode"
          :class-filter="filters.classFilter.value"
          :sort="filters.effectiveSort.value"
          :scope-available="filters.scopeAvailable.value"
          :department="zoneDepartment ?? null"
          :scope="filters.effectiveScope.value"
          @select="openDistrict"
          @retry="store.loadIndex"
          @update:class-filter="filters.setClass"
          @clear-filters="filters.clearFilters"
          @update:scope="(v) => { filters.scope.value = v; filters.resetReveal(); }"
          @update:sort="(v) => { filters.sort.value = v; filters.resetReveal(); }"
        />
        <button type="button" class="places-link" @click="openPlaces">{{ openPlacesLabel }}</button>
      </template>

      <section v-else class="places">
        <h3 ref="placesHeading" class="places-title" tabindex="-1">{{ placesLabel }}</h3>
        <slot name="places"></slot>
      </section>
    </section>

    <!-- One district at a time, beside the list and the map, closed until asked for -->
    <aside
      v-if="store.selectedDistrict"
      class="detail-panel"
      data-testid="detail-aside"
      :aria-label="store.selectedDistrict.district_name"
    >
      <DistrictDetail
        ref="detailRef"
        :district="store.selectedDistrict"
        :audit="store.audit"
        :audit-loading="store.isLoadingAudit"
        :audit-error="store.auditError"
        :total="store.districts.length"
        :mode="mode"
        :zone-name="zoneName ?? null"
        @open-places="openPlaces"
        @close="closeDetail"
      />
    </aside>

    <PrintSheet
      v-if="sheet"
      :model="sheet.model"
      :variant="sheet.variant"
      @close="sheet = null"
    />
  </div>
</template>

<style scoped>
/* The shell adds no box: its two children sit directly in the workspace grid */
.triage-shell {
  display: contents;
}
.triage-panel {
  grid-area: queue;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  min-width: 0;
  box-sizing: border-box;
  background: var(--eoc-bg-panel);
  border-left: var(--eoc-border-width) solid var(--eoc-border);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
  gap: var(--eoc-gap-y);
  overflow-y: auto;
}
.head {
  display: flex;
  align-items: baseline;
  gap: var(--eoc-gap-x);
}
.title {
  margin: 0;
  font-size: var(--eoc-fs-title);
  font-weight: var(--eoc-fw-semibold);
}
.places {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  gap: var(--eoc-gap-y);
}
.places-title {
  margin: 0;
  font-size: var(--eoc-fs-title);
  font-weight: var(--eoc-fw-semibold);
}
.places > :deep(*:not(.places-title)) {
  flex: 1;
  min-height: 0;
}
.places-link {
  align-self: flex-start;
  min-height: var(--eoc-target-min);
  padding: 0 var(--eoc-gap-x);
  background: transparent;
  border: 0;
  color: var(--eoc-accent-text);
  font: inherit;
  font-size: var(--eoc-fs-body);
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
}
.detail-panel {
  grid-area: detail;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
  background: var(--eoc-bg-panel);
  border-left: var(--eoc-border-width) solid var(--eoc-border);
  overflow: hidden;
}
/* Narrow screens: the detail floats over the map from the right, full width on phones */
@media (max-width: 1100px) {
  .detail-panel {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    z-index: 1000;
    width: min(380px, 100vw);
    border-left: var(--eoc-border-width) solid var(--eoc-border-strong);
    box-shadow: var(--eoc-shadow-dialog);
  }
}
@media (max-width: 700px) {
  .detail-panel {
    width: 100vw;
    border-left: 0;
  }
  .triage-panel {
    height: auto;
    min-height: 100%;
  }
}
</style>
