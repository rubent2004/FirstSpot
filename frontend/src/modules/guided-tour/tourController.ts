import type { Config, Driver, DriveStep, PopoverDOM } from "driver.js";
import type { TourMessages } from "../../i18n/tourMessages";
import type { TourPort, TourSnapshot } from "./tourAppPort";
import { findAnchor, planStep, type PlannedStep, type TourStepDef } from "./tourSteps";

/** The part of a Driver.js instance the tour uses; a fake stands in for it in tests. */
export type DriverLike = Pick<Driver, "drive" | "moveTo" | "destroy" | "isActive" | "refresh">;
export type DriverFactory = (config: Config) => DriverLike;

export interface TourControllerOptions {
  steps: readonly TourStepDef[];
  port: TourPort;
  /** Resolves Driver.js lazily; it is never loaded until a tour starts. */
  loadDriver: () => Promise<DriverFactory>;
  messages: () => TourMessages;
  /** How long to wait for an anchor that appears after a state change. */
  anchorTimeoutMs?: number;
  target?: Window;
}

export interface TourController {
  start(): Promise<void>;
  stop(): Promise<void>;
  toggle(): Promise<void>;
  isActive(): boolean;
  /** Index of the step on screen, or null when the tour is not running. */
  currentIndex(): number | null;
  /** The plan of the step on screen (skipped or not), for tests and diagnostics. */
  currentPlan(): PlannedStep | null;
}

const NAV_NEXT = new Set(["ArrowRight", "PageDown"]);
const NAV_PREVIOUS = new Set(["ArrowLeft", "PageUp"]);

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function createTourController(options: TourControllerOptions): TourController {
  const { steps, port, loadDriver, messages } = options;
  const anchorTimeoutMs = options.anchorTimeoutMs ?? 2_500;
  const target = options.target ?? window;

  let active = false;
  let stopping = false;
  let busy = false;
  let shown = false;
  let current: number | null = null;
  let plan: PlannedStep | null = null;
  let instance: DriverLike | null = null;
  let snapshot: TourSnapshot | null = null;

  /** Wait briefly for an anchor that a state change is about to render. */
  async function resolve(def: TourStepDef): Promise<PlannedStep> {
    const deadline = Date.now() + anchorTimeoutMs;
    let planned = planStep(def, port.meets, (anchor) => findAnchor(anchor) !== null);
    while (planned.skip === "anchor" || planned.skip === "sphere") {
      if (Date.now() >= deadline) break;
      await wait(50);
      planned = planStep(def, port.meets, (anchor) => findAnchor(anchor) !== null);
    }
    if (!planned.skip && def.settleMs) await wait(def.settleMs);
    return planned;
  }

  async function go(index: number): Promise<void> {
    if (!active || busy || !instance) return;
    if (index < 0) return;
    if (index >= steps.length) {
      await stop();
      return;
    }
    busy = true;
    try {
      const def = steps[index];
      await port.apply(def.scene, { deferData: def.deferData });
      if (!active || !instance) return;
      plan = await resolve(def);
      if (!active || !instance) return;
      current = index;
      if (shown) instance.moveTo(index);
      else {
        shown = true;
        instance.drive(index);
      }
    } finally {
      busy = false;
    }
  }

  function renderPopover(popover: PopoverDOM): void {
    if (!plan) return;
    popover.wrapper.classList.toggle("is-skipped", plan.skip !== null);
    const copy = messages();
    if (!plan.skip) {
      const variant = port.variant(plan.def.id);
      if (variant) popover.description.textContent = copy.variants[variant];
      return;
    }
    popover.title.textContent = copy.skipped.title;
    popover.title.style.display = "block";
    popover.description.textContent = copy.skipped.reasons[plan.skip];
    popover.description.style.display = "block";
  }

  function buildSteps(copy: TourMessages): DriveStep[] {
    return steps.map((def, index) => ({
      // A skipped or centred step resolves to nothing, and Driver.js centres it.
      element: (() =>
        index === current && plan && !plan.skip && def.anchor
          ? findAnchor(def.anchor)
          : undefined) as () => Element,
      popover: {
        title: copy.steps[def.id].title,
        description: copy.steps[def.id].body,
        side: def.side,
        align: def.align ?? "start",
      },
    }));
  }

  /** Presenter keys: arrows and clicker page keys move, Esc ends. The app never sees them. */
  function onKeydown(event: KeyboardEvent): void {
    if (!active || event.ctrlKey || event.metaKey || event.altKey) return;
    const isNext = NAV_NEXT.has(event.key);
    const isPrevious = NAV_PREVIOUS.has(event.key);
    const isEscape = event.key === "Escape";
    if (!isNext && !isPrevious && !isEscape) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.repeat) return;
    if (isEscape) void stop();
    else if (current !== null) void go(current + (isNext ? 1 : -1));
  }

  async function start(): Promise<void> {
    if (active) return;
    active = true;
    shown = false;
    current = null;
    plan = null;
    snapshot = port.snapshot();
    target.addEventListener("keydown", onKeydown, true);
    try {
      const factory = await loadDriver();
      if (!active) return;
      const copy = messages();
      instance = factory({
        steps: buildSteps(copy),
        animate: true,
        smoothScroll: true,
        allowClose: true,
        // The tour owns the keys (see onKeydown) so Esc always restores the app.
        allowKeyboardControl: false,
        // The presenter never clicks inside the app; a stray click must not end the tour.
        disableActiveInteraction: true,
        overlayClickBehavior: "none",
        overlayColor: "rgb(8, 11, 16)",
        overlayOpacity: 0.62,
        stagePadding: 8,
        stageRadius: 10,
        popoverOffset: 12,
        popoverClass: "firstspot-tour",
        showProgress: true,
        progressText: copy.progress,
        nextBtnText: copy.next,
        prevBtnText: copy.previous,
        doneBtnText: copy.done,
        closeBtnLabel: copy.close,
        onPopoverRender: (popover) => renderPopover(popover),
        onNextClick: () => {
          if (current !== null) void go(current + 1);
        },
        onPrevClick: () => {
          if (current !== null) void go(current - 1);
        },
        onCloseClick: () => void stop(),
        onDestroyStarted: () => void stop(),
      });
      await go(0);
    } catch (error) {
      console.warn("[guided-tour] could not start", error);
      await stop();
    }
  }

  async function stop(): Promise<void> {
    if (!active || stopping) return;
    stopping = true;
    target.removeEventListener("keydown", onKeydown, true);
    const running = instance;
    instance = null;
    current = null;
    plan = null;
    try {
      running?.destroy();
    } catch (error) {
      console.warn("[guided-tour] driver teardown failed", error);
    }
    try {
      if (snapshot) await port.restore(snapshot);
    } finally {
      snapshot = null;
      active = false;
      stopping = false;
      busy = false;
      shown = false;
    }
  }

  return {
    start,
    stop,
    toggle: () => (active ? stop() : start()),
    isActive: () => active,
    currentIndex: () => current,
    currentPlan: () => plan,
  };
}
