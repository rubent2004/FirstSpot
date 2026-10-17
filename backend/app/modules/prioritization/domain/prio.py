"""The composed PRIO-SV index: two explicit modes, INFORM Equation 1, DGPC colours.

This is where three separately scored dimensions become one ranked list of
territories, which is the thing the Rally LATAM challenge actually asks for::

    PRIO = (H&E)^(1/3) x (V)^(1/3) x (LCC)^(1/3)        range 0-10

Source: INFORM Concept and Methodology, Version 2017, Equation 1 -- *"a
multiplicative equation where each of the dimensions is treated equally"*. The
1/3 exponent is the only declared weight anywhere in PRIO-SV.

The composition is the PLAIN geometric mean, and that was measured
------------------------------------------------------------------
:mod:`.inform` publishes two compositions, and choosing between them here is the
single most consequential decision in the index.

* :func:`~app.modules.prioritization.domain.inform.inform_geometric_mean` inverts
  onto [1, 10] before multiplying, which removes the annihilating zero. That is
  **correct inside a dimension**: a district maximally vulnerable on one
  sub-dimension and not at all on the other is still vulnerable, and a plain
  geometric mean would report zero.
* :func:`~app.modules.prioritization.domain.inform.geometric_mean` is the plain
  mean. A single zero annihilates it.

At the top level the annihilation is the point: *a district with no ground shaking
must not be prioritised for an earthquake response merely for being poor.* But
the argument for it here is not that INFORM says so -- it is that the alternative
was run against a real earthquake and ranked the wrong districts first. See
:data:`RESCALED_COMPOSITION_EXCLUSION` for the numbers. Both values are published
per district, the plain one as ``score`` and the rescaled one as
``inform_rescaled_score``, so the choice is auditable rather than asserted.

A zero has two meanings, and they must not be confused
------------------------------------------------------
Because the composition annihilates, any dimension at exactly zero takes the
composed score to zero, and the index therefore has to say *which* dimension did
it and *what that means*:

* **H&E = 0** means the event did not reach this district. The score is zero
  because nothing happened, which is the behaviour INFORM's equation exists for.
* **V = 0 or LCC = 0** means the district ranked **best of 262** on a CDC
  percentile, whose floor is exactly 0 by construction. It does **not** mean "no
  vulnerability" or "perfect coping capacity".

The second case is real and measured: Antiguo Cuscatlán's LCC is exactly 0,
because it ranks 262nd of 262 on coping capacity, so its composed score is 0 in
every event however hard it shakes. That is defensible as a *relative* statement
-- it is genuinely last in this ranking -- and it is dangerous if read as "not
affected", so :attr:`DistrictPrio.zeroed_by` names the dimension and
:attr:`DistrictPrio.zero_reason` explains which of the two cases applies. The
count of percentile-floored districts is pinned as a test, so a normalisation
change cannot absorb it silently.

Two modes, named so they cannot be confused
-------------------------------------------
With no active event H&E is zero everywhere, so the composed product is zero
everywhere. That is *correct* -- nobody needs rescue if nothing happened -- and
useless as a default view, so there are two modes and a caller always knows which
one it received:

``BASELINE``
    V x LCC. Structural risk: "where would a disaster hurt most". Two dimensions,
    composed by the same rule, labelled as such. This is also the correct view
    for any hazard H&E cannot see, which today means every hazard except an
    earthquake with a ShakeMap.
``EVENT``
    The full three-dimension PRIO against one named ShakeMap grid release.

The modes are refused rather than coerced: a baseline index carrying a hazard
score and an event index missing one both raise
:class:`PrioCompositionError`, because a silently mixed mode would produce a
plausible number answering neither question.

Colour classes: four, because the national standard publishes four
------------------------------------------------------------------
See :data:`DGPC_CLASS_SOURCE`. The vocabulary is the DGPC's four official alert
levels; the cut points are INFORM Risk's own published class breaks. What the
classes are *not* is medical triage -- see
:data:`TRIAGE_COLOUR_ANALOGY_NOTE`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.modules.prioritization.domain.coping import LCC_DIMENSION_KEY
from app.modules.prioritization.domain.hazard import HAZARD_DIMENSION_KEY
from app.modules.prioritization.domain.inform import (
    SCORE_CEILING,
    SCORE_FLOOR,
    geometric_mean,
    inform_geometric_mean,
)
from app.modules.prioritization.domain.sphere import (
    SphereRequirement,
    sphere_minimum_requirements,
)
from app.modules.prioritization.domain.vulnerability import DIMENSION_KEY

VULNERABILITY_DIMENSION_KEY = DIMENSION_KEY
"""Re-exported so this module names all three dimensions in one place."""


class PrioMode(StrEnum):
    """Which question the composed index answers. Never inferred, always declared."""

    BASELINE = "baseline"
    EVENT = "event"


BASELINE_DIMENSION_KEYS: tuple[str, ...] = (
    VULNERABILITY_DIMENSION_KEY,
    LCC_DIMENSION_KEY,
)
"""The two dimensions a baseline index composes, in publication order."""

EVENT_DIMENSION_KEYS: tuple[str, ...] = (
    HAZARD_DIMENSION_KEY,
    VULNERABILITY_DIMENSION_KEY,
    LCC_DIMENSION_KEY,
)
"""The three dimensions an event index composes, hazard first."""

MODE_DIMENSION_KEYS: Mapping[PrioMode, tuple[str, ...]] = {
    PrioMode.BASELINE: BASELINE_DIMENSION_KEYS,
    PrioMode.EVENT: EVENT_DIMENSION_KEYS,
}
"""The declared dimension set of each mode. Enforced, not documented."""

BASELINE_MODE_MEANING = (
    "BASELINE: structural risk with no active event. Composes Vulnerability and "
    "Lack of Coping Capacity only, by the same INFORM rule, and answers 'where "
    "would a disaster hurt most' rather than 'who needs help now'. It is a "
    "standing map of where response capacity is thinnest against the population "
    "least able to absorb a shock, and it changes only when the census or the "
    "infrastructure snapshot changes -- not day to day. It is also the correct "
    "view for any hazard the Hazard & Exposure dimension cannot see, which today "
    "means everything except an earthquake with a published ShakeMap. It must "
    "NEVER be read as a statement that an event has occurred, and its ranking is "
    "not a dispatch order."
)
"""What the baseline index means, published with every baseline response."""

EVENT_MODE_MEANING = (
    "EVENT: the full three-dimension PRIO against one named ShakeMap grid "
    "release. Composes Hazard & Exposure with Vulnerability and Lack of Coping "
    "Capacity, so a district the event did not reach scores zero however "
    "structurally disadvantaged it is. This is the view that answers 'who to "
    "attend first', and every figure in it is valid only for the ShakeMap grid "
    "timestamp published with it, because ShakeMap is revised."
)
"""What an event index means, published with every event response."""

MODE_MEANINGS: Mapping[PrioMode, str] = {
    PrioMode.BASELINE: BASELINE_MODE_MEANING,
    PrioMode.EVENT: EVENT_MODE_MEANING,
}

PRIO_COMPOSITION_RULE = (
    "PRIO = (H&E)^(1/3) x (V)^(1/3) x (LCC)^(1/3), the unweighted geometric mean "
    "of the dimension scores on 0-10. Source: INFORM Concept and Methodology "
    "2017, Equation 1 -- 'a multiplicative equation where each of the dimensions "
    "is treated equally'. The 1/3 exponent is the ONLY declared weight anywhere "
    "in PRIO-SV; every other aggregation is an unweighted mean. In baseline mode "
    "the same rule runs over two dimensions, so the exponent is 1/2. The "
    "geometric mean is the PLAIN one: a zero in any dimension zeroes the product, "
    "which is what stops a district with no shaking being prioritised for being "
    "poor. Because that annihilation is real, every zeroed district publishes "
    "which dimension zeroed it and what the zero means there."
)
"""The composition rule, published with every composed score."""

RESCALED_COMPOSITION_EXCLUSION = (
    "INFORM's [1, 10] rescale -- invert, rescale, geometric mean, rescale back, "
    "re-invert -- is used INSIDE every dimension and is deliberately NOT used to "
    "compose them, and the reason is measured rather than theoretical. Run "
    "against the 13 February 2001 M6.6 Cojutepeque earthquake over the real 262 "
    "districts, the rescaled composition ranked VICTORIA (Cabañas, maximum MMI "
    "4.5, nobody above MMI VI) first at 8.06, and LISLIQUE (La Unión, never "
    "shaken at all, H&E exactly 0) second at 8.03 -- above San Pedro Nonualco, "
    "which took MMI 7.0 with its entire population of 9,443 inside the MMI VI "
    "band and placed sixth. The cause is arithmetic: the rescale maps a hazard "
    "score of 0.42 onto 9.62 of 10 before multiplying, so it does not penalise a "
    "near-absent hazard at all, and a district extreme on V and LCC rises to the "
    "top of an earthquake response it was not in. It also destroyed the class "
    "distribution, placing 40 districts in the red class against 6 under the "
    "shipped composition. The rescaled value is still computed and published per "
    "district as `inform_rescaled_score` so this exclusion stays checkable, and "
    "no ranking, class or Sphere figure reads it."
)
"""Why the non-annihilating composition is published and never ranked on."""

PERCENTILE_FLOOR_ZERO_MEANING = (
    "A Vulnerability or Lack of Coping Capacity score of exactly 0 is a "
    "PERCENTILE FLOOR, not a measurement of absence. Both dimensions normalise "
    "with CDC/ATSDR percentile ranks over a closed set of 262 districts, and the "
    "best-ranked district receives exactly 0 by construction. It means 'ranked "
    "best of 262 on this method', never 'no vulnerability' or 'able to cope with "
    "anything'. On the current corpus one district is affected: Antiguo "
    "Cuscatlán, whose LCC is exactly 0, so INFORM's multiplicative composition "
    "takes its composed PRIO to 0 in every event however hard it shakes. That is "
    "defensible as a relative statement and dangerous if read as 'not affected', "
    "so the dimension responsible is always named. Read it together with the "
    "ecological fallacy: a district at the bottom of this ranking still contains "
    "people at extreme risk."
)
"""What a zero from a percentile floor means, published with every zeroed score."""

HAZARD_ZERO_MEANING = (
    "A Hazard & Exposure score of exactly 0 means the event did not reach this "
    "district: no modelled MMI band at or above the declared floor of MMI IV "
    "intersects it, or its maximum is exactly MMI IV, which is 'light' shaking "
    "with no structural damage. The composed score is therefore 0 because nothing "
    "happened here, which is precisely the behaviour INFORM's multiplicative "
    "equation exists to produce. It is not a statement that the district is safe "
    "in general -- see the baseline mode for its structural standing."
)
"""What a zero from the hazard dimension means, published with every zeroed score."""

ECOLOGICAL_FALLACY_WARNING = (
    "ECOLOGICAL FALLACY: this index ranks TERRITORIES, not people. Every score "
    "is a property of a district, and attributing it to any individual inside "
    "that district is a category error. A green district contains people at "
    "extreme risk -- an elderly woman living alone in an adobe house in Antiguo "
    "Cuscatlán is in more danger than the median resident of the reddest "
    "district in the country, and this index cannot see her. Use it to decide "
    "WHERE to send a brigade, never to decide WHO is at risk, and never to "
    "decide that anybody is not."
)
"""Published with every composed score. Not optional reading."""

MAUP_WARNING = (
    "MODIFIABLE AREAL UNIT PROBLEM: these results change with the unit of "
    "analysis. The same census and the same ShakeMap aggregated to the 14 "
    "departments, the 44 municipalities, the 262 districts or the 902 DEGURBA "
    "sub-district polygons produce different rankings, and no one of them is the "
    "true answer -- the question 'which district is worst' has no scale-free "
    "meaning. PRIO-SV therefore publishes at ONE DECLARED SCALE, the district "
    "(ADM3, 262 units), and figures from two scales must never be compared or "
    "combined. The underlying measurement happens at the finer 902-unit DEGURBA "
    "layer and is aggregated upward; the published scale is the district."
)
"""Published with every composed score. Not optional reading."""

DECLARED_SCALE = (
    "District (ADM3), 262 units of the post-D.L. 57/2023 structure. Published "
    "secondary summaries routinely say 263 because they count the geometry-less "
    "'Otros' pseudo-unit, which holds 107,055 people and no territory."
)
"""The one scale this index publishes at."""

PRIO_INDEX_INTERPRETATION = (
    "A relative priority rank among the 262 districts of El Salvador on a 0-10 "
    "scale, composed from three equally weighted dimensions by INFORM 2017's "
    "multiplicative equation. Two of those dimensions (V, LCC) are relative "
    "percentile ranks over exactly these 262 districts and one (H&E) is absolute "
    "against fixed bounds, so the composed score is comparable across events but "
    "is NOT comparable with another country's index and is not an absolute "
    "measure of need. It is not a forecast, not a measurement of damage, not a "
    "count of people needing assistance, and under no circumstance a casualty "
    "figure. A 10 would mean 'ranked highest priority of these 262 districts by "
    "this method, in this event' and nothing more."
)
"""The only interpretation the composed score supports."""


class DgpcAlertClass(StrEnum):
    """The four official alert levels of El Salvador's civil protection system."""

    VERDE = "verde"
    AMARILLA = "amarilla"
    NARANJA = "naranja"
    ROJA = "roja"


DGPC_CLASS_SOURCE = (
    "The four colour names are El Salvador's own national standard: the DGPC's "
    "'Declaratoria de Alertas y su Clasificacion' publishes exactly four alert "
    "levels -- verde, amarilla, naranja and roja -- which is what legitimises four "
    "classes rather than three or five. The CUT POINTS are not the DGPC's and "
    "cannot be: the Declaratoria defines its levels by institutional situation "
    "and response posture, never by the value of an index. The cut points are "
    "INFORM Risk's own published class breaks -- very low 0-1.9, low 2-3.4, "
    "medium 3.5-4.9, high 5-6.4, very high 6.5-10 -- with INFORM's two lowest "
    "classes merged so that five breaks map onto four colours. So: DGPC "
    "vocabulary, INFORM arithmetic, and the merge is ours and is declared here."
)
"""Where the colours come from and where the numbers come from. Not the same place."""

TRIAGE_COLOUR_ANALOGY_NOTE = (
    "These four colours are NOT medical triage. Any resemblance to START or SALT "
    "mass-casualty triage categories is a COMMUNICATION ANALOGY only -- useful "
    "because responders already read four colours under pressure -- and the "
    "instrument here is INFORM Risk composed over census and infrastructure "
    "data, not a triage protocol. START and SALT sort individual patients by "
    "immediate physiological findings; this sorts territories by a statistical "
    "index. A district is not a patient, a red district is not a red tag, and "
    "nothing in this index is a clinical judgement about any person."
)
"""Stated wherever the colours appear, because the analogy is otherwise inevitable."""


@dataclass(frozen=True, slots=True)
class DgpcClassBreak:
    """One alert class with the half-open score interval it covers."""

    alert_class: DgpcAlertClass
    floor: Decimal
    ceiling: Decimal
    inform_class: str
    meaning: str


DGPC_CLASS_BREAKS: tuple[DgpcClassBreak, ...] = (
    DgpcClassBreak(
        alert_class=DgpcAlertClass.VERDE,
        floor=Decimal(0),
        ceiling=Decimal("3.5"),
        inform_class="INFORM very low (0-1.9) and low (2-3.4), merged",
        meaning=(
            "Lowest priority of these 262 districts by this method. In event "
            "mode this includes every district the event did not reach at all. "
            "It does NOT mean nobody here needs help -- see the ecological "
            "fallacy."
        ),
    ),
    DgpcClassBreak(
        alert_class=DgpcAlertClass.AMARILLA,
        floor=Decimal("3.5"),
        ceiling=Decimal(5),
        inform_class="INFORM medium (3.5-4.9)",
        meaning="Mid-table priority among these 262 districts.",
    ),
    DgpcClassBreak(
        alert_class=DgpcAlertClass.NARANJA,
        floor=Decimal(5),
        ceiling=Decimal("6.5"),
        inform_class="INFORM high (5-6.4)",
        meaning=(
            "High priority. Sphere minimum requirements are published for this "
            "class and above."
        ),
    ),
    DgpcClassBreak(
        alert_class=DgpcAlertClass.ROJA,
        floor=Decimal("6.5"),
        ceiling=Decimal(10),
        inform_class="INFORM very high (6.5-10)",
        meaning=(
            "Highest priority among these 262 districts by this method. Sphere "
            "minimum requirements are published."
        ),
    ),
)
"""The four classes in ascending order, covering [0, 10] with no gap or overlap."""

SPHERE_TRIGGER_CLASSES: tuple[DgpcAlertClass, ...] = (
    DgpcAlertClass.NARANJA,
    DgpcAlertClass.ROJA,
)
"""Classes for which Sphere minimum requirements are published."""

CLASS_DISTRIBUTION_CAVEAT = (
    "The class breaks are INFORM's, and INFORM calibrated them for a global "
    "country-level index whose dimensions are normalised against fixed reference "
    "values. Two of PRIO-SV's three dimensions are RELATIVE percentile ranks "
    "over 262 districts, which by construction span the full 0-10 range, so a "
    "fixed break set puts a large share of districts in the top classes whenever "
    "no hazard factor is compressing the range. Measured on the real corpus: in "
    "BASELINE mode 92 of 262 districts fall in the red class, because 'red' there "
    "means 'among the structurally worst-placed in the country' rather than "
    "'under emergency alert'. In EVENT mode the hazard dimension compresses the "
    "range and the distribution becomes an operational triage -- 6 red and 17 "
    "orange for the 2001 M6.6 event. Read the class distribution published with "
    "every response before reading any single district's class, and do not treat "
    "a baseline red as an alert."
)
"""Why a baseline red and an event red are not the same thing."""


def classify_dgpc(score: Decimal) -> DgpcAlertClass:
    """Return the DGPC alert class of a composed score.

    The intervals are half-open upward -- ``[floor, ceiling)`` -- so a score
    landing exactly on a break belongs to the **higher** class. A district at
    exactly 6.5 is red rather than orange, which is the direction a
    prioritisation instrument should round: the cost of one extra district in the
    red class is a wasted assessment, and the cost of one missing from it is a
    district nobody visits. The top class is closed at 10 so the maximum score
    has a class at all.

    Raises:
        PrioCompositionError: If the score is outside [0, 10], which means the
            composition produced something that is not an index score.
    """
    if score < SCORE_FLOOR or score > SCORE_CEILING:
        raise PrioCompositionError(
            f"Cannot classify {score}: a composed PRIO score lies in [0, 10], so "
            f"a value outside it means the composition produced something that "
            f"is not an index score."
        )
    for current in DGPC_CLASS_BREAKS:
        if score < current.ceiling:
            return current.alert_class
    return DGPC_CLASS_BREAKS[-1].alert_class


class PrioCompositionError(ValueError):
    """Raised when dimension scores cannot be composed into a published index."""


def compose_prio(scores: Sequence[Decimal]) -> Decimal:
    """Compose dimension scores by INFORM 2017 Equation 1, taken literally.

    The plain geometric mean: equal weights, and a zero in any dimension zeroes
    the product. See :data:`PRIO_COMPOSITION_RULE` for the citation and
    :data:`RESCALED_COMPOSITION_EXCLUSION` for the measured evidence that the
    non-annihilating alternative ranks the wrong districts first.

    Args:
        scores: One score per dimension, each in [0, 10], higher meaning higher
            priority. Two for a baseline index and three for an event index.

    Returns:
        The composed score in [0, 10]. Equal inputs return that input exactly,
        which is the cheapest available detector of a broken composition.

    Raises:
        PrioCompositionError: If the sequence is empty or any score falls outside
            [0, 10].
    """
    if not scores:
        raise PrioCompositionError(
            "A composed index needs at least one dimension score; an empty "
            "composition has no neutral answer, and returning 0 would publish "
            "'no priority' for a district nobody scored."
        )
    for score in scores:
        if score < SCORE_FLOOR or score > SCORE_CEILING:
            raise PrioCompositionError(
                f"Dimension score {score} is outside [0, 10]. Every dimension "
                f"publishes on that range, so a value beyond it means a "
                f"dimension's own rescale is broken."
            )
    if len(set(scores)) == 1:
        # Idempotence must be exact; exp(ln(x)) is not.
        return scores[0]
    return geometric_mean(list(scores))


def compose_prio_rescaled(scores: Sequence[Decimal]) -> Decimal:
    """Compose the same scores on INFORM's [1, 10] rescale, for audit only.

    Published per district as ``inform_rescaled_score`` and read by no ranking,
    no class and no Sphere figure. It exists so that
    :data:`RESCALED_COMPOSITION_EXCLUSION` stays checkable against the data
    rather than being a claim in a docstring.

    Raises:
        PrioCompositionError: If the sequence is empty or a score is out of range.
    """
    if not scores:
        raise PrioCompositionError(
            "A composed index needs at least one dimension score."
        )
    for score in scores:
        if score < SCORE_FLOOR or score > SCORE_CEILING:
            raise PrioCompositionError(
                f"Dimension score {score} is outside [0, 10]."
            )
    return inform_geometric_mean(list(scores))


@dataclass(frozen=True, slots=True)
class DimensionScore:
    """One dimension's contribution to a district's composed score."""

    dimension: str
    score: Decimal | None
    rank: int | None = None
    withheld_reason: str | None = None


@dataclass(frozen=True, slots=True)
class DistrictPrio:
    """One district's composed priority with every dimension behind it."""

    district_code: str
    district_name: str
    population: int | None
    dimensions: tuple[DimensionScore, ...]
    score: Decimal | None
    inform_rescaled_score: Decimal | None
    rank: int | None
    alert_class: DgpcAlertClass | None
    zeroed_by: tuple[str, ...]
    zero_reason: str | None
    withheld: bool
    withheld_reason: str | None
    max_mmi: Decimal | None
    estimated_exposed_population: int | None
    sphere: SphereRequirement | None


@dataclass(frozen=True, slots=True)
class PrioEvent:
    """The named ShakeMap release an event index was computed against."""

    event_id: str
    magnitude: Decimal | None
    place: str
    latitude: Decimal
    longitude: Decimal
    depth_km: Decimal | None
    occurred_at_iso: str
    grid_processed_at_iso: str | None
    shakemap_version: str | None
    shakemap_declared_max_mmi: Decimal | None
    contour_max_mmi: Decimal | None
    contour_interval: Decimal | None
    pager_level: str | None
    pager_band_label: str | None
    pager_response_implication: str | None


@dataclass(frozen=True, slots=True)
class PrioIndex:
    """Every district's composed priority, with the mode that produced it."""

    mode: PrioMode
    dimension_keys: tuple[str, ...]
    districts: tuple[DistrictPrio, ...]
    scored_unit_count: int
    withheld_unit_count: int
    zeroed_by_hazard_count: int
    zeroed_by_percentile_floor_count: int
    class_distribution: Mapping[DgpcAlertClass, int]
    total_exposed_population: int | None
    event: PrioEvent | None
    mode_meaning: str
    composition_rule: str = PRIO_COMPOSITION_RULE
    rescaled_composition_exclusion: str = RESCALED_COMPOSITION_EXCLUSION
    percentile_floor_zero_meaning: str = PERCENTILE_FLOOR_ZERO_MEANING
    hazard_zero_meaning: str = HAZARD_ZERO_MEANING
    ecological_fallacy: str = ECOLOGICAL_FALLACY_WARNING
    modifiable_areal_unit_problem: str = MAUP_WARNING
    declared_scale: str = DECLARED_SCALE
    class_distribution_caveat: str = CLASS_DISTRIBUTION_CAVEAT
    dgpc_class_source: str = DGPC_CLASS_SOURCE
    triage_colour_analogy: str = TRIAGE_COLOUR_ANALOGY_NOTE
    interpretation: str = PRIO_INDEX_INTERPRETATION


DistrictPrioInput = tuple[str, str, int | None, tuple[DimensionScore, ...]]
"""One district's composition input: code, name, population and dimension scores."""


def _validate_mode(
    mode: PrioMode,
    dimensions: Sequence[DimensionScore],
    district_code: str,
) -> None:
    """Refuse a district whose dimension set does not match the declared mode.

    Coercion is not an option here. A baseline index that quietly dropped a
    hazard score, or an event index that quietly composed two dimensions instead
    of three, would publish a plausible number answering neither question, and
    the payload would look identical either way.
    """
    expected = set(MODE_DIMENSION_KEYS[mode])
    supplied = {dimension.dimension for dimension in dimensions}
    if supplied == expected:
        return
    if mode is PrioMode.BASELINE and HAZARD_DIMENSION_KEY in supplied:
        raise PrioCompositionError(
            f"District {district_code} supplies a {HAZARD_DIMENSION_KEY} score "
            f"to a baseline index. Baseline answers 'where would a disaster hurt "
            f"most' from structure alone; composing a hazard into it would "
            f"produce an event index labelled as a baseline, which is the one "
            f"confusion the two modes exist to prevent."
        )
    if mode is PrioMode.EVENT and HAZARD_DIMENSION_KEY not in supplied:
        raise PrioCompositionError(
            f"District {district_code} supplies no {HAZARD_DIMENSION_KEY} score "
            f"to an event index. An event index without a hazard dimension is a "
            f"baseline index wearing the wrong label."
        )
    raise PrioCompositionError(
        f"District {district_code} supplies dimensions {sorted(supplied)} for "
        f"{mode.value} mode, which declares {sorted(expected)}. The dimension "
        f"set of a mode is fixed so that two responses with the same mode are "
        f"always comparable."
    )


def _zero_reason(zeroed_by: Sequence[str]) -> str | None:
    """Explain a zeroed composed score by naming what the zero means there."""
    if not zeroed_by:
        return None
    if HAZARD_DIMENSION_KEY in zeroed_by:
        return HAZARD_ZERO_MEANING
    return PERCENTILE_FLOOR_ZERO_MEANING


def build_prio_index(
    mode: PrioMode,
    districts: Sequence[DistrictPrioInput],
    event: PrioEvent | None = None,
    exposed_population: Mapping[str, int] | None = None,
    max_mmi: Mapping[str, Decimal | None] | None = None,
    urban_exposure: Mapping[str, bool] | None = None,
) -> PrioIndex:
    """Compose a ranked priority index for one mode over a set of districts.

    Args:
        mode: Which index this is. Enforced against each district's dimension
            set rather than assumed.
        districts: One tuple per district of code, name, population and
            dimension scores.
        event: The ShakeMap release an event index was computed against. Required
            for :attr:`PrioMode.EVENT` and refused for
            :attr:`PrioMode.BASELINE`, so a caller can never read a baseline
            ranking as a response to something that happened.
        exposed_population: Estimated exposed residents per district code, used
            for the Sphere minimum requirements. Absent in baseline mode, where
            there is no event to be exposed to.
        max_mmi: Maximum modelled intensity per district code, republished at the
            composed level because an operator reads it beside the score.
        urban_exposure: True per district code when the exposed population is
            predominantly urban with internal services, raising Sphere's shelter
            area from 3.5 to 4.5 m² per person.

    Raises:
        PrioCompositionError: If a district code repeats, a district's dimension
            set does not match the mode, or the event argument contradicts it.
    """
    if mode is PrioMode.EVENT and event is None:
        raise PrioCompositionError(
            "An event index has to name the ShakeMap release it was computed "
            "against. ShakeMap is revised, so an event score without its grid "
            "identity cannot be compared with anything, including a later run of "
            "the same earthquake."
        )
    if mode is PrioMode.BASELINE and event is not None:
        raise PrioCompositionError(
            "A baseline index must not name an event. Baseline composes "
            "structure alone, and attaching an event to it would invite a reader "
            "to treat a standing structural map as a response to that event."
        )

    codes = [code for code, _, _, _ in districts]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise PrioCompositionError(
            f"duplicate district code(s) {duplicates}: a district entering the "
            f"index twice would appear twice in a dispatch queue and would "
            f"double-count in the published class distribution."
        )

    exposed_population = exposed_population or {}
    max_mmi = max_mmi or {}
    urban_exposure = urban_exposure or {}
    ordered_keys = MODE_DIMENSION_KEYS[mode]

    composed: list[DistrictPrio] = []
    for code, name, population, dimensions in districts:
        _validate_mode(mode, dimensions, code)
        by_key = {dimension.dimension: dimension for dimension in dimensions}
        ordered = tuple(by_key[key] for key in ordered_keys)
        scores = [dimension.score for dimension in ordered]

        if any(score is None for score in scores):
            missing = sorted(
                dimension.dimension
                for dimension in ordered
                if dimension.score is None
            )
            composed.append(
                DistrictPrio(
                    district_code=code,
                    district_name=name,
                    population=population,
                    dimensions=ordered,
                    score=None,
                    inform_rescaled_score=None,
                    rank=None,
                    alert_class=None,
                    zeroed_by=(),
                    zero_reason=None,
                    withheld=True,
                    withheld_reason=(
                        f"No composed score is published for this district: the "
                        f"dimension(s) {missing} published no score, and a "
                        f"geometric mean over a hole is not a score. The "
                        f"dimension's own response carries why it was withheld."
                    ),
                    max_mmi=max_mmi.get(code),
                    estimated_exposed_population=exposed_population.get(code),
                    sphere=None,
                )
            )
            continue

        present = [score for score in scores if score is not None]
        score = compose_prio(present)
        alert_class = classify_dgpc(score)
        zeroed_by = tuple(
            dimension.dimension
            for dimension in ordered
            if dimension.score == SCORE_FLOOR
        )
        exposed = exposed_population.get(code)
        composed.append(
            DistrictPrio(
                district_code=code,
                district_name=name,
                population=population,
                dimensions=ordered,
                score=score,
                inform_rescaled_score=compose_prio_rescaled(present),
                rank=None,
                alert_class=alert_class,
                zeroed_by=zeroed_by,
                zero_reason=_zero_reason(zeroed_by),
                withheld=False,
                withheld_reason=None,
                max_mmi=max_mmi.get(code),
                estimated_exposed_population=exposed,
                sphere=(
                    sphere_minimum_requirements(
                        exposed,
                        urban_with_internal_services=urban_exposure.get(code, False),
                    )
                    if alert_class in SPHERE_TRIGGER_CLASSES and exposed is not None
                    else None
                ),
            )
        )

    ranked = _ranked(composed)
    distribution = {alert_class: 0 for alert_class in DgpcAlertClass}
    for district in ranked:
        if district.alert_class is not None:
            distribution[district.alert_class] += 1

    return PrioIndex(
        mode=mode,
        dimension_keys=ordered_keys,
        districts=ranked,
        scored_unit_count=sum(1 for d in ranked if d.score is not None),
        withheld_unit_count=sum(1 for d in ranked if d.withheld),
        zeroed_by_hazard_count=sum(
            1 for d in ranked if HAZARD_DIMENSION_KEY in d.zeroed_by
        ),
        zeroed_by_percentile_floor_count=sum(
            1
            for d in ranked
            if d.zeroed_by and HAZARD_DIMENSION_KEY not in d.zeroed_by
        ),
        class_distribution=distribution,
        total_exposed_population=(
            sum(
                d.estimated_exposed_population or 0
                for d in ranked
            )
            if mode is PrioMode.EVENT
            else None
        ),
        event=event,
        mode_meaning=MODE_MEANINGS[mode],
    )


def _ranked(districts: Sequence[DistrictPrio]) -> tuple[DistrictPrio, ...]:
    """Order districts highest priority first and assign competition ranks.

    Tied scores share one rank, because the alternative is deciding which
    district a brigade reaches first by the ``ORDER BY`` of a query. Districts
    with no score sort last and carry no rank, so a withheld dimension is visible
    as a hole instead of shortening the list.
    """
    scoreable = sorted(
        (district for district in districts if district.score is not None),
        key=lambda district: (-district.score, district.district_code),  # type: ignore[operator]
    )
    withheld = sorted(
        (district for district in districts if district.score is None),
        key=lambda district: district.district_code,
    )

    ranked: list[DistrictPrio] = []
    previous_score: Decimal | None = None
    previous_rank = 0
    for position, district in enumerate(scoreable, start=1):
        rank = (
            previous_rank
            if previous_score is not None and district.score == previous_score
            else position
        )
        previous_score, previous_rank = district.score, rank
        ranked.append(_with_rank(district, rank))
    return tuple(ranked) + tuple(withheld)


def _with_rank(district: DistrictPrio, rank: int) -> DistrictPrio:
    """Return the district with its rank filled in, leaving the record frozen."""
    return DistrictPrio(
        district_code=district.district_code,
        district_name=district.district_name,
        population=district.population,
        dimensions=district.dimensions,
        score=district.score,
        inform_rescaled_score=district.inform_rescaled_score,
        rank=rank,
        alert_class=district.alert_class,
        zeroed_by=district.zeroed_by,
        zero_reason=district.zero_reason,
        withheld=district.withheld,
        withheld_reason=district.withheld_reason,
        max_mmi=district.max_mmi,
        estimated_exposed_population=district.estimated_exposed_population,
        sphere=district.sphere,
    )
