<script setup lang="ts">
import { toRef } from "vue";
import type { AppLocale } from "../../../../i18n/useI18n";
import type { ReportModel } from "../../exportModel";
import { usePrintCopy } from "../usePrintCopy";

const props = defineProps<{
  model: ReportModel;
  coverage: "in" | "out";
  lang: AppLocale;
}>();
const { m, c } = usePrintCopy(toRef(props, "lang"));
</script>

<template>
  <section class="print-section keep-together limits" data-testid="section-limits">
    <h2 class="eoc-label">{{ m.sheet.limitsHeading }}</h2>
    <ul class="plain">
      <li v-for="line in model.limitations" :key="line">{{ line }}</li>
      <li>{{ coverage === "out" ? m.sheet.coverageOut : m.sheet.rankingNote }}</li>
    </ul>
    <p class="muted">{{ c.honesty.attributionLabel }}: {{ model.attribution }}</p>
  </section>
</template>
