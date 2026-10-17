<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../../i18n/useI18n";
import { ALERT_CLASS_ORDER, type AlertClassKey } from "./triageModel";

const props = defineProps<{ alertClass: AlertClassKey }>();
const { t } = useI18n();

/** Roja lights four pips, verde one: severity survives a greyscale print. */
const litPips = computed(
  () => ALERT_CLASS_ORDER.length - ALERT_CLASS_ORDER.indexOf(props.alertClass),
);
</script>

<template>
  <span class="class-badge" :class="`eoc-class-${alertClass}`">
    <span class="pips" aria-hidden="true">
      <i v-for="n in ALERT_CLASS_ORDER.length" :key="n" :class="{ lit: n <= litPips }"></i>
    </span>
    {{ t.community.classes[alertClass].name }}
  </span>
</template>

<style scoped>
.class-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  padding: 0 var(--eoc-gap-x);
  height: 18px;
  border: var(--eoc-border-width) solid var(--class-border);
  border-radius: var(--eoc-radius-control);
  background: var(--class-bg);
  color: var(--class-color);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  white-space: nowrap;
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}
.pips {
  display: inline-flex;
  gap: 1px;
}
.pips i {
  width: 4px;
  height: 8px;
  border: var(--eoc-border-width) solid var(--class-color);
  box-sizing: border-box;
}
.pips i.lit {
  background: var(--class-color);
}
</style>
