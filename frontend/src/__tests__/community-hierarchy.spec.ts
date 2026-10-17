import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import { h } from "vue";
import ElementPlus from "element-plus";

import { apiClient } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import CommunityTriagePanel from "../modules/community-triage/CommunityTriagePanel.vue";
import {
  auditFor,
  baselineIndex,
  eventIndex,
  redDistrict,
} from "./fixtures/prioFixtures";

async function mountPanel() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const wrapper = mount(CommunityTriagePanel, {
    props: { zoneName: "Sonsonate", zoneDepartment: null },
    slots: { places: () => h("div", { "data-testid": "places-slot" }, "queue") },
    global: { plugins: [pinia, ElementPlus] },
    attachTo: document.body,
  });
  await flushPromises();
  return wrapper;
}

const rows = (w: ReturnType<typeof mount>) => w.findAll('[data-testid="district-row"]');
const announcer = (w: ReturnType<typeof mount>) => w.get('[data-testid="announcer"]');

describe("district-first hierarchy", () => {
  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getPrioIndex").mockImplementation(async (eventId) =>
      eventId ? eventIndex() : baselineIndex(),
    );
    vi.spyOn(apiClient, "listHazardEvents").mockResolvedValue({
      events: [],
      pager_alert_bands: [],
      declared_gaps: [],
      source: "x",
    });
    vi.spyOn(apiClient, "getPrioAudit").mockImplementation(async () => auditFor(redDistrict));
  });

  it("opens on the district ranking and has no peer tabs", async () => {
    const wrapper = await mountPanel();
    expect(wrapper.find('[role="tablist"]').exists()).toBe(false);
    expect(wrapper.get("h2").text()).toBe("Priority by district");
    expect(rows(wrapper).length).toBeGreaterThan(0);
    expect(wrapper.find('[data-testid="places-slot"]').exists()).toBe(false);
  });

  it("opens one district in a side panel, keeps the list, moves focus in and announces it", async () => {
    const wrapper = await mountPanel();
    const listBefore = rows(wrapper).length;
    await rows(wrapper)[0].trigger("click");
    await flushPromises();

    const aside = wrapper.get('[data-testid="detail-aside"]');
    expect(aside.element.tagName).toBe("ASIDE");
    expect(aside.attributes("aria-label")).toBe("San Marcos Rojo");
    expect(rows(wrapper)).toHaveLength(listBefore);
    expect(wrapper.findAll('[data-testid="detail-panel"]')).toHaveLength(1);
    const heading = wrapper.get('[data-testid="detail-heading"]');
    expect(heading.attributes("tabindex")).toBe("-1");
    expect(document.activeElement).toBe(heading.element);
    expect(announcer(wrapper).attributes("role")).toBe("status");
    expect(announcer(wrapper).text()).toBe("Detail opened: San Marcos Rojo");
  });

  it("closes with its button and puts focus back on the row that was opened", async () => {
    const wrapper = await mountPanel();
    await rows(wrapper)[0].trigger("click");
    await flushPromises();
    await wrapper.get('[data-testid="detail-aside"] button').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="detail-aside"]').exists()).toBe(false);
    expect(document.activeElement).toBe(rows(wrapper)[0].element);
    expect(announcer(wrapper).text()).toBe("District list");
  });

  it("Escape closes the detail", async () => {
    const wrapper = await mountPanel();
    await rows(wrapper)[0].trigger("click");
    await flushPromises();
    await wrapper.get('[data-testid="detail-aside"]').trigger("keydown", { key: "Escape" });
    await flushPromises();
    expect(wrapper.find('[data-testid="detail-aside"]').exists()).toBe(false);
  });

  it("orders the detail by what the operator needs: score and drivers, then places, then folded technicals", async () => {
    const wrapper = await mountPanel();
    await rows(wrapper)[0].trigger("click");
    await flushPromises();
    const detail = wrapper.get('[data-testid="detail-panel"]');
    const order = Array.from(detail.element.children).map((el) => el.className || el.tagName);
    const at = (needle: string) => order.findIndex((c) => c.includes(needle));
    expect(at("summary")).toBeLessThan(at("block"));
    expect(at("fold")).toBe(order.length - 1);
    expect(detail.find('[data-testid="detail-places"]').exists()).toBe(true);

    const drivers = detail.get(".block .dims").findAll("li");
    expect(drivers.length).toBeLessThanOrEqual(3);
    const scores = drivers.map((li) => Number(li.get("strong").text()));
    expect(scores).toEqual([...scores].sort((a, b) => b - a));

    const fold = detail.get("details.fold");
    expect(fold.attributes("open")).toBeUndefined();
    expect(fold.get("summary").text()).toBe("Indicators, Sphere needs and sources");
  });

  it("keeps the Sphere figures inside the fold and labelled as a minimum", async () => {
    const wrapper = await mountPanel();
    await wrapper.vm.$nextTick();
    const store = (await import("../stores/useCommunityTriageStore")).useCommunityTriageStore();
    await store.selectEvent("usp000a9jv");
    await flushPromises();
    await rows(wrapper)[0].trigger("click");
    await flushPromises();
    const sphere = wrapper.get("details.fold [data-testid='sphere-block']");
    expect(sphere.text()).toContain("Sphere minimum requirement");
  });

  it("shows exposed population, or 'no estimate' when it is missing: never 0", async () => {
    const wrapper = await mountPanel();
    const store = (await import("../stores/useCommunityTriageStore")).useCommunityTriageStore();
    vi.mocked(apiClient.getPrioIndex).mockImplementation(async () => {
      const index = eventIndex();
      index.districts = index.districts.map((d) =>
        d.district_code === redDistrict.district_code
          ? { ...d, estimated_exposed_population: null }
          : d,
      );
      return index;
    });
    vi.mocked(apiClient.getPrioAudit).mockImplementation(async () => ({
      ...auditFor(redDistrict),
      estimated_exposed_population: null,
    }));
    await store.selectEvent("usp000a9jv");
    await flushPromises();
    await rows(wrapper)[0].trigger("click");
    await flushPromises();
    const exposed = wrapper.get('[data-testid="detail-exposed"]').text();
    expect(exposed).toContain("no estimate");
    expect(exposed).not.toMatch(/\b0\b/);
  });

  it("shows a real zero as 0", async () => {
    const wrapper = await mountPanel();
    const store = (await import("../stores/useCommunityTriageStore")).useCommunityTriageStore();
    vi.mocked(apiClient.getPrioAudit).mockImplementation(async () => ({
      ...auditFor(redDistrict),
      estimated_exposed_population: 0,
    }));
    await store.selectEvent("usp000a9jv");
    await flushPromises();
    await rows(wrapper)[0].trigger("click");
    await flushPromises();
    const exposed = wrapper.get('[data-testid="detail-exposed"]').text();
    expect(exposed).toMatch(/\b0\b/);
    expect(exposed).not.toContain("no estimate");
  });

  it("shows a real figure with its thousands separator", async () => {
    const wrapper = await mountPanel();
    const store = (await import("../stores/useCommunityTriageStore")).useCommunityTriageStore();
    await store.selectEvent("usp000a9jv");
    await flushPromises();
    await rows(wrapper)[0].trigger("click");
    await flushPromises();
    expect(wrapper.get('[data-testid="detail-exposed"]').text()).toContain("52,000");
  });

  it("reaches the places of the work zone from the detail, replacing the list with the zone queue", async () => {
    const wrapper = await mountPanel();
    await rows(wrapper)[0].trigger("click");
    await flushPromises();
    const open = wrapper.findAll("button").find((b) => b.text() === "See places in Sonsonate")!;
    await open.trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="places-slot"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="detail-aside"]').exists()).toBe(false);
    const crumbs = wrapper.get('nav[aria-label="Where you are"]');
    expect(crumbs.get("button").text()).toContain("Districts");
    expect(crumbs.get('[aria-current="page"]').text()).toBe("Places in Sonsonate");
    expect(announcer(wrapper).text()).toBe("Places in the Sonsonate zone");
  });

  it("also reaches the zone's places from the overview, and comes back to the list", async () => {
    const wrapper = await mountPanel();
    const open = wrapper.findAll("button").find((b) => b.text() === "See places in Sonsonate")!;
    await open.trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="places-slot"]').exists()).toBe(true);
    await wrapper.get('nav[aria-label="Where you are"] button').trigger("click");
    await flushPromises();
    expect(rows(wrapper).length).toBeGreaterThan(0);
    expect(wrapper.find('[data-testid="places-slot"]').exists()).toBe(false);
  });
});
