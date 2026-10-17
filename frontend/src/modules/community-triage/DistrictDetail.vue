<script setup lang="ts">
import { computed, ref } from "vue";
import { ElButton } from "element-plus";
import type { DistrictPrioRead, PrioIndexAuditRead } from "../../api/client";
import { DATA_ATTRIBUTION, fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";
import ClassBadge from "./ClassBadge.vue";
import { departmentName } from "./departments";
import { formatInteger, formatScore } from "./formatters";
import {
  DIMENSION_ORDER,
  SPHERE_CLASSES,
  asAlertClass,
  asDimensionKey,
  type DimensionKey,
} from "./triageModel";

const props = defineProps<{
  district: DistrictPrioRead;
  audit: PrioIndexAuditRead | null;
  auditLoading: boolean;
  auditError: string | null;
  total: number;
  mode: "baseline" | "event";
  /** Work-zone name, when the zone is a predefined one. */
  zoneName: string | null;
}>();

const emit = defineEmits<{ (e: "open-places"): void; (e: "close"): void }>();

const heading = ref<HTMLElement | null>(null);
defineExpose({ focusHeading: () => heading.value?.focus() });

const { t, locale } = useI18n();
const c = computed(() => t.value.community);

/** The audit response carries the same fields as the row, in the same mode. */
const view = computed<DistrictPrioRead | PrioIndexAuditRead>(
  () => props.audit ?? props.district,
);
const alertClass = computed(() => asAlertClass(view.value.alert_class));
const isZero = computed(() => view.value.score === 0);
const showsSphereNote = computed(
  () =>
    !view.value.sphere &&
    alertClass.value !== null &&
    SPHERE_CLASSES.includes(alertClass.value),
);

interface DimensionLine {
  key: DimensionKey;
  score: number | null;
  rank: number | null;
  withheld: boolean;
  zeroed: boolean;
}

const dimensionLines = computed<DimensionLine[]>(() => {
  const byKey = new Map(
    view.value.dimensions.map((d) => [asDimensionKey(d.dimension), d] as const),
  );
  return DIMENSION_ORDER.filter((key) => byKey.has(key)).map((key) => {
      const d = byKey.get(key)!;
      return {
        key,
        score: d.score,
        rank: d.rank,
        withheld: Boolean(d.withheld_reason),
        zeroed: view.value.zeroed_by.includes(key),
      };
    });
});

/** The strongest drivers first: what pushes this district up the ranking. */
const drivers = computed(() =>
  [...dimensionLines.value]
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
    .slice(0, 3),
);

const zeroLines = computed<string[]>(() => {
  if (!isZero.value) return [];
  const keys = view.value.zeroed_by
    .map(asDimensionKey)
    .filter((key): key is DimensionKey => key !== null);
  if (keys.length === 0) return [c.value.detail.zeroGeneric];
  return keys.map((key) =>
    key === "hazard_and_exposure"
      ? c.value.detail.zeroHazard
      : fillMessage(c.value.detail.zeroFloor, {
          dimension: c.value.dimensions[key].name,
          total: props.total,
        }),
  );
});

const barWidth = (score: number | null): string =>
  `${Math.max(0, Math.min(10, score ?? 0)) * 10}%`;

const informReference = computed(() =>
  props.audit?.inform_rescaled_score != null
    ? formatScore(props.audit.inform_rescaled_score, locale.value)
    : null,
);
</script>

<template>
  <article class="detail" data-testid="detail-panel">
    <header class="head">
      <div class="title">
        <h3 ref="heading" class="name" tabindex="-1" data-testid="detail-heading">
          {{ district.district_name }}
        </h3>
        <p v-if="departmentName(district.district_code)" class="dept">
          {{ departmentName(district.district_code) }}
        </p>
      </div>
      <ElButton class="close" size="small" :aria-label="c.nav.closeDetail" @click="emit('close')">
        <span aria-hidden="true">✕</span>
        <span class="close-text">{{ c.nav.closeDetail }}</span>
      </ElButton>
    </header>

    <p v-if="district.withheld" class="note">{{ c.detail.withheldWhole }}</p>

    <template v-else>
      <!-- 1. Where it stands and why -->
      <section class="summary">
        <div class="headline">
          <span class="score eoc-numeric">
            {{ view.score === null ? "—" : formatScore(view.score, locale) }}
          </span>
          <span class="of10 eoc-numeric">/ 10 · {{ c.detail.score }}</span>
          <ClassBadge v-if="alertClass" :alert-class="alertClass" :mode="mode" />
        </div>
        <p v-if="view.rank !== null" class="rank eoc-numeric">
          {{ fillMessage(c.detail.rankOf, { rank: view.rank, total }) }}
        </p>
        <p v-if="mode === 'event'" class="exposed" data-testid="detail-exposed">
          <span class="eoc-label">{{ c.detail.exposedTitle }}</span>
          <strong v-if="view.estimated_exposed_population !== null" class="eoc-numeric">
            {{ formatInteger(view.estimated_exposed_population, locale) }}
          </strong>
          <strong v-else>{{ c.list.exposedNone }}</strong>
        </p>
      </section>

      <section v-if="zeroLines.length" class="zero" data-testid="zero-reason">
        <h4 class="eoc-label">{{ c.detail.zeroTitle }}</h4>
        <p v-for="line in zeroLines" :key="line">{{ line }}</p>
      </section>

      <section class="block" data-tour="detail-drivers">
        <h4 class="eoc-label">{{ c.detail.driversTitle }}</h4>
        <ul class="dims">
          <li v-for="line in drivers" :key="line.key">
            <div class="dim-head">
              <span>{{ c.dimensions[line.key].name }}</span>
              <span v-if="line.withheld" class="muted">{{ c.detail.withheldDimension }}</span>
              <span v-else class="eoc-numeric">
                <strong>{{ line.score === null ? "—" : formatScore(line.score, locale) }}</strong>
                <span v-if="line.rank !== null" class="muted">
                  · {{ fillMessage(c.detail.dimensionRank, { rank: line.rank }) }}
                </span>
              </span>
            </div>
            <div class="track" aria-hidden="true">
              <div class="fill" :style="{ width: barWidth(line.score) }"></div>
            </div>
          </li>
        </ul>
        <p v-if="mode === 'baseline'" class="muted small">{{ c.detail.baselineNoHazard }}</p>
      </section>
    </template>

    <!-- 2. What to attend next -->
    <section class="block" data-testid="detail-places">
      <h4 class="eoc-label">{{ c.detail.placesTitle }}</h4>
      <p class="small">{{ c.detail.placesBody }}</p>
      <ElButton size="small" class="places-open" @click="emit('open-places')">
        {{ zoneName ? fillMessage(c.detail.placesOpen, { zone: zoneName }) : c.nav.places }}
      </ElButton>
    </section>

    <!-- 3. Raw indicators, Sphere needs and sources: folded -->
    <details v-if="!district.withheld" class="fold" data-tour="detail-technical">
      <summary>{{ c.detail.technicalTitle }}</summary>

      <section v-if="view.sphere" class="block" data-testid="sphere-block" data-tour="sphere">
        <h4 class="eoc-label">{{ c.detail.sphereTitle }}</h4>
        <dl class="sphere">
          <dt>{{ c.detail.waterPerDay }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(view.sphere.water_litres_per_day, locale) }} L</dd>
          <dt>{{ c.detail.waterHeat }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(view.sphere.water_litres_per_day_extreme_heat, locale) }} L</dd>
          <dt>{{ c.detail.taps }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(view.sphere.water_taps_minimum, locale) }}</dd>
          <dt>{{ c.detail.waterDistance }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(view.sphere.water_point_maximum_distance_metres, locale) }} m</dd>
          <dt>{{ c.detail.food }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(view.sphere.food_kcal_per_day, locale) }} kcal</dd>
          <dt>{{ c.detail.shelter }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(view.sphere.shelter_area_m2, locale) }} m²</dd>
        </dl>
        <p class="muted small">{{ c.detail.sphereNote }}</p>
      </section>
      <p v-else-if="showsSphereNote" class="muted small">{{ c.detail.sphereNotComputed }}</p>

      <section v-if="mode === 'event'" class="block">
        <h4 class="eoc-label">{{ c.detail.exposedTitle }}</h4>
        <p class="muted small">{{ c.detail.exposedNote }}</p>
      </section>

      <section class="block">
        <h4 class="eoc-label">{{ c.detail.auditTitle }}</h4>
        <ul class="dims all">
          <li v-for="line in dimensionLines" :key="line.key" class="small">
            {{ c.dimensions[line.key].name }}:
            <span class="eoc-numeric">{{ line.score === null ? "—" : formatScore(line.score, locale) }}</span>
          </li>
        </ul>
        <p class="small">
          {{ fillMessage(c.detail.auditRule, { count: dimensionLines.length }) }}
        </p>
        <p v-if="view.max_mmi !== null" class="small eoc-numeric">
          {{ c.event.maxShaking }}: {{ view.max_mmi.toFixed(1) }}
        </p>
        <p v-if="informReference" class="muted small eoc-numeric">
          {{ c.detail.auditReference }}: {{ informReference }}
        </p>
        <p v-if="auditLoading" class="muted small" role="status">{{ c.detail.auditLoading }}</p>
        <p v-else-if="auditError" class="error small" role="alert">{{ c.detail.auditFailed }}</p>
        <p class="muted small">{{ c.honesty.attributionLabel }}: {{ DATA_ATTRIBUTION }}</p>
      </section>
    </details>
  </article>
</template>

<style scoped>
.detail {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
  overflow-y: auto;
  min-height: 0;
  flex: 1;
}
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--eoc-gap-x);
}
.title {
  min-width: 0;
}
.name {
  margin: 0;
  font-size: var(--eoc-fs-heading);
  font-weight: var(--eoc-fw-semibold);
  overflow-wrap: anywhere;
}
.name:focus-visible {
  outline-offset: 2px;
}
.dept {
  margin: 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-label);
}
.close {
  flex: none;
  min-width: var(--eoc-target-min);
}
.summary {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.headline {
  display: flex;
  align-items: baseline;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}
.score {
  font-size: 28px;
  line-height: 1.1;
  font-weight: var(--eoc-fw-semibold);
}
.of10,
.rank {
  margin: 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
.exposed {
  margin: var(--eoc-gap-y) 0 0;
  display: flex;
  align-items: baseline;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}
.zero {
  border: var(--eoc-border-width) solid var(--eoc-info-border);
  border-left: 3px solid var(--eoc-info);
  background: var(--eoc-info-bg);
  border-radius: var(--eoc-radius-control);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
}
.zero h4,
.block h4 {
  margin: 0 0 2px;
}
.zero p {
  margin: 0;
  font-size: var(--eoc-fs-body);
  line-height: 1.4;
}
.block {
  border: var(--eoc-border-width) solid var(--eoc-border);
  border-radius: var(--eoc-radius-control);
  background: var(--eoc-bg-card);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
}
.block p {
  margin: 0;
}
.dims {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
}
.dim-head {
  display: flex;
  justify-content: space-between;
  font-size: var(--eoc-fs-body);
}
.track {
  height: 4px;
  background: var(--eoc-bg-sunken);
  border: var(--eoc-border-width) solid var(--eoc-border);
}
/* A bar is a measurement, not a severity: neutral ink */
.fill {
  height: 100%;
  background: var(--eoc-icon);
}
.fold {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
}
.fold > summary {
  min-height: var(--eoc-target-min);
  display: flex;
  align-items: center;
  cursor: pointer;
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-accent-text);
}
.fold[open] > summary {
  margin-bottom: var(--eoc-gap-y);
}
.sphere {
  margin: 0 0 var(--eoc-gap-y);
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 2px var(--eoc-pad-panel);
  font-size: var(--eoc-fs-body);
}
.sphere dt {
  color: var(--eoc-text-secondary);
}
.sphere dd {
  margin: 0;
  text-align: right;
}
.muted {
  color: var(--eoc-text-secondary);
}
.small {
  font-size: var(--eoc-fs-micro);
  line-height: 1.4;
}
.error {
  color: var(--eoc-text-primary);
  border-left: 3px solid var(--eoc-critical);
  padding-left: var(--eoc-gap-x);
}
.note {
  margin: 0;
  font-size: var(--eoc-fs-body);
  color: var(--eoc-text-secondary);
}
.places-open {
  margin-top: var(--eoc-gap-y);
}
</style>
