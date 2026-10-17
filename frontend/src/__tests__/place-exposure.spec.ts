import { afterEach, describe, expect, it } from "vitest";
import { DOMWrapper, flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import type { PlaceExposureEstimateRead, PlaceRead } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import PriorityQueuePanel from "../modules/priority-queue/PriorityQueuePanel.vue";
import PlaceTriageDrawer from "../modules/priority-queue/PlaceTriageDrawer.vue";

const basePlace: PlaceRead = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  osm_type: "way",
  osm_id: 248190101,
  name: "Unidad de Salud Acajutla",
  category: "clinic",
  vulnerability_group: "health",
  zone_name: "Sonsonate",
  latitude: 13.5926,
  longitude: -89.8275,
  osm_tags: { amenity: "clinic" },
  attention_status: "pending",
  urgency_level: 3,
  // Institution-entered field, unrelated to the census estimate.
  estimated_vulnerable_count: 0,
  institution_notes: null,
  category_weight: 80,
  nearby_places_count: 2,
  priority_score: 90.0,
  last_osm_sync_at: "2026-10-16T11:00:00Z",
  updated_at: "2026-10-16T11:00:00Z",
};

const coveredExposure: PlaceExposureEstimateRead = {
  radius_meters: 1000,
  estimated_exposed_population: 12480,
  estimated_exposed_older_adults: 1120,
  estimated_exposed_young_children: 980,
  estimated_exposed_persons_with_disability: 540,
  suppressed: false,
  suppression_reason: null,
  estimated_at: "2026-10-16T11:00:00Z",
};

/** The 56 places outside CPV 2024 coverage: every figure is null, not zero. */
const uncoveredExposure: PlaceExposureEstimateRead = {
  radius_meters: 1000,
  estimated_exposed_population: null,
  estimated_exposed_older_adults: null,
  estimated_exposed_young_children: null,
  estimated_exposed_persons_with_disability: null,
  suppressed: false,
  suppression_reason: null,
  estimated_at: null,
};

const withheldExposure: PlaceExposureEstimateRead = {
  ...uncoveredExposure,
  suppressed: true,
  suppression_reason: "Statistical secrecy threshold",
};

function placeWith(
  exposure: PlaceExposureEstimateRead | null,
  overrides: Partial<PlaceRead> = {},
): PlaceRead {
  return { ...basePlace, population_exposure: exposure, ...overrides };
}

function mountQueue(places: PlaceRead[]) {
  return mount(PriorityQueuePanel, {
    global: { plugins: [ElementPlus] },
    props: { places, selectedPlace: null, isLoading: false },
  });
}

function mountDrawer(place: PlaceRead) {
  return mount(PlaceTriageDrawer, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
    props: { visible: true, place },
  });
}

afterEach(() => {
  setAppLocale("es");
});

describe("Estimated exposed population in the dispatch queue", () => {
  it("renders a real estimate with estimate wording and tabular numerals", async () => {
    setAppLocale("es");
    const wrapper = mountQueue([placeWith(coveredExposure)]);
    await flushPromises();

    const readout = wrapper.get('[data-testid="row-exposed-population"]');
    expect(readout.text()).toBe("12.480 pob. estimada");
    expect(readout.classes()).toContain("eoc-numeric");
    expect(readout.classes()).not.toContain("is-unknown");
    // The method travels with the figure, never implying a count of presence.
    expect(readout.attributes("title")).toContain("ponderación areal");

    setAppLocale("en");
    await flushPromises();
    expect(wrapper.get('[data-testid="row-exposed-population"]').text()).toBe(
      "12,480 est. population",
    );
    wrapper.unmount();
  });

  it("renders a null estimate as missing census coverage and never as zero", async () => {
    setAppLocale("es");
    const wrapper = mountQueue([placeWith(uncoveredExposure)]);
    await flushPromises();

    const readout = wrapper.get('[data-testid="row-exposed-population"]');
    expect(readout.text()).toBe("— sin cobertura censal");
    expect(readout.classes()).toContain("is-unknown");
    expect(readout.text()).not.toMatch(/\b0\b/);
    expect(readout.attributes("title")).toBe("Valor desconocido, no cero.");

    setAppLocale("en");
    await flushPromises();
    expect(wrapper.get('[data-testid="row-exposed-population"]').text()).toBe(
      "— no census coverage",
    );
    wrapper.unmount();
  });

  it("keeps a withheld figure apart from both zero and missing coverage", async () => {
    setAppLocale("es");
    const wrapper = mountQueue([placeWith(withheldExposure)]);
    await flushPromises();

    const readout = wrapper.get('[data-testid="row-exposed-population"]');
    expect(readout.text()).toBe("— dato reservado");
    expect(readout.classes()).toContain("is-unknown");
    wrapper.unmount();
  });

  it("falls back to the unknown state when no estimate was computed", async () => {
    setAppLocale("es");
    const wrapper = mountQueue([placeWith(null)]);
    await flushPromises();

    expect(wrapper.get('[data-testid="row-exposed-population"]').text()).toBe(
      "— sin cobertura censal",
    );
    wrapper.unmount();
  });

  it("repeats the identical figure for places sharing a census unit", async () => {
    setAppLocale("es");
    const wrapper = mountQueue([
      placeWith(coveredExposure, { id: `${basePlace.id}-a`, census_unit_id: 71 }),
      placeWith(coveredExposure, {
        id: `${basePlace.id}-b`,
        name: "Centro Escolar Acajutla",
        census_unit_id: 71,
      }),
    ]);
    await flushPromises();

    const readouts = wrapper
      .findAll('[data-testid="row-exposed-population"]')
      .map((node) => node.text());
    // Uniform density inside a unit is the documented assumption, not a bug:
    // the estimate must not be jittered to look more precise than it is.
    expect(readouts).toEqual(["12.480 pob. estimada", "12.480 pob. estimada"]);
    wrapper.unmount();
  });

  it("leaves the institution-entered vulnerable count untouched", async () => {
    setAppLocale("es");
    const wrapper = mountQueue([
      placeWith(coveredExposure, { estimated_vulnerable_count: 220 }),
    ]);
    await flushPromises();

    // The census estimate replaced the readout; it did not overwrite the field.
    expect(wrapper.get('[data-testid="row-exposed-population"]').text()).toBe(
      "12.480 pob. estimada",
    );
    expect(wrapper.props("places")[0].estimated_vulnerable_count).toBe(220);
    wrapper.unmount();
  });
});

describe("Vulnerable-group breakdown in the triage drawer", () => {
  it("shows the 65+, under-five and disability estimates with their method", async () => {
    setAppLocale("es");
    const view = new DOMWrapper(document.body);
    const wrapper = mountDrawer(placeWith(coveredExposure));
    await flushPromises();

    const panel = view.get('[data-testid="exposure-estimate"]');
    expect(panel.text()).toContain("Población Expuesta Estimada");
    expect(view.get('[data-testid="exposure-total"]').text()).toBe("12.480");
    expect(panel.text()).toContain("Radio 1000 m");

    const breakdown = view.get('[data-testid="exposure-breakdown"]');
    expect(breakdown.text()).toContain("65 y más");
    expect(breakdown.text()).toContain("1120");
    expect(breakdown.text()).toContain("Menores de 5");
    expect(breakdown.text()).toContain("980");
    expect(breakdown.text()).toContain("Con discapacidad");
    expect(breakdown.text()).toContain("540");
    expect(panel.text()).toContain(
      "se asume densidad uniforme dentro de cada unidad",
    );
    wrapper.unmount();
  });

  it("marks every breakdown figure as unknown outside census coverage", async () => {
    setAppLocale("en");
    const view = new DOMWrapper(document.body);
    const wrapper = mountDrawer(placeWith(uncoveredExposure));
    await flushPromises();

    const total = view.get('[data-testid="exposure-total"]');
    expect(total.text()).toBe("— no census coverage");
    expect(total.classes()).toContain("is-unknown");

    const figures = view
      .get('[data-testid="exposure-breakdown"]')
      .findAll("dd")
      .map((node) => node.text());
    expect(figures).toEqual(["—", "—", "—"]);
    expect(figures).not.toContain("0");
    wrapper.unmount();
  });

  it("still drives the editable form from the institution-entered count", async () => {
    setAppLocale("es");
    const view = new DOMWrapper(document.body);
    const wrapper = mountDrawer(
      placeWith(coveredExposure, { estimated_vulnerable_count: 35 }),
    );
    await flushPromises();

    const input = view.get('[data-testid="triage-population-input"] input');
    expect((input.element as HTMLInputElement).value).toBe("35");
    wrapper.unmount();
  });
});
