import type { PlaceRead } from "../../api/client";

/**
 * Reading of a census exposure figure. The API returns `null` both when a
 * figure is withheld under statistical secrecy and when the place lies outside
 * census coverage, so the UI keeps those apart from an actual figure and never
 * collapses either of them into zero: "unknown" and "nobody" are different
 * facts when someone is deciding a rescue.
 */
export type PopulationExposureState =
  | { readonly kind: "estimate"; readonly value: number }
  | { readonly kind: "withheld" }
  | { readonly kind: "no-coverage" };

/** Vulnerable sub-populations, each with its own availability. */
export interface VulnerableExposureBreakdown {
  readonly olderAdults: PopulationExposureState;
  readonly youngChildren: PopulationExposureState;
  readonly personsWithDisability: PopulationExposureState;
}

const WITHHELD: PopulationExposureState = { kind: "withheld" };
const NO_COVERAGE: PopulationExposureState = { kind: "no-coverage" };

function toExposureState(
  value: number | null | undefined,
  suppressed: boolean,
): PopulationExposureState {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return suppressed ? WITHHELD : NO_COVERAGE;
  }
  return { kind: "estimate", value };
}

/**
 * Estimated residents the census places around this point, or the reason the
 * figure is unavailable. A missing `population_exposure` means no estimate was
 * computed for the place, which is also an unknown rather than a zero.
 */
export function exposedPopulationState(
  place: PlaceRead | null | undefined,
): PopulationExposureState {
  const exposure = place?.population_exposure;
  if (!exposure) return NO_COVERAGE;
  return toExposureState(
    exposure.estimated_exposed_population,
    exposure.suppressed === true,
  );
}

/** Vulnerable-group estimates derived from the same exposed population. */
export function vulnerableExposureBreakdown(
  place: PlaceRead | null | undefined,
): VulnerableExposureBreakdown {
  const exposure = place?.population_exposure;
  const suppressed = exposure?.suppressed === true;
  return {
    olderAdults: toExposureState(
      exposure?.estimated_exposed_older_adults,
      suppressed,
    ),
    youngChildren: toExposureState(
      exposure?.estimated_exposed_young_children,
      suppressed,
    ),
    personsWithDisability: toExposureState(
      exposure?.estimated_exposed_persons_with_disability,
      suppressed,
    ),
  };
}

/** Radius the cached estimate was computed for, in metres. */
export function exposureRadiusMeters(
  place: PlaceRead | null | undefined,
): number | null {
  return place?.population_exposure?.radius_meters ?? null;
}

/**
 * Group the digits and leave the figure itself untouched. The estimate is flat
 * inside a census unit (density x buffer area), so rounding it further would
 * imply precision that areal weighting never produced.
 */
export function formatExposureValue(
  value: number,
  locale: "es" | "en",
): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(
    value,
  );
}
