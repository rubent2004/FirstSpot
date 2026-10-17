import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import { apiClient } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import CommunityTriagePanel from "../modules/community-triage/CommunityTriagePanel.vue";
import { useCommunityTriageStore } from "../stores/useCommunityTriageStore";
import { EVENT_ID, baselineIndex, eventIndex } from "./fixtures/prioFixtures";
import { describeEventLabel, localizeEventPlace } from "../modules/community-triage/formatters";
import { communityMessages } from "../i18n/communityMessages";

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

describe("mode control and limits trigger", () => {
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

  it("renders no paragraph-level honesty text by default, only the info trigger", async () => {
    const { wrapper } = await mountPanel();
    expect(wrapper.find('[data-testid="honesty-notice"]').exists()).toBe(false);
    const trigger = wrapper.get('button[aria-label="How to read this and its limits"]');
    expect(trigger.attributes("aria-expanded")).toBe("false");
    expect(trigger.attributes("aria-haspopup")).toBe("dialog");
    expect(wrapper.text()).not.toContain("construction quality");
  });

  it("opens the full limits in one click and keeps the attribution", async () => {
    const { wrapper } = await mountPanel();
    const trigger = wrapper.get('button[aria-label="How to read this and its limits"]');
    await trigger.trigger("click");
    expect(trigger.attributes("aria-expanded")).toBe("true");
    const text = wrapper.get('[data-testid="honesty-notice"]').text();
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

  it("closes with Escape and returns focus to the trigger", async () => {
    const { wrapper } = await mountPanel();
    const trigger = wrapper.get('button[aria-label="How to read this and its limits"]');
    await trigger.trigger("click");
    await flushPromises();
    await wrapper.get('[role="dialog"]').trigger("keydown", { key: "Escape" });
    await flushPromises();
    expect(wrapper.find('[data-testid="honesty-notice"]').exists()).toBe(false);
    expect(document.activeElement).toBe(trigger.element);
  });

  it("the score column header says the priority is relative, even with the popover closed", async () => {
    const { wrapper } = await mountPanel();
    expect(wrapper.get(".columns").text()).toContain("Relative priority");
  });

  it("labels an event the catalogue does not list, never with its raw id", async () => {
    // The catalogue (recent quakes) is empty; the 2001 demo event is chosen directly.
    const { wrapper, store } = await mountPanel();
    await store.selectEvent(EVENT_ID);
    await flushPromises();
    const picker = wrapper.get(".picker");
    expect(picker.text()).toContain("Earthquake M6.6 · Offshore San Salvador · Feb 13, 2001");
    expect(document.body.innerHTML).not.toContain(EVENT_ID);
  });

  it("writes the USGS place and date the Spanish way", () => {
    expect(localizeEventPlace("5 km S of Cojutepeque, El Salvador", "es")).toBe("5 km S de Cojutepeque");
    expect(localizeEventPlace("35 km SSW of Jucuarán, El Salvador", "es")).toBe("35 km SSO de Jucuarán");
    expect(localizeEventPlace("5 km S of Cojutepeque, El Salvador", "en")).toBe("5 km S of Cojutepeque");
    setAppLocale("es");
    const label = describeEventLabel(
      { magnitude: 6.6, place: "5 km S of Cojutepeque, El Salvador", occurred_at: "2001-02-13T14:22:05Z" },
      communityMessages("es"),
      "es",
    );
    expect(label).toBe("Sismo M6.6 · 5 km S de Cojutepeque · 13 feb 2001");
  });
});
