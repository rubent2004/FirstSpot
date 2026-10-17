"""PostGIS reads for the LCC dimension: one raw estimate per variable per district.

This adapter only *reads*, and like its Vulnerability sibling it performs **no
arithmetic beyond summation**. Every ratio, percentile and score is computed in
:mod:`app.modules.prioritization.domain.coping`, so a published number is
auditable in one place rather than split between SQL and Python. The percentile
step in particular is kept out of SQL on purpose: a window function would hide
the tie rule, which is the one choice in the normalisation that materially
changes the ranking.

Three things in the query are not obvious and are load-bearing.

**The distances are already measured.** ``osm_unit_access`` is a cache written at
ingest time by
:class:`app.modules.ingestion.infrastructure.osm_coping_loader.OsmCopingLoader`.
Measured on the real corpus, recomputing it costs seconds; the V dimension
answers in about 100 ms, and LCC has to compose with it per request. The same
decision B4 made for ``census_unit_id``.

**Aggregation to district is population-weighted, and that is a declared rule.**
``sum(population * metres)`` over a district's DEGURBA polygons is person-metres,
and the domain divides it by the summed population. One distance from a district
centroid would have placed the measurement in an uninhabited mountain for exactly
the dispersed rural districts whose access is worst -- which is the population
this dimension exists to find.

**A missing polygon measurement withholds the district rather than counting as
zero.** ``sum`` over a NULL silently skips it in PostgreSQL, which would make a
district with one unmeasured polygon look closer to care than it is. The query
therefore counts the unmeasured polygons alongside the sum, and the mapping
refuses to publish a numerator when any of them is unmeasured.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.census.domain.geo_codes import CensusLevel
from app.modules.prioritization.domain.coping import (
    CopingVariableInput,
    DistrictCopingInput,
)

EXPECTED_DISTRICT_COUNT = 262
"""Districts of the post-D.L. 57/2023 structure, excluding the 'Otros' pseudo-unit.

Published secondary summaries routinely say 263 because they count the
geometry-less ``id_depto='15'`` row. The index refuses to run against a different
count rather than silently ranking a territory that does not exist, and rather
than publishing percentiles relative to a unit set nobody can reconstruct.
"""

ANALYSIS_DUG_LEVEL = 2
"""DEGURBA Nivel 2, the layer that carries real population and household figures."""

SHELTER_RATE_BASIS = 1000
"""Shelter density is published per 1,000 inhabitants rather than per person.

Per person the figure would be about 0.0003 and would round to zero in any
published decimal; the multiplier is cosmetic for the percentile (a monotone
rescale changes no rank) and material for whether a reader can read it.
"""


class CopingCorpusError(RuntimeError):
    """Raised when the corpus cannot support the LCC dimension."""


_DISTRICT_INPUTS = text(
    """
    WITH unit AS (
        SELECT u.district_code,
               u.population,
               a.geodesic_metres_to_nearest_health AS health_metres,
               a.geodesic_metres_to_nearest_road AS road_metres,
               a.geodesic_metres_to_nearest_fire_station AS fire_metres,
               a.area_m2,
               a.area_beyond_health_threshold_m2,
               a.area_beyond_road_threshold_m2,
               a.shelter_facility_count
        FROM census_population_unit u
        JOIN osm_unit_access a ON a.population_unit_id = u.id
        WHERE u.dug_level = CAST(:dug_level AS smallint)
    ),
    district AS (
        SELECT district_code,
               sum(population) AS population,
               -- Person-metres: the numerator E of each distance variable. The
               -- domain divides by the population to get metres per person.
               sum(population * health_metres) AS health_person_metres,
               sum(population * road_metres) AS road_person_metres,
               sum(population * fire_metres) AS fire_person_metres,
               -- A polygon whose distance could not be measured is counted, not
               -- skipped: sum() ignores NULL, which would understate the
               -- district's distance without leaving any trace.
               count(*) FILTER (WHERE health_metres IS NULL) AS health_unmeasured,
               count(*) FILTER (WHERE road_metres IS NULL) AS road_unmeasured,
               count(*) FILTER (WHERE fire_metres IS NULL) AS fire_unmeasured,
               -- Areal weighting under the uniform-density assumption declared
               -- in B4: the share of a polygon's land beyond the threshold is
               -- taken as the share of its people beyond the threshold.
               sum(
                   population
                   * area_beyond_health_threshold_m2
                   / NULLIF(area_m2, 0)
               ) AS population_beyond_health,
               sum(
                   population
                   * area_beyond_road_threshold_m2
                   / NULLIF(area_m2, 0)
               ) AS population_beyond_road,
               sum(shelter_facility_count) AS shelter_facilities
        FROM unit
        GROUP BY district_code
    )
    SELECT u.code AS district_code,
           u.name AS district_name,
           d.population,
           d.health_person_metres,
           d.road_person_metres,
           d.fire_person_metres,
           d.health_unmeasured,
           d.road_unmeasured,
           d.fire_unmeasured,
           d.population_beyond_health,
           d.population_beyond_road,
           d.shelter_facilities
    FROM census_admin_unit u
    JOIN district d ON d.district_code = u.code
    WHERE u.level = CAST(:district_level AS text)
      AND (
          CAST(:district_codes AS text[]) IS NULL
          OR u.code = ANY(CAST(:district_codes AS text[]))
      )
    ORDER BY u.code
    """
)

_UNIT_ACCESS = text(
    """
    SELECT u.id AS unit_id,
           u.district_code,
           a.name AS district_name,
           u.dug_level,
           u.dug_class,
           u.dug_code,
           u.population,
           acc.geodesic_metres_to_nearest_health,
           acc.geodesic_metres_to_nearest_road,
           acc.geodesic_metres_to_nearest_fire_station,
           acc.shelter_facility_count,
           acc.access_threshold_metres,
           acc.snapshot_date
    FROM census_population_unit u
    JOIN census_admin_unit a ON a.code = u.district_code
    JOIN osm_unit_access acc ON acc.population_unit_id = u.id
    WHERE u.dug_level = CAST(:dug_level AS smallint)
      -- Both sides are cast: an untyped bind parameter compared only against
      -- NULL leaves asyncpg unable to determine its type, which is the same
      -- failure the census loaders hit on `:param::text`.
      AND (
          CAST(:district_code AS text) IS NULL
          OR u.district_code = CAST(:district_code AS text)
      )
    ORDER BY u.district_code, u.id
    """
)


def _decimal(value: Any) -> Decimal | None:
    """Carry a database measure into Decimal without inheriting float noise."""
    if value is None:
        return None
    return Decimal(str(value))


def _measured(value: Any, unmeasured_units: Any) -> Decimal | None:
    """Return a weighted sum only when every polygon behind it was measured.

    A district with an unmeasured polygon gets ``None``, which the domain turns
    into a withheld score. The alternative -- publishing the sum over the
    polygons that happened to be measurable -- would report a shorter distance
    for a district precisely because part of it could not be reached by the
    measurement.
    """
    if int(unmeasured_units or 0) > 0:
        return None
    return _decimal(value)


def to_district_input(row: Any) -> DistrictCopingInput:
    """Map one query row onto the declared variable set of the LCC dimension.

    This is the single place where a cached measurement becomes a named index
    variable, so the mapping is reviewable in one screen rather than scattered
    across the SQL and the scorer.
    """
    population = _decimal(row.population)
    return DistrictCopingInput(
        district_code=str(row.district_code),
        district_name=str(row.district_name),
        population=int(population or 0),
        variables=(
            CopingVariableInput(
                variable="LCC_HEALTHDIST",
                numerator=_measured(
                    row.health_person_metres, row.health_unmeasured
                ),
                denominator=population,
            ),
            CopingVariableInput(
                variable="LCC_ROADDIST",
                numerator=_measured(row.road_person_metres, row.road_unmeasured),
                denominator=population,
            ),
            CopingVariableInput(
                variable="LCC_HEALTHFAR",
                numerator=_decimal(row.population_beyond_health),
                denominator=population,
            ),
            CopingVariableInput(
                variable="LCC_ROADFAR",
                numerator=_decimal(row.population_beyond_road),
                denominator=population,
            ),
            CopingVariableInput(
                variable="LCC_SHELTER",
                numerator=(
                    None
                    if row.shelter_facilities is None
                    else _decimal(row.shelter_facilities) * Decimal(SHELTER_RATE_BASIS)
                ),
                denominator=population,
            ),
            CopingVariableInput(
                variable="LCC_FIREDIST",
                numerator=_measured(row.fire_person_metres, row.fire_unmeasured),
                denominator=population,
            ),
        ),
    )


class CopingRepository:
    """Read-only adapter producing the LCC dimension's raw inputs per district."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def district_inputs(
        self,
        district_codes: Sequence[str] | None = None,
    ) -> list[DistrictCopingInput]:
        """Return one input record per district, in district-code order.

        Args:
            district_codes: Restrict the unit set. Exposed for tests and
                refused below unless it still covers every district, because a
                percentile over a subset is not comparable with a published
                score and would look identical in the payload.

        Raises:
            CopingCorpusError: If the corpus holds no access measurements, or a
                different number of districts than the verified 262.
        """
        rows = (
            await self.session.execute(
                _DISTRICT_INPUTS,
                {
                    "district_level": str(CensusLevel.DISTRITO),
                    "dug_level": ANALYSIS_DUG_LEVEL,
                    "district_codes": (
                        None if district_codes is None else list(district_codes)
                    ),
                },
            )
        ).all()
        if not rows:
            raise CopingCorpusError(
                "The OSM coping corpus holds no cached access measurements, so "
                "the Lack of Coping Capacity dimension cannot be computed. Run "
                "'just osm-ingest' first."
            )
        if len(rows) != EXPECTED_DISTRICT_COUNT:
            raise CopingCorpusError(
                f"Expected {EXPECTED_DISTRICT_COUNT} districts and found "
                f"{len(rows)}. A percentile rank is relative to its unit set, so "
                f"ranking against a different set would publish scores that are "
                f"not comparable with any other run of this index."
            )
        return [to_district_input(row) for row in rows]

    async def unit_access(
        self,
        district_code: str | None = None,
    ) -> Sequence[Any]:
        """Return the per-polygon access measurements behind a district figure.

        Geometry is deliberately not selected: the caller needs the measurement
        and the unit's identity, and the 162 MB of DEGURBA geometry is served by
        the existing cartography paths.
        """
        return (
            await self.session.execute(
                _UNIT_ACCESS,
                {
                    "dug_level": ANALYSIS_DUG_LEVEL,
                    "district_code": district_code,
                },
            )
        ).all()
