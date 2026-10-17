<script setup lang="ts">
import { toRef } from "vue";
import type { AppLocale } from "../../../../i18n/useI18n";
import { EMERGENCY_CONTACTS } from "../../../map-viewer/composables/emergencyContacts";
import { usePrintCopy } from "../usePrintCopy";

const props = defineProps<{ lang: AppLocale }>();
const { m } = usePrintCopy(toRef(props, "lang"));
</script>

<template>
  <section class="print-section keep-together" data-testid="section-contacts">
    <h2 class="eoc-label">{{ m.sheet.contactsHeading }}</h2>
    <ul class="counts">
      <li v-for="contact in EMERGENCY_CONTACTS" :key="contact.id">
        <span>{{ m.sheet.contactNames[contact.id] }}</span>
        <strong class="eoc-numeric">{{ contact.display }}</strong>
      </li>
    </ul>
  </section>
</template>
