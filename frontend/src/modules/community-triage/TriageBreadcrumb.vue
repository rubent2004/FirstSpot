<script setup lang="ts">
import { useI18n } from "../../i18n/useI18n";

defineProps<{
  /** The ancestor the operator returns to. */
  parent: string;
  /** Where the operator is now. */
  current: string;
}>();
const emit = defineEmits<{ (e: "navigate-parent"): void }>();
const { t } = useI18n();
</script>

<template>
  <nav class="crumbs" :aria-label="t.community.nav.breadcrumb">
    <ol>
      <li>
        <button type="button" class="parent" @click="emit('navigate-parent')">
          <span aria-hidden="true">←</span>
          {{ parent }}
        </button>
      </li>
      <li class="current" aria-current="page">{{ current }}</li>
    </ol>
  </nav>
</template>

<style scoped>
ol {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--eoc-gap-x);
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: var(--eoc-fs-body);
}
li + li::before {
  content: "/" / "";
  margin-right: var(--eoc-gap-x);
  color: var(--eoc-text-secondary);
}
.parent {
  min-height: var(--eoc-target-min);
  padding: 0 var(--eoc-gap-x);
  background: transparent;
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  border-radius: var(--eoc-radius-control);
  color: var(--eoc-accent-text);
  font: inherit;
  font-weight: var(--eoc-fw-semibold);
  cursor: pointer;
}
.parent:hover {
  background: var(--eoc-bg-hover);
}
.current {
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-primary);
  overflow-wrap: anywhere;
}
@media (pointer: coarse) {
  .parent {
    min-height: var(--eoc-target-primary);
  }
}
</style>
