<script setup lang="ts">
import { useI18n } from "../../i18n/useI18n";
import ClassPips from "./ClassPips.vue";
import {
  classCarrier,
  classLabels,
  type AlertClassKey,
  type TriageMode,
} from "./triageModel";

defineProps<{ alertClass: AlertClassKey; mode: TriageMode }>();
const { t } = useI18n();
</script>

<template>
  <span class="class-badge" :class="classCarrier(mode, alertClass)">
    <ClassPips :alert-class="alertClass" />
    {{ classLabels(t.community, mode, alertClass).name }}
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
</style>
