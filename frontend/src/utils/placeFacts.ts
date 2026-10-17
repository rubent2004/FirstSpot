/**
 * The handful of OpenStreetMap tags that change what a responder does next.
 *
 * A place arrives carrying everything its OSM contributors ever typed:
 * `amenity`, `source`, `wikidata`, `ref:MINSAL`, survey dates. Printing that
 * dictionary is a developer's view of the record, and at 3 AM it buries the two
 * or three facts that matter — who runs this place, whether its emergency
 * entrance is open, how to get through the door. Everything outside this
 * whitelist is dropped.
 */

/** A fact the drawer knows how to label and render. */
export type PlaceFactKey =
  | "operator"
  | "address"
  | "openingHours"
  | "emergency"
  | "capacity"
  | "wheelchair"
  | "website";

/** Tri-state OSM flag, which the UI localizes rather than printing raw. */
export type PlaceFactFlag = "yes" | "limited" | "no";

export interface PlaceFact {
  readonly key: PlaceFactKey;
  /** Text to render when the fact is not a flag. */
  readonly text: string;
  /** Set when the value should be a link; always http(s). */
  readonly href?: string;
  /** Set when the value is a flag whose wording belongs to the UI locale. */
  readonly flag?: PlaceFactFlag;
}

function tagValue(
  tags: Record<string, unknown> | undefined,
  ...keys: string[]
): string | null {
  for (const key of keys) {
    const raw = tags?.[key];
    if (typeof raw !== "string") continue;
    const trimmed = raw.trim();
    if (trimmed.length > 0) return trimmed;
  }
  return null;
}

function flagValue(raw: string | null): PlaceFactFlag | null {
  if (raw === "yes" || raw === "designated") return "yes";
  if (raw === "limited" || raw === "partial") return "limited";
  if (raw === "no") return "no";
  return null;
}

/**
 * Normalize an OSM website value to an absolute http(s) URL.
 *
 * OSM values are contributor-entered free text, so a scheme other than http(s)
 * is refused outright rather than rendered as a link an operator might tap.
 */
function safeHttpUrl(raw: string): string | null {
  const candidate = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  try {
    const url = new URL(candidate);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    if (url.hostname.length === 0) return null;
    return url.toString();
  } catch {
    return null;
  }
}

/** Street address as a single line, city included when the tags carry one. */
function addressLine(tags: Record<string, unknown> | undefined): string | null {
  const street = tagValue(tags, "addr:street");
  const houseNumber = tagValue(tags, "addr:housenumber");
  const city = tagValue(tags, "addr:city", "addr:place", "addr:suburb");
  const line = [street && houseNumber ? `${street} ${houseNumber}` : street, city]
    .filter((part): part is string => Boolean(part))
    .join(", ");
  return line.length > 0 ? line : null;
}

/**
 * Operator-relevant facts, in the order a responder needs them: who to call
 * about the place, where it is, when it is open, whether it takes emergencies,
 * how many it holds, whether it can be entered, and finally its website.
 */
export function operatorRelevantFacts(place: {
  osm_tags?: Record<string, unknown>;
} | null | undefined): PlaceFact[] {
  const tags = place?.osm_tags;
  if (!tags) return [];
  const facts: PlaceFact[] = [];

  const operator = tagValue(tags, "operator", "brand", "owner");
  if (operator) facts.push({ key: "operator", text: operator });

  const address = addressLine(tags);
  if (address) facts.push({ key: "address", text: address });

  const openingHours = tagValue(tags, "opening_hours");
  if (openingHours) facts.push({ key: "openingHours", text: openingHours });

  const emergency = flagValue(tagValue(tags, "emergency"));
  if (emergency) facts.push({ key: "emergency", text: "", flag: emergency });

  const capacity = tagValue(tags, "capacity:beds", "beds", "capacity");
  if (capacity) facts.push({ key: "capacity", text: capacity });

  const wheelchair = flagValue(tagValue(tags, "wheelchair"));
  if (wheelchair) facts.push({ key: "wheelchair", text: "", flag: wheelchair });

  const website = tagValue(tags, "website", "contact:website", "url");
  if (website) {
    const href = safeHttpUrl(website);
    if (href) facts.push({ key: "website", text: website, href });
  }

  return facts;
}
