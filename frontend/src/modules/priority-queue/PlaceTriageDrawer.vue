<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElSelect,
} from "element-plus";
import {
  type AttentionStatus,
  type PlaceCategory,
  type PlaceRead,
  type PlaceTriageUpdate,
  type VulnerabilityGroup,
} from "../../api/client";
import Icon0 from "../../components/Icon0.vue";
import {
  CATEGORY_ICON_MAP,
} from "../../components/icons0Registry";
import { useI18n } from "../../i18n/useI18n";

const props = defineProps<{
  visible: boolean;
  place: PlaceRead | null;
}>();

const emit = defineEmits<{
  (e: "update:visible", value: boolean): void;
  (e: "save-triage", placeId: string, payload: PlaceTriageUpdate): void;
}>();

const { t, locale, localizePlaceName } = useI18n();
const isSaving = ref<boolean>(false);
const coordsCopied = ref<boolean>(false);
const copy = computed(() => locale.value === "es" ? {
  title: "Evaluación y despacho", subtitle: "Actualiza la atención y las necesidades del lugar.",
  status: "Estado de atención", urgency: "Nivel de urgencia", population: "Personas por atender",
  notes: "Notas de la evaluación", priority: "Prioridad estimada", breakdown: "Cómo se calcula",
  location: "Ubicación", route: "Cómo llegar", coordinates: "Copiar coordenadas",
  details: "Datos del lugar", save: "Guardar evaluación", close: "Cancelar",
  pending: "Pendiente", progress: "En atención", attended: "Atendido",
  noteTemplates: "Añadir una nota rápida", reduction: "Atendido: se aplica un factor de 0.20.",
  scoreHint: "Se actualiza al ajustar la evaluación.", reset: "Restablecer", points: "puntos",
} : {
  title: "Assessment & dispatch", subtitle: "Update this location’s status and support needs.",
  status: "Response status", urgency: "Urgency level", population: "People needing support",
  notes: "Assessment notes", priority: "Estimated priority", breakdown: "How it’s calculated",
  location: "Location", route: "Directions", coordinates: "Copy coordinates",
  details: "Location data", save: "Save assessment", close: "Cancel",
  pending: "Pending", progress: "In progress", attended: "Attended",
  noteTemplates: "Add a quick note", reduction: "Attended: a 0.20 factor is applied.",
  scoreHint: "Updates as you adjust the assessment.", reset: "Reset", points: "points",
});

const statusOptions = computed(() => [
  { value: "pending", label: copy.value.pending },
  { value: "in_progress", label: copy.value.progress },
  { value: "attended", label: copy.value.attended },
]);

const formState = reactive<{
  attention_status: AttentionStatus;
  urgency_level: number;
  estimated_vulnerable_count: number;
  institution_notes: string;
}>({
  attention_status: "pending",
  urgency_level: 3,
  estimated_vulnerable_count: 0,
  institution_notes: "",
});

watch(
  () => [props.place, props.visible] as const,
  ([place, visible]) => {
    if (place && visible) {
      formState.attention_status = place.attention_status;
      formState.urgency_level = place.urgency_level;
      formState.estimated_vulnerable_count = place.estimated_vulnerable_count;
      formState.institution_notes = place.institution_notes ?? "";
    }
  },
  { immediate: true },
);

const urgencyMultipliers: Record<number, number> = {
  1: 0.6,
  2: 0.8,
  3: 1.0,
  4: 1.3,
  5: 1.6,
};

const scoreTerms = computed(() => {
  if (!props.place) {
    return {
      wCat: 0,
      mUrg: 1.0,
      weightedCat: 0,
      popTerm: 0,
      clusterTerm: 0,
      rawTotal: 0,
      finalScore: 0,
      delta: 0,
    };
  }
  const wCat = props.place.category_weight;
  const mUrg = urgencyMultipliers[formState.urgency_level] ?? 1.0;
  const weightedCat = wCat * mUrg;
  const pVuln = Math.max(0, formState.estimated_vulnerable_count);
  const popTerm = 15 * Math.log(1 + pVuln);
  const n500m = props.place.nearby_places_count ?? 0;
  const clusterTerm = 5 * n500m;
  const rawTotal = weightedCat + popTerm + clusterTerm;
  const finalScore =
    formState.attention_status === "attended" ? rawTotal * 0.2 : rawTotal;
  const delta = finalScore - props.place.priority_score;

  return {
    wCat,
    mUrg,
    weightedCat,
    popTerm,
    clusterTerm,
    rawTotal,
    finalScore,
    delta,
  };
});

const prioritySeverity = computed(() => {
  const score = scoreTerms.value.finalScore;
  const urg = formState.urgency_level;
  if (score >= 130 || urg >= 5) {
    return {
      level: "critical",
      label: t.value.drawer.severityCritical,
      color: "#ef4444",
      bg: "rgba(239, 68, 68, 0.15)",
      border: "rgba(239, 68, 68, 0.4)",
    };
  }
  if (score >= 100 || urg >= 4) {
    return {
      level: "high",
      label: t.value.drawer.severityHigh,
      color: "#f97316",
      bg: "rgba(249, 115, 22, 0.15)",
      border: "rgba(249, 115, 22, 0.4)",
    };
  }
  if (score >= 70) {
    return {
      level: "medium",
      label: t.value.drawer.severityMedium,
      color: "#eab308",
      bg: "rgba(234, 179, 8, 0.15)",
      border: "rgba(234, 179, 8, 0.4)",
    };
  }
  return {
    level: "low",
    label: t.value.drawer.severityLow,
    color: "#10b981",
    bg: "rgba(16, 185, 129, 0.15)",
    border: "rgba(16, 185, 129, 0.4)",
  };
});

const placePhone = computed<string | null>(() => {
  if (!props.place?.osm_tags) return null;
  const tags = props.place.osm_tags as Record<string, string>;
  return tags.phone || tags["contact:phone"] || null;
});

function addPopulationPreset(amount: number): void {
  formState.estimated_vulnerable_count = Math.max(
    0,
    (formState.estimated_vulnerable_count || 0) + amount,
  );
}

function appendQuickNote(template: string): void {
  const existing = formState.institution_notes.trim();
  formState.institution_notes = existing
    ? `${existing} • ${template}`
    : template;
}

async function copyCoordinates(): Promise<void> {
  if (!props.place) return;
  const text = `${props.place.latitude.toFixed(5)}, ${props.place.longitude.toFixed(5)}`;
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      coordsCopied.value = true;
      setTimeout(() => {
        coordsCopied.value = false;
      }, 2000);
    }
  } catch {
    // Clipboard permission fallback
  }
}

function openGoogleMaps(): void {
  if (!props.place) return;
  const url = `https://www.google.com/maps/dir/?api=1&destination=${props.place.latitude},${props.place.longitude}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

function openWaze(): void {
  if (!props.place) return;
  const url = `https://waze.com/ul?ll=${props.place.latitude},${props.place.longitude}&navigate=yes`;
  window.open(url, "_blank", "noopener,noreferrer");
}

function handleSave(): void {
  if (!props.place) return;
  isSaving.value = true;
  try {
    emit("save-triage", props.place.id, {
      attention_status: formState.attention_status,
      urgency_level: formState.urgency_level,
      estimated_vulnerable_count: formState.estimated_vulnerable_count,
      institution_notes: formState.institution_notes.trim() || null,
    });
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <ElDialog
    :model-value="props.visible"
    :title="copy.title"
    width="min(920px, calc(100vw - 32px))"
    align-center
    append-to-body
    :close-on-click-modal="false"
    class="triage-modal"
    @update:model-value="(val) => emit('update:visible', Boolean(val))"
  >
    <template #header>
      <div class="modal-heading">
        <span class="heading-icon"><Icon0 name="shield_alert" :size="20" /></span>
        <div><h2>{{ copy.title }}</h2><p>{{ copy.subtitle }}</p></div>
      </div>
    </template>

    <div v-if="props.place" class="triage-content" data-testid="triage-drawer">
      <section class="place-overview" aria-labelledby="triage-place-name">
        <span class="place-icon"><Icon0 :name="CATEGORY_ICON_MAP[props.place.category as PlaceCategory] ?? 'map_pin'" :size="24" /></span>
        <div class="place-identity">
          <span class="place-zone"><Icon0 name="map_pin" :size="12" />{{ props.place.zone_name }}</span>
          <h3 id="triage-place-name">{{ localizePlaceName(props.place) }}</h3>
          <p>{{ t.categories[props.place.category as PlaceCategory] }}<span aria-hidden="true"> · </span>{{ t.groups[props.place.vulnerability_group as VulnerabilityGroup] }}</p>
        </div>
      </section>

      <div class="assessment-layout">
        <ElForm label-position="top" class="assessment-form" @submit.prevent="handleSave">
          <ElFormItem :label="copy.status">
            <div class="status-options" role="radiogroup" :aria-label="copy.status" data-testid="triage-status-group">
              <label v-for="option in statusOptions" :key="option.value" class="status-option" :class="{ selected: formState.attention_status === option.value }">
                <input v-model="formState.attention_status" type="radio" name="triage-status" :value="option.value" />
                <span class="radio-mark" aria-hidden="true"></span><span>{{ option.label }}</span>
              </label>
            </div>
          </ElFormItem>

          <div class="form-columns">
            <ElFormItem :label="copy.urgency">
              <ElSelect v-model="formState.urgency_level" :aria-label="copy.urgency" data-testid="triage-urgency-select">
                <ElOption v-for="(label, level) in t.urgency" :key="level" :label="label" :value="Number(level)" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem :label="copy.population">
              <ElInputNumber v-model="formState.estimated_vulnerable_count" :min="0" :max="100000" :step="10" :precision="0" :aria-label="copy.population" data-testid="triage-population-input" />
            </ElFormItem>
          </div>
          <div class="population-shortcuts" :aria-label="t.drawer.populationPresets">
            <span>{{ t.drawer.populationPresets }}</span>
            <button v-for="amount in [10, 25, 50, 100, 250]" :key="amount" type="button" @click="addPopulationPreset(amount)">+{{ amount }}</button>
            <button type="button" class="reset-population" :aria-label="copy.reset" @click="formState.estimated_vulnerable_count = 0"><Icon0 name="rotate_ccw" :size="13" /></button>
          </div>

          <ElFormItem :label="copy.notes" class="notes-field">
            <ElInput v-model="formState.institution_notes" type="textarea" :rows="3" :placeholder="t.drawer.notesPlaceholder" :aria-label="copy.notes" data-testid="triage-notes-input" />
          </ElFormItem>
          <details class="quiet-details note-templates">
            <summary>{{ copy.noteTemplates }}<Icon0 name="chevron_down" :size="14" /></summary>
            <div class="note-options"><button v-for="note in t.drawer.quickNotes" :key="note" type="button" @click="appendQuickNote(note)">{{ note }}</button></div>
          </details>
        </ElForm>

        <aside class="assessment-sidebar">
          <section class="priority-summary" :class="`severity-${prioritySeverity.level}`">
            <div class="summary-label">{{ copy.priority }}</div>
            <div class="priority-value" data-testid="preview-priority-score">{{ scoreTerms.finalScore.toFixed(1) }}<span>{{ copy.points }}</span></div>
            <span class="severity-label"><span aria-hidden="true"></span>{{ prioritySeverity.label }}</span>
            <p class="score-hint">{{ copy.scoreHint }}</p>
            <details class="quiet-details score-details" data-testid="priority-breakdown">
              <summary>{{ copy.breakdown }}<Icon0 name="chevron_down" :size="14" /></summary>
              <dl>
                <div><dt>{{ t.drawer.weightBase }} <small>×{{ scoreTerms.mUrg.toFixed(1) }}</small></dt><dd>{{ scoreTerms.weightedCat.toFixed(1) }}</dd></div>
                <div><dt>{{ t.drawer.popBonus }}</dt><dd>+{{ scoreTerms.popTerm.toFixed(1) }}</dd></div>
                <div><dt>{{ t.drawer.clusterBonus }}</dt><dd>+{{ scoreTerms.clusterTerm.toFixed(1) }}</dd></div>
              </dl>
              <p v-if="formState.attention_status === 'attended'" class="score-hint">{{ copy.reduction }}</p>
            </details>
          </section>

          <section class="location-actions" data-testid="prominent-nav-bar">
            <h4>{{ copy.route }}</h4>
            <div class="route-buttons">
              <button type="button" @click="openGoogleMaps"><Icon0 name="navigation" :size="15" />Google Maps</button>
              <button type="button" @click="openWaze"><Icon0 name="compass" :size="15" />Waze</button>
            </div>
            <button type="button" class="coordinates-button" @click="copyCoordinates"><Icon0 :name="coordsCopied ? 'circle_check' : 'copy'" :size="14" />{{ coordsCopied ? t.drawer.coordsCopied : copy.coordinates }}</button>
            <span class="coordinates">{{ props.place.latitude.toFixed(5) }}, {{ props.place.longitude.toFixed(5) }}</span>
            <a v-if="placePhone" :href="`tel:${placePhone}`" class="phone-link"><Icon0 name="phone" :size="14" />{{ placePhone }}</a>
          </section>
        </aside>
      </div>

      <details class="quiet-details technical-details">
        <summary>{{ copy.details }}<Icon0 name="chevron_down" :size="14" /></summary>
        <div class="technical-content">
          <p>{{ t.drawer.fieldOsm }}: <code>{{ props.place.osm_type }}/{{ props.place.osm_id }}</code></p>
          <dl><div v-for="(value, key) in props.place.osm_tags" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></div></dl>
        </div>
      </details>
    </div>

    <template v-if="props.place" #footer>
      <div class="modal-footer">
        <span class="footer-context"><Icon0 name="shield_alert" :size="14" />{{ locale === 'es' ? 'Registro de atención institucional' : 'Institutional response record' }}</span>
        <div class="footer-buttons">
          <ElButton @click="emit('update:visible', false)">{{ copy.close }}</ElButton>
          <ElButton type="primary" :loading="isSaving" data-testid="save-triage-btn" @click="handleSave">{{ copy.save }}</ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.modal-heading { display: flex; align-items: center; gap: 12px; }
.heading-icon, .place-icon { display: grid; place-items: center; flex-shrink: 0; color: var(--eoc-accent); background: var(--eoc-accent-glow); border-radius: 10px; }
.heading-icon { width: 40px; height: 40px; }
.modal-heading h2 { margin: 0; font-size: 18px; line-height: 1.35; font-weight: 650; letter-spacing: -.025em; color: var(--eoc-text-primary); }
.modal-heading p { margin: 4px 0 0; font-size: 12px; color: var(--eoc-text-secondary); }
.triage-content { padding: 24px 28px 16px; }
.place-overview { display: flex; align-items: center; gap: 14px; padding-bottom: 24px; border-bottom: 1px solid var(--eoc-border-subtle); }
.place-icon { width: 48px; height: 48px; background: var(--eoc-bg-card); color: var(--eoc-text-secondary); border: 1px solid var(--eoc-border-subtle); }
.place-identity { min-width: 0; }
.place-zone { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--eoc-text-secondary); }
.place-identity h3 { margin: 5px 0; font-size: 21px; line-height: 1.3; font-weight: 650; letter-spacing: -.025em; color: var(--eoc-text-primary); overflow-wrap: anywhere; }
.place-identity p { margin: 0; color: var(--eoc-text-secondary); font-size: 12px; line-height: 1.5; }
.assessment-layout { display: grid; grid-template-columns: minmax(0, 1fr) 240px; gap: 32px; padding-top: 24px; }
.assessment-form { min-width: 0; }
.assessment-form :deep(.el-form-item) { margin-bottom: 20px; }
.assessment-form :deep(.el-form-item__label) { color: var(--eoc-text-primary); font-size: 12px; font-weight: 600; padding-bottom: 8px; line-height: 1.4; }
.assessment-form :deep(.el-form-item__content) { line-height: normal; }
.status-options { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: 100%; }
.status-option { position: relative; display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 42px; padding: 8px; border: 1px solid var(--eoc-border); border-radius: 8px; font-size: 12px; color: var(--eoc-text-secondary); cursor: pointer; transition: border-color .15s, background .15s; }
.status-option input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.radio-mark { display: grid; place-items: center; width: 13px; height: 13px; border: 1px solid var(--eoc-border); border-radius: 50%; flex-shrink: 0; }
.status-option.selected { color: var(--eoc-accent); background: var(--eoc-accent-glow); border-color: var(--eoc-accent); font-weight: 600; }
.selected .radio-mark { border-color: var(--eoc-accent); }
.selected .radio-mark::after { content: ''; width: 5px; height: 5px; border-radius: 50%; background: var(--eoc-accent); }
.status-option:focus-within, button:focus-visible, summary:focus-visible, a:focus-visible { outline: 2px solid var(--eoc-accent); outline-offset: 3px; }
.form-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-columns :deep(.el-input-number), .form-columns :deep(.el-select) { width: 100%; }
.population-shortcuts { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin: -8px 0 22px; color: var(--eoc-text-secondary); font-size: 11px; }
.population-shortcuts > span { margin-right: 3px; }
.population-shortcuts button, .note-options button { border: 1px solid var(--eoc-border-subtle); background: var(--eoc-bg-card); color: var(--eoc-text-secondary); border-radius: 5px; padding: 4px 7px; cursor: pointer; font: inherit; }
.population-shortcuts button:hover, .note-options button:hover { color: var(--eoc-accent); border-color: var(--eoc-accent); }
.reset-population { display: grid; place-items: center; min-height: 24px; }
.assessment-form :deep(.notes-field) { margin-bottom: 10px; }
.quiet-details summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; cursor: pointer; list-style: none; color: var(--eoc-text-secondary); font-size: 11px; }
.quiet-details summary::-webkit-details-marker { display: none; }
.quiet-details[open] > summary > svg { transform: rotate(180deg); }
.note-templates summary { justify-content: flex-start; }
.note-options { display: flex; flex-wrap: wrap; gap: 6px; padding-top: 12px; }
.note-options button { font-size: 11px; text-align: left; line-height: 1.5; }
.assessment-sidebar { display: flex; flex-direction: column; gap: 22px; min-width: 0; }
.priority-summary { --severity: var(--eoc-success); border-left: 2px solid var(--severity); padding-left: 18px; }
.severity-critical { --severity: var(--eoc-critical); }
.severity-high { --severity: var(--eoc-warning); }
.severity-medium { --severity: var(--eoc-warning); }
.summary-label, .location-actions h4 { font-size: 12px; font-weight: 600; color: var(--eoc-text-secondary); margin: 0; }
.priority-value { display: flex; align-items: baseline; gap: 7px; margin: 6px 0 7px; font-size: 38px; font-weight: 600; letter-spacing: -.055em; line-height: 1.15; font-variant-numeric: tabular-nums; color: var(--eoc-text-primary); }
.priority-value > span { font-size: 11px; letter-spacing: 0; font-weight: 400; color: var(--eoc-text-secondary); }
.severity-label { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--eoc-text-secondary); }
.severity-label > span { width: 6px; height: 6px; border-radius: 50%; background: var(--severity); flex-shrink: 0; }
.score-hint { font-size: 11px; color: var(--eoc-text-secondary); line-height: 1.6; margin: 10px 0 0; }
.score-details { margin-top: 14px; border-top: 1px solid var(--eoc-border-subtle); padding-top: 12px; }
.score-details dl { margin: 14px 0 0; }
.score-details dl > div { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; padding: 6px 0; font-size: 11px; }
.score-details dt { color: var(--eoc-text-secondary); }
.score-details dd { margin: 0; color: var(--eoc-text-primary); font-variant-numeric: tabular-nums; }
.score-details small { white-space: nowrap; }
.location-actions { border-top: 1px solid var(--eoc-border-subtle); padding-top: 18px; }
.route-buttons { display: flex; gap: 8px; margin-top: 10px; }
.route-buttons button { display: inline-flex; align-items: center; justify-content: center; gap: 6px; border: 1px solid var(--eoc-border); background: var(--eoc-bg-panel); color: var(--eoc-text-primary); border-radius: 6px; padding: 8px; font: inherit; font-size: 11px; cursor: pointer; flex: 1; }
.route-buttons button:hover { border-color: var(--eoc-accent); color: var(--eoc-accent); }
.coordinates-button, .phone-link { display: inline-flex; align-items: center; gap: 7px; color: var(--eoc-text-secondary); font: inherit; font-size: 11px; border: 0; background: transparent; padding: 0; text-decoration: none; cursor: pointer; margin-top: 14px; }
.coordinates-button:hover, .phone-link:hover { color: var(--eoc-accent); }
.coordinates { display: block; color: var(--eoc-text-secondary); font-family: ui-monospace, monospace; font-size: 10px; margin-top: 5px; }
.technical-details { border-top: 1px solid var(--eoc-border-subtle); margin-top: 24px; padding-top: 14px; }
.technical-content { padding-top: 8px; font-size: 11px; color: var(--eoc-text-secondary); overflow-wrap: anywhere; }
.technical-content dl { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 24px; }
.technical-content dl > div { display: grid; grid-template-columns: minmax(80px, .5fr) 1fr; gap: 8px; }
.technical-content dd { margin: 0; }
.modal-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.footer-context { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; color: var(--eoc-text-secondary); }
.footer-buttons { display: flex; gap: 8px; }
.footer-buttons :deep(.el-button--primary) { background: var(--eoc-accent); border-color: var(--eoc-accent); color: var(--eoc-text-inverse); }
.footer-buttons :deep(.el-button--primary:hover) { background: var(--eoc-accent-hover); border-color: var(--eoc-accent-hover); }
.footer-buttons :deep(.el-button + .el-button) { margin-left: 0; }
@media (max-width: 700px) {
  .triage-content { padding: 20px; }
  .assessment-layout { grid-template-columns: 1fr; gap: 24px; }
  .assessment-sidebar { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .location-actions { border-top: 0; padding-top: 0; }
  .priority-value { font-size: 32px; }
  .place-identity h3 { font-size: 18px; }
  .footer-context { display: none; }
  .modal-footer { justify-content: flex-end; }
}
@media (max-width: 420px) {
  .triage-content { padding: 16px; }
  .form-columns, .assessment-sidebar { grid-template-columns: 1fr; }
  .status-option { font-size: 11px; padding: 7px 4px; gap: 5px; }
  .form-columns { gap: 0; }
  .technical-content dl { grid-template-columns: 1fr; }
  .footer-buttons { width: 100%; }
  .footer-buttons :deep(.el-button) { flex: 1; }
  .modal-heading h2 { font-size: 16px; }
}
@media (prefers-reduced-motion: reduce) { .status-option { transition: none; } }
</style>

<style>
.el-dialog.triage-modal { --el-color-primary: var(--eoc-accent); display: flex; flex-direction: column; max-height: calc(100dvh - 48px); padding: 0; border-radius: 16px; border: 1px solid var(--eoc-border); background: var(--eoc-bg-panel); color: var(--eoc-text-primary); box-shadow: 0 24px 80px rgba(0, 0, 0, .22); overflow: hidden; }
.triage-modal .el-dialog__header { margin-right: 0; padding: 22px 56px 20px 28px; border-bottom: 1px solid var(--eoc-border-subtle); flex-shrink: 0; }
.triage-modal .el-dialog__headerbtn { top: 20px; right: 18px; width: 32px; height: 32px; }
.triage-modal .el-dialog__body { padding: 0; overflow-y: auto; min-height: 0; color: var(--eoc-text-primary); }
.triage-modal .el-dialog__footer { padding: 16px 28px; border-top: 1px solid var(--eoc-border-subtle); flex-shrink: 0; }
.triage-modal .el-input__wrapper, .triage-modal .el-select__wrapper { min-height: 38px; border-radius: 7px; }
.triage-modal .el-textarea__inner { border-radius: 7px; font-family: inherit; font-size: 12px; line-height: 1.6; padding: 10px 12px; }
@media (max-width: 700px) {
  .triage-modal .el-dialog__header { padding: 18px 50px 18px 20px; }
  .triage-modal .el-dialog__footer { padding: 14px 20px; }
}
</style>
