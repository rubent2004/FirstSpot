<script setup lang="ts">
import { computed } from "vue";
import { ElButton } from "element-plus";
import type { DistrictPrioRead, PrioIndexAuditRead } from "../../api/client";
import { fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";
import ClassBadge from "./ClassBadge.vue";
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
}>();

const emit = defineEmits<{ (e: "back"): void }>();

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
  <article class="detail">
    <ElButton size="small" text class="back" @click="emit('back')">
      ← {{ c.detail.back }}
    </ElButton>

    <header class="head">
      <h3 class="name">{{ district.district_name }}</h3>
      <ClassBadge v-if="alertClass && !district.withheld" :alert-class="alertClass" />
    </header>

    <p v-if="district.withheld" class="note">{{ c.detail.withheldWhole }}</p>

    <template v-else>
      <div class="headline">
        <span class="score eoc-numeric">
          {{ view.score === null ? "—" : formatScore(view.score, locale) }}
        </span>
        <span class="of10 eoc-numeric">/ 10 · {{ c.detail.score }}</span>
        <span v-if="view.rank !== null" class="rank eoc-numeric">
          {{ fillMessage(c.detail.rankOf, { rank: view.rank, total }) }}
        </span>
      </div>

      <section v-if="zeroLines.length" class="zero" data-testid="zero-reason">
        <h4 class="eoc-label">{{ c.detail.zeroTitle }}</h4>
        <p v-for="line in zeroLines" :key="line">{{ line }}</p>
      </section>

      <section class="block">
        <h4 class="eoc-label">{{ c.detail.dimensionsTitle }}</h4>
        <ul class="dims">
          <li v-for="line in dimensionLines" :key="line.key">
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

      <section v-if="view.estimated_exposed_population !== null" class="block">
        <h4 class="eoc-label">{{ c.detail.exposedTitle }}</h4>
        <p class="big eoc-numeric">{{ formatInteger(view.estimated_exposed_population, locale) }}</p>
        <p class="muted small">{{ c.detail.exposedNote }}</p>
      </section>

      <section v-if="view.sphere" class="block" data-testid="sphere-block">
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

      <section class="block">
        <h4 class="eoc-label">{{ c.detail.auditTitle }}</h4>
        <p class="small">
          {{ fillMessage(c.detail.auditRule, { count: dimensionLines.length }) }}
        </p>
        <p v-if="view.max_mmi !== null" class="small eoc-numeric">
          {{ c.event.maxShaking }}: {{ view.max_mmi.toFixed(1) }}
        </p>
        <p v-if="informReference" class="muted small eoc-numeric">
          {{ c.detail.auditReference }}: {{ informReference }}
        </p>
        <p v-if="auditLoading" class="muted small">{{ c.detail.auditLoading }}</p>
        <p v-else-if="auditError" class="error small">{{ c.detail.auditFailed }}</p>
      </section>
    </template>
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
.back {
  align-self: flex-start;
  padding-left: 0;
}
.head {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}
.name {
  margin: 0;
  font-size: var(--eoc-fs-title);
  font-weight: var(--eoc-fw-semibold);
}
.headline {
  display: flex;
  align-items: baseline;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}
.score {
  font-size: var(--eoc-fs-heading);
  font-weight: var(--eoc-fw-semibold);
}
.of10,
.rank {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
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
/* Operational accent: a bar is a measurement, not a severity */
.fill {
  height: 100%;
  background: var(--eoc-accent);
}
.big {
  font-size: var(--eoc-fs-title);
  font-weight: var(--eoc-fw-semibold);
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
  color: var(--eoc-text-muted);
}
.small {
  font-size: var(--eoc-fs-micro);
  line-height: 1.4;
}
.error {
  color: var(--eoc-critical);
}
.note {
  margin: 0;
  font-size: var(--eoc-fs-body);
  color: var(--eoc-text-secondary);
}
</style>
