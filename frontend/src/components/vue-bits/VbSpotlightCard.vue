<script setup lang="ts">
import { ref } from "vue";

const props = withDefaults(
  defineProps<{
    spotlightColor?: string;
    active?: boolean;
    clickable?: boolean;
    accentColor?: string;
    pulse?: boolean;
  }>(),
  {
    spotlightColor: "rgba(56, 189, 248, 0.16)",
    active: false,
    clickable: true,
    accentColor: "#38bdf8",
    pulse: false,
  },
);

const cardRef = ref<HTMLElement | null>(null);
const mouseX = ref<number>(0);
const mouseY = ref<number>(0);
const isHovered = ref<boolean>(false);

function handleMouseMove(e: MouseEvent): void {
  if (!cardRef.value) return;
  const rect = cardRef.value.getBoundingClientRect();
  mouseX.value = e.clientX - rect.left;
  mouseY.value = e.clientY - rect.top;
}
</script>

<template>
  <div
    ref="cardRef"
    class="vb-spotlight-card"
    :class="{
      'is-active': props.active,
      'is-clickable': props.clickable,
      'is-pulsing': props.pulse,
    }"
    :style="{
      '--vb-accent': props.accentColor,
      '--vb-spot-color': props.spotlightColor,
      '--vb-mouse-x': `${mouseX}px`,
      '--vb-mouse-y': `${mouseY}px`,
      '--vb-spot-opacity': isHovered || props.active ? '1' : '0',
    }"
    :tabindex="props.clickable ? 0 : undefined"
    :role="props.clickable ? 'button' : undefined"
    @mousemove="handleMouseMove"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  >
    <div class="vb-spotlight-overlay" aria-hidden="true"></div>
    <div class="vb-spotlight-content">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.vb-spotlight-card {
  position: relative;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.78);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-left: 3px solid var(--vb-accent, #38bdf8);
  padding: 10px 14px;
  overflow: hidden;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background-color 0.18s ease;
}

.vb-spotlight-card.is-clickable {
  cursor: pointer;
}

.vb-spotlight-card.is-clickable:hover {
  transform: translateY(-1px);
  border-color: var(--vb-accent, #38bdf8);
  background: rgba(30, 41, 59, 0.92);
}

.vb-spotlight-card.is-active {
  border-color: var(--vb-accent, #38bdf8);
  background: rgba(30, 41, 59, 0.96);
  box-shadow:
    0 0 0 1px var(--vb-accent, #38bdf8),
    0 6px 18px -6px rgba(15, 23, 42, 0.65);
}

.vb-spotlight-card.is-pulsing {
  box-shadow: 0 0 14px rgba(239, 68, 68, 0.28);
}

.vb-spotlight-overlay {
  pointer-events: none;
  position: absolute;
  inset: 0;
  opacity: var(--vb-spot-opacity, 0);
  transition: opacity 0.25s ease;
  background: radial-gradient(
    220px circle at var(--vb-mouse-x, 50%) var(--vb-mouse-y, 50%),
    var(--vb-spot-color, rgba(56, 189, 248, 0.16)),
    transparent 75%
  );
}

.vb-spotlight-content {
  position: relative;
  z-index: 1;
}
</style>
