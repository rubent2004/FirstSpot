import { afterEach, describe, expect, it } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import type { PlaceRead } from "../api/client";
import { describePlaceName, setAppLocale } from "../i18n/useI18n";
import {
  containsOsmIdentifier,
  isSynthesisedPlaceName,
  placeLocatingHint,
} from "../utils/placeName";
import PriorityQueuePanel from "../modules/priority-queue/PriorityQueuePanel.vue";

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
