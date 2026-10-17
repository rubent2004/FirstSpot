<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useCommunityTriageStore } from "../../stores/useCommunityTriageStore";
import { useI18n } from "../../i18n/useI18n";
import DistrictDetail from "./DistrictDetail.vue";
import DistrictRankList from "./DistrictRankList.vue";
import HonestyNotice from "./HonestyNotice.vue";
import TriageModeBar from "./TriageModeBar.vue";
import { resolveMode } from "./triageModel";

const store = useCommunityTriageStore();
const { t } = useI18n();

onMounted(() => {
  if (!store.index && !store.isLoading) void store.initialize();
});

const mode = computed(() => resolveMode(store.index?.mode, store.requestedEventId));
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
