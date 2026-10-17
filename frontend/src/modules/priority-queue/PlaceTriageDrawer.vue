<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElSelect,
  ElTag,
} from "element-plus";
import {
  type AttentionStatus,
  type PlaceCategory,
  type PlaceRead,
  type PlaceTriageUpdate,
  type VulnerabilityGroup,
  type PlaceActivityRead,
  type InstitutionAccountRead,
} from "../../api/client";
import Icon0 from "../../components/Icon0.vue";
import {
  CATEGORY_ICON_MAP,
} from "../../components/icons0Registry";
import { useI18n } from "../../i18n/useI18n";
import {
  exposedPopulationState,
  exposureRadiusMeters,
  formatExposureValue,
  vulnerableExposureBreakdown,
  type PopulationExposureState,
} from "./populationExposure";

const props = withDefaults(defineProps<{
  visible: boolean;
  place: PlaceRead | null;
  account?: InstitutionAccountRead | null;
  activities?: PlaceActivityRead[];
  activitiesLoading?: boolean;
  activitiesError?: string | null;
}>(), {
  account: null,
  activities: () => [],
  activitiesLoading: false,
  activitiesError: null,
});

const emit = defineEmits<{
  (e: "update:visible", value: boolean): void;
  (e: "save-triage", placeId: string, payload: PlaceTriageUpdate): void;
  (e: "request-access"): void;
}>();

const { t, locale, describePlace } = useI18n();
const placeName = computed(() =>
  describePlace(props.place ?? { name: "", category: undefined }),
);
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
  activity: "Acción de coordinación", timeline: "Bitácora de coordinación", noActivity: "Aún no hay acciones registradas.",
  actionTypes: { reported: "Reportar condición", en_route: "Unidad en camino", on_scene: "Unidad en el lugar", needs_support: "Solicitar apoyo", resource_available: "Recurso disponible", update: "Actualizar evaluación", resolved: "Atención resuelta" },
  accessRequired: "Inicia sesión para registrar una acción.", verificationRequired: "La organización todavía debe ser verificada para publicar reportes oficiales.",
  openAccess: "Acceso institucional", verified: "Organización verificada", verifiedBy: "Registrado por", noSensitive: "No incluyas datos personales de pacientes o personas afectadas.",
  verificationDisclaimer: "La verificación identifica a la organización, no confirma la exactitud del reporte. El estado del mapa refleja la última actualización, no un consenso multiagencia.",
} : {
  title: "Assessment & dispatch", subtitle: "Update this location’s status and support needs.",
  status: "Response status", urgency: "Urgency level", population: "People needing support",
  notes: "Assessment notes", priority: "Estimated priority", breakdown: "How it’s calculated",
  location: "Location", route: "Directions", coordinates: "Copy coordinates",
  details: "Location data", save: "Save assessment", close: "Cancel",
  pending: "Pending", progress: "In progress", attended: "Attended",
  noteTemplates: "Add a quick note", reduction: "Attended: a 0.20 factor is applied.",
  scoreHint: "Updates as you adjust the assessment.", reset: "Reset", points: "points",
  activity: "Coordination action", timeline: "Coordination log", noActivity: "No actions have been recorded yet.",
  actionTypes: { reported: "Report a condition", en_route: "Unit en route", on_scene: "Unit on scene", needs_support: "Request support", resource_available: "Resource available", update: "Update assessment", resolved: "Response resolved" },
  accessRequired: "Sign in to record an action.", verificationRequired: "The organization must be verified before it can publish official reports.",
  openAccess: "Institutional access", verified: "Verified organization", verifiedBy: "Recorded by", noSensitive: "Do not include personal data about patients or affected people.",
  verificationDisclaimer: "Verification confirms the organization’s identity, not report accuracy. The map status is the latest update, not multi-agency consensus.",
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
  activity_type: "reported" | "en_route" | "on_scene" | "needs_support" | "resource_available" | "update" | "resolved";
}>({
  attention_status: "pending",
  urgency_level: 3,
  estimated_vulnerable_count: 0,
  institution_notes: "",
  activity_type: "update",
});

watch(
  () => [props.place, props.visible] as const,
  ([place, visible]) => {
    if (place && visible) {
      formState.attention_status = place.attention_status;
      formState.urgency_level = place.urgency_level;
      formState.estimated_vulnerable_count = place.estimated_vulnerable_count;
      formState.institution_notes = place.institution_notes ?? "";
      formState.activity_type = "update";
    }
  },
  { immediate: true },
);

watch(() => formState.activity_type, (activityType) => {
  if (["en_route", "on_scene", "needs_support"].includes(activityType)) {
    formState.attention_status = "in_progress";
  } else if (activityType === "resolved") {
    formState.attention_status = "attended";
  }
});

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

// Colour comes from the .severity-* CSS classes, which are token-driven.
const prioritySeverity = computed(() => {
  const score = scoreTerms.value.finalScore;
  const urg = formState.urgency_level;
  if (score >= 130 || urg >= 5) {
    return { level: "critical", label: t.value.drawer.severityCritical };
  }
  if (score >= 100 || urg >= 4) {
    return { level: "high", label: t.value.drawer.severityHigh };
  }
  if (score >= 70) {
    return { level: "medium", label: t.value.drawer.severityMedium };
  }
  return { level: "low", label: t.value.drawer.severityLow };
});

const exposedPopulation = computed(() => exposedPopulationState(props.place));
const exposureBreakdown = computed(() =>
  vulnerableExposureBreakdown(props.place),
);
const exposureRadius = computed(() => exposureRadiusMeters(props.place));

/** Headline figure, or the reason the census cannot supply one. */
const exposureTotalLabel = computed<string>(() => {
  const state = exposedPopulation.value;
  if (state.kind === "estimate") {
    return formatExposureValue(state.value, locale.value);
  }
  const reason =
    state.kind === "withheld"
      ? t.value.exposure.withheld
      : t.value.exposure.noCoverage;
  return `— ${reason}`;
});

/**
 * Breakdown figures carry the em dash alone: the headline above already names
 * why the figures are missing, and an unknown is never shown as zero.
 */
function exposureFigure(state: PopulationExposureState): string {
  return state.kind === "estimate"
    ? formatExposureValue(state.value, locale.value)
    : "—";
}

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
  if (props.account?.institution.verification_status !== "verified") {
    emit("request-access");
    return;
  }
  isSaving.value = true;
  try {
    emit("save-triage", props.place.id, {
      attention_status: formState.attention_status,
      activity_type: formState.activity_type,
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
          <span class="place-zone"><Icon0 name="map_pin" :size="12" />{{ props.place.zone_name }}<template v-if="placeName.hint"><span aria-hidden="true"> · </span>{{ placeName.hint }}</template></span>
          <h3 id="triage-place-name">{{ placeName.label }}</h3>
          <p>{{ t.categories[props.place.category as PlaceCategory] }}<span aria-hidden="true"> · </span>{{ t.groups[props.place.vulnerability_group as VulnerabilityGroup] }}</p>
        </div>
      </section>

      <div class="assessment-layout">
        <ElForm label-position="top" class="assessment-form" @submit.prevent="handleSave">
          <ElFormItem :label="copy.activity">
            <ElSelect v-model="formState.activity_type" size="small" :aria-label="copy.activity" data-testid="triage-activity-select">
              <ElOption v-for="(label, value) in copy.actionTypes" :key="value" :label="label" :value="value" />
            </ElSelect>
          </ElFormItem>
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
              <ElSelect v-model="formState.urgency_level" size="small" :aria-label="copy.urgency" data-testid="triage-urgency-select">
                <ElOption v-for="(label, level) in t.urgency" :key="level" :label="label" :value="Number(level)" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem :label="copy.population">
              <ElInputNumber v-model="formState.estimated_vulnerable_count" :min="0" :max="100000" :step="10" :precision="0" size="small" :aria-label="copy.population" data-testid="triage-population-input" />
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
            <div class="summary-label eoc-label">{{ copy.priority }}</div>
            <div class="priority-value eoc-numeric" data-testid="preview-priority-score">{{ scoreTerms.finalScore.toFixed(1) }}<span>{{ copy.points }}</span></div>
            <span class="severity-label"><span aria-hidden="true"></span>{{ prioritySeverity.label }}</span>
            <p class="score-hint">{{ copy.scoreHint }}</p>
            <details class="quiet-details score-details" data-testid="priority-breakdown">
              <summary>{{ copy.breakdown }}<Icon0 name="chevron_down" :size="14" /></summary>
              <dl class="eoc-numeric">
                <div><dt>{{ t.drawer.weightBase }} <small>×{{ scoreTerms.mUrg.toFixed(1) }}</small></dt><dd>{{ scoreTerms.weightedCat.toFixed(1) }}</dd></div>
                <div><dt>{{ t.drawer.popBonus }}</dt><dd>+{{ scoreTerms.popTerm.toFixed(1) }}</dd></div>
                <div><dt>{{ t.drawer.clusterBonus }}</dt><dd>+{{ scoreTerms.clusterTerm.toFixed(1) }}</dd></div>
              </dl>
              <p v-if="formState.attention_status === 'attended'" class="score-hint">{{ copy.reduction }}</p>
            </details>
          </section>

          <section class="census-exposure" data-testid="exposure-estimate">
            <div class="summary-label eoc-label">{{ t.exposure.panelTitle }}</div>
            <div
              class="exposure-value eoc-numeric"
              :class="{ 'is-unknown': exposedPopulation.kind !== 'estimate' }"
              :title="exposedPopulation.kind === 'estimate' ? t.exposure.methodNote : t.exposure.unknownHint"
              data-testid="exposure-total"
            >{{ exposureTotalLabel }}</div>
            <span v-if="exposureRadius !== null" class="exposure-radius eoc-numeric">{{ t.exposure.radiusLabel }} {{ exposureRadius }} m</span>
            <dl class="exposure-breakdown eoc-numeric" data-testid="exposure-breakdown">
              <div><dt>{{ t.exposure.olderAdults }}</dt><dd>{{ exposureFigure(exposureBreakdown.olderAdults) }}</dd></div>
              <div><dt>{{ t.exposure.youngChildren }}</dt><dd>{{ exposureFigure(exposureBreakdown.youngChildren) }}</dd></div>
              <div><dt>{{ t.exposure.personsWithDisability }}</dt><dd>{{ exposureFigure(exposureBreakdown.personsWithDisability) }}</dd></div>
            </dl>
            <p class="score-hint">{{ t.exposure.methodNote }}</p>
          </section>

          <section class="location-actions" data-testid="prominent-nav-bar">
            <h4>{{ copy.route }}</h4>
            <div class="route-buttons">
              <button type="button" @click="openGoogleMaps"><Icon0 name="navigation" :size="15" />Google Maps</button>
              <button type="button" @click="openWaze"><Icon0 name="compass" :size="15" />Waze</button>
            </div>
            <button type="button" class="coordinates-button" @click="copyCoordinates"><Icon0 :name="coordsCopied ? 'circle_check' : 'copy'" :size="14" />{{ coordsCopied ? t.drawer.coordsCopied : copy.coordinates }}</button>
            <span class="coordinates eoc-numeric">{{ props.place.latitude.toFixed(5) }}, {{ props.place.longitude.toFixed(5) }}</span>
            <a v-if="placePhone" :href="`tel:${placePhone}`" class="phone-link"><Icon0 name="phone" :size="14" />{{ placePhone }}</a>
          </section>
        </aside>
      </div>

      <section class="activity-log" aria-labelledby="activity-log-title" data-testid="place-activity-log">
        <div class="activity-log-heading">
          <div><h3 id="activity-log-title">{{ copy.timeline }}</h3><p>{{ placeName.label }}</p></div>
          <span class="activity-count eoc-numeric">{{ props.activities.length }}</span>
        </div>
        <p class="activity-disclaimer">{{ copy.verificationDisclaimer }}</p>
        <ElAlert v-if="!props.account" :title="copy.accessRequired" type="info" show-icon :closable="false" class="access-hint">
          <template #default><button type="button" class="access-hint-link" @click="emit('request-access')">{{ copy.openAccess }}</button></template>
        </ElAlert>
        <ElAlert v-else-if="props.account.institution.verification_status !== 'verified'" :title="copy.verificationRequired" type="warning" show-icon :closable="false" class="access-hint" />
        <ElAlert v-if="props.activitiesError" :title="props.activitiesError" type="warning" :closable="false" />
        <div v-else-if="props.activitiesLoading" class="activity-loading">{{ locale === 'es' ? 'Cargando bitácora…' : 'Loading activity…' }}</div>
        <div v-else-if="props.activities.length === 0" class="activity-empty">{{ copy.noActivity }}</div>
        <ol v-else class="activity-list">
          <li v-for="item in props.activities" :key="item.id" class="activity-entry">
            <span class="activity-marker" aria-hidden="true"></span>
            <div class="activity-main">
              <div class="activity-title-row">
                <strong>{{ copy.actionTypes[item.activity_type] }}</strong>
                <time :datetime="item.created_at">{{ new Intl.DateTimeFormat(locale === 'es' ? 'es-SV' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(item.created_at)) }}</time>
              </div>
              <div class="activity-byline"><b>{{ item.organization.name }}</b><span>·</span>{{ copy.verifiedBy }} {{ item.actor_name }}<ElTag v-if="item.organization.verification_status === 'verified'" size="small" type="success" effect="plain">{{ copy.verified }}</ElTag></div>
              <p v-if="item.notes" class="activity-notes">{{ item.notes }}</p>
              <div v-if="item.attention_status || item.urgency_level || item.estimated_vulnerable_count !== null" class="activity-snapshot">
                <span v-if="item.attention_status">{{ statusOptions.find((option) => option.value === item.attention_status)?.label ?? item.attention_status }}</span>
                <span v-if="item.urgency_level">{{ copy.urgency }}: {{ t.urgency[item.urgency_level] ?? item.urgency_level }}</span>
                <span v-if="item.estimated_vulnerable_count != null">{{ item.estimated_vulnerable_count }} {{ locale === 'es' ? 'personas' : 'people' }}</span>
              </div>
            </div>
          </li>
        </ol>
        <div v-if="props.account?.institution.verification_status === 'verified'" class="activity-compose-note">{{ copy.noSensitive }}</div>
      </section>

      <details class="quiet-details technical-details">
        <summary>{{ copy.details }}<Icon0 name="chevron_down" :size="14" /></summary>
        <div class="technical-content">
          <dl><div v-for="(value, key) in props.place.osm_tags" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></div></dl>
        </div>
      </details>
    </div>

    <template v-if="props.place" #footer>
      <div class="modal-footer">
        <span class="footer-context"><Icon0 name="shield_alert" :size="14" />{{ locale === 'es' ? 'Registro de atención institucional' : 'Institutional response record' }}</span>
        <div class="footer-buttons">
          <ElButton @click="emit('update:visible', false)">{{ copy.close }}</ElButton>
          <ElButton v-if="props.account?.institution.verification_status === 'verified'" type="primary" :loading="isSaving" data-testid="save-triage-btn" @click="handleSave">{{ copy.save }}</ElButton>
          <ElButton v-else type="primary" data-testid="institution-access-btn" @click="emit('request-access')">{{ copy.openAccess }}</ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.modal-heading { display: flex; align-items: center; gap: var(--eoc-pad-panel); }
.heading-icon, .place-icon { display: grid; place-items: center; flex-shrink: 0; color: var(--eoc-accent); background: var(--eoc-accent-glow); border-radius: var(--eoc-radius-control); }
.heading-icon { width: 28px; height: 28px; }
.modal-heading h2 { margin: 0; font-size: var(--eoc-fs-heading); line-height: 1.3; font-weight: var(--eoc-fw-semibold); color: var(--eoc-text-primary); }
.modal-heading p { margin: 2px 0 0; font-size: var(--eoc-fs-micro); color: var(--eoc-text-secondary); }
.triage-content { padding: var(--eoc-pad-panel) 14px; }
.place-overview { display: flex; align-items: center; gap: var(--eoc-pad-panel); padding-bottom: var(--eoc-pad-panel); border-bottom: var(--eoc-border-width) solid var(--eoc-border-subtle); }
.place-icon { width: 32px; height: 32px; background: var(--eoc-bg-card); color: var(--eoc-icon); border: var(--eoc-border-width) solid var(--eoc-border); }
.place-identity { min-width: 0; }
.place-zone { display: flex; align-items: center; gap: 4px; font-size: var(--eoc-fs-micro); color: var(--eoc-text-secondary); }
.place-identity h3 { margin: 2px 0; font-size: var(--eoc-fs-title); line-height: 1.3; font-weight: var(--eoc-fw-semibold); color: var(--eoc-text-primary); overflow-wrap: anywhere; }
.place-identity p { margin: 0; color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); line-height: 1.4; }
.assessment-layout { display: grid; grid-template-columns: minmax(0, 1fr) 240px; gap: 18px; padding-top: var(--eoc-pad-panel); }
.assessment-form { min-width: 0; }
.assessment-form :deep(.el-form-item) { margin-bottom: var(--eoc-pad-panel); }
.assessment-form :deep(.el-form-item__label) { color: var(--eoc-text-primary); font-size: var(--eoc-fs-micro); font-weight: var(--eoc-fw-semibold); padding-bottom: 4px; line-height: 1.4; }
.assessment-form :deep(.el-form-item__content) { line-height: normal; }
.status-options { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--eoc-gap-x); width: 100%; }
.status-option { position: relative; display: flex; align-items: center; justify-content: center; gap: var(--eoc-gap-x); min-height: calc(var(--eoc-control-h) + 6px); padding: 4px; border: var(--eoc-border-width) solid var(--eoc-border); border-radius: var(--eoc-radius-button); font-size: var(--eoc-fs-body); color: var(--eoc-text-secondary); cursor: pointer; transition: border-color var(--eoc-transition), background-color var(--eoc-transition); }
.status-option input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.radio-mark { display: grid; place-items: center; width: 12px; height: 12px; border: var(--eoc-border-width) solid var(--eoc-border-strong); border-radius: var(--eoc-radius-pill); flex-shrink: 0; }
.status-option.selected { color: var(--eoc-text-primary); background: var(--eoc-bg-selected); border-color: var(--eoc-accent); font-weight: var(--eoc-fw-semibold); }
.selected .radio-mark { border-color: var(--eoc-accent); }
.selected .radio-mark::after { content: ''; width: 5px; height: 5px; border-radius: var(--eoc-radius-pill); background: var(--eoc-accent); }
.status-option:focus-within, button:focus-visible, summary:focus-visible, a:focus-visible { outline: 2px solid var(--eoc-border-focus); outline-offset: 2px; }
.form-columns { display: grid; grid-template-columns: 1fr 1fr; gap: var(--eoc-pad-panel); }
.form-columns :deep(.el-input-number), .form-columns :deep(.el-select) { width: 100%; }
.population-shortcuts { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin: -6px 0 var(--eoc-pad-panel); color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); }
.population-shortcuts > span { margin-right: 3px; }
.population-shortcuts button, .note-options button { border: var(--eoc-border-width) solid var(--eoc-border); background: var(--eoc-bg-card); color: var(--eoc-text-secondary); border-radius: var(--eoc-radius-control); padding: var(--eoc-pad-button); cursor: pointer; font: inherit; font-size: var(--eoc-fs-micro); }
.population-shortcuts button:hover, .note-options button:hover { color: var(--eoc-text-primary); border-color: var(--eoc-border-strong); background: var(--eoc-bg-hover); }
.population-shortcuts button { font-variant-numeric: tabular-nums; }
.reset-population { display: grid; place-items: center; min-height: var(--eoc-control-h); }
.assessment-form :deep(.notes-field) { margin-bottom: var(--eoc-gap-y); }
.quiet-details summary { display: flex; align-items: center; justify-content: space-between; gap: var(--eoc-gap-x); cursor: pointer; list-style: none; color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); }
.quiet-details summary::-webkit-details-marker { display: none; }
.quiet-details[open] > summary > svg { transform: rotate(180deg); }
.note-templates summary { justify-content: flex-start; }
.note-options { display: flex; flex-wrap: wrap; gap: var(--eoc-gap-x); padding-top: var(--eoc-gap-x); }
.note-options button { text-align: left; line-height: 1.4; }
.assessment-sidebar { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.priority-summary { --severity: var(--eoc-success); border-left: 2px solid var(--severity); padding-left: var(--eoc-pad-panel); }
.severity-critical { --severity: var(--eoc-critical); }
.severity-high { --severity: var(--eoc-warning); }
.severity-medium { --severity: var(--eoc-warning); }
.location-actions h4 { font-size: var(--eoc-fs-micro); font-weight: var(--eoc-fw-semibold); color: var(--eoc-text-label); letter-spacing: 0.09em; text-transform: uppercase; margin: 0; }
.summary-label { margin: 0; }
.priority-value { display: flex; align-items: baseline; gap: var(--eoc-gap-x); margin: 4px 0; font-size: var(--eoc-fs-heading); font-weight: var(--eoc-fw-semibold); line-height: 1.2; color: var(--eoc-text-primary); }
.priority-value > span { font-size: var(--eoc-fs-micro); font-weight: var(--eoc-fw-regular); color: var(--eoc-text-secondary); }
.severity-label { display: flex; align-items: center; gap: var(--eoc-gap-x); font-size: var(--eoc-fs-micro); color: var(--eoc-text-secondary); }
.severity-label > span { width: 6px; height: 6px; border-radius: var(--eoc-radius-pill); background: var(--severity); flex-shrink: 0; }
.score-hint { font-size: var(--eoc-fs-micro); color: var(--eoc-text-secondary); line-height: 1.5; margin: var(--eoc-gap-x) 0 0; }
.score-details { margin-top: var(--eoc-pad-panel); border-top: var(--eoc-border-width) solid var(--eoc-border-subtle); padding-top: var(--eoc-gap-x); }
.score-details dl { margin: var(--eoc-gap-x) 0 0; }
.score-details dl > div { display: flex; align-items: baseline; justify-content: space-between; gap: var(--eoc-gap-x); padding: 3px 0; font-size: var(--eoc-fs-micro); }
.score-details dt { color: var(--eoc-text-secondary); }
.score-details dd { margin: 0; color: var(--eoc-text-primary); font-variant-numeric: tabular-nums; }
.score-details small { white-space: nowrap; }
.census-exposure, .location-actions { border-top: var(--eoc-border-width) solid var(--eoc-border-subtle); padding-top: var(--eoc-pad-panel); }
.exposure-value { margin: 4px 0; font-size: var(--eoc-fs-heading); font-weight: var(--eoc-fw-semibold); line-height: 1.2; color: var(--eoc-text-primary); }
/* An unknown figure never borrows the headline weight of a real estimate */
.exposure-value.is-unknown { font-size: var(--eoc-fs-body); font-weight: var(--eoc-fw-regular); color: var(--eoc-text-muted); }
.exposure-radius { display: block; color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); }
.exposure-breakdown { margin: var(--eoc-gap-x) 0 0; }
.exposure-breakdown > div { display: flex; align-items: baseline; justify-content: space-between; gap: var(--eoc-gap-x); padding: 3px 0; font-size: var(--eoc-fs-micro); }
.exposure-breakdown dt { color: var(--eoc-text-secondary); }
.exposure-breakdown dd { margin: 0; color: var(--eoc-text-primary); font-variant-numeric: tabular-nums; }
.route-buttons { display: flex; gap: var(--eoc-gap-x); margin-top: var(--eoc-gap-x); }
.route-buttons button { display: inline-flex; align-items: center; justify-content: center; gap: var(--eoc-gap-x); height: var(--eoc-control-h); border: var(--eoc-border-width) solid var(--eoc-border); background: var(--eoc-bg-card); color: var(--eoc-text-primary); border-radius: var(--eoc-radius-button); padding: var(--eoc-pad-button); font: inherit; font-size: var(--eoc-fs-micro); cursor: pointer; flex: 1; }
.route-buttons button:hover { border-color: var(--eoc-border-strong); background: var(--eoc-bg-hover); }
.coordinates-button, .phone-link { display: inline-flex; align-items: center; gap: var(--eoc-gap-x); color: var(--eoc-text-secondary); font: inherit; font-size: var(--eoc-fs-micro); border: 0; background: transparent; padding: 0; text-decoration: none; cursor: pointer; margin-top: var(--eoc-pad-panel); }
.coordinates-button:hover, .phone-link:hover { color: var(--eoc-accent-text); }
.coordinates { display: block; color: var(--eoc-text-secondary); font-family: var(--eoc-font-mono); font-size: var(--eoc-fs-micro); margin-top: 4px; }
.activity-log { margin-top: var(--eoc-pad-panel); padding-top: var(--eoc-pad-panel); border-top: var(--eoc-border-width) solid var(--eoc-border-subtle); }
.activity-log-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--eoc-gap-x); }
.activity-log-heading h3 { margin: 0; color: var(--eoc-text-primary); font-size: var(--eoc-fs-title); font-weight: var(--eoc-fw-semibold); }
.activity-log-heading p { margin: 2px 0 0; color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); }
.activity-disclaimer { margin: -2px 0 var(--eoc-gap-x); color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); line-height: 1.4; }
.activity-count { min-width: var(--eoc-icon-btn); height: var(--eoc-control-h); display: grid; place-items: center; border: var(--eoc-border-width) solid var(--eoc-border); border-radius: var(--eoc-radius-control); color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); }
.activity-list { list-style: none; margin: 0; padding: 0 0 0 4px; }
.activity-entry { position: relative; display: flex; gap: var(--eoc-pad-panel); padding: var(--eoc-gap-y) 0 var(--eoc-pad-panel); }
.activity-entry:not(:last-child)::before { content: ''; position: absolute; left: 4px; top: 17px; bottom: -1px; width: var(--eoc-border-width); background: var(--eoc-border); }
.activity-marker { position: relative; z-index: 1; flex: 0 0 9px; width: 9px; height: 9px; margin-top: 4px; border: 2px solid var(--eoc-accent); border-radius: var(--eoc-radius-pill); background: var(--eoc-bg-panel); }
.activity-main { flex: 1; min-width: 0; }
.activity-title-row { display: flex; justify-content: space-between; align-items: baseline; gap: var(--eoc-gap-x); }
.activity-title-row strong { color: var(--eoc-text-primary); font-size: var(--eoc-fs-body); font-weight: var(--eoc-fw-semibold); }
.activity-title-row time { flex: none; color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); font-variant-numeric: tabular-nums; }
.activity-byline { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-top: 4px; color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); }
.activity-byline b { color: var(--eoc-text-primary); font-weight: var(--eoc-fw-semibold); }
.activity-notes { margin: 4px 0 0; color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); line-height: 1.45; white-space: pre-wrap; overflow-wrap: anywhere; }
.activity-snapshot { display: flex; flex-wrap: wrap; gap: 5px; margin-top: var(--eoc-gap-y); }
.activity-snapshot span { padding: 1px var(--eoc-gap-x); color: var(--eoc-text-secondary); background: var(--eoc-bg-card); border: var(--eoc-border-width) solid var(--eoc-border); border-radius: var(--eoc-radius-control); font-size: var(--eoc-fs-micro); }
.activity-empty, .activity-loading { padding: var(--eoc-pad-panel); border: var(--eoc-border-width) dashed var(--eoc-border); color: var(--eoc-text-secondary); text-align: center; font-size: var(--eoc-fs-body); }
.activity-compose-note { margin-top: 4px; color: var(--eoc-text-secondary); font-size: var(--eoc-fs-micro); }
.access-hint { margin-bottom: var(--eoc-gap-x); }
.access-hint-link { padding: 0; border: 0; color: var(--eoc-accent-text); background: transparent; font: inherit; font-weight: var(--eoc-fw-semibold); cursor: pointer; }
.technical-details { border-top: var(--eoc-border-width) solid var(--eoc-border-subtle); margin-top: var(--eoc-pad-panel); padding-top: var(--eoc-pad-panel); }
.technical-content { padding-top: var(--eoc-gap-x); font-size: var(--eoc-fs-micro); color: var(--eoc-text-secondary); overflow-wrap: anywhere; }
.technical-content dl { display: grid; grid-template-columns: 1fr 1fr; gap: var(--eoc-gap-y) 24px; }
.technical-content dl > div { display: grid; grid-template-columns: minmax(80px, .5fr) 1fr; gap: var(--eoc-gap-x); }
.technical-content dd { margin: 0; }
.technical-content code { font-family: var(--eoc-font-mono); }
.modal-footer { display: flex; align-items: center; justify-content: space-between; gap: var(--eoc-pad-panel); }
.footer-context { display: inline-flex; align-items: center; gap: var(--eoc-gap-x); font-size: var(--eoc-fs-micro); color: var(--eoc-text-secondary); }
.footer-buttons { display: flex; gap: var(--eoc-gap-x); }
.footer-buttons :deep(.el-button + .el-button) { margin-left: 0; }
@media (max-width: 700px) {
  .assessment-layout { grid-template-columns: 1fr; gap: 16px; }
  .assessment-sidebar { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .location-actions { border-top: 0; padding-top: 0; }
  .footer-context { display: none; }
  .modal-footer { justify-content: flex-end; }
}
@media (max-width: 420px) {
  .form-columns, .assessment-sidebar { grid-template-columns: 1fr; }
  .status-option { padding: 4px 2px; gap: 4px; }
  .form-columns { gap: 0; }
  .technical-content dl { grid-template-columns: 1fr; }
  .footer-buttons { width: 100%; }
  .footer-buttons :deep(.el-button) { flex: 1; }
}
@media (prefers-reduced-motion: reduce) { .status-option { transition: none; } }
</style>

<style>
/* A dialog genuinely floats, so it keeps the dialog shadow */
.el-dialog.triage-modal { --el-color-primary: var(--eoc-accent); display: flex; flex-direction: column; max-height: calc(100dvh - 48px); padding: 0; border-radius: var(--eoc-radius-dialog); border: var(--eoc-border-width) solid var(--eoc-border-strong); background: var(--eoc-bg-overlay); color: var(--eoc-text-primary); box-shadow: var(--eoc-shadow-dialog); overflow: hidden; }
.triage-modal .el-dialog__header { margin-right: 0; padding: var(--eoc-pad-panel) 48px var(--eoc-pad-panel) 14px; border-bottom: var(--eoc-border-width) solid var(--eoc-border); flex-shrink: 0; }
.triage-modal .el-dialog__headerbtn { top: 6px; right: 6px; width: var(--eoc-icon-btn); height: var(--eoc-icon-btn); }
.triage-modal .el-dialog__body { padding: 0; overflow-y: auto; min-height: 0; color: var(--eoc-text-primary); }
.triage-modal .el-dialog__footer { padding: var(--eoc-gap-y) 14px; border-top: var(--eoc-border-width) solid var(--eoc-border); flex-shrink: 0; }
.triage-modal .el-input__wrapper, .triage-modal .el-select__wrapper { min-height: var(--eoc-control-h); border-radius: var(--eoc-radius-control); }
.triage-modal .el-textarea__inner { border-radius: var(--eoc-radius-control); font-family: inherit; font-size: var(--eoc-fs-body); line-height: 1.5; padding: var(--eoc-gap-y) var(--eoc-gap-x); }
</style>
