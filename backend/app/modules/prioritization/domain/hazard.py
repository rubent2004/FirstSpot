"""The Hazard & Exposure (H&E) dimension: fixed bounds, per event, declared gaps.

H&E is the first of PRIO's three equally weighted dimensions and the only one
that is **live**. V is a 2024 census and LCC is an OSM snapshot; this dimension
is recomputed from a ShakeMap grid that did not exist yesterday and will be
revised tomorrow. That difference drives every design decision in this module.

Why this dimension does NOT use the CDC percentile method
---------------------------------------------------------
V and LCC normalise with CDC/ATSDR SVI 2022 percentile ranks, which is defensible
*because their unit set never changes*: 262 districts, one census, one snapshot.
A percentile is still relative, but the thing it is relative to is fixed.

Per event it is not. A percentile rank of this event's shaking would mean "shaken
worse than X% of districts **in this earthquake**", so the same district with the
same MMI VII would score 10 in an event that touched nothing else and 3 in an
event that flattened the coast. Two events would be incomparable, a time series
would be fiction, and -- the specific failure that disqualifies it -- **a district
could appear to improve because a different district got worse**, which is the
one property this whole index exists to avoid.

Every variable here is therefore rescaled onto 0-10 between **two fixed declared
constants**, published per variable as ``fixed_floor`` and ``fixed_ceiling``:

==================  ============================================================
``HE_MMIMAX``       MMI 4 -> 0, MMI 10 -> 10. The Mercalli scale's own anchors.
``HE_EXPABS``       log10(1 + exposed people), 0 -> 0, the national population -> 10.
``HE_EXPREL``       share of district population exposed, 0 -> 0, 1 -> 10.
==================  ============================================================

The consequence is declared rather than hidden: because the ceiling is MMI 10 and
El Salvador's worst recorded inland ShakeMap peaked at MMI 7.5, **a severe
Salvadoran earthquake uses only the lower half of the intensity range**. Absolute
H&E scores are therefore low-looking by construction. The ranking is what is
operational; the magnitude is comparable across events, which is what it is for.

Why exposure is computed twice and averaged
-------------------------------------------
INFORM log-transforms absolute exposed population because "the distribution of
the absolute value of exposed people is extremely skewed" -- without it one
metropolis compresses every other unit into the bottom of the scale. The log is
INFORM's own choice, not a convenience.

But a log-transformed absolute count still ranks by size, and San Salvador
district has 330,543 residents against San Pedro Nonualco's 9,443. A district
with a tenth of its people above MMI VI would outrank a village with **all** of
them above it, which inverts the operational question: the village has nowhere to
absorb its own displaced. So the **relative** form is computed as well -- the
share of the district's population inside the MMI >= VI area, which needs no log
because a share is already bounded -- and the two are averaged **arithmetically**,
equal weights, as :data:`EXPOSURE_AGGREGATION_RULE`.

An arithmetic mean rather than a geometric one is deliberate here. The two forms
measure the same people through two lenses, and a geometric mean would let the
relative form annihilate the absolute one for a large district with a small
exposed fringe -- which is a real response need, not a zero.

How a district gets its MMI, and what that number is not
--------------------------------------------------------
``HE_MMIMAX`` is the **maximum** modelled intensity anywhere in the district,
which is what INFORM's hazard components use and what a responder planning for
the worst affected settlement needs. It is deliberately not an average: a
district whose urban core reaches MMI VII and whose fringe reaches V is a
district with an MMI VII problem.

The cost is that the maximum is reached by **any** part of the district, including
an uninhabited corner. ``HE_MMIMEAN``, the population-weighted mean MMI, is
therefore computed, ranked and published as a **context variable outside the
index** so that the sensitivity is visible in every payload rather than argued
about.

Both figures come from iso-line contours drawn at a fixed interval, so the
district maximum is short of the grid's true peak by up to one contour interval --
see :data:`CONTOUR_DISCRETISATION_RULE`, and note the direction: it understates
hazard, and therefore priority.

What this dimension may never claim
-----------------------------------
Modelled ground shaking is not damage and exposure is not harm. A high H&E means
"the modelled shaking here was severe and people live in it", never "this many
buildings fell" and never, under any circumstance, a casualty figure --
see :data:`~app.modules.hazards.domain.shakemap.CASUALTY_REPORTING_PROHIBITION`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.modules.hazards.domain.shakemap import (
    CASUALTY_REPORTING_PROHIBITION,
    EXPOSURE_MMI_THRESHOLD,
    MMI_SCALE_CEILING,
    MMI_SCALE_FLOOR,
    SHAKEMAP_REVISION_WARNING,
    USGS_ATTRIBUTION,
)
from app.modules.prioritization.domain.inform import (
    INFORM_AGGREGATION_RULE,
    SCORE_CEILING,
    SCORE_FLOOR,
    inform_geometric_mean,
    rescale,
)

INTENSITY_THEME = "intensity"
"""Sub-dimension key: how hard the ground shook."""

EXPOSURE_THEME = "exposure"
"""Sub-dimension key: how many of the district's people were in that shaking."""

HAZARD_DIMENSION_KEY = "hazard_and_exposure"
"""Key of this PRIO dimension, as composed by INFORM's 1/3 exponent."""

HE_THEMES: tuple[str, ...] = (INTENSITY_THEME, EXPOSURE_THEME)
"""Both sub-dimensions in publication order. Both carry variables."""

NATIONAL_REFERENCE_POPULATION = Decimal(5_922_921)
"""Georeferenced population of El Salvador, CPV 2024, as the exposure ceiling.

The fixed upper bound of :data:`HE_EXPABS`'s log scale. It comes from the 2024
census -- a static input that does not move between events -- and **never** from
the event's own largest exposed district, which would be the defect this module
exists to prevent. A district with the entire country exposed would score 10;
San Salvador's 330,543 residents fully exposed score 8.15.

This is the reconciled georeferenced total: 5,922,921 of the published 6,029,976,
the difference being the 107,055 people in the geometry-less ``id_depto='15'``
pseudo-unit. The georeferenced figure is used because this dimension can only
measure people it can locate.
"""

MMI_MEASURE = (
    "maximum Modified Mercalli intensity (MMI) modelled anywhere inside the "
    "district by the USGS ShakeMap grid. A dimensionless intensity on the "
    "Mercalli scale, not a percentage and not a magnitude: magnitude describes "
    "the earthquake, intensity describes a place. Taken from the highest closed "
    "iso-line enclosing any part of the district, so it is short of the grid's "
    "true peak by up to one contour interval."
)

MEAN_MMI_MEASURE = (
    "population-weighted mean Modified Mercalli intensity across the district's "
    "DEGURBA Nivel 2 polygons. A dimensionless intensity, not a percentage."
)

EXPOSED_ABSOLUTE_MEASURE = (
    "log10(1 + estimated exposed residents), where an exposed resident lives "
    "where modelled intensity reaches MMI VI or above. The log transform is "
    "INFORM's own: the distribution of the absolute value of exposed people is "
    "extremely skewed, and without it one metropolis compresses every other "
    "district into the bottom of the scale. A logarithm of a count, not a "
    "percentage."
)

EXPOSED_RELATIVE_MEASURE = (
    "share of the district's resident population estimated to live where "
    "modelled intensity reaches MMI VI or above. Deliberately "
    "left untransformed: a share is already bounded in [0, 1], whereas "
    "INFORM's transform exists to tame the skew of an unbounded count."
)

FIXED_BOUNDS_RATIONALE = (
    "Every variable in this dimension is rescaled onto 0-10 between two FIXED "
    "declared constants, published per variable, and never between the minimum "
    "and maximum observed in the current event. Normalising against an event's "
    "own range destroys comparability in two ways that matter operationally. "
    "Across events: the same district with the same MMI VII would score 10 in an "
    "earthquake that touched nothing else and 3 in one that also flattened the "
    "coast. Over time: a district's score would move when an unrelated "
    "district's shaking changed, so a district could appear to IMPROVE because "
    "another district got worse. This is also why the CDC/ATSDR percentile "
    "method used by the Vulnerability and Lack of Coping Capacity dimensions is "
    "deliberately NOT used here -- a percentile is relative to its unit set, "
    "which is fixed for a census and is not fixed for an event."
)
"""The declared normalisation rule, published with every response."""

EXPOSURE_AGGREGATION_RULE = (
    "Unweighted arithmetic mean of the absolute (log-transformed) and relative "
    "(share) exposure scores. Both measure the same people through two lenses, "
    "and each alone is wrong in a known direction: the absolute form ranks by "
    "size, so San Salvador's 330,543 residents would dominate a village whose "
    "entire population is exposed, while the relative form alone is indifferent "
    "to whether 3,000 or 300,000 people need reaching. The mean is arithmetic "
    "rather than geometric on purpose -- a geometric mean would let a small "
    "relative share annihilate a large absolute count, and a metropolis with an "
    "exposed fringe of 30,000 people is a response need, not a zero."
)
"""How the two exposure variables become one sub-dimension score."""

INTENSITY_AGGREGATION_RULE = (
    "The intensity sub-dimension carries one index variable, the district "
    "maximum MMI, so its score is that variable's score. The "
    "population-weighted mean MMI is computed and published beside it as a "
    "context variable and contributes nothing, because summing a maximum and a "
    "mean of the same quantity would weight intensity twice against exposure."
)
"""How the intensity sub-dimension is composed."""

CONTOUR_DISCRETISATION_RULE = (
    "Intensity comes from ShakeMap's MMI iso-lines (cont_mi.json), drawn at a "
    "fixed interval of 0.5 MMI, not from the full grid (grid.xml). A district's "
    "maximum is therefore the highest contour that encloses part of it, and is "
    "short of the grid's true peak by UP TO ONE CONTOUR INTERVAL. The 13 "
    "February 2001 M6.6 event declares maxmmi 7.504 while its highest drawn "
    "contour is 7.0. The direction is not conservative for a prioritisation "
    "tool: it understates intensity, and therefore understates priority, by at "
    "most 0.83 points on the 0-10 intensity scale. The ShakeMap's own declared "
    "maximum is published beside the derived figure so the gap is visible and "
    "bounded. The grid is 27 MB per event against 51 KB for the contours, which "
    "is why it is not fetched; nothing else has to change to switch."
)
"""The discretisation a reader of these intensities has to know about."""

UNIFORM_DENSITY_ASSUMPTION = (
    "Exposed population is estimated by areal intersection of each MMI band with "
    "each DEGURBA Nivel 2 polygon in EPSG:32616, taking the share of a polygon's "
    "LAND inside the band as the share of its PEOPLE inside the band. This is "
    "the same uniform-density assumption already declared for place exposure in "
    "B4, and it is an assumption rather than a measurement: population is not "
    "uniform inside a polygon, so a band covering the uninhabited half of a "
    "polygon still claims half its residents. The error is bounded by the "
    "polygon, which is why the 902-unit DEGURBA layer is used rather than the "
    "262 districts -- 3.4 times finer geography means 3.4 times less of this "
    "assumption. Within one polygon the estimate cannot discriminate between "
    "locations."
)
"""Assumption every exposed-population figure rests on."""

MAXIMUM_VERSUS_MEAN_RULE = (
    "The index variable is the district MAXIMUM intensity, which is what INFORM's "
    "hazard components use and what planning for the worst-affected settlement "
    "needs. It is reached by ANY part of the district, including an uninhabited "
    "corner, so a district whose far ridge clips a high band carries that band's "
    "value. The population-weighted mean is published as a context variable so "
    "this sensitivity is visible in the payload rather than argued about: a "
    "district whose maximum and mean diverge sharply is one whose figure is "
    "driven by a small part of its territory."
)
"""Why the maximum, and what the mean is published for."""

HAZARD_SCORE_INTERPRETATION = (
    "An absolute per-event hazard and exposure score on a 0-10 scale, measured "
    "against fixed bounds rather than against the other districts, so it is "
    "comparable across events and over time. It describes MODELLED GROUND "
    "SHAKING and the resident population inside it, as of one ShakeMap grid "
    "release. It is NOT a measurement of damage, of building collapse, of "
    "injuries or of casualties, and no figure in this dimension may be reported "
    "as any of those. Because the scale is anchored to MMI 10 and El Salvador's "
    "worst recorded inland ShakeMap peaked at MMI 7.5, a severe Salvadoran "
    "earthquake uses only the lower half of this range: the ranking is what is "
    "operational, and the magnitude is what is comparable."
)
"""The only interpretation this score supports, published with every response."""

HAZARD_METHOD = (
    "Zonal statistics of USGS ShakeMap MMI iso-lines over the 902 DEGURBA Nivel "
    "2 census polygons, aggregated to 262 districts. Each variable is rescaled "
    "onto 0-10 between FIXED declared bounds -- no percentile ranking anywhere in "
    "this dimension, unlike V and LCC. The two exposure variables are combined "
    "by unweighted arithmetic mean, and the two sub-dimension scores are then "
    "composed by INFORM 2017's equally weighted geometric mean on the [1, 10] "
    "rescale, identically to V and LCC."
)
"""Short method label returned with every score."""

HAZARD_UNIT_OF_ANALYSIS = (
    "District (ADM3), 262 units, consistent with the Vulnerability and Lack of "
    "Coping Capacity dimensions so all three compose on one geography. The "
    "underlying intersection is measured per DEGURBA Nivel 2 polygon (902 "
    "units), because that is the finest geography carrying real census "
    "population, and aggregated upward: the district maximum is the maximum over "
    "its polygons, and its exposed population is their sum."
)
"""The declared unit of analysis, published with every score."""


class HazardInputError(ValueError):
    """Raised when a district input set cannot be scored as published."""


@dataclass(frozen=True, slots=True)
class HazardVariable:
    """One declared variable of the H&E dimension, with its two fixed bounds.

    Args:
        key: Stable identifier published with every score.
        label: Human-readable name for an operational UI.
        theme: Sub-dimension the variable belongs to.
        numerator: What is measured, in the source's own terms.
        denominator: The universe it is divided by, or None for a bare measure
            such as a maximum intensity, which is not a ratio.
        measure: What the resulting rate is, so an intensity is never read as a
            percentage and a logarithm is never read as a count.
        fixed_floor: Rate that scores 0. A declared constant.
        fixed_ceiling: Rate that scores 10. A declared constant.
        bound_source: Where the two constants come from, so they are auditable
            rather than merely asserted.
        inform_equivalent: The INFORM 2017 Hazard & Exposure component this
            stands in for, or None when INFORM has no counterpart.
        in_index: False for a variable computed and published for audit that
            contributes to no sub-dimension score.
        exclusion_reason: Why a context variable stays out of the index.
    """

    key: str
    label: str
    theme: str
    numerator: str
    denominator: str | None
    measure: str
    fixed_floor: Decimal
    fixed_ceiling: Decimal
    bound_source: str
    inform_equivalent: str | None = None
    in_index: bool = True
    exclusion_reason: str | None = None


EXPOSED_LOG_CEILING = (Decimal(1) + NATIONAL_REFERENCE_POPULATION).log10()
"""log10(1 + 5,922,921) = 6.77243..., the fixed ceiling of absolute exposure."""


HAZARD_VARIABLES: tuple[HazardVariable, ...] = (
    # --- Intensity sub-dimension ---
    HazardVariable(
        key="HE_MMIMAX",
        label="Maximum modelled shaking intensity",
        theme=INTENSITY_THEME,
        numerator=(
            "highest ShakeMap MMI iso-line value whose enclosed area intersects "
            "any part of the district"
        ),
        denominator=None,
        measure=MMI_MEASURE,
        fixed_floor=MMI_SCALE_FLOOR,
        fixed_ceiling=MMI_SCALE_CEILING,
        bound_source=(
            "The Modified Mercalli scale's own anchors. MMI IV is 'light' "
            "shaking -- felt indoors, dishes rattle, no structural damage -- so it "
            "is the intensity below which there is nothing to prioritise, and it "
            "scores exactly 0. MMI X is 'extreme'. Neither bound is derived from "
            "any event."
        ),
        inform_equivalent=(
            "INFORM Hazard & Exposure / Natural / Earthquake (INFORM scores a "
            "country's long-run physical exposure from a probabilistic hazard "
            "model; this scores one observed event's modelled intensity per "
            "district, so it is the same concept at a different time horizon and "
            "is not the same indicator)"
        ),
    ),
    HazardVariable(
        key="HE_MMIMEAN",
        label="Population-weighted mean shaking intensity",
        theme=INTENSITY_THEME,
        numerator=(
            "sum over the district's DEGURBA Nivel 2 polygons of (polygon "
            "resident population x the polygon's own maximum MMI), in "
            "person-MMI"
        ),
        denominator="district population summed over its DEGURBA Nivel 2 polygons",
        measure=MEAN_MMI_MEASURE,
        fixed_floor=MMI_SCALE_FLOOR,
        fixed_ceiling=MMI_SCALE_CEILING,
        bound_source="The same Mercalli anchors as HE_MMIMAX, so the two are comparable.",
        in_index=False,
        exclusion_reason=(
            "Same concept as HE_MMIMAX, so summing both would weight intensity "
            "twice against exposure, and INFORM's 1/3 per dimension is the only "
            "declared weight in PRIO-SV. The maximum is preferred as the index "
            "variable because a response plans for the worst-affected settlement "
            "rather than for the district's average resident. This mean is "
            "published because it is the direct check on the maximum's known "
            "weakness: the maximum is reached by any part of the district, "
            "including an uninhabited corner, and a district whose maximum and "
            "mean diverge sharply is one whose figure is driven by a small part "
            "of its territory."
        ),
    ),
    # --- Exposure sub-dimension ---
    HazardVariable(
        key="HE_EXPABS",
        label="Exposed population at or above MMI VI, absolute",
        theme=EXPOSURE_THEME,
        numerator=(
            "sum over the district's DEGURBA Nivel 2 polygons of (polygon "
            "resident population x the polygon's area fraction inside the MMI VI "
            "band), under the declared uniform-density assumption"
        ),
        denominator=None,
        measure=EXPOSED_ABSOLUTE_MEASURE,
        fixed_floor=Decimal(0),
        fixed_ceiling=EXPOSED_LOG_CEILING,
        bound_source=(
            "Floor log10(1 + 0) = 0, so nobody exposed scores exactly 0. Ceiling "
            "log10(1 + 5,922,921) = 6.7724, the georeferenced population of El "
            "Salvador in the 2024 census -- a static national constant, never the "
            "largest exposed district in the current event. A district with the "
            "whole country exposed scores 10."
        ),
        inform_equivalent=(
            "INFORM Hazard & Exposure / Natural / Earthquake / Physical exposure "
            "of population, which INFORM also log-transforms for exactly this "
            "skew"
        ),
    ),
    HazardVariable(
        key="HE_EXPREL",
        label="Exposed population at or above MMI VI, share of district",
        theme=EXPOSURE_THEME,
        numerator=(
            "the same exposed-population estimate as HE_EXPABS, unchanged -- the "
            "two variables differ only in the universe they are divided by"
        ),
        denominator="district population summed over its DEGURBA Nivel 2 polygons",
        measure=EXPOSED_RELATIVE_MEASURE,
        fixed_floor=Decimal(0),
        fixed_ceiling=Decimal(1),
        bound_source=(
            "A share is bounded by its own definition: 0 of the district exposed "
            "scores 0 and all of it scores 10. There is nothing to choose and "
            "nothing to derive from the data."
        ),
        inform_equivalent=(
            "No direct INFORM counterpart. INFORM scores absolute physical "
            "exposure only, which is adequate when comparing countries and is "
            "not when comparing districts inside one small country: San "
            "Salvador district holds 330,543 residents against San Pedro "
            "Nonualco's 9,443, so the absolute form alone would rank by size."
        ),
    ),
)
"""The declared variable list, in publication order. Changing it changes the index."""


@dataclass(frozen=True, slots=True)
class DeclaredGap:
    """A variable the index cannot carry, recorded with what its absence costs."""

    subject: str
    reason: str
    consequence: str


HAZARD_DECLARED_GAPS: tuple[DeclaredGap, ...] = (
    DeclaredGap(
        subject="flood, storm, volcanic and landslide hazard in the H&E dimension",
        reason=(
            "This dimension measures intensity on one declared scale, and only "
            "earthquakes publish a free, keyless, per-district intensity grid. "
            "GDACS covers flood and tropical cyclone and was verified working -- "
            "one alert level per request, because asking for all three returns "
            "only green -- but it publishes an alert LEVEL and an affected-country "
            "footprint, not an intensity field, so a flood cannot enter a fixed "
            "MMI rescale. MARN and the DGPC publish no API at all, and their own "
            "parameters are explicitly labelled preliminary. Copernicus EMS is "
            "not self-service for El Salvador. Inventing a flood-to-MMI "
            "conversion would produce a plausible and wrong hazard score."
        ),
        consequence=(
            "H&E is EARTHQUAKE ONLY. A district flooded to its rooftops scores 0 "
            "on this dimension, and under INFORM's multiplicative composition "
            "that takes its composed PRIO to 0 as well. The BASELINE mode exists "
            "partly for this: it answers 'where would a disaster hurt most' "
            "without a hazard input, and it is the correct view for any hazard "
            "this dimension cannot see. GDACS flood events are listed beside the "
            "earthquake catalogue so the gap is visible to a caller rather than "
            "looking like an absence of flooding."
        ),
    ),
    DeclaredGap(
        subject="the contour interval between the district maximum and the grid peak",
        reason=(
            "Intensity is read from cont_mi.json iso-lines drawn at a fixed 0.5 "
            "MMI interval rather than from the 27 MB grid.xml. The highest drawn "
            "contour is below the grid's true maximum: the 13 February 2001 M6.6 "
            "event declares maxmmi 7.504 against a highest contour of 7.0."
        ),
        consequence=(
            "Every district maximum is short by up to one contour interval, which "
            "is at most 0.83 points on the 0-10 intensity scale. The direction is "
            "NOT conservative for a prioritisation tool: it understates "
            "intensity, and therefore understates priority. The ShakeMap's own "
            "declared maximum travels with every response so the gap is bounded "
            "and checkable, and switching to the grid requires no change beyond "
            "the reader."
        ),
    ),
    DeclaredGap(
        subject="population distribution inside a DEGURBA polygon",
        reason=(
            "The census publishes population per DEGURBA Nivel 2 polygon and "
            "nothing finer: the 10,291 segment polygons carry official geometry "
            "and zero population attributes, and the microdata's finest "
            "geographic variable is the 6-digit district. Resolving population "
            "inside a polygon would require dasymetric modelling, not a join."
        ),
        consequence=(
            "Exposed population is estimated by areal weighting under a "
            "uniform-density assumption, so an MMI band covering the uninhabited "
            "half of a polygon still claims half its residents. The error is "
            "bounded by the polygon and is why the 902-unit layer is used rather "
            "than the 262 districts. Inside one polygon the estimate cannot "
            "discriminate between locations."
        ),
    ),
    DeclaredGap(
        subject="building vulnerability to the modelled shaking",
        reason=(
            "Construction materials were not ingested: the source CSVs use "
            "unlabelled r1..rN columns whose counts disagree with the published "
            "dictionary, and construction quality is published only at "
            "department level (14 rows). This is C1's declared gap, and it lands "
            "hardest here."
        ),
        consequence=(
            "MMI VII over adobe and MMI VII over reinforced concrete produce the "
            "same H&E score and the same V score. For an earthquake "
            "prioritisation tool this is the most consequential gap in the whole "
            "index: the single variable that most determines whether modelled "
            "shaking becomes a collapsed building is absent from every dimension."
        ),
    ),
    DeclaredGap(
        subject="aftershocks, and the cumulative effect of a sequence",
        reason=(
            "Each ShakeMap grid describes one event. The USGS catalogue publishes "
            "the sequence, but no published model combines a mainshock and its "
            "aftershocks into one intensity field, and summing MMI is not "
            "meaningful -- the Mercalli scale is ordinal."
        ),
        consequence=(
            "A district shaken at MMI VI three times in a week scores exactly as "
            "though it were shaken once, and the 2001 sequence -- M7.7 on 13 "
            "January followed by M6.6 on 13 February -- would be scored as two "
            "unrelated events. Running the index per event and comparing the "
            "outputs is possible precisely because the bounds are fixed, which is "
            "the available answer and is not the same as modelling the sequence."
        ),
    ),
    DeclaredGap(
        subject="time of day, and where people actually were",
        reason=(
            "The census records where people sleep. Nothing published records "
            "where they were at the moment of the event."
        ),
        consequence=(
            "Exposed population is a RESIDENT count. A district whose daytime "
            "population triples with commuters is scored on its residents, and a "
            "school or market full at 10:00 is invisible. Voluntary location "
            "sharing (Phase D) is the intended answer and does not exist yet."
        ),
    ),
)
"""Every gap in this dimension, with the reason and the cost."""


def hazard_variables_for_theme(theme: str) -> tuple[HazardVariable, ...]:
    """Return every declared variable of a sub-dimension, index and context alike."""
    return tuple(variable for variable in HAZARD_VARIABLES if variable.theme == theme)


def hazard_index_variables_for_theme(theme: str) -> tuple[HazardVariable, ...]:
    """Return only the variables of a sub-dimension that feed its score."""
    return tuple(
        variable for variable in hazard_variables_for_theme(theme) if variable.in_index
    )


_VARIABLES_BY_KEY = {variable.key: variable for variable in HAZARD_VARIABLES}


def rescale_fixed(
    value: Decimal,
    floor: Decimal,
    ceiling: Decimal,
) -> Decimal:
    """Rescale a value onto 0-10 between two fixed bounds, clamping outside them.

    The clamp is what makes a fixed bound usable. MMI 2 is below the declared
    floor and MMI 11 is above the declared ceiling; without a clamp the first
    would produce a negative score and the second a score above 10, and both
    would break the INFORM rescale downstream with the cause three frames away.
    Clamping publishes the bound's meaning instead: "at or below the floor there
    is nothing to prioritise", and "at or above the ceiling this is as severe as
    this scale can express".

    Args:
        value: The measured rate.
        floor: Declared rate scoring 0.
        ceiling: Declared rate scoring 10.

    Raises:
        HazardInputError: If the declared range has zero or negative width,
            which is a defect in the variable catalogue rather than in the data.
    """
    if ceiling <= floor:
        raise HazardInputError(
            f"The declared range [{floor}, {ceiling}] has no positive width, so "
            f"it carries no information about where a value sits. This is a "
            f"defect in the variable catalogue, not in the measurement."
        )
    if value <= floor:
        return SCORE_FLOOR
    if value >= ceiling:
        return SCORE_CEILING
    return rescale(value, floor, ceiling, SCORE_FLOOR, SCORE_CEILING)


@dataclass(frozen=True, slots=True)
class HazardVariableInput:
    """One district's raw measurement for one variable, with its universe.

    Args:
        variable: Key of a declared :class:`HazardVariable`.
        numerator: The raw measurement -- an MMI for the maximum, person-MMI for
            the mean, exposed people for both exposure forms -- or None when the
            district was not reached by any band.
        denominator: The universe, or None for a variable that is not a ratio.
    """

    variable: str
    numerator: Decimal | None
    denominator: Decimal | None = None


@dataclass(frozen=True, slots=True)
class DistrictHazardInput:
    """Every declared variable's raw input for one district."""

    district_code: str
    district_name: str
    population: int
    variables: tuple[HazardVariableInput, ...]


@dataclass(frozen=True, slots=True)
class ScoredHazardVariable:
    """One variable's published audit trail: the measurement, rate and score."""

    variable: str
    estimate: Decimal | None
    universe: int | None
    rate: Decimal | None
    score: Decimal
    fixed_floor: Decimal
    fixed_ceiling: Decimal
    in_index: bool
    measured: bool


@dataclass(frozen=True, slots=True)
class ScoredHazardTheme:
    """One sub-dimension's score with the rule that produced it."""

    theme: str
    variable_count: int
    score: Decimal
    aggregation_rule: str


@dataclass(frozen=True, slots=True)
class DistrictHazard:
    """One district's H&E score with the whole chain that produced it."""

    district_code: str
    district_name: str
    population: int | None
    variables: tuple[ScoredHazardVariable, ...]
    themes: tuple[ScoredHazardTheme, ...]
    score: Decimal
    rank: int | None
    shaken: bool
    max_mmi: Decimal | None
    mean_mmi: Decimal | None
    estimated_exposed_population: int


@dataclass(frozen=True, slots=True)
class HazardRanking:
    """Every district's H&E score, ordered worst hazard and exposure first."""

    districts: tuple[DistrictHazard, ...]
    scored_unit_count: int
    shaken_unit_count: int
    exposed_unit_count: int
    total_exposed_population: int
    method: str = HAZARD_METHOD
    aggregation_rule: str = INFORM_AGGREGATION_RULE
    exposure_aggregation_rule: str = EXPOSURE_AGGREGATION_RULE
    intensity_aggregation_rule: str = INTENSITY_AGGREGATION_RULE
    fixed_bounds_rationale: str = FIXED_BOUNDS_RATIONALE
    contour_discretisation_rule: str = CONTOUR_DISCRETISATION_RULE
    uniform_density_assumption: str = UNIFORM_DENSITY_ASSUMPTION
    maximum_versus_mean_rule: str = MAXIMUM_VERSUS_MEAN_RULE
    unit_of_analysis: str = HAZARD_UNIT_OF_ANALYSIS
    interpretation: str = HAZARD_SCORE_INTERPRETATION
    reporting_contract: str = CASUALTY_REPORTING_PROHIBITION
    revision_warning: str = SHAKEMAP_REVISION_WARNING
    attribution: str = USGS_ATTRIBUTION
    exposure_mmi_threshold: Decimal = EXPOSURE_MMI_THRESHOLD
    uses_percentile_normalisation: bool = False
    """Always False. See :data:`FIXED_BOUNDS_RATIONALE` for why."""


def _supplied(district: DistrictHazardInput) -> Mapping[str, HazardVariableInput]:
    """Index one district's inputs by key, refusing an incomplete set."""
    supplied = {raw.variable: raw for raw in district.variables}
    unknown = sorted(key for key in supplied if key not in _VARIABLES_BY_KEY)
    if unknown:
        raise HazardInputError(
            f"District {district.district_code} supplies undeclared variable(s) "
            f"{unknown}. Every published input is declared in HAZARD_VARIABLES, "
            f"so a key outside it would be scored without a definition, a "
            f"measure or fixed bounds."
        )
    missing = sorted(
        key for key in _VARIABLES_BY_KEY if key not in supplied
    )
    if missing:
        raise HazardInputError(
            f"District {district.district_code} is missing declared variable(s) "
            f"{missing}. Every district has to supply every variable: a silent "
            f"omission would score the district against a different variable set "
            f"than the one published, and the payload would look identical."
        )
    return supplied


def _score_variable(
    declared: HazardVariable,
    raw: HazardVariableInput,
) -> ScoredHazardVariable:
    """Rescale one measurement onto 0-10 between its own declared fixed bounds.

    An unmeasured variable scores 0 rather than being withheld, and that is the
    one place this dimension behaves differently from V and LCC. There, a missing
    input is a hole in the data and withholding the score is the honest answer.
    Here, "no MMI band reached this district" is not missing data -- it is the
    measurement, and it means the ground did not shake. Withholding it would
    remove exactly the districts that the event did not touch from a ranking
    whose purpose is to say which districts the event touched.
    """
    numerator = raw.numerator
    denominator = raw.denominator
    universe = None if denominator is None else int(denominator)

    if numerator is None:
        return ScoredHazardVariable(
            variable=declared.key,
            estimate=None,
            universe=universe,
            rate=None,
            score=SCORE_FLOOR,
            fixed_floor=declared.fixed_floor,
            fixed_ceiling=declared.fixed_ceiling,
            in_index=declared.in_index,
            measured=False,
        )

    if denominator is None:
        rate = numerator
    elif denominator == 0:
        # A district with no residents has no share and no mean to publish. Zero
        # population is not zero exposure; there is simply nobody to divide by.
        return ScoredHazardVariable(
            variable=declared.key,
            estimate=numerator,
            universe=0,
            rate=None,
            score=SCORE_FLOOR,
            fixed_floor=declared.fixed_floor,
            fixed_ceiling=declared.fixed_ceiling,
            in_index=declared.in_index,
            measured=False,
        )
    else:
        rate = numerator / denominator

    # The log transform belongs to the variable's declared measure, so it is
    # applied here where the measure string says it is, rather than in the
    # repository where a reader of the SQL would have to infer it.
    scored_rate = (
        (Decimal(1) + rate).log10() if declared.key == "HE_EXPABS" else rate
    )
    return ScoredHazardVariable(
        variable=declared.key,
        estimate=numerator,
        universe=universe,
        rate=rate,
        score=rescale_fixed(
            scored_rate, declared.fixed_floor, declared.fixed_ceiling
        ),
        fixed_floor=declared.fixed_floor,
        fixed_ceiling=declared.fixed_ceiling,
        in_index=declared.in_index,
        measured=True,
    )


def _theme_score(
    theme: str,
    scored: Mapping[str, ScoredHazardVariable],
) -> ScoredHazardTheme:
    """Combine a sub-dimension's index variables by its declared rule."""
    members = hazard_index_variables_for_theme(theme)
    parts = [scored[member.key].score for member in members]
    return ScoredHazardTheme(
        theme=theme,
        variable_count=len(members),
        score=sum(parts, SCORE_FLOOR) / len(parts),
        aggregation_rule=(
            EXPOSURE_AGGREGATION_RULE
            if theme == EXPOSURE_THEME
            else INTENSITY_AGGREGATION_RULE
        ),
    )


def score_hazard(
    districts: Sequence[DistrictHazardInput],
) -> HazardRanking:
    """Score the H&E dimension for one ShakeMap release over a set of districts.

    Each variable is rescaled between its own fixed declared bounds, the two
    exposure variables are averaged arithmetically, and the two sub-dimension
    scores are composed by INFORM's geometric mean on the [1, 10] rescale. No
    percentile is taken anywhere: a district's score depends on its own shaking
    and its own population and on nothing about any other district, which is the
    property :data:`FIXED_BOUNDS_RATIONALE` exists to guarantee and the reason
    this function needs no closed unit set.

    Args:
        districts: One input record per district. Unlike V and LCC this sequence
            is not required to be the complete national set, because no
            percentile is relative to it -- though the repository still insists
            on all 262 so that a published ranking is always national.

    Raises:
        HazardInputError: If a district code repeats, a district omits or invents
            a declared variable, or an exposed population exceeds the district's
            own population.
    """
    codes = [district.district_code for district in districts]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise HazardInputError(
            f"duplicate district code(s) {duplicates}: a district entering the "
            f"ranking twice would be dispatched to twice and would double-count "
            f"in the published exposed population."
        )

    scored: list[DistrictHazard] = []
    for district in districts:
        supplied = _supplied(district)
        variables = {
            declared.key: _score_variable(declared, supplied[declared.key])
            for declared in HAZARD_VARIABLES
        }

        exposed_raw = variables["HE_EXPABS"].estimate or Decimal(0)
        if exposed_raw > Decimal(district.population):
            raise HazardInputError(
                f"District {district.district_code} reports {exposed_raw} people "
                f"exposed against a population of {district.population}. An "
                f"exposed population that exceeds the resident population is an "
                f"upstream geometry defect -- most likely a double-counted "
                f"polygon intersection -- and publishing it as a share above 100% "
                f"would hide the cause."
            )

        themes = tuple(_theme_score(theme, variables) for theme in HE_THEMES)
        max_mmi_variable = variables["HE_MMIMAX"]
        scored.append(
            DistrictHazard(
                district_code=district.district_code,
                district_name=district.district_name,
                population=district.population,
                variables=tuple(
                    variables[declared.key] for declared in HAZARD_VARIABLES
                ),
                themes=themes,
                score=inform_geometric_mean([theme.score for theme in themes]),
                rank=None,
                shaken=max_mmi_variable.measured,
                max_mmi=max_mmi_variable.rate,
                mean_mmi=variables["HE_MMIMEAN"].rate,
                # Rounded to a person, because a published exposed population is
                # read as a count of people and 9442.7 people is not a count.
                estimated_exposed_population=int(
                    exposed_raw.to_integral_value(rounding="ROUND_HALF_UP")
                ),
            )
        )

    return HazardRanking(
        districts=_ranked(scored),
        scored_unit_count=len(scored),
        shaken_unit_count=sum(1 for district in scored if district.shaken),
        exposed_unit_count=sum(
            1 for district in scored if district.estimated_exposed_population > 0
        ),
        total_exposed_population=sum(
            district.estimated_exposed_population for district in scored
        ),
    )


def _ranked(districts: Sequence[DistrictHazard]) -> tuple[DistrictHazard, ...]:
    """Order districts worst-hazard first and assign competition ranks.

    Tied scores share one rank, because the alternative is deciding which
    district a brigade reaches first by the ``ORDER BY`` of a query. Every
    district carries a rank here, including the ones that scored zero: an
    unshaken district is a measured zero rather than a hole, so it belongs in the
    ranking at the bottom rather than outside it.
    """
    ordered = sorted(
        districts,
        key=lambda district: (-district.score, district.district_code),
    )
    ranked: list[DistrictHazard] = []
    previous_score: Decimal | None = None
    previous_rank = 0
    for position, district in enumerate(ordered, start=1):
        rank = (
            previous_rank
            if previous_score is not None and district.score == previous_score
            else position
        )
        previous_score, previous_rank = district.score, rank
        ranked.append(_with_rank(district, rank))
    return tuple(ranked)


def _with_rank(district: DistrictHazard, rank: int) -> DistrictHazard:
    """Return the district with its rank filled in, leaving the record frozen."""
    return DistrictHazard(
        district_code=district.district_code,
        district_name=district.district_name,
        population=district.population,
        variables=district.variables,
        themes=district.themes,
        score=district.score,
        rank=rank,
        shaken=district.shaken,
        max_mmi=district.max_mmi,
        mean_mmi=district.mean_mmi,
        estimated_exposed_population=district.estimated_exposed_population,
    )
