<script setup lang="ts">
import { toRef } from "vue";
import type { HazardEventRead } from "../../../../api/client";
import type { AppLocale } from "../../../../i18n/useI18n";
import { fillMessage } from "../../../../i18n/communityMessages";
import { getHazardAgencyLabel, humanizeHazardTitle } from "../../../map-viewer/composables/hazardPresentation";
import { formatUtcTimestamp } from "../../formatters";
import { usePrintCopy } from "../usePrintCopy";

const props = defineProps<{ hazards: HazardEventRead[]; lang: AppLocale }>();
const { m } = usePrintCopy(toRef(props, "lang"));
</script>

<template>
  <section class="print-section keep-together" data-testid="section-hazards">
    <h2 class="eoc-label">{{ m.sheet.hazardsHeading }}</h2>
    <ul class="plain">
      <li v-for="event in hazards" :key="event.id">
        <strong>{{ humanizeHazardTitle(event.title, lang) }}</strong>
        <span class="muted">
          · {{ getHazardAgencyLabel(event.source, lang) }} ·
          <span class="eoc-numeric">{{ formatUtcTimestamp(event.occurred_at) }}</span> ·
          {{ fillMessage(m.sheet.radius, { km: event.radius_km }) }}
          <template v-if="event.magnitude !== null"> · <span class="eoc-numeric">M{{ event.magnitude.toFixed(1) }}</span></template>
        </span>
      </li>
    </ul>
  </section>
</template>
