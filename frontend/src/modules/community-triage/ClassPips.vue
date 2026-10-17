<script setup lang="ts">
import { computed } from "vue";
import { ALERT_CLASS_ORDER, type AlertClassKey } from "./triageModel";

const props = defineProps<{ alertClass: AlertClassKey }>();

/** Roja lights four pips, verde one: severity survives a greyscale print. */
const litPips = computed(
  () => ALERT_CLASS_ORDER.length - ALERT_CLASS_ORDER.indexOf(props.alertClass),
);
</script>

<template>
  <span class="pips" aria-hidden="true">
    <i v-for="n in ALERT_CLASS_ORDER.length" :key="n" :class="{ lit: n <= litPips }"></i>
  </span>
</template>

<style scoped>
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
