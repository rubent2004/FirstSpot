export type DistanceLocale = "es" | "en";

/** Format map distances with the unit people normally use at that scale. */
export function formatDistance(meters: number, locale: DistanceLocale): string {
  if (!Number.isFinite(meters) || meters <= 0) return "—";

  if (meters < 1000) {
    const roundedMeters = Math.round(meters);
    return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(roundedMeters)} m`;
  }

  const kilometers = meters / 1000;
  const isWholeKilometer = Math.abs(kilometers - Math.round(kilometers)) < 0.001;
  const formattedKilometers = new Intl.NumberFormat(locale, {
    minimumFractionDigits: isWholeKilometer ? 0 : 1,
    maximumFractionDigits: 1,
  }).format(kilometers);

  return `${formattedKilometers} km`;
}
