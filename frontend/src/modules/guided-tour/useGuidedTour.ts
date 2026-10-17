import { onBeforeUnmount, onMounted } from "vue";
import { tourMessages } from "../../i18n/tourMessages";
import { useI18n } from "../../i18n/useI18n";
import { useCommunityTriageStore } from "../../stores/useCommunityTriageStore";
import { usePrioritizationStore } from "../../stores/usePrioritizationStore";
import { createAppPort, type TourPort } from "./tourAppPort";
import { isTourShortcut, wantsTourFromUrl } from "./tourActivation";
import { createTourController, type DriverFactory, type TourController } from "./tourController";
import { TOUR_STEPS, type TourStepDef } from "./tourSteps";

/** Driver.js and its CSS arrive only here, through a dynamic import: a lazy chunk. */
export const loadDriverRuntime = (): Promise<DriverFactory> =>
  import("./driverRuntime").then((module) => module.driver as DriverFactory);

export interface GuidedTourOptions {
  loadDriver?: () => Promise<DriverFactory>;
  port?: TourPort;
  steps?: readonly TourStepDef[];
  /** Defaults to the page URL's query string. */
  search?: () => string;
  /** True once the first data has arrived, so a URL start opens on real numbers. */
  isReady?: () => boolean;
  readyTimeoutMs?: number;
}

export function useGuidedTour(options: GuidedTourOptions = {}): { controller: () => TourController } {
  const { locale } = useI18n();
  const places = usePrioritizationStore();
  const triage = useCommunityTriageStore();
  const isReady =
    options.isReady ?? (() => !places.isLoading && (triage.index !== null || triage.error !== null));
  const readyTimeoutMs = options.readyTimeoutMs ?? 20_000;

  let controller: TourController | null = null;
  function getController(): TourController {
    controller ??= createTourController({
      steps: options.steps ?? TOUR_STEPS,
      port: options.port ?? createAppPort(),
      loadDriver: options.loadDriver ?? loadDriverRuntime,
      messages: () => tourMessages(locale.value),
    });
    return controller;
  }

  function onKeydown(event: KeyboardEvent): void {
    if (!isTourShortcut(event)) return;
    event.preventDefault();
    void getController().toggle();
  }

  let readyTimer: ReturnType<typeof setTimeout> | null = null;
  function startWhenReady(deadline: number): void {
    if (isReady() || Date.now() >= deadline) {
      readyTimer = null;
      void getController().start();
      return;
    }
    readyTimer = setTimeout(() => startWhenReady(deadline), 200);
  }

  onMounted(() => {
    window.addEventListener("keydown", onKeydown);
    const search = options.search?.() ?? window.location.search;
    if (wantsTourFromUrl(search)) startWhenReady(Date.now() + readyTimeoutMs);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("keydown", onKeydown);
    if (readyTimer !== null) clearTimeout(readyTimer);
    void controller?.stop();
  });

  return { controller: getController };
}
