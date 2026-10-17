import type { PlaceRead } from "../../api/client";
import { describePlaceName, type AppLocale } from "../../i18n/useI18n";
import { exposedPopulationState } from "../priority-queue/populationExposure";

/**
 * The place the tour points at, chosen from the queue that is actually loaded,
 * never hardcoded: the highest-ranked place with a real name and a census
 * estimate (not "no coverage", not withheld). The queue is already in priority
 * order. Falls back to the first place; null when the queue is empty.
 */
export function pickDemoPlace(places: readonly PlaceRead[], locale: AppLocale): PlaceRead | null {
  const qualified = places.find(
    (place) =>
      !describePlaceName(place, locale).isUnnamed &&
      exposedPopulationState(place).kind === "estimate",
  );
  return qualified ?? places[0] ?? null;
}
