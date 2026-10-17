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
  baselineIndex,
  eventIndex,
} from "./fixtures/prioFixtures";

async function mountPanel(props: Record<string, unknown> = {}, eventMode = false) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const wrapper = mount(CommunityTriagePanel, {
    props,
    global: { plugins: [pinia, ElementPlus] },
    attachTo: document.body,
  });
  await flushPromises();
  const store = useCommunityTriageStore();
  if (eventMode) {
    await store.selectEvent(EVENT_ID);
    await flushPromises();
  }
  return { wrapper, store };
}

const rows = (w: ReturnType<typeof mount>) => w.findAll('[data-testid="district-row"]');

describe("ranking rows", () => {
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

  it("is three columns: rank, district with its department beneath, score with a mini bar", async () => {
    const { wrapper } = await mountPanel({}, true);
    const first = rows(wrapper)[0];
    expect(first.get(".rank").text()).toBe("1");
    expect(first.get(".who .name").text()).toBe("San Marcos Rojo");
    expect(first.get(".who .dept").text()).toBe("San Salvador");
    expect(first.get(".score").text()).toBe("8.4");
    expect(first.find('[data-testid="score-bar"]').exists()).toBe(true);
    // exposed population and the dimensions belong to the detail, not to every row
    expect(first.text()).not.toMatch(/exposed|no estimate|52,000/);
    expect(first.find('[data-testid="dim-bar"]').exists()).toBe(false);
    const label = first.attributes("aria-label") ?? "";
    expect(label).toContain("San Marcos Rojo");
    expect(label).toContain("San Salvador");
    expect(label).toContain("rank 1");
    expect(label).toContain("Priority 8.4");
  });

  it("carries the class as an edge colour plus a pips icon, never as a pill per row", async () => {
    const { wrapper } = await mountPanel({}, true);
    const first = rows(wrapper)[0];
    expect(first.classes()).toContain("eoc-class-roja");
    expect(first.find(".pips").exists()).toBe(true);
    expect(wrapper.findAll(".class-badge")).toHaveLength(0);
  });

  it("shows a withheld district by name only: no rank, score, bar or figures", async () => {
    const { wrapper } = await mountPanel({}, true);
    const withheld = rows(wrapper).find((r) => r.text().includes("Reservado Sur"))!;
    expect(withheld.text()).toContain("Withheld");
    expect(withheld.get(".rank").text()).toBe("—");
    expect(withheld.find('[data-testid="score-bar"]').exists()).toBe(false);
    expect(withheld.text()).not.toMatch(/7\.7|777/);
    expect(withheld.html()).not.toContain(String(REDACTED_LEAK));
    expect(withheld.attributes("aria-label")).not.toMatch(/7\.7/);
  });

  it("states the class once per group instead of on every row", async () => {
    const { wrapper } = await mountPanel();
    const heads = wrapper.findAll('[data-testid="group-head"]').map((h) => h.text());
    expect(heads[0]).toContain("Very high structural risk");
    expect(heads[0]).toContain("1");
    expect(heads[1]).toContain("Low structural risk");
    expect(wrapper.findAll(".class-badge")).toHaveLength(0);
  });

  it("uses the alert class names for the groups in event mode", async () => {
    const { wrapper } = await mountPanel({}, true);
    const heads = wrapper.findAll('[data-testid="group-head"]').map((h) => h.text());
    expect(heads.some((h) => h.includes("Red"))).toBe(true);
    expect(heads.some((h) => h.includes("Withheld"))).toBe(true);
  });
});

describe("scope, sort and filters", () => {
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

  it("defaults to the work zone's department and says how many of the country are shown", async () => {
    const { wrapper } = await mountPanel({ zoneDepartment: "San Salvador" });
    expect(rows(wrapper)).toHaveLength(1);
    expect(wrapper.get('[data-testid="list-count"]').text()).toBe("Showing 1 of 2 districts");
  });

  it("widens to the whole country in one click and back", async () => {
    const { wrapper } = await mountPanel({ zoneDepartment: "San Salvador" });
    const scope = wrapper.get('[aria-label="Scope"]');
    const radios = scope.findAll('input[type="radio"]');
    expect(radios).toHaveLength(2);
    await radios[1].setValue(true);
    await flushPromises();
    expect(rows(wrapper)).toHaveLength(2);
    expect(wrapper.get('[data-testid="list-count"]').text()).toBe("Showing 2 of 2 districts");
    await radios[0].setValue(true);
    await flushPromises();
    expect(rows(wrapper)).toHaveLength(1);
  });

  it("does not guess a zone: an unresolvable department shows the whole country, labelled", async () => {
    const { wrapper } = await mountPanel({ zoneDepartment: "Atlantis" });
    expect(rows(wrapper)).toHaveLength(2);
    expect(wrapper.find('[aria-label="Scope"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="scope-label"]').text()).toBe("Whole country");
  });

  it("sorts by name into a flat list without group headings", async () => {
    const { wrapper } = await mountPanel();
    const sort = wrapper.get('[aria-label="Sort by"]');
    const byName = sort.findAll("label").find((l) => l.text() === "Name")!;
    await byName.get("input").setValue(true);
    await flushPromises();
    expect(rows(wrapper)[0].text()).toContain("Lejos Verde");
    expect(wrapper.findAll('[data-testid="group-head"]')).toHaveLength(0);
  });

  it("offers the exposed sort only when an event exists", async () => {
    const { wrapper } = await mountPanel();
    expect(wrapper.get('[aria-label="Sort by"]').text()).not.toContain("Exposed");
    const { wrapper: event } = await mountPanel({}, true);
    expect(event.get('[aria-label="Sort by"]').text()).toContain("Exposed");
  });

  it("labels the search and merges the level filter and legend into one segmented control", async () => {
    const { wrapper } = await mountPanel();
    expect(wrapper.find('input[aria-label="Search district"]').exists()).toBe(true);
    const group = wrapper.get('[role="radiogroup"][aria-label="Filter by level"]');
    const radios = group.findAll('input[type="radio"]');
    expect(radios).toHaveLength(5);
    expect((radios[0].element as HTMLInputElement).checked).toBe(true);
    // the legend: every option names its level and its count
    expect(group.text()).toContain("Very high");
    expect(group.text()).toMatch(/All\s*2/);
    await radios[1].setValue(true);
    await flushPromises();
    expect(rows(wrapper)).toHaveLength(1);
    expect(wrapper.get('[data-testid="list-count"]').attributes("aria-live")).toBe("polite");
  });

  it("explains an empty result and offers to clear the filters", async () => {
    const { wrapper } = await mountPanel();
    await wrapper.get('input[aria-label="Search district"]').setValue("zzzz");
    await flushPromises();
    expect(rows(wrapper)).toHaveLength(0);
    const empty = wrapper.get(".state.empty");
    expect(empty.text()).toContain("No district matches.");
    expect(empty.findAll("button")).toHaveLength(1);
    const clear = empty.get("button");
    expect(clear.text()).toBe("Clear filters");
    await clear.trigger("click");
    await flushPromises();
    expect(rows(wrapper)).toHaveLength(2);
  });

  it("moves between rows with the arrow keys and keeps a single tab stop", async () => {
    const { wrapper } = await mountPanel();
    const list = rows(wrapper);
    expect(list.map((r) => r.attributes("tabindex"))).toEqual(["0", "-1"]);
    await list[0].trigger("keydown", { key: "ArrowDown" });
    expect(document.activeElement).toBe(list[1].element);
    await list[1].trigger("keydown", { key: "ArrowUp" });
    expect(document.activeElement).toBe(list[0].element);
    await list[0].trigger("keydown", { key: "End" });
    expect(document.activeElement).toBe(list[1].element);
  });

  it("shows a calm, retryable message when the ranking fails to load", async () => {
    vi.mocked(apiClient.getPrioIndex).mockRejectedValue(new Error("boom 500"));
    const { wrapper, store } = await mountPanel();
    expect(store.error).not.toBeNull();
    const alert = wrapper.get('[role="alert"]');
    expect(alert.text()).toContain("Could not load the district ranking.");
    expect(alert.text()).not.toContain("boom");
    vi.mocked(apiClient.getPrioIndex).mockResolvedValue(baselineIndex());
    await alert.get("button").trigger("click");
    await flushPromises();
    expect(rows(wrapper)).toHaveLength(2);
  });
});
