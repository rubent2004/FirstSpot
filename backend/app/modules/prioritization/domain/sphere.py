"""Sphere Handbook 2018 minimum requirements, translated from exposed population.

This module converts an estimated exposed population into the quantities the
Sphere Handbook publishes as **minimum standards**. The arithmetic is trivial and
exact; everything difficult here is about what the resulting numbers are allowed
to be called.

The label is load-bearing
-------------------------
Every figure is a **"Sphere minimum requirement"**: the floor below which a
response is failing a published humanitarian standard. It is never "resources to
deliver", never a procurement list and never a target. The distinction is not
pedantry -- there is published criticism that treating Sphere figures as planning
targets, in situations where needs exceed response capacity, promotes
inappropriate planning: a brigade told it needs 150,000 litres a day and able to
move 20,000 can conclude the operation is impossible, when the operational
question is how to allocate 20,000 litres among the people who need them most.
Sphere answers "is this enough", not "what shall we send". See
:data:`SPHERE_NOT_A_DELIVERY_TARGET`.

For the same reason a requirement is never compared against available capacity.
C2 established that **shelter capacity is unmeasured** in this system -- no
shelter register is published per district, and the OSM proxy was rejected on
measured evidence -- so a shelter-area requirement here has nothing to be
subtracted from. A "gap" figure would require a capacity figure that does not
exist.

Rounding goes up, because the standard is a minimum
---------------------------------------------------
``water_taps_minimum`` is the one derived count rather than a product, and it
rounds **up**. Sphere's indicator is a *maximum of 250 people per tap*, so 251
people need two taps and not 1.004: rounding down would publish a figure that
breaches the standard it claims to state. The products -- litres, kilocalories,
square metres -- are exact by construction because the multipliers are integers
or exact decimals, and :class:`~decimal.Decimal` keeps them that way.
"""

from dataclasses import dataclass
from decimal import Decimal

WATER_LITRES_PER_PERSON_PER_DAY = 15
"""Sphere 2018 WASH: basic survival water needs, drinking and hygiene."""

WATER_LITRES_PER_PERSON_PER_DAY_EXTREME_HEAT = 20
"""Sphere 2018 WASH: the figure under extreme heat or high physical exertion.

Published beside the 15-litre figure rather than instead of it, because choosing
between them needs an observed temperature at the district at the time of
response. That is an operational judgement, and nothing in this index measures
it: a hard-coded choice would be a weather claim this system cannot support.
"""

PEOPLE_PER_WATER_TAP = 250
"""Sphere 2018 WASH: maximum people per tap. A maximum, hence the round up."""

WATER_POINT_MAXIMUM_DISTANCE_METRES = 500
"""Sphere 2018 WASH: maximum distance from any shelter to the nearest water point.

A distance standard rather than a quantity, so it is published as a constraint to
check against a site plan and never multiplied by anything. Note that LCC's own
distances are geodesic lower bounds and cannot verify it.
"""

FOOD_KCAL_PER_PERSON_PER_DAY = 2100
"""Sphere 2018 Food Security: planning figure for a population's energy needs."""

SHELTER_M2_PER_PERSON = Decimal("3.5")
"""Sphere 2018 Shelter: minimum covered living area per person."""

SHELTER_M2_PER_PERSON_URBAN_WITH_INTERNAL_SERVICES = Decimal("4.5")
"""Sphere 2018 Shelter: the figure where cooking and sanitation are internal.

Sphere raises the area when kitchen, bathing and sanitation facilities sit inside
the covered area rather than in shared external blocks, which is the normal
arrangement for urban collective shelter in adapted buildings.
"""

SPHERE_SOURCE = (
    "Sphere Handbook 2018 (Sphere Association, Humanitarian Charter and Minimum "
    "Standards in Humanitarian Response, 4th edition): WASH water supply "
    "standard 1, Food Security nutrition requirements, Shelter and Settlement "
    "standard 3."
)
"""Provenance published with every requirement."""

SPHERE_REQUIREMENT_LABEL = "Sphere minimum requirement"
"""The only label these figures carry. Checked by a test."""

SPHERE_NOT_A_DELIVERY_TARGET = (
    "These are MINIMUM REQUIREMENTS from a published humanitarian standard, not "
    "resources to send and not a procurement list. They answer 'would this "
    "response meet the standard', never 'what shall we deliver'. There is "
    "published criticism that treating Sphere figures as planning targets, where "
    "needs exceed available response capacity, promotes inappropriate planning: a "
    "brigade told a district requires 150,000 litres a day and able to move "
    "20,000 can conclude the operation is impossible, when the real question is "
    "how to allocate what exists. Nor is any figure here a gap: this system does "
    "not know what capacity is available. Shelter capacity in particular is a "
    "DECLARED GAP -- no shelter register is published per district and the "
    "OpenStreetMap proxy was rejected on measured evidence -- so a shelter-area "
    "requirement has nothing it can legitimately be subtracted from."
)
"""The caveat that travels with every requirement figure."""

SPHERE_POPULATION_BASIS = (
    "P is the ESTIMATED EXPOSED POPULATION: residents estimated to live where "
    "modelled ShakeMap intensity reaches MMI VI or above, by areal weighting "
    "under the declared uniform-density assumption. It is not a count of people "
    "displaced, not a count of people needing assistance, and not a casualty "
    "figure of any kind. Exposure is a location, not an outcome: many exposed "
    "people will need nothing, and the requirement is therefore an upper bound "
    "on the standard for this population rather than a measured need."
)
"""What the P in every formula is, published with every requirement."""


@dataclass(frozen=True, slots=True)
class SphereRequirement:
    """Sphere 2018 minimum requirements for one exposed population.

    Every field is a *minimum to meet a published standard*. See
    :data:`SPHERE_NOT_A_DELIVERY_TARGET` before presenting any of them.
    """

    exposed_population: int
    water_litres_per_day: int
    water_litres_per_day_extreme_heat: int
    water_taps_minimum: int
    water_point_maximum_distance_metres: int
    food_kcal_per_day: int
    shelter_area_m2: Decimal
    shelter_basis: str
    urban_with_internal_services: bool
    population_basis: str = SPHERE_POPULATION_BASIS
    label: str = SPHERE_REQUIREMENT_LABEL
    caveat: str = SPHERE_NOT_A_DELIVERY_TARGET
    source: str = SPHERE_SOURCE


def _taps(exposed_population: int) -> int:
    """Return the minimum tap count, rounding up because 250 is a maximum."""
    if exposed_population <= 0:
        return 0
    # Ceiling division on integers: exact, and never a float that rounds 250/250
    # to 1.0000000000000002.
    return -(-exposed_population // PEOPLE_PER_WATER_TAP)


def sphere_minimum_requirements(
    exposed_population: int,
    urban_with_internal_services: bool = False,
) -> SphereRequirement:
    """Translate an exposed population into Sphere 2018 minimum requirements.

    Args:
        exposed_population: Estimated residents inside the MMI VI band. Zero is
            valid and yields zero requirements.
        urban_with_internal_services: True when cooking, bathing and sanitation
            are inside the covered area, which raises Sphere's minimum living
            area from 3.5 to 4.5 m² per person.

    Raises:
        ValueError: If the population is negative, which is an upstream defect
            rather than a quantity to translate.
    """
    if exposed_population < 0:
        raise ValueError(
            f"Cannot translate a negative exposed population "
            f"({exposed_population}) into a minimum requirement. A negative "
            f"count is an upstream defect in the zonal statistics, and clamping "
            f"it to zero here would publish a requirement of nothing for a "
            f"district whose geometry is broken."
        )
    area_per_person = (
        SHELTER_M2_PER_PERSON_URBAN_WITH_INTERNAL_SERVICES
        if urban_with_internal_services
        else SHELTER_M2_PER_PERSON
    )
    return SphereRequirement(
        exposed_population=exposed_population,
        water_litres_per_day=WATER_LITRES_PER_PERSON_PER_DAY * exposed_population,
        water_litres_per_day_extreme_heat=(
            WATER_LITRES_PER_PERSON_PER_DAY_EXTREME_HEAT * exposed_population
        ),
        water_taps_minimum=_taps(exposed_population),
        water_point_maximum_distance_metres=WATER_POINT_MAXIMUM_DISTANCE_METRES,
        food_kcal_per_day=FOOD_KCAL_PER_PERSON_PER_DAY * exposed_population,
        shelter_area_m2=area_per_person * Decimal(exposed_population),
        shelter_basis=(
            f"{area_per_person} m2 per person"
            + (
                " (urban collective shelter with internal cooking, bathing and "
                "sanitation facilities)"
                if urban_with_internal_services
                else " (covered living area with shared external facilities)"
            )
        ),
        urban_with_internal_services=urban_with_internal_services,
    )
