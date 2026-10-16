<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  ElButton,
  ElDescriptions,
  ElDescriptionsItem,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElTag,
} from "element-plus";
import {
  CATEGORY_LABELS,
  GROUP_LABELS,
  URGENCY_LABELS,
  type AttentionStatus,
  type PlaceRead,
  type PlaceTriageUpdate,
} from "../../api/client";

const props = defineProps<{
  visible: boolean;
  place: PlaceRead | null;
}>();

const emit = defineEmits<{
  (e: "update:visible", value: boolean): void;
  (e: "save-triage", placeId: string, payload: PlaceTriageUpdate): void;
}>();

const isSaving = ref<boolean>(false);

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
  () => props.place,
  (place) => {
    if (place) {
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

const previewPriorityScore = computed<number>(() => {
  if (!props.place) return 0;
  const wCat = props.place.category_weight;
  const mUrg = urgencyMultipliers[formState.urgency_level] ?? 1.0;
  const pVuln = Math.max(0, formState.estimated_vulnerable_count);
  const n500m = props.place.nearby_places_count ?? 0;
  const base = wCat * mUrg + 15 * Math.log(1 + pVuln) + 5 * n500m;
  return formState.attention_status === "attended" ? base * 0.2 : base;
});

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
  <ElDrawer
    :model-value="props.visible"
    title="Institutional Triage & Dispatch Assessment"
    size="440px"
    @update:model-value="(val) => emit('update:visible', Boolean(val))"
  >
    <div v-if="props.place" class="drawer-body" data-testid="triage-drawer">
      <div class="score-preview-banner">
        <div>
          <div class="preview-label">Projected Priority Score</div>
          <div class="preview-formula">
            (W_cat={{ props.place.category_weight }} &times; M_urg) + 15&middot;ln(1+P_vuln) + 5&middot;N_500m({{ props.place.nearby_places_count }})
          </div>
        </div>
        <div class="preview-value" data-testid="preview-priority-score">
          {{ previewPriorityScore.toFixed(2) }}
        </div>
      </div>

      <ElDescriptions :column="1" border size="small" title="OpenStreetMap & Spatial Metadata">
        <ElDescriptionsItem label="Name">
          <strong>{{ props.place.name }}</strong>
        </ElDescriptionsItem>
        <ElDescriptionsItem label="OSM Element">
          <code>{{ props.place.osm_type }}/{{ props.place.osm_id }}</code>
        </ElDescriptionsItem>
        <ElDescriptionsItem label="Category">
          {{ CATEGORY_LABELS[props.place.category] }} (Base Weight:
          {{ props.place.category_weight }})
        </ElDescriptionsItem>
        <ElDescriptionsItem label="Vulnerability Group">
          {{ GROUP_LABELS[props.place.vulnerability_group] }}
        </ElDescriptionsItem>
        <ElDescriptionsItem label="Zone & Coordinates">
          {{ props.place.zone_name }} ({{ props.place.latitude.toFixed(5) }},
          {{ props.place.longitude.toFixed(5) }})
        </ElDescriptionsItem>
        <ElDescriptionsItem label="500m Spatial Cluster">
          {{ props.place.nearby_places_count }} neighboring vulnerable places
          within 500m (`ST_DWithin`)
        </ElDescriptionsItem>
      </ElDescriptions>

      <ElForm label-position="top" class="triage-form">
        <ElFormItem label="Attention & Dispatch Status">
          <ElRadioGroup
            v-model="formState.attention_status"
            data-testid="triage-status-group"
          >
            <ElRadioButton value="pending">Pending</ElRadioButton>
            <ElRadioButton value="in_progress">In Progress</ElRadioButton>
            <ElRadioButton value="attended">Attended (20% Heat)</ElRadioButton>
          </ElRadioGroup>
        </ElFormItem>

        <ElFormItem label="Institutional Urgency Level (1 - 5)">
          <ElSelect
            v-model="formState.urgency_level"
            data-testid="triage-urgency-select"
          >
            <ElOption
              v-for="(label, level) in URGENCY_LABELS"
              :key="level"
              :label="label"
              :value="Number(level)"
            />
          </ElSelect>
        </ElFormItem>

        <ElFormItem label="Estimated Vulnerable Population Count">
          <ElInputNumber
            v-model="formState.estimated_vulnerable_count"
            :min="0"
            :max="100000"
            :step="10"
            style="width: 100%"
            data-testid="triage-population-input"
          />
        </ElFormItem>

        <ElFormItem label="Institutional Field Notes">
          <ElInput
            v-model="formState.institution_notes"
            type="textarea"
            :rows="3"
            placeholder="Record brigade assignment, medical supply needs, or evacuation notes..."
            data-testid="triage-notes-input"
          />
        </ElFormItem>

        <div class="drawer-actions">
          <ElButton @click="emit('update:visible', false)">Cancel</ElButton>
          <ElButton
            type="primary"
            :loading="isSaving"
            data-testid="save-triage-btn"
            @click="handleSave"
          >
            Save Triage &amp; Recalculate Score
          </ElButton>
        </div>
      </ElForm>

      <div class="osm-tags-box">
        <div class="tags-title">Raw OpenStreetMap Tags (Preserved on UPSERT)</div>
        <div class="tags-list">
          <ElTag
            v-for="(val, key) in props.place.osm_tags"
            :key="key"
            size="small"
            type="info"
          >
            {{ key }}={{ val }}
          </ElTag>
        </div>
      </div>
    </div>
  </ElDrawer>
</template>

<style scoped>
.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.score-preview-banner {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: #f8fafc;
  padding: 12px 16px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-label {
  font-size: 12px;
  font-weight: 700;
  color: #38bdf8;
  text-transform: uppercase;
}

.preview-formula {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.preview-value {
  font-size: 24px;
  font-weight: 800;
  color: #f8fafc;
}

.triage-form {
  margin-top: 4px;
}

.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.osm-tags-box {
  border-top: 1px solid #e2e8f0;
  padding-top: 12px;
}

.tags-title {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
