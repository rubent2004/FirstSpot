<script setup lang="ts">
import { computed, toRef } from "vue";
import type { PlaceRead } from "../../../../api/client";
import type { AppLocale } from "../../../../i18n/useI18n";
import { placesTable } from "../mapPrintData";
import type { PlaceColumn } from "../mapPrintModel";
import { usePrintCopy } from "../usePrintCopy";

const props = defineProps<{
  places: PlaceRead[];
  topN: number;
  columns: PlaceColumn[];
  lang: AppLocale;
}>();
const { m, ui } = usePrintCopy(toRef(props, "lang"));
const table = computed(() =>
  placesTable(props.places, { topN: props.topN, columns: props.columns }, ui.value, props.lang, m.value),
);
</script>

<template>
  <section class="print-section keep-together" data-testid="section-places">
    <h2 class="eoc-label">{{ m.sheet.placesHeading }}</h2>
    <table class="grid">
      <thead>
        <tr>
          <th class="eoc-label">{{ m.sheet.rank }}</th>
          <th class="eoc-label">{{ m.sheet.place }}</th>
          <th v-for="col in table.columns" :key="col" class="eoc-label">{{ m.placeColumns[col] }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in table.rows" :key="index">
          <td class="eoc-numeric">{{ index + 1 }}</td>
          <td>{{ row.name }}</td>
          <td v-for="col in table.columns" :key="col" :class="{ 'eoc-numeric': col === 'population' || col === 'nearby' }">
            {{ row.cells[col] }}
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
