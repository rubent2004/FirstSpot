<script setup lang="ts">
import { computed } from "vue";
import { ICONS0_SVG_PATHS, type Icon0Name } from "./icons0Registry";

const props = withDefaults(
  defineProps<{
    name: Icon0Name;
    size?: number | string;
    label?: string;
  }>(),
  {
    size: 16,
    label: "",
  },
);

const svgInner = computed<string>(
  () => ICONS0_SVG_PATHS[props.name] ?? ICONS0_SVG_PATHS.map_pin,
);
</script>

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    :width="props.size"
    :height="props.size"
    viewBox="0 0 24 24"
    class="icon0-svg"
    :aria-label="props.label || undefined"
    :aria-hidden="props.label ? undefined : 'true'"
    role="img"
    v-html="svgInner"
  />
</template>

<style scoped>
.icon0-svg {
  display: inline-block;
  vertical-align: middle;
  flex-shrink: 0;
  color: inherit;
}
</style>
