<script setup lang="ts">
import { computed, ref } from "vue";
import InfoPopover from "../../components/InfoPopover.vue";
import { useI18n } from "../../i18n/useI18n";
import { useTourActions } from "../guided-tour/tourBridge";
import HonestyContent from "./HonestyContent.vue";

defineProps<{ districtCount: number }>();
const { t } = useI18n();

/**
 * The guided tour pins the limits open while it points at them: the presenter's
 * focus moves to the tour, which would otherwise close the popover at once.
 */
const opened = ref(false);
const pinned = ref(false);
const open = computed({
  get: () => opened.value || pinned.value,
  set: (value: boolean) => {
    opened.value = value;
  },
});
useTourActions({
  isLimitsOpen: () => open.value,
  setLimitsOpen: (value: boolean) => {
    pinned.value = value;
    if (!value) opened.value = false;
  },
});
</script>

<template>
  <!--
    The limits are one click away, never removed: this is the info trigger next to
    the score header. The same text ships in every export and in the PDF.
  -->
  <InfoPopover v-model:open="open" :label="t.community.honesty.more" align="end">
    <HonestyContent :district-count="districtCount" />
  </InfoPopover>
</template>
