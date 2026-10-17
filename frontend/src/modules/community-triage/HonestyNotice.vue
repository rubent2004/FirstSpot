<script setup lang="ts">
import { computed } from "vue";
import { DATA_ATTRIBUTION, fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";
import InfoPopover from "../../components/InfoPopover.vue";

const props = defineProps<{ districtCount: number }>();
const { t } = useI18n();

const relative = computed(() =>
  fillMessage(t.value.community.honesty.relative, {
    total: props.districtCount || 262,
  }),
);
</script>

<template>
  <!--
    The limits are one click away, never removed: this is the ⓘ next to the
    score header. The same text ships in every export and in the PDF.
  -->
  <InfoPopover :label="t.community.honesty.more" align="end">
    <div class="honesty" data-testid="honesty-notice">
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
    </div>
  </InfoPopover>
</template>

<style scoped>
.honesty {
  display: flex;
  flex-direction: column;
  gap: var(--eoc-gap-y);
}
h3 {
  margin: 0;
}
ul {
  margin: 0;
  padding-left: 16px;
  color: var(--eoc-text-secondary);
  line-height: 1.45;
}
.strong {
  color: var(--eoc-text-primary);
  font-weight: var(--eoc-fw-semibold);
}
.source {
  margin: 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
</style>
