/**
 * The tour is off by default and never in the operators' way: it starts only
 * from the URL (`?tour=1`) or from the Shift+Alt+T shortcut, with no button.
 */
export function wantsTourFromUrl(search: string): boolean {
  return new URLSearchParams(search).get("tour") === "1";
}

/** Shift+Alt+T. `code` keeps it layout-independent: Alt changes `key` on some layouts. */
export function isTourShortcut(event: KeyboardEvent): boolean {
  if (!event.shiftKey || !event.altKey || event.ctrlKey || event.metaKey) return false;
  return event.code === "KeyT" || event.key.toLowerCase() === "t";
}
