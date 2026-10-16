<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    text: string;
    speedSeconds?: number;
  }>(),
  {
    speedSeconds: 4,
  },
);
</script>

<template>
  <span
    class="vb-shiny-text"
    :style="{ '--vb-shine-duration': `${props.speedSeconds}s` }"
  >
    {{ props.text }}
  </span>
</template>

<style scoped>
.vb-shiny-text {
  display: inline-block;
  background: linear-gradient(
    110deg,
    #38bdf8 0%,
    #7dd3fc 35%,
    #ffffff 50%,
    #7dd3fc 65%,
    #38bdf8 100%
  );
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: vb-shine var(--vb-shine-duration, 4s) linear infinite;
}

@keyframes vb-shine {
  to {
    background-position: 200% center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .vb-shiny-text {
    animation: none;
  }
}
</style>
