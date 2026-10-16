<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    value: number;
    decimals?: number;
    durationMs?: number;
    suffix?: string;
    prefix?: string;
  }>(),
  {
    decimals: 0,
    durationMs: 420,
    suffix: "",
    prefix: "",
  },
);

const displayValue = ref<number>(props.value);
let rafId: number | null = null;

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return true;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

watch(
  () => props.value,
  (target, prev) => {
    const startVal: number =
      typeof prev === "number" && Number.isFinite(prev) ? prev : 0;
    if (
      prefersReducedMotion() ||
      typeof requestAnimationFrame !== "function" ||
      props.durationMs <= 0 ||
      Math.abs(target - startVal) < 0.001
    ) {
      displayValue.value = target;
      return;
    }

    if (rafId !== null && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(rafId);
    }

    const startTime = performance.now();
    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / props.durationMs);
      const eased = 1 - Math.pow(1 - progress, 3);
      displayValue.value = startVal + (target - startVal) * eased;
      if (progress < 1) {
        rafId = requestAnimationFrame(step);
      } else {
        displayValue.value = target;
        rafId = null;
      }
    };
    rafId = requestAnimationFrame(step);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (rafId !== null && typeof cancelAnimationFrame === "function") {
    cancelAnimationFrame(rafId);
  }
});

function formatNumber(num: number): string {
  if (!Number.isFinite(num)) return "0";
  if (props.decimals > 0) {
    return num.toFixed(props.decimals);
  }
  return Math.round(num).toLocaleString();
}
</script>

<template>
  <span class="vb-count-up">
    <span v-if="props.prefix" class="vb-count-prefix">{{ props.prefix }}</span>
    <span class="vb-count-number">{{ formatNumber(displayValue) }}</span>
    <span v-if="props.suffix" class="vb-count-suffix">{{ props.suffix }}</span>
  </span>
</template>

<style scoped>
.vb-count-up {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  font-variant-numeric: tabular-nums;
}

.vb-count-number {
  font-weight: 800;
  letter-spacing: -0.02em;
}

.vb-count-suffix {
  font-size: 0.72em;
  font-weight: 600;
  opacity: 0.78;
}
</style>
