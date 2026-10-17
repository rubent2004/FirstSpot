<script setup lang="ts">
import { computed, toRef } from "vue";
import type { PlaceActivityRead, PlaceRead } from "../../../../api/client";
import { describePlaceName, type AppLocale } from "../../../../i18n/useI18n";
import { operatorRelevantFacts } from "../../../../utils/placeFacts";
import {
  exposedPopulationState,
  vulnerableExposureBreakdown,
  type PopulationExposureState,
} from "../../../priority-queue/populationExposure";
import { formatUtcTimestamp } from "../../formatters";
import { usePrintCopy } from "../usePrintCopy";

const props = defineProps<{
  place: PlaceRead;
  activities: PlaceActivityRead[];
  /** False outside census coverage: the figures section is then not printed at all. */
  showPopulation: boolean;
  lang: AppLocale;
}>();
const { m, ui, number } = usePrintCopy(toRef(props, "lang"));

const name = computed(() => describePlaceName(props.place, props.lang).label);
const facts = computed(() => operatorRelevantFacts(props.place));
const breakdown = computed(() => vulnerableExposureBreakdown(props.place));

function figure(state: PopulationExposureState): string {
  if (state.kind === "estimate") return number(state.value);
  return state.kind === "withheld" ? m.value.exposure.withheld : m.value.exposure.noCoverage;
}

function factText(fact: ReturnType<typeof operatorRelevantFacts>[number]): string {
  if (fact.flag) return ui.value.drawer.facts[fact.flag];
  return fact.text;
}
</script>

<template>
  <section class="print-section keep-together" data-testid="section-place-detail">
    <h2 class="eoc-label">{{ m.sheet.placeDetailHeading }}</h2>
    <p class="title">{{ name }}</p>
    <p class="muted">
      {{ ui.categories[place.category] }} · {{ ui.urgency[place.urgency_level] }} · {{ ui.statuses[place.attention_status] }}
    </p>

    <dl v-if="facts.length" class="facts">
      <template v-for="fact in facts" :key="fact.key">
        <dt>{{ ui.drawer.facts[fact.key] }}</dt>
        <dd>{{ factText(fact) }}</dd>
      </template>
    </dl>

    <template v-if="showPopulation">
      <h3 class="sub">{{ m.sheet.exposedHeading }}</h3>
      <dl class="facts">
        <dt>{{ m.placePopulationName }}</dt>
        <dd class="eoc-numeric">{{ figure(exposedPopulationState(place)) }}</dd>
        <dt>{{ m.sheet.olderAdults }}</dt>
        <dd class="eoc-numeric">{{ figure(breakdown.olderAdults) }}</dd>
        <dt>{{ m.sheet.youngChildren }}</dt>
        <dd class="eoc-numeric">{{ figure(breakdown.youngChildren) }}</dd>
        <dt>{{ m.sheet.disability }}</dt>
        <dd class="eoc-numeric">{{ figure(breakdown.personsWithDisability) }}</dd>
      </dl>
    </template>

    <h3 class="sub">{{ m.sheet.activityHeading }}</h3>
    <p v-if="activities.length === 0" class="muted">{{ m.sheet.noActivity }}</p>
    <ol v-else class="log">
      <li v-for="item in activities" :key="item.id">
        <strong>{{ m.sheet.activityTypes[item.activity_type] ?? item.activity_type }}</strong>
        <span class="eoc-numeric"> · {{ formatUtcTimestamp(item.created_at) }}</span>
        <span> · {{ item.organization.name }}</span>
        <span v-if="item.notes" class="note">{{ item.notes }}</span>
      </li>
    </ol>
  </section>
</template>
