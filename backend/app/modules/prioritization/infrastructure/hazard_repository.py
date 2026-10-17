"""PostGIS zonal statistics of ShakeMap MMI bands over the census population units.

This adapter only *reads*, and like its V and LCC siblings it performs **no
arithmetic beyond summation and intersection**. Every rescale, mean and composed
score is computed in :mod:`app.modules.prioritization.domain.hazard`, so a
published number is auditable in one place rather than split between SQL and
Python.

Four things in the query are load-bearing and not obvious.

**The bands arrive as lines and PostGIS builds the areas.** ``cont_mi.json``
publishes MMI iso-lines, and ``ST_BuildArea`` turns a collection of closed rings
into an areal geometry with correct hole semantics. A hand-built
``MultiPolygon`` would treat a ring nested inside another ring of the same value
as a second solid polygon rather than as a hole, double-counting the area in
between. Verified on the 13 February 2001 event: every band from MMI 4 to MMI 7
builds a valid geometry and their areas nest monotonically, 18,852 km² down to
286 km².

**The bands are passed as a bind parameter, not stored.** There is no migration
and no table for them: the index recomputes per request exactly as V and LCC do,
and a ShakeMap grid is revised, so a cached band would be a stale hazard claim
with a fresh timestamp. The geometry the query *does* rely on being cached is the
census -- ``census_population_unit`` already holds simplified DEGURBA polygons.

**Area maths happens in EPSG:32616.** The declared metric projection of this
project, consistent with B4's areal weighting and C2's threshold areas. The
stored column is ``GEOGRAPHY`` on the WGS 84 datum, which UTM zone 16N shares, so
the transform needs no datum shift and no PROJ ballpark fallback. Measured in B4
on the westernmost DEGURBA unit -- the worst case for a zone centred on 87°W --
the areal weight differs from the geodesic weight by 1.5e-6 relative.

**A district the bands never touch returns a row with NULLs, not no row.** The
join to ``census_admin_unit`` is the outer side, so all 262 districts come back
and an unshaken district is published as a measured zero. Dropping it would
remove exactly the districts the event did not reach from a ranking whose job is
to say which districts it did.
"""

from collections.abc import Sequence
from decimal import Decimal
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.census.domain.geo_codes import CensusLevel
from app.modules.hazards.domain.shakemap import EXPOSURE_MMI_THRESHOLD, MmiBand
from app.modules.prioritization.domain.hazard import (
    DistrictHazardInput,
    HazardVariableInput,
)

EXPECTED_DISTRICT_COUNT = 262
"""Districts of the post-D.L. 57/2023 structure, excluding the 'Otros' pseudo-unit.

The hazard dimension takes no percentile, so it does not strictly *need* a closed
unit set the way V and LCC do. The count is still enforced, because a composed
PRIO index joins all three dimensions on district code and a partial hazard pass
would compose two dimensions against three for some districts and look identical
in the payload.
"""

ANALYSIS_DUG_LEVEL = 2
"""DEGURBA Nivel 2, the layer that carries real census population."""

METRIC_SRID = 32616
"""EPSG:32616, WGS 84 / UTM zone 16N. The project's declared metric projection."""

URBAN_DUG_CODE_FLOOR = 21
"""Lowest DEGURBA class code that is not rural.

The Degree of Urbanisation endorsed by the 51st UN Statistical Commission (2020)
groups 11, 12 and 13 as rural and 21, 22, 23 and 30 as towns, semi-dense areas
and cities. The split decides which Sphere shelter figure applies, 3.5 m² or
4.5 m² per person, and the grouping is the standard's rather than this project's.
"""


class HazardCorpusError(RuntimeError):
    """Raised when the corpus or the bands cannot support the H&E dimension."""


_DISTRICT_INPUTS = text(
    f"""
    WITH band AS (
        SELECT (b->>'mmi')::numeric AS mmi,
               ST_Transform(
                   ST_MakeValid(
                       ST_BuildArea(
                           ST_SetSRID(ST_GeomFromGeoJSON(b->'geometry'), 4326)
                       )
                   ),
                   {METRIC_SRID}
               ) AS metric
        FROM jsonb_array_elements(CAST(:bands AS jsonb)) AS b
    ),
    envelope AS (
        -- One bounding geometry over every band, so the index-backed prefilter
        -- below transforms only the polygons an event could possibly have
        -- reached. Measured on the real corpus this is what keeps the national
        -- pass in single-digit seconds rather than transforming all 902 units
        -- against all seven bands.
        SELECT ST_Envelope(ST_Collect(metric)) AS metric FROM band
    ),
    unit AS (
        SELECT u.id,
               u.district_code,
               u.population,
               u.dug_code,
               ST_Transform(u.geom::geometry, {METRIC_SRID}) AS metric
        FROM census_population_unit u
        WHERE u.dug_level = CAST(:dug_level AS smallint)
    ),
    candidate AS (
        SELECT u.*
        FROM unit u, envelope e
        WHERE ST_Intersects(u.metric, e.metric)
    ),
    measured AS (
        SELECT c.id,
               c.district_code,
               c.population,
               c.dug_code,
               ST_Area(c.metric) AS area_m2,
               max(b.mmi) AS max_mmi,
               -- The MMI >= threshold region is the area enclosed by the
               -- threshold contour, and the bands nest, so the largest
               -- intersection among the qualifying bands IS that area. max()
               -- rather than a filter on equality, so a ShakeMap that omits the
               -- exact threshold contour but draws a higher one still yields the
               -- conservative area it does publish.
               COALESCE(
                   max(ST_Area(ST_Intersection(c.metric, b.metric)))
                   FILTER (WHERE b.mmi >= CAST(:exposure_threshold AS numeric)),
                   0
               ) AS exposed_area_m2
        FROM candidate c
        JOIN band b ON ST_Intersects(c.metric, b.metric)
        GROUP BY c.id, c.district_code, c.population, c.dug_code, c.metric
    ),
    district AS (
        SELECT m.district_code,
               max(m.max_mmi) AS max_mmi,
               -- Person-MMI: the numerator E of the mean-intensity variable.
               -- The domain divides by the population to get mean MMI, mirroring
               -- the person-metres convention LCC established.
               sum(m.population * m.max_mmi) AS person_mmi,
               sum(m.population) FILTER (WHERE m.max_mmi IS NOT NULL)
                   AS shaken_population,
               -- Areal weighting under the uniform-density assumption declared
               -- in B4: the share of a polygon's land inside the band is taken
               -- as the share of its people inside the band.
               sum(
                   m.population * m.exposed_area_m2 / NULLIF(m.area_m2, 0)
               ) AS exposed_population,
               sum(
                   m.population * m.exposed_area_m2 / NULLIF(m.area_m2, 0)
               ) FILTER (
                   WHERE m.dug_code >= CAST(:urban_floor AS smallint)
               ) AS exposed_urban_population
        FROM measured m
        GROUP BY m.district_code
    ),
    resident AS (
        SELECT district_code, sum(population) AS population
        FROM census_population_unit
        WHERE dug_level = CAST(:dug_level AS smallint)
        GROUP BY district_code
    )
    SELECT a.code AS district_code,
           a.name AS district_name,
           r.population,
           d.max_mmi,
           d.person_mmi,
           d.shaken_population,
           d.exposed_population,
           d.exposed_urban_population
    FROM census_admin_unit a
    JOIN resident r ON r.district_code = a.code
    -- LEFT, so a district no band reached comes back with NULLs and is scored a
    -- measured zero rather than disappearing from the ranking.
    LEFT JOIN district d ON d.district_code = a.code
    WHERE a.level = CAST(:district_level AS text)
      AND (
          CAST(:district_codes AS text[]) IS NULL
          OR a.code = ANY(CAST(:district_codes AS text[]))
      )
    ORDER BY a.code
    """
)


def _decimal(value: Any) -> Decimal | None:
    """Carry a database measure into Decimal without inheriting float noise."""
    if value is None:
        return None
    return Decimal(str(value))


def to_district_input(row: Any) -> DistrictHazardInput:
    """Map one query row onto the declared variable set of the H&E dimension.

    This is the single place where a zonal measurement becomes a named index
    variable, so the mapping is reviewable in one screen rather than scattered
    across the SQL and the scorer.

    The two exposure variables deliberately share one numerator -- the same
    estimated exposed population -- and differ only in the universe they are
    divided by. ``HE_EXPABS`` has no universe because it is a log of a count, and
    ``HE_EXPREL`` divides by the district population to produce a share. Writing
    them from one value here is what guarantees the absolute and relative forms
    can never describe different populations.

    A district the bands never reached yields ``None`` for intensity -- never
    zero. Zero MMI would be a claim that the ground was measured and did not
    move; ``None`` carries "no band reached here", and the domain turns that into
    a measured score of 0 while recording ``shaken=False``.
    """
    population = _decimal(row.population) or Decimal(0)
    max_mmi = _decimal(row.max_mmi)
    exposed = _decimal(row.exposed_population) or Decimal(0)
    # Floating-point areal intersection overshoots a fully covered polygon by
    # ~1e-11 people. Clamp only that noise; a genuine excess is refused by the
    # domain.
    if population < exposed <= population + Decimal('0.001'):
        exposed = population
    # The mean is weighted by the population the bands actually covered, not by
    # the whole district: a polygon no band reached has no measured intensity,
    # and folding it in as a zero would report a mean below the Mercalli scale's
    # own floor for a district that was genuinely shaken in part.
    shaken_population = _decimal(row.shaken_population)
    return DistrictHazardInput(
        district_code=str(row.district_code),
        district_name=str(row.district_name),
        population=int(population),
        variables=(
            HazardVariableInput(
                variable="HE_MMIMAX", numerator=max_mmi, denominator=None
            ),
            HazardVariableInput(
                variable="HE_MMIMEAN",
                numerator=_decimal(row.person_mmi),
                denominator=shaken_population,
            ),
            HazardVariableInput(
                variable="HE_EXPABS", numerator=exposed, denominator=None
            ),
            HazardVariableInput(
                variable="HE_EXPREL", numerator=exposed, denominator=population
            ),
        ),
    )


def urban_exposure_share(row: Any) -> bool:
    """Return whether a district's exposed population is predominantly urban.

    Decides between Sphere's 3.5 m² and 4.5 m² shelter minimums. "Predominantly"
    is a strict majority of the exposed population in DEGURBA classes 21 and
    above; a tie falls to the lower figure, because 3.5 m² is the base standard
    and the raised figure applies only where internal services are the normal
    arrangement.
    """
    exposed = _decimal(row.exposed_population) or Decimal(0)
    urban = _decimal(row.exposed_urban_population) or Decimal(0)
    return exposed > 0 and urban > exposed / 2


class HazardRepository:
    """Read-only adapter producing the H&E dimension's raw inputs per district."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def district_inputs(
        self,
        bands: Sequence[MmiBand],
        district_codes: Sequence[str] | None = None,
    ) -> list[DistrictHazardInput]:
        """Return one input record per district for one set of MMI bands.

        Args:
            bands: The closed MMI bands of one ShakeMap release, from
                :func:`~app.modules.hazards.domain.shakemap.parse_mmi_bands`.
            district_codes: Restrict the unit set. Exposed for tests and refused
                below unless it still covers every district.

        Raises:
            HazardCorpusError: If the band set is empty, the census corpus holds
                no population units, or the query returns a different number of
                districts than the verified 262.
        """
        if not bands:
            raise HazardCorpusError(
                "No MMI band was supplied, so there is no modelled shaking to "
                "measure. An empty band set would score every district zero and "
                "be indistinguishable from an event that reached nobody, so it "
                "is refused here where the cause is still visible."
            )
        rows = await self._rows(bands, district_codes)
        if not rows:
            raise HazardCorpusError(
                "The census corpus holds no districts, so the Hazard & Exposure "
                "dimension cannot be computed. Run 'just census-ingest' first."
            )
        if len(rows) != EXPECTED_DISTRICT_COUNT:
            raise HazardCorpusError(
                f"Expected {EXPECTED_DISTRICT_COUNT} districts and found "
                f"{len(rows)}. All three PRIO dimensions join on district code, "
                f"so a partial hazard pass would compose two dimensions against "
                f"three for some districts while the payload looked identical."
            )
        return [to_district_input(row) for row in rows]

    async def district_context(
        self,
        bands: Sequence[MmiBand],
    ) -> dict[str, bool]:
        """Return, per district code, whether its exposed population is urban.

        Kept separate from :meth:`district_inputs` because it answers a Sphere
        question rather than an index question: no score depends on it, and only
        the shelter-area figure changes.
        """
        rows = await self._rows(bands, None)
        return {str(row.district_code): urban_exposure_share(row) for row in rows}

    async def _rows(
        self,
        bands: Sequence[MmiBand],
        district_codes: Sequence[str] | None,
    ) -> Sequence[Any]:
        """Run the zonal pass once for a band set."""
        payload = json.dumps(
            [
                {"mmi": str(band.mmi), "geometry": band.geometry}
                for band in bands
            ]
        )
        return (
            await self.session.execute(
                _DISTRICT_INPUTS,
                {
                    "bands": payload,
                    "dug_level": ANALYSIS_DUG_LEVEL,
                    "district_level": str(CensusLevel.DISTRITO),
                    "exposure_threshold": str(EXPOSURE_MMI_THRESHOLD),
                    "urban_floor": URBAN_DUG_CODE_FLOOR,
                    "district_codes": (
                        None if district_codes is None else list(district_codes)
                    ),
                },
            )
        ).all()
