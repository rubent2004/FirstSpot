"""Tag classification for the national OpenStreetMap extract behind LCC.

Why a national extract and not the live Overpass ingestion
----------------------------------------------------------
The existing Overpass path in :mod:`..infrastructure.overpass_client` answers "what
can a responder use near this point", and it is queried zone by zone. Measured on
the ingested corpus, that leaves **24 of 262 districts with any place at all and
21 with a hospital or clinic**. An index built on it would not measure coping
capacity; it would measure where Overpass happened to be queried, and it would do
so while looking entirely plausible, because the queried zones are the
metropolitan ones and the unqueried remainder is rural.

The Geofabrik country extract (``el-salvador-latest.osm.pbf``, ODbL 1.0, rebuilt
daily) fixes that in one move: 184 hospitals, 518 clinics, 1,199 schools and
2,506 primary-class road ways nationally, from a **pinned file rather than a live
API**. The pinning matters as much as the coverage -- a published index has to be
reproducible, and an Overpass answer changes between two runs for reasons that
have nothing to do with the territory.

Why these tags and no others
----------------------------
``amenity`` is checked before ``healthcare`` because a building carrying both
must resolve the same way on every run; OSM applies the two tags inconsistently
and the order is therefore a declared choice rather than an accident.

``highway`` is restricted to ``motorway``, ``trunk`` and ``primary``: the feature
document specifies the *primary* network, and quietly admitting ``secondary``
would change every road-access score in the index without changing its
documentation. The secondary network is 2,251 ways and is deliberately left out.

What this module refuses to do
------------------------------
It does not decide whether a facility is *usable*. OSM records that a building is
tagged ``amenity=hospital``; it does not record whether the hospital has power,
staff, or a standing roof. Nothing downstream may read a short distance as
available care.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

OSM_SNAPSHOT_SOURCE = "OpenStreetMap via Geofabrik, el-salvador-latest.osm.pbf"
"""Attribution published with every facility and road record."""

OSM_SNAPSHOT_LICENCE = "ODbL 1.0"
"""Licence of the Geofabrik extract, required to be published with derived data."""

OSM_SNAPSHOT_URL = (
    "https://download.geofabrik.de/central-america/el-salvador-latest.osm.pbf"
)
"""The pinned download location, so the corpus is regenerable by script."""

PRIMARY_ROAD_CLASS = "primary"
"""The one road class ingested: the classified primary network."""

PRIMARY_HIGHWAY_TAGS: frozenset[str] = frozenset({"motorway", "trunk", "primary"})
"""``highway`` values that constitute the primary network.

Link roads (``primary_link``, ``trunk_link``) are excluded: they are ramps whose
geometry duplicates the junction they serve, so including them would add length
without adding reach, and would pull a district's distance down for a road it
already measures against.
"""


class CopingFacilityKind(StrEnum):
    """A facility that bears on a territory's ability to cope with an event.

    These are **response capacity**, not vulnerable places. The distinction is
    why they live here and not in
    :class:`app.modules.places.domain.entities.PlaceCategory`: a fire station is
    not a population to evacuate, it carries no ``priority_score``, and it
    belongs to none of the four ``VulnerabilityGroup`` axes.
    """

    HOSPITAL = "hospital"
    CLINIC = "clinic"
    FIRE_STATION = "fire_station"
    SCHOOL = "school"
    COMMUNITY_CENTRE = "community_centre"


HEALTH_FACILITY_KINDS: tuple[CopingFacilityKind, ...] = (
    CopingFacilityKind.HOSPITAL,
    CopingFacilityKind.CLINIC,
)
"""Facilities that can treat a casualty, grouped because the index measures
distance to *care*, not distance to a particular tier of it."""

SHELTER_FACILITY_KINDS: tuple[CopingFacilityKind, ...] = (
    CopingFacilityKind.SCHOOL,
    CopingFacilityKind.COMMUNITY_CENTRE,
)
"""Buildings commonly requisitioned as collective shelter in El Salvador.

Published, but excluded from the index -- see the catalogue's
``exclusion_reason`` for the measured evidence.
"""

AMENITY_FACILITY_MAP: dict[str, CopingFacilityKind] = {
    "hospital": CopingFacilityKind.HOSPITAL,
    "clinic": CopingFacilityKind.CLINIC,
    # A doctors' surgery is primary care and treats the same walk-in casualty a
    # clinic does; OSM splits them by establishment size, not by capability.
    "doctors": CopingFacilityKind.CLINIC,
    "fire_station": CopingFacilityKind.FIRE_STATION,
    "school": CopingFacilityKind.SCHOOL,
    "community_centre": CopingFacilityKind.COMMUNITY_CENTRE,
}

HEALTHCARE_FACILITY_MAP: dict[str, CopingFacilityKind] = {
    "hospital": CopingFacilityKind.HOSPITAL,
    "clinic": CopingFacilityKind.CLINIC,
    "centre": CopingFacilityKind.CLINIC,
}


@dataclass(frozen=True, slots=True)
class OsmFacility:
    """One point facility extracted from the national snapshot.

    Args:
        kind: The classified capability.
        osm_type: ``node``, ``way`` or ``relation``, kept so a record traces back
            to the upstream object and a re-ingest is idempotent.
        osm_id: Upstream identifier within ``osm_type``.
        name: Published name, possibly empty -- an unnamed clinic is still a
            clinic, and dropping it would shorten the distance of nobody.
        longitude: Representative point, degrees.
        latitude: Representative point, degrees.
    """

    kind: CopingFacilityKind
    osm_type: str
    osm_id: int
    name: str
    longitude: float
    latitude: float

    def __post_init__(self) -> None:
        if self.osm_type not in {"node", "way", "relation"}:
            raise ValueError(
                f"Unknown OSM object type {self.osm_type!r}: a facility has to "
                f"trace back to a node, a way or a relation for the ingest to be "
                f"idempotent."
            )


@dataclass(frozen=True, slots=True)
class OsmRoad:
    """One way of the primary road network, as an ordered coordinate run.

    Args:
        road_class: Always :data:`PRIMARY_ROAD_CLASS` today; stored rather than
            implied so admitting the secondary network later is a data change
            and not a silent redefinition of every published score.
        highway_tag: The upstream ``highway`` value, kept for audit.
        osm_id: Upstream way identifier.
        coordinates: ``(longitude, latitude)`` pairs in way order.
    """

    road_class: str
    highway_tag: str
    osm_id: int
    coordinates: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if len(self.coordinates) < 2:
            raise ValueError(
                f"Way {self.osm_id} has {len(self.coordinates)} usable node(s); a "
                f"road needs at least two. A degenerate linestring has no length "
                f"and PostGIS would refuse it at insert time rather than here, "
                f"where the upstream object is still identifiable."
            )

    def to_wkt(self) -> str:
        """Render the run as a WKT linestring for ``ST_GeogFromText``.

        Seven decimal places is about 11 mm at the equator -- far finer than OSM
        node accuracy -- and keeps the literal short enough that a national load
        of 2,506 ways stays one bulk statement.
        """
        points = ", ".join(
            f"{longitude:.7f} {latitude:.7f}"
            for longitude, latitude in self.coordinates
        )
        return f"LINESTRING({points})"


def _tag(tags: Mapping[str, Any], key: str) -> str:
    """Read one tag, normalised, treating an absent tag as empty."""
    return str(tags.get(key, "")).strip().lower()


def classify_coping_facility(tags: Mapping[str, Any]) -> CopingFacilityKind | None:
    """Map raw OSM tags onto a coping facility kind, or None.

    ``amenity`` is consulted first on purpose: a building tagged both
    ``amenity=hospital`` and ``healthcare=clinic`` exists in this extract, and an
    undefined precedence would make the ingest non-deterministic.
    """
    amenity = _tag(tags, "amenity")
    if amenity in AMENITY_FACILITY_MAP:
        return AMENITY_FACILITY_MAP[amenity]

    healthcare = _tag(tags, "healthcare")
    if healthcare in HEALTHCARE_FACILITY_MAP:
        return HEALTHCARE_FACILITY_MAP[healthcare]

    return None


def classify_road_class(tags: Mapping[str, Any]) -> str | None:
    """Return the ingested road class of a way, or None when it is not primary."""
    if _tag(tags, "highway") in PRIMARY_HIGHWAY_TAGS:
        return PRIMARY_ROAD_CLASS
    return None
