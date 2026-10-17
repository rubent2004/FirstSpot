<script setup lang="ts">
import { ElButton } from "element-plus";
import { useI18n } from "../../i18n/useI18n";

defineProps<{ disabled: boolean; isBusy: boolean; error: string | null }>();
defineEmits<{
  (e: "excel"): void;
  (e: "report"): void;
  (e: "map"): void;
}>();

const { t } = useI18n();
</script>

<template>
  <section class="exports" :aria-label="t.community.exports.menu">
    <span class="eoc-label">{{ t.community.exports.menu }}</span>
    <ElButton size="small" :disabled="disabled" :loading="isBusy" @click="$emit('excel')">
      {{ t.community.exports.excel }}
    </ElButton>
    <ElButton size="small" :disabled="disabled" @click="$emit('report')">
      {{ t.community.exports.report }}
    </ElButton>
    <ElButton size="small" :disabled="disabled" @click="$emit('map')">
      {{ t.community.exports.map }}
    </ElButton>
    <p class="note">
      {{ error ?? (disabled ? t.community.exports.unavailable : t.community.exports.offlineNote) }}
    </p>
  </section>
</template>

<style scoped>
.exports {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--eoc-gap-x);
}
.note {
  flex-basis: 100%;
  margin: 0;
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-muted);
}
</style>
