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
  <section class="honesty" data-testid="honesty-notice" :aria-label="t.community.honesty.title">
    <!-- Always visible: the one sentence that must never be missed -->
    <p class="short">{{ t.community.honesty.short }}</p>

    <!-- Native disclosure: one click or Enter/Space, no script, full text stays in the DOM -->
    <details class="more">
      <summary>{{ t.community.honesty.more }}</summary>
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
    </details>
  </section>
</template>

<style scoped>
.honesty {
  border-left: 3px solid var(--eoc-info);
  padding: 0 var(--eoc-pad-panel);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.short {
  margin: 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-primary);
  line-height: 1.4;
}
summary {
  display: inline-flex;
  align-items: center;
  min-height: var(--eoc-target-min);
  cursor: pointer;
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-accent-text);
  text-decoration: underline;
  text-underline-offset: 2px;
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
  margin: 2px 0 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
</style>
