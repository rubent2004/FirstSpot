"""INFORM's equal-weight geometric aggregation, including the [1, 10] rescale.

Source: INFORM Concept and Methodology, Version 2017, Equation 1 -- *"a
multiplicative equation where each of the dimensions is treated equally"*. PRIO-SV
composes its three top-level dimensions exactly that way::

    PRIO = (H&E)^(1/3) x (V)^(1/3) x (LCC)^(1/3)

and the 1/3 exponent is the **only declared weight anywhere in the index**. Every
other aggregation is an unweighted sum of percentiles under the CDC/ATSDR method
in :mod:`.percentile`.

Why a geometric mean destroys zeros, and when that is wanted
------------------------------------------------------------
A geometric mean is zero whenever any factor is zero. At the **top level that is
the point**: a district with no ground shaking must not be prioritised for an
earthquake response merely for being poor, so a zero hazard has to zero the risk.

Inside a dimension it is the opposite. A district that is maximally vulnerable on
one sub-dimension and not at all on the other is still vulnerable, and a plain
geometric mean would report zero. INFORM's answer is to rescale onto [1, 10]
before multiplying, which removes the annihilating element while keeping the
geometric mean's conservatism. :func:`inform_geometric_mean` implements that as
five explicit steps:

1. **invert**, so higher means *better* -- the geometric mean penalises low
   values, and the value that should be penalised is the good one;
2. **rescale** [0, 10] onto [1, 10], removing the zero;
3. take the **geometric mean**, equal weights;
4. **rescale** [1, 10] back onto [0, 10];
5. **re-invert**, returning to a badness score.

The composition is an identity on equal inputs, which is the cheapest available
detector of a broken rescale, and it maps (0, 10) to 7.597 rather than to 0.

Exactness
---------
Everything is :class:`~decimal.Decimal`. The two-factor case uses
:meth:`~decimal.Decimal.sqrt`, which is correctly rounded, so the equal-input
identity holds *exactly* rather than to 27 digits; the n-ary case needs
``exp(sum(ln) / n)`` because Decimal has no n-th root, and is therefore exact only
to the context's precision. V has exactly two sub-dimensions, so the published
Vulnerability score always takes the exact path.
"""

from collections.abc import Sequence
from decimal import Decimal

SCORE_FLOOR = Decimal(0)
"""Lowest value of a published INFORM-compatible dimension score."""

SCORE_CEILING = Decimal(10)
"""Highest value of a published INFORM-compatible dimension score."""

INFORM_RESCALE_FLOOR = Decimal(1)
"""Lower bound of the interval INFORM multiplies on, chosen to exclude zero."""

INFORM_RESCALE_CEILING = Decimal(10)
"""Upper bound of the interval INFORM multiplies on."""

INFORM_AGGREGATION_RULE = (
    "Equally weighted geometric mean, INFORM Concept and Methodology 2017 "
    "Equation 1. Sub-dimension scores are inverted so that higher is better, "
    "rescaled from [0, 10] onto [1, 10], combined by geometric mean, rescaled "
    "back onto [0, 10] and re-inverted. The rescale removes the annihilating "
    "zero: a district with no vulnerability on one sub-dimension keeps the "
    "vulnerability it has on the other, while the geometric mean still refuses "
    "to average a severe sub-dimension away."
)
"""The declared aggregation rule, published with every composed score."""


class InformScoreError(ValueError):
    """Raised when a value cannot be aggregated as an INFORM dimension score."""


def geometric_mean(values: Sequence[Decimal]) -> Decimal:
    """Return the equally weighted geometric mean of non-negative values.

    This is the plain mean, with no rescale: a single zero annihilates it. That
    behaviour is correct at PRIO's top level and wrong inside a dimension, which
    is why :func:`inform_geometric_mean` wraps it rather than replacing it.

    Raises:
        InformScoreError: If the sequence is empty or holds a negative value.
    """
    if not values:
        raise InformScoreError(
            "A geometric mean needs at least one value; an empty aggregation has "
            "no neutral answer, and returning 0 or 1 would invent one."
        )
    negative = [value for value in values if value < 0]
    if negative:
        raise InformScoreError(
            f"Cannot take the geometric mean of a negative value {negative[0]}: "
            f"no index score is negative, so this is a defect upstream."
        )
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        # Correctly rounded, so the equal-input identity is exact rather than
        # approximate. This is the path the two-sub-dimension V score takes.
        return (values[0] * values[1]).sqrt()
    if any(value == 0 for value in values):
        return Decimal(0)
    return (sum((value.ln() for value in values), Decimal(0)) / len(values)).exp()


def rescale(
    value: Decimal,
    from_floor: Decimal,
    from_ceiling: Decimal,
    to_floor: Decimal,
    to_ceiling: Decimal,
) -> Decimal:
    """Linearly rescale a value from one closed interval onto another.

    The bounds are **fixed arguments, never derived from the data**. Normalising
    against the observed range of a single event would make two events
    incomparable and make a district's score move when an unrelated district's
    did, which is precisely the defect this index exists to avoid.

    Raises:
        InformScoreError: If the source range has zero width.
    """
    source_width = from_ceiling - from_floor
    if source_width == 0:
        raise InformScoreError(
            f"Cannot rescale from the degenerate range [{from_floor}, "
            f"{from_ceiling}]: a zero-width source range carries no information "
            f"about where the value sits."
        )
    return to_floor + (value - from_floor) * (to_ceiling - to_floor) / source_width


def invert_score(
    value: Decimal,
    floor: Decimal = SCORE_FLOOR,
    ceiling: Decimal = SCORE_CEILING,
) -> Decimal:
    """Reflect a score within its range, swapping "worse" for "better".

    Reflection is its own inverse, which is what lets
    :func:`inform_geometric_mean` invert at both ends of the composition and
    return to the original units.
    """
    return ceiling + floor - value


def inform_geometric_mean(scores: Sequence[Decimal]) -> Decimal:
    """Combine 0-10 sub-dimension scores the way INFORM combines sub-components.

    Args:
        scores: Equally weighted sub-dimension scores, each in [0, 10], where
            higher means *more* vulnerable.

    Returns:
        The combined score in [0, 10], in the same direction as the inputs. Equal
        inputs return that input exactly; a zero alongside a ten returns 7.597,
        not zero.

    Raises:
        InformScoreError: If any score falls outside [0, 10].
    """
    for score in scores:
        if score < SCORE_FLOOR or score > SCORE_CEILING:
            raise InformScoreError(
                f"Sub-dimension score {score} is outside [0, 10]. Scores are "
                f"rescaled percentile ranks, so a value beyond the range means "
                f"the percentile step produced something that is not a "
                f"percentile."
            )
    rescaled = [
        rescale(
            invert_score(score),
            SCORE_FLOOR,
            SCORE_CEILING,
            INFORM_RESCALE_FLOOR,
            INFORM_RESCALE_CEILING,
        )
        for score in scores
    ]
    combined = geometric_mean(rescaled)
    return invert_score(
        rescale(
            combined,
            INFORM_RESCALE_FLOOR,
            INFORM_RESCALE_CEILING,
            SCORE_FLOOR,
            SCORE_CEILING,
        )
    )
