import type {
  DistrictPrioRead,
  EventRead,
  PrioIndexAuditRead,
  PrioIndexRead,
  SphereRead,
} from "../../api/client";

export const EVENT_ID = "usp000a9jv";
export const REDACTED_LEAK = 777_777;

export const sphere: SphereRead = {
  label: "Sphere minimum requirement",
  exposed_population: 52000,
  water_litres_per_day: 780000,
  water_litres_per_day_extreme_heat: 1040000,
  water_taps_minimum: 208,
  water_point_maximum_distance_metres: 500,
  food_kcal_per_day: 109200000,
  shelter_area_m2: 182000,
  shelter_basis: "3.5 m2 per person",
  population_basis: "x",
  caveat: "x",
  source: "x",
};

export const sampleEvent: EventRead = {
  event_id: EVENT_ID,
  magnitude: 6.6,
  place: "Offshore San Salvador",
  latitude: 13.671,
  longitude: -88.938,
  depth_km: 60,
  occurred_at: "2001-02-13T14:22:05Z",
  shakemap_grid_processed_at: "2023-06-30T08:15:00Z",
  shakemap_version: "9",
  shakemap_declared_max_mmi: 8.1,
  contour_max_mmi: 7.9,
  contour_interval: 0.5,
  pager: {
    level: "orange",
    band_label: "100-999 estimated fatalities (PAGER orange)",
    response_implication: "x",
  },
};

function dims(h: number | null, v: number, l: number) {
  const out = [
    { dimension: "vulnerability", score: v, rank: 10 },
    { dimension: "lack_of_coping_capacity", score: l, rank: 20 },
  ];
  if (h !== null) out.unshift({ dimension: "hazard_and_exposure", score: h, rank: 5 });
  return out;
}

export const redDistrict: DistrictPrioRead = {
  district_code: "060101",
  district_name: "San Marcos Rojo",
  population: 120000,
  rank: 1,
  score: 8.4,
  inform_rescaled_score: 8.9,
  alert_class: "roja",
  dimensions: dims(9.1, 8.2, 7.9),
  zeroed_by: [],
  zero_reason: null,
  withheld: false,
  withheld_reason: null,
  max_mmi: 7.8,
  estimated_exposed_population: 52000,
  sphere,
};

export const zeroDistrict: DistrictPrioRead = {
  district_code: "010203",
  district_name: "Lejos Verde",
  population: 40000,
  rank: 262,
  score: 0,
  inform_rescaled_score: 1.2,
  alert_class: "verde",
  dimensions: dims(0, 6.1, 4.0),
  zeroed_by: ["hazard_and_exposure"],
  zero_reason: "BACKEND ENGLISH ZERO REASON",
  withheld: false,
  withheld_reason: null,
  max_mmi: 3.1,
  estimated_exposed_population: 0,
  sphere: null,
};

/** The API nulls these; the leak proves exports do not rely on that. */
export const withheldDistrict: DistrictPrioRead = {
  district_code: "090909",
  district_name: "Reservado Sur",
  population: REDACTED_LEAK,
  rank: 2,
  score: 7.7,
  inform_rescaled_score: 7.7,
  alert_class: "roja",
  dimensions: dims(7.7, 7.7, 7.7),
  zeroed_by: [],
  zero_reason: null,
  withheld: true,
  withheld_reason: "statistical secrecy",
  max_mmi: 7.7,
  estimated_exposed_population: REDACTED_LEAK,
  sphere,
};

const methodology = {
  composition_rule: "x",
  rescaled_composition_exclusion: "x",
  percentile_floor_zero_meaning: "x",
  hazard_zero_meaning: "x",
  dgpc_class_source: "x",
  triage_colour_analogy: "x",
  class_distribution_caveat: "x",
  declared_scale: "x",
  interpretation: "x",
  uses_principal_components: false,
  scored_unit_count: 262,
  withheld_unit_count: 1,
  zeroed_by_hazard_count: 1,
  zeroed_by_percentile_floor_count: 0,
  suppression_threshold: 3,
  suppression_reference: "x",
};

const alertClasses = [
  { alert_class: "verde", floor: 0, ceiling: 3.5, inform_class: "x", meaning: "x" },
  { alert_class: "amarilla", floor: 3.5, ceiling: 5, inform_class: "x", meaning: "x" },
  { alert_class: "naranja", floor: 5, ceiling: 6.5, inform_class: "x", meaning: "x" },
  { alert_class: "roja", floor: 6.5, ceiling: 10, inform_class: "x", meaning: "x" },
];

export function eventIndex(): PrioIndexRead {
  return {
    mode: "event",
    mode_meaning: "BACKEND EVENT MEANING",
    dimension_keys: ["hazard_and_exposure", "vulnerability", "lack_of_coping_capacity"],
    event: sampleEvent,
    districts: [redDistrict, withheldDistrict, zeroDistrict],
    class_distribution: { roja: 1, naranja: 0, amarilla: 0, verde: 1 },
    alert_classes: alertClasses,
    total_exposed_population: 52000,
    methodology,
    declared_gaps: [],
    ecological_fallacy: "x",
    modifiable_areal_unit_problem: "x",
    casualty_reporting_prohibition: "x",
    shakemap_revision_warning: "x",
    source: "x",
    computed_at: "2026-10-17T10:00:00Z",
  };
}

export function baselineIndex(): PrioIndexRead {
  const stripHazard = (d: DistrictPrioRead): DistrictPrioRead => ({
    ...d,
    dimensions: d.dimensions.filter((x) => x.dimension !== "hazard_and_exposure"),
    estimated_exposed_population: null,
    sphere: null,
    max_mmi: null,
  });
  return {
    ...eventIndex(),
    mode: "baseline",
    mode_meaning: "BACKEND BASELINE MEANING",
    dimension_keys: ["vulnerability", "lack_of_coping_capacity"],
    event: null,
    districts: [stripHazard(redDistrict), stripHazard(zeroDistrict)],
    total_exposed_population: null,
  };
}

export function auditFor(district: DistrictPrioRead): PrioIndexAuditRead {
  const index = eventIndex();
  return {
    ...district,
    mode: "event",
    mode_meaning: "x",
    dimension_keys: index.dimension_keys,
    event: sampleEvent,
    methodology,
    declared_gaps: [],
    ecological_fallacy: "x",
    modifiable_areal_unit_problem: "x",
    casualty_reporting_prohibition: "x",
    computed_at: "2026-10-17T10:00:00Z",
  };
}
