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
