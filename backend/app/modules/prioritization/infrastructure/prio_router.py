"""FastAPI adapters for the Hazard & Exposure dimension and the composed PRIO index.

Every composed response declares its ``mode`` (``baseline`` or ``event``), the
``dimension_keys`` it composed and, in event mode, the exact ShakeMap grid it was
computed against. A caller can never receive one mode without knowing which.

Endpoints
---------
``GET /prioritization/index/districts``
    Baseline (V x LCC) by default; event mode (H&E x V x LCC) when ``event_id``
    names a USGS earthquake with a ShakeMap.
``GET /prioritization/index/districts/{district_code}``
    One district with every dimension behind its composed score.
``GET /prioritization/hazard-exposure/districts``
    The H&E dimension alone for one event (``event_id`` required).
``GET /prioritization/hazard-exposure/events``
    The USGS earthquake catalogue around El Salvador.
"""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.privacy import CENSUS_SUPPRESSION_POLICY, STATISTICAL_SECRECY_REFERENCE
from app.modules.census.domain.geo_codes import CENSUS_SOURCE_ATTRIBUTION
from app.modules.hazards.domain.shakemap import (
    CASUALTY_REPORTING_PROHIBITION,
    PAGER_ALERT_BANDS,
    SHAKEMAP_REVISION_WARNING,
    USGS_ATTRIBUTION,
    ShakeMapError,
    ShakeMapRelease,
)
from app.modules.hazards.infrastructure.shakemap_client import (
    ShakeMapProviderError,
    ShakeMapProviderPort,
    UsgsShakeMapClient,
)
from app.modules.prioritization.domain.coping import COPING_DECLARED_GAPS
from app.modules.prioritization.domain.hazard import (
    CONTOUR_DISCRETISATION_RULE,
    FIXED_BOUNDS_RATIONALE,
    HAZARD_DECLARED_GAPS,
    HAZARD_DIMENSION_KEY,
    HAZARD_METHOD,
    HAZARD_SCORE_INTERPRETATION,
    HAZARD_VARIABLES,
    UNIFORM_DENSITY_ASSUMPTION,
    DistrictHazard,
)
from app.modules.prioritization.domain.prio import (
    CLASS_DISTRIBUTION_CAVEAT,
    DGPC_CLASS_BREAKS,
    DGPC_CLASS_SOURCE,
    ECOLOGICAL_FALLACY_WARNING,
    MAUP_WARNING,
    PRIO_COMPOSITION_RULE,
    PRIO_INDEX_INTERPRETATION,
    RESCALED_COMPOSITION_EXCLUSION,
    TRIAGE_COLOUR_ANALOGY_NOTE,
    DistrictPrio,
    PrioIndex,
    PrioMode,
)
from app.modules.prioritization.domain.vulnerability import DECLARED_GAPS as V_GAPS
from app.modules.prioritization.infrastructure.hazard_repository import (
    EXPECTED_DISTRICT_COUNT,
    HazardCorpusError,
)
from app.modules.prioritization.infrastructure.prio_repository import (
    PrioRepository,
    prio_event,
)

router = APIRouter(tags=["prioritization"])

_QUANTUM = Decimal(1).scaleb(-6)


def _p(value: Decimal | None) -> float | None:
    """Quantise a score for publication, preserving absence."""
    return None if value is None else float(value.quantize(_QUANTUM, rounding=ROUND_HALF_UP))


def get_shakemap_provider() -> ShakeMapProviderPort:
    """Dependency so tests and verification runs can substitute the provider."""
    return UsgsShakeMapClient()


class GapRead(BaseModel):
    dimension: str
    subject: str
    reason: str
    consequence: str


class AlertClassRead(BaseModel):
    alert_class: str = Field(description="DGPC alert level: verde, amarilla, naranja, roja.")
    floor: float
    ceiling: float
    inform_class: str
    meaning: str


class DimensionRead(BaseModel):
    dimension: str
    score: float | None
    rank: int | None
    withheld_reason: str | None = None


class SphereRead(BaseModel):
    label: str = Field(description="Always 'Sphere minimum requirement'.")
    exposed_population: int
    water_litres_per_day: int
    water_litres_per_day_extreme_heat: int
    water_taps_minimum: int
    water_point_maximum_distance_metres: int
    food_kcal_per_day: int
    shelter_area_m2: float
    shelter_basis: str
    population_basis: str
    caveat: str
    source: str


class DistrictPrioRead(BaseModel):
    district_code: str
    district_name: str
    population: int | None
    rank: int | None
    score: float | None = Field(description="Composed PRIO, 0-10, plain geometric mean.")
    inform_rescaled_score: float | None = Field(
        description="Audit only; read by no ranking, class or Sphere figure."
    )
    alert_class: str | None
    dimensions: list[DimensionRead]
    zeroed_by: list[str]
    zero_reason: str | None
    withheld: bool
    withheld_reason: str | None
    max_mmi: float | None
    estimated_exposed_population: int | None = Field(
        description="Estimated EXPOSED residents at MMI VI or above. Never a casualty count."
    )
    sphere: SphereRead | None = None


class PagerRead(BaseModel):
    level: str | None
    band_label: str | None
    response_implication: str | None


class EventRead(BaseModel):
    event_id: str
    magnitude: float | None
    place: str
    latitude: float
    longitude: float
    depth_km: float | None
    occurred_at: str
    shakemap_grid_processed_at: str | None = Field(
        description="ShakeMap is revised: every figure is valid only for this grid time."
    )
    shakemap_version: str | None
    shakemap_declared_max_mmi: float | None
    contour_max_mmi: float | None
    contour_interval: float | None
    pager: PagerRead | None = Field(
        description="PAGER alert level with its range, or null when the event has none."
    )


class PrioMethodologyRead(BaseModel):
    composition_rule: str
    rescaled_composition_exclusion: str
    percentile_floor_zero_meaning: str
    hazard_zero_meaning: str
    dgpc_class_source: str
    triage_colour_analogy: str
    class_distribution_caveat: str
    declared_scale: str
    interpretation: str
    uses_principal_components: bool = False
    scored_unit_count: int
    withheld_unit_count: int
    zeroed_by_hazard_count: int
    zeroed_by_percentile_floor_count: int
    suppression_threshold: int
    suppression_reference: str


class PrioIndexRead(BaseModel):
    mode: str = Field(description="'baseline' (V x LCC) or 'event' (H&E x V x LCC).")
    mode_meaning: str
    dimension_keys: list[str]
    event: EventRead | None
    districts: list[DistrictPrioRead]
    class_distribution: dict[str, int]
    alert_classes: list[AlertClassRead]
    total_exposed_population: int | None
    methodology: PrioMethodologyRead
    declared_gaps: list[GapRead]
    ecological_fallacy: str
    modifiable_areal_unit_problem: str
    casualty_reporting_prohibition: str
    shakemap_revision_warning: str
    source: str
    computed_at: datetime


class PrioIndexAuditRead(DistrictPrioRead):
    mode: str
    mode_meaning: str
    dimension_keys: list[str]
    event: EventRead | None
    methodology: PrioMethodologyRead
    declared_gaps: list[GapRead]
    ecological_fallacy: str
    modifiable_areal_unit_problem: str
    casualty_reporting_prohibition: str
    computed_at: datetime


class HazardVariableRead(BaseModel):
    variable: str
    label: str
    theme: str
    in_index: bool
    measure: str
    fixed_floor: float
    fixed_ceiling: float
    bound_source: str
    estimate: float | None = None
    universe: int | None = None
    rate: float | None = None
    score: float | None = None
    exclusion_reason: str | None = None


class DistrictHazardRead(BaseModel):
    district_code: str
    district_name: str
    population: int | None
    rank: int | None
    score: float
    shaken: bool
    max_mmi: float | None
    mean_mmi: float | None
    estimated_exposed_population: int
    themes: dict[str, float]
    variables: list[HazardVariableRead]


class HazardRankingRead(BaseModel):
    event: EventRead
    districts: list[DistrictHazardRead]
    scored_unit_count: int
    shaken_unit_count: int
    exposed_unit_count: int
    total_exposed_population: int
    method: str
    fixed_bounds_rationale: str
    contour_discretisation_rule: str
    uniform_density_assumption: str
    interpretation: str
    uses_percentile_normalisation: bool
    declared_gaps: list[GapRead]
    casualty_reporting_prohibition: str
    shakemap_revision_warning: str
    source: str
    computed_at: datetime


class EventSummaryRead(BaseModel):
    event_id: str
    magnitude: float | None
    place: str
    latitude: float
    longitude: float
    depth_km: float | None
    occurred_at: str
    has_shakemap: bool
    has_pager: bool
    url: str | None


class EventCatalogueRead(BaseModel):
    events: list[EventSummaryRead]
    pager_alert_bands: list[PagerRead]
    declared_gaps: list[GapRead]
    source: str


def _gaps(*, hazard: bool, v: bool, lcc: bool) -> list[GapRead]:
    out: list[GapRead] = []
    if hazard:
        out += [GapRead(dimension="hazard_and_exposure", subject=g.subject, reason=g.reason, consequence=g.consequence) for g in HAZARD_DECLARED_GAPS]
    if v:
        out += [GapRead(dimension="vulnerability", subject=g.subject, reason=g.reason, consequence=g.consequence) for g in V_GAPS]
    if lcc:
        out += [GapRead(dimension="lack_of_coping_capacity", subject=g.subject, reason=g.reason, consequence=g.consequence) for g in COPING_DECLARED_GAPS]
    return out


def _event(index_event) -> EventRead | None:  # type: ignore[no-untyped-def]
    if index_event is None:
        return None
    e = index_event
    f = lambda d: None if d is None else float(d)  # noqa: E731
    return EventRead(
        event_id=e.event_id, magnitude=f(e.magnitude), place=e.place,
        latitude=float(e.latitude), longitude=float(e.longitude), depth_km=f(e.depth_km),
        occurred_at=e.occurred_at_iso, shakemap_grid_processed_at=e.grid_processed_at_iso,
        shakemap_version=e.shakemap_version, shakemap_declared_max_mmi=f(e.shakemap_declared_max_mmi),
        contour_max_mmi=f(e.contour_max_mmi), contour_interval=f(e.contour_interval),
        pager=(
            PagerRead(level=e.pager_level, band_label=e.pager_band_label,
                      response_implication=e.pager_response_implication)
            if e.pager_level else None
        ),
    )


def _district(d: DistrictPrio) -> DistrictPrioRead:
    s = d.sphere
    return DistrictPrioRead(
        district_code=d.district_code, district_name=d.district_name, population=d.population,
        rank=d.rank, score=_p(d.score), inform_rescaled_score=_p(d.inform_rescaled_score),
        alert_class=d.alert_class.value if d.alert_class else None,
        dimensions=[DimensionRead(dimension=x.dimension, score=_p(x.score), rank=x.rank, withheld_reason=x.withheld_reason) for x in d.dimensions],
        zeroed_by=list(d.zeroed_by), zero_reason=d.zero_reason, withheld=d.withheld,
        withheld_reason=d.withheld_reason,
        max_mmi=None if d.max_mmi is None else float(d.max_mmi),
        estimated_exposed_population=d.estimated_exposed_population,
        sphere=None if s is None else SphereRead(
            label=s.label, exposed_population=s.exposed_population,
            water_litres_per_day=s.water_litres_per_day,
            water_litres_per_day_extreme_heat=s.water_litres_per_day_extreme_heat,
            water_taps_minimum=s.water_taps_minimum,
            water_point_maximum_distance_metres=s.water_point_maximum_distance_metres,
            food_kcal_per_day=s.food_kcal_per_day, shelter_area_m2=float(s.shelter_area_m2),
            shelter_basis=s.shelter_basis, population_basis=s.population_basis,
            caveat=s.caveat, source=s.source,
        ),
    )


def _methodology(index: PrioIndex) -> PrioMethodologyRead:
    return PrioMethodologyRead(
        composition_rule=index.composition_rule,
        rescaled_composition_exclusion=index.rescaled_composition_exclusion,
        percentile_floor_zero_meaning=index.percentile_floor_zero_meaning,
        hazard_zero_meaning=index.hazard_zero_meaning,
        dgpc_class_source=index.dgpc_class_source,
        triage_colour_analogy=index.triage_colour_analogy,
        class_distribution_caveat=index.class_distribution_caveat,
        declared_scale=index.declared_scale, interpretation=index.interpretation,
        scored_unit_count=index.scored_unit_count, withheld_unit_count=index.withheld_unit_count,
        zeroed_by_hazard_count=index.zeroed_by_hazard_count,
        zeroed_by_percentile_floor_count=index.zeroed_by_percentile_floor_count,
        suppression_threshold=CENSUS_SUPPRESSION_POLICY.minimum_units,
        suppression_reference=STATISTICAL_SECRECY_REFERENCE,
    )


async def _release(provider: ShakeMapProviderPort, event_id: str) -> ShakeMapRelease:
    try:
        return await provider.fetch_release(event_id)
    except ShakeMapError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ShakeMapProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


async def _index(
    session: AsyncSession, provider: ShakeMapProviderPort, event_id: str | None
) -> PrioIndex:
    repo = PrioRepository(session)
    try:
        if event_id is None:
            return await repo.baseline_index()
        return await repo.event_index(await _release(provider, event_id))
    except HazardCorpusError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


EventIdQuery = Annotated[
    str | None,
    Query(
        description=(
            "USGS event id (e.g. usp000a9jv). Omit for BASELINE mode (V x LCC, no "
            "event). Supply it for EVENT mode (H&E x V x LCC) against that event's "
            "ShakeMap."
        )
    ),
]


@router.get(
    "/prioritization/index/districts",
    response_model=PrioIndexRead,
    operation_id="listDistrictPrioIndex",
    summary="Rank every district by the composed PRIO-SV index (baseline or event)",
)
async def list_district_prio_index(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    provider: Annotated[ShakeMapProviderPort, Depends(get_shakemap_provider)],
    event_id: EventIdQuery = None,
) -> PrioIndexRead:
    """Composed PRIO-SV ranking. The response always declares its mode.

    Baseline answers "where would a disaster hurt most"; event answers "who to
    attend first" for one ShakeMap grid. Sphere minimum requirements are
    attached to naranja and roja districts in event mode. No figure is a
    casualty count, and the ranking is of territories, not people.
    """
    index = await _index(session, provider, event_id)
    return PrioIndexRead(
        mode=index.mode.value, mode_meaning=index.mode_meaning,
        dimension_keys=list(index.dimension_keys), event=_event(index.event),
        districts=[_district(d) for d in index.districts],
        class_distribution={k.value: v for k, v in index.class_distribution.items()},
        alert_classes=[
            AlertClassRead(alert_class=b.alert_class.value, floor=float(b.floor), ceiling=float(b.ceiling), inform_class=b.inform_class, meaning=b.meaning)
            for b in DGPC_CLASS_BREAKS
        ],
        total_exposed_population=index.total_exposed_population,
        methodology=_methodology(index),
        declared_gaps=_gaps(hazard=index.mode is PrioMode.EVENT, v=True, lcc=True),
        ecological_fallacy=ECOLOGICAL_FALLACY_WARNING,
        modifiable_areal_unit_problem=MAUP_WARNING,
        casualty_reporting_prohibition=CASUALTY_REPORTING_PROHIBITION,
        shakemap_revision_warning=SHAKEMAP_REVISION_WARNING,
        source=f"{CENSUS_SOURCE_ATTRIBUTION}; {USGS_ATTRIBUTION}",
        computed_at=datetime.now(timezone.utc),
    )


@router.get(
    "/prioritization/index/districts/{district_code}",
    response_model=PrioIndexAuditRead,
    operation_id="getDistrictPrioIndexAudit",
    summary="Retrieve every dimension behind one district's composed PRIO score",
)
async def get_district_prio_index_audit(
    district_code: Annotated[str, Path(min_length=6, max_length=6)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    provider: Annotated[ShakeMapProviderPort, Depends(get_shakemap_provider)],
    event_id: EventIdQuery = None,
) -> PrioIndexAuditRead:
    """One district with its dimension scores, zero attribution and Sphere figure."""
    index = await _index(session, provider, event_id)
    district = next((d for d in index.districts if d.district_code == district_code), None)
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"District {district_code} is not one of the {EXPECTED_DISTRICT_COUNT} districts.",
        )
    return PrioIndexAuditRead(
        **_district(district).model_dump(),
        mode=index.mode.value, mode_meaning=index.mode_meaning,
        dimension_keys=list(index.dimension_keys), event=_event(index.event),
        methodology=_methodology(index),
        declared_gaps=_gaps(hazard=index.mode is PrioMode.EVENT, v=True, lcc=True),
        ecological_fallacy=ECOLOGICAL_FALLACY_WARNING,
        modifiable_areal_unit_problem=MAUP_WARNING,
        casualty_reporting_prohibition=CASUALTY_REPORTING_PROHIBITION,
        computed_at=datetime.now(timezone.utc),
    )


def _hazard_district(d: DistrictHazard) -> DistrictHazardRead:
    by_key = {v.key: v for v in HAZARD_VARIABLES}
    f = lambda x: None if x is None else float(x)  # noqa: E731
    return DistrictHazardRead(
        district_code=d.district_code, district_name=d.district_name, population=d.population,
        rank=d.rank, score=_p(d.score) or 0.0, shaken=d.shaken, max_mmi=f(d.max_mmi),
        mean_mmi=_p(d.mean_mmi), estimated_exposed_population=d.estimated_exposed_population,
        themes={t.theme: _p(t.score) or 0.0 for t in d.themes},
        variables=[
            HazardVariableRead(
                variable=v.variable, label=by_key[v.variable].label, theme=by_key[v.variable].theme,
                in_index=v.in_index, measure=by_key[v.variable].measure,
                fixed_floor=float(v.fixed_floor), fixed_ceiling=float(v.fixed_ceiling),
                bound_source=by_key[v.variable].bound_source, estimate=_p(v.estimate),
                universe=v.universe, rate=_p(v.rate), score=_p(v.score),
                exclusion_reason=by_key[v.variable].exclusion_reason,
            )
            for v in d.variables
        ],
    )


@router.get(
    "/prioritization/hazard-exposure/districts",
    response_model=HazardRankingRead,
    operation_id="listDistrictHazardExposure",
    summary="Rank districts by the Hazard & Exposure dimension for one earthquake",
)
async def list_district_hazard_exposure(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    provider: Annotated[ShakeMapProviderPort, Depends(get_shakemap_provider)],
    event_id: Annotated[str, Query(description="USGS event id with a ShakeMap.")],
) -> HazardRankingRead:
    """H&E alone: fixed-bound MMI intensity and exposed population (MMI >= VI)."""
    release = await _release(provider, event_id)
    try:
        ranking = await PrioRepository(session).hazard(release)
    except HazardCorpusError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return HazardRankingRead(
        event=_event(prio_event(release)),  # type: ignore[arg-type]
        districts=[_hazard_district(d) for d in ranking.districts],
        scored_unit_count=ranking.scored_unit_count, shaken_unit_count=ranking.shaken_unit_count,
        exposed_unit_count=ranking.exposed_unit_count,
        total_exposed_population=ranking.total_exposed_population,
        method=HAZARD_METHOD, fixed_bounds_rationale=FIXED_BOUNDS_RATIONALE,
        contour_discretisation_rule=CONTOUR_DISCRETISATION_RULE,
        uniform_density_assumption=UNIFORM_DENSITY_ASSUMPTION,
        interpretation=HAZARD_SCORE_INTERPRETATION,
        uses_percentile_normalisation=False,
        declared_gaps=_gaps(hazard=True, v=False, lcc=False),
        casualty_reporting_prohibition=CASUALTY_REPORTING_PROHIBITION,
        shakemap_revision_warning=SHAKEMAP_REVISION_WARNING,
        source=USGS_ATTRIBUTION, computed_at=datetime.now(timezone.utc),
    )


@router.get(
    "/prioritization/hazard-exposure/events",
    response_model=EventCatalogueRead,
    operation_id="listHazardExposureEvents",
    summary="List USGS earthquakes around El Salvador and whether each has a ShakeMap",
)
async def list_hazard_exposure_events(
    provider: Annotated[ShakeMapProviderPort, Depends(get_shakemap_provider)],
    min_magnitude: Annotated[float, Query(ge=0, le=10)] = 4.0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    start_time: Annotated[str | None, Query(description="ISO date, e.g. 2001-01-01.")] = None,
) -> EventCatalogueRead:
    """Catalogue of candidate events. Flood (GDACS) is a declared gap, not absent."""
    try:
        events = await provider.list_events(min_magnitude, limit, start_time)
    except ShakeMapProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return EventCatalogueRead(
        events=[
            EventSummaryRead(
                event_id=e.event_id, magnitude=None if e.magnitude is None else float(e.magnitude),
                place=e.place, latitude=float(e.latitude), longitude=float(e.longitude),
                depth_km=None if e.depth_km is None else float(e.depth_km),
                occurred_at=e.occurred_at.isoformat(), has_shakemap=e.has_shakemap,
                has_pager=e.has_pager, url=e.url,
            )
            for e in events
        ],
        pager_alert_bands=[PagerRead(level=b.level, band_label=b.label, response_implication=b.response_implication) for b in PAGER_ALERT_BANDS],
        declared_gaps=_gaps(hazard=True, v=False, lcc=False),
        source=USGS_ATTRIBUTION,
    )
