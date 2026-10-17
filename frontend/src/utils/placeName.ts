/**
 * Presentation rules for place names coming out of the ingestion pipeline.
 *
 * When OpenStreetMap carries no name for an element, the backend synthesises
 * one from the English category label and the raw OSM identifier, e.g.
 * `Unnamed Commercial Hub (#398433965)`. That identifier is a database key: it
 * tells an operator nothing about where to go and costs them a second of
 * reading on every row. The backend cannot be changed, so the identifier is
 * intercepted here and never reaches the screen.
 */

/**
 * The synthesised-name shape: the word "Unnamed", a category label, and the
 * OSM id in parentheses. Anchored at both ends so a genuine place called
 * "Unnamed Road Clinic" is only rewritten when it also carries the id.
 */
const SYNTHESISED_NAME = /^unnamed\s+.+\s+\(#\d+\)$/i;

/** Any `(#12345)` fragment, wherever it sits inside a name. */
const OSM_ID_FRAGMENT = /\(#\d+\)/;

/**
 * True when the backend had no real name and fell back to the OSM identifier.
 * The caller is expected to substitute human wording for the whole string.
 */
export function isSynthesisedPlaceName(name: string | null | undefined): boolean {
  return typeof name === "string" && SYNTHESISED_NAME.test(name.trim());
}

/**
 * True when a name carries a raw OSM identifier anywhere inside it. Used as the
 * last-resort guard so a future backend format change still cannot leak an id
 * into the queue, even if it stops matching `isSynthesisedPlaceName`.
 */
export function containsOsmIdentifier(name: string | null | undefined): boolean {
  return typeof name === "string" && OSM_ID_FRAGMENT.test(name);
}

/** Strips every `(#12345)` fragment and collapses the whitespace it leaves. */
export function stripOsmIdentifier(name: string): string {
  return name.replace(new RegExp(OSM_ID_FRAGMENT.source, "g"), "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function tagValue(
  tags: Record<string, unknown> | undefined,
  key: string,
): string | null {
  const raw = tags?.[key];
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/**
 * A short phrase that helps someone find an unnamed place on the ground.
 *
 * Street address first, because that is what a driver needs; then the smallest
 * administrative area OSM supplies; then whoever runs the place, which is often
 * how locals refer to it. The zone is deliberately excluded: every place in the
 * queue already belongs to the active zone, so repeating it adds no bearing,
 * and a custom radius scan labels its zone with raw coordinates.
 */
export function placeLocatingHint(place: {
  osm_tags?: Record<string, unknown>;
}): string | null {
  const tags = place.osm_tags;
  const street = tagValue(tags, "addr:street");
  if (street) {
    const houseNumber = tagValue(tags, "addr:housenumber");
    return houseNumber ? `${street} ${houseNumber}` : street;
  }
  const area =
    tagValue(tags, "addr:neighbourhood") ??
    tagValue(tags, "addr:suburb") ??
    tagValue(tags, "addr:place") ??
    tagValue(tags, "addr:city");
  if (area) return area;
  return tagValue(tags, "operator") ?? tagValue(tags, "brand");
}
