"""Predefined geographic zones in El Salvador for humanitarian prioritization."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PredefinedZone:
    """Immutable definition of a target geographic zone for OSM ingestion."""

    key: str
    name: str
    department: str
    latitude: float
    longitude: float
    default_radius_meters: int


PREDEFINED_ZONES: dict[str, PredefinedZone] = {
    "sonsonate": PredefinedZone(
        key="sonsonate",
        name="Sonsonate",
        department="Sonsonate",
        latitude=13.7222,
        longitude=-89.7236,
        default_radius_meters=10000,
    ),
    "san_salvador": PredefinedZone(
        key="san_salvador",
        name="San Salvador",
        department="San Salvador",
        latitude=13.6929,
        longitude=-89.2182,
        default_radius_meters=8000,
    ),
    "santa_ana": PredefinedZone(
        key="santa_ana",
        name="Santa Ana",
        department="Santa Ana",
        latitude=13.9942,
        longitude=-89.5597,
        default_radius_meters=8000,
    ),
    "san_miguel": PredefinedZone(
        key="san_miguel",
        name="San Miguel",
        department="San Miguel",
        latitude=13.4833,
        longitude=-88.1833,
        default_radius_meters=8000,
    ),
    "santa_tecla": PredefinedZone(
        key="santa_tecla",
        name="Santa Tecla",
        department="La Libertad",
        latitude=13.6769,
        longitude=-89.2797,
        default_radius_meters=7000,
    ),
    "acajutla": PredefinedZone(
        key="acajutla",
        name="Acajutla",
        department="Sonsonate",
        latitude=13.5928,
        longitude=-89.8275,
        default_radius_meters=7000,
    ),
}


def get_predefined_zone(zone_key_or_name: str) -> PredefinedZone | None:
    """Resolve a predefined zone by its key or display name (case-insensitive)."""
    normalized = zone_key_or_name.strip().lower().replace(" ", "_")
    if normalized in PREDEFINED_ZONES:
        return PREDEFINED_ZONES[normalized]
    for zone in PREDEFINED_ZONES.values():
        if zone.name.lower() == zone_key_or_name.strip().lower():
            return zone
    return None
