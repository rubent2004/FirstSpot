import type {
  HazardEventRead,
  PlaceActivityRead,
  PlaceExposureEstimateRead,
  PlaceRead,
  WeatherConditionRead,
} from "../../api/client";
import type { MapSnapshot } from "../../modules/community-triage/mapPrint/mapSnapshot";

const base: PlaceRead = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  osm_type: "way",
  osm_id: 248190101,
  name: "Unidad de Salud Acajutla",
  category: "clinic",
  vulnerability_group: "health",
  zone_name: "Sonsonate",
  latitude: 13.5926,
  longitude: -89.8275,
  osm_tags: {
    amenity: "clinic",
    operator: "MINSAL",
    "addr:street": "Calle Principal",
    opening_hours: "24/7",
    emergency: "yes",
    wheelchair: "limited",
  },
  attention_status: "pending",
  urgency_level: 4,
  estimated_vulnerable_count: 0,
  institution_notes: null,
  category_weight: 80,
  nearby_places_count: 2,
  priority_score: 90,
  last_osm_sync_at: "2026-10-16T11:00:00Z",
  updated_at: "2026-10-16T11:00:00Z",
};

const covered: PlaceExposureEstimateRead = {
  radius_meters: 1000,
  estimated_exposed_population: 12480,
  estimated_exposed_older_adults: 1120,
  estimated_exposed_young_children: 980,
  estimated_exposed_persons_with_disability: 540,
  suppressed: false,
  estimated_at: "2026-10-16T11:00:00Z",
};
const uncovered: PlaceExposureEstimateRead = {
  radius_meters: 1000,
  estimated_exposed_population: null,
  estimated_exposed_older_adults: null,
  estimated_exposed_young_children: null,
  estimated_exposed_persons_with_disability: null,
  suppressed: false,
  estimated_at: null,
};
const withheld: PlaceExposureEstimateRead = { ...uncovered, suppressed: true };

export function place(overrides: Partial<PlaceRead>): PlaceRead {
  return { ...base, ...overrides };
}

export const SONSONATE_PLACES: PlaceRead[] = [
  place({ id: "p1", name: "Hospital Nacional de Sonsonate", category: "hospital", priority_score: 95, urgency_level: 5, population_exposure: covered }),
  place({ id: "p2", name: "Unidad de Salud Acajutla", priority_score: 90, urgency_level: 4, population_exposure: covered }),
  place({ id: "p3", name: "Escuela <b>Central</b>", category: "school", vulnerability_group: "education", priority_score: 70, urgency_level: 3, attention_status: "in_progress", population_exposure: withheld }),
  place({ id: "p4", name: "Parvularia La Esperanza", category: "kindergarten", vulnerability_group: "education", priority_score: 40, urgency_level: 2, attention_status: "attended", population_exposure: uncovered }),
];

export const ESCUINTLA_PLACES: PlaceRead[] = [
  place({ id: "g1", name: "Hospital de Escuintla", category: "hospital", zone_name: "Escuintla", latitude: 14.3, longitude: -90.78, priority_score: 88, urgency_level: 5, population_exposure: uncovered }),
  place({ id: "g2", name: "Escuela Rural Mixta", category: "school", vulnerability_group: "education", zone_name: "Escuintla", latitude: 14.31, longitude: -90.79, priority_score: 60, urgency_level: 3, population_exposure: uncovered }),
];

export const HAZARD: HazardEventRead = {
  id: "h1",
  hazard_type: "earthquake",
  title: "M 4.6 - 10 km S of Acajutla",
  source: "usgs",
  alert_level: "yellow",
  latitude: 13.5,
  longitude: -89.83,
  radius_km: 40,
  magnitude: 4.6,
  depth_km: 35,
  occurred_at: "2026-10-17T08:00:00Z",
  url: null,
  is_simulated: false,
};

export const WEATHER: WeatherConditionRead = {
  temperature_c: 24.1,
  precipitation_mm: 0,
  rain_mm: 0,
  wind_speed_kmh: 6,
  wind_gusts_kmh: 12,
  weather_code: 1,
  weather_label: "Mayormente despejado",
  alert_level: "green",
  source: "open-meteo",
  is_simulated: false,
};

export const ACTIVITY: PlaceActivityRead = {
  id: "a1",
  place_id: "p2",
  activity_type: "on_scene",
  attention_status: "in_progress",
  urgency_level: 4,
  estimated_vulnerable_count: 30,
  notes: "Brigada en sitio",
  actor_name: "Ana",
  organization: { id: "o1", name: "Cruz Roja", verification_status: "verified" } as PlaceActivityRead["organization"],
  created_at: "2026-10-17T09:00:00Z",
};

const view = (center: [number, number]) => ({
  center,
  zoom: 13,
  bounds: { south: center[0] - 0.1, west: center[1] - 0.1, north: center[0] + 0.1, east: center[1] + 0.1 },
  basemap: "grayDark" as const,
  radius: null,
});

export function sonsonateSnapshot(overrides: Partial<MapSnapshot> = {}): MapSnapshot {
  return {
    view: view([13.7222, -89.7236]),
    layers: { heat: true, markers: true, hazards: true },
    zone: { name: "Sonsonate", department: "Sonsonate" },
    places: SONSONATE_PLACES,
    heatPoints: [{ latitude: 13.72, longitude: -89.72, intensity: 0.8 }] as MapSnapshot["heatPoints"],
    hazards: [HAZARD],
    weather: WEATHER,
    selectedPlace: SONSONATE_PLACES[1],
    activities: [ACTIVITY],
    ...overrides,
  };
}

export function escuintlaSnapshot(overrides: Partial<MapSnapshot> = {}): MapSnapshot {
  return {
    view: view([14.3, -90.78]),
    layers: { heat: true, markers: true, hazards: true },
    zone: { name: "Escuintla", department: "Escuintla" },
    places: ESCUINTLA_PLACES,
    heatPoints: [],
    hazards: [],
    weather: WEATHER,
    selectedPlace: null,
    activities: [],
    ...overrides,
  };
}
