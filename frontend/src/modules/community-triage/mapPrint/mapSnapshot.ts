import type {
  HazardEventRead,
  HeatmapPointRead,
  PlaceActivityRead,
  PlaceRead,
  WeatherConditionRead,
} from "../../../api/client";
import type { MapViewState } from "../../map-viewer/composables/mapViewState";

/**
 * Everything the printed map needs, captured from the live app at the moment of
 * export: where the map is, what is painted on it and the data behind it. The
 * print never refetches and never reconstructs: it renders this.
 */
export interface MapSnapshot {
  view: MapViewState;
  layers: { heat: boolean; markers: boolean; hazards: boolean };
  /** The work zone; null for a custom radius, which is not a predefined zone. */
  zone: { name: string | null; department: string | null };
  places: PlaceRead[];
  heatPoints: HeatmapPointRead[];
  hazards: HazardEventRead[];
  weather: WeatherConditionRead | null;
  selectedPlace: PlaceRead | null;
  /** Coordination log of the selected place, when it has been loaded. */
  activities: PlaceActivityRead[];
}
