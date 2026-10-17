import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import ElementPlus from "element-plus";
import GeoRibbon from "../components/GeoRibbon.vue";
import type { PredefinedZoneRead } from "../api/client";
import type { PlaceFilters } from "../stores/usePrioritizationStore";

const zones: PredefinedZoneRead[] = [
  {
    key: "sonsonate",
    name: "Sonsonate",
    department: "Sonsonate",
    latitude: 13.7222,
    longitude: -89.7236,
    default_radius_meters: 10000,
  },
];

const mountedRibbons: VueWrapper[] = [];
const RIBBON_KEY = "firstspot.ribbon.v1";

function makeFilters(search = "Escuela"): PlaceFilters {
  return {
    category: "",
    vulnerabilityGroup: "",
    attentionStatus: "",
    minUrgency: null,
    search,
    includeAttendedInHeatmap: true,
  };
}

function mountRibbon(filters = makeFilters(), attachToBody = false): VueWrapper {
  const wrapper = mount(GeoRibbon, {
    props: {
      zones,
      selectedZoneKey: "sonsonate",
      activeZoneName: "Sonsonate",
      isSyncing: false,
      isLoading: false,
      hasError: false,
      radiusEnabled: false,
      radiusMeters: 3000,
      isDark: false,
      locale: "es",
      showHeatmapLayer: true,
      showMarkersLayer: true,
      showHazardsLayer: true,
      tacticalBasemap: false,
      filters,
    },
    global: { plugins: [ElementPlus] },
    attachTo: attachToBody ? document.body : undefined,
  });
  mountedRibbons.push(wrapper);
  return wrapper;
}

afterEach(() => {
  for (const wrapper of mountedRibbons.splice(0)) wrapper.unmount();
  document.body.innerHTML = "";
  vi.useRealTimers();
});

describe("GeoRibbon actions", () => {
  it("uses the transparent FirstSpot brand asset in the title bar", () => {
    const wrapper = mountRibbon();
    const logo = wrapper.find(".geo-brand img");

    expect(logo.exists()).toBe(true);
    expect(logo.attributes("src")).toBe("/firstspot-logo.svg");
    expect(logo.attributes("alt")).toBe("");
  });

  it("supports accessible tab semantics and arrow-key navigation", async () => {
    const wrapper = mountRibbon();
    const tabs = wrapper.findAll('[role="tab"]');

    expect(tabs).toHaveLength(5);
    expect(tabs[0].attributes("aria-selected")).toBe("true");
    await tabs[0].trigger("keydown", { key: "ArrowRight" });
    expect(tabs[1].attributes("aria-selected")).toBe("true");
    expect(tabs[0].attributes("tabindex")).toBe("-1");
    expect(tabs[1].attributes("tabindex")).toBe("0");

    await tabs[1].trigger("keydown", { key: "End" });
    expect(tabs[4].attributes("aria-selected")).toBe("true");
  });

  it("can minimize and restore the ribbon command area", async () => {
    const wrapper = mountRibbon();
    const toggle = wrapper.find(".ribbon-expand-toggle");
    const panel = wrapper.find("#geo-ribbon-panel");

    expect(toggle.attributes("aria-expanded")).toBe("true");
    expect((panel.element as HTMLElement).style.display).not.toBe("none");

    await toggle.trigger("click");
    expect(toggle.attributes("aria-expanded")).toBe("false");
    expect((panel.element as HTMLElement).style.display).toBe("none");

    await toggle.trigger("click");
    expect(toggle.attributes("aria-expanded")).toBe("true");
    expect((panel.element as HTMLElement).style.display).not.toBe("none");
  });

  describe("remembering the collapsed state", () => {
    class MemoryStorage {
      private data = new Map<string, string>();
      getItem(key: string) {
        return this.data.get(key) ?? null;
      }
      setItem(key: string, value: string) {
        this.data.set(key, value);
      }
    }

    beforeEach(() => {
      Object.defineProperty(window, "localStorage", { value: new MemoryStorage(), configurable: true });
    });

    it("remembers a collapsed ribbon under a namespaced, versioned key", async () => {
      const first = mountRibbon();
      await first.find(".ribbon-expand-toggle").trigger("click");
      expect(JSON.parse(window.localStorage.getItem(RIBBON_KEY)!)).toEqual({ version: 1, collapsed: true });
      first.unmount();

      const second = mountRibbon();
      expect(second.find(".ribbon-expand-toggle").attributes("aria-expanded")).toBe("false");
      expect((second.find("#geo-ribbon-panel").element as HTMLElement).style.display).toBe("none");
    });

    it("starts expanded when nothing was remembered or the value is junk", () => {
      expect(mountRibbon().find(".ribbon-expand-toggle").attributes("aria-expanded")).toBe("true");
      window.localStorage.setItem(RIBBON_KEY, "{broken");
      expect(mountRibbon().find(".ribbon-expand-toggle").attributes("aria-expanded")).toBe("true");
    });

    it("collapses and restores with Ctrl+F1", async () => {
      const wrapper = mountRibbon();
      const toggle = wrapper.find(".ribbon-expand-toggle");
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "F1", ctrlKey: true }));
      await flushPromises();
      expect(toggle.attributes("aria-expanded")).toBe("false");
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "F1", ctrlKey: true }));
      await flushPromises();
      expect(toggle.attributes("aria-expanded")).toBe("true");
    });

    it("names the shortcut on the toggle", () => {
      expect(mountRibbon().find(".ribbon-expand-toggle").attributes("title")).toContain("Ctrl F1");
    });
  });

  it("routes toolbar actions from each tab to the app", async () => {
    const wrapper = mountRibbon();

    await wrapper.findAll(".geo-big-tool").find((button) =>
      button.text().includes("Centrar zona"),
    )!.trigger("click");
    await wrapper.findAll(".geo-small-tool").find((button) =>
      button.text().includes("Ajustar datos"),
    )!.trigger("click");
    await wrapper.findAll(".geo-big-tool").find((button) =>
      button.text().includes("Amenazas"),
    )!.trigger("click");
    await wrapper.findAll(".geo-small-tool").find((button) =>
      button.text().includes("Restablecer filtros"),
    )!.trigger("click");
    expect(wrapper.emitted("center-map")).toHaveLength(1);
    expect(wrapper.emitted("fit-map")).toHaveLength(1);
    expect(wrapper.emitted("refresh-hazards")).toHaveLength(1);
    expect(wrapper.emitted("reset-filters")).toHaveLength(1);

    await wrapper.findAll(".geo-tab")[1].trigger("click");
    const refreshLayers = wrapper.findAll(".geo-big-tool").find((button) =>
      button.text().includes("Sincronizar lugares"),
    );
    expect(refreshLayers).toBeDefined();
    await refreshLayers!.trigger("click");
    expect(wrapper.emitted("sync-zone")).toHaveLength(1);

    await wrapper.findAll(".geo-tab")[3].trigger("click");
    await wrapper.find(".geo-radius-editor .el-switch").trigger("click");
    expect(wrapper.emitted("update:radius-enabled")?.[0]).toEqual([true]);

    await wrapper.findAll(".geo-tab")[4].trigger("click");
    const themeTool = wrapper.findAll(".geo-big-tool").find((button) =>
      button.text().includes("Modo oscuro"),
    );
    await themeTool!.trigger("click");
    expect(wrapper.emitted("toggle-theme")).toHaveLength(1);
  });

  it("lets the user adjust the radius in kilometers, with presets and map guidance", async () => {
    const wrapper = mountRibbon();
    await wrapper.findAll(".geo-tab")[3].trigger("click");

    expect(wrapper.find(".geo-radius-editor").text()).toContain(
      "Activa y haz clic en el mapa para elegir el centro",
    );
    const radiusInput = wrapper.findComponent({ name: "ElInputNumber" });
    expect(radiusInput.exists()).toBe(true);
    expect(radiusInput.props("modelValue")).toBe(3);
    expect(wrapper.findAll(".geo-radius-preset").map((preset) => preset.text())).toEqual([
      "500 m", "1 km", "3 km", "5 km", "10 km", "25 km",
    ]);

    radiusInput.vm.$emit("update:modelValue", 4.5);
    await flushPromises();
    expect(wrapper.emitted("update:radius-meters")?.at(-1)).toEqual([4500]);

    await wrapper.findAll(".geo-radius-preset")[0].trigger("click");
    expect(wrapper.emitted("update:radius-meters")?.at(-1)).toEqual([500]);
  });

  it("opens Analyze from the home radius summary and displays kilometers", async () => {
    const wrapper = mountRibbon();
    const summary = wrapper.get(".geo-radius-summary");
    expect(summary.text()).toContain("3 km");
    expect(summary.text()).toContain("Editar");

    await summary.trigger("click");
    expect(wrapper.findAll('[role="tab"]')[3].attributes("aria-selected")).toBe("true");
    expect(wrapper.find(".geo-radius-editor").exists()).toBe(true);
  });

  it("keeps the Data ribbon filters connected to the app filter state", async () => {
    vi.useFakeTimers();
    const filters = makeFilters();
    const wrapper = mountRibbon(filters);
    await wrapper.findAll(".geo-tab")[1].trigger("click");

    const search = wrapper.get('[data-testid="ribbon-filter-search"]');
    await search.setValue("hospital");
    expect(filters.search).toBe("hospital");

    expect(wrapper.emitted("filter-change")).toBeUndefined();
    await vi.advanceTimersByTimeAsync(250);
    expect(wrapper.emitted("filter-change")).toHaveLength(1);

    await search.trigger("mouseenter");
    await search.trigger("focus");
    await flushPromises();
    await wrapper.get(".el-input__clear").trigger("click");
    await flushPromises();
    expect(filters.search).toBe("");
    expect(wrapper.emitted("filter-change")).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(250);
    expect(wrapper.emitted("filter-change")).toHaveLength(2);

    await wrapper.setProps({ filters: { ...filters, category: "hospital" } });
    await wrapper.get(".geo-filter-actions .geo-big-tool").trigger("click");
    expect(wrapper.emitted("reset-filters")).toHaveLength(1);
  });

  it("opens Data and focuses the filter search from the command palette", async () => {
    const wrapper = mountRibbon(makeFilters(), true);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    await flushPromises();

    const input = document.body.querySelector<HTMLInputElement>('[role="dialog"] input')!;
    input.value = "Buscar lugar priorizado";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await flushPromises();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await flushPromises();

    expect(wrapper.findAll('[role="tab"]')[1].attributes("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(
      wrapper.get('[data-testid="ribbon-filter-search"]').element,
    );
  });

  it("disables clear-filter actions when no filters are active", async () => {
    const wrapper = mountRibbon(makeFilters(""));
    await wrapper.findAll(".geo-tab")[1].trigger("click");

    expect(wrapper.get(".geo-quick-access .geo-quick:nth-child(2)").attributes("disabled")).toBeDefined();
    expect(wrapper.get(".geo-filter-actions .geo-big-tool").attributes("disabled")).toBeDefined();
    await wrapper.get(".geo-filter-actions .geo-big-tool").trigger("click");
    expect(wrapper.emitted("reset-filters")).toBeUndefined();
  });

  it("exposes synchronized map layers and basemap controls in the Style tab", async () => {
    const wrapper = mountRibbon();
    await wrapper.findAll(".geo-tab")[2].trigger("click");

    const heatmap = wrapper.findAll(".layer-tool").find((button) =>
      button.text().includes("Mapa de calor"),
    );
    expect(heatmap?.attributes("aria-pressed")).toBe("true");
    await heatmap!.trigger("click");
    expect(wrapper.emitted("update:show-heatmap-layer")?.[0]).toEqual([false]);

    const markers = wrapper.findAll(".layer-tool").find((button) =>
      button.text().includes("Marcadores"),
    );
    await markers!.trigger("click");
    expect(wrapper.emitted("update:show-markers-layer")?.[0]).toEqual([false]);

    const hazards = wrapper.findAll(".layer-tool").find((button) =>
      button.text().includes("Amenazas"),
    );
    await hazards!.trigger("click");
    expect(wrapper.emitted("update:show-hazards-layer")?.[0]).toEqual([false]);

    const lightMap = wrapper.findAll(".layer-tool").find((button) =>
      button.text().includes("Mapa claro"),
    );
    await lightMap!.trigger("click");
    expect(wrapper.emitted("update:tactical-basemap")?.[0]).toEqual([false]);

    const tactical = wrapper.findAll(".layer-tool").find((button) =>
      button.text().includes("Mapa táctico"),
    );
    expect(tactical?.attributes("aria-pressed")).toBe("false");
    await tactical!.trigger("click");
    expect(wrapper.emitted("update:tactical-basemap")?.[1]).toEqual([true]);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    await flushPromises();
    const input = document.body.querySelector<HTMLInputElement>('[role="dialog"] input')!;
    input.value = "Abrir Estilo";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await flushPromises();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await flushPromises();
    expect(wrapper.findAll('[role="tab"]')[2].attributes("aria-selected")).toBe("true");
  });

  it("opens the Ctrl+K command palette and executes a filtered command with Enter", async () => {
    const wrapper = mountRibbon();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    await flushPromises();

    const dialog = document.body.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    const input = dialog?.querySelector<HTMLInputElement>("input");
    expect(input).not.toBeNull();
    input!.value = "Centrar mapa";
    input!.dispatchEvent(new Event("input", { bubbles: true }));
    await flushPromises();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await flushPromises();

    expect(wrapper.emitted("center-map")).toHaveLength(1);
    expect(document.body.querySelector('[role="dialog"]')).toBeNull();

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    await flushPromises();
    const reopenedDialog = document.body.querySelector('[role="dialog"]');
    const reopenedInput = reopenedDialog?.querySelector<HTMLInputElement>("input");
    reopenedInput!.value = "Ajustar mapa";
    reopenedInput!.dispatchEvent(new Event("input", { bubbles: true }));
    await flushPromises();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await flushPromises();
    expect(wrapper.emitted("fit-map")).toHaveLength(1);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    await flushPromises();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    await flushPromises();
    expect(document.body.querySelector('[role="dialog"]')).toBeNull();
  });

  it("exposes working project-level quick actions", async () => {
    const wrapper = mountRibbon();
    await wrapper.find(".geo-project-tab").trigger("click");
    await flushPromises();

    const menuItems = Array.from(document.body.querySelectorAll<HTMLElement>(".el-dropdown-menu__item"));
    const syncItem = menuItems.find((item) => item.textContent?.includes("Sincronizar zona actual"));
    expect(syncItem).toBeDefined();
    syncItem!.click();
    await flushPromises();
    expect(wrapper.emitted("sync-zone")).toHaveLength(1);
  });
});
