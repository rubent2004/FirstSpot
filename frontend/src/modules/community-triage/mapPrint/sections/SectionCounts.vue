<script setup lang="ts">
import { computed, toRef } from "vue";
import type { PlaceRead } from "../../../../api/client";
import type { AppLocale } from "../../../../i18n/useI18n";
import { countsByStatus, countsByUrgency } from "../mapPrintData";
import { usePrintCopy } from "../usePrintCopy";

const props = defineProps<{ places: PlaceRead[]; lang: AppLocale }>();
const { m, ui } = usePrintCopy(toRef(props, "lang"));
const urgency = computed(() => countsByUrgency(props.places));
const status = computed(() => countsByStatus(props.places));
</script>

<template>
  <section class="print-section keep-together" data-testid="section-counts">
    <h2 class="eoc-label">{{ m.sheet.countsHeading }}</h2>
    <h3 class="sub">{{ m.sheet.byUrgency }}</h3>
    <ul class="counts">
      <li v-for="level in [5, 4, 3, 2, 1]" :key="level">
        <span>{{ ui.urgency[level] }}</span>
        <strong class="eoc-numeric">{{ urgency[level] }}</strong>
      </li>
    </ul>
    <h3 class="sub">{{ m.sheet.byStatus }}</h3>
    <ul class="counts">
      <li v-for="key in (['pending', 'in_progress', 'attended'] as const)" :key="key">
        <span>{{ ui.statuses[key] }}</span>
        <strong class="eoc-numeric">{{ status[key] }}</strong>
      </li>
    </ul>
  </section>
</template>
