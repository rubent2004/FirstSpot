/**
 * Date and relative time formatting utilities for disaster telemetry and triage.
 */

export function formatRelativeTime(
  isoDateStr: string | null | undefined,
  locale: "es" | "en" = "es",
): string {
  if (!isoDateStr) return locale === "es" ? "reciente" : "recent";
  const date = new Date(isoDateStr);
  if (Number.isNaN(date.getTime())) return locale === "es" ? "reciente" : "recent";

  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.max(0, Math.floor(diffMs / 1000));
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (locale === "es") {
    if (diffSec < 60) return "hace instantes";
    if (diffMin < 60) return `hace ${diffMin} min`;
    if (diffHours < 24) return `hace ${diffHours} h`;
    return `hace ${diffDays} d`;
  }

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export function formatExactTime(
  isoDateStr: string | null | undefined,
  locale: "es" | "en" = "es",
): string {
  if (!isoDateStr) return "";
  const date = new Date(isoDateStr);
  if (Number.isNaN(date.getTime())) return "";

  try {
    return new Intl.DateTimeFormat(locale === "es" ? "es-SV" : "en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
      timeZone: "America/El_Salvador",
    }).format(date);
  } catch {
    return date.toLocaleTimeString();
  }
}

export function formatFullHazardTime(
  isoDateStr: string | null | undefined,
  locale: "es" | "en" = "es",
): string {
  const rel = formatRelativeTime(isoDateStr, locale);
  const exact = formatExactTime(isoDateStr, locale);
  if (!exact) return rel;
  return `${rel} (${exact})`;
}
