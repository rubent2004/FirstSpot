import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import ElementPlus from "element-plus";

import { apiClient } from "../api/client";
import { setAppLocale } from "../i18n/useI18n";
import CommunityTriagePanel from "../modules/community-triage/CommunityTriagePanel.vue";
import { baselineIndex, eventIndex } from "./fixtures/prioFixtures";

const original = window.matchMedia;
let wrapper: VueWrapper | null = null;

function phoneViewport(matches: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: matches && query.includes("max-width: 700px"),
    media: query,
    addEventListener() {},
    removeEventListener() {},
  })) as unknown as typeof window.matchMedia;
}

async function mountPanel() {
  const pinia = createPinia();
  setActivePinia(pinia);
  wrapper = mount(CommunityTriagePanel, {
    props: { zoneName: "Sonsonate", zoneDepartment: "Sonsonate" },
    global: { plugins: [pinia, ElementPlus] },
    attachTo: document.body,
  });
  await flushPromises();
  return wrapper;
}

describe("phone layout", () => {
  beforeEach(() => {
    setAppLocale("en");
    document.body.innerHTML = "";
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getPrioIndex").mockImplementation(async (id) => (id ? eventIndex() : baselineIndex()));
    vi.spyOn(apiClient, "listHazardEvents").mockResolvedValue({ events: [], pager_alert_bands: [], declared_gaps: [], source: "x" });
  });
  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    window.matchMedia = original;
    document.body.innerHTML = "";
  });

  it("is not a bottom sheet on a desktop viewport, and Export sits in the header", async () => {
    phoneViewport(false);
    const app = await mountPanel();
    expect(app.find(".sheet-handle").exists()).toBe(false);
    expect(app.findAll(".head button").some((b) => b.text() === "Export")).toBe(true);
    expect(app.find('button[aria-label="More actions"]').exists()).toBe(false);
  });

  it("is a bottom sheet peeking the list, with a labelled handle that expands it", async () => {
    phoneViewport(true);
    const app = await mountPanel();
    const handle = app.get(".sheet-handle");
    expect(handle.attributes("aria-expanded")).toBe("false");
    expect(handle.attributes("aria-label")).toBe("Expand the list");
    expect(app.get(".triage-panel").classes()).toContain("is-phone");
    expect(app.get(".triage-panel").classes()).not.toContain("is-expanded");
    await handle.trigger("click");
    expect(handle.attributes("aria-expanded")).toBe("true");
    expect(handle.attributes("aria-label")).toBe("Reduce the list");
    expect(app.get(".triage-panel").classes()).toContain("is-expanded");
  });

  it("keeps the mode visible and moves export, limits and feeds under one menu", async () => {
    phoneViewport(true);
    const app = await mountPanel();
    expect(app.find('[data-testid="mode-badge"]').exists()).toBe(true);
    expect(app.findAll(".head button").some((b) => b.text() === "Export")).toBe(false);
    expect(app.find('.columns button[aria-label="How to read this and its limits"]').exists()).toBe(false);
    const more = app.get('button[aria-label="More actions"]');
    expect(more.attributes("aria-haspopup")).toBeDefined();
    await more.trigger("click");
    await flushPromises();
    const items = Array.from(document.body.querySelectorAll(".el-dropdown-menu__item")).map((i) => i.textContent!.trim());
    expect(items).toEqual(expect.arrayContaining(["Export", "How to read this and its limits", "Data sources"]));
  });

  it("opens the limits from the menu with the full text", async () => {
    phoneViewport(true);
    const app = await mountPanel();
    await app.get('button[aria-label="More actions"]').trigger("click");
    await flushPromises();
    const item = Array.from(document.body.querySelectorAll<HTMLElement>(".el-dropdown-menu__item")).find((i) =>
      i.textContent!.includes("limits"),
    )!;
    item.click();
    await flushPromises();
    const dialog = document.body.querySelector('[role="dialog"]')!;
    expect(dialog.textContent).toContain("never reports victims or casualties");
    expect(dialog.textContent).toContain("BCR/ONEC, CPV 2024");
  });

  it("asks the app to open the feeds, which it owns", async () => {
    phoneViewport(true);
    const app = await mountPanel();
    await app.get('button[aria-label="More actions"]').trigger("click");
    await flushPromises();
    Array.from(document.body.querySelectorAll<HTMLElement>(".el-dropdown-menu__item"))
      .find((i) => i.textContent!.includes("Data sources"))!
      .click();
    await flushPromises();
    expect(app.emitted("open-feeds")).toHaveLength(1);
  });

  it("opens the export dialog from the menu", async () => {
    phoneViewport(true);
    const app = await mountPanel();
    await app.get('button[aria-label="More actions"]').trigger("click");
    await flushPromises();
    Array.from(document.body.querySelectorAll<HTMLElement>(".el-dropdown-menu__item"))
      .find((i) => i.textContent!.trim() === "Export")!
      .click();
    await flushPromises();
    expect(document.body.querySelector('[role="dialog"] [data-testid="export-filename"]')).not.toBeNull();
  });
});
