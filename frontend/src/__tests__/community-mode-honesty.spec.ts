import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import { apiClient } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import CommunityTriagePanel from "../modules/community-triage/CommunityTriagePanel.vue";
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

describe("mode control and honesty line", () => {
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

  it("offers the mode as ONE labelled radio group, not a badge plus two buttons", async () => {
    const { wrapper } = await mountPanel();
    const group = wrapper.get('[role="radiogroup"]');
    expect(group.attributes("aria-label")).toBe("Mode");
    const radios = group.findAll('input[type="radio"]');
    expect(radios).toHaveLength(2);
    expect((radios[0].element as HTMLInputElement).checked).toBe(true);
    expect(wrapper.findAll('[data-testid="mode-badge"]')).toHaveLength(1);
  });

  it("always shows the displayed mode in a polite live region", async () => {
    const { wrapper, store } = await mountPanel();
    const line = () => wrapper.get('[data-testid="mode-badge"]');
    expect(line().attributes("role")).toBe("status");
    expect(line().attributes("aria-live")).toBe("polite");
    expect(line().text()).toContain("Baseline");
    await store.selectEvent(EVENT_ID);
    await flushPromises();
    expect(line().text()).toContain("Event");
  });

  it("keeps stating the displayed mode while an event is being chosen", async () => {
    const { wrapper } = await mountPanel();
    const eventRadio = wrapper.findAll('input[type="radio"]')[1];
    await eventRadio.setValue(true);
    await flushPromises();
    expect(wrapper.get('[data-testid="mode-badge"]').text()).toContain("Baseline");
    expect(wrapper.get('[data-testid="mode-badge"]').text()).toContain("Pick an earthquake");
  });

  it("always shows the one-line honesty statement, with the long text collapsed", async () => {
    const { wrapper } = await mountPanel();
    const notice = wrapper.get('[data-testid="honesty-notice"]');
    expect(notice.get(".short").text()).toContain("relative ranking of territories, not of people");
    expect(notice.get(".short").text()).toContain("never reports victims or casualties");
    const details = notice.get("details");
    expect(details.attributes("open")).toBeUndefined();
    expect(details.get("summary").text()).toBe("How to read this and its limits");
  });

  it("keeps the full limits reachable in one click and keeps the attribution", async () => {
    const { wrapper } = await mountPanel();
    const details = wrapper.get('[data-testid="honesty-notice"] details');
    await details.get("summary").trigger("click");
    (details.element as HTMLDetailsElement).open = true;
    const text = details.text();
    for (const phrase of [
      "relative ranking of territories (districts), not of people",
      "never reports victims or casualties",
      "estimate of residents",
      "construction quality",
      "urban poverty",
      "earthquakes only",
      "BCR/ONEC, CPV 2024",
    ]) {
      expect(text).toContain(phrase);
    }
  });
});
