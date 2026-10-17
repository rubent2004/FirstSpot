<script setup lang="ts">
import { computed } from "vue";
import { DATA_ATTRIBUTION, fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";

const props = defineProps<{ districtCount: number }>();
const { t } = useI18n();

const relative = computed(() =>
  fillMessage(t.value.community.honesty.relative, {
    total: props.districtCount || 262,
  }),
);
</script>

<template>
  <section class="honesty" data-testid="honesty-notice">
    <h3 class="eoc-label">{{ t.community.honesty.title }}</h3>
    <ul>
      <li class="strong">{{ t.community.honesty.ranking }}</li>
      <li>{{ t.community.honesty.noVictims }}</li>
      <li>{{ t.community.honesty.exposure }}</li>
      <li>{{ t.community.honesty.gaps }}</li>
      <li>{{ relative }}</li>
    </ul>
    <p class="source">
      {{ t.community.honesty.attributionLabel }}: {{ DATA_ATTRIBUTION }}
    </p>
  </section>
</template>

<style scoped>
.honesty {
  border: var(--eoc-border-width) solid var(--eoc-border);
  border-left: 3px solid var(--eoc-info);
  border-radius: var(--eoc-radius-control);
  background: var(--eoc-bg-card);
  padding: var(--eoc-gap-y) var(--eoc-pad-panel);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
h3 {
  margin: 0;
}
ul {
  margin: 0;
  padding-left: 14px;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
  line-height: 1.4;
}
.strong {
  color: var(--eoc-text-primary);
  font-weight: var(--eoc-fw-semibold);
}
.source {
  margin: 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-muted);
}
</style>
