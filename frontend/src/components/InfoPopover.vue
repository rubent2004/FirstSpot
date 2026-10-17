<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";

const props = defineProps<{
  /** Accessible name of the trigger and of the popover itself. */
  label: string;
  /** Where the popover hangs from its trigger. */
  align?: "start" | "end";
  /** Opens below its trigger, or above it when the trigger sits at the bottom of the screen. */
  placement?: "bottom" | "top";
}>();

const open = defineModel<boolean>("open", { default: false });

const root = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const popover = ref<HTMLElement | null>(null);
const id = `info-pop-${Math.random().toString(36).slice(2, 8)}`;

function close(returnFocus: boolean): void {
  open.value = false;
  if (returnFocus) void nextTick(() => trigger.value?.focus());
}

function onOutside(event: Event): void {
  if (root.value && !root.value.contains(event.target as Node)) close(false);
}

watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener("pointerdown", onOutside);
    document.addEventListener("focusin", onOutside);
    void nextTick(() => popover.value?.focus());
  } else {
    document.removeEventListener("pointerdown", onOutside);
    document.removeEventListener("focusin", onOutside);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onOutside);
  document.removeEventListener("focusin", onOutside);
});

defineExpose({ close });
void props;
</script>

<template>
  <span ref="root" class="info">
    <button
      ref="trigger"
      type="button"
      class="trigger"
      aria-haspopup="dialog"
      :aria-expanded="open"
      :aria-controls="open ? id : undefined"
      :aria-label="label"
      :title="label"
      @click="open = !open"
    >
      <slot name="trigger"><span aria-hidden="true">ⓘ</span></slot>
    </button>
    <!-- Rendered only while open: closed, it costs the default view nothing -->
    <div
      v-if="open"
      :id="id"
      ref="popover"
      class="pop"
      :class="[align === 'end' ? 'is-end' : 'is-start', placement === 'top' ? 'is-top' : '']"
      role="dialog"
      tabindex="-1"
      :aria-label="label"
      @keydown.esc.stop.prevent="close(true)"
    >
      <slot></slot>
    </div>
  </span>
</template>

<style scoped>
.info {
  position: relative;
  display: inline-flex;
}
.trigger {
  min-width: var(--eoc-target-min);
  min-height: var(--eoc-target-min);
  padding: 0 var(--eoc-gap-x);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--eoc-gap-x);
  background: transparent;
  border: var(--eoc-border-width) solid transparent;
  border-radius: var(--eoc-radius-control);
  color: var(--eoc-accent-text);
  font: inherit;
  font-size: var(--eoc-fs-body);
  cursor: pointer;
}
.trigger:hover {
  background: var(--eoc-bg-hover);
  border-color: var(--eoc-border-strong);
}
.trigger[aria-expanded="true"] {
  background: var(--eoc-bg-active);
}
/* A floating surface: the one place a shadow is allowed */
.pop {
  position: absolute;
  top: calc(100% + 4px);
  z-index: 30;
  width: min(340px, 86vw);
  padding: var(--eoc-pad-panel);
  background: var(--eoc-bg-overlay);
  color: var(--eoc-text-primary);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  border-radius: var(--eoc-radius-menu);
  box-shadow: var(--eoc-shadow-popup);
  font-size: var(--eoc-fs-body);
  text-align: left;
}
.pop.is-top {
  top: auto;
  bottom: calc(100% + 4px);
}
.pop.is-start {
  left: 0;
}
.pop.is-end {
  right: 0;
}
@media (pointer: coarse) {
  .trigger {
    min-width: var(--eoc-target-primary);
    min-height: var(--eoc-target-primary);
  }
}
</style>
