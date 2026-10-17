"""Asynchronous Overpass API HTTP adapter with mirror failover and offline fallback."""

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import settings
from app.modules.ingestion.domain.classifier import build_overpass_query

DEFAULT_OVERPASS_MIRRORS: tuple[str, ...] = (
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

USER_AGENT_HEADER = "FirstSpot/0.1 (Humanitarian Response El Salvador)"

SONSONATE_FALLBACK_ELEMENTS: list[dict[str, Any]] = [
    {
        "type": "way",
        "id": 248190101,
        "center": {"lat": 13.7203, "lon": -89.7248},
        "tags": {
            "amenity": "hospital",
            "name": "Hospital Nacional General Dr. Jorge Mazzini Villacorta",
            "name:en": "Sonsonate Regional National Hospital",
            "emergency": "yes",
            "operator": "Ministerio de Salud (MINSAL)",
        },
    },
    {
        "type": "node",
        "id": 248190102,
        "lat": 13.7212,
        "lon": -89.7254,
        "tags": {
            "amenity": "clinic",
            "name": "Unidad Comunitaria de Salud Familiar (UCSF) Sonsonate",
            "name:en": "Sonsonate Community Health Clinic",
            "healthcare": "clinic",
        },
    },
    {
        "type": "node",
        "id": 248190103,
        "lat": 13.7196,
        "lon": -89.7239,
        "tags": {
            "amenity": "social_facility",
            "social_facility": "nursing_home",
            "social_facility:for": "senior",
            "name": "Hogar de Ancianos San Vicente de Paúl",
            "name:en": "San Vicente Senior Care Shelter",
        },
    },
    {
        "type": "node",
        "id": 248190104,
        "lat": 13.7228,
        "lon": -89.7261,
        "tags": {
            "amenity": "kindergarten",
            "name": "Escuela de Educación Parvularia de Sonsonate",
            "name:en": "Sonsonate Early Childhood Kindergarten",
        },
    },
    {
        "type": "way",
        "id": 248190105,
        "center": {"lat": 13.7219, "lon": -89.7231},
        "tags": {
            "amenity": "school",
            "name": "Complejo Educativo Thomas Jefferson",
            "name:en": "Thomas Jefferson Public School",
        },
    },
    {
        "type": "node",
        "id": 248190106,
        "lat": 13.7184,
        "lon": -89.7270,
        "tags": {
            "amenity": "community_centre",
            "name": "Casa Comunal Barrio El Ángel",
            "name:en": "El Angel Community Center",
        },
    },
    {
        "type": "way",
        "id": 248190107,
        "center": {"lat": 13.7295, "lon": -89.7192},
        "tags": {
            "amenity": "university",
            "name": "Universidad de Sonsonate (USO)",
            "name:en": "Sonsonate Regional University",
        },
    },
    {
        "type": "node",
        "id": 248190108,
        "lat": 13.7207,
        "lon": -89.7243,
        "tags": {
            "amenity": "pharmacy",
            "name": "Farmacia Central de Sonsonate",
            "name:en": "Sonsonate Central Pharmacy",
        },
    },
    {
        "type": "way",
        "id": 248190109,
        "center": {"lat": 13.7175, "lon": -89.7220},
        "tags": {
            "amenity": "marketplace",
            "name": "Mega Plaza y Mercado Central de Sonsonate",
            "name:en": "Sonsonate Central Marketplace",
        },
    },
    {
        "type": "way",
        "id": 248190110,
        "center": {"lat": 13.7209, "lon": -89.7235},
        "tags": {
            "amenity": "place_of_worship",
            "religion": "christian",
            "name": "Catedral Santísima Trinidad de Sonsonate",
            "name:en": "Holy Trinity Cathedral of Sonsonate",
        },
    },
    {
        "type": "relation",
        "id": 248190111,
        "center": {"lat": 13.7152, "lon": -89.7188},
        "tags": {
            "shop": "mall",
            "name": "Centro Comercial Metrocentro Sonsonate",
            "name:en": "Metrocentro Sonsonate Mall",
        },
    },
    {
        "type": "node",
        "id": 248190112,
        "lat": 13.7240,
        "lon": -89.7285,
        "tags": {
            "amenity": "social_facility",
            "social_facility": "shelter",
            "name": "Albergue Municipal de Protección Civil Sonsonate",
            "name:en": "Sonsonate Municipal Civil Protection Shelter",
        },
    },
]


@dataclass(slots=True)
class OverpassSyncPayload:
    """Result returned by a geospatial provider fetch operation."""

    elements: list[dict[str, Any]]
    source_endpoint: str
    used_fallback: bool = False


class GeospatialProviderPort(Protocol):
    """Outbound port for fetching raw OpenStreetMap elements around a coordinate."""

    async def fetch_elements(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> OverpassSyncPayload:
        """Fetch raw OSM elements within radius_meters around (latitude, longitude)."""


def build_fallback_elements_for_coordinates(
    latitude: float,
    longitude: float,
) -> list[dict[str, Any]]:
    """Build deterministic fallback elements anchored around target coordinates."""
    lat_offset = latitude - 13.7222
    lon_offset = longitude - (-89.7236)
    is_near_sonsonate = abs(lat_offset) < 0.08 and abs(lon_offset) < 0.08

    if is_near_sonsonate:
        return [dict(item) for item in SONSONATE_FALLBACK_ELEMENTS]

    adjusted: list[dict[str, Any]] = []
    for idx, base in enumerate(SONSONATE_FALLBACK_ELEMENTS, start=1):
        cloned = dict(base)
        cloned["id"] = int(base["id"]) + idx * 1000 + int(abs(latitude * 100))
        if "lat" in cloned and "lon" in cloned:
            cloned["lat"] = round(float(cloned["lat"]) + lat_offset, 6)
            cloned["lon"] = round(float(cloned["lon"]) + lon_offset, 6)
        elif "center" in cloned and isinstance(cloned["center"], dict):
            cloned["center"] = {
                "lat": round(float(cloned["center"]["lat"]) + lat_offset, 6),
                "lon": round(float(cloned["center"]["lon"]) + lon_offset, 6),
            }
        adjusted.append(cloned)
    return adjusted


class OverpassHttpClient:
    """HTTP adapter for querying Overpass API with mirror failover and offline fallback."""

    def __init__(
        self,
        mirrors: tuple[str, ...] | None = None,
        timeout_seconds: float = 25.0,
        allow_fallback: bool = True,
    ) -> None:
        primary = settings.overpass_url.strip()
        ordered_mirrors = [primary] if primary else []
        for candidate in mirrors or DEFAULT_OVERPASS_MIRRORS:
            if candidate not in ordered_mirrors:
                ordered_mirrors.append(candidate)
        self.mirrors = tuple(ordered_mirrors)
        self.timeout_seconds = timeout_seconds
        self.allow_fallback = allow_fallback

    async def fetch_elements(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> OverpassSyncPayload:
        """Query Overpass QL across configured mirrors or return fallback dataset on failure."""
        query = build_overpass_query(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            timeout_seconds=60,
        )
        headers = {
            "User-Agent": USER_AGENT_HEADER,
            "Accept": "application/json",
        }
        last_error: Exception | None = None

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=8.0),
            headers=headers,
            follow_redirects=True,
        ) as client:
            for endpoint in self.mirrors:
                try:
                    response = await client.post(
                        endpoint,
                        data={"data": query},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    raw_elements = payload.get("elements")
                    if isinstance(raw_elements, list):
                        return OverpassSyncPayload(
                            elements=raw_elements,
                            source_endpoint=endpoint,
                            used_fallback=False,
                        )
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    continue

        if self.allow_fallback:
            return OverpassSyncPayload(
                elements=build_fallback_elements_for_coordinates(latitude, longitude),
                source_endpoint="fallback://sonsonate-seed",
                used_fallback=True,
            )

        raise RuntimeError(
            f"All Overpass mirrors failed to respond: {last_error}"
        ) from last_error
