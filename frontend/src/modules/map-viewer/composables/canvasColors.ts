/**
 * Canvas-rendered vector paths (Leaflet runs on canvas whenever
 * `preferCanvas` is on) cannot read CSS custom properties, so severity colors
 * that reach a canvas context are mirrored from the token palette as literals.
 * The DGPC "orange" level sits between --eoc-warning and --eoc-critical, a step
 * the token set does not name, so it is interpolated once and documented here.
 *
 * Every literal below reaches a canvas context (`L.circle`, `L.circleMarker`
 * or the `leaflet.heat` canvas) and therefore cannot become a `var()` token.
 * Only `divIcon` HTML, which the browser lays out as real DOM, may use `var()`.
 * Keep them here so the whole canvas-bound palette stays auditable in one file.
 */

/** Hazard severity ramp for the canvas-rendered impact circles. */
export const ALERT_RAMP_HEX: Record<string, string> = {
  green: "#3fc282",
  yellow: "#f2b848",
  orange: "#ed8f3c",
  red: "#f06a6a",
};

/** Attention status rings. Canvas fallback needs literals, HTML pins use tokens. */
export const STATUS_RING = {
  attended: { token: "var(--eoc-success)", hex: "#3fc282" },
  in_progress: { token: "var(--eoc-info)", hex: "#2cc2ae" },
  pending: { token: "var(--eoc-text-primary)", hex: "#e6eaef" },
} as const;

/** Operational accent as a literal, for the canvas-rendered radius circle. */
export const ACCENT_HEX = "#5b8df6";

/**
 * Heat ramp stops. `leaflet.heat` only reads this object to bake a canvas
 * linear gradient, so a single shared constant is safe. The `.gradient-bar`
 * rule in VulnerabilityHeatmapCanvas.vue mirrors these stops literally: the
 * legend is only honest while both ramps hold the same values.
 */
export const HEAT_GRADIENT_STOPS: Record<number, string> = {
  0.2: "#3b82f6",
  0.45: "#06b6d4",
  0.65: "#eab308",
  0.85: "#f97316",
  1.0: "#ef4444",
};
