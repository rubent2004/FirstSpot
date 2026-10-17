"""The CDC/ATSDR SVI percentile-ranking step, implemented exactly as published.

Source: CDC/ATSDR Social Vulnerability Index 2022 Documentation. The method is a
chain of seven named steps, and this module owns the one that does all the work:

===========  ==================================================================
``E``        raw estimate of a variable for one unit
``EP``       that estimate expressed as a percentage or ratio of its universe
``EPL``      **percentile rank of each variable across all units, 0 to 1**
``SPL``      sum of the ``EPL`` values belonging to one theme
``RPL``      percentile rank of that theme's ``SPL``
=========== ===================================================================

Why percentile ranking and not a principal component
----------------------------------------------------
Spielman et al. (2020), *Natural Hazards* 100:417-436, showed that SoVI-style
PCA rankings **do not converge when the set of units changes**: a district's rank
moves because an unrelated district was added to the analysis. For an index that
decides who is attended first, that is disqualifying. Percentile ranking is also
relative -- adding a unit does move ranks -- but it moves them *monotonically and
explainably*, and it never changes a unit's own measured inputs. That difference
is what :func:`percentile_ranks` is tested for.

Why equal weights
-----------------
CDC/ATSDR assigns every variable inside a theme the same weight by construction:
``SPL`` is a plain sum of percentiles. This module therefore exposes no weighting
parameter at all. The only declared weight anywhere in PRIO-SV is INFORM's 1/3
per top-level dimension, and it lives in :mod:`.inform`, not here.

The tie rule, and why it is the mean rank
-----------------------------------------
Two units with the same rate must receive the same percentile, or else which one
is prioritised would depend on a query's ``ORDER BY`` rather than on anything
about the unit. That leaves the choice of *which* shared value, and it is not
cosmetic for this corpus: 102 of the 262 Salvadoran districts have a rural
population share of exactly 1.0.

* A **minimum**-rank tie rule would put all 102 at 0.613 and, in the degenerate
  case of a variable with one repeated value, would rank every unit at 0 --
  silently deleting that variable from its theme's sum.
* The **mean**-rank rule used here (SPSS ``RANK`` ``TIES=MEAN``, which is the
  CDC toolchain's default) puts those 102 at 0.807 and a non-discriminating
  variable at 0.5 for every unit, which is what "this variable separates nobody"
  should mean.

The rule is published with every score as :data:`PERCENTILE_TIE_RULE` so the
choice is auditable rather than buried.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal

PERCENTILE_RANK_FORMULA = (
    "(rank - 1) / (N - 1) over all ranked units, CDC/ATSDR SVI 2022 Documentation"
)
"""The published EPL/RPL formula, returned with every score for auditability."""

PERCENTILE_TIE_RULE = (
    "mean rank: tied units share the mean of the ordinal ranks they span, so a "
    "tie is never resolved by input order and a variable that separates nobody "
    "ranks every unit at 0.5 instead of 0"
)
"""The declared tie rule, published with every score."""

SCORE_FLOOR = Decimal(0)
"""Lowest value of the 0-10 INFORM-compatible score range."""

SCORE_CEILING = Decimal(10)
"""Highest value of the 0-10 INFORM-compatible score range."""

MEDIAN_PERCENTILE = Decimal("0.5")
"""Percentile assigned when no unit can be separated from any other.

This is the limit of ``(rank - 1) / (N - 1)`` under the mean-rank tie rule: when
every unit shares one value its mean rank is ``(N + 1) / 2``, which gives 0.5 for
any ``N`` above one, and the single-unit case is defined to agree with it rather
than to divide by zero.
"""


def percentile_ranks(values: Sequence[Decimal]) -> list[Decimal]:
    """Return the CDC ``EPL`` percentile rank of every value, in input order.

    Args:
        values: One value per ranked unit. Higher must already mean *worse*;
            a variable whose direction is inverted is inverted by its caller,
            because the direction belongs to the variable's definition and not
            to the ranking arithmetic.

    Returns:
        One percentile in the closed interval [0, 1] per input value, positioned
        to match the input sequence. The minimum value ranks 0 and the maximum
        ranks 1 whenever they are unique.
    """
    unit_count = len(values)
    if unit_count == 0:
        return []
    if unit_count == 1:
        return [MEDIAN_PERCENTILE]

    # Ordinal rank of the first occurrence of each distinct value, plus the span
    # it covers, is all the mean-rank rule needs: a value tied k ways starting at
    # ordinal rank r spans r..r+k-1, whose mean is r + (k - 1) / 2.
    ascending = sorted(values)
    first_rank: dict[Decimal, int] = {}
    tie_count: dict[Decimal, int] = {}
    for position, value in enumerate(ascending, start=1):
        if value not in first_rank:
            first_rank[value] = position
        tie_count[value] = tie_count.get(value, 0) + 1

    divisor = Decimal(unit_count - 1)
    return [
        (
            Decimal(first_rank[value])
            + (Decimal(tie_count[value]) - 1) / 2
            - 1
        )
        / divisor
        for value in values
    ]


def percentile_ranks_by_unit(
    values_by_unit: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Return the percentile rank of every unit, keyed by unit code.

    The keyed form exists so that a percentile cannot be mis-paired with the
    district it describes: the positional form is convenient to hand-verify, and
    zipping it back onto unit codes is exactly where such a bug would live.
    """
    keys = list(values_by_unit)
    ranks = percentile_ranks([values_by_unit[key] for key in keys])
    return dict(zip(keys, ranks, strict=True))


def rescale_to_score(percentile: Decimal) -> Decimal:
    """Rescale a 0-1 percentile onto the 0-10 range INFORM aggregates on.

    Args:
        percentile: A value in the closed interval [0, 1], normally an ``EPL`` or
            an ``RPL``.

    Raises:
        ValueError: If the value is not a percentile. A score outside 0-10 would
            break the INFORM rescale downstream, so it is refused here where the
            cause is still visible.
    """
    if percentile < 0 or percentile > 1:
        raise ValueError(
            f"Expected a percentile in [0, 1], got {percentile}. Only an EPL or "
            f"an RPL may be rescaled onto the 0-10 INFORM range."
        )
    return percentile * SCORE_CEILING
