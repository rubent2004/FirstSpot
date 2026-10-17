import { afterEach, describe, expect, it } from "vitest";
import { DOMWrapper, flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import type { PlaceRead } from "../api/client";
import { describePlaceName, setAppLocale } from "../i18n/useI18n";
import {
  containsOsmIdentifier,
  isSynthesisedPlaceName,
  placeLocatingHint,
} from "../utils/placeName";
import { operatorRelevantFacts } from "../utils/placeFacts";
import PriorityQueuePanel from "../modules/priority-queue/PriorityQueuePanel.vue";
import PlaceTriageDrawer from "../modules/priority-queue/PlaceTriageDrawer.vue";

const basePlace: PlaceRead = {
  id: "cccccccc-0000-0000-0000-000000000001",
  osm_type: "way",
  osm_id: 398433965,
  name: "Unnamed Commercial Hub (#398433965)",
  category: "commercial_hub",
  vulnerability_group: "concurrency",
  zone_name: "Sonsonate",
  latitude: 13.5926,
  longitude: -89.8275,
  osm_tags: { shop: "mall" },
  attention_status: "pending",
  urgency_level: 3,
  estimated_vulnerable_count: 0,
  institution_notes: null,
  category_weight: 60,
  nearby_places_count: 2,
  priority_score: 130.0,
  last_osm_sync_at: "2026-10-16T11:00:00Z",
  updated_at: "2026-10-16T11:00:00Z",
};

function placeWith(overrides: Partial<PlaceRead> = {}): PlaceRead {
  return { ...basePlace, ...overrides };
}

afterEach(() => {
  setAppLocale("es");
});

describe("synthesised OSM name detection", () => {
  it("recognises the ingestion fallback shape for every category label", () => {
    expect(isSynthesisedPlaceName("Unnamed Commercial Hub (#398433965)")).toBe(true);
    expect(isSynthesisedPlaceName("Unnamed Place of Worship (#12)")).toBe(true);
    expect(isSynthesisedPlaceName("  Unnamed School (#7)  ")).toBe(true);
  });

  it("leaves a real place name alone, including one that merely says unnamed", () => {
    expect(isSynthesisedPlaceName("Hospital Nacional de Sonsonate")).toBe(false);
    expect(isSynthesisedPlaceName("Unnamed Road Clinic")).toBe(false);
    expect(isSynthesisedPlaceName("")).toBe(false);
    expect(isSynthesisedPlaceName(null)).toBe(false);
  });

  it("flags an OSM identifier wherever it appears in a name", () => {
    expect(containsOsmIdentifier("Clínica Zacamil (#8812)")).toBe(true);
    expect(containsOsmIdentifier("Clínica Zacamil")).toBe(false);
  });
});

describe("locating hint for an unnamed place", () => {
  it("prefers a street address, then an area, then the operator", () => {
    expect(
      placeLocatingHint({
        osm_tags: {
          "addr:street": "Calle Obrero Mundial",
          "addr:housenumber": "214",
          "addr:city": "Acajutla",
          operator: "MINSAL",
        },
      }),
    ).toBe("Calle Obrero Mundial 214");
    expect(placeLocatingHint({ osm_tags: { "addr:suburb": "Barrio El Centro" } })).toBe(
      "Barrio El Centro",
    );
    expect(placeLocatingHint({ osm_tags: { operator: "MINSAL" } })).toBe("MINSAL");
  });

  it("returns nothing rather than inventing a bearing", () => {
    expect(placeLocatingHint({ osm_tags: { shop: "mall" } })).toBeNull();
    expect(placeLocatingHint({})).toBeNull();
    expect(placeLocatingHint({ osm_tags: { "addr:street": "   " } })).toBeNull();
  });
});

describe("describePlaceName", () => {
  it("replaces the synthesised name with human wording in both locales", () => {
    expect(describePlaceName(placeWith(), "es")).toEqual({
      label: "Centro comercial sin nombre",
      hint: null,
      isUnnamed: true,
    });
    expect(describePlaceName(placeWith(), "en").label).toBe("Unnamed commercial hub");
  });

  it("carries the locating hint when the tags supply one", () => {
    const described = describePlaceName(
      placeWith({ osm_tags: { "addr:street": "Avenida Morazán" } }),
      "es",
    );
    expect(described.hint).toBe("Avenida Morazán");
    expect(described.isUnnamed).toBe(true);
  });

  it("keeps a real name and its localized OSM tag", () => {
    expect(
      describePlaceName(
        placeWith({
          name: "Hospital Nacional",
          osm_tags: { "name:en": "National Hospital" },
        }),
        "en",
      ),
    ).toEqual({ label: "National Hospital", hint: null, isUnnamed: false });
  });

  it("strips a stray identifier instead of discarding the whole name", () => {
    expect(describePlaceName(placeWith({ name: "Clínica Zacamil (#8812)" }), "es")).toEqual(
      { label: "Clínica Zacamil", hint: null, isUnnamed: false },
    );
  });

  it("falls back to generic wording when the category is unrecognised", () => {
    expect(
      describePlaceName(
        { name: "Unnamed Something (#1)", category: "bunker" },
        "es",
      ).label,
    ).toBe("Lugar sin nombre");
  });
});

describe("the dispatch queue never shows an OSM identifier", () => {
  it("renders human wording plus the locating hint instead of the raw name", async () => {
    setAppLocale("es");
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: {
        places: [
          placeWith({
            osm_tags: { "addr:street": "Calle Obrero Mundial", "addr:housenumber": "214" },
          }),
        ],
        selectedPlace: null,
        isLoading: false,
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Centro comercial sin nombre");
    expect(wrapper.text()).toContain("Calle Obrero Mundial 214");
    expect(wrapper.text()).not.toContain("398433965");
    expect(wrapper.text()).not.toMatch(/\(#\d+\)/);
    expect(wrapper.text()).not.toContain("Unnamed");
    wrapper.unmount();
  });

  it("keeps no identifier on screen for any place in a mixed queue", async () => {
    setAppLocale("es");
    const wrapper = mount(PriorityQueuePanel, {
      global: { plugins: [ElementPlus] },
      props: {
        places: [
          placeWith({ id: "mixed-1" }),
          placeWith({ id: "mixed-2", name: "Unnamed School (#771)", category: "school" }),
          placeWith({ id: "mixed-3", name: "Hospital Nacional de Sonsonate" }),
        ],
        selectedPlace: null,
        isLoading: false,
      },
    });
    await flushPromises();

    expect(wrapper.text()).toMatch(/Hospital Nacional de Sonsonate/);
    expect(wrapper.text()).toContain("Centro escolar sin nombre");
    expect(wrapper.text()).not.toMatch(/\(#\d+\)/);
    expect(wrapper.text()).not.toContain("398433965");
    expect(wrapper.text()).not.toContain("771");
    wrapper.unmount();
  });
});

describe("operator-relevant OSM facts", () => {
  it("keeps only the facts that change what a responder does next", () => {
    expect(
      operatorRelevantFacts({
        osm_tags: {
          amenity: "hospital",
          source: "survey 2019",
          wikidata: "Q12345",
          "ref:MINSAL": "SV-1142",
          operator: "MINSAL",
          "addr:street": "Calle Obrero Mundial",
          "addr:housenumber": "214",
          "addr:city": "Acajutla",
          opening_hours: "24/7",
          emergency: "yes",
          "capacity:beds": "120",
          wheelchair: "limited",
        },
      }),
    ).toEqual([
      { key: "operator", text: "MINSAL" },
      { key: "address", text: "Calle Obrero Mundial 214, Acajutla" },
      { key: "openingHours", text: "24/7" },
      { key: "emergency", text: "", flag: "yes" },
      { key: "capacity", text: "120" },
      { key: "wheelchair", text: "", flag: "limited" },
    ]);
  });

  it("returns nothing when the tags carry only cartographic bookkeeping", () => {
    expect(
      operatorRelevantFacts({ osm_tags: { amenity: "clinic", source: "bing" } }),
    ).toEqual([]);
    expect(operatorRelevantFacts(null)).toEqual([]);
  });

  it("refuses a website value that is not an http(s) address", () => {
    expect(
      operatorRelevantFacts({ osm_tags: { website: "hospitalsonsonate.sv" } }),
    ).toEqual([
      {
        key: "website",
        text: "hospitalsonsonate.sv",
        href: "https://hospitalsonsonate.sv/",
      },
    ]);
    // OSM values are contributor-entered free text, so a scripted scheme is
    // dropped rather than rendered as something an operator might tap.
    expect(
      operatorRelevantFacts({ osm_tags: { website: "javascript:alert(1)" } }),
    ).toEqual([]);
  });
});

describe("the triage record shows facts, not a tag dump", () => {
  it("labels each kept fact and never prints the OSM identifier", async () => {
    setAppLocale("es");
    const wrapper = mount(PlaceTriageDrawer, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
      props: {
        visible: true,
        place: placeWith({
          name: "Hospital Nacional de Sonsonate",
          osm_tags: {
            amenity: "hospital",
            wikidata: "Q12345",
            operator: "MINSAL",
            emergency: "yes",
          },
        }),
      },
    });
    await flushPromises();

    const facts = new DOMWrapper(document.body).get('[data-testid="place-facts"]');
    expect(facts.text()).toContain("Operado por");
    expect(facts.text()).toContain("MINSAL");
    expect(facts.text()).toContain("Atiende urgencias");
    expect(facts.text()).toContain("Sí");
    expect(facts.text()).not.toContain("wikidata");
    expect(facts.text()).not.toContain("amenity");
    expect(facts.text()).not.toContain("way/398433965");
    expect(facts.text()).not.toContain("398433965");
    wrapper.unmount();
  });

  it("says so plainly when the map carries nothing further", async () => {
    setAppLocale("es");
    const wrapper = mount(PlaceTriageDrawer, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
      props: {
        visible: true,
        place: placeWith({
          name: "Hospital Nacional de Sonsonate",
          osm_tags: { amenity: "hospital" },
        }),
      },
    });
    await flushPromises();

    expect(
      new DOMWrapper(document.body).get('[data-testid="place-facts"]').text(),
    ).toBe("El mapa no tiene más datos de este lugar.");
    wrapper.unmount();
  });
});
