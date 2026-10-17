"""Loads the national OSM coping corpus and refreshes the cached access measures.

Two passes, both idempotent.

**Load.** Facilities and primary roads are replaced wholesale rather than merged.
The upstream extract is rebuilt daily and a deleted hospital has to disappear
from our copy too; an upsert-only load would accumulate facilities that OSM has
since removed, and every one of them would shorten somebody's published
distance. ``TRUNCATE`` plus bulk insert inside one transaction is both simpler
and more correct than reconciling deletions.

**Measure.** The access pass writes ``osm_unit_access``, one row per DEGURBA
Nivel 2 polygon. It is the only place in LCC where PostGIS does arithmetic, and
it does the minimum: a nearest-neighbour distance and an area. Every ratio,
percentile and score is computed in
:mod:`app.modules.prioritization.domain.coping`, so the published numbers stay
auditable in one place.

Two measurements, and why each is shaped the way it is
------------------------------------------------------
``geodesic_metres_to_nearest_*`` is measured from **one representative interior
point** per polygon (``ST_PointOnSurface``), in **geography** space, so the
result is true ellipsoidal metres. It is a lower bound on travel distance -- see
:data:`app.modules.prioritization.domain.coping.DISTANCE_BASIS`.

``area_beyond_*_threshold_m2`` is measured by **areal intersection in EPSG:32616**,
the same metric CRS B4 settled on after establishing that EPSG:5399 does not
exist. It answers a different question from the distance -- what fraction of a
polygon's *land* lies beyond reach, rather than how far its centre is -- and that
fraction is converted to a population share by the domain under the same
uniform-density assumption B4 declared.

Why the buffers are unioned once
--------------------------------
Buffering 2,506 road ways and 702 facilities individually and intersecting each
against 902 polygons is a quarter of a million intersections. Unioning each
buffer set once first turns it into 902, and measured on the real corpus the
whole areal pass then runs in about 5 s.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.domain.osm_extract import (
    HEALTH_FACILITY_KINDS,
    SHELTER_FACILITY_KINDS,
    CopingFacilityKind,
    OsmFacility,
    OsmRoad,
)

METRIC_SRID = 32616
"""EPSG:32616, WGS 84 / UTM zone 16N.

Inherited from B4 rather than chosen again. It shares the WGS 84 datum with the
stored ``GEOGRAPHY``, so the transform needs no datum shift and no PROJ
"ballpark" fallback; measured on the westernmost DEGURBA unit the areal weight
differs from the geodesic weight by 1.5e-6 relative. **EPSG:5399 does not
exist** -- it is absent from PROJ's ``crs_view`` and from PostGIS
``spatial_ref_sys``, despite being named in the research as "SIRGAS-ES2007".
"""

_INSERT_FACILITIES = text(
    """
    INSERT INTO osm_coping_facility
        (kind, osm_type, osm_id, name, geom, snapshot_date)
    SELECT f.kind, f.osm_type, f.osm_id, f.name,
           ST_SetSRID(ST_MakePoint(f.longitude, f.latitude), 4326)::geography,
           CAST(:snapshot_date AS date)
    FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS f(
        kind text, osm_type text, osm_id bigint, name text,
        longitude double precision, latitude double precision
    )
    ON CONFLICT (osm_type, osm_id, kind) DO NOTHING
    """
)

_INSERT_ROADS = text(
    """
    INSERT INTO osm_road_segment
        (road_class, highway_tag, osm_id, geom, snapshot_date)
    SELECT r.road_class, r.highway_tag, r.osm_id,
           ST_GeogFromText('SRID=4326;' || r.wkt),
           CAST(:snapshot_date AS date)
    FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r(
        road_class text, highway_tag text, osm_id bigint, wkt text
    )
    ON CONFLICT (osm_id) DO NOTHING
    """
)

_REFRESH_ACCESS = text(
    """
    WITH unit AS (
        SELECT id,
               geom,
               -- One representative interior point per polygon. ST_PointOnSurface
               -- is guaranteed to fall inside the polygon, which ST_Centroid is
               -- not for the crescent-shaped coastal and ravine units here.
               ST_PointOnSurface(geom::geometry)::geography AS point,
               ST_Transform(geom::geometry, CAST(:metric_srid AS integer)) AS metric
        FROM census_population_unit
        WHERE dug_level = CAST(:dug_level AS smallint)
    ),
    health_buffer AS (
        SELECT ST_Union(
                   ST_Buffer(
                       ST_Transform(geom::geometry, CAST(:metric_srid AS integer)),
                       CAST(:threshold AS double precision)
                   )
               ) AS area
        FROM osm_coping_facility
        WHERE kind = ANY(:health_kinds)
    ),
    road_buffer AS (
        SELECT ST_Union(
                   ST_Buffer(
                       ST_Transform(geom::geometry, CAST(:metric_srid AS integer)),
                       CAST(:threshold AS double precision)
                   )
               ) AS area
        FROM osm_road_segment
    )
    INSERT INTO osm_unit_access (
        population_unit_id,
        geodesic_metres_to_nearest_health,
        geodesic_metres_to_nearest_road,
        geodesic_metres_to_nearest_fire_station,
        area_m2,
        area_beyond_health_threshold_m2,
        area_beyond_road_threshold_m2,
        shelter_facility_count,
        access_threshold_metres,
        snapshot_date,
        computed_at
    )
    SELECT u.id,
           (
               SELECT min(ST_Distance(u.point, f.geom))
               FROM osm_coping_facility f
               WHERE f.kind = ANY(:health_kinds)
           ),
           (SELECT min(ST_Distance(u.point, r.geom)) FROM osm_road_segment r),
           (
               SELECT min(ST_Distance(u.point, f.geom))
               FROM osm_coping_facility f
               WHERE f.kind = CAST(:fire_kind AS text)
           ),
           ST_Area(u.metric),
           -- The area NOT within the threshold. GREATEST guards the floating
           -- point case where an entirely covered polygon intersects its own
           -- buffer at an area a few ulps above its own.
           GREATEST(
               ST_Area(u.metric)
               - COALESCE(
                   ST_Area(ST_Intersection(u.metric, hb.area)), 0
               ),
               0
           ),
           GREATEST(
               ST_Area(u.metric)
               - COALESCE(ST_Area(ST_Intersection(u.metric, rb.area)), 0),
               0
           ),
           (
               SELECT count(*)
               FROM osm_coping_facility s
               WHERE s.kind = ANY(:shelter_kinds)
                 AND ST_Intersects(u.geom, s.geom)
           ),
           CAST(:threshold AS integer),
           CAST(:snapshot_date AS date),
           now()
    FROM unit u
    CROSS JOIN health_buffer hb
    CROSS JOIN road_buffer rb
    """
)


@dataclass(frozen=True, slots=True)
class CopingLoadReport:
    """What one load wrote, for the script's stdout and for the tests."""

    facilities_loaded: int
    roads_loaded: int
    access_rows: int
    facility_counts: dict[str, int]
    snapshot_date: date
    elapsed_seconds: float


class OsmCopingLoader:
    """Writes the OSM coping corpus and its cached access measurements."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load(
        self,
        facilities: tuple[OsmFacility, ...],
        roads: tuple[OsmRoad, ...],
        snapshot_date: date,
        access_threshold_metres: int,
        dug_level: int,
    ) -> CopingLoadReport:
        """Replace the corpus and recompute every cached access measurement.

        One transaction: a half-loaded corpus with a fully recomputed access
        table would publish distances measured against facilities that are no
        longer there, and nothing downstream could detect it.
        """
        started = datetime.now(timezone.utc)

        # Replaced wholesale, newest dependency first. osm_unit_access has an ON
        # DELETE CASCADE to the census units, not to these tables, so it is
        # cleared explicitly.
        await self.session.execute(text("TRUNCATE TABLE osm_unit_access"))
        await self.session.execute(text("TRUNCATE TABLE osm_coping_facility"))
        await self.session.execute(text("TRUNCATE TABLE osm_road_segment"))

        facility_rows = [
            {
                "kind": facility.kind.value,
                "osm_type": facility.osm_type,
                "osm_id": facility.osm_id,
                "name": facility.name,
                "longitude": facility.longitude,
                "latitude": facility.latitude,
            }
            for facility in facilities
        ]
        road_rows = [
            {
                "road_class": road.road_class,
                "highway_tag": road.highway_tag,
                "osm_id": road.osm_id,
                "wkt": road.to_wkt(),
            }
            for road in roads
        ]

        import json

        if facility_rows:
            await self.session.execute(
                _INSERT_FACILITIES,
                {
                    "rows": json.dumps(facility_rows),
                    "snapshot_date": snapshot_date,
                },
            )
        if road_rows:
            await self.session.execute(
                _INSERT_ROADS,
                {
                    "rows": json.dumps(road_rows),
                    "snapshot_date": snapshot_date,
                },
            )

        await self.session.execute(
            _REFRESH_ACCESS,
            {
                "metric_srid": METRIC_SRID,
                "dug_level": dug_level,
                "threshold": access_threshold_metres,
                "snapshot_date": snapshot_date,
                "health_kinds": [kind.value for kind in HEALTH_FACILITY_KINDS],
                "shelter_kinds": [kind.value for kind in SHELTER_FACILITY_KINDS],
                "fire_kind": CopingFacilityKind.FIRE_STATION.value,
            },
        )
        await self.session.commit()

        facilities_loaded = await self.session.scalar(
            text("SELECT count(*) FROM osm_coping_facility")
        )
        roads_loaded = await self.session.scalar(
            text("SELECT count(*) FROM osm_road_segment")
        )
        access_rows = await self.session.scalar(
            text("SELECT count(*) FROM osm_unit_access")
        )
        counts_result = await self.session.execute(
            text("SELECT kind, count(*) AS n FROM osm_coping_facility GROUP BY kind")
        )

        return CopingLoadReport(
            facilities_loaded=int(facilities_loaded or 0),
            roads_loaded=int(roads_loaded or 0),
            access_rows=int(access_rows or 0),
            facility_counts={row.kind: int(row.n) for row in counts_result},
            snapshot_date=snapshot_date,
            elapsed_seconds=(
                datetime.now(timezone.utc) - started
            ).total_seconds(),
        )
