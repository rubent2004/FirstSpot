<script setup lang="ts">
import { toRef } from "vue";
import type { WeatherConditionRead } from "../../../../api/client";
import type { AppLocale } from "../../../../i18n/useI18n";
import { usePrintCopy } from "../usePrintCopy";

const props = defineProps<{ weather: WeatherConditionRead; lang: AppLocale }>();
const { m, number } = usePrintCopy(toRef(props, "lang"));
</script>

<template>
  <section class="print-section keep-together" data-testid="section-weather">
    <h2 class="eoc-label">{{ m.sheet.weatherHeading }}</h2>
    <p>{{ weather.weather_label }}</p>
    <dl class="facts">
      <dt>{{ m.sheet.temperature }}</dt>
      <dd class="eoc-numeric">{{ number(weather.temperature_c, 1) }} °C</dd>
      <dt>{{ m.sheet.precipitation }}</dt>
      <dd class="eoc-numeric">{{ number(weather.precipitation_mm, 1) }} mm</dd>
      <dt>{{ m.sheet.wind }}</dt>
      <dd class="eoc-numeric">{{ number(weather.wind_speed_kmh) }} km/h</dd>
      <dt>{{ m.sheet.gusts }}</dt>
      <dd class="eoc-numeric">{{ number(weather.wind_gusts_kmh) }} km/h</dd>
    </dl>
  </section>
</template>
