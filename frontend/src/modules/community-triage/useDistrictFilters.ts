import { computed, ref, type Ref } from "vue";
import type { DistrictPrioRead } from "../../api/client";
import type { AppLocale } from "../../i18n/useI18n";
import {
  filterDistricts,
  sortDistricts,
  type SortKey,
} from "./rankModel";
import { classCounts, type AlertClassKey, type TriageMode } from "./triageModel";

export type ScopeKey = "zone" | "country";

/** Rows revealed per step; the full ranking is 262 rows on modest hardware. */
export const REVEAL_CHUNK = 60;

/**
 * What the operator is looking at: scope, class, search and sort over the loaded
 * ranking. It lives above the list so that the export dialog can offer "what I
 * am looking at" and so the choices survive opening a district and coming back.
 */
export function useDistrictFilters(
  districts: Ref<DistrictPrioRead[]>,
  departmentPrefix: Ref<string | null>,
  mode: Ref<TriageMode>,
  locale: Ref<AppLocale>,
) {
  const search = ref("");
  const classFilter = ref<AlertClassKey | null>(null);
  const sortChoice = ref<SortKey>("score");
  const scopeChoice = ref<ScopeKey>("zone");
  const revealLimit = ref(REVEAL_CHUNK);

  /** Only a department the zone resolves to can scope the list; never guessed. */
  const scopeAvailable = computed(() => departmentPrefix.value !== null);
  const scope = computed<ScopeKey>(() =>
    scopeAvailable.value ? scopeChoice.value : "country",
  );
  const activePrefix = computed(() => (scope.value === "zone" ? departmentPrefix.value : null));

  /** Exposed population has no meaning before an event, so the sort is event-only. */
  const sort = computed<SortKey>(() =>
    sortChoice.value === "exposed" && mode.value !== "event" ? "score" : sortChoice.value,
  );

  const searched = computed(() =>
    filterDistricts(districts.value, {
      departmentPrefix: activePrefix.value,
      classFilter: null,
      search: search.value,
    }),
  );
  const counts = computed(() => classCounts(searched.value));
  const shown = computed(() =>
    sortDistricts(
      classFilter.value
        ? filterDistricts(searched.value, { departmentPrefix: null, classFilter: classFilter.value, search: "" })
        : searched.value,
      sort.value,
      locale.value,
    ),
  );

  const filterActive = computed(
    () => scope.value === "zone" || classFilter.value !== null || search.value.trim() !== "",
  );

  function resetReveal(): void {
    revealLimit.value = REVEAL_CHUNK;
  }

  function setClass(key: AlertClassKey | null): void {
    classFilter.value = key;
    resetReveal();
  }

  /** Clears class and search; the scope stays because it is a place, not a filter. */
  function clearFilters(): void {
    classFilter.value = null;
    search.value = "";
    resetReveal();
  }

  return {
    search,
    classFilter,
    sort: sortChoice,
    effectiveSort: sort,
    scope: scopeChoice,
    effectiveScope: scope,
    scopeAvailable,
    revealLimit,
    counts,
    shown,
    filterActive,
    setClass,
    clearFilters,
    resetReveal,
  };
}
