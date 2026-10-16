"""Domain entities, severity classifiers, and PostGIS hazard impact calculation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import math


class HazardType(StrEnum):
    """Supported natural hazard categories."""

    EARTHQUAKE = "earthquake"
    SEVERE_STORM = "severe_storm"
    VOLCANO = "volcano"
    FLOOD = "flood"
    WILDFIRE = "wildfire"


class HazardAlertLevel(StrEnum):
    """Standardized alert severity levels aligned with GDACS / USGS."""

    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


class HazardScenarioPreset(StrEnum):
    """Simulation scenarios for civil protection training and live demos."""

    NONE = "none"
    SONSONATE_EARTHQUAKE_M64 = "sonsonate_earthquake_m64"
    PACIFIC_TROPICAL_STORM = "pacific_tropical_storm"
    IZALCO_VOLCANIC_ASH = "izalco_volcanic_ash"


@dataclass(slots=True)
class HazardEvent:
    """Single active disaster or hazard event from USGS, NASA EONET, or simulation."""

    id: str
    hazard_type: HazardType
    title: str
    source: str
    alert_level: HazardAlertLevel
    latitude: float
    longitude: float
    radius_km: float
    magnitude: float | None = None
    depth_km: float | None = None
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    url: str | None = None
    is_simulated: bool = False


@dataclass(slots=True)
class WeatherCondition:
    """Real-time hydrometeorological snapshot from Open-Meteo API."""

    temperature_c: float
    precipitation_mm: float
    rain_mm: float
    wind_speed_kmh: float
    wind_gusts_kmh: float
    weather_code: int
    weather_label: str
    alert_level: HazardAlertLevel
    source: str = "https://api.open-meteo.com/v1/forecast"
    is_simulated: bool = False


@dataclass(slots=True)
class GeocodeSuggestion:
    """Nominatim geocoding result for El Salvador locations."""

    display_name: str
    latitude: float
    longitude: float
    place_type: str
    importance: float = 0.5


WMO_WEATHER_LABELS: dict[int, tuple[str, HazardAlertLevel]] = {
    0: ("Clear sky / Despejado", HazardAlertLevel.GREEN),
    1: ("Mainly clear / Mayormente despejado", HazardAlertLevel.GREEN),
    2: ("Partly cloudy / Parcialmente nublado", HazardAlertLevel.GREEN),
    3: ("Overcast / Nublado", HazardAlertLevel.GREEN),
    45: ("Fog / Niebla", HazardAlertLevel.GREEN),
    48: ("Dense fog / Niebla densa", HazardAlertLevel.YELLOW),
    51: ("Light drizzle / Llovizna ligera", HazardAlertLevel.GREEN),
    53: ("Moderate drizzle / Llovizna moderada", HazardAlertLevel.GREEN),
    55: ("Dense drizzle / Llovizna intensa", HazardAlertLevel.YELLOW),
    61: ("Slight rain / Lluvia débil", HazardAlertLevel.GREEN),
    63: ("Moderate rain / Lluvia moderada", HazardAlertLevel.YELLOW),
    65: ("Heavy rain / Lluvia fuerte", HazardAlertLevel.ORANGE),
    80: ("Rain showers / Chubascos", HazardAlertLevel.YELLOW),
    81: ("Moderate rain showers / Chubascos fuertes", HazardAlertLevel.ORANGE),
    82: ("Violent rain showers / Tormenta torrencial", HazardAlertLevel.RED),
    95: ("Thunderstorm / Tormenta eléctrica", HazardAlertLevel.ORANGE),
    96: ("Thunderstorm with hail / Tormenta severa", HazardAlertLevel.RED),
    99: ("Extreme thunderstorm / Tormenta extrema", HazardAlertLevel.RED),
}


def classify_weather_alert(
    weather_code: int,
    precipitation_mm: float,
    wind_gusts_kmh: float,
) -> tuple[str, HazardAlertLevel]:
    """Classify Open-Meteo WMO code, rain, and gusts into a civil protection alert."""
    label, base_level = WMO_WEATHER_LABELS.get(
        weather_code, ("Variable weather / Clima variable", HazardAlertLevel.GREEN)
    )
    level_rank = {
        HazardAlertLevel.GREEN: 0,
        HazardAlertLevel.YELLOW: 1,
        HazardAlertLevel.ORANGE: 2,
        HazardAlertLevel.RED: 3,
    }
    rank = level_rank[base_level]

    if precipitation_mm >= 15.0 or wind_gusts_kmh >= 65.0:
        rank = max(rank, 3)
    elif precipitation_mm >= 6.0 or wind_gusts_kmh >= 45.0:
        rank = max(rank, 2)
    elif precipitation_mm >= 2.0 or wind_gusts_kmh >= 30.0:
        rank = max(rank, 1)

    inv_rank = {v: k for k, v in level_rank.items()}
    return label, inv_rank[rank]


def classify_earthquake_alert_and_radius(
    magnitude: float,
    usgs_alert: str | None = None,
) -> tuple[HazardAlertLevel, float]:
    """Map seismic magnitude and USGS PAGER alert to alert level and impact radius (km)."""
    normalized_pager = (usgs_alert or "").strip().lower()
    if normalized_pager == "red" or magnitude >= 6.2:
        return HazardAlertLevel.RED, max(25.0, magnitude * 4.5)
    if normalized_pager == "orange" or magnitude >= 5.2:
        return HazardAlertLevel.ORANGE, max(18.0, magnitude * 3.8)
    if normalized_pager == "yellow" or magnitude >= 4.3:
        return HazardAlertLevel.YELLOW, max(12.0, magnitude * 3.0)
    return HazardAlertLevel.GREEN, max(8.0, magnitude * 2.2)


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Compute great-circle distance in kilometers between two WGS84 coordinates."""
    r_earth = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * r_earth * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def is_hazard_relevant_to_point(
    latitude: float,
    longitude: float,
    event: HazardEvent,
) -> bool:
    """Return whether an event's modeled influence area reaches a target point."""
    impact_radius_km = max(event.radius_km, 1.0) * 2.5
    distance_km = haversine_distance_km(
        latitude, longitude, event.latitude, event.longitude
    )
    return distance_km <= impact_radius_km


def compute_hazard_bonus_for_point(
    latitude: float,
    longitude: float,
    events: list[HazardEvent],
    weather: WeatherCondition | None = None,
) -> float:
    """Calculate additive emergency hazard bonus for a vulnerable place based on proximity to active hazards."""
    bonus = 0.0
    alert_weights = {
        HazardAlertLevel.GREEN: 8.0,
        HazardAlertLevel.YELLOW: 18.0,
        HazardAlertLevel.ORANGE: 35.0,
        HazardAlertLevel.RED: 55.0,
    }

    for ev in events:
        dist_km = haversine_distance_km(
            latitude, longitude, ev.latitude, ev.longitude
        )
        impact_radius_km = max(ev.radius_km, 1.0) * 2.5
        if dist_km <= impact_radius_km:
            proximity_factor = max(
                0.0, 1.0 - (dist_km / impact_radius_km)
            )
            base_weight = alert_weights.get(ev.alert_level, 10.0)
            mag_boost = (
                max(0.0, (ev.magnitude - 4.0) * 6.0)
                if ev.magnitude is not None
                else 5.0
            )
            bonus += (base_weight + mag_boost) * proximity_factor

    if weather is not None:
        if weather.alert_level == HazardAlertLevel.RED:
            bonus += 22.0
        elif weather.alert_level == HazardAlertLevel.ORANGE:
            bonus += 12.0
        elif weather.alert_level == HazardAlertLevel.YELLOW:
            bonus += 5.0

    return round(bonus, 2)


def build_simulation_scenario(
    preset: HazardScenarioPreset,
    center_lat: float = 13.7222,
    center_lon: float = -89.7236,
) -> tuple[list[HazardEvent], WeatherCondition | None]:
    """Build deterministic civil protection drill scenarios around the active zone."""
    now = datetime.now(timezone.utc)
    if preset == HazardScenarioPreset.SONSONATE_EARTHQUAKE_M64:
        return (
            [
                HazardEvent(
                    id="sim-usgs-sv-m64",
                    hazard_type=HazardType.EARTHQUAKE,
                    title="Sismo M 6.4 - zona seleccionada (Simulacro)",
                    source="USGS Earthquake API (Simulation Drill)",
                    alert_level=HazardAlertLevel.RED,
                    latitude=center_lat - 0.008,
                    longitude=center_lon - 0.011,
                    radius_km=18.0,
                    magnitude=6.4,
                    depth_km=32.5,
                    occurred_at=now,
                    url="https://earthquake.usgs.gov/earthquakes/map/",
                    is_simulated=True,
                ),
                HazardEvent(
                    id="sim-usgs-sv-aftershock-m48",
                    hazard_type=HazardType.EARTHQUAKE,
                    title="Réplica M 4.8 - zona seleccionada (Simulacro)",
                    source="USGS Earthquake API (Simulation Drill)",
                    alert_level=HazardAlertLevel.YELLOW,
                    latitude=center_lat + 0.014,
                    longitude=center_lon + 0.009,
                    radius_km=9.0,
                    magnitude=4.8,
                    depth_km=19.0,
                    occurred_at=now,
                    url="https://earthquake.usgs.gov/earthquakes/map/",
                    is_simulated=True,
                ),
            ],
            WeatherCondition(
                temperature_c=27.5,
                precipitation_mm=4.2,
                rain_mm=4.2,
                wind_speed_kmh=24.0,
                wind_gusts_kmh=38.0,
                weather_code=63,
                weather_label="Moderate rain / Lluvia moderada post-sismo",
                alert_level=HazardAlertLevel.YELLOW,
                is_simulated=True,
            ),
        )

    if preset == HazardScenarioPreset.PACIFIC_TROPICAL_STORM:
        return (
            [
                HazardEvent(
                    id="sim-eonet-storm-sv",
                    hazard_type=HazardType.SEVERE_STORM,
                    title="Tormenta Tropical 19-E - lluvias intensas en zona seleccionada (Simulacro)",
                    source="NASA EONET + Open-Meteo (Simulation Drill)",
                    alert_level=HazardAlertLevel.RED,
                    latitude=center_lat + 0.003,
                    longitude=center_lon - 0.004,
                    radius_km=22.0,
                    magnitude=None,
                    depth_km=None,
                    occurred_at=now,
                    url="https://eonet.gsfc.nasa.gov/api/v3/events",
                    is_simulated=True,
                ),
            ],
            WeatherCondition(
                temperature_c=23.4,
                precipitation_mm=28.5,
                rain_mm=28.5,
                wind_speed_kmh=52.0,
                wind_gusts_kmh=74.0,
                weather_code=82,
                weather_label="Violent rain showers / Tormenta torrencial",
                alert_level=HazardAlertLevel.RED,
                is_simulated=True,
            ),
        )

    if preset == HazardScenarioPreset.IZALCO_VOLCANIC_ASH:
        return (
            [
                HazardEvent(
                    id="sim-eonet-volcano-izalco",
                    hazard_type=HazardType.VOLCANO,
                    title="Alerta Volcánica - Complejo Izalco / Ilamatepec (Caída de Ceniza)",
                    source="NASA EONET / MARN (Simulation Drill)",
                    alert_level=HazardAlertLevel.ORANGE,
                    latitude=13.8130,
                    longitude=-89.6330,
                    radius_km=16.0,
                    magnitude=None,
                    depth_km=None,
                    occurred_at=now,
                    url="https://eonet.gsfc.nasa.gov/api/v3/events",
                    is_simulated=True,
                ),
            ],
            WeatherCondition(
                temperature_c=26.0,
                precipitation_mm=1.2,
                rain_mm=1.2,
                wind_speed_kmh=34.0,
                wind_gusts_kmh=49.0,
                weather_code=48,
                weather_label="Volcanic plume & wind dispersion / Dispersión eólica",
                alert_level=HazardAlertLevel.ORANGE,
                is_simulated=True,
            ),
        )

    return [], None
