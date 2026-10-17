"""PostGIS repository adapter for idempotent census persistence.

Geometry is never stored as published. The cartography ships at full precision
(162 MB for DEGURBA, 164 MB for the segments), which makes any API serving it
unusable, so every polygon passes through one declared pipeline:

    GeoJSON -> SRID 4326 -> ST_SimplifyPreserveTopology -> ST_SnapToGrid(1e-6)
            -> ST_MakeValid -> ST_CollectionExtract(polygons) -> MULTIPOLYGON
            -> GEOGRAPHY

``ST_SimplifyPreserveTopology`` is used rather than ``ST_Simplify`` because a
collapsed boundary would silently move population across districts. The 1e-6
degree grid is roughly 11 cm, which is far below the positional accuracy of the
source and gives ~6-decimal coordinates. ``ST_MakeValid`` runs after snapping
because snapping can introduce self-intersections, and ``ST_CollectionExtract``
discards the degenerate lines and points ``ST_MakeValid`` may emit.

Every writer upserts on the natural key, so re-running an ingest is safe.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GEOMETRY_SIMPLIFY_TOLERANCE = 0.0001
"""Simplification tolerance in degrees (~11 m at the equator)."""

GEOMETRY_GRID_SIZE = 0.000001
"""Coordinate snapping grid in degrees (~11 cm), i.e. 6 decimal places."""

UPSERT_BATCH_SIZE = 500
"""Rows per executemany round-trip. Bounded so a 10k-row layer stays streamable."""


def simplified_geography_sql(source_expression: str) -> str:
    """Return the SQL expression that turns raw GeoJSON into a stored geography.

    Args:
        source_expression: SQL expression yielding the GeoJSON geometry text,
            typically a bind parameter such as ``:geom_json``.
    """
    return (
        "ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_SnapToGrid("
        "ST_SimplifyPreserveTopology("
        f"ST_SetSRID(ST_GeomFromGeoJSON({source_expression}), 4326), "
        f"{GEOMETRY_SIMPLIFY_TOLERANCE}), "
        f"{GEOMETRY_GRID_SIZE})), 3))::geography"
    )


_GEOM = simplified_geography_sql(":geom_json")

_UPSERT_ADMIN_UNIT = text(
    f"""
    INSERT INTO census_admin_unit
        (code, level, parent_code, name, iso_3166_2, geom, source)
    VALUES
        (CAST(:code AS text), CAST(:level AS text), CAST(:parent_code AS text),
         CAST(:name AS text), CAST(:iso_3166_2 AS text), {_GEOM},
         CAST(:source AS text))
    ON CONFLICT (code) DO UPDATE SET
        level = EXCLUDED.level,
        parent_code = EXCLUDED.parent_code,
        name = EXCLUDED.name,
        iso_3166_2 = EXCLUDED.iso_3166_2,
        geom = EXCLUDED.geom,
        source = EXCLUDED.source,
        ingested_at = now()
    """
)

_UPSERT_POPULATION_UNIT = text(
    f"""
    INSERT INTO census_population_unit
        (district_code, dug_level, dug_class, dug_code, population, households,
         dwellings, area_km2, density, geom, source)
    VALUES
        (CAST(:district_code AS text), CAST(:dug_level AS smallint),
         CAST(:dug_class AS text), CAST(:dug_code AS smallint),
         CAST(:population AS integer), CAST(:households AS integer),
         CAST(:dwellings AS integer), CAST(:area_km2 AS numeric),
         CAST(:density AS numeric), {_GEOM}, CAST(:source AS text))
    ON CONFLICT (district_code, dug_class, dug_level) DO UPDATE SET
        dug_code = EXCLUDED.dug_code,
        population = EXCLUDED.population,
        households = EXCLUDED.households,
        dwellings = EXCLUDED.dwellings,
        area_km2 = EXCLUDED.area_km2,
        density = EXCLUDED.density,
        geom = EXCLUDED.geom,
        source = EXCLUDED.source,
        ingested_at = now()
    """
)

_UPSERT_SEGMENT = text(
    f"""
    INSERT INTO census_segment
        (segment_code, district_code, area_type, area_km2, geom, source)
    VALUES
        (CAST(:segment_code AS text), CAST(:district_code AS text),
         CAST(:area_type AS text), CAST(:area_km2 AS numeric), {_GEOM},
         CAST(:source AS text))
    ON CONFLICT (segment_code) DO UPDATE SET
        district_code = EXCLUDED.district_code,
        area_type = EXCLUDED.area_type,
        area_km2 = EXCLUDED.area_km2,
        geom = EXCLUDED.geom,
        source = EXCLUDED.source,
        ingested_at = now()
    """
)

_UPSERT_INDICATOR = text(
    """
    INSERT INTO census_indicator
        (unit_code, unit_level, topic, category, sex, age_band, value, share,
         suppressed, source)
    VALUES
        (CAST(:unit_code AS text), CAST(:unit_level AS text),
         CAST(:topic AS text), CAST(:category AS text), CAST(:sex AS text),
         CAST(:age_band AS text), CAST(:value AS numeric),
         CAST(:share AS numeric), CAST(:suppressed AS boolean),
         CAST(:source AS text))
    ON CONFLICT (unit_code, unit_level, topic, category, sex, age_band)
    DO UPDATE SET
        value = EXCLUDED.value,
        share = EXCLUDED.share,
        suppressed = EXCLUDED.suppressed,
        source = EXCLUDED.source,
        ingested_at = now()
    """
)

_COUNT_BY_TABLE = {
    "census_admin_unit": text("SELECT count(*) FROM census_admin_unit"),
    "census_population_unit": text("SELECT count(*) FROM census_population_unit"),
    "census_indicator": text("SELECT count(*) FROM census_indicator"),
    "census_segment": text("SELECT count(*) FROM census_segment"),
}


@dataclass(slots=True)
class CensusLoadReport:
    """Row counts observed while loading one logical dataset."""

    dataset: str
    rows_read: int = 0
    rows_written: int = 0
    rows_skipped_sentinel: int = 0
    rows_suppressed: int = 0

    def __str__(self) -> str:
        """Return a single-line, log-friendly summary."""
        return (
            f"{self.dataset}: read={self.rows_read} written={self.rows_written} "
            f"sentinel_skipped={self.rows_skipped_sentinel} "
            f"suppressed={self.rows_suppressed}"
        )


class CensusRepository:
    """PostgreSQL + PostGIS repository for the CPV 2024 census corpus."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _upsert_batched(
        self,
        statement: Any,
        rows: Sequence[dict[str, Any]],
    ) -> int:
        """Execute one upsert statement over a row sequence in bounded batches."""
        if not rows:
            return 0
        for start in range(0, len(rows), UPSERT_BATCH_SIZE):
            batch = rows[start : start + UPSERT_BATCH_SIZE]
            await self.session.execute(statement, list(batch))
        await self.session.flush()
        return len(rows)

    async def upsert_admin_units(self, rows: Sequence[dict[str, Any]]) -> int:
        """Idempotently upsert administrative units keyed by their census code."""
        return await self._upsert_batched(_UPSERT_ADMIN_UNIT, rows)

    async def upsert_population_units(self, rows: Sequence[dict[str, Any]]) -> int:
        """Idempotently upsert DEGURBA population units keyed by district/class/level."""
        return await self._upsert_batched(_UPSERT_POPULATION_UNIT, rows)

    async def upsert_segments(self, rows: Sequence[dict[str, Any]]) -> int:
        """Idempotently upsert census segment polygons keyed by segment code."""
        return await self._upsert_batched(_UPSERT_SEGMENT, rows)

    async def upsert_indicators(self, rows: Sequence[dict[str, Any]]) -> int:
        """Idempotently upsert long-format indicator cells keyed by their full grain."""
        return await self._upsert_batched(_UPSERT_INDICATOR, rows)

    async def count_rows(self, table_name: str) -> int:
        """Return the live row count of one census table."""
        statement = _COUNT_BY_TABLE.get(table_name)
        if statement is None:
            raise KeyError(f"{table_name!r} is not a census table")
        return int((await self.session.execute(statement)).scalar_one())

    async def existing_admin_codes(self) -> set[str]:
        """Return every administrative code already stored, for referential checks."""
        result = await self.session.execute(text("SELECT code FROM census_admin_unit"))
        return set(result.scalars().all())

    async def georeferenced_population_total(self) -> int:
        """Return the population summed over DEGURBA units at the analysis level."""
        result = await self.session.execute(
            text(
                "SELECT COALESCE(sum(population), 0) FROM census_population_unit "
                "WHERE dug_level = :dug_level"
            ),
            {"dug_level": 2},
        )
        return int(result.scalar_one())
