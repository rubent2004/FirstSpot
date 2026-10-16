"""Overpass QL query builder and OpenStreetMap tag classifier."""

from typing import Any

from app.modules.places.domain.entities import (
    CATEGORY_GROUP_MAP,
    PlaceCategory,
    VulnerablePlace,
)

AMENITY_CATEGORY_MAP: dict[str, PlaceCategory] = {
    "hospital": PlaceCategory.HOSPITAL,
    "clinic": PlaceCategory.CLINIC,
    "social_facility": PlaceCategory.SOCIAL_FACILITY,
    "kindergarten": PlaceCategory.KINDERGARTEN,
    "school": PlaceCategory.SCHOOL,
    "community_centre": PlaceCategory.COMMUNITY_CENTRE,
    "university": PlaceCategory.UNIVERSITY,
    "pharmacy": PlaceCategory.PHARMACY,
    "marketplace": PlaceCategory.COMMERCIAL_HUB,
    "place_of_worship": PlaceCategory.PLACE_OF_WORSHIP,
}

CATEGORY_DISPLAY_LABELS: dict[PlaceCategory, str] = {
    PlaceCategory.HOSPITAL: "Hospital",
    PlaceCategory.CLINIC: "Clinic",
    PlaceCategory.SOCIAL_FACILITY: "Social Facility",
    PlaceCategory.KINDERGARTEN: "Kindergarten",
    PlaceCategory.SCHOOL: "School",
    PlaceCategory.COMMUNITY_CENTRE: "Community Centre",
    PlaceCategory.UNIVERSITY: "University",
    PlaceCategory.PHARMACY: "Pharmacy",
    PlaceCategory.COMMERCIAL_HUB: "Commercial Hub",
    PlaceCategory.PLACE_OF_WORSHIP: "Place of Worship",
}


def build_overpass_query(
    latitude: float,
    longitude: float,
    radius_meters: int,
    timeout_seconds: int = 60,
) -> str:
    """Build an Overpass QL query using nwr quantifiers and center geometry output."""
    if radius_meters <= 0 or radius_meters > 50000:
        raise ValueError("radius_meters must be between 1 and 50000")
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError("latitude must be between -90 and 90")
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError("longitude must be between -180 and 180")

    return (
        f"[out:json][timeout:{timeout_seconds}];\n"
        "(\n"
        '  nwr["amenity"~"hospital|clinic|pharmacy|school|kindergarten|university|social_facility|community_centre|marketplace|place_of_worship"]'
        f"(around:{radius_meters},{latitude},{longitude});\n"
        f'  nwr["shop"="mall"](around:{radius_meters},{latitude},{longitude});\n'
        ");\n"
        "out center tags;"
    )


def classify_osm_tags(tags: dict[str, Any]) -> PlaceCategory | None:
    """Map raw OpenStreetMap tags to a domain PlaceCategory."""
    amenity = str(tags.get("amenity", "")).strip().lower()
    if amenity in AMENITY_CATEGORY_MAP:
        return AMENITY_CATEGORY_MAP[amenity]

    shop = str(tags.get("shop", "")).strip().lower()
    if shop == "mall":
        return PlaceCategory.COMMERCIAL_HUB

    healthcare = str(tags.get("healthcare", "")).strip().lower()
    if healthcare == "hospital":
        return PlaceCategory.HOSPITAL
    if healthcare in {"clinic", "centre"}:
        return PlaceCategory.CLINIC
    if healthcare == "pharmacy":
        return PlaceCategory.PHARMACY

    return None


def extract_coordinates(element: dict[str, Any]) -> tuple[float, float] | None:
    """Extract (latitude, longitude) from an Overpass node, way, or relation element."""
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])

    center = element.get("center")
    if isinstance(center, dict) and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])

    return None


def parse_overpass_element(
    element: dict[str, Any],
    zone_name: str,
) -> VulnerablePlace | None:
    """Convert a raw Overpass JSON element into a domain VulnerablePlace entity."""
    osm_type = str(element.get("type", "")).strip().lower()
    osm_id_raw = element.get("id")
    if osm_type not in {"node", "way", "relation"} or osm_id_raw is None:
        return None

    try:
        osm_id = int(osm_id_raw)
    except (TypeError, ValueError):
        return None

    raw_tags = element.get("tags")
    tags: dict[str, Any] = dict(raw_tags) if isinstance(raw_tags, dict) else {}
    category = classify_osm_tags(tags)
    if category is None:
        return None

    coords = extract_coordinates(element)
    if coords is None:
        return None
    latitude, longitude = coords

    raw_name = (
        tags.get("name:es")
        or tags.get("name")
        or tags.get("name:en")
        or tags.get("official_name")
        or tags.get("operator")
    )
    label = CATEGORY_DISPLAY_LABELS[category]
    name = (
        str(raw_name).strip()
        if raw_name and str(raw_name).strip()
        else f"Unnamed {label} (#{osm_id})"
    )

    cleaned_tags = {str(k): str(v) for k, v in tags.items() if v is not None}

    return VulnerablePlace(
        osm_type=osm_type,
        osm_id=osm_id,
        name=name,
        category=category,
        vulnerability_group=CATEGORY_GROUP_MAP[category],
        zone_name=zone_name,
        latitude=latitude,
        longitude=longitude,
        osm_tags=cleaned_tags,
    )


def parse_overpass_elements(
    elements: list[dict[str, Any]],
    zone_name: str,
) -> list[VulnerablePlace]:
    """Parse and deduplicate a list of Overpass JSON elements by (osm_type, osm_id)."""
    deduped: dict[tuple[str, int], VulnerablePlace] = {}
    for elem in elements:
        parsed = parse_overpass_element(elem, zone_name=zone_name)
        if parsed is not None:
            deduped[(parsed.osm_type, parsed.osm_id)] = parsed
    return list(deduped.values())
