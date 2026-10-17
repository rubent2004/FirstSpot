"""PostGIS reads for areal-weighted exposure: overlaps and district rates.

This adapter only *reads* census tables. It returns the raw ingredients -- metric
areas and district rates -- and leaves every arithmetic decision to
:mod:`app.modules.census.domain.exposure`, so the estimator stays testable
without a database and the published numbers are auditable in one place instead
of being buried in SQL.

Two SQL shapes matter here, both for cost rather than correctness.

**The buffer test runs in geometry space, not geography space.** The buffer
itself is built with ``ST_Buffer`` on the ``GEOGRAPHY`` point, so its radius is
already in metres and no degree conversion is invented. But the containment test
against ``census_population_unit.geom`` is made on ``geom::geometry`` against a
GIST index on that same expression. Measured on the ingested corpus: the exact
geography ``ST_Intersects`` over 1,481 places took 24.2 s, the same test in
geometry space without the expression index took 50.9 s, and with the index it
took 0.72 s. Both spaces agree for El Salvador, which crosses no meridian
discontinuity; the index is what makes a whole-table refresh affordable.

**Each unit's own area is computed once, not once per overlap.** Transforming a
full DEGURBA multipolygon is the expensive half of the ratio, while the clipped
intersection is small. The unit areas are therefore resolved in a separate CTE
over the distinct units actually touched.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.census.domain.exposure import (
    METRIC_PROJECTION_SRID,
    DistrictVulnerableRates,
    UnitOverlap,
)
from app.modules.census.domain.geo_codes import CensusLevel
from app.modules.census.domain.population import (
    OLDER_ADULT_BANDS,
    YOUNG_CHILD_BANDS,
)

ANALYSIS_DUG_LEVEL = 2
"""DEGURBA Nivel 2: the 902-unit layer that carries real population figures."""

AGE_STRUCTURE_TOPIC = "edad_sexo"
DISABILITY_TOPIC = "discapacidad"
POPULATION_TOPIC = "poblacion"
POPULATION_TOTAL_CATEGORY = "total"


def metric_area_sql(geometry_expression: str) -> str:
    """Return the SQL that measures a geometry in square metres.

    Args:
        geometry_expression: SQL expression yielding a ``geometry`` in SRID 4326.
    """
    return f"ST_Area(ST_Transform({geometry_expression}, {METRIC_PROJECTION_SRID}))"


def areal_weight_sql(unit_geometry: str, buffer_geometry: str) -> str:
    """Return the SQL that computes one unit's areal weight inside a buffer.

    This is the declared spatial assignment rule expressed in SQL: the share of
    the unit's own area that falls inside the buffer, measured in the metric
    projection and saturated at 1. It is exported so the arithmetic can be
    verified against literal geometries, independently of any ingested row.

    Args:
        unit_geometry: SQL expression yielding the population unit's geometry.
        buffer_geometry: SQL expression yielding the buffer's geometry.
    """
    overlap = metric_area_sql(f"ST_Intersection({unit_geometry}, {buffer_geometry})")
    unit = metric_area_sql(unit_geometry)
    return f"LEAST(1.0, {overlap} / NULLIF({unit}, 0))"


UNIT_IN_BUFFER_SQL = (
    "u.dug_level = CAST(:dug_level AS smallint) "
    "AND u.geom::geometry && {buffer} "
    "AND ST_Intersects(u.geom::geometry, {buffer})"
)
"""The spatial assignment predicate: the indexed geometry-space containment test."""


def overlaps_query_sql(buffered_source: str, key_columns: Sequence[str] = ()) -> str:
    """Build the overlap query for any source of buffers.

    One definition of the shape, used both for a single ad-hoc point and for a
    whole table of places, so the two paths cannot drift apart in their areas,
    their clipping or their spatial predicate.

    Args:
        buffered_source: SQL for a relation exposing ``buffer_geom`` plus every
            column named in ``key_columns``.
        key_columns: Columns of ``buffered_source`` carried through to identify
            which buffer each overlap belongs to.

    Returns:
        SQL selecting one row per (buffer, population unit) overlap, with the
        unit's metric area and the metric area of the clipped intersection.
    """
    carried = "".join(f"b.{column}, " for column in key_columns)
    projected = "".join(f"p.{column}, " for column in key_columns)
    ordering = "".join(f"p.{column}, " for column in key_columns)
    predicate = UNIT_IN_BUFFER_SQL.format(buffer="b.buffer_geom")
    return f"""
    WITH buffered AS ({buffered_source}),
    pairs AS (
        SELECT {carried}u.id AS unit_id,
               u.district_code,
               u.population,
               ST_Intersection(u.geom::geometry, b.buffer_geom) AS clip
        FROM buffered b
        JOIN census_population_unit u ON {predicate}
    ),
    unit_area AS (
        SELECT u.id, {metric_area_sql("u.geom::geometry")} AS unit_area_m2
        FROM census_population_unit u
        WHERE u.id IN (SELECT unit_id FROM pairs)
    )
    SELECT {projected}p.unit_id,
           p.district_code,
           p.population,
           a.unit_area_m2,
           {metric_area_sql("p.clip")} AS overlap_area_m2
    FROM pairs p
    JOIN unit_area a ON a.id = p.unit_id
    ORDER BY {ordering}p.unit_id
    """


POINT_BUFFER_SOURCE = """
        SELECT ST_Buffer(
            ST_SetSRID(ST_Point(CAST(:longitude AS double precision),
                                CAST(:latitude AS double precision)), 4326)::geography,
            CAST(:radius_meters AS double precision)
        )::geometry AS buffer_geom
"""
"""Buffer around one ad-hoc coordinate, built on geography so the radius is metres."""

_OVERLAPS_FOR_POINT = text(overlaps_query_sql(POINT_BUFFER_SOURCE))

_DISTRICT_VULNERABLE_RATES = text(
    """
    WITH age AS (
        SELECT unit_code,
               sum(value) FILTER (WHERE age_band = ANY(:young_child_bands))
                   AS young_children,
               sum(value) FILTER (WHERE age_band = ANY(:older_adult_bands))
                   AS older_adults
        FROM census_indicator
        WHERE unit_level = CAST(:district_level AS text)
          AND topic = CAST(:age_topic AS text)
          AND NOT suppressed
        GROUP BY unit_code
    ),
    resident_total AS (
        SELECT unit_code, sum(value) AS population
        FROM census_indicator
        WHERE unit_level = CAST(:district_level AS text)
          AND topic = CAST(:population_topic AS text)
          AND category = CAST(:population_category AS text)
          AND sex IS NULL
          AND NOT suppressed
        GROUP BY unit_code
    ),
    disability AS (
        SELECT unit_code, sum(value) AS persons
        FROM census_indicator
        WHERE unit_level = CAST(:district_level AS text)
          AND topic = CAST(:disability_topic AS text)
          AND NOT suppressed
        GROUP BY unit_code
    )
    SELECT t.unit_code AS district_code,
           COALESCE(a.older_adults, 0) / t.population AS older_adult_rate,
           COALESCE(a.young_children, 0) / t.population AS young_child_rate,
           COALESCE(d.persons, 0) / t.population AS disability_rate
    FROM resident_total t
    LEFT JOIN age a ON a.unit_code = t.unit_code
    LEFT JOIN disability d ON d.unit_code = t.unit_code
    WHERE t.population > 0
    ORDER BY t.unit_code
    """
)


class CensusExposureRepository:
    """Read-only PostGIS adapter for areal-weighted exposure ingredients."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overlaps_for_point(
        self,
        longitude: float,
        latitude: float,
        radius_meters: int,
    ) -> list[UnitOverlap]:
        """Return every DEGURBA unit overlapping a buffer, with metric areas.

        The buffer is built on the ``GEOGRAPHY`` point, so ``radius_meters`` is
        genuinely metres on the ground rather than a degree approximation.

        Raises:
            ValueError: If the radius is not a positive distance.
        """
        if radius_meters <= 0:
            raise ValueError(
                f"An exposure radius must be a positive distance, "
                f"got {radius_meters} m."
            )
        rows = (
            await self.session.execute(
                _OVERLAPS_FOR_POINT,
                {
                    "longitude": longitude,
                    "latitude": latitude,
                    "radius_meters": float(radius_meters),
                    "dug_level": ANALYSIS_DUG_LEVEL,
                },
            )
        ).all()
        return [to_unit_overlap(row) for row in rows]

    async def vulnerable_rates(self) -> dict[str, DistrictVulnerableRates]:
        """Return every district's vulnerable-group rates, keyed by district code.

        All three rates share one denominator: the district's published total
        resident population (``topic='poblacion'``), which reconciles exactly to
        the 5,922,921 georeferenced national figure. The age numerators come from
        the ``edad_sexo`` bands excluding the 88 cells withheld under statistical
        secrecy, so the age rates are marginally conservative -- 143 people
        nationally, 0.0024% -- rather than being inflated by a denominator that
        silently drops the same cells.

        The census publishes its own ``share`` beside the disability count, but
        against an unstated denominator that is about 96% of the resident
        population. It is deliberately not used as the multiplier: the rate here
        has to share a base with the DEGURBA population it multiplies.
        """
        rows = (
            await self.session.execute(
                _DISTRICT_VULNERABLE_RATES,
                {
                    "district_level": str(CensusLevel.DISTRITO),
                    "age_topic": AGE_STRUCTURE_TOPIC,
                    "disability_topic": DISABILITY_TOPIC,
                    "population_topic": POPULATION_TOPIC,
                    "population_category": POPULATION_TOTAL_CATEGORY,
                    "young_child_bands": list(YOUNG_CHILD_BANDS),
                    "older_adult_bands": list(OLDER_ADULT_BANDS),
                },
            )
        ).all()
        return {
            row.district_code: DistrictVulnerableRates(
                district_code=row.district_code,
                older_adult_rate=Decimal(str(row.older_adult_rate)),
                young_child_rate=Decimal(str(row.young_child_rate)),
                disability_rate=Decimal(str(row.disability_rate)),
            )
            for row in rows
        }


def to_unit_overlap(row: Any) -> UnitOverlap:
    """Map one row of :func:`overlaps_query_sql` to the domain record.

    Areas arrive as PostgreSQL ``double precision`` and are carried into Decimal
    through ``str`` so the ratio is a decimal division rather than inheriting
    binary floating-point noise into a published figure.
    """
    return UnitOverlap(
        unit_id=int(row.unit_id),
        district_code=str(row.district_code),
        population=int(row.population),
        unit_area_m2=Decimal(str(row.unit_area_m2)),
        overlap_area_m2=Decimal(str(row.overlap_area_m2)),
    )
