<script setup lang="ts">
import { computed, toRef, useId } from "vue";
import type { DistrictPrioRead } from "../../../api/client";
import { fillMessage } from "../../../i18n/communityMessages";
import type { AppLocale } from "../../../i18n/useI18n";
import type { ReportModel } from "../exportModel";
import MapPrintBody from "./MapPrintBody.vue";
import {
  PLACE_COLUMNS,
  SECTION_ORDER,
  normalizeSelection,
  presetSelection,
  type Availability,
  type MapPrintPrefs,
  type PresetId,
  type SectionId,
} from "./mapPrintModel";
import type { MapSnapshot } from "./mapSnapshot";
import { usePrintCopy } from "./usePrintCopy";

const props = defineProps<{
  snapshot: MapSnapshot;
  model: ReportModel;
  availability: Availability;
  selectedDistrict: DistrictPrioRead | null;
  lang: AppLocale;
}>();

const prefs = defineModel<MapPrintPrefs>("prefs", { required: true });
const notes = defineModel<string>("notes", { required: true });

const { m } = usePrintCopy(toRef(props, "lang"));
const uid = useId();
const PRESET_ORDER: PresetId[] = ["summary", "complete", "dispatch"];

const selected = computed(() => normalizeSelection(prefs.value.sections, props.availability));
const countText = computed(() => fillMessage(m.value.selectedCount, { n: selected.value.length }));

function applyPreset(id: PresetId): void {
  prefs.value = { ...prefs.value, sections: presetSelection(id, props.availability) };
}

function toggle(id: SectionId, checked: boolean): void {
  const next = new Set(prefs.value.sections);
  if (checked) next.add(id);
  else next.delete(id);
  prefs.value = { ...prefs.value, sections: SECTION_ORDER.filter((s) => next.has(s)) };
}

function toggleColumn(column: (typeof PLACE_COLUMNS)[number], checked: boolean): void {
  const next = new Set(prefs.value.placeColumns);
  if (checked) next.add(column);
  else next.delete(column);
  prefs.value = { ...prefs.value, placeColumns: PLACE_COLUMNS.filter((c) => next.has(c)) };
}

function onTopN(event: Event): void {
  const n = Math.floor(Number((event.target as HTMLInputElement).value));
  prefs.value = { ...prefs.value, topPlaces: Number.isFinite(n) && n > 0 ? Math.min(n, 200) : 1 };
}

const reasonId = (id: string) => `${uid}-${id}`;
const isOn = (id: SectionId) => selected.value.includes(id);
</script>

<template>
  <div class="map-options" data-testid="map-options" data-tour="export-map">
    <div class="controls">
      <div class="presets" role="group" :aria-label="m.presetsLabel">
        <button
          v-for="preset in PRESET_ORDER"
          :key="preset"
          type="button"
          class="preset"
          :data-preset="preset"
          @click="applyPreset(preset)"
        >
          {{ m.presets[preset] }}
        </button>
      </div>

      <fieldset class="sections">
        <legend class="eoc-label">{{ m.contentLegend }}</legend>
        <div v-for="id in SECTION_ORDER" :key="id" class="section">
          <label class="row" :class="{ disabled: !availability[id].available && !availability[id].locked }">
            <input
              type="checkbox"
              name="print-section"
              :value="id"
              :checked="isOn(id)"
              :disabled="availability[id].locked || !availability[id].available"
              :aria-describedby="
                availability[id].locked || !availability[id].available ? reasonId(id) : undefined
              "
              @change="toggle(id, ($event.target as HTMLInputElement).checked)"
            />
            <span class="name">{{ m.sections[id].name }}</span>
            <span class="what">{{ m.sections[id].description }}</span>
          </label>
          <span
            v-if="availability[id].locked || !availability[id].available"
            :id="reasonId(id)"
            class="reason"
          >{{ availability[id].locked ? m.reasons.locked : availability[id].reason }}</span>

          <div v-if="id === 'map'" class="sub toggles">
            <label v-for="key in (['legend', 'scale', 'north'] as const)" :key="key" class="check">
              <input
                type="checkbox"
                :checked="prefs[key]"
                @change="prefs = { ...prefs, [key]: ($event.target as HTMLInputElement).checked }"
              />
              <span>{{ m.mapToggles[key] }}</span>
            </label>
          </div>

          <div v-if="id === 'places' && isOn('places')" class="sub">
            <label class="check">
              <span>{{ m.topPlaces }}</span>
              <input
                class="number eoc-numeric"
                type="number"
                min="1"
                max="200"
                :value="prefs.topPlaces"
                :aria-label="m.topPlaces"
                @input="onTopN"
              />
              <span>{{ m.placesUnit }}</span>
            </label>
            <fieldset class="columns">
              <legend class="sr-only">{{ m.columnsLegend }}</legend>
              <label v-for="column in PLACE_COLUMNS" :key="column" class="check">
                <input
                  type="checkbox"
                  name="print-place-column"
                  :checked="
                    prefs.placeColumns.includes(column) &&
                    !(column === 'population' && !availability.placePopulation.available)
                  "
                  :disabled="column === 'population' && !availability.placePopulation.available"
                  :aria-describedby="
                    column === 'population' && !availability.placePopulation.available
                      ? reasonId('placePopulation')
                      : undefined
                  "
                  @change="toggleColumn(column, ($event.target as HTMLInputElement).checked)"
                />
                <span>{{ m.placeColumns[column] }}</span>
              </label>
              <span
                v-if="!availability.placePopulation.available"
                :id="reasonId('placePopulation')"
                class="reason"
              >{{ availability.placePopulation.reason }}</span>
            </fieldset>
          </div>

          <div v-if="id === 'notes' && isOn('notes')" class="sub">
            <textarea
              v-model="notes"
              class="notes"
              rows="3"
              maxlength="1500"
              :aria-label="m.notesLabel"
              :placeholder="m.notesPlaceholder"
            ></textarea>
          </div>
        </div>
      </fieldset>

      <!-- Announced once per change in count, not on every re-render of the preview -->
      <p class="sr-only" role="status" aria-live="polite" data-testid="section-count">{{ countText }}</p>
    </div>

    <div class="preview" aria-hidden="true" data-testid="map-preview">
      <span class="eoc-label">{{ m.previewLabel }}</span>
      <div class="map-preview">
        <div class="page theme-light">
          <MapPrintBody
            preview
            :snapshot="snapshot"
            :model="model"
            :prefs="prefs"
            :sections="selected"
            :notes="notes"
            :selected-district="selectedDistrict"
            :lang="lang"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-options {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--eoc-pad-panel);
}
@media (min-width: 860px) {
  .map-options {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}
.controls {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
  min-width: 0;
}
.presets {
  display: flex;
  flex-wrap: wrap;
  gap: var(--eoc-gap-x);
}
.preset {
  min-height: var(--eoc-target-min);
  padding: 0 var(--eoc-pad-panel);
  background: var(--eoc-bg-card);
  color: var(--eoc-text-primary);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  border-radius: var(--eoc-radius-control);
  font: inherit;
  cursor: pointer;
}
.preset:hover {
  background: var(--eoc-bg-hover);
}
fieldset {
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}
legend {
  padding: 0;
  margin-bottom: var(--eoc-gap-y);
}
.section {
  display: flex;
  flex-direction: column;
}
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0 var(--eoc-gap-x);
  min-height: var(--eoc-target-min);
  padding: 2px 0;
  cursor: pointer;
}
.row.disabled {
  cursor: not-allowed;
}
.row:focus-within,
.check:focus-within {
  outline: 2px solid var(--eoc-border-focus);
  outline-offset: 2px;
  border-radius: var(--eoc-radius-control);
}
.name {
  font-weight: var(--eoc-fw-semibold);
}
.what,
.reason {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
.reason {
  padding-left: 22px;
}
.sub {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
  padding: 2px 0 var(--eoc-gap-y) 22px;
}
.toggles {
  flex-direction: row;
  flex-wrap: wrap;
  gap: var(--eoc-gap-x) var(--eoc-pad-panel);
}
.columns {
  display: flex;
  flex-wrap: wrap;
  gap: 0 var(--eoc-pad-panel);
}
.check {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  min-height: var(--eoc-target-min);
}
.number {
  width: 64px;
  min-height: var(--eoc-target-min);
  padding: 0 var(--eoc-gap-x);
  background: var(--eoc-bg-sunken);
  color: var(--eoc-text-primary);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  border-radius: var(--eoc-radius-control);
  font: inherit;
}
.notes {
  width: 100%;
  padding: var(--eoc-gap-x);
  background: var(--eoc-bg-sunken);
  color: var(--eoc-text-primary);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  border-radius: var(--eoc-radius-control);
  font: inherit;
  resize: vertical;
}
.preview {
  display: none;
  min-width: 0;
}
@media (min-width: 860px) {
  .preview {
    display: block;
  }
}
.map-preview {
  margin-top: var(--eoc-gap-y);
  max-height: 62vh;
  overflow: auto;
  background: var(--eoc-bg-canvas);
  border: var(--eoc-border-width) solid var(--eoc-border);
  padding: var(--eoc-gap-x);
}
/* The page is laid out at full width and shrunk, so what you see is how it breaks */
.page {
  width: 297mm;
  zoom: 0.32;
  padding: 8mm;
  background: var(--eoc-bg-panel);
  color: var(--eoc-text-primary);
}
</style>
