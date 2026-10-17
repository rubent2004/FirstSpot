<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useCommunityTriageStore } from "../../stores/useCommunityTriageStore";
import { useI18n } from "../../i18n/useI18n";
import ExportMenu from "./ExportMenu.vue";
import DistrictDetail from "./DistrictDetail.vue";
import DistrictRankList from "./DistrictRankList.vue";
import HonestyNotice from "./HonestyNotice.vue";
import PrintSheet, { type SheetVariant } from "./PrintSheet.vue";
import { buildReportModel, type ReportModel } from "./exportModel";
import { downloadRankingXlsx } from "./exportXlsx";
import TriageModeBar from "./TriageModeBar.vue";
import { resolveMode } from "./triageModel";

const store = useCommunityTriageStore();
const { t, locale } = useI18n();

onMounted(() => {
  if (!store.index && !store.isLoading) void store.initialize();
});

const mode = computed(() => resolveMode(store.index?.mode, store.requestedEventId));
const sheet = ref<{ variant: SheetVariant; model: ReportModel } | null>(null);
const isExporting = ref(false);
const exportError = ref<string | null>(null);

/**
 * Exports read only what is already loaded: no request is made here, so they
 * work offline. Each one stamps its own generation time.
 */
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

const showExposed = computed(() => mode.value === "event");
</script>

<template>
  <section class="triage-panel">
    <header class="head">
      <h2 class="title">{{ t.community.title }}</h2>
      <span class="eoc-numeric count">{{ store.districts.length }} {{ t.community.list.districts }}</span>
    </header>

    <TriageModeBar
      :index="store.index"
      :requested-event-id="store.requestedEventId"
      :events="store.events"
      :is-loading-events="store.isLoadingEvents"
      :events-error="store.eventsError"
      @select-event="store.selectEvent"
    />

    <HonestyNotice :district-count="store.districts.length" />

    <ExportMenu
      :disabled="!store.index"
      :is-busy="isExporting"
      :error="exportError"
      @excel="exportExcel"
      @report="openSheet('report')"
      @map="openSheet('map')"
    />

    <DistrictDetail
      v-if="store.selectedDistrict"
      :district="store.selectedDistrict"
      :audit="store.audit"
      :audit-loading="store.isLoadingAudit"
      :audit-error="store.auditError"
      :total="store.districts.length"
      :mode="mode"
      @back="store.selectDistrict(null)"
    />
    <DistrictRankList
      v-else
      :districts="store.districts"
      :selected-code="store.selectedCode"
      :is-loading="store.isLoading"
      :error="store.error"
      :show-exposed="showExposed"
      @select="store.selectDistrict"
      @retry="store.loadIndex"
    />

    <PrintSheet
      v-if="sheet"
      :model="sheet.model"
      :variant="sheet.variant"
      @close="sheet = null"
    />
  </section>
</template>

<style scoped>
.triage-panel {
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
.count {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
</style>
