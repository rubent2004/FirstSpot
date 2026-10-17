"""Cached attachment of vulnerable places to census units, plus exposure refresh.

Two caches live on ``vulnerable_places`` and both are written here, never
derived per request:

``census_unit_id``
    Which DEGURBA population unit contains the place. Resolved with
    ``ST_Intersects`` and stored, because the dispatch queue reads it on every
    row of every poll and a per-query spatial join over 902 multipolygons is not
    something to pay for repeatedly.
``estimated_exposed_*`` and ``exposure_radius_meters``
    The areal-weighted exposure estimate at the declared default radius.
    Measured on the ingested corpus, the whole-table recomputation takes about
    1.3 s; serving that per list request would make the queue sluggish for a
    number that only changes when places or census data change.

An arbitrary radius is still available on demand through
:class:`app.modules.census.infrastructure.exposure_repository.CensusExposureRepository`,
which costs about 40 ms for one place.

Both passes are idempotent: re-running them writes nothing when nothing moved.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import CENSUS_SUPPRESSION_POLICY, SuppressionPolicy
from app.modules.census.domain.exposure import (
    DEFAULT_EXPOSURE_RADIUS_METERS,
    ExposedPopulationEstimate,
    UnitOverlap,
    estimate_exposed_population,
)
from app.modules.census.infrastructure.exposure_repository import (
    ANALYSIS_DUG_LEVEL,
    UNIT_IN_BUFFER_SQL,
    CensusExposureRepository,
    overlaps_query_sql,
    to_unit_overlap,
)

UPDATE_BATCH_SIZE = 500
"""Rows per executemany round-trip, matching the census ingestion convention."""

_PLACE_BUFFER_SOURCE = """
        SELECT p.id AS place_id,
               ST_Buffer(p.location,
                         CAST(:radius_meters AS double precision))::geometry
                   AS buffer_geom
        FROM vulnerable_places p
        WHERE CAST(:zone_name AS text) IS NULL
           OR lower(p.zone_name) = lower(CAST(:zone_name AS text))
"""

_OVERLAPS_FOR_PLACES = text(
    overlaps_query_sql(_PLACE_BUFFER_SOURCE, key_columns=("place_id",))
)

# Attachment runs before detachment so a place that moved between units is
# re-pointed in one statement instead of being nulled and then re-attached.
_ATTACH_PLACES = text(
    f"""
    UPDATE vulnerable_places p
    SET census_unit_id = resolved.unit_id
    FROM (
        SELECT DISTINCT ON (candidate.id)
               candidate.id AS place_id,
               u.id AS unit_id
        FROM vulnerable_places candidate
        JOIN census_population_unit u
          ON {UNIT_IN_BUFFER_SQL.format(buffer="candidate.location::geometry")}
        WHERE CAST(:zone_name AS text) IS NULL
           OR lower(candidate.zone_name) = lower(CAST(:zone_name AS text))
        ORDER BY candidate.id, u.id
    ) AS resolved
    WHERE p.id = resolved.place_id
      AND p.census_unit_id IS DISTINCT FROM resolved.unit_id
    """
)

_DETACH_PLACES = text(
    """
    UPDATE vulnerable_places p
    SET census_unit_id = NULL
    WHERE p.census_unit_id IS NOT NULL
      AND (CAST(:zone_name AS text) IS NULL
           OR lower(p.zone_name) = lower(CAST(:zone_name AS text)))
      AND NOT EXISTS (
          SELECT 1
          FROM census_population_unit u
          WHERE u.id = p.census_unit_id
            AND ST_Intersects(u.geom::geometry, p.location::geometry)
      )
    """
)

_COUNT_UNATTACHED = text(
    """
    SELECT count(*)
    FROM vulnerable_places p
    WHERE p.census_unit_id IS NULL
      AND (CAST(:zone_name AS text) IS NULL
           OR lower(p.zone_name) = lower(CAST(:zone_name AS text)))
    """
)

_SELECT_PLACE_IDS = text(
    """
    SELECT p.id
    FROM vulnerable_places p
    WHERE CAST(:zone_name AS text) IS NULL
       OR lower(p.zone_name) = lower(CAST(:zone_name AS text))
    """
)

_WRITE_EXPOSURE = text(
    """
    UPDATE vulnerable_places
    SET exposure_radius_meters = CAST(:radius_meters AS integer),
        estimated_exposed_population = CAST(:population AS integer),
        estimated_exposed_older_adults = CAST(:older_adults AS integer),
        estimated_exposed_young_children = CAST(:young_children AS integer),
        estimated_exposed_persons_with_disability = CAST(:with_disability AS integer),
        exposure_estimated_at = CAST(:estimated_at AS timestamptz)
    WHERE id = CAST(:place_id AS uuid)
    """
)


@dataclass(slots=True)
class AttachmentReport:
    """What one attachment pass changed. All zeros means nothing moved."""

    attached: int = 0
    detached: int = 0
    unattached: int = 0

    def __str__(self) -> str:
        """Return a single-line, log-friendly summary."""
        return (
            f"attachment: attached={self.attached} detached={self.detached} "
            f"outside_census_coverage={self.unattached}"
        )


@dataclass(slots=True)
class ExposureRefreshReport:
    """What one exposure refresh wrote, and how much of it had to be withheld."""

    radius_meters: int
    places_written: int = 0
    places_withheld: int = 0
    places_without_census_coverage: int = 0
    contributions: int = 0

    def __str__(self) -> str:
        """Return a single-line, log-friendly summary."""
        return (
            f"exposure@{self.radius_meters}m: estimated={self.places_written} "
            f"withheld={self.places_withheld} "
            f"outside_census_coverage={self.places_without_census_coverage} "
            f"unit_contributions={self.contributions}"
        )


class PlaceCensusAttachmentRepository:
    """Writes the cached census attachment and exposure estimates onto places."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.census = CensusExposureRepository(session)

    async def attach_places_to_census_units(
        self,
        zone_name: str | None = None,
        commit: bool = True,
    ) -> AttachmentReport:
        """Resolve and cache each place's containing DEGURBA unit.

        The spatial rule is plain ``ST_Intersects`` containment of the place's
        point. Where a point somehow falls in two units -- possible only along a
        shared boundary after simplification -- the lowest unit id wins, so the
        result is deterministic rather than dependent on scan order.

        A place that intersects no unit is left with ``census_unit_id`` NULL and
        is **never** snapped to the nearest unit. On the current corpus the 56
        unattached places sit in Escuintla, Guatemala, 87 km from the nearest
        Salvadoran census unit; snapping them would invent a territory for them.

        Args:
            zone_name: Restrict the pass to one zone. ``None`` processes every place.
            commit: Whether to commit, so a caller inside a larger transaction can
                defer.
        """
        parameters = {"zone_name": zone_name, "dug_level": ANALYSIS_DUG_LEVEL}
        attached = (await self.session.execute(_ATTACH_PLACES, parameters)).rowcount
        detached = (
            await self.session.execute(_DETACH_PLACES, {"zone_name": zone_name})
        ).rowcount
        unattached = (
            await self.session.execute(_COUNT_UNATTACHED, {"zone_name": zone_name})
        ).scalar_one()
        await self.session.flush()
        if commit:
            await self.session.commit()
        return AttachmentReport(
            attached=int(attached or 0),
            detached=int(detached or 0),
            unattached=int(unattached or 0),
        )

    async def refresh_exposure_estimates(
        self,
        radius_meters: int = DEFAULT_EXPOSURE_RADIUS_METERS,
        zone_name: str | None = None,
        policy: SuppressionPolicy = CENSUS_SUPPRESSION_POLICY,
        commit: bool = True,
    ) -> ExposureRefreshReport:
        """Recompute and cache the areal-weighted exposure estimate for each place.

        The overlaps are fetched for every place in one set-based statement, the
        arithmetic and the disclosure screening happen in the domain layer, and
        the results are written back in bounded batches.

        A place whose buffer overlaps no population unit is written as *unknown*
        (NULL), not as zero: the DEGURBA layer tiles El Salvador, so an empty
        overlap set means the place lies outside census coverage altogether, and
        "no census data" is not the same claim as "nobody lives here".

        Args:
            radius_meters: Radius the cached estimate applies to, stored alongside it.
            zone_name: Restrict the pass to one zone. ``None`` processes every place.
            policy: Disclosure policy applied before any figure is stored.
            commit: Whether to commit, so a caller inside a larger transaction can
                defer.
        """
        overlaps_by_place = await self._overlaps_by_place(radius_meters, zone_name)
        rates = await self.census.vulnerable_rates()
        place_ids = (
            (await self.session.execute(_SELECT_PLACE_IDS, {"zone_name": zone_name}))
            .scalars()
            .all()
        )

        report = ExposureRefreshReport(radius_meters=radius_meters)
        rows: list[dict[str, Any]] = []
        for place_id in place_ids:
            overlaps = overlaps_by_place.get(place_id, [])
            report.contributions += len(overlaps)
            if not overlaps:
                report.places_without_census_coverage += 1
                rows.append(_unknown_exposure_row(place_id, radius_meters))
                continue
            estimate = estimate_exposed_population(
                overlaps=overlaps,
                rates_by_district=rates,
                radius_meters=radius_meters,
                policy=policy,
            )
            if estimate.estimated_exposed_population is None:
                report.places_withheld += 1
            else:
                report.places_written += 1
            rows.append(_exposure_row(place_id, estimate))

        await self._write_batched(rows)
        if commit:
            await self.session.commit()
        return report

    async def _overlaps_by_place(
        self,
        radius_meters: int,
        zone_name: str | None,
    ) -> dict[uuid.UUID, list[UnitOverlap]]:
        """Group every place's buffer overlaps from one set-based statement."""
        if radius_meters <= 0:
            raise ValueError(
                f"An exposure radius must be a positive distance, "
                f"got {radius_meters} m."
            )
        result = await self.session.execute(
            _OVERLAPS_FOR_PLACES,
            {
                "radius_meters": float(radius_meters),
                "dug_level": ANALYSIS_DUG_LEVEL,
                "zone_name": zone_name,
            },
        )
        grouped: dict[uuid.UUID, list[UnitOverlap]] = {}
        for row in result.all():
            grouped.setdefault(row.place_id, []).append(to_unit_overlap(row))
        return grouped

    async def _write_batched(self, rows: Sequence[dict[str, Any]]) -> int:
        """Write exposure estimates back in bounded executemany batches."""
        if not rows:
            return 0
        for start in range(0, len(rows), UPDATE_BATCH_SIZE):
            batch = rows[start : start + UPDATE_BATCH_SIZE]
            await self.session.execute(_WRITE_EXPOSURE, list(batch))
        await self.session.flush()
        return len(rows)

def _exposure_row(
    place_id: uuid.UUID,
    estimate: ExposedPopulationEstimate,
) -> dict[str, Any]:
    """Map a screened estimate to the cache row that will be written."""
    return {
        "place_id": str(place_id),
        "radius_meters": estimate.radius_meters,
        "population": estimate.estimated_exposed_population,
        "older_adults": estimate.estimated_exposed_older_adults,
        "young_children": estimate.estimated_exposed_young_children,
        "with_disability": estimate.estimated_exposed_persons_with_disability,
        "estimated_at": datetime.now(timezone.utc),
    }


def _unknown_exposure_row(place_id: uuid.UUID, radius_meters: int) -> dict[str, Any]:
    """Map a place outside census coverage to an explicitly unknown estimate."""
    return {
        "place_id": str(place_id),
        "radius_meters": radius_meters,
        "population": None,
        "older_adults": None,
        "young_children": None,
        "with_disability": None,
        "estimated_at": datetime.now(timezone.utc),
    }


