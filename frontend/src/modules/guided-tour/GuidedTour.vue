<script setup lang="ts">
/**
 * Presenter-driven guided tour, mounted once by App. It renders nothing and
 * stays idle until `?tour=1` or Shift+Alt+T; Driver.js is loaded only then.
 */
import { useGuidedTour } from "./useGuidedTour";

useGuidedTour();
</script>

<template>
  <span hidden></span>
</template>
