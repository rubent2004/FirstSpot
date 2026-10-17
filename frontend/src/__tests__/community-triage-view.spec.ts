import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import { apiClient } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import CommunityTriagePanel from "../modules/community-triage/CommunityTriagePanel.vue";
import { useCommunityTriageStore } from "../stores/useCommunityTriageStore";
import {
  EVENT_ID,
  REDACTED_LEAK,
  auditFor,
  baselineIndex,
  eventIndex,
  redDistrict,
  zeroDistrict,
} from "./fixtures/prioFixtures";

async function mountPanel() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const wrapper = mount(CommunityTriagePanel, {
    global: { plugins: [pinia, ElementPlus] },
    attachTo: document.body,
  });
  await flushPromises();
  return { wrapper, store: useCommunityTriageStore() };
}

describe("CommunityTriagePanel", () => {
  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getPrioIndex").mockImplementation(async (eventId) =>
      eventId ? eventIndex() : baselineIndex(),
    );
    vi.spyOn(apiClient, "listHazardEvents").mockResolvedValue({
      events: [
        {
          event_id: EVENT_ID,
          magnitude: 6.6,
          place: "Offshore San Salvador",
          latitude: 13.6,
          longitude: -88.9,
          depth_km: 60,
          occurred_at: "2001-02-13T14:22:05Z",
          has_shakemap: true,
          has_pager: true,
          url: null,
        },
      ],
      pager_alert_bands: [],
      declared_gaps: [],
      source: "x",
    });
    vi.spyOn(apiClient, "getPrioAudit").mockImplementation(async (code) =>
      auditFor(code === zeroDistrict.district_code ? zeroDistrict : redDistrict),
    );
  });

  it("always says which mode it is displaying, baseline first", async () => {
    const { wrapper } = await mountPanel();
    const badge = wrapper.get('[data-testid="mode-badge"]');
    expect(badge.text()).toContain("Baseline");
    expect(wrapper.text()).toContain("No earthquake");
  });

  it("switches to event mode and shows the event, ShakeMap time and PAGER range", async () => {
    const { wrapper, store } = await mountPanel();
    await store.selectEvent(EVENT_ID);
    await flushPromises();
    expect(wrapper.get('[data-testid="mode-badge"]').text()).toContain("Event");
    const facts = wrapper.get('[data-testid="event-facts"]').text();
    expect(facts).toContain("Offshore San Salvador");
    expect(facts).toContain("2023-06-30 08:15 UTC");
    expect(facts).toContain("orange 100–999");
    expect(facts).toContain("range, not a count");
  });

  it("keeps the honesty notice visible with the declared gaps", async () => {
    const { wrapper } = await mountPanel();
    const notice = wrapper.get('[data-testid="honesty-notice"]').text();
    expect(notice).toContain("relative ranking of territories (districts), not of people");
    expect(notice).toContain("never reports victims or casualties");
    expect(notice).toContain("estimate of residents");
    expect(notice).toContain("construction quality");
    expect(notice).toContain("urban poverty");
    expect(notice).toContain("earthquakes only");
  });

  it("explains a zero score instead of showing a bare zero", async () => {
    const { wrapper, store } = await mountPanel();
    await store.selectEvent(EVENT_ID);
    await store.selectDistrict(zeroDistrict.district_code);
    await flushPromises();
    const detail = wrapper.get('[data-testid="zero-reason"]').text();
    expect(detail).toContain("did not reach this district");
    expect(detail).toContain("does not say the district is poor");
    expect(wrapper.text()).not.toContain("BACKEND ENGLISH ZERO REASON");
  });

  it("labels Sphere figures as a minimum requirement for red districts", async () => {
    const { wrapper, store } = await mountPanel();
    await store.selectEvent(EVENT_ID);
    await store.selectDistrict(redDistrict.district_code);
    await flushPromises();
    const sphere = wrapper.get('[data-testid="sphere-block"]').text();
    expect(sphere).toContain("Sphere minimum requirement");
    expect(wrapper.text()).not.toMatch(/resources to deliver/i);
  });

  it("shows a withheld district as withheld and never its figures", async () => {
    const { wrapper, store } = await mountPanel();
    await store.selectEvent(EVENT_ID);
    await flushPromises();
    expect(wrapper.text()).toContain("Withheld");
    expect(wrapper.html()).not.toContain(String(REDACTED_LEAK));
    expect(wrapper.html()).not.toContain("777,777");
  });

  it("never lets a district code, event id or OSM id reach the DOM", async () => {
    const { wrapper, store } = await mountPanel();
    await store.selectEvent(EVENT_ID);
    await store.selectDistrict(redDistrict.district_code);
    await flushPromises();
    const html = wrapper.html();
    for (const forbidden of ["060101", "010203", "090909", EVENT_ID]) {
      expect(html).not.toContain(forbidden);
    }
    expect(html).not.toMatch(/\b(node|way|relation)[/ ]\d{4,}/i);
    expect(html).not.toContain("inform_rescaled_score");
    expect(html).not.toContain("hazard_and_exposure");
  });

  it("renders in Spanish with no English copy for the mode", async () => {
    setAppLocale("es");
    const { wrapper } = await mountPanel();
    expect(wrapper.get('[data-testid="mode-badge"]').text()).toContain("Línea base");
    expect(wrapper.get('[data-testid="honesty-notice"]').text()).toContain(
      "no de personas",
    );
    setAppLocale("en");
  });
});
