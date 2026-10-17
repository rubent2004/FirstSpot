import { nextTick } from "vue";
import type { PlaceRead } from "../../api/client";
import { useI18n } from "../../i18n/useI18n";
import type { TourStepId } from "../../i18n/tourMessages";
import { useCommunityTriageStore } from "../../stores/useCommunityTriageStore";
import { usePrioritizationStore } from "../../stores/usePrioritizationStore";
import { pickDemoPlace } from "./demoPlace";
import { tourAction, type ListScope } from "./tourBridge";
import {
  DEMO_EVENT_ID,
  DEMO_ZONE_KEY,
  anchorSelector,
  type TourRequirement,
  type TourScene,
} from "./tourSteps";

/** What the tour may change, as it was before the tour started. */
export interface TourSnapshot {
  zoneKey: string;
  customRadius: boolean;
  eventId: string | null;
  districtCode: string | null;
  scope: ListScope | null;
  placesOpen: boolean | null;
  exportOpen: boolean | null;
  technicalOpen: boolean | null;
  place: PlaceRead | null;
  placeOpen: boolean;
}

/** Copy that depends on what the screen actually shows. */
export type TourVariant = "placeLogEmpty";

/**
 * The tour's view of the app: it reads and changes state only through this port.
 * Every change is a read or a UI toggle. The tour never saves, posts, signs in or
 * syncs: changing zone reloads the zone's data with GET requests only.
 */
export interface TourPort {
  snapshot(): TourSnapshot;
  apply(scene: TourScene, options?: { deferData?: boolean }): Promise<void>;
  restore(snapshot: TourSnapshot): Promise<void>;
  meets(requirement: TourRequirement): boolean;
  variant(step: TourStepId): TourVariant | null;
}

const ZONE_TIMEOUT_MS = 12_000;
const EVENT_TIMEOUT_MS = 20_000;

/** A slow server must not freeze the presenter: give up waiting, never fake the result. */
function withTimeout(work: Promise<unknown>, ms: number): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    work.then(
      () => {
        clearTimeout(timer);
        resolve();
      },
      () => {
        clearTimeout(timer);
        resolve();
      },
    );
  });
}

function technicalFold(): HTMLDetailsElement | null {
  return document.querySelector<HTMLDetailsElement>(anchorSelector("detail-technical"));
}

/** The real port, wired to the Pinia stores and to the actions components register. */
export function createAppPort(): TourPort {
  const places = usePrioritizationStore();
  const triage = useCommunityTriageStore();
  const { locale } = useI18n();
  let inflight: Promise<void> = Promise.resolve();
  let undoRibbon: (() => void) | null = null;
  let customRadiusAtStart = false;
  let placeChanged = false;

  function topDistrictCode(): string | null {
    let best: { code: string; rank: number } | null = null;
    for (const district of triage.districts) {
      if (district.withheld || district.rank === null) continue;
      if (!best || district.rank < best.rank) best = { code: district.district_code, rank: district.rank };
    }
    return best?.code ?? null;
  }

  function setTechnical(open: boolean): void {
    const fold = technicalFold();
    if (fold && fold.open !== open) fold.open = open;
  }

  /**
   * Switch zone with reads only. The store's selectZone falls back to an Overpass
   * sync (a POST) when a zone has no places; the tour must never trigger a write.
   */
  async function showZone(key: string): Promise<void> {
    const zone = places.zones.find((candidate) => candidate.key === key);
    if (!zone) return;
    places.customRadiusMode.enabled = false;
    places.selectedZoneKey = key;
    places.activeZoneName = zone.name;
    await places.fetchPlacesAndHeatmap();
    await places.fetchHazards();
  }

  /** Close what this scene does not show, reveal what its anchor needs. Synchronous. */
  function prepareUi(scene: TourScene): void {
    if (scene.exportFormat === null && tourAction("isExportOpen")?.()) tourAction("setExportOpen")?.(false);
    if (!scene.limitsOpen) tourAction("setLimitsOpen")?.(false);
    if (!scene.technicalOpen) setTechnical(false);
    if (!scene.placeOpen && places.isTriageDrawerOpen) places.isTriageDrawerOpen = false;
    if (scene.revealZone && !undoRibbon) undoRibbon = tourAction("revealZoneSelector")?.() ?? null;
    if (scene.scope) tourAction("setListScope")?.(scene.scope);
  }

  async function applyData(scene: TourScene): Promise<void> {
    const zoneKey = scene.zoneKey;
    if (
      zoneKey &&
      !customRadiusAtStart &&
      (places.selectedZoneKey !== zoneKey || places.customRadiusMode.enabled)
    ) {
      await withTimeout(showZone(zoneKey), ZONE_TIMEOUT_MS);
    }
    if (scene.eventId !== undefined && triage.requestedEventId !== scene.eventId) {
      await withTimeout(triage.selectEvent(scene.eventId), EVENT_TIMEOUT_MS);
    }
  }

  async function finishUi(scene: TourScene): Promise<void> {
    const setPlaces = tourAction("setPlacesOpen");
    if (setPlaces && tourAction("isPlacesOpen")?.() !== scene.placesOpen) setPlaces(scene.placesOpen);
    const target = scene.district === "top" ? topDistrictCode() : null;
    // The audit arrives later; the detail renders from the ranking row at once.
    if (triage.selectedCode !== target) void triage.selectDistrict(target);
    if (scene.place === "demo") {
      const place = pickDemoPlace(places.places, locale.value);
      if (place && places.selectedPlace?.id !== place.id) {
        placeChanged = true;
        places.selectPlace(place, false);
      }
    }
    // Opening the record only reads: the form starts from the place and is never saved.
    if (scene.placeOpen && places.selectedPlace && !places.isTriageDrawerOpen) {
      places.isTriageDrawerOpen = true;
    }
    if (scene.exportFormat) {
      if (tourAction("isExportOpen")?.()) tourAction("setExportFormat")?.(scene.exportFormat);
      else tourAction("setExportOpen")?.(true, scene.exportFormat);
    }
    if (scene.limitsOpen) tourAction("setLimitsOpen")?.(true);
    if (scene.technicalOpen) {
      await nextTick();
      setTechnical(true);
    }
  }

  return {
    snapshot() {
      customRadiusAtStart = places.customRadiusMode.enabled;
      undoRibbon = null;
      placeChanged = false;
      return {
        zoneKey: places.selectedZoneKey,
        customRadius: places.customRadiusMode.enabled,
        eventId: triage.requestedEventId,
        districtCode: triage.selectedCode,
        scope: tourAction("getListScope")?.() ?? null,
        placesOpen: tourAction("isPlacesOpen")?.() ?? null,
        exportOpen: tourAction("isExportOpen")?.() ?? null,
        technicalOpen: technicalFold()?.open ?? null,
        place: places.selectedPlace,
        placeOpen: places.isTriageDrawerOpen,
      };
    },

    async apply(scene, options = {}) {
      await inflight;
      prepareUi(scene);
      const work = (async () => {
        await applyData(scene);
        await finishUi(scene);
      })();
      inflight = work.catch(() => undefined);
      if (!options.deferData) await inflight;
    },

    async restore(snapshot) {
      // What covers the screen goes first, at once; the data reloads after.
      tourAction("setExportOpen")?.(false);
      tourAction("setLimitsOpen")?.(false);
      setTechnical(false);
      places.isTriageDrawerOpen = false;
      await inflight;
      tourAction("setExportOpen")?.(false);
      if (snapshot.placesOpen !== null) tourAction("setPlacesOpen")?.(snapshot.placesOpen);
      if (snapshot.scope) tourAction("setListScope")?.(snapshot.scope);
      undoRibbon?.();
      undoRibbon = null;
      if (!snapshot.customRadius && snapshot.zoneKey && places.selectedZoneKey !== snapshot.zoneKey) {
        await withTimeout(showZone(snapshot.zoneKey), ZONE_TIMEOUT_MS);
      }
      if (triage.requestedEventId !== snapshot.eventId) {
        await withTimeout(triage.selectEvent(snapshot.eventId), EVENT_TIMEOUT_MS);
      }
      if (triage.selectedCode !== snapshot.districtCode) void triage.selectDistrict(snapshot.districtCode);
      if (placeChanged) {
        placeChanged = false;
        // The same record if it is still loaded; the map follows the selection back.
        const previous = snapshot.place
          ? (places.places.find((p) => p.id === snapshot.place?.id) ?? snapshot.place)
          : null;
        places.selectPlace(previous, false);
        if (!previous) window.dispatchEvent(new CustomEvent("geo-priority:center-zone"));
      }
      if (snapshot.placeOpen && places.selectedPlace) places.isTriageDrawerOpen = true;
      if (snapshot.technicalOpen) {
        await nextTick();
        setTechnical(true);
      }
    },

    meets(requirement) {
      const index = triage.index;
      const hasData = index !== null && !triage.error;
      switch (requirement) {
        case "zone":
          return !customRadiusAtStart && places.zones.some((zone) => zone.key === DEMO_ZONE_KEY);
        case "data":
          return hasData;
        case "event":
          return hasData && index?.mode === "event" && index.event?.event_id === DEMO_EVENT_ID;
        case "district":
          return triage.selectedDistrict !== null;
        case "place":
          return places.places.length > 0;
      }
    },

    variant(step) {
      if (step !== "placeLog") return null;
      const loaded = !places.arePlaceActivitiesLoading && !places.placeActivityError;
      return loaded && places.placeActivities.length === 0 ? "placeLogEmpty" : null;
    },
  };
}
