<script setup lang="ts">
import { computed, toRef } from "vue";
import type { DistrictPrioRead } from "../../../api/client";
import { fillMessage } from "../../../i18n/communityMessages";
import type { AppLocale } from "../../../i18n/useI18n";
import type { ReportModel } from "../exportModel";
import { coverageOf, SECTION_ORDER, type MapPrintPrefs, type SectionId } from "./mapPrintModel";
import type { MapSnapshot } from "./mapSnapshot";
import PrintViewMap from "./PrintViewMap.vue";
import SectionContacts from "./sections/SectionContacts.vue";
import SectionCounts from "./sections/SectionCounts.vue";
import SectionDistrict from "./sections/SectionDistrict.vue";
import SectionHazards from "./sections/SectionHazards.vue";
import SectionLimits from "./sections/SectionLimits.vue";
import SectionNotes from "./sections/SectionNotes.vue";
import SectionPlaceDetail from "./sections/SectionPlaceDetail.vue";
import SectionPlaces from "./sections/SectionPlaces.vue";
import SectionWeather from "./sections/SectionWeather.vue";
import { usePrintCopy } from "./usePrintCopy";

const props = defineProps<{
  snapshot: MapSnapshot;
  model: ReportModel;
  prefs: MapPrintPrefs;
  /** Sections the operator ticked, already reduced to the ones that have data. */
  sections: SectionId[];
  notes: string;
  selectedDistrict: DistrictPrioRead | null;
  lang: AppLocale;
  /** The preview swaps the live map for a placeholder: tiles are not worth loading twice. */
  preview?: boolean;
}>();

const { m, c, number } = usePrintCopy(toRef(props, "lang"));
const coverage = computed(() => coverageOf(props.snapshot.view.center));
const has = (id: SectionId): boolean => props.sections.includes(id);

/** The title says what is printed: the open district, else the work zone. */
const title = computed(() => {
  if (props.selectedDistrict && coverage.value === "in") return props.selectedDistrict.district_name;
  return props.snapshot.zone.name
    ? fillMessage(m.value.title, { zone: props.snapshot.zone.name })
    : m.value.titleNoZone;
});

const painted = computed(() => {
  const s = props.snapshot;
  return {
    heat: s.layers.heat && s.heatPoints.length > 0,
    places: s.layers.markers && s.places.length > 0,
    hazards: s.layers.hazards && s.hazards.length > 0,
    radius: s.view.radius !== null,
    selected: s.selectedPlace !== null && s.layers.markers,
  };
});

const viewLine = computed(() =>
  fillMessage(m.value.sheet.viewLine, {
    lat: number(props.snapshot.view.center[0], 4),
    lon: number(props.snapshot.view.center[1], 4),
    zoom: props.snapshot.view.zoom,
  }),
);
/** The limits block is not optional; everything else prints only if chosen. */
const orderedSections = computed(() => SECTION_ORDER.filter((id) => id === "limits" || has(id)));
</script>

<template>
  <div class="map-body" data-testid="map-print-body">
    <header class="sheet-head keep-together">
      <h1 data-testid="map-print-title">{{ title }}</h1>
      <dl class="meta">
        <div>
          <dt class="eoc-label">{{ c.mode.label }}</dt>
          <dd>
            <strong data-testid="sheet-mode">{{ model.modeLabel }}</strong>
            — {{ model.modeMeaning }}
          </dd>
        </div>
        <div v-if="model.event">
          <dt class="eoc-label">{{ c.event.pickerLabel }}</dt>
          <dd>
            <span v-if="model.event.magnitude !== null" class="eoc-numeric">M{{ model.event.magnitude.toFixed(1) }}</span>
            {{ model.event.place }} ·
            <span class="eoc-numeric">{{ model.event.occurredLabel ?? "—" }}</span>
          </dd>
        </div>
        <div v-if="model.event">
          <dt class="eoc-label">{{ c.event.shakemapGrid }}</dt>
          <dd class="eoc-numeric">
            {{ model.event.shakemapLabel ?? c.event.shakemapPending }}
            <small>{{ c.event.shakemapRevised }}</small>
          </dd>
        </div>
        <div>
          <dt class="eoc-label">{{ c.sheet.generatedAt }}</dt>
          <dd class="eoc-numeric">{{ model.generatedAtLabel }}</dd>
        </div>
      </dl>
    </header>

    <p v-if="coverage === 'out'" class="coverage-out" data-testid="coverage-out">
      {{ m.sheet.coverageOut }}
    </p>

    <div class="map-frame">
      <div v-if="preview" class="map-placeholder">{{ m.previewMapPlaceholder }}</div>
      <PrintViewMap v-else :snapshot="snapshot" :scale="prefs.scale" :north="prefs.north" />
    </div>
    <p class="view-line muted eoc-numeric">{{ viewLine }} · {{ m.sheet.basemapNote }}</p>

    <section v-if="prefs.legend" class="legend keep-together" data-testid="map-legend" :aria-label="m.sheet.legendHeading">
      <h2 class="eoc-label">{{ m.sheet.legendHeading }}</h2>
      <ul>
        <li v-if="painted.heat"><i class="key heat"></i>{{ m.sheet.legendHeat }}</li>
        <li v-if="painted.places"><i class="key dot"></i>{{ m.sheet.legendPlaces }}</li>
        <li v-if="painted.selected"><i class="key ring"></i>{{ m.sheet.legendSelected }}</li>
        <li v-if="painted.hazards"><i class="key hazard"></i>{{ m.sheet.legendHazards }}</li>
        <li v-if="painted.radius"><i class="key radius"></i>{{ m.sheet.legendRadius }}</li>
      </ul>
    </section>

    <div class="sections">
      <template v-for="id in orderedSections" :key="id">
        <SectionPlaces
          v-if="id === 'places' && snapshot.places.length > 0"
          :places="snapshot.places"
          :top-n="prefs.topPlaces"
          :columns="prefs.placeColumns"
          :lang="lang"
        />
        <SectionPlaceDetail
          v-else-if="id === 'placeDetail' && snapshot.selectedPlace"
          :place="snapshot.selectedPlace"
          :activities="snapshot.activities"
          :show-population="coverage === 'in'"
          :lang="lang"
        />
        <SectionCounts v-else-if="id === 'counts' && snapshot.places.length > 0" :places="snapshot.places" :lang="lang" />
        <SectionDistrict
          v-else-if="id === 'districtDetail' && selectedDistrict && coverage === 'in'"
          :district="selectedDistrict"
          :lang="lang"
        />
        <SectionHazards v-else-if="id === 'hazards' && snapshot.hazards.length > 0" :hazards="snapshot.hazards" :lang="lang" />
        <SectionWeather v-else-if="id === 'weather' && snapshot.weather" :weather="snapshot.weather" :lang="lang" />
        <SectionContacts v-else-if="id === 'contacts' && coverage === 'in'" :lang="lang" />
        <SectionNotes v-else-if="id === 'notes' && notes.trim() !== ''" :notes="notes" :lang="lang" />
        <SectionLimits v-else-if="id === 'limits'" :model="model" :coverage="coverage" :lang="lang" />
      </template>
    </div>

    <footer class="sheet-footer">
      {{ model.modeLabel }} · {{ c.sheet.generatedAt }} {{ model.generatedAtLabel }} ·
      {{ c.honesty.attributionLabel }}: {{ model.attribution }}
    </footer>
  </div>
</template>

<style scoped>
.map-body {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
}
h1 {
  margin: 0 0 var(--eoc-gap-y);
  font-size: var(--eoc-fs-heading);
  overflow-wrap: anywhere;
}
.meta {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--eoc-gap-y) var(--eoc-pad-panel);
}
.meta dt,
.meta dd {
  margin: 0;
}
.meta small {
  display: block;
  color: var(--eoc-text-secondary);
  font-size: var(--eoc-fs-micro);
}
.coverage-out {
  margin: 0;
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  border-left: 3px solid var(--eoc-icon);
  font-weight: var(--eoc-fw-semibold);
}
.map-frame {
  position: relative;
  height: 120mm;
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
}
.map-frame :deep(.print-map) {
  position: absolute;
  inset: 0;
  min-height: 0;
  height: 100%;
  border: 0;
}
.map-placeholder {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: var(--eoc-bg-sunken);
  color: var(--eoc-text-secondary);
  font-size: var(--eoc-fs-micro);
}
.view-line {
  margin: 0;
  font-size: var(--eoc-fs-micro);
}
.muted {
  color: var(--eoc-text-secondary);
}
.legend h2 {
  margin: 0 0 2px;
}
.legend ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--eoc-gap-y) var(--eoc-pad-panel);
  font-size: var(--eoc-fs-micro);
}
.legend li {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
}
.key {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
}
.key.heat {
  background: var(--eoc-warning);
}
.key.dot {
  border-radius: var(--eoc-radius-pill);
  background: var(--eoc-icon);
}
.key.ring {
  border-radius: var(--eoc-radius-pill);
  border: 3px solid var(--eoc-accent);
}
.key.hazard {
  border: 2px dashed var(--eoc-icon);
  border-radius: var(--eoc-radius-pill);
}
.key.radius {
  border: 2px solid var(--eoc-accent);
  border-radius: var(--eoc-radius-pill);
}
.sections {
  column-gap: var(--eoc-pad-panel);
  column-count: 1;
}
@media (min-width: 900px) {
  .sections {
    column-count: 2;
  }
}
.sections > :deep(*) {
  break-inside: avoid;
}
.sheet-footer {
  padding-top: var(--eoc-gap-y);
  border-top: var(--eoc-border-width) solid var(--eoc-border);
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
</style>
