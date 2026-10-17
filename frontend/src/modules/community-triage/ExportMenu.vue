<script setup lang="ts">
import { computed, ref } from "vue";
import { ElButton } from "element-plus";
import { Download, RefreshRight } from "@element-plus/icons-vue";
import { fillMessage } from "../../i18n/communityMessages";
import { useI18n } from "../../i18n/useI18n";

const props = defineProps<{
  /** No ranking is loaded, so there is nothing to export. */
  disabled: boolean;
  isBusy: boolean;
  /** File name the remembered settings would produce now, or null when none were saved. */
  repeatFile: string | null;
}>();

const emit = defineEmits<{ (e: "open"): void; (e: "repeat"): void }>();

const { t } = useI18n();
const openButton = ref<InstanceType<typeof ElButton> | null>(null);
defineExpose({ focus: () => openButton.value?.ref?.focus() });
const d = computed(() => t.value.community.exportDialog);
const repeatHint = computed(() =>
  props.repeatFile ? fillMessage(d.value.repeatHint, { file: props.repeatFile }) : "",
);
</script>

<template>
  <div class="export-menu">
    <ElButton
      ref="openButton"
      size="small"
      class="open"
      aria-haspopup="dialog"
      :disabled="disabled"
      :loading="isBusy"
      :icon="Download"
      aria-describedby="export-unavailable"
      @click="emit('open')"
    >
      {{ d.open }}
    </ElButton>
    <ElButton
      v-if="repeatFile"
      size="small"
      text
      class="repeat"
      :disabled="disabled || isBusy"
      :icon="RefreshRight"
      :title="repeatHint"
      :aria-label="`${d.repeat}. ${repeatHint}`"
      @click="emit('repeat')"
    >
      {{ d.repeat }}
    </ElButton>
    <span v-if="disabled" id="export-unavailable" class="reason">{{ d.unavailable }}</span>
  </div>
</template>

<style scoped>
.export-menu {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--eoc-gap-x);
}
.reason {
  font-size: var(--eoc-fs-micro);
  color: var(--eoc-text-secondary);
}
@media (pointer: coarse) {
  .export-menu :deep(.el-button) {
    min-height: var(--eoc-target-primary);
  }
}
</style>
