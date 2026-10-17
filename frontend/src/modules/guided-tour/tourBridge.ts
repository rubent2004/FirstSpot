import { onBeforeUnmount, onMounted } from "vue";

/**
 * The few UI states the guided tour must drive that live inside components
 * rather than in a store: which list scope is shown, whether the zone places
 * or the export dialog are open, whether the limits popover is pinned open.
 *
 * Components register what they own; the tour only calls what is registered.
 * A component that is not mounted simply has no action, and the tour treats
 * the matching step as unavailable instead of failing.
 *
 * None of these actions writes anything: they open, close and select only.
 */
export type ListScope = "zone" | "country";
export type TourExportFormat = "xlsx" | "csv" | "report" | "map";

export interface TourActions {
  /** Show the work-zone picker in the ribbon; returns how to put the ribbon back. */
  revealZoneSelector: () => () => void;
  getListScope: () => ListScope;
  setListScope: (scope: ListScope) => void;
  isPlacesOpen: () => boolean;
  setPlacesOpen: (open: boolean) => void;
  isExportOpen: () => boolean;
  /** Opens the export dialog on a format, or closes it. Never exports. */
  setExportOpen: (open: boolean, format?: TourExportFormat) => void;
  /** Registered by the open export dialog: switch its draft format, nothing else. */
  setExportFormat: (format: TourExportFormat) => void;
  isLimitsOpen: () => boolean;
  /** Keeps the limits popover open while the tour points at it, even when focus leaves. */
  setLimitsOpen: (open: boolean) => void;
}

export type TourActionName = keyof TourActions;

const registry = new Map<TourActionName, TourActions[TourActionName]>();

export function registerTourActions(actions: Partial<TourActions>): () => void {
  const names = Object.keys(actions) as TourActionName[];
  for (const name of names) registry.set(name, actions[name]!);
  return () => {
    for (const name of names) {
      if (registry.get(name) === actions[name]) registry.delete(name);
    }
  };
}

/** Register for the lifetime of the calling component. */
export function useTourActions(actions: Partial<TourActions>): void {
  let unregister: (() => void) | null = null;
  onMounted(() => {
    unregister = registerTourActions(actions);
  });
  onBeforeUnmount(() => {
    unregister?.();
    unregister = null;
  });
}

export function tourAction<K extends TourActionName>(name: K): TourActions[K] | null {
  return (registry.get(name) as TourActions[K] | undefined) ?? null;
}

/** Test helper: forget every registration. */
export function resetTourActions(): void {
  registry.clear();
}
