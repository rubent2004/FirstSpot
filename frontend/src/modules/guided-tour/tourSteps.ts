import type { TourSkipReason, TourStepId } from "../../i18n/tourMessages";
import type { ListScope, TourExportFormat } from "./tourBridge";

/** Deterministic demo state: the Sonsonate work zone and the real historical 2001-02-13 M6.6 event. */
export const DEMO_ZONE_KEY = "sonsonate";
export const DEMO_EVENT_ID = "usp000a9jv";

/** What must hold for a step to be shown as designed, beyond its anchor. */
export type TourRequirement = "zone" | "data" | "event" | "district" | "place";

/**
 * The app state a step shows. The tour sets the whole scene on every move,
 * forward or back, so the presenter can step back and the screen still matches.
 * `undefined` means "leave as it is". No field ever causes a write.
 */
export interface TourScene {
  zoneKey?: string;
  eventId?: string | null;
  scope?: ListScope;
  /** "top": the first-ranked district of the loaded ranking. */
  district: "top" | null;
  /** "demo": one real place picked at run time from the loaded queue (see pickDemoPlace). */
  place: "demo" | null;
  /** The place record (assessment and coordination log), read-only for the tour. */
  placeOpen: boolean;
  placesOpen: boolean;
  /** Export dialog open on this format, or closed. */
  exportFormat: TourExportFormat | null;
  limitsOpen: boolean;
  technicalOpen: boolean;
  revealZone: boolean;
}

export interface TourStepDef {
  id: TourStepId;
  /** `data-tour` value of the element to highlight; null is a centred step. */
  anchor: string | null;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  requires: TourRequirement[];
  scene: TourScene;
  /**
   * Show the step first and load its data while it is on screen, so the
   * audience sees the change happen (the zone switching, the ranking reordering).
   */
  deferData?: boolean;
  /** Wait this long after the anchor appears, for an opening dialog to settle. */
  settleMs?: number;
}

const CLOSED: TourScene = {
  district: null,
  place: null,
  placeOpen: false,
  placesOpen: false,
  exportFormat: null,
  limitsOpen: false,
  technicalOpen: false,
  revealZone: false,
};

const BASELINE: Partial<TourScene> = { zoneKey: DEMO_ZONE_KEY, eventId: null, scope: "zone" };
const EVENT: Partial<TourScene> = { zoneKey: DEMO_ZONE_KEY, eventId: DEMO_EVENT_ID, scope: "country" };
const ON_PLACE: Partial<TourScene> = { placesOpen: true, place: "demo" };

/**
 * Fourteen steps of about 8-9 seconds, following the challenge: whom to attend
 * first, where to concentrate effort, what to send, and how it reaches the field.
 * docs/demo/guion-video.md is aligned 1:1 with this list.
 */
export const TOUR_STEPS: readonly TourStepDef[] = [
  { id: "opening", anchor: null, requires: [], scene: { ...CLOSED } },
  {
    id: "zone",
    anchor: "zone-selector",
    side: "bottom",
    requires: ["zone"],
    deferData: true,
    scene: { ...CLOSED, ...BASELINE, revealZone: true },
  },
  {
    id: "baseline",
    anchor: "district-list",
    side: "right",
    requires: ["data"],
    scene: { ...CLOSED, ...BASELINE, limitsOpen: true },
  },
  {
    id: "mode",
    anchor: "mode",
    side: "right",
    requires: ["data"],
    deferData: true,
    scene: { ...CLOSED, ...EVENT },
  },
  {
    id: "eventTop",
    anchor: "district-top",
    side: "right",
    requires: ["event"],
    scene: { ...CLOSED, ...EVENT },
  },
  {
    id: "detail",
    anchor: "detail-drivers",
    side: "left",
    requires: ["event", "district"],
    scene: { ...CLOSED, ...EVENT, district: "top" },
  },
  {
    id: "sphere",
    anchor: "sphere",
    side: "left",
    requires: ["event", "district"],
    scene: { ...CLOSED, ...EVENT, district: "top", technicalOpen: true },
  },
  {
    id: "places",
    anchor: "places-queue",
    side: "right",
    requires: ["place"],
    scene: { ...CLOSED, ...EVENT, ...ON_PLACE },
  },
  {
    id: "placeSummary",
    anchor: "place-summary",
    side: "left",
    requires: ["place"],
    settleMs: 300,
    scene: { ...CLOSED, ...EVENT, ...ON_PLACE, placeOpen: true },
  },
  {
    id: "placeLog",
    anchor: "place-log",
    side: "top",
    requires: ["place"],
    scene: { ...CLOSED, ...EVENT, ...ON_PLACE, placeOpen: true },
  },
  {
    id: "placeAccess",
    anchor: "place-access",
    side: "top",
    align: "end",
    requires: ["place"],
    scene: { ...CLOSED, ...EVENT, ...ON_PLACE, placeOpen: true },
  },
  {
    id: "exportFormat",
    anchor: "export-form",
    side: "left",
    requires: ["data"],
    settleMs: 300,
    // The zone scope gives "what I am looking at" a real row count beside "all".
    scene: { ...CLOSED, ...EVENT, ...ON_PLACE, scope: "zone", exportFormat: "xlsx" },
  },
  {
    id: "exportMap",
    anchor: "export-map",
    side: "left",
    requires: ["data"],
    settleMs: 300,
    scene: { ...CLOSED, ...EVENT, ...ON_PLACE, scope: "zone", exportFormat: "map" },
  },
  { id: "closing", anchor: null, requires: [], scene: { ...CLOSED, ...EVENT, ...ON_PLACE } },
];

export function anchorSelector(anchor: string): string {
  return `[data-tour="${anchor}"]`;
}

/** A present anchor that is hidden (display:none, collapsed ribbon) is not shown. */
export function findAnchor(anchor: string, root: ParentNode = document): HTMLElement | null {
  const element = root.querySelector<HTMLElement>(anchorSelector(anchor));
  if (!element || !element.isConnected) return null;
  if (element.closest("[hidden]")) return null;
  const view = element.ownerDocument.defaultView;
  for (let node: HTMLElement | null = element; node; node = node.parentElement) {
    if (view?.getComputedStyle(node).display === "none") return null;
  }
  return element;
}

export interface PlannedStep {
  def: TourStepDef;
  /** Null when the step can be shown as designed. */
  skip: TourSkipReason | null;
}

/**
 * Decide whether a step can be shown as designed. A missing anchor or unmet
 * requirement keeps the step in the list (so "6 / 14" stays aligned with the
 * narrator script) but turns it into a short centred note.
 */
export function planStep(
  def: TourStepDef,
  meets: (requirement: TourRequirement) => boolean,
  hasAnchor: (anchor: string) => boolean,
): PlannedStep {
  const unmet = def.requires.find((requirement) => !meets(requirement));
  if (unmet) return { def, skip: unmet };
  if (def.anchor && !hasAnchor(def.anchor)) {
    return { def, skip: def.id === "sphere" ? "sphere" : "anchor" };
  }
  return { def, skip: null };
}

export function planSteps(
  defs: readonly TourStepDef[],
  meets: (requirement: TourRequirement) => boolean,
  hasAnchor: (anchor: string) => boolean,
): PlannedStep[] {
  return defs.map((def) => planStep(def, meets, hasAnchor));
}
