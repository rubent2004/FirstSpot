<script setup lang="ts">
import InfoPopover from "../../components/InfoPopover.vue";
import { useI18n } from "../../i18n/useI18n";
import HonestyContent from "./HonestyContent.vue";

defineProps<{ districtCount: number }>();
const { t } = useI18n();
</script>

<template>
  <!--
    The limits are one click away, never removed: this is the info trigger next to
    the score header. The same text ships in every export and in the PDF.
  -->
  <InfoPopover :label="t.community.honesty.more" align="end">
    <HonestyContent :district-count="districtCount" />
  </InfoPopover>
</template>
