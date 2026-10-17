<script setup lang="ts">
import { computed, ref } from "vue";
import {
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElTag,
} from "element-plus";
import {
  apiClient,
  type ActiveHazardsResponse,
  type GeocodeResultRead,
  type HazardScenarioPreset,
} from "../../api/client";
import Icon0 from "../../components/Icon0.vue";
import { useI18n } from "../../i18n/useI18n";
import { formatExactTime, formatRelativeTime } from "../../utils/date";

const props = withDefaults(
  defineProps<{
    activeHazards: ActiveHazardsResponse | null;
    scenario: HazardScenarioPreset;
    lastCheckedAt?: string | null;
    isRefreshing?: boolean;
    refreshError?: string | null;
  }>(),
  {
    lastCheckedAt: null,
    isRefreshing: false,
    refreshError: null,
  },
);

const emit = defineEmits<{
  (e: "change-scenario", scenario: HazardScenarioPreset): void;
  (e: "fly-to-coordinates", lat: number, lon: number, label: string): void;
}>();

const { locale } = useI18n();

const geocodeQuery = ref<string>("");
const geocodeResults = ref<GeocodeResultRead[]>([]);
const isSearchingGeo = ref<boolean>(false);

const labels = computed(() =>
  locale.value === "es"
    ? {
        feedsBadge: "FEEDS MULTI-AGENCIA EN VIVO",
        weatherTitle: "Clima Open-Meteo",
        rain: "Lluvia",
        gusts: "Ráfagas",
        seismicTitle: "USGS Sismos / NASA EONET",
        noActiveEvents: "Sin amenazas activas cerca de esta zona",
        activeEventsCount: "amenazas cercanas",
        hazardBonusLabel: "Impulso por Amenaza",
        regionalCoverage: "Filtrado por zona",
        feedStatus: {
          checking: "Actualizando",
          live: "Feeds en vivo",
          cached: "Caché reciente",
          partial: "Parcialmente en caché",
          fallback: "Usando respaldo",
          error: "No se pudo actualizar",
          simulation: "Simulacro activo",
          unavailable: "Sin datos",
        },
        checkedAt: "consulta",
        scenarioLabel: "Simulacro Protección Civil",
        scenarios: {
          none: "Monitoreo Real (USGS + Open-Meteo + EONET)",
          sonsonate_earthquake_m64:
            "Simulacro: Terremoto M6.4 zona seleccionada (USGS)",
          pacific_tropical_storm:
            "Simulacro: Tormenta Tropical 19-E zona seleccionada",
          izalco_volcanic_ash:
            "Simulacro: Alerta Volcánica Izalco / Ilamatepec (EONET)",
        },
        nominatimPlaceholder: "Buscar cantón/dirección (Nominatim)...",
        nominatimBtn: "Ir",
      }
    : {
        feedsBadge: "LIVE MULTI-AGENCY FEEDS",
        weatherTitle: "Open-Meteo Weather",
        rain: "Rain",
        gusts: "Gusts",
        seismicTitle: "USGS Quakes / NASA EONET",
        noActiveEvents: "No active hazards near this zone",
        activeEventsCount: "nearby active hazards",
        hazardBonusLabel: "Hazard Score Boost",
        regionalCoverage: "Filtered by zone",
        feedStatus: {
          checking: "Refreshing",
          live: "Live feeds",
          cached: "Recent cache",
          partial: "Partially cached",
          fallback: "Using fallback data",
          error: "Refresh failed",
          simulation: "Drill active",
          unavailable: "No data",
        },
        checkedAt: "checked",
        scenarioLabel: "Civil Protection Drill",
        scenarios: {
          none: "Live Telemetry (USGS + Open-Meteo + EONET)",
          sonsonate_earthquake_m64:
            "Drill: M6.4 Earthquake in Selected Zone (USGS)",
          pacific_tropical_storm:
            "Drill: Tropical Storm 19-E in Selected Zone",
          izalco_volcanic_ash:
            "Drill: Izalco / Ilamatepec Volcanic Ash (EONET)",
        },
        nominatimPlaceholder: "Geocode address/canton (Nominatim)...",
        nominatimBtn: "Go",
      },
);

const feedStatus = computed(() => {
  if (props.isRefreshing) {
    return { key: "refreshing", label: labels.value.feedStatus.checking };
  }
  if (props.refreshError) {
    return { key: "error", label: labels.value.feedStatus.error };
  }
  if (props.scenario !== "none") {
    return { key: "simulation", label: labels.value.feedStatus.simulation };
  }

  const sources = props.activeHazards?.active_sources ?? [];
  if (sources.length === 0) {
    return { key: "unavailable", label: labels.value.feedStatus.unavailable };
  }
  if (
    sources.some(
      (source) =>
        source.startsWith("fallback://") || source.startsWith("stale-cache://"),
    )
  ) {
    return { key: "fallback", label: labels.value.feedStatus.fallback };
  }
  if (sources.every((source) => source.startsWith("cache://"))) {
    return { key: "cached", label: labels.value.feedStatus.cached };
  }
  if (sources.some((source) => source.startsWith("cache://"))) {
    return { key: "partial", label: labels.value.feedStatus.partial };
  }
  return { key: "live", label: labels.value.feedStatus.live };
});

function getAlertTagType(
  level?: string,
): "success" | "warning" | "danger" | "info" {
  if (level === "red") return "danger";
  if (level === "orange" || level === "yellow") return "warning";
  return "success";
}

async function handleGeocodeSearch(): Promise<void> {
  const q = geocodeQuery.value.trim();
  if (!q) return;
  isSearchingGeo.value = true;
  try {
    const res = await apiClient.geocodeLocation(q, 4);
    geocodeResults.value = res;
    if (res.length > 0) {
      emit(
        "fly-to-coordinates",
        res[0].latitude,
        res[0].longitude,
        res[0].display_name,
      );
    }
  } finally {
    isSearchingGeo.value = false;
  }
}

function selectSuggestion(item: GeocodeResultRead): void {
  geocodeResults.value = [];
  geocodeQuery.value = item.display_name.split(",")[0] ?? item.display_name;
  emit(
    "fly-to-coordinates",
    item.latitude,
    item.longitude,
    item.display_name,
  );
}
</script>

<template>
  <section class="hazard-telemetry-strip" data-testid="hazard-telemetry-strip">
    <div class="telemetry-item telemetry-badge-box">
      <span
        class="alert-dot"
        :class="`alert-${props.activeHazards?.overall_alert_level ?? 'green'}`"
      ></span>
      <Icon0 name="siren" :size="14" />
      <span class="badge-title eoc-label">{{ labels.feedsBadge }}</span>
    </div>

    <div
      v-if="props.activeHazards?.weather"
      class="telemetry-item weather-pill"
    >
      <Icon0 name="activity" :size="14" class="text-sky" />
      <span class="telemetry-label">{{ labels.weatherTitle }}:</span>
      <strong class="eoc-numeric">{{ props.activeHazards.weather.temperature_c.toFixed(1) }}°C</strong>
      <span class="sep">•</span>
      <span>
        {{ labels.rain }}:
        <b class="eoc-numeric">{{ props.activeHazards.weather.precipitation_mm.toFixed(1) }} mm</b>
      </span>
      <span class="sep">•</span>
      <span>
        {{ labels.gusts }}:
        <b class="eoc-numeric">{{ props.activeHazards.weather.wind_gusts_kmh.toFixed(0) }} km/h</b>
      </span>
    </div>

    <div class="telemetry-item events-pill">
      <Icon0 name="triangle_alert" :size="14" class="text-amber" />
      <span class="telemetry-label">{{ labels.seismicTitle }}:</span>
      <template
        v-if="props.activeHazards && props.activeHazards.events.length > 0"
      >
        <ElTag
          size="small"
          :type="getAlertTagType(props.activeHazards.overall_alert_level)"
          effect="dark"
          class="eoc-numeric"
        >
          {{ props.activeHazards.events.length }}
          {{ labels.activeEventsCount }}
        </ElTag>
        <span
          v-if="props.scenario === 'none'"
          class="regional-feed-badge"
          :title="labels.regionalCoverage"
        >
          {{ labels.regionalCoverage }}
        </span>
        <span class="top-event-title">
          {{ props.activeHazards.events[0].title }}
        </span>
        <span
          class="event-time-badge"
          :title="`${formatExactTime(props.activeHazards.events[0].occurred_at, locale)} (Hora local El Salvador)`"
        >
          <Icon0 name="clock" :size="10" />
          {{ formatRelativeTime(props.activeHazards.events[0].occurred_at, locale) }}
        </span>
        <span
          v-if="props.activeHazards.zone_hazard_bonus > 0"
          class="hazard-boost-pill eoc-numeric"
        >
          +{{ props.activeHazards.zone_hazard_bonus.toFixed(1) }} pts
        </span>
      </template>
      <span v-else class="calm-text">{{ labels.noActiveEvents }}</span>
    </div>

    <div class="telemetry-controls">
      <div v-if="props.scenario === 'none'" class="live-monitoring-badge">
        <span class="live-status-dot"></span>
        <span class="live-status-text">
          {{ locale === "es" ? "Monitoreo Oficial en Vivo" : "Official Live Feeds" }}
        </span>
      </div>

      <div v-else class="active-drill-badge">
        <span class="active-drill-dot"></span>
        <span class="active-drill-text">
          {{ locale === "es" ? "Simulacro Activo" : "Active Drill" }}
        </span>
        <button
          type="button"
          class="exit-drill-btn"
          data-testid="exit-drill-btn"
          :title="locale === 'es' ? 'Volver a monitoreo real' : 'Return to live monitoring'"
          @click="emit('change-scenario', 'none')"
        >
          <Icon0 name="x" :size="11" />
          <span>{{ locale === "es" ? "Finalizar" : "End" }}</span>
        </button>
      </div>

      <ElDropdown
        trigger="click"
        @command="(cmd: string) => emit('change-scenario', cmd as HazardScenarioPreset)"
      >
        <button
          type="button"
          class="drill-toggle-btn"
          data-testid="drill-toggle-btn"
        >
          <Icon0 name="activity" :size="12" />
          <span>{{ locale === 'es' ? 'Simulacro' : 'Drill' }}</span>
          <Icon0 name="chevron_down" :size="10" />
        </button>
        <template #dropdown>
          <ElDropdownMenu class="drill-dropdown-menu">
            <ElDropdownItem
              v-if="props.scenario !== 'none'"
              command="none"
            >
              <span class="drill-item-title text-emerald">
                <Icon0 name="shield_alert" :size="12" />
                {{ labels.scenarios.none }}
              </span>
            </ElDropdownItem>
            <ElDropdownItem command="sonsonate_earthquake_m64">
              <span class="drill-item-title">
                <Icon0 name="siren" :size="12" class="text-red" />
                {{ labels.scenarios.sonsonate_earthquake_m64 }}
              </span>
            </ElDropdownItem>
            <ElDropdownItem command="pacific_tropical_storm">
              <span class="drill-item-title">
                <Icon0 name="triangle_alert" :size="12" class="text-blue" />
                {{ labels.scenarios.pacific_tropical_storm }}
              </span>
            </ElDropdownItem>
            <ElDropdownItem command="izalco_volcanic_ash">
              <span class="drill-item-title">
                <Icon0 name="flame" :size="12" class="text-amber" />
                {{ labels.scenarios.izalco_volcanic_ash }}
              </span>
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>

      <div
        class="feed-freshness"
        :class="`feed-${feedStatus.key}`"
        data-testid="hazard-feed-status"
        :title="props.refreshError || undefined"
        aria-live="polite"
      >
        <Icon0 name="clock" :size="11" />
        <span>{{ feedStatus.label }}</span>
        <span v-if="props.lastCheckedAt" class="feed-checked-at">
          · {{ labels.checkedAt }}
          {{ formatRelativeTime(props.lastCheckedAt, locale) }}
        </span>
      </div>

      <div class="nominatim-box">
        <div class="nominatim-input-row">
          <Icon0 name="search" :size="13" class="nominatim-icon" />
          <input
            v-model="geocodeQuery"
            type="text"
            class="nominatim-input"
            :placeholder="labels.nominatimPlaceholder"
            data-testid="nominatim-search-input"
            @keyup.enter="handleGeocodeSearch"
          />
          <ElButton
            size="small"
            type="primary"
            :loading="isSearchingGeo"
            data-testid="nominatim-search-btn"
            @click="handleGeocodeSearch"
          >
            {{ labels.nominatimBtn }}
          </ElButton>
        </div>

        <ul v-if="geocodeResults.length > 0" class="nominatim-dropdown">
          <li
            v-for="item in geocodeResults"
            :key="`${item.latitude}-${item.longitude}`"
            class="nominatim-option"
            @click="selectSuggestion(item)"
          >
            <Icon0 name="map_pin" :size="12" />
            <span>{{ item.display_name }}</span>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hazard-telemetry-strip {
  background: var(--eoc-bg-statusbar);
  border-bottom: var(--eoc-border-width) solid var(--eoc-border);
  color: var(--eoc-text-secondary);
  padding: 3px var(--eoc-pad-panel);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--eoc-gap-x);
  font-size: var(--eoc-fs-micro);
  z-index: 19;
  min-height: var(--eoc-tabstrip-h);
  transition: background-color var(--eoc-transition),
    border-color var(--eoc-transition);
}

.telemetry-item {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
}

.telemetry-badge-box {
  background: transparent;
  border: none;
  padding: 0 4px 0 0;
}

.weather-pill,
.events-pill {
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
  padding: 2px var(--eoc-gap-x);
  border-radius: var(--eoc-radius-control);
}

.alert-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--eoc-radius-pill);
}

.alert-green {
  background: var(--eoc-success);
}

/* DGPC yellow and orange alerts both land on the warning role */
.alert-yellow,
.alert-orange {
  background: var(--eoc-warning);
}

.alert-red {
  background: var(--eoc-critical);
}

.telemetry-label {
  color: var(--eoc-text-label);
  font-weight: var(--eoc-fw-regular);
}

.sep {
  color: var(--eoc-text-muted);
}

.top-event-title {
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-text-primary);
  max-width: 240px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hazard-boost-pill {
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  color: var(--eoc-critical);
  background: var(--eoc-critical-bg);
  border: var(--eoc-border-width) solid var(--eoc-critical-border);
  padding: 0 var(--eoc-gap-x);
  border-radius: var(--eoc-radius-pill);
}

.regional-feed-badge {
  color: var(--eoc-text-secondary);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
  border-radius: var(--eoc-radius-pill);
  padding: 0 var(--eoc-gap-x);
  font-size: var(--eoc-fs-micro);
  white-space: nowrap;
}

.event-time-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-regular);
  color: var(--eoc-text-secondary);
  background: var(--eoc-bg-sunken);
  border: var(--eoc-border-width) solid var(--eoc-border);
  padding: 1px var(--eoc-gap-x);
  border-radius: var(--eoc-radius-control);
  cursor: help;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.calm-text {
  color: var(--eoc-text-muted);
}

.telemetry-controls {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  flex-wrap: wrap;
}

.feed-freshness {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--eoc-text-muted);
  font-size: var(--eoc-fs-micro);
  white-space: nowrap;
}

.feed-checked-at {
  opacity: 0.8;
}

.feed-refreshing,
.feed-live {
  color: var(--eoc-success);
}

.feed-cached,
.feed-partial {
  color: var(--eoc-warning);
}

.feed-fallback,
.feed-error {
  color: var(--eoc-critical);
}

.feed-simulation {
  color: var(--eoc-accent);
}

.live-monitoring-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  background: var(--eoc-success-bg);
  border: var(--eoc-border-width) solid var(--eoc-success-border);
  color: var(--eoc-success);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  padding: 2px var(--eoc-gap-x);
  border-radius: var(--eoc-radius-control);
  white-space: nowrap;
}

.live-status-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--eoc-radius-pill);
  background: var(--eoc-success);
  animation: eoc-beacon-pulse 2s infinite;
}

.nominatim-box {
  position: relative;
}

.nominatim-input-row {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--eoc-bg-sunken);
  border: var(--eoc-border-width) solid var(--eoc-border);
  border-radius: var(--eoc-radius-control);
  padding: 1px 2px 1px var(--eoc-gap-x);
}

.nominatim-icon {
  color: var(--eoc-text-muted);
}

.nominatim-input {
  background: transparent;
  border: none;
  outline: none;
  color: var(--eoc-text-primary);
  font-family: var(--eoc-font-sans);
  font-size: var(--eoc-fs-body);
  width: 155px;
}

.nominatim-input::placeholder {
  color: var(--eoc-text-muted);
}

/* Floating suggestion list: genuinely elevated, so it keeps a popup shadow */
.nominatim-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  width: 280px;
  background: var(--eoc-bg-overlay);
  border: var(--eoc-border-width) solid var(--eoc-border-strong);
  border-radius: var(--eoc-radius-menu);
  list-style: none;
  margin: 0;
  padding: 4px;
  z-index: 999;
  box-shadow: var(--eoc-shadow-popup);
}

.nominatim-option {
  display: flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  padding: 4px var(--eoc-gap-x);
  border-radius: var(--eoc-radius-control);
  color: var(--eoc-text-primary);
  font-size: var(--eoc-fs-body);
  cursor: pointer;
  transition: background-color var(--eoc-transition);
}

.nominatim-option:hover {
  background: var(--eoc-bg-hover);
}

.drill-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: var(--eoc-control-h);
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
  color: var(--eoc-text-secondary);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  padding: var(--eoc-pad-button);
  border-radius: var(--eoc-radius-button);
  cursor: pointer;
  transition: background-color var(--eoc-transition),
    border-color var(--eoc-transition), color var(--eoc-transition);
}

.drill-toggle-btn:hover {
  color: var(--eoc-text-primary);
  border-color: var(--eoc-border-strong);
  background: var(--eoc-bg-hover);
}

.active-drill-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  background: var(--eoc-critical-bg);
  border: var(--eoc-border-width) solid var(--eoc-critical-border);
  color: var(--eoc-critical);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  padding: 2px var(--eoc-gap-x);
  border-radius: var(--eoc-radius-control);
  white-space: nowrap;
}

.active-drill-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--eoc-radius-pill);
  background: var(--eoc-critical);
  animation: eoc-beacon-pulse 1.8s infinite;
}

.exit-drill-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: var(--eoc-bg-card);
  border: var(--eoc-border-width) solid var(--eoc-border);
  color: var(--eoc-text-primary);
  font-size: var(--eoc-fs-micro);
  font-weight: var(--eoc-fw-semibold);
  padding: 1px var(--eoc-gap-x);
  border-radius: var(--eoc-radius-control);
  cursor: pointer;
  margin-left: 2px;
  transition: background-color var(--eoc-transition),
    color var(--eoc-transition);
}

.exit-drill-btn:hover {
  background: var(--eoc-critical-border);
  color: var(--eoc-critical);
}

.drill-item-title {
  display: inline-flex;
  align-items: center;
  gap: var(--eoc-gap-x);
  font-size: var(--eoc-fs-body);
}

.text-sky {
  color: var(--eoc-accent);
}
.text-amber {
  color: var(--eoc-warning);
}
.text-red {
  color: var(--eoc-critical);
}
.text-blue {
  color: var(--eoc-info);
}
.text-emerald {
  color: var(--eoc-success);
}
</style>
