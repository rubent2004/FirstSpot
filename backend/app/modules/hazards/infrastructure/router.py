"""FastAPI REST adapters for live disaster feeds (USGS, Open-Meteo, NASA EONET) and Nominatim geocoding."""

from datetime import datetime
import math
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.modules.hazards.domain.entities import (
    HazardAlertLevel,
    HazardScenarioPreset,
    HazardType,
    compute_hazard_bonus_for_point,
    is_hazard_relevant_to_point,
)
from app.modules.hazards.infrastructure.feeds_client import (
    HazardFeedsProviderPort,
    LiveHazardFeedsClient,
)
from app.modules.ingestion.domain.zones import PREDEFINED_ZONES, get_predefined_zone

router = APIRouter(tags=["hazards"])


class HazardEventRead(BaseModel):
    """Schema representing an active earthquake, storm, or volcanic event."""

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
    occurred_at: datetime
    url: str | None = None
    is_simulated: bool = False


class WeatherConditionRead(BaseModel):
    """Schema representing current Open-Meteo weather and rain telemetry."""

    temperature_c: float
    precipitation_mm: float
    rain_mm: float
    wind_speed_kmh: float
    wind_gusts_kmh: float
    weather_code: int
    weather_label: str
    alert_level: HazardAlertLevel
    source: str
    is_simulated: bool = False


class ActiveHazardsResponse(BaseModel):
    """Aggregated response with active natural hazards, weather telemetry, and zone threat score."""

    zone_name: str
    latitude: float
    longitude: float
    scenario: HazardScenarioPreset
    overall_alert_level: HazardAlertLevel
    zone_hazard_bonus: float = Field(
        description="Estimated priority score boost at the zone center from active hazards."
    )
    active_sources: list[str]
    weather: WeatherConditionRead
    events: list[HazardEventRead]


class GeocodeResultRead(BaseModel):
    """Nominatim geocoding suggestion for El Salvador."""

    display_name: str
    latitude: float
    longitude: float
    place_type: str
    importance: float


def get_hazard_feeds_provider() -> HazardFeedsProviderPort:
    """Provide default live hazard feeds HTTP adapter."""
    return LiveHazardFeedsClient()


@router.get(
    "/hazards/active",
    response_model=ActiveHazardsResponse,
    summary="Get live earthquakes (USGS), natural events (NASA EONET), and weather (Open-Meteo)",
    include_in_schema=False,
)
async def get_active_hazards(
    provider: Annotated[HazardFeedsProviderPort, Depends(get_hazard_feeds_provider)],
    zone_key: Annotated[
        str | None, Query(description="Predefined El Salvador zone key")
    ] = "sonsonate",
    latitude: Annotated[
        float | None, Query(ge=-90.0, le=90.0, description="Target latitude")
    ] = None,
    longitude: Annotated[
        float | None, Query(ge=-180.0, le=180.0, description="Target longitude")
    ] = None,
    scenario: Annotated[
        HazardScenarioPreset,
        Query(description="Optional civil protection simulation drill preset"),
    ] = HazardScenarioPreset.NONE,
) -> ActiveHazardsResponse:
    """Fetch live disaster telemetry from USGS, Open-Meteo, and NASA EONET or activate a simulation drill."""
    zone = get_predefined_zone(zone_key or "sonsonate") or PREDEFINED_ZONES["sonsonate"]
    target_lat = latitude if latitude is not None else zone.latitude
    target_lon = longitude if longitude is not None else zone.longitude
    is_predefined_zone_center = (
        (latitude is None and longitude is None)
        or (
            latitude is not None
            and longitude is not None
            and math.isclose(latitude, zone.latitude, abs_tol=0.0001)
            and math.isclose(longitude, zone.longitude, abs_tol=0.0001)
        )
    )
    zone_label = (
        zone.name
        if is_predefined_zone_center
        else f"Radar ({target_lat:.3f}, {target_lon:.3f})"
    )

    events, weather, sources = await provider.fetch_active_hazards(
        latitude=target_lat,
        longitude=target_lon,
        scenario=scenario,
    )
    if scenario == HazardScenarioPreset.NONE:
        # The providers/cache are regional; only return events whose modeled
        # impact area reaches this zone so map markers and counts stay local.
        events = [
            event
            for event in events
            if is_hazard_relevant_to_point(target_lat, target_lon, event)
        ]

    alert_rank = {
        HazardAlertLevel.GREEN: 0,
        HazardAlertLevel.YELLOW: 1,
        HazardAlertLevel.ORANGE: 2,
        HazardAlertLevel.RED: 3,
    }
    inv_rank = {v: k for k, v in alert_rank.items()}
    max_rank = alert_rank[weather.alert_level]
    for ev in events:
        max_rank = max(max_rank, alert_rank[ev.alert_level])

    zone_bonus = compute_hazard_bonus_for_point(
        target_lat, target_lon, events, weather
    )

    return ActiveHazardsResponse(
        zone_name=zone_label,
        latitude=target_lat,
        longitude=target_lon,
        scenario=scenario,
        overall_alert_level=inv_rank[max_rank],
        zone_hazard_bonus=zone_bonus,
        active_sources=sources,
        weather=WeatherConditionRead(
            temperature_c=weather.temperature_c,
            precipitation_mm=weather.precipitation_mm,
            rain_mm=weather.rain_mm,
            wind_speed_kmh=weather.wind_speed_kmh,
            wind_gusts_kmh=weather.wind_gusts_kmh,
            weather_code=weather.weather_code,
            weather_label=weather.weather_label,
            alert_level=weather.alert_level,
            source=weather.source,
            is_simulated=weather.is_simulated,
        ),
        events=[
            HazardEventRead(
                id=e.id,
                hazard_type=e.hazard_type,
                title=e.title,
                source=e.source,
                alert_level=e.alert_level,
                latitude=e.latitude,
                longitude=e.longitude,
                radius_km=e.radius_km,
                magnitude=e.magnitude,
                depth_km=e.depth_km,
                occurred_at=e.occurred_at,
                url=e.url,
                is_simulated=e.is_simulated,
            )
            for e in events
        ],
    )


@router.get(
    "/hazards/geocode",
    response_model=list[GeocodeResultRead],
    summary="Geocode address or municipality in El Salvador via Nominatim",
    include_in_schema=False,
)
async def geocode_location(
    provider: Annotated[HazardFeedsProviderPort, Depends(get_hazard_feeds_provider)],
    q: Annotated[str, Query(min_length=1, description="Address or place name in El Salvador")],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> list[GeocodeResultRead]:
    """Resolve an address, canton, or municipality in El Salvador into WGS84 coordinates."""
    results = await provider.search_location(query=q, limit=limit)
    return [
        GeocodeResultRead(
            display_name=r.display_name,
            latitude=r.latitude,
            longitude=r.longitude,
            place_type=r.place_type,
            importance=r.importance,
        )
        for r in results
    ]
