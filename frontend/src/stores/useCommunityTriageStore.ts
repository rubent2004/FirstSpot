import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  apiClient,
  type DistrictPrioRead,
  type EventSummaryRead,
  type PrioIndexAuditRead,
  type PrioIndexRead,
} from "../api/client";

/** Recent earthquakes offered in the event picker. */
const EVENT_PICKER_LIMIT = 30;

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * District-level prioritization: the ranked territories, the mode they were
 * ranked in, and the district the operator is inspecting.
 *
 * The mode is a request parameter (`requestedEventId`) AND a property of the
 * response (`index.mode`). The UI shows the response's, never the request's,
 * so a half-finished switch can not label old numbers with a new mode.
 */
export const useCommunityTriageStore = defineStore("communityTriage", () => {
  /** Null requests BASELINE mode; a USGS event id requests EVENT mode. */
  const requestedEventId = ref<string | null>(null);
  const index = ref<PrioIndexRead | null>(null);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  const events = ref<EventSummaryRead[]>([]);
  const isLoadingEvents = ref(false);
  const eventsError = ref<string | null>(null);

  const selectedCode = ref<string | null>(null);
  const audit = ref<PrioIndexAuditRead | null>(null);
  const isLoadingAudit = ref(false);
  const auditError = ref<string | null>(null);

  let latestIndexRequest = 0;
  let latestAuditRequest = 0;

  const districts = computed<DistrictPrioRead[]>(() => index.value?.districts ?? []);
  const selectedDistrict = computed<DistrictPrioRead | null>(
    () => districts.value.find((d) => d.district_code === selectedCode.value) ?? null,
  );

  async function loadIndex(): Promise<void> {
    const requestId = ++latestIndexRequest;
    isLoading.value = true;
    error.value = null;
    try {
      const response = await apiClient.getPrioIndex(requestedEventId.value);
      if (requestId !== latestIndexRequest) return;
      index.value = response;
    } catch (caught) {
      if (requestId !== latestIndexRequest) return;
      error.value = messageOf(caught);
    } finally {
      if (requestId === latestIndexRequest) isLoading.value = false;
    }
  }

  async function loadEvents(): Promise<void> {
    isLoadingEvents.value = true;
    eventsError.value = null;
    try {
      const catalogue = await apiClient.listHazardEvents({ limit: EVENT_PICKER_LIMIT });
      events.value = catalogue.events;
    } catch (caught) {
      eventsError.value = messageOf(caught);
    } finally {
      isLoadingEvents.value = false;
    }
  }

  /** Switch mode. A null event id returns to BASELINE. */
  async function selectEvent(eventId: string | null): Promise<void> {
    requestedEventId.value = eventId;
    audit.value = null;
    await loadIndex();
    if (selectedCode.value) await loadAudit(selectedCode.value);
  }

  async function loadAudit(code: string): Promise<void> {
    const requestId = ++latestAuditRequest;
    isLoadingAudit.value = true;
    auditError.value = null;
    try {
      const response = await apiClient.getPrioAudit(code, requestedEventId.value);
      if (requestId !== latestAuditRequest) return;
      audit.value = response;
    } catch (caught) {
      if (requestId !== latestAuditRequest) return;
      auditError.value = messageOf(caught);
    } finally {
      if (requestId === latestAuditRequest) isLoadingAudit.value = false;
    }
  }

  async function selectDistrict(code: string | null): Promise<void> {
    selectedCode.value = code;
    audit.value = null;
    auditError.value = null;
    if (code) await loadAudit(code);
  }

  async function initialize(): Promise<void> {
    await Promise.all([loadIndex(), loadEvents()]);
  }

  return {
    requestedEventId,
    index,
    isLoading,
    error,
    events,
    isLoadingEvents,
    eventsError,
    selectedCode,
    audit,
    isLoadingAudit,
    auditError,
    districts,
    selectedDistrict,
    loadIndex,
    loadEvents,
    selectEvent,
    selectDistrict,
    initialize,
  };
});
