<script setup lang="ts">
import { toRef } from "vue";
import type { AppLocale } from "../../../../i18n/useI18n";
import { usePrintCopy } from "../usePrintCopy";

const props = defineProps<{ notes: string; lang: AppLocale }>();
const { m } = usePrintCopy(toRef(props, "lang"));
</script>

<template>
  <section class="print-section keep-together" data-testid="section-notes">
    <h2 class="eoc-label">{{ m.sheet.notesHeading }}</h2>
    <!-- Text interpolation escapes markup; pre-wrap keeps the operator's line breaks -->
    <p class="notes">{{ notes }}</p>
  </section>
</template>

<style scoped>
.notes {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
