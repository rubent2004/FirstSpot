"""Reads the pinned Geofabrik country extract with pyosmium.

One pass over the 35 MB file yields everything the LCC dimension needs: the
response-capacity facilities and the classified primary road network. Measured on
``el-salvador-latest.osm.pbf`` -- 5,390,925 nodes, 809,474 ways, 4,223 relations
-- the pass takes about 22 s.

Three details of the OSM data model are load-bearing here, and getting any of
them wrong silently loses facilities rather than failing.

**A facility is not always a node.** Hospitals in this extract appear as nodes,
as closed ways, and as multipolygon *relations*. Reading nodes and ways only
returns 164 hospitals; enabling the area handler returns 184. Twenty missing
hospitals would have lengthened the published distance for every district around
them, so :meth:`read` enables ``with_areas`` and takes the mean of each area's
outer-ring nodes as its representative point.

**Way geometry needs a location index.** A way stores node references, not
coordinates, so ``with_locations`` is required before ``w.nodes`` has usable
positions. Without it the roads come back empty and no error is raised.

**The same facility can carry two identities.** A hospital mapped as both a node
and a building area is two upstream objects, and both are kept: they deduplicate
on ``(osm_type, osm_id, kind)``, and for a *nearest-facility* measurement a
duplicate point in the same place changes no distance. Dropping one on a guess
about which is canonical could move a facility by the width of a campus.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from app.modules.ingestion.domain.osm_extract import (
    CopingFacilityKind,
    OsmFacility,
    OsmRoad,
    classify_coping_facility,
    classify_road_class,
)

NAME_TAGS: tuple[str, ...] = ("name:es", "name", "name:en", "official_name", "operator")
"""Name preference order, matching the Overpass classifier already in use."""

MAX_NAME_LENGTH = 200
"""Width of the stored name column; a longer upstream name is truncated."""


class OsmExtractError(RuntimeError):
    """Raised when the extract cannot be read as a coping-capacity source."""


@dataclass(frozen=True, slots=True)
class OsmExtractContents:
    """Everything one pass over the extract produced, with its own counts."""

    facilities: tuple[OsmFacility, ...]
    roads: tuple[OsmRoad, ...]
    node_count: int
    way_count: int
    relation_count: int
    degenerate_way_count: int

    def facility_counts(self) -> dict[str, int]:
        """Count facilities per kind, for the ingest report."""
        counts: dict[str, int] = {kind.value: 0 for kind in CopingFacilityKind}
        for facility in self.facilities:
            counts[facility.kind.value] += 1
        return counts


def _name(tags: object) -> str:
    """Pick the best available name, or an empty string.

    An unnamed clinic is still a clinic and still shortens somebody's distance,
    so an absent name is never a reason to drop a facility.
    """
    for key in NAME_TAGS:
        value = tags.get(key)  # type: ignore[attr-defined]
        if value and str(value).strip():
            return str(value).strip()[:MAX_NAME_LENGTH]
    return ""


class OsmPbfReader:
    """Single-pass reader over a Geofabrik ``.osm.pbf`` country extract."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> OsmExtractContents:
        """Extract facilities and primary roads in one pass.

        Raises:
            OsmExtractError: If the file is absent, or if pyosmium is not
                installed. Both are reported here rather than as an opaque
                import or OS error, because the remedy differs: one is ``just
                osm-download`` and the other is ``uv sync``.
        """
        try:
            import osmium
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise OsmExtractError(
                "pyosmium is not installed, so the national OpenStreetMap "
                "extract cannot be read. Run 'uv sync' in backend/."
            ) from exc

        if not self.path.exists():
            raise OsmExtractError(
                f"The OpenStreetMap extract {self.path} is absent. Run "
                f"'just osm-download' to fetch it from Geofabrik; it is about "
                f"35 MB and is deliberately not committed."
            )

        facilities: dict[tuple[str, int, str], OsmFacility] = {}
        roads: dict[int, OsmRoad] = {}
        nodes = ways = relations = degenerate = 0

        # with_locations resolves way node coordinates; with_areas assembles
        # closed ways and multipolygon relations into Area objects. Both are
        # required, and omitting either loses data without raising.
        processor = osmium.FileProcessor(str(self.path)).with_locations().with_areas()

        for obj in processor:
            if isinstance(obj, osmium.osm.Node):
                nodes += 1
                kind = classify_coping_facility(obj.tags)
                if kind is not None:
                    facilities[("node", obj.id, kind.value)] = OsmFacility(
                        kind=kind,
                        osm_type="node",
                        osm_id=obj.id,
                        name=_name(obj.tags),
                        longitude=obj.location.lon,
                        latitude=obj.location.lat,
                    )
                continue

            if isinstance(obj, osmium.osm.Area):
                # An Area is synthesised from a closed way or from a
                # multipolygon relation; from_way() says which, and orig_id()
                # gives the upstream identifier rather than the synthetic one.
                kind = classify_coping_facility(obj.tags)
                if kind is None:
                    continue
                point = _area_representative_point(obj)
                if point is None:
                    continue
                osm_type = "way" if obj.from_way() else "relation"
                facilities[(osm_type, obj.orig_id(), kind.value)] = OsmFacility(
                    kind=kind,
                    osm_type=osm_type,
                    osm_id=obj.orig_id(),
                    name=_name(obj.tags),
                    longitude=point[0],
                    latitude=point[1],
                )
                continue

            if isinstance(obj, osmium.osm.Way):
                ways += 1
                road_class = classify_road_class(obj.tags)
                if road_class is None:
                    continue
                coordinates = tuple(
                    (node.lon, node.lat)
                    for node in obj.nodes
                    if node.location.valid()
                )
                if len(coordinates) < 2:
                    # A way clipped at the country border can keep a single
                    # node. Counted rather than dropped silently, so the ingest
                    # report shows how much of the network was unusable.
                    degenerate += 1
                    continue
                roads[obj.id] = OsmRoad(
                    road_class=road_class,
                    highway_tag=str(obj.tags.get("highway", "")),
                    osm_id=obj.id,
                    coordinates=coordinates,
                )
                continue

            if isinstance(obj, osmium.osm.Relation):
                relations += 1

        if not facilities:
            raise OsmExtractError(
                f"No coping-capacity facility was found in {self.path}. The "
                f"extract parsed but matched nothing, which means either the "
                f"wrong country file or a tag taxonomy change upstream."
            )

        return OsmExtractContents(
            facilities=tuple(facilities.values()),
            roads=tuple(roads.values()),
            node_count=nodes,
            way_count=ways,
            relation_count=relations,
            degenerate_way_count=degenerate,
        )


def _area_representative_point(area: object) -> tuple[float, float] | None:
    """Return the mean of an area's outer-ring nodes, or None when it has none.

    The mean of the outer rings is not the polygon centroid and does not need to
    be: it is a point inside or near a building footprint, and a building
    footprint is tens of metres across while the distances this feeds are
    hundreds to tens of thousands. Computing a true centroid would mean carrying
    a geometry library into the reader for an error smaller than the OSM node
    accuracy it is derived from.
    """
    longitude_total = latitude_total = 0.0
    count = 0
    for ring in area.outer_rings():  # type: ignore[attr-defined]
        for node in ring:
            longitude_total += node.lon
            latitude_total += node.lat
            count += 1
    if count == 0:
        return None
    return longitude_total / count, latitude_total / count


def iter_road_wkt(roads: tuple[OsmRoad, ...]) -> Iterator[tuple[int, str, str, str]]:
    """Yield ``(osm_id, road_class, highway_tag, wkt)`` rows for a bulk insert."""
    for road in roads:
        yield road.osm_id, road.road_class, road.highway_tag, road.to_wkt()
