"""FastAPI adapters and Pydantic v2 schemas for the PRIO-SV Vulnerability dimension.

Three endpoints, and the division between them is about auditability rather than
convenience:

``GET /prioritization/vulnerability/districts``
    The ranked list a responder reads, with the methodology, the unit count the
    percentiles are relative to, and every declared data gap. No per-variable
    detail, because 262 districts times eight variables is not a list anybody
    reads.
``GET /prioritization/vulnerability/districts/{district_code}``
    The whole chain behind one score: each variable's ``E``, ``EP`` and ``EPL``,
    each theme's ``SPL`` and ``RPL``, and both composition rules. **An
    unexplainable score is useless in front of a jury**, so this exists to make
    any published score reducible to its inputs in one request.
``GET /prioritization/vulnerability/population-units``
    The district score attributed to each of the 902 DEGURBA polygons, with the
    uniformity assumption that makes it legitimate stated in the response.

Every response carries :data:`~app.modules.prioritization.domain.vulnerability.SCORE_INTERPRETATION`.
The score is a relative rank among Salvadoran districts; it is not a measurement
of poverty, damage or need, and the contract says so in the payload rather than
in documentation a caller may never read.

Exact arithmetic, rounded publication
-------------------------------------
Scores and percentiles are :class:`~decimal.Decimal` throughout the domain and are
published as floats quantised to :data:`PUBLISHED_DECIMAL_PLACES`. Six decimal
places is well inside what is needed to reproduce the ranking -- with 262 units a
percentile moves in steps of 1/261, about 0.00383 -- and ``rank`` is computed on
the exact values, so it stays authoritative if two rounded scores collide.
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
from app.modules.census.domain.exposure import CENSUS_REFERENCE_PERIOD
from app.modules.census.domain.geo_codes import CENSUS_SOURCE_ATTRIBUTION
from app.modules.prioritization.domain.vulnerability import (
    DECLARED_GAPS,
    DIMENSION_KEY,
    SCORE_INTERPRETATION,
    UNIFORM_DISTRICT_SCORE_ASSUMPTION,
    UNIT_OF_ANALYSIS,
    VULNERABILITY_VARIABLES,
    DistrictVulnerability,
    ScoredVariable,
    VulnerabilityRanking,
    score_vulnerability,
)
from app.modules.prioritization.infrastructure.vulnerability_repository import (
    EXPECTED_DISTRICT_COUNT,
    VulnerabilityCorpusError,
    VulnerabilityRepository,
)

router = APIRouter(tags=["prioritization"])

PUBLISHED_DECIMAL_PLACES = 6
"""Decimal places every published score and percentile is quantised to."""

_QUANTUM = Decimal(1).scaleb(-PUBLISHED_DECIMAL_PLACES)

_VARIABLES_BY_KEY = {variable.key: variable for variable in VULNERABILITY_VARIABLES}

VULNERABILITY_DISCLAIMER = (
    "A relative rank, not a forecast. This score says how a district's resident "
    "population compares with the other 261 on published census variables. It "
    "does not predict damage, it does not count casualties, and it cannot see "
    "building construction quality, which was not ingested and is a declared "
    "gap."
)
"""Published with every response, beside the interpretation."""


def _published(value: Decimal | None) -> float | None:
    """Quantise an exact score or percentile for publication, preserving absence."""
    if value is None:
        return None
    return float(value.quantize(_QUANTUM, rounding=ROUND_HALF_UP))


class DeclaredGapRead(BaseModel):
    """A variable the index cannot carry, with the reason and what it costs."""

    subject: str = Field(description="The variable or table that is unavailable.")
    reason: str = Field(description="Why it is unavailable, with its evidence.")
    consequence: str = Field(
        description="What its absence does to the published score."
    )


class VulnerabilityMethodologyRead(BaseModel):
    """Everything a published score cannot be interpreted without."""

    dimension: str = Field(description="PRIO dimension key this score belongs to.")
    method: str = Field(description="The normalisation and composition method.")
    percentile_formula: str = Field(description="The published percentile formula.")
    tie_rule: str = Field(description="How tied values share a percentile.")
    aggregation_rule: str = Field(
        description="How the two sub-dimensions are composed into the dimension."
    )
    unit_of_analysis: str = Field(description="The territorial unit scored.")
    interpretation: str = Field(
        description="The only reading this score supports."
    )
    uses_principal_components: bool = Field(
        default=False,
        description=(
            "Always false. PCA/SoVI rankings do not converge when the set of "
            "units changes (Spielman et al. 2020), so a district's score would "
            "move because an unrelated district was added."
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
        description="Units given no score because an input was withheld."
    )
    suppression_threshold: int = Field(
        description="Minimum statistical units in any published cell."
    )
    suppression_reference: str = Field(
        description="Legal basis for the suppression threshold."
    )
    reference_period: str = Field(
        description="What the census measures, and what it does not."
    )


class VulnerabilityVariableRead(BaseModel):
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
    numerator: str = Field(description="What is counted, in the census's terms.")
    denominator: str = Field(description="The universe the count is divided by.")
    measure: str = Field(
        description="What the rate is, so a ratio is not read as a percentage."
    )
    svi_equivalent: str | None = Field(
        default=None,
        description="The CDC/ATSDR SVI 2022 variable this stands in for.",
    )
    higher_is_worse: bool = Field(
        description="Direction of the ranking, declared rather than assumed."
    )
    estimate: int | None = Field(
        description="CDC step E: the raw estimate, or null when withheld."
    )
    universe: int | None = Field(
        description="The denominator as published, or null when withheld."
    )
    rate: float | None = Field(
        description="CDC step EP: estimate over universe, or null when withheld."
    )
    percentile: float | None = Field(
        description="CDC step EPL: percentile rank 0-1, or null when not ranked."
    )
    suppressed: bool = Field(
        description="True when this cell is withheld under statistical secrecy."
    )
    suppression_reason: str | None = Field(
        default=None, description="Why the cell is withheld."
    )
    inputs_incomplete: bool = Field(
        description=(
            "True when the estimate was summed over at least one withheld cell, "
            "making it a lower bound."
        )
    )
    maximum_undercount: int = Field(
        description=(
            "Largest number of units the estimate can be short by, bounded by "
            "the suppression threshold itself."
        )
    )


class VulnerabilityThemeRead(BaseModel):
    """One sub-dimension's CDC ``SPL`` and ``RPL`` with its 0-10 score."""

    theme: str = Field(description="Sub-dimension key.")
    variable_count: int = Field(
        description="Index variables summed into this theme, all equally weighted."
    )
    percentile_sum: float | None = Field(
        description="CDC step SPL: unweighted sum of the theme's percentiles."
    )
    percentile_rank: float | None = Field(
        description="CDC step RPL: percentile rank of that sum, 0-1."
    )
    score: float | None = Field(description="The RPL rescaled onto 0-10.")


class DistrictVulnerabilityRead(BaseModel):
    """One district's V score, as it appears in the ranked list."""

    district_code: str = Field(description="Six-character DIGESTYC/BCR-CNR code.")
    district_name: str = Field(description="Published district name.")
    population: int | None = Field(
        description="Published resident population, or null when withheld."
    )
    rank: int | None = Field(
        description=(
            "1 is the most vulnerable district. Tied scores share a rank; a "
            "district with no score carries none."
        )
    )
    score: float | None = Field(
        description="The V dimension score, 0-10, or null when withheld."
    )
    cdc_score: float | None = Field(
        description=(
            "CDC's own cross-theme composition (RPL_THEMES rescaled to 0-10), "
            "published beside the INFORM geometric mean as an audit cross-check."
        )
    )
    theme_percentile_sum: float | None = Field(
        description="CDC step SPL_THEMES: sum of the two theme ranks."
    )
    theme_percentile_rank: float | None = Field(
        description="CDC step RPL_THEMES: percentile rank of that sum."
    )
    themes: list[VulnerabilityThemeRead] = Field(
        description="The two sub-dimensions, each with its own rank and score."
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


class DistrictVulnerabilityAuditRead(DistrictVulnerabilityRead):
    """One district's V score with every variable behind it."""

    variables: list[VulnerabilityVariableRead] = Field(
        description="Every declared variable's E, EP and EPL for this district."
    )
    methodology: VulnerabilityMethodologyRead = Field(
        description="The method this score was produced by."
    )
    declared_gaps: list[DeclaredGapRead] = Field(
        description="Variables the index cannot carry, with their consequences."
    )
    source: str = Field(description="Census attribution.")
    disclaimer: str = Field(description="What this score is not.")
    computed_at: datetime = Field(description="When the score was computed.")


class VulnerabilityRankingRead(BaseModel):
    """Every district ranked from most to least vulnerable, with its methodology."""

    districts: list[DistrictVulnerabilityRead] = Field(
        description="Districts ordered most vulnerable first."
    )
    scored_unit_count: int = Field(
        description="Districts that received a score."
    )
    withheld_unit_count: int = Field(
        description="Districts given no score because an input was withheld."
    )
    methodology: VulnerabilityMethodologyRead = Field(
        description="The method these scores were produced by."
    )
    variables: list[VulnerabilityVariableRead] = Field(
        description=(
            "The declared variable catalogue with its definitions. Per-district "
            "estimates are null here; request a single district for those."
        )
    )
    declared_gaps: list[DeclaredGapRead] = Field(
        description="Variables the index cannot carry, with their consequences."
    )
    source: str = Field(description="Census attribution.")
    disclaimer: str = Field(description="What these scores are not.")
    computed_at: datetime = Field(description="When the scores were computed.")


class PopulationUnitVulnerabilityRead(BaseModel):
    """One DEGURBA polygon carrying its district's V score."""

    unit_id: int = Field(description="Primary key of the DEGURBA population unit.")
    district_code: str = Field(description="District the unit belongs to.")
    district_name: str = Field(description="Published district name.")
    dug_level: int = Field(description="DEGURBA level; 2 is the analysis unit.")
    dug_class: str = Field(description="Published degree-of-urbanisation class.")
    dug_code: int | None = Field(
        default=None, description="Numeric DEGURBA class code."
    )
    population: int = Field(description="Resident population of this unit.")
    households: int = Field(description="Households in this unit.")
    score: float | None = Field(
        description=(
            "The district's V score, attributed to this unit under the "
            "uniformity assumption. Not measured at this level."
        )
    )
    rank: int | None = Field(description="The district's rank, 1 being worst.")
    withheld: bool = Field(
        description="True when the district carries no score."
    )


class PopulationUnitVulnerabilityResponse(BaseModel):
    """The V dimension applied to the DEGURBA polygons, with its assumption."""

    units: list[PopulationUnitVulnerabilityRead] = Field(
        description="DEGURBA Nivel 2 polygons with their district's score."
    )
    unit_count: int = Field(description="Number of polygons returned.")
    unit_of_analysis: str = Field(
        description="The unit the score is actually measured at."
    )
    uniform_district_score_assumption: str = Field(
        description=(
            "The assumption that makes attributing a district score to a finer "
            "polygon legitimate, stated because the figure cannot be read "
            "without it."
        )
    )
    methodology: VulnerabilityMethodologyRead = Field(
        description="The method these scores were produced by."
    )
    source: str = Field(description="Census attribution.")
    disclaimer: str = Field(description="What these scores are not.")
    computed_at: datetime = Field(description="When the scores were computed.")


def _methodology(ranking: VulnerabilityRanking) -> VulnerabilityMethodologyRead:
    """Build the methodology block published with every response."""
    return VulnerabilityMethodologyRead(
        dimension=DIMENSION_KEY,
        method=ranking.method,
        percentile_formula=ranking.percentile_formula,
        tie_rule=ranking.tie_rule,
        aggregation_rule=ranking.aggregation_rule,
        unit_of_analysis=ranking.unit_of_analysis,
        interpretation=ranking.interpretation,
        scored_unit_count=ranking.scored_unit_count,
        withheld_unit_count=ranking.withheld_unit_count,
        suppression_threshold=CENSUS_SUPPRESSION_POLICY.minimum_units,
        suppression_reference=STATISTICAL_SECRECY_REFERENCE,
        reference_period=CENSUS_REFERENCE_PERIOD,
    )


def _declared_gaps() -> list[DeclaredGapRead]:
    """Publish every declared gap, so the gaps travel with the scores."""
    return [
        DeclaredGapRead(
            subject=gap.subject, reason=gap.reason, consequence=gap.consequence
        )
        for gap in DECLARED_GAPS
    ]


def _variable(scored: ScoredVariable) -> VulnerabilityVariableRead:
    """Merge a district's measured variable with its catalogue definition."""
    declared = _VARIABLES_BY_KEY[scored.variable]
    return VulnerabilityVariableRead(
        variable=declared.key,
        label=declared.label,
        theme=declared.theme,
        in_index=declared.in_index,
        exclusion_reason=declared.exclusion_reason,
        numerator=declared.numerator,
        denominator=declared.denominator,
        measure=declared.measure,
        svi_equivalent=declared.svi_equivalent,
        higher_is_worse=declared.higher_is_worse,
        estimate=scored.estimate,
        universe=scored.universe,
        rate=_published(scored.rate),
        percentile=_published(scored.percentile),
        suppressed=scored.suppressed,
        suppression_reason=scored.suppression_reason,
        inputs_incomplete=scored.inputs_incomplete,
        maximum_undercount=scored.maximum_undercount,
    )


def _catalogue() -> list[VulnerabilityVariableRead]:
    """Publish the variable definitions without any district's measured values."""
    return [
        VulnerabilityVariableRead(
            variable=declared.key,
            label=declared.label,
            theme=declared.theme,
            in_index=declared.in_index,
            exclusion_reason=declared.exclusion_reason,
            numerator=declared.numerator,
            denominator=declared.denominator,
            measure=declared.measure,
            svi_equivalent=declared.svi_equivalent,
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
        for declared in VULNERABILITY_VARIABLES
    ]


def _district(district: DistrictVulnerability) -> DistrictVulnerabilityRead:
    """Map one scored district onto the ranked-list contract."""
    return DistrictVulnerabilityRead(
        district_code=district.district_code,
        district_name=district.district_name,
        population=district.population,
        rank=district.rank,
        score=_published(district.score),
        cdc_score=_published(district.cdc_score),
        theme_percentile_sum=_published(district.theme_percentile_sum),
        theme_percentile_rank=_published(district.theme_percentile_rank),
        themes=[
            VulnerabilityThemeRead(
                theme=theme.theme,
                variable_count=theme.variable_count,
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


async def _ranking(session: AsyncSession) -> VulnerabilityRanking:
    """Compute the ranking, turning an unusable corpus into a 503 rather than a 500.

    The index is recomputed per request rather than materialised. Over 262
    districts the whole pipeline -- one query plus eight percentile sets, two
    theme ranks and one cross-theme rank -- costs single-digit milliseconds, and
    a stored table would need a refresh step that could silently serve a ranking
    from a superseded census.
    """
    try:
        inputs = await VulnerabilityRepository(session).district_inputs()
    except VulnerabilityCorpusError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return score_vulnerability(inputs)


@router.get(
    "/prioritization/vulnerability/districts",
    response_model=VulnerabilityRankingRead,
    operation_id="listDistrictVulnerability",
    summary="Rank every district by the PRIO-SV Vulnerability dimension",
)
async def list_district_vulnerability(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VulnerabilityRankingRead:
    """Rank the 262 districts by the Vulnerability dimension of PRIO-SV.

    The score is the equally weighted geometric mean of two sub-dimensions,
    each normalised by the CDC/ATSDR SVI 2022 percentile method with equal
    weights at variable level and no PCA. It is a **relative rank among
    Salvadoran districts** and nothing else.

    The response carries the declared data gaps, because half of this dimension
    is a measurement and half is a proxy: the vulnerable-groups sub-dimension
    rests on five measured district rates, while the socioeconomic
    sub-dimension rests on a single territorial proxy, since the ingested
    corpus publishes no CDC socioeconomic variable at district level and the
    construction-material tables were not ingested at all.
    """
    ranking = await _ranking(session)
    return VulnerabilityRankingRead(
        districts=[_district(district) for district in ranking.districts],
        scored_unit_count=ranking.scored_unit_count,
        withheld_unit_count=ranking.withheld_unit_count,
        methodology=_methodology(ranking),
        variables=_catalogue(),
        declared_gaps=_declared_gaps(),
        source=CENSUS_SOURCE_ATTRIBUTION,
        disclaimer=VULNERABILITY_DISCLAIMER,
        computed_at=datetime.now(timezone.utc),
    )


@router.get(
    "/prioritization/vulnerability/population-units",
    response_model=PopulationUnitVulnerabilityResponse,
    operation_id="listPopulationUnitVulnerability",
    summary="Apply the district Vulnerability score to the DEGURBA polygons",
)
async def list_population_unit_vulnerability(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    district_code: Annotated[
        str | None,
        Query(
            min_length=6,
            max_length=6,
            description="Restrict the result to one six-character district code.",
        ),
    ] = None,
) -> PopulationUnitVulnerabilityResponse:
    """Attribute each district's Vulnerability score to its DEGURBA sub-districts.

    The score is **measured at district level** and attributed to the finer
    polygon, which assumes vulnerability is uniform within the district. That is
    the same assumption place exposure already makes when it applies district
    vulnerable-group rates to a DEGURBA population, and it is returned with the
    result because the figure cannot be read without it.

    Nothing here is measured at sub-district level: a DEGURBA polygon has no age
    pyramid, no disability count and no household composition of its own.
    """
    ranking = await _ranking(session)
    scored = {district.district_code: district for district in ranking.districts}
    rows = await VulnerabilityRepository(session).population_units(district_code)

    units: list[PopulationUnitVulnerabilityRead] = []
    for row in rows:
        district = scored.get(str(row.district_code))
        units.append(
            PopulationUnitVulnerabilityRead(
                unit_id=int(row.unit_id),
                district_code=str(row.district_code),
                district_name=str(row.district_name),
                dug_level=int(row.dug_level),
                dug_class=str(row.dug_class),
                dug_code=None if row.dug_code is None else int(row.dug_code),
                population=int(row.population),
                households=int(row.households),
                score=_published(district.score) if district else None,
                rank=district.rank if district else None,
                withheld=district.withheld if district else True,
            )
        )

    return PopulationUnitVulnerabilityResponse(
        units=units,
        unit_count=len(units),
        unit_of_analysis=UNIT_OF_ANALYSIS,
        uniform_district_score_assumption=UNIFORM_DISTRICT_SCORE_ASSUMPTION,
        methodology=_methodology(ranking),
        source=CENSUS_SOURCE_ATTRIBUTION,
        disclaimer=VULNERABILITY_DISCLAIMER,
        computed_at=datetime.now(timezone.utc),
    )


@router.get(
    "/prioritization/vulnerability/districts/{district_code}",
    response_model=DistrictVulnerabilityAuditRead,
    operation_id="getDistrictVulnerabilityAudit",
    summary="Retrieve every variable behind one district's Vulnerability score",
)
async def get_district_vulnerability_audit(
    district_code: Annotated[
        str,
        Path(
            min_length=6,
            max_length=6,
            description="Six-character DIGESTYC/BCR-CNR district code.",
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DistrictVulnerabilityAuditRead:
    """Take one district's Vulnerability score apart into the variables behind it.

    Returns every declared variable's raw estimate (``E``), rate (``EP``) and
    percentile rank (``EPL``), each sub-dimension's percentile sum (``SPL``) and
    rank (``RPL``), both composition rules, and every withheld cell with the
    bound on what its absence can cost. A score nobody can take apart cannot be
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
    return DistrictVulnerabilityAuditRead(
        **base.model_dump(),
        variables=[_variable(variable) for variable in district.variables],
        methodology=_methodology(ranking),
        declared_gaps=_declared_gaps(),
        source=CENSUS_SOURCE_ATTRIBUTION,
        disclaimer=VULNERABILITY_DISCLAIMER,
        computed_at=datetime.now(timezone.utc),
    )
