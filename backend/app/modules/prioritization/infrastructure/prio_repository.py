"""Composition of the three dimensions into baseline and event PRIO indexes.

Reads nothing itself: it calls the three dimension repositories and scorers and
hands their scores to :func:`build_prio_index`, so every composed number is
reducible to a dimension that already publishes its own audit trail.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hazards.domain.shakemap import ShakeMapRelease
from app.modules.prioritization.domain.coping import (
    LCC_DIMENSION_KEY,
    CopingRanking,
    score_coping,
)
from app.modules.prioritization.domain.hazard import (
    HAZARD_DIMENSION_KEY,
    HazardRanking,
    score_hazard,
)
from app.modules.prioritization.domain.prio import (
    DimensionScore,
    PrioEvent,
    PrioIndex,
    PrioMode,
    build_prio_index,
)
from app.modules.prioritization.domain.vulnerability import (
    DIMENSION_KEY,
    VulnerabilityRanking,
    score_vulnerability,
)
from app.modules.prioritization.infrastructure.coping_repository import CopingRepository
from app.modules.prioritization.infrastructure.hazard_repository import HazardRepository
from app.modules.prioritization.infrastructure.vulnerability_repository import (
    VulnerabilityRepository,
)


def prio_event(release: ShakeMapRelease) -> PrioEvent:
    """Stamp an event index with the exact ShakeMap grid it was computed from."""
    pager = release.pager
    return PrioEvent(
        event_id=release.event_id,
        magnitude=release.magnitude,
        place=release.place,
        latitude=release.latitude,
        longitude=release.longitude,
        depth_km=release.depth_km,
        occurred_at_iso=release.occurred_at.isoformat(),
        grid_processed_at_iso=(
            release.grid_processed_at.isoformat() if release.grid_processed_at else None
        ),
        shakemap_version=release.version,
        shakemap_declared_max_mmi=release.declared_max_mmi,
        contour_max_mmi=release.contour_max_mmi,
        contour_interval=release.contour_interval,
        pager_level=pager.level if pager else None,
        pager_band_label=pager.band_label if pager else None,
        pager_response_implication=pager.response_implication if pager else None,
    )


class PrioRepository:
    """Computes composed indexes; recomputed per request like V and LCC."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def vulnerability(self) -> VulnerabilityRanking:
        return score_vulnerability(await VulnerabilityRepository(self.session).district_inputs())

    async def coping(self) -> CopingRanking:
        return score_coping(await CopingRepository(self.session).district_inputs())

    async def hazard(self, release: ShakeMapRelease) -> HazardRanking:
        return score_hazard(
            await HazardRepository(self.session).district_inputs(release.bands)
        )

    async def baseline_index(self) -> PrioIndex:
        v = {d.district_code: d for d in (await self.vulnerability()).districts}
        l = {d.district_code: d for d in (await self.coping()).districts}
        rows = [
            (
                code,
                v[code].district_name,
                v[code].population,
                (
                    DimensionScore(DIMENSION_KEY, v[code].score, v[code].rank, v[code].withheld_reason),
                    DimensionScore(LCC_DIMENSION_KEY, l[code].score, l[code].rank, l[code].withheld_reason),
                ),
            )
            for code in sorted(v)
        ]
        return build_prio_index(PrioMode.BASELINE, rows)

    async def event_index(self, release: ShakeMapRelease) -> PrioIndex:
        v = {d.district_code: d for d in (await self.vulnerability()).districts}
        l = {d.district_code: d for d in (await self.coping()).districts}
        h = {d.district_code: d for d in (await self.hazard(release)).districts}
        urban = await HazardRepository(self.session).district_context(release.bands)
        rows = [
            (
                code,
                v[code].district_name,
                v[code].population,
                (
                    DimensionScore(HAZARD_DIMENSION_KEY, h[code].score, h[code].rank),
                    DimensionScore(DIMENSION_KEY, v[code].score, v[code].rank, v[code].withheld_reason),
                    DimensionScore(LCC_DIMENSION_KEY, l[code].score, l[code].rank, l[code].withheld_reason),
                ),
            )
            for code in sorted(v)
        ]
        return build_prio_index(
            PrioMode.EVENT,
            rows,
            event=prio_event(release),
            exposed_population={c: d.estimated_exposed_population for c, d in h.items()},
            max_mmi={c: d.max_mmi for c, d in h.items()},
            urban_exposure=urban,
        )
