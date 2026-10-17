import { computed, type Ref } from "vue";
import { MAP_PRINT_EN, MAP_PRINT_ES, type MapPrintMessages } from "../../../i18n/communityMapPrintMessages";
import { communityMessages } from "../../../i18n/communityMessages";
import { MESSAGES, type AppLocale } from "../../../i18n/useI18n";

/** All the copy a printed section needs, in the document's own language. */
export function usePrintCopy(lang: Ref<AppLocale>) {
  const m = computed<MapPrintMessages>(() => (lang.value === "es" ? MAP_PRINT_ES : MAP_PRINT_EN));
  const ui = computed(() => MESSAGES[lang.value]);
  const c = computed(() => communityMessages(lang.value));
  const tag = computed(() => (lang.value === "es" ? "es-SV" : "en-US"));
  const number = (value: number, digits = 0) =>
    value.toLocaleString(tag.value, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return { m, ui, c, tag, number };
}
