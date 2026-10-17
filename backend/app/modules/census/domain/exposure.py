"""Areal-weighted estimation of the population exposed around a point.

Nothing in this module produces a count of people. It produces an **estimate of
how many residents the census places inside a radius**, which is a different
quantity from how many people are there: the CPV 2024 records where people
*sleep*, not where they were at the moment of an event. Every public name here
carries ``estimated_`` for that reason.

Spatial assignment rule
-----------------------
The rule is declared, not implied, because the choice changes the answer by
orders of magnitude. :data:`SPATIAL_ASSIGNMENT_RULE` is the single source of that
declaration and it is published with every estimate.

*Intersection with areal weighting* is used: a DEGURBA polygon that overlaps the
buffer contributes its population **in proportion to the share of its own area
that falls inside the buffer**. The two alternatives were rejected:

* *Centroid containment* assigns a polygon's entire population when its centroid
  falls inside and nothing otherwise. For the 902 DEGURBA units, whose median
  area is far larger than an operational 500 m buffer, that is a step function:
  it reports either a whole sub-district or zero.
* *Plain intersection* assigns a polygon's entire population whenever it merely
  touches the buffer, which over-counts by the ratio of polygon area to buffer
  area -- a factor of hundreds for a large rural unit.

Areal weighting assumes population is **uniformly distributed inside each
DEGURBA polygon** (:data:`UNIFORM_DENSITY_ASSUMPTION`). That is an assumption,
not a measurement. It is also the reason DEGURBA was chosen over the district:
the assumption is applied over a unit 3.4x finer, and DEGURBA's own
degree-of-urbanisation classes already separate dense from sparse settlement, so
the uniformity being assumed is assumed within a class rather than across one.

Metric projection
-----------------
Area ratios are computed in a metric projection, never in 4326 degrees, because
a square degree is not a constant area. The brief for this work specified
EPSG:5399 as "SIRGAS-ES2007"; that code **does not exist** in the EPSG registry
(it is absent from PROJ's ``crs_view`` and from PostGIS ``spatial_ref_sys``), and
the SIRGAS-ES2007.8 family that does exist -- 5391, 5392, 5393 -- is geodetic
only, with no projected metric member. :data:`METRIC_PROJECTION_SRID` is
therefore EPSG:32616, WGS 84 / UTM zone 16N, which:

* is installed (asserted by the test suite rather than assumed);
* shares the WGS 84 datum with the stored ``GEOGRAPHY(..., 4326)`` columns, so
  the transform is a pure projection with no datum shift and no PROJ "ballpark"
  fallback -- unlike EPSG:5460, El Salvador Lambert on the 1935 Ocotepeque datum;
* was measured against geodesic spheroid area on the westernmost DEGURBA unit,
  the worst case for a zone whose central meridian is 87W: the resulting areal
  weight differed from the geodesic weight by 1.5e-6 relative. Area ratios are
  taken between two areas inside one small polygon, so projection scale error
  very nearly cancels.

Vulnerable proportions
----------------------
Age structure and disability are published **only at district level**. They are
applied here as a *rate* onto :class:`UnitOverlap.population`, never as an
absolute count, because a DEGURBA polygon has no age pyramid of its own and the
district count belongs to a territory 3.4x larger. This assumes the rate is
**uniform within the district** (:data:`UNIFORM_DISTRICT_RATE_ASSUMPTION`), which
is again an assumption and not a measurement: a district's older-adult share
genuinely differs between its urban core and its rural fringe, and this method
cannot see that difference.

:func:`apply_vulnerable_rate` refuses any multiplier outside [0, 1]. That guard
exists specifically to make the "rate, not count" rule mechanical: passing a
district's 12,090 older adults where its 0.095 share belongs raises instead of
silently producing an estimate larger than the national population.

Disclosure
----------
Estimates are screened by the shared :mod:`app.core.privacy` policy before they
leave the API, and the census module's rule is preserved: a withheld total
withholds every figure derived from it, because a derived sub-population
published against a known total discloses the withheld total.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.privacy import CENSUS_SUPPRESSION_POLICY, SuppressionPolicy

SPATIAL_ASSIGNMENT_RULE = (
    "Intersection with areal weighting: a DEGURBA population unit contributes "
    "its population in proportion to the share of its own area that falls inside "
    "the buffer, computed in EPSG:32616. Centroid containment and plain "
    "intersection are both rejected, because the first reports a whole "
    "sub-district or zero and the second assigns a whole sub-district to any "
    "polygon that merely touches the buffer."
)
"""The declared spatial assignment rule, published with every estimate."""

EXPOSURE_ESTIMATION_METHOD = "areal weighting of CPV 2024 DEGURBA units (estimate)"
"""Short method label. It says "estimate" because the figure is one."""

UNIFORM_DENSITY_ASSUMPTION = (
    "Population is assumed uniformly distributed within each DEGURBA polygon. "
    "This is an assumption, not a measurement: a partially covered unit "
    "contributes by area share, so an estimate is wrong in proportion to how "
    "unevenly that unit is actually settled."
)
"""Assumption a reader of the exposed-population figure has to know about."""

UNIFORM_DISTRICT_RATE_ASSUMPTION = (
    "Age structure (65 and over, under 5) and disability exist only at district "
    "level, so their rates are assumed uniform within the district and applied "
    "to the finer DEGURBA population. This is an assumption, not a measurement: "
    "the finer polygon has no age pyramid of its own."
)
"""Assumption a reader of the vulnerable sub-population figures has to know about."""

CENSUS_REFERENCE_PERIOD = (
    "CPV 2024 records residence, not presence: it says where people sleep, not "
    "where they were when the event happened."
)
"""The temporal caveat that stops an exposure estimate reading as a headcount."""

METRIC_PROJECTION_SRID = 32616
"""EPSG:32616, WGS 84 / UTM zone 16N: the metric projection used for area maths."""

METRIC_PROJECTION_NAME = "EPSG:32616 (WGS 84 / UTM zone 16N)"
"""Human-readable name of the metric projection, for the published methodology."""

DEFAULT_EXPOSURE_RADIUS_METERS = 500
"""Default operational radius, matching the 500 m neighbour radius already used
for place density and the Sphere Handbook's 500 m maximum to a water point."""

MAX_EXPOSURE_RADIUS_METERS = 20_000
"""Largest radius an on-demand estimate will compute, to bound query cost."""

AREAL_WEIGHT_EXCESS_TOLERANCE = Decimal("0.01")
"""Relative overlap excess tolerated as geometry noise before raising.

``ST_Intersection`` of a simplified polygon against a buffer can return a
fractionally larger area than the polygon itself. Up to this fraction the weight
saturates at 1; beyond it the input is a defect and must not be absorbed.
"""


class ArealWeightError(ValueError):
    """Raised when an areal weight cannot be computed from the given areas."""


class VulnerableRateError(ValueError):
    """Raised when a vulnerable proportion is not a rate in the interval [0, 1]."""


def areal_weight(overlap_area_m2: Decimal, unit_area_m2: Decimal) -> Decimal:
    """Return the share of a population unit's area that falls inside the buffer.

    Args:
        overlap_area_m2: Area of the intersection of the unit and the buffer.
        unit_area_m2: Total area of the population unit.

    Returns:
        The ratio in [0, 1], as an exact Decimal division.

    Raises:
        ArealWeightError: If either area is negative, if the unit has zero area,
            or if the overlap exceeds the unit by more than
            :data:`AREAL_WEIGHT_EXCESS_TOLERANCE`.
    """
    if overlap_area_m2 < 0 or unit_area_m2 < 0:
        raise ArealWeightError(
            f"Areas cannot be negative: overlap={overlap_area_m2}, "
            f"unit={unit_area_m2}. No geometry has a negative area."
        )
    if unit_area_m2 == 0:
        raise ArealWeightError(
            "Cannot weight a population unit of zero area: the areal share "
            "would divide by zero. A degenerate polygon must be excluded "
            "upstream rather than weighted."
        )
    if overlap_area_m2 > unit_area_m2 * (Decimal(1) + AREAL_WEIGHT_EXCESS_TOLERANCE):
        raise ArealWeightError(
            f"Overlap area {overlap_area_m2} exceeds unit area {unit_area_m2} by "
            f"more than {AREAL_WEIGHT_EXCESS_TOLERANCE:%}. An intersection cannot "
            f"be larger than the geometry it clips, so this is a defect rather "
            f"than simplification noise."
        )
    if overlap_area_m2 >= unit_area_m2:
        return Decimal(1)
    return overlap_area_m2 / unit_area_m2


def weighted_population(population: int, unit_weight: Decimal) -> Decimal:
    """Return the share of a unit's population attributed to the buffer.

    Args:
        population: Resident population the census publishes for the whole unit.
        unit_weight: Areal weight from :func:`areal_weight`, in [0, 1].

    Raises:
        ArealWeightError: If the population is negative or the weight is not in [0, 1].
    """
    if population < 0:
        raise ArealWeightError(
            f"Population cannot be negative, got {population}: a unit holding "
            f"nobody holds zero people, never fewer."
        )
    if unit_weight < 0 or unit_weight > 1:
        raise ArealWeightError(
            f"Areal weight {unit_weight} is outside [0, 1]; it is an area share."
        )
    return Decimal(population) * unit_weight


def apply_vulnerable_rate(
    population_estimate: Decimal,
    rate: Decimal,
) -> Decimal:
    """Scale an exposed-population estimate by a district vulnerable-group rate.

    The multiplier must be a proportion. Passing a district's absolute count
    raises, which is the mechanical form of the rule that district age structure
    and disability are applied as rates onto the finer DEGURBA population and
    never as counts.

    Raises:
        VulnerableRateError: If ``rate`` is outside [0, 1].
    """
    if rate < 0 or rate > 1:
        raise VulnerableRateError(
            f"A vulnerable-group proportion must be a rate in [0, 1], got {rate}. "
            f"District age structure and disability are published as counts for a "
            f"territory 3.4x larger than a DEGURBA unit; apply the share, not the "
            f"count."
        )
    if population_estimate < 0:
        raise VulnerableRateError(
            f"Cannot apply a rate to a negative population estimate, "
            f"got {population_estimate}."
        )
    return population_estimate * rate


# Aliased because UnitOverlap exposes methods of the same name, and reading
# `return areal_weight(...)` inside `def areal_weight(self)` invites a
# second-guess about recursion that the aliases remove.
_compute_areal_weight = areal_weight
_compute_weighted_population = weighted_population


@dataclass(frozen=True, slots=True)
class UnitOverlap:
    """One DEGURBA population unit's overlap with a buffer, with metric areas."""

    unit_id: int
    district_code: str
    population: int
    unit_area_m2: Decimal
    overlap_area_m2: Decimal

    def areal_weight(self) -> Decimal:
        """Return the share of this unit's area that falls inside the buffer."""
        return _compute_areal_weight(self.overlap_area_m2, self.unit_area_m2)

    def weighted_population(self) -> Decimal:
        """Return this unit's estimated contribution to the exposed population."""
        return _compute_weighted_population(self.population, self.areal_weight())


@dataclass(frozen=True, slots=True)
class DistrictVulnerableRates:
    """District-level vulnerable proportions, validated as rates rather than counts."""

    district_code: str
    older_adult_rate: Decimal
    young_child_rate: Decimal
    disability_rate: Decimal

    def __post_init__(self) -> None:
        """Reject any proportion that is not a rate in [0, 1]."""
        for name in ("older_adult_rate", "young_child_rate", "disability_rate"):
            value = getattr(self, name)
            if value < 0 or value > 1:
                raise VulnerableRateError(
                    f"District {self.district_code} {name} is {value}, which is "
                    f"not a rate in [0, 1]. A count was probably supplied where a "
                    f"share belongs."
                )


@dataclass(frozen=True, slots=True)
class ExposedPopulationEstimate:
    """A published exposure estimate, already screened for statistical secrecy.

    Every measure is an estimate of resident population inside a radius. None of
    them is a count of people present, and ``None`` means withheld or unknown,
    never zero.
    """

    radius_meters: int
    contributing_unit_count: int
    estimated_exposed_population: int | None
    estimated_exposed_older_adults: int | None
    estimated_exposed_young_children: int | None
    estimated_exposed_persons_with_disability: int | None
    suppressed: bool
    suppression_reason: str | None


def _to_published_integer(value: Decimal) -> int:
    """Round an estimate to the whole person that will actually be published."""
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def estimate_exposed_population(
    overlaps: Iterable[UnitOverlap],
    rates_by_district: Mapping[str, DistrictVulnerableRates],
    radius_meters: int,
    policy: SuppressionPolicy = CENSUS_SUPPRESSION_POLICY,
) -> ExposedPopulationEstimate:
    """Estimate the population exposed inside a radius by areal weighting.

    Each overlapping DEGURBA unit contributes its population in proportion to the
    share of its own area inside the buffer, and each contribution is multiplied
    by *its own* district's vulnerable-group rates before being summed, so a
    buffer spanning two districts does not borrow one district's age structure.

    A contributing district with no published rates withholds the derived
    sub-populations entirely rather than contributing zero, because treating an
    unpublished rate as zero would understate the result while looking precise.

    Args:
        overlaps: Overlapping units with their metric areas.
        rates_by_district: District rates, keyed by six-character district code.
        radius_meters: Radius the estimate applies to; published with the result.
        policy: Disclosure policy applied to every published figure.

    Raises:
        ValueError: If ``radius_meters`` is not a positive distance.
    """
    if radius_meters <= 0:
        raise ValueError(
            f"An exposure radius must be a positive distance, got {radius_meters} m."
        )

    exposed = Decimal(0)
    older_adults = Decimal(0)
    young_children = Decimal(0)
    with_disability = Decimal(0)
    contributing = 0
    rates_are_complete = True

    for overlap in overlaps:
        contribution = overlap.weighted_population()
        if contribution <= 0:
            continue
        contributing += 1
        exposed += contribution
        rates = rates_by_district.get(overlap.district_code)
        if rates is None:
            rates_are_complete = False
            continue
        older_adults += apply_vulnerable_rate(contribution, rates.older_adult_rate)
        young_children += apply_vulnerable_rate(contribution, rates.young_child_rate)
        with_disability += apply_vulnerable_rate(contribution, rates.disability_rate)

    published_total = policy.apply(_to_published_integer(exposed))
    if published_total.suppressed:
        # A derived sub-population published against a withheld total discloses
        # that total, so the whole estimate is withheld together.
        return ExposedPopulationEstimate(
            radius_meters=radius_meters,
            contributing_unit_count=contributing,
            estimated_exposed_population=None,
            estimated_exposed_older_adults=None,
            estimated_exposed_young_children=None,
            estimated_exposed_persons_with_disability=None,
            suppressed=True,
            suppression_reason=policy.label,
        )

    def publish(measure: Decimal) -> int | None:
        """Screen one derived sub-population on its own account."""
        if not rates_are_complete:
            return None
        cell = policy.apply(_to_published_integer(measure))
        return None if cell.suppressed else int(cell.value or 0)

    older = publish(older_adults)
    young = publish(young_children)
    disabled = publish(with_disability)
    any_withheld = rates_are_complete and None in (older, young, disabled)

    return ExposedPopulationEstimate(
        radius_meters=radius_meters,
        contributing_unit_count=contributing,
        estimated_exposed_population=int(published_total.value or 0),
        estimated_exposed_older_adults=older,
        estimated_exposed_young_children=young,
        estimated_exposed_persons_with_disability=disabled,
        suppressed=any_withheld or not rates_are_complete,
        suppression_reason=(
            policy.label if any_withheld or not rates_are_complete else None
        ),
    )
