import { onBeforeUnmount, onMounted, ref } from "vue";

/** The width at which the console switches to its phone layout. */
export const PHONE_QUERY = "(max-width: 700px)";

/** Reactive "is this a phone-sized viewport", safe where matchMedia does not exist. */
export function useIsPhone(query: string = PHONE_QUERY) {
  const isPhone = ref(false);
  let list: MediaQueryList | null = null;
  const update = () => {
    isPhone.value = list?.matches ?? false;
  };
  onMounted(() => {
    list = typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query) : null;
    update();
    list?.addEventListener?.("change", update);
  });
  onBeforeUnmount(() => list?.removeEventListener?.("change", update));
  return isPhone;
}
