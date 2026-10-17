"""The Lack of Coping Capacity (LCC) dimension: variables, scoring, declared gaps.

LCC is the third of PRIO's three equally weighted dimensions. Per INFORM it
measures a territory's **lack** of ability to cope, so higher is worse, and like V
it is a **relative rank among the 262 Salvadoran districts** and nothing else.
:data:`LCC_SCORE_INTERPRETATION` is published with every score and is deliberately
restrictive.

The method is identical to V's, which is the point
--------------------------------------------------
LCC composes through exactly the same two standards, in the same two modules:

* **CDC/ATSDR SVI 2022** for normalisation -- ``E`` -> ``EP`` -> ``EPL`` ->
  ``SPL`` -> ``RPL``, equal weights at variable level, no PCA (see
  :mod:`.percentile` for why Spielman et al. (2020) rules PCA out);
* **INFORM 2017 Equation 1** for composition -- the equally weighted geometric
  mean taken on the [1, 10] rescale (see :mod:`.inform`).

One thing is genuinely new. V's variables are *shares*, bounded in [0, 1]. LCC's
index variables are **population-weighted mean distances in metres**, unbounded
above. The CDC pipeline is indifferent to that -- a percentile rank only needs an
order -- but the audit trail is not, so ``E`` is published as **person-metres**
and its universe as **people**, making ``EP`` a mean distance that divides back
out to the inputs a reader can check. :data:`METRES_PER_PERSON` says so in the
payload, because a bare "4,999" next to a column of shares would be read as a
percentage.

Distance is a lower bound, and that is not a detail
---------------------------------------------------
pgRouting is **not installed and not installable** inside the pinned
``postgis/postgis:16-3.4-alpine`` image: it is absent from
``pg_available_extensions``, Alpine's package repository does not carry it, and
the image is declared in ``docker-compose.yml``. Every distance in this dimension
is therefore **geodesic** -- ``ST_Distance`` on a ``GEOGRAPHY`` column, which is
true metres on the WGS 84 ellipsoid rather than planar degrees -- and it is a
**lower bound on travel distance**.

That distinction is operationally load-bearing rather than pedantic. In a
disaster the hospital 2 km away as the crow flies can be 40 minutes away if the
bridge fell, and the error is **not** a constant factor: it is worst in exactly
the mountainous, river-cut districts this index is meant to find, so the geodesic
measure understates their disadvantage. :data:`DISTANCE_BASIS` is published with
every response and network routing is recorded in :data:`COPING_DECLARED_GAPS` as
open work.

The two sub-dimensions, and why one of them is empty
----------------------------------------------------
**Infrastructure** carries two measured variables: distance to care and distance
to the classified road network. Their Pearson correlation over the 262 districts
is 0.18, so they are close to independent and neither is a disguised copy of the
other -- two collinear variables would be an undeclared double weight, and
INFORM's 1/3 per dimension is the only declared weight in PRIO-SV.

**Institutional** carries **nothing**. No published subnational disaster-risk
-reduction capacity indicator exists for El Salvador: governance and institutional
capacity are published nationally by INFORM itself and by the Sendai Framework
monitor, never per district, and MARN/DGPC publish no API at all. Rather than
manufacture a proxy, the sub-dimension is declared empty and published with
``score = None``.

The consequence has to be stated wherever these scores appear: **LCC is
infrastructure only.** With one scored sub-dimension INFORM's geometric mean is
the identity, so the published LCC score *is* the infrastructure score. That
identity is pinned as a test, exactly as C1 pinned its saturation ceiling, so the
day a real institutional indicator exists the test fails -- and that failure is
the wanted signal that the dimension stopped being half-measured.

What a short distance does not mean
-----------------------------------
OSM records that a building is tagged ``amenity=hospital``. It does not record
whether that hospital has power, staff, supplies or a standing roof, and after
the event that is precisely what has changed. A low LCC score means "better
placed to cope **before** the event, on the published infrastructure", never
"care is available".
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.core.privacy import (
    CENSUS_SUPPRESSION_POLICY,
    STATISTICAL_SECRECY_REFERENCE,
    SuppressionPolicy,
)
from app.modules.prioritization.domain.inform import (
    INFORM_AGGREGATION_RULE,
    inform_geometric_mean,
)
from app.modules.prioritization.domain.percentile import (
    PERCENTILE_RANK_FORMULA,
    PERCENTILE_TIE_RULE,
    percentile_ranks_by_unit,
    rescale_to_score,
)

INFRASTRUCTURE_THEME = "infrastructure"
"""Sub-dimension key: can help physically reach people, and is there shelter."""

INSTITUTIONAL_THEME = "institutional"
"""Sub-dimension key: a declared gap carrying no variable and no score."""

LCC_DIMENSION_KEY = "lack_of_coping_capacity"
"""Key of this PRIO dimension, as composed by INFORM's 1/3 exponent."""

METRES_PER_PERSON = (
    "population-weighted mean geodesic metres to the nearest facility of this "
    "kind -- a LOWER BOUND on travel distance, never travel distance itself. "
    "Not a percentage: the value is unbounded above."
)
"""Measure string for every distance variable, published per variable."""

SHARE_OF_POPULATION = "share of district resident population"
FACILITIES_PER_1000 = (
    "facilities per 1,000 inhabitants (a density, not a percentage)"
)

DISTANCE_BASIS = (
    "Geodesic distance: PostGIS ST_Distance on a GEOGRAPHY column, which "
    "returns true metres on the WGS 84 ellipsoid rather than planar degrees. It "
    "is a LOWER BOUND on travel distance and is NOT travel distance, because "
    "pgRouting is absent from the pinned postgis/postgis:16-3.4-alpine image "
    "and no road network was routed. The understatement is not a constant "
    "factor: it is largest in mountainous and river-cut districts, which are "
    "the districts this dimension exists to identify, so every distance here is "
    "conservative against the territory it describes. In a disaster a facility "
    "2 km away in a straight line can be 40 minutes away if one bridge fell."
)
"""The declared distance basis, published with every response."""

LCC_SCORE_INTERPRETATION = (
    "A relative lack-of-coping-capacity rank among the 262 districts of El "
    "Salvador, on a 0-10 scale, where 10 is the worst-placed district. It is "
    "measured on published infrastructure geography only: it is not a "
    "measurement of emergency-service quality, of institutional preparedness, "
    "of expected damage or of casualties, and it is not comparable with any "
    "other country's index. It describes the situation BEFORE the event -- a "
    "facility recorded as nearby may have no power, no staff and no roof "
    "afterwards."
)
"""The only interpretation this score supports, published with every response."""

LCC_METHOD = (
    "CDC/ATSDR SVI 2022 percentile method within each sub-dimension (E, EP, "
    "EPL, SPL, RPL), equal weights at variable level, no PCA; sub-dimension "
    "scores are then composed by INFORM 2017's equally weighted geometric mean "
    "on the [1, 10] rescale. Only the infrastructure sub-dimension carries "
    "variables, so the composition currently reduces to the identity and the "
    "published score IS the infrastructure score. CDC's own cross-theme "
    "composition (SPL_THEMES, RPL_THEMES) is published beside it for audit."
)
"""Short method label returned with every score."""

LCC_UNIT_OF_ANALYSIS = (
    "District (ADM3), 262 units, consistent with the Vulnerability dimension so "
    "the two compose on one geography. Distances are measured per DEGURBA Nivel "
    "2 sub-district polygon (902 units) and aggregated to the district weighted "
    "by each polygon's resident population, so a district's figure is dominated "
    "by where its people actually live rather than by its geometric centre."
)
"""The declared unit of analysis, published with every score."""

POPULATION_WEIGHTING_RULE = (
    "Each DEGURBA Nivel 2 polygon contributes its resident population times its "
    "own distance, and the district total is divided by its population. The "
    "alternative -- one distance from the district centroid -- would place the "
    "measurement in an uninhabited mountain for exactly the dispersed rural "
    "districts whose access is worst. Within a single polygon the distance is "
    "measured from one representative interior point (ST_PointOnSurface), so "
    "the figure discriminates between polygons and not between locations inside "
    "one polygon: this is the same uniformity assumption already declared for "
    "place exposure in B4."
)
"""Aggregation rule a reader of these distances has to know about."""

UNIFORM_DISTRICT_SCORE_ASSUMPTION = (
    "Applying a district's LCC score to the DEGURBA sub-district polygons "
    "inside it assumes coping capacity is uniform within the district. For this "
    "dimension that assumption is weaker than it is for Vulnerability, because "
    "the underlying measurement is explicitly per polygon: a district's urban "
    "core can sit 400 m from a clinic while its rural fringe sits 12 km away, "
    "and the district figure is the population-weighted average of exactly that "
    "spread. Read a district score as the district's aggregate position, never "
    "as the position of any settlement inside it."
)
"""Assumption a reader of a DEGURBA-level LCC score has to know about."""


class CopingInputError(ValueError):
    """Raised when a district input set cannot be scored as published."""


@dataclass(frozen=True, slots=True)
class CopingVariable:
    """One declared variable of the LCC dimension, with direction and provenance.

    Args:
        key: Stable identifier published with every percentile.
        label: Human-readable name for an operational UI.
        theme: Sub-dimension the variable belongs to.
        numerator: What is counted, in the source's own terms.
        denominator: The universe the count is divided by.
        measure: What the resulting ``EP`` is, so a distance is never read as a
            percentage.
        inform_equivalent: Name of the INFORM 2017 Lack of Coping Capacity
            component this stands in for, or None when INFORM has no counterpart.
        higher_is_worse: Direction of the ranking. ``LCC_SHELTER`` is the only
            variable in either dimension whose high values are *good*, and CDC
            handles that by ranking it in reverse.
        in_index: False for a variable computed, ranked and published for audit
            that contributes nothing to any theme sum.
        exclusion_reason: Why a context variable stays out of the index.
    """

    key: str
    label: str
    theme: str
    numerator: str
    denominator: str
    measure: str
    inform_equivalent: str | None = None
    higher_is_worse: bool = True
    in_index: bool = True
    exclusion_reason: str | None = None


ACCESS_THRESHOLD_METRES = 5000
"""Fixed distance defining "beyond reach on foot", used by the context shares.

Sphere Handbook 2018 expresses health access as roughly one hour's travel, which
on foot over Salvadoran terrain is about 5 km. It is a **fixed declared bound**,
chosen once and never derived from an event's observed range -- normalising
against a current event would make two events incomparable, which is the defect
this whole index exists to avoid.
"""


COPING_VARIABLES: tuple[CopingVariable, ...] = (
    # --- Infrastructure sub-dimension: the two measured index variables ---
    CopingVariable(
        key="LCC_HEALTHDIST",
        label="Distance to the nearest hospital or clinic",
        theme=INFRASTRUCTURE_THEME,
        numerator=(
            "sum over the district's DEGURBA Nivel 2 polygons of (polygon "
            "resident population x geodesic metres from the polygon's "
            "representative interior point to the nearest OSM amenity=hospital, "
            "amenity=clinic, amenity=doctors, healthcare=hospital, "
            "healthcare=clinic or healthcare=centre), in person-metres"
        ),
        denominator="district population summed over its DEGURBA Nivel 2 polygons",
        measure=METRES_PER_PERSON,
        inform_equivalent=(
            "INFORM Lack of Coping Capacity / Infrastructure / Access to health "
            "care (INFORM measures it nationally; this is its subnational "
            "geographic analogue, not the same indicator)"
        ),
    ),
    CopingVariable(
        key="LCC_ROADDIST",
        label="Distance to the nearest primary-network road",
        theme=INFRASTRUCTURE_THEME,
        numerator=(
            "sum over the district's DEGURBA Nivel 2 polygons of (polygon "
            "resident population x geodesic metres from the polygon's "
            "representative interior point to the nearest OSM "
            "highway=motorway, highway=trunk or highway=primary way), in "
            "person-metres"
        ),
        denominator="district population summed over its DEGURBA Nivel 2 polygons",
        measure=METRES_PER_PERSON,
        inform_equivalent=(
            "INFORM Lack of Coping Capacity / Infrastructure / Road density "
            "(INFORM uses national road density; this measures population "
            "distance to the classified network instead, which is what decides "
            "whether a brigade can arrive)"
        ),
    ),
    # --- Infrastructure sub-dimension: published for audit, outside the index ---
    CopingVariable(
        key="LCC_HEALTHFAR",
        label="Population beyond 5 km of a hospital or clinic",
        theme=INFRASTRUCTURE_THEME,
        numerator=(
            "sum over the district's DEGURBA Nivel 2 polygons of (polygon "
            "resident population x the polygon's area fraction lying further "
            "than 5,000 geodesic metres from any hospital or clinic), under the "
            "uniform-density assumption already declared for place exposure"
        ),
        denominator="district population summed over its DEGURBA Nivel 2 polygons",
        measure=SHARE_OF_POPULATION,
        in_index=False,
        exclusion_reason=(
            "Same concept as LCC_HEALTHDIST, so summing both would weight "
            "health access twice against road access, and INFORM's 1/3 per "
            "dimension is the only declared weight in PRIO-SV. The mean "
            "distance is preferred as the index variable because it separates "
            "all 262 districts, while this share leaves 44 districts tied at "
            "exactly 0 and 6 tied at exactly 1 -- the same saturation that "
            "limits V's socioeconomic sub-dimension, which there was "
            "unavoidable and here is not. Published because it is the form an "
            "operator reads directly, and it cross-checks the distance."
        ),
    ),
    CopingVariable(
        key="LCC_ROADFAR",
        label="Population beyond 5 km of a primary-network road",
        theme=INFRASTRUCTURE_THEME,
        numerator=(
            "sum over the district's DEGURBA Nivel 2 polygons of (polygon "
            "resident population x the polygon's area fraction lying further "
            "than 5,000 geodesic metres from any primary-network road), under "
            "the uniform-density assumption"
        ),
        denominator="district population summed over its DEGURBA Nivel 2 polygons",
        measure=SHARE_OF_POPULATION,
        in_index=False,
        exclusion_reason=(
            "Same concept as LCC_ROADDIST and excluded for the same reason. Its "
            "saturation is worse than the health share's: 39 districts sit at "
            "exactly 0 and 36 at exactly 1, so 75 of 262 districts fall into "
            "two tie blocks that the mean distance separates completely."
        ),
    ),
    CopingVariable(
        key="LCC_SHELTER",
        label="Schools and community centres per 1,000 inhabitants",
        theme=INFRASTRUCTURE_THEME,
        numerator=(
            "OSM amenity=school and amenity=community_centre features whose "
            "representative point falls inside the district"
        ),
        denominator="district population summed over its DEGURBA Nivel 2 polygons",
        measure=FACILITIES_PER_1000,
        higher_is_worse=False,
        in_index=False,
        exclusion_reason=(
            "Excluded on measured evidence, not on taste, and the numbers are "
            "worth keeping because they disqualify any school-derived capacity "
            "variable rather than only this one. The national extract holds "
            "1,199 amenity=school features against the roughly 5,100 centros "
            "escolares MINED operates, so it is about 23% complete; 32 of 262 "
            "districts show zero schools, which cannot be true of a country "
            "with compulsory basic education, and 25 of those 32 fall in the "
            "two most rural quartiles -- so the incompleteness is concentrated "
            "exactly where the index would read it as a finding. Dividing by "
            "population then inverts the direction: the Pearson correlation of "
            "this density with rural population share is +0.18, meaning the "
            "most rural districts score as BETTER supplied because their "
            "denominators are small, while the raw feature count correlates "
            "-0.35 the other way. A variable that reports rural villages as "
            "well sheltered because 1,900 people share one mapped school "
            "cannot be summed into a coping theme. Shelter capacity is "
            "therefore a declared gap, and this is published only so the "
            "exclusion is checkable."
        ),
    ),
    CopingVariable(
        key="LCC_FIREDIST",
        label="Distance to the nearest fire station",
        theme=INFRASTRUCTURE_THEME,
        numerator=(
            "sum over the district's DEGURBA Nivel 2 polygons of (polygon "
            "resident population x geodesic metres from the polygon's "
            "representative interior point to the nearest OSM "
            "amenity=fire_station), in person-metres"
        ),
        denominator="district population summed over its DEGURBA Nivel 2 polygons",
        measure=METRES_PER_PERSON,
        in_index=False,
        exclusion_reason=(
            "Excluded on measured evidence. The national extract holds 18 "
            "amenity=fire_station features for the whole country, and the "
            "departments of Santa Ana and Cabañas hold zero -- Santa Ana is El "
            "Salvador's second city with roughly a quarter of a million "
            "inhabitants and certainly has a Cuerpo de Bomberos station, so the "
            "zero is a mapping gap and not a finding. Only 12 of 262 districts "
            "contain a mapped station, and the worst district measures 60 km to "
            "the nearest one, a figure produced by the missing stations rather "
            "than by Salvadoran geography. Including it would have scored Santa "
            "Ana as having no fire response at all. Published so the gap is "
            "visible and so the variable can be promoted unchanged the day the "
            "DGPC station list is obtainable."
        ),
    ),
    # --- Institutional sub-dimension: no variable exists. See COPING_DECLARED_GAPS.
)
"""The declared variable list, in publication order. Changing it changes the index."""


@dataclass(frozen=True, slots=True)
class DeclaredGap:
    """A variable the index cannot carry, recorded with what its absence costs."""

    subject: str
    reason: str
    consequence: str


COPING_DECLARED_GAPS: tuple[DeclaredGap, ...] = (
    DeclaredGap(
        subject="the entire institutional sub-dimension of LCC",
        reason=(
            "No published subnational disaster-risk-reduction capacity "
            "indicator exists for El Salvador. INFORM itself publishes "
            "governance and institutional capacity at national level only; the "
            "Sendai Framework monitor is reported nationally; and MARN and the "
            "DGPC publish no API and no per-district capacity series at all. "
            "Any district-level institutional score would therefore have been "
            "invented rather than measured."
        ),
        consequence=(
            "LCC is INFRASTRUCTURE ONLY. The institutional sub-dimension is "
            "published with a null score and zero variables rather than imputed "
            "at the median, so with one scored sub-dimension INFORM's geometric "
            "mean reduces to the identity and the published LCC score IS the "
            "infrastructure score. Half of this dimension is therefore not "
            "measured, and a district with good roads and a nearby clinic "
            "scores well even if its emergency committee has never met. The "
            "identity is pinned as a test so that ingesting a real "
            "institutional indicator breaks it visibly."
        ),
    ),
    DeclaredGap(
        subject="network distance (pgRouting) for every distance in this dimension",
        reason=(
            "pgRouting is absent from pg_available_extensions in the pinned "
            "postgis/postgis:16-3.4-alpine image, Alpine's package repository "
            "does not carry it, and installing it means changing the image in "
            "docker-compose.yml. Every published distance is therefore geodesic "
            "ST_Distance on the GEOGRAPHY column: true ellipsoidal metres, but "
            "a straight line."
        ),
        consequence=(
            "Every distance is a LOWER BOUND on travel distance, never travel "
            "distance. The error is not a constant factor that a reader can "
            "mentally divide out: it is largest in mountainous and river-cut "
            "districts, which are precisely the districts this dimension exists "
            "to identify, so the published figures understate their "
            "disadvantage. Importing the primary network as a routable topology "
            "and republishing these two variables as network distance is open "
            "work, and the ingested road geometry is already in place for it."
        ),
    ),
    DeclaredGap(
        subject="fire stations and ambulance stations as a response-capacity variable",
        reason=(
            "The national extract holds 18 amenity=fire_station and 18 "
            "emergency=ambulance_station features. The departments of Santa Ana "
            "and Cabañas hold zero fire stations, which is a mapping gap rather "
            "than a fact about those departments."
        ),
        consequence=(
            "Emergency response capacity is absent from the index. The distance "
            "is still computed, cached and published as LCC_FIREDIST so the gap "
            "is visible and quantified, and the facilities are ingested so they "
            "appear on the map, but no score depends on them."
        ),
    ),
    DeclaredGap(
        subject="shelter capacity (usable collective shelter, and its capacity)",
        reason=(
            "No shelter register is published per district. The OSM proxy fails "
            "on measurement: 1,199 mapped schools against roughly 5,100 MINED "
            "centros escolares, 32 districts at zero, and the incompleteness "
            "concentrated in rural districts. OSM amenity=shelter is unusable "
            "for a different reason -- it holds 41 features nationally and the "
            "tag denotes a bus or picnic shelter, not an emergency one -- and "
            "emergency=assembly_point holds 17."
        ),
        consequence=(
            "The 'is there anywhere to shelter them' half of the infrastructure "
            "sub-dimension is not measured. The dimension answers only 'can "
            "help physically reach people'. Sphere shelter-area minimums in C4 "
            "therefore compute a REQUIREMENT and must never be compared against "
            "an available-capacity figure, because none exists."
        ),
    ),
    DeclaredGap(
        subject="road condition, surface and post-event passability",
        reason=(
            "The OSM highway classification is functional, not structural: it "
            "records that a way is a primary road, not whether it is paved, "
            "single-lane, landslide-prone or currently standing. No published "
            "condition inventory exists per district."
        ),
        consequence=(
            "A district scores well on LCC_ROADDIST for being near a road that "
            "may be unpaved, or that may be the exact road a landslide closes "
            "first. The variable measures the presence of classified "
            "infrastructure before the event, not its usability after it."
        ),
    ),
    DeclaredGap(
        subject="facility usability (power, staff, supplies, standing structure)",
        reason=(
            "OSM records that a building is tagged amenity=hospital. It records "
            "nothing about whether that hospital is operational, and after a "
            "catastrophic event that is the only thing that matters."
        ),
        consequence=(
            "A short distance in this dimension means a facility is NEARBY, "
            "never that care is AVAILABLE. The score describes the situation "
            "before the event; the hospital counted here may be the building "
            "that collapsed."
        ),
    ),
)
"""Every gap in this dimension, with the reason and the cost."""


def coping_variables_for_theme(theme: str) -> tuple[CopingVariable, ...]:
    """Return every declared variable of a sub-dimension, index and context alike."""
    return tuple(variable for variable in COPING_VARIABLES if variable.theme == theme)


def coping_index_variables_for_theme(theme: str) -> tuple[CopingVariable, ...]:
    """Return only the variables of a sub-dimension that feed its ``SPL`` sum."""
    return tuple(
        variable for variable in coping_variables_for_theme(theme) if variable.in_index
    )


LCC_THEMES: tuple[str, ...] = (INFRASTRUCTURE_THEME, INSTITUTIONAL_THEME)
"""Both sub-dimensions in publication order, including the empty one.

The institutional theme stays in this tuple on purpose. Dropping it would make
the gap invisible in the payload, and a reader would have no way to tell a
dimension built from one sub-dimension from a dimension built from two.
"""


@dataclass(frozen=True, slots=True)
class CopingVariableInput:
    """One district's raw ``E`` for one variable, with its universe.

    Args:
        variable: Key of a declared :class:`CopingVariable`.
        numerator: The raw estimate ``E`` -- person-metres for a distance
            variable, a population for a share, a feature count for a density --
            or None when it could not be measured.
        denominator: The universe ``E`` is divided by.
        suppressed_input_cells: How many of the cells summed into ``numerator``
            were withheld under statistical secrecy, carried for symmetry with
            the V dimension. The population figures behind these weights come
            from the already-screened census aggregates, so this is normally 0.
    """

    variable: str
    numerator: Decimal | None
    denominator: Decimal | None
    suppressed_input_cells: int = 0


@dataclass(frozen=True, slots=True)
class DistrictCopingInput:
    """Every declared variable's raw input for one district."""

    district_code: str
    district_name: str
    population: int
    variables: tuple[CopingVariableInput, ...]


@dataclass(frozen=True, slots=True)
class ScoredCopingVariable:
    """One variable's published audit trail: ``E``, ``EP`` and ``EPL``."""

    variable: str
    estimate: Decimal | None
    universe: int | None
    rate: Decimal | None
    percentile: Decimal | None
    in_index: bool
    suppressed: bool
    suppression_reason: str | None
    inputs_incomplete: bool
    maximum_undercount: int


@dataclass(frozen=True, slots=True)
class ScoredCopingTheme:
    """One sub-dimension's published ``SPL``, ``RPL`` and 0-10 score.

    ``declared_gap`` is True for a sub-dimension that carries no variable, which
    is how the institutional hole stays visible in a payload rather than looking
    like a district-specific suppression.
    """

    theme: str
    variable_count: int
    percentile_sum: Decimal | None
    percentile_rank: Decimal | None
    score: Decimal | None
    declared_gap: bool


@dataclass(frozen=True, slots=True)
class DistrictCoping:
    """One district's LCC score with the whole chain that produced it."""

    district_code: str
    district_name: str
    population: int | None
    variables: tuple[ScoredCopingVariable, ...]
    themes: tuple[ScoredCopingTheme, ...]
    theme_percentile_sum: Decimal | None
    theme_percentile_rank: Decimal | None
    cdc_score: Decimal | None
    score: Decimal | None
    rank: int | None
    inputs_incomplete: bool
    withheld: bool
    withheld_reason: str | None


@dataclass(frozen=True, slots=True)
class CopingRanking:
    """Every district's LCC score, ordered worst coping capacity first."""

    districts: tuple[DistrictCoping, ...]
    scored_unit_count: int
    withheld_unit_count: int
    scored_theme_count: int
    declared_gap_theme_count: int
    method: str = LCC_METHOD
    percentile_formula: str = PERCENTILE_RANK_FORMULA
    tie_rule: str = PERCENTILE_TIE_RULE
    aggregation_rule: str = INFORM_AGGREGATION_RULE
    distance_basis: str = DISTANCE_BASIS
    population_weighting_rule: str = POPULATION_WEIGHTING_RULE
    unit_of_analysis: str = LCC_UNIT_OF_ANALYSIS
    interpretation: str = LCC_SCORE_INTERPRETATION


@dataclass(frozen=True, slots=True)
class _ScreenedVariable:
    """Internal: one variable after disclosure screening, before ranking."""

    key: str
    in_index: bool
    estimate: Decimal | None
    universe: int | None
    rate: Decimal | None
    suppressed: bool
    inputs_incomplete: bool
    maximum_undercount: int


def _screen(
    raw: CopingVariableInput,
    declared: CopingVariable,
    policy: SuppressionPolicy,
) -> _ScreenedVariable:
    """Screen one raw input for disclosure and derive its publishable rate.

    Only the **denominator** is screened against the suppression policy, and the
    asymmetry is deliberate. A denominator here is always a resident population,
    so a district of two people must not have it published. A numerator is
    person-metres or a facility count, neither of which is a count of people:
    20,000 person-metres discloses nothing about anybody, and screening it
    against a three-person threshold would withhold a district for having a short
    road rather than a small population.
    """
    undercount = max(policy.minimum_units - 1, 0) * max(raw.suppressed_input_cells, 0)
    denominator_cell = policy.apply(raw.denominator)
    universe = None if denominator_cell.suppressed else denominator_cell.value

    unusable = (
        raw.numerator is None
        or denominator_cell.suppressed
        or denominator_cell.value in (None, Decimal(0))
    )
    if unusable:
        # The rate goes with the input: a mean distance published against a known
        # population is a reconstruction of the person-metres, and a distance
        # that could not be measured must never be read as a distance of zero.
        return _ScreenedVariable(
            key=declared.key,
            in_index=declared.in_index,
            estimate=None,
            universe=None if universe is None else int(universe),
            rate=None,
            suppressed=True,
            inputs_incomplete=raw.suppressed_input_cells > 0,
            maximum_undercount=undercount,
        )

    numerator = raw.numerator or Decimal(0)
    denominator = denominator_cell.value or Decimal(0)
    return _ScreenedVariable(
        key=declared.key,
        in_index=declared.in_index,
        estimate=numerator,
        universe=int(denominator),
        rate=numerator / denominator,
        suppressed=False,
        inputs_incomplete=raw.suppressed_input_cells > 0,
        maximum_undercount=undercount,
    )


def _screen_district(
    district: DistrictCopingInput,
    policy: SuppressionPolicy,
) -> dict[str, _ScreenedVariable]:
    """Screen every declared variable of one district, refusing an incomplete set."""
    supplied = {raw.variable: raw for raw in district.variables}
    missing = sorted(
        declared.key for declared in COPING_VARIABLES if declared.key not in supplied
    )
    if missing:
        raise CopingInputError(
            f"District {district.district_code} is missing declared variable(s) "
            f"{missing}. Every district has to supply every variable, because a "
            f"percentile is taken over one closed set of units and a silent "
            f"omission would rank the remaining districts against a different "
            f"population than the one published."
        )
    return {
        declared.key: _screen(supplied[declared.key], declared, policy)
        for declared in COPING_VARIABLES
    }


def _ranking_values(
    screened: Mapping[str, Mapping[str, _ScreenedVariable]],
    declared: CopingVariable,
    codes: Sequence[str],
) -> dict[str, Decimal]:
    """Collect one variable's rates, flipping the sign when high values are good.

    CDC ranks a variable whose high values are *good* in reverse -- per-capita
    income is its own example. Negating the rate is the arithmetically exact way
    to do that: it reverses the order without touching the published ``EP``, so
    the audit trail still shows the measured density and only the percentile
    knows the direction.
    """
    direction = Decimal(1) if declared.higher_is_worse else Decimal(-1)
    return {
        code: screened[code][declared.key].rate * direction
        for code in codes
        if screened[code][declared.key].rate is not None
    }


def score_coping(
    districts: Sequence[DistrictCopingInput],
    policy: SuppressionPolicy = CENSUS_SUPPRESSION_POLICY,
) -> CopingRanking:
    """Score the LCC dimension for a closed set of districts.

    The seven CDC steps run over the districts that can be scored, and the
    sub-dimension scores are composed by INFORM's geometric mean. Only the
    infrastructure sub-dimension carries variables today, so the composition
    reduces to the identity -- see :data:`COPING_DECLARED_GAPS`.

    A district whose index inputs could not be measured is published as a visible
    hole -- score ``None``, rank ``None`` -- and is excluded from every percentile
    denominator, so a gap costs that district its score without distorting
    anyone else's.

    Args:
        districts: One input record per district. The set is closed: percentiles
            are relative to exactly these units, which is why
            :attr:`CopingRanking.scored_unit_count` is published.
        policy: Disclosure policy applied to every published population figure.

    Raises:
        CopingInputError: If a district code repeats or a district omits a
            declared variable.
    """
    codes = [district.district_code for district in districts]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise CopingInputError(
            f"duplicate district code(s) {duplicates}: a district entering the "
            f"ranking twice is counted twice in every percentile denominator, "
            f"which moves every other district's rank for no reason."
        )

    screened = {
        district.district_code: _screen_district(district, policy)
        for district in districts
    }
    scoreable = [
        district.district_code
        for district in districts
        if all(
            not variable.suppressed
            for variable in screened[district.district_code].values()
            if variable.in_index
        )
    ]

    # EPL: one percentile set per variable, over the districts that can be ranked
    # on it. A context variable may be unmeasurable for a district that is
    # otherwise perfectly scoreable, which is why this is not simply `scoreable`.
    percentiles: dict[str, dict[str, Decimal]] = {
        declared.key: percentile_ranks_by_unit(
            _ranking_values(screened, declared, scoreable)
        )
        for declared in COPING_VARIABLES
    }

    # SPL and RPL: sum each theme's percentiles, then rank the sums. A theme with
    # no variable produces no sum and no rank -- not a sum of zero, which would
    # rank every district identically and then score them all at the median.
    scored_themes = tuple(
        theme for theme in LCC_THEMES if coping_index_variables_for_theme(theme)
    )
    theme_sums: dict[str, dict[str, Decimal]] = {
        theme: {
            code: sum(
                (
                    percentiles[member.key][code]
                    for member in coping_index_variables_for_theme(theme)
                ),
                Decimal(0),
            )
            for code in scoreable
        }
        for theme in scored_themes
    }
    theme_ranks = {
        theme: percentile_ranks_by_unit(sums) for theme, sums in theme_sums.items()
    }

    # SPL_THEMES and RPL_THEMES: CDC's own cross-theme composition, published as
    # the audit cross-check beside the INFORM geometric mean. Over one theme it
    # is that theme's own rank re-ranked, which is the identity, and publishing
    # it anyway keeps the two dimensions' payloads comparable.
    cross_theme_sums = {
        code: sum((theme_ranks[theme][code] for theme in scored_themes), Decimal(0))
        for code in scoreable
    }
    cross_theme_ranks = percentile_ranks_by_unit(cross_theme_sums)

    scored = [
        _assemble(
            district,
            screened[district.district_code],
            percentiles,
            theme_sums,
            theme_ranks,
            cross_theme_sums,
            cross_theme_ranks,
            policy,
        )
        for district in districts
    ]
    return CopingRanking(
        districts=_ranked(scored),
        scored_unit_count=len(set(scoreable)),
        withheld_unit_count=len(districts) - len(set(scoreable)),
        scored_theme_count=len(scored_themes),
        declared_gap_theme_count=len(LCC_THEMES) - len(scored_themes),
    )


def _assemble(
    district: DistrictCopingInput,
    screened: Mapping[str, _ScreenedVariable],
    percentiles: Mapping[str, Mapping[str, Decimal]],
    theme_sums: Mapping[str, Mapping[str, Decimal]],
    theme_ranks: Mapping[str, Mapping[str, Decimal]],
    cross_theme_sums: Mapping[str, Decimal],
    cross_theme_ranks: Mapping[str, Decimal],
    policy: SuppressionPolicy,
) -> DistrictCoping:
    """Assemble one district's published record from the ranked intermediates."""
    code = district.district_code
    withheld = code not in cross_theme_ranks

    variables = tuple(
        ScoredCopingVariable(
            variable=declared.key,
            estimate=screened[declared.key].estimate,
            universe=screened[declared.key].universe,
            rate=screened[declared.key].rate,
            percentile=percentiles[declared.key].get(code),
            in_index=declared.in_index,
            suppressed=screened[declared.key].suppressed,
            suppression_reason=(
                f"{policy.label} ({STATISTICAL_SECRECY_REFERENCE})"
                if screened[declared.key].suppressed
                else None
            ),
            inputs_incomplete=screened[declared.key].inputs_incomplete,
            maximum_undercount=screened[declared.key].maximum_undercount,
        )
        for declared in COPING_VARIABLES
    )

    themes = tuple(
        ScoredCopingTheme(
            theme=theme,
            variable_count=len(coping_index_variables_for_theme(theme)),
            percentile_sum=theme_sums.get(theme, {}).get(code),
            percentile_rank=theme_ranks.get(theme, {}).get(code),
            score=(
                rescale_to_score(theme_ranks[theme][code])
                if theme in theme_ranks and code in theme_ranks[theme]
                else None
            ),
            declared_gap=not coping_index_variables_for_theme(theme),
        )
        for theme in LCC_THEMES
    )

    population_cell = policy.apply(district.population)
    theme_scores = [theme.score for theme in themes if theme.score is not None]
    score = None if withheld or not theme_scores else inform_geometric_mean(
        theme_scores
    )
    return DistrictCoping(
        district_code=code,
        district_name=district.district_name,
        population=(
            None if population_cell.suppressed else int(population_cell.value or 0)
        ),
        variables=variables,
        themes=themes,
        theme_percentile_sum=cross_theme_sums.get(code),
        theme_percentile_rank=cross_theme_ranks.get(code),
        cdc_score=None if withheld else rescale_to_score(cross_theme_ranks[code]),
        score=score,
        rank=None,
        inputs_incomplete=any(variable.inputs_incomplete for variable in variables),
        withheld=withheld,
        withheld_reason=(
            f"No LCC score is published for this district: at least one index "
            f"input could not be measured on the published corpus, so a score "
            f"would have been computed over a hole. Where the cause is a "
            f"population below the disclosure threshold, the applicable policy "
            f"is {policy.label} ({STATISTICAL_SECRECY_REFERENCE})."
            if withheld
            else None
        ),
    )


def _ranked(districts: Sequence[DistrictCoping]) -> tuple[DistrictCoping, ...]:
    """Order districts worst-coping-capacity first and assign competition ranks.

    Tied scores share one rank, because the alternative is deciding which
    district a brigade reaches first by the ``ORDER BY`` of a query. Districts
    with no score sort last, so a gap is visible instead of shortening the list,
    and they carry no rank at all.
    """
    scoreable = sorted(
        (district for district in districts if district.score is not None),
        key=lambda district: (-district.score, district.district_code),  # type: ignore[operator]
    )
    withheld = sorted(
        (district for district in districts if district.score is None),
        key=lambda district: district.district_code,
    )

    ranked: list[DistrictCoping] = []
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


def _with_rank(district: DistrictCoping, rank: int) -> DistrictCoping:
    """Return the district with its rank filled in, leaving the record frozen."""
    return DistrictCoping(
        district_code=district.district_code,
        district_name=district.district_name,
        population=district.population,
        variables=district.variables,
        themes=district.themes,
        theme_percentile_sum=district.theme_percentile_sum,
        theme_percentile_rank=district.theme_percentile_rank,
        cdc_score=district.cdc_score,
        score=district.score,
        rank=rank,
        inputs_incomplete=district.inputs_incomplete,
        withheld=district.withheld,
        withheld_reason=district.withheld_reason,
    )
