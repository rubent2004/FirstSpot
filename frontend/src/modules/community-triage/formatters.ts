import type { PagerRead } from "../../api/client";
import type { CommunityMessages } from "../../i18n/communityMessages";
import type { AppLocale } from "../../i18n/useI18n";
import { formatPagerRange, parsePagerRange } from "./triageModel";

function tag(locale: AppLocale): string {
  return locale === "es" ? "es-SV" : "en-US";
}

export function formatInteger(value: number, locale: AppLocale): string {
  return Math.round(value).toLocaleString(tag(locale));
}

/** One decimal, the precision of a 0-10 relative score. */
export function formatScore(value: number, locale: AppLocale): string {
  return value.toLocaleString(tag(locale), {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

/**
 * Timestamps are shown in UTC. ShakeMap and USGS publish UTC, and a time that
 * silently shifts with the reader's laptop clock is a hazard in a hand-off.
 */
export function formatUtcTimestamp(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

/** What an event label needs; both the catalogue entry and the index event carry it. */
export interface EventLabelSource {
  magnitude: number | null;
  place: string;
  occurred_at: string;
}

const USGS_OFFSET = /^(\d+(?:\.\d+)?) km ([NSEW]{1,3}) of (.+)$/;

/**
 * USGS writes places as "5 km S of Cojutepeque, El Salvador". The country is
 * implied by the app, and in Spanish the bearing reads "5 km S de Cojutepeque",
 * with W as O (oeste).
 */
export function localizeEventPlace(place: string, locale: AppLocale): string {
  const trimmed = place.trim().replace(/,\s*El Salvador$/i, "");
  if (locale !== "es") return trimmed;
  const match = USGS_OFFSET.exec(trimmed);
  if (!match) return trimmed;
  const [, distance, bearing, town] = match;
  return `${distance} km ${bearing.replace(/W/g, "O")} de ${town}`;
}

/** "Sismo M6.6 · 5 km S de Cojutepeque · 13 feb 2001": readable, never the USGS id. */
export function describeEventLabel(
  event: EventLabelSource,
  t: CommunityMessages,
  locale: AppLocale,
): string {
  const magnitude = event.magnitude !== null ? `M${event.magnitude.toFixed(1)}` : "M ?";
  const date = new Date(event.occurred_at);
  const day = Number.isNaN(date.getTime())
    ? event.occurred_at.slice(0, 10)
    : new Intl.DateTimeFormat(tag(locale), {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(date);
  return `${t.event.quake} ${magnitude} · ${localizeEventPlace(event.place, locale)} · ${day}`;
}

/**
 * "naranja 100–999": the PAGER level always travels with its range, never as a
 * bare colour. Null when the event has no PAGER or the range is unreadable.
 */
export function describePager(
  pager: PagerRead | null | undefined,
  t: CommunityMessages,
  locale: AppLocale,
): string | null {
  const range = parsePagerRange(pager);
  if (!range) return null;
  const level = range.level ? (t.event.pagerLevels[range.level] ?? range.level) : "";
  return `${level} ${formatPagerRange(range, locale)}`.trim();
}
