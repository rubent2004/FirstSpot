"""FastAPI adapters and Pydantic v2 schemas for the PRIO-SV LCC dimension.

Three endpoints, and the division between them is about auditability rather than
convenience, mirroring the Vulnerability router exactly:

``GET /prioritization/coping-capacity/districts``
    The ranked list a responder reads, with the methodology, the unit count the
    percentiles are relative to, the distance basis and every declared gap.
``GET /prioritization/coping-capacity/districts/{district_code}``
    The whole chain behind one score: each variable's ``E``, ``EP`` and ``EPL``,
    each theme's ``SPL`` and ``RPL``, and both composition rules. **An
    unexplainable score is useless in front of a jury**, so this exists to make
    any published score reducible to its inputs in one request.
``GET /prioritization/coping-capacity/population-units``
    The per-polygon measurements the district figure is the population-weighted
    mean of. This endpoint has no counterpart in V and exists because LCC's
    district figure *averages a real spread*: a district whose urban core sits
    400 m from a clinic and whose rural fringe sits 12 km away publishes one
    number, and an operator deciding where to send a brigade needs the spread.

Every response carries
:data:`~app.modules.prioritization.domain.coping.DISTANCE_BASIS` as a top-level
field, not buried in the methodology block. That placement is deliberate: these
are geodesic straight-line metres and a **lower bound on travel distance**, and a
consumer that reads one field of this payload has to read that one.
"""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.privacy import (
    CENSUS_SUPPRESSION_POLICY,
    STATISTICAL_SECRECY_REFERENCE,
)
from app.modules.census.domain.geo_codes import CENSUS_SOURCE_ATTRIBUTION
from app.modules.ingestion.domain.osm_extract import (
    OSM_SNAPSHOT_LICENCE,
    OSM_SNAPSHOT_SOURCE,
)
from app.modules.prioritization.domain.coping import (
    ACCESS_THRESHOLD_METRES,
    COPING_DECLARED_GAPS,
    COPING_VARIABLES,
    DISTANCE_BASIS,
    LCC_DIMENSION_KEY,
    POPULATION_WEIGHTING_RULE,
    UNIFORM_DISTRICT_SCORE_ASSUMPTION,
    CopingRanking,
    DistrictCoping,
    ScoredCopingVariable,
    score_coping,
)
from app.modules.prioritization.infrastructure.coping_repository import (
    EXPECTED_DISTRICT_COUNT,
    SHELTER_RATE_BASIS,
    CopingCorpusError,
    CopingRepository,
)

router = APIRouter(tags=["prioritization"])

PUBLISHED_DECIMAL_PLACES = 6
"""Decimal places every published score and percentile is quantised to."""

_QUANTUM = Decimal(1).scaleb(-PUBLISHED_DECIMAL_PLACES)

_VARIABLES_BY_KEY = {variable.key: variable for variable in COPING_VARIABLES}

COPING_DISCLAIMER = (
    "A relative rank, not a forecast, and a description of the situation BEFORE "
    "the event. This score says how a district's published infrastructure "
    "geography compares with the other 261: how far its people are from a "
    "hospital or clinic, and from the classified road network. Every distance "
    "is a straight-line LOWER BOUND on travel distance, because pgRouting is "
    "not installed and no road was routed. It cannot see whether a facility has "
    "power, staff or a standing roof after the event, it cannot see road "
    "condition, and its institutional half is not measured at all -- no "
    "published subnational DRR capacity indicator exists for El Salvador."
)
"""Published with every response, beside the interpretation."""


def _published(value: Decimal | None) -> float | None:
    """Quantise an exact score or percentile for publication, preserving absence."""
    if value is None:
        return None
    return float(value.quantize(_QUANTUM, rounding=ROUND_HALF_UP))


class DeclaredGapRead(BaseModel):
    """A variable the index cannot carry, with the reason and what it costs."""

    subject: str = Field(description="The variable or sub-dimension unavailable.")
    reason: str = Field(description="Why it is unavailable, with its evidence.")
    consequence: str = Field(
        description="What its absence does to the published score."
    )


class CopingMethodologyRead(BaseModel):
    """Everything a published LCC score cannot be interpreted without."""

    dimension: str = Field(description="PRIO dimension key this score belongs to.")
    method: str = Field(description="The normalisation and composition method.")
    percentile_formula: str = Field(description="The published percentile formula.")
    tie_rule: str = Field(description="How tied values share a percentile.")
    aggregation_rule: str = Field(
        description="How the sub-dimensions are composed into the dimension."
    )
    population_weighting_rule: str = Field(
        description="How per-polygon distances aggregate to a district figure."
    )
    unit_of_analysis: str = Field(description="The territorial unit scored.")
    interpretation: str = Field(description="The only reading this score supports.")
    uses_principal_components: bool = Field(
        default=False,
        description=(
            "Always false. PCA/SoVI rankings do not converge when the set of "
            "units changes (Spielman et al. 2020), so a district's score would "
            "move because an unrelated district was added."
        ),
    )
    uses_network_routing: bool = Field(
        default=False,
        description=(
            "Always false on this deployment. pgRouting is absent from the "
            "pinned postgis/postgis:16-3.4-alpine image, so every distance is "
            "a geodesic straight line and a lower bound on travel distance. "
            "Read `distance_basis` before using any distance here."
        ),
    )
    scored_unit_count: int = Field(
        description=(
            "Number of units the percentiles are relative to. A percentile is "
            "meaningless without its N, and two runs are only comparable at the "
            "same N."
        )
    )
    withheld_unit_count: int = Field(
        description="Units given no score because an input was not measurable."
    )
    scored_sub_dimension_count: int = Field(
        description=(
            "Sub-dimensions carrying at least one variable. Currently 1 of 2: "
            "the institutional sub-dimension is a declared gap, so INFORM's "
            "geometric mean reduces to the identity and this score IS the "
            "infrastructure score."
        )
    )
    declared_gap_sub_dimension_count: int = Field(
        description="Sub-dimensions carrying no variable at all."
    )
    access_threshold_metres: int = Field(
        description=(
            "Fixed distance defining 'beyond reach on foot' for the published "
            "context shares, about one hour's walk per Sphere 2018. A FIXED "
            "bound, never derived from an event's observed range. The two index "
            "variables are mean distances and do not use it."
        )
    )
    suppression_threshold: int = Field(
        description="Minimum statistical units in any published cell."
    )
    suppression_reference: str = Field(
        description="Legal basis for the suppression threshold."
    )
    osm_source: str = Field(description="Provenance of the facility and road data.")
    osm_licence: str = Field(description="Licence the derived data inherits.")


class CopingVariableRead(BaseModel):
    """One variable's full audit trail behind a district's score."""

    variable: str = Field(description="Stable variable key.")
    label: str = Field(description="Human-readable variable name.")
    theme: str = Field(description="Sub-dimension the variable belongs to.")
    in_index: bool = Field(
        description=(
            "False for a variable published for audit that contributes to no "
            "theme sum."
        )
    )
    exclusion_reason: str | None = Field(
        default=None,
        description="Why a published variable stays out of the index.",
    )
    numerator: str = Field(description="What is counted, in the source's terms.")
    denominator: str = Field(description="The universe the count is divided by.")
    measure: str = Field(
        description=(
            "What the rate is. A distance variable says so here, including that "
            "it is a lower bound, so metres are never read as a percentage."
        )
    )
    inform_equivalent: str | None = Field(
        default=None,
        description="The INFORM 2017 LCC component this stands in for.",
    )
    higher_is_worse: bool = Field(
        description=(
            "Direction of the ranking, declared rather than assumed. False for "
            "the shelter density, whose high values are good and which is "
            "therefore ranked in reverse."
        )
    )
    estimate: float | None = Field(
        description=(
            "CDC step E: the raw estimate. Person-metres for a distance "
            "variable, people for a share, facilities x 1,000 for the shelter "
            "density. Null when it could not be measured."
        )
    )
    universe: int | None = Field(
        description="The denominator as published, or null when withheld."
    )
    rate: float | None = Field(
        description="CDC step EP: estimate over universe, in the stated measure."
    )
    percentile: float | None = Field(
        description="CDC step EPL: percentile rank 0-1, or null when not ranked."
    )
    suppressed: bool = Field(
        description=(
            "True when this variable could not be published for this district, "
            "either because the measurement is absent or because its population "
            "denominator is below the disclosure threshold."
        )
    )
    suppression_reason: str | None = Field(
        default=None, description="Why the value is absent."
    )
    inputs_incomplete: bool = Field(
        description=(
            "True when the estimate was summed over at least one withheld cell, "
            "making it a lower bound in the disclosure sense as well."
        )
    )
    maximum_undercount: int = Field(
        description=(
            "Largest number of units the estimate can be short by, bounded by "
            "the suppression threshold itself."
        )
    )


class CopingThemeRead(BaseModel):
    """One sub-dimension's CDC ``SPL`` and ``RPL`` with its 0-10 score."""

    theme: str = Field(description="Sub-dimension key.")
    variable_count: int = Field(
        description="Index variables summed into this theme, all equally weighted."
    )
    declared_gap: bool = Field(
        description=(
            "True for a sub-dimension carrying no variable at all. The "
            "institutional sub-dimension is such a gap, and it is published with "
            "a null score rather than imputed at the median."
        )
    )
    percentile_sum: float | None = Field(
        description="CDC step SPL: unweighted sum of the theme's percentiles."
    )
    percentile_rank: float | None = Field(
        description="CDC step RPL: percentile rank of that sum, 0-1."
    )
    score: float | None = Field(description="The RPL rescaled onto 0-10.")


class DistrictCopingRead(BaseModel):
    """One district's LCC score, as it appears in the ranked list."""

    district_code: str = Field(description="Six-character DIGESTYC/BCR-CNR code.")
    district_name: str = Field(description="Published district name.")
    population: int | None = Field(
        description="Published resident population, or null when withheld."
    )
    rank: int | None = Field(
        description=(
            "1 is the district with the worst coping capacity. Tied scores "
            "share a rank; a district with no score carries none."
        )
    )
    score: float | None = Field(
        description=(
            "The LCC dimension score, 0-10, where 10 is worst placed. Equal to "
            "the infrastructure sub-dimension score while the institutional "
            "sub-dimension remains a declared gap."
        )
    )
    cdc_score: float | None = Field(
        description=(
            "CDC's own cross-theme composition (RPL_THEMES rescaled to 0-10), "
            "published beside the INFORM geometric mean as an audit cross-check."
        )
    )
    theme_percentile_sum: float | None = Field(
        description="CDC step SPL_THEMES: sum of the scored theme ranks."
    )
    theme_percentile_rank: float | None = Field(
        description="CDC step RPL_THEMES: percentile rank of that sum."
    )
    themes: list[CopingThemeRead] = Field(
        description="Both sub-dimensions, including the declared-gap one."
    )
    inputs_incomplete: bool = Field(
        description="True when any published estimate is a lower bound."
    )
    withheld: bool = Field(
        description="True when no score is published for this district."
    )
    withheld_reason: str | None = Field(
        default=None, description="Why no score is published."
    )


class DistrictCopingAuditRead(DistrictCopingRead):
    """One district's LCC score with every variable behind it."""

    variables: list[CopingVariableRead] = Field(
        description="Every declared variable's E, EP and EPL for this district."
    )
    methodology: CopingMethodologyRead = Field(
        description="The method this score was produced by."
    )
    distance_basis: str = Field(
        description="What the distances are, and what they are not."
    )
    declared_gaps: list[DeclaredGapRead] = Field(
        description="What the index cannot carry, with the consequences."
    )
    source: str = Field(description="Census attribution.")
    disclaimer: str = Field(description="What this score is not.")
    computed_at: datetime = Field(description="When the score was computed.")


class CopingRankingRead(BaseModel):
    """Every district ranked from worst to best coping capacity."""

    districts: list[DistrictCopingRead] = Field(
        description="Districts ordered worst coping capacity first."
    )
    scored_unit_count: int = Field(description="Districts that received a score.")
    withheld_unit_count: int = Field(
        description="Districts given no score because an input was unmeasurable."
    )
    methodology: CopingMethodologyRead = Field(
        description="The method these scores were produced by."
    )
    distance_basis: str = Field(
        description=(
            "What the distances are, and what they are not. Published at the top "
            "level rather than inside the methodology because a consumer that "
            "reads one field has to read this one."
        )
    )
    variables: list[CopingVariableRead] = Field(
        description=(
            "The declared variable catalogue with its definitions. Per-district "
            "estimates are null here; request a single district for those."
        )
    )
    declared_gaps: list[DeclaredGapRead] = Field(
        description="What the index cannot carry, with the consequences."
    )
    source: str = Field(description="Census attribution.")
    disclaimer: str = Field(description="What these scores are not.")
    computed_at: datetime = Field(description="When the scores were computed.")


class PopulationUnitAccessRead(BaseModel):
    """One DEGURBA polygon's own measured access, behind its district figure."""

    unit_id: int = Field(description="Primary key of the DEGURBA population unit.")
    district_code: str = Field(description="District the unit belongs to.")
    district_name: str = Field(description="Published district name.")
    dug_level: int = Field(description="DEGURBA level; 2 is the analysis unit.")
    dug_class: str = Field(description="Published degree-of-urbanisation class.")
    dug_code: int | None = Field(
        default=None, description="Numeric DEGURBA class code."
    )
    population: int = Field(description="Resident population of this unit.")
    geodesic_metres_to_nearest_health: float | None = Field(
        description=(
            "Straight-line metres from this polygon's representative interior "
            "point to the nearest hospital or clinic. A LOWER BOUND on travel "
            "distance. Null when unmeasurable, never zero."
        )
    )
    geodesic_metres_to_nearest_road: float | None = Field(
        description=(
            "Straight-line metres to the nearest primary-network road. A LOWER "
            "BOUND on travel distance."
        )
    )
    geodesic_metres_to_nearest_fire_station: float | None = Field(
        description=(
            "Straight-line metres to the nearest mapped fire station. Published "
            "for audit only: the national extract holds 18 stations and two "
            "departments hold none, so this feeds no score."
        )
    )
    shelter_facility_count: int = Field(
        description=(
            "Schools and community centres inside this polygon. Published for "
            "audit only; OSM school coverage is about 23% of the MINED register."
        )
    )
    score: float | None = Field(
        description=(
            "The district's LCC score, attributed to this unit under the "
            "uniformity assumption. Not measured at this level."
        )
    )
    rank: int | None = Field(description="The district's rank, 1 being worst.")
    withheld: bool = Field(description="True when the district carries no score.")


class PopulationUnitAccessResponse(BaseModel):
    """The per-polygon measurements, with the assumption and the basis."""

    units: list[PopulationUnitAccessRead] = Field(
        description="DEGURBA Nivel 2 polygons with their own measured access."
    )
    unit_count: int = Field(description="Number of polygons returned.")
    distance_basis: str = Field(
        description="What the distances are, and what they are not."
    )
    population_weighting_rule: str = Field(
        description="How these per-polygon figures become a district figure."
    )
    uniform_district_score_assumption: str = Field(
        description=(
            "The assumption that makes attributing a district score to a finer "
            "polygon legitimate, stated because the figure cannot be read "
            "without it."
        )
    )
    methodology: CopingMethodologyRead = Field(
        description="The method these scores were produced by."
    )
    source: str = Field(description="Census attribution.")
    disclaimer: str = Field(description="What these scores are not.")
    computed_at: datetime = Field(description="When the scores were computed.")


def _methodology(ranking: CopingRanking) -> CopingMethodologyRead:
    """Build the methodology block published with every response."""
    return CopingMethodologyRead(
        dimension=LCC_DIMENSION_KEY,
        method=ranking.method,
        percentile_formula=ranking.percentile_formula,
        tie_rule=ranking.tie_rule,
        aggregation_rule=ranking.aggregation_rule,
        population_weighting_rule=ranking.population_weighting_rule,
        unit_of_analysis=ranking.unit_of_analysis,
        interpretation=ranking.interpretation,
        scored_unit_count=ranking.scored_unit_count,
        withheld_unit_count=ranking.withheld_unit_count,
        scored_sub_dimension_count=ranking.scored_theme_count,
        declared_gap_sub_dimension_count=ranking.declared_gap_theme_count,
        access_threshold_metres=ACCESS_THRESHOLD_METRES,
        suppression_threshold=CENSUS_SUPPRESSION_POLICY.minimum_units,
        suppression_reference=STATISTICAL_SECRECY_REFERENCE,
        osm_source=OSM_SNAPSHOT_SOURCE,
        osm_licence=OSM_SNAPSHOT_LICENCE,
    )


def _declared_gaps() -> list[DeclaredGapRead]:
    """Publish every declared gap, so the gaps travel with the scores."""
    return [
        DeclaredGapRead(
            subject=gap.subject, reason=gap.reason, consequence=gap.consequence
        )
        for gap in COPING_DECLARED_GAPS
    ]


def _variable(scored: ScoredCopingVariable) -> CopingVariableRead:
    """Merge a district's measured variable with its catalogue definition."""
    declared = _VARIABLES_BY_KEY[scored.variable]
    return CopingVariableRead(
        variable=declared.key,
        label=declared.label,
        theme=declared.theme,
        in_index=declared.in_index,
        exclusion_reason=declared.exclusion_reason,
        numerator=declared.numerator,
        denominator=declared.denominator,
        measure=declared.measure,
        inform_equivalent=declared.inform_equivalent,
        higher_is_worse=declared.higher_is_worse,
        estimate=_published(scored.estimate),
        universe=scored.universe,
        rate=_published(scored.rate),
        percentile=_published(scored.percentile),
        suppressed=scored.suppressed,
        suppression_reason=scored.suppression_reason,
        inputs_incomplete=scored.inputs_incomplete,
        maximum_undercount=scored.maximum_undercount,
    )


def _catalogue() -> list[CopingVariableRead]:
    """Publish the variable definitions without any district's measured values."""
    return [
        CopingVariableRead(
            variable=declared.key,
            label=declared.label,
            theme=declared.theme,
            in_index=declared.in_index,
            exclusion_reason=declared.exclusion_reason,
            numerator=declared.numerator,
            denominator=declared.denominator,
            measure=declared.measure,
            inform_equivalent=declared.inform_equivalent,
            higher_is_worse=declared.higher_is_worse,
            estimate=None,
            universe=None,
            rate=None,
            percentile=None,
            suppressed=False,
            suppression_reason=None,
            inputs_incomplete=False,
            maximum_undercount=0,
        )
        for declared in COPING_VARIABLES
    ]


def _district(district: DistrictCoping) -> DistrictCopingRead:
    """Map one scored district onto the ranked-list contract."""
    return DistrictCopingRead(
        district_code=district.district_code,
        district_name=district.district_name,
        population=district.population,
        rank=district.rank,
        score=_published(district.score),
        cdc_score=_published(district.cdc_score),
        theme_percentile_sum=_published(district.theme_percentile_sum),
        theme_percentile_rank=_published(district.theme_percentile_rank),
        themes=[
            CopingThemeRead(
                theme=theme.theme,
                variable_count=theme.variable_count,
                declared_gap=theme.declared_gap,
                percentile_sum=_published(theme.percentile_sum),
                percentile_rank=_published(theme.percentile_rank),
                score=_published(theme.score),
            )
            for theme in district.themes
        ],
        inputs_incomplete=district.inputs_incomplete,
        withheld=district.withheld,
        withheld_reason=district.withheld_reason,
    )


async def _ranking(session: AsyncSession) -> CopingRanking:
    """Compute the ranking, turning an unusable corpus into a 503 rather than a 500.

    The index is recomputed per request rather than materialised, matching the V
    dimension. What is *not* recomputed per request is the geometry: the
    per-polygon distances and areas are cached in ``osm_unit_access`` at ingest
    time, because measured on the real corpus the national areal pass takes
    about 5 s and the nearest-facility pass longer. With the cache in place the
    whole dimension answers in single-digit milliseconds over 262 districts.
    """
    try:
        inputs = await CopingRepository(session).district_inputs()
    except CopingCorpusError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return score_coping(inputs)


@router.get(
    "/prioritization/coping-capacity/districts",
    response_model=CopingRankingRead,
    operation_id="listDistrictCopingCapacity",
    summary="Rank every district by the PRIO-SV Lack of Coping Capacity dimension",
)
async def list_district_coping_capacity(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CopingRankingRead:
    """Rank the 262 districts by the Lack of Coping Capacity dimension of PRIO-SV.

    Higher is worse: 10 means "worst placed of the 262 districts on this
    method". The score is normalised by the CDC/ATSDR SVI 2022 percentile method
    with equal weights at variable level and no PCA, then composed by INFORM
    2017's geometric mean.

    Two things in the response are not optional reading. Every distance is a
    **geodesic straight line and a lower bound on travel distance** -- pgRouting
    is not installed, so nothing here is a route. And the **institutional
    sub-dimension is a declared gap**, because no published subnational DRR
    capacity indicator exists for El Salvador, so this dimension is
    infrastructure only and its score equals its infrastructure score.
    """
    ranking = await _ranking(session)
    return CopingRankingRead(
        districts=[_district(district) for district in ranking.districts],
        scored_unit_count=ranking.scored_unit_count,
        withheld_unit_count=ranking.withheld_unit_count,
        methodology=_methodology(ranking),
        distance_basis=DISTANCE_BASIS,
        variables=_catalogue(),
        declared_gaps=_declared_gaps(),
        source=CENSUS_SOURCE_ATTRIBUTION,
        disclaimer=COPING_DISCLAIMER,
        computed_at=datetime.now(timezone.utc),
    )


@router.get(
    "/prioritization/coping-capacity/population-units",
    response_model=PopulationUnitAccessResponse,
    operation_id="listPopulationUnitCopingAccess",
    summary="Per-polygon access measurements behind each district's LCC score",
)
async def list_population_unit_coping_access(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    district_code: Annotated[
        str | None,
        Query(
            min_length=6,
            max_length=6,
            description="Restrict the result to one six-character district code.",
        ),
    ] = None,
) -> PopulationUnitAccessResponse:
    """Return the per-polygon distances a district's LCC figure averages.

    Unlike the Vulnerability dimension, LCC's underlying measurement really is
    taken at this finer level: each DEGURBA Nivel 2 polygon has its own measured
    distance, and the district figure is their population-weighted mean. A
    district whose urban core sits 400 m from a clinic and whose rural fringe
    sits 12 km away publishes one number, and an operator deciding where to send
    a brigade needs the spread rather than the average.

    The attributed ``score`` is still the district's, under the uniformity
    assumption returned with the response.
    """
    ranking = await _ranking(session)
    scored = {district.district_code: district for district in ranking.districts}
    rows = await CopingRepository(session).unit_access(district_code)

    units: list[PopulationUnitAccessRead] = []
    for row in rows:
        district = scored.get(str(row.district_code))
        units.append(
            PopulationUnitAccessRead(
                unit_id=int(row.unit_id),
                district_code=str(row.district_code),
                district_name=str(row.district_name),
                dug_level=int(row.dug_level),
                dug_class=str(row.dug_class),
                dug_code=None if row.dug_code is None else int(row.dug_code),
                population=int(row.population),
                geodesic_metres_to_nearest_health=_published(
                    None
                    if row.geodesic_metres_to_nearest_health is None
                    else Decimal(str(row.geodesic_metres_to_nearest_health))
                ),
                geodesic_metres_to_nearest_road=_published(
                    None
                    if row.geodesic_metres_to_nearest_road is None
                    else Decimal(str(row.geodesic_metres_to_nearest_road))
                ),
                geodesic_metres_to_nearest_fire_station=_published(
                    None
                    if row.geodesic_metres_to_nearest_fire_station is None
                    else Decimal(
                        str(row.geodesic_metres_to_nearest_fire_station)
                    )
                ),
                shelter_facility_count=int(row.shelter_facility_count),
                score=_published(district.score) if district else None,
                rank=district.rank if district else None,
                withheld=district.withheld if district else True,
            )
        )

    return PopulationUnitAccessResponse(
        units=units,
        unit_count=len(units),
        distance_basis=DISTANCE_BASIS,
        population_weighting_rule=POPULATION_WEIGHTING_RULE,
        uniform_district_score_assumption=UNIFORM_DISTRICT_SCORE_ASSUMPTION,
        methodology=_methodology(ranking),
        source=CENSUS_SOURCE_ATTRIBUTION,
        disclaimer=COPING_DISCLAIMER,
        computed_at=datetime.now(timezone.utc),
    )


@router.get(
    "/prioritization/coping-capacity/districts/{district_code}",
    response_model=DistrictCopingAuditRead,
    operation_id="getDistrictCopingCapacityAudit",
    summary="Retrieve every variable behind one district's LCC score",
)
async def get_district_coping_capacity_audit(
    district_code: Annotated[
        str,
        Path(
            min_length=6,
            max_length=6,
            description="Six-character DIGESTYC/BCR-CNR district code.",
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DistrictCopingAuditRead:
    """Take one district's LCC score apart into the variables behind it.

    Returns every declared variable's raw estimate (``E``), rate (``EP``) and
    percentile rank (``EPL``), each sub-dimension's percentile sum (``SPL``) and
    rank (``RPL``), both composition rules, and the four context variables that
    are measured and published but deliberately excluded from the index, each
    with the evidence that excluded it. A score nobody can take apart cannot be
    defended in front of an emergency committee or a jury, which is the whole
    reason this endpoint exists.
    """
    ranking = await _ranking(session)
    district = next(
        (
            candidate
            for candidate in ranking.districts
            if candidate.district_code == district_code
        ),
        None,
    )
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"District {district_code} is not one of the "
                f"{EXPECTED_DISTRICT_COUNT} districts of the census hierarchy."
            ),
        )
    base = _district(district)
    return DistrictCopingAuditRead(
        **base.model_dump(),
        variables=[_variable(variable) for variable in district.variables],
        methodology=_methodology(ranking),
        distance_basis=DISTANCE_BASIS,
        declared_gaps=_declared_gaps(),
        source=CENSUS_SOURCE_ATTRIBUTION,
        disclaimer=COPING_DISCLAIMER,
        computed_at=datetime.now(timezone.utc),
    )
