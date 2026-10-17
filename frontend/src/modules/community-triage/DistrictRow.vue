<script setup lang="ts">
import { computed, ref } from "vue";
import type { DistrictPrioRead } from "../../api/client";
import { fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";
import ClassPips from "./ClassPips.vue";
import { departmentName } from "./departments";
import { formatScore } from "./formatters";
import { asAlertClass, classCarrier, classLabels, type TriageMode } from "./triageModel";

const props = defineProps<{
  district: DistrictPrioRead;
  mode: TriageMode;
  tabbable: boolean;
  selected: boolean;
}>();

const emit = defineEmits<{ (e: "select"): void; (e: "focus"): void }>();

const { t, locale } = useI18n();
const c = computed(() => t.value.community);
const button = ref<HTMLButtonElement | null>(null);

const alertClass = computed(() =>
  props.district.withheld ? null : asAlertClass(props.district.alert_class),
);
const department = computed(() => departmentName(props.district.district_code));
const scoreText = computed(() =>
  props.district.score === null ? "—" : formatScore(props.district.score, locale.value),
);
/** The bar is a 0-10 measurement; a missing score draws no bar rather than an empty one. */
const barWidth = computed(() =>
  props.district.score === null
    ? null
    : `${Math.max(0, Math.min(10, props.district.score)) * 10}%`,
);

/** One sentence carrying everything the visual row shows. */
const accessibleName = computed(() => {
  const d = props.district;
  if (d.withheld) return `${d.district_name}. ${c.value.list.withheld}`;
  const parts = [d.district_name];
  if (department.value) parts.push(department.value);
  if (d.rank !== null) parts.push(fillMessage(c.value.list.rankLabel, { rank: d.rank }));
  parts.push(`${c.value.detail.score} ${scoreText.value}`);
  if (alertClass.value) parts.push(classLabels(c.value, props.mode, alertClass.value).name);
  return parts.join(", ");
});

defineExpose({ focus: () => button.value?.focus() });
</script>

<template>
  <button
    ref="button"
    type="button"
    class="row"
    data-testid="district-row"
    :class="[
      alertClass ? classCarrier(mode, alertClass) : '',
      { selected, withheld: district.withheld },
    ]"
    :aria-label="accessibleName"
    :tabindex="tabbable ? 0 : -1"
    @click="emit('select')"
    @focus="emit('focus')"
  >
    <span class="rank eoc-numeric" aria-hidden="true">{{ district.withheld ? "—" : district.rank }}</span>

    <span class="who" aria-hidden="true">
      <span class="name">{{ district.district_name }}</span>
      <span v-if="department" class="dept">{{ department }}</span>
    </span>

    <span v-if="district.withheld" class="withheld-note" aria-hidden="true" :title="c.list.withheldHint">
      {{ c.list.withheld }}
    </span>
    <span v-else class="measure" aria-hidden="true">
      <span class="figure">
        <ClassPips v-if="alertClass" :alert-class="alertClass" />
        <span class="score eoc-numeric">{{ scoreText }}</span>
      </span>
      <span v-if="barWidth" class="track" data-testid="score-bar">
        <span class="fill" :style="{ width: barWidth }"></span>
      </span>
    </span>
  </button>
</template>

<style scoped>
.row {
  width: 100%;
  min-height: 40px;
  display: grid;
  /* rank | district + department | score + bar */
  grid-template-columns: 34px minmax(0, 1fr) 84px;
  align-items: center;
  column-gap: var(--eoc-gap-x);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel) var(--eoc-gap-y) var(--eoc-gap-x);
  background: transparent;
  border: 0;
  border-bottom: var(--eoc-border-width) solid var(--eoc-border);
  /* The class on the edge: colour (event) or neutral ink (baseline), never alone */
  border-left: 4px solid var(--class-color, var(--eoc-border));
  color: var(--eoc-text-primary);
  font: inherit;
  font-size: var(--eoc-fs-body);
  text-align: left;
  cursor: pointer;
}
.row:hover {
  background: var(--eoc-bg-hover);
}
.row.selected {
  background: var(--eoc-bg-selected);
}
.row:focus-visible {
  outline-offset: -2px;
}
.rank {
  color: var(--eoc-text-secondary);
  text-align: right;
}
.who {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: var(--eoc-fw-semibold);
}
.dept {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-label);
}
.measure {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.figure {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--eoc-gap-x);
}
.score {
  font-weight: var(--eoc-fw-semibold);
}
.track {
  height: 4px;
  background: var(--eoc-border);
}
/* A measurement, not a severity: neutral ink */
.fill {
  display: block;
  height: 100%;
  background: var(--eoc-icon);
}
.withheld-note {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
  font-style: italic;
  text-align: right;
}
@media (pointer: coarse) {
  .row {
    min-height: var(--eoc-target-primary);
  }
}
</style>
