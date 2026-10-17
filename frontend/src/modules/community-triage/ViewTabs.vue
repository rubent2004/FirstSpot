<script setup lang="ts">
import { useI18n } from "../../i18n/useI18n";

export type WorkspaceView = "territories" | "places";

defineProps<{ modelValue: WorkspaceView }>();
const emit = defineEmits<{ (e: "update:modelValue", value: WorkspaceView): void }>();

const { t } = useI18n();
const VIEWS: WorkspaceView[] = ["territories", "places"];
</script>

<template>
  <div class="tabs" role="tablist" :aria-label="t.community.tabs.label">
    <button
      v-for="view in VIEWS"
      :key="view"
      type="button"
      role="tab"
      class="tab"
      :class="{ active: modelValue === view }"
      :aria-selected="modelValue === view"
      @click="emit('update:modelValue', view)"
    >
      {{ t.community.tabs[view] }}
    </button>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  height: var(--eoc-tabstrip-h);
  flex: none;
  background: var(--eoc-bg-header);
  border-left: var(--eoc-border-width) solid var(--eoc-border);
  border-bottom: var(--eoc-border-width) solid var(--eoc-border);
}
.tab {
  flex: 1;
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  color: var(--eoc-text-secondary);
  font: inherit;
  font-size: var(--eoc-fs-body);
  cursor: pointer;
}
.tab:hover {
  background: var(--eoc-bg-hover);
}
.tab.active {
  color: var(--eoc-text-primary);
  font-weight: var(--eoc-fw-semibold);
  border-bottom-color: var(--eoc-accent);
}
</style>
