<script setup lang="ts">
import { computed, toRef } from "vue";
import type { DistrictPrioRead } from "../../../../api/client";
import type { AppLocale } from "../../../../i18n/useI18n";
import { departmentName } from "../../departments";
import { formatInteger, formatScore } from "../../formatters";
import { dimensionScores } from "../../rankModel";
import { usePrintCopy } from "../usePrintCopy";

const props = defineProps<{ district: DistrictPrioRead; lang: AppLocale }>();
const { m, c } = usePrintCopy(toRef(props, "lang"));
const dims = computed(() => dimensionScores(props.district));
const sphere = computed(() => (props.district.withheld ? null : (props.district.sphere ?? null)));
</script>

<template>
  <section class="print-section keep-together" data-testid="section-district">
    <h2 class="eoc-label">{{ m.sheet.districtHeading }}</h2>
    <p class="title">{{ district.district_name }}</p>
    <p v-if="departmentName(district.district_code)" class="muted">{{ departmentName(district.district_code) }}</p>
    <p v-if="district.withheld" class="muted">{{ c.detail.withheldWhole }}</p>
    <template v-else>
      <p class="eoc-numeric">
        {{ c.detail.score }}: <strong>{{ district.score === null ? "—" : formatScore(district.score, lang) }}</strong> / 10
      </p>
      <dl class="facts">
        <template v-for="d in dims" :key="d.key">
          <dt>{{ c.dimensions[d.key].name }}</dt>
          <dd class="eoc-numeric">{{ d.score === null ? "—" : formatScore(d.score, lang) }}</dd>
        </template>
      </dl>
      <template v-if="sphere">
        <h3 class="sub">{{ c.detail.sphereTitle }}</h3>
        <dl class="facts">
          <dt>{{ c.detail.waterPerDay }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(sphere.water_litres_per_day, lang) }} L</dd>
          <dt>{{ c.detail.taps }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(sphere.water_taps_minimum, lang) }}</dd>
          <dt>{{ c.detail.food }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(sphere.food_kcal_per_day, lang) }} kcal</dd>
          <dt>{{ c.detail.shelter }}</dt>
          <dd class="eoc-numeric">{{ formatInteger(sphere.shelter_area_m2, lang) }} m²</dd>
        </dl>
        <p class="muted">{{ c.detail.sphereNote }}</p>
      </template>
    </template>
  </section>
</template>
