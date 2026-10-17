import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import { apiClient } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import CommunityTriagePanel from "../modules/community-triage/CommunityTriagePanel.vue";
import { buildReportModel } from "../modules/community-triage/exportModel";
import { buildWorkbookSheets } from "../modules/community-triage/exportXlsx";
import { COMMUNITY_EN } from "../i18n/communityMessages";
import { useCommunityTriageStore } from "../stores/useCommunityTriageStore";
import { EVENT_ID, baselineIndex, eventIndex } from "./fixtures/prioFixtures";

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

const ALERT_NAMES = [/\bRed\b/, /\bOrange\b/, /\bYellow\b/, /\bGreen\b/];

describe("alert colours belong to event mode only", () => {
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
  });

  it("baseline never carries an alert class or an alert label", async () => {
    const { wrapper } = await mountPanel();
    const html = wrapper.html();
    expect(html).not.toMatch(/eoc-class-(roja|naranja|amarilla|verde)/);
    for (const name of ALERT_NAMES) expect(wrapper.text()).not.toMatch(name);
    expect(html).toContain("eoc-level-");
    expect(wrapper.text()).toMatch(/Very high|High|Medium|Low/);
  });

  it("event mode does use the four alert classes", async () => {
    const { wrapper, store } = await mountPanel();
    await store.selectEvent(EVENT_ID);
    await flushPromises();
    expect(wrapper.html()).toMatch(/eoc-class-roja/);
    expect(wrapper.text()).toMatch(/\bRed\b/);
    expect(wrapper.html()).not.toContain("eoc-level-");
  });

  it("exports name the classes with the scale of their own mode", () => {
    const now = new Date("2026-10-17T12:30:00Z");
    const baseline = buildReportModel(baselineIndex(), COMMUNITY_EN, "en", now);
    expect(baseline.classes.map((c) => c.name)).toEqual(["Very high", "High", "Medium", "Low"]);
    const event = buildReportModel(eventIndex(), COMMUNITY_EN, "en", now);
    expect(event.classes.map((c) => c.name)).toEqual(["Red", "Orange", "Yellow", "Green"]);
    const cells = buildWorkbookSheets(baseline, COMMUNITY_EN, "en")[0]
      .data.flat()
      .map((c) => (c && typeof c === "object" && "value" in c ? c.value : c));
    for (const name of ALERT_NAMES) expect(cells.join("|")).not.toMatch(name);
  });
});
