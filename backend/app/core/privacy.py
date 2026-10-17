"""Statistical disclosure control: minimum publishable cell size.

The Ley Especial de Estadistica y Censos (Decreto Legislativo 904), Arts. 24, 25,
33 and 35, imposes statistical secrecy, aggregate-only dissemination, and a
**minimum of three units per published cell**. No license is published for the
CPV 2024 items, so the binding regime is legal rather than contractual: a derived
cell holding fewer than three units must be suppressed before it can leave the API.

The same mechanism is the k-anonymity suppression required for voluntary location
sharing: instantiate :class:`SuppressionPolicy` with the desired ``minimum_units``
instead of writing a second threshold comparison. This module therefore depends on
nothing census-specific and is the single place where a publication threshold lives.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TypeVar

MINIMUM_PUBLISHABLE_UNITS = 3
"""Legal minimum number of statistical units in any published cell (D.L. 904)."""

STATISTICAL_SECRECY_REFERENCE = (
    "Ley Especial de Estadistica y Censos (D.L. 904), Arts. 24, 25, 33 and 35"
)
"""Citation to attach whenever a cell is reported as suppressed."""

SUPPRESSED_PLACEHOLDER = None
"""Value exposed in place of a suppressed measure: absence, never a zero."""

CellKey = TypeVar("CellKey")


@dataclass(frozen=True, slots=True)
class SuppressedCell:
    """Outcome of applying a suppression policy to a single derived cell."""

    value: Decimal | None
    suppressed: bool


@dataclass(frozen=True, slots=True)
class SuppressionPolicy:
    """Threshold rule deciding whether a derived cell may be published.

    Args:
        minimum_units: Smallest number of units a published cell may hold.
        suppress_structural_zero: When False (the default) an empty cell is
            published as a true zero, because a cell holding nobody identifies
            nobody. Set to True to also hide zeros, which blocks differencing
            attacks at the cost of making genuine absences indistinguishable
            from withheld values.
        label: Human-readable reason attached to suppressed output.
    """

    minimum_units: int = MINIMUM_PUBLISHABLE_UNITS
    suppress_structural_zero: bool = False
    label: str = "D.L. 904 statistical secrecy"

    def __post_init__(self) -> None:
        """Reject a threshold that would publish single-unit cells."""
        if self.minimum_units < 1:
            raise ValueError(
                f"minimum_units must be at least 1, got {self.minimum_units}"
            )

    def is_suppressed(self, unit_count: Decimal | float | int | None) -> bool:
        """Return True when a cell holding ``unit_count`` units must be withheld."""
        if unit_count is None:
            return True
        count = _as_decimal(unit_count)
        if count < 0:
            raise ValueError(
                f"A statistical cell cannot hold a negative unit count, got {count}"
            )
        if count == 0:
            return self.suppress_structural_zero
        return count < self.minimum_units

    def apply(self, unit_count: Decimal | float | int | None) -> SuppressedCell:
        """Return the publishable form of a cell under this policy."""
        if self.is_suppressed(unit_count):
            return SuppressedCell(value=SUPPRESSED_PLACEHOLDER, suppressed=True)
        return SuppressedCell(value=_as_decimal(unit_count), suppressed=False)


CENSUS_SUPPRESSION_POLICY = SuppressionPolicy()
"""Default policy for every census-derived cell published by this service."""


def _as_decimal(unit_count: Decimal | float | int) -> Decimal:
    """Convert a measure to Decimal without inheriting binary float noise."""
    if isinstance(unit_count, Decimal):
        return unit_count
    try:
        return Decimal(str(unit_count))
    except InvalidOperation as exc:
        raise ValueError(f"Unit count {unit_count!r} is not numeric") from exc


def suppress_cell(
    unit_count: Decimal | float | int | None,
    policy: SuppressionPolicy = CENSUS_SUPPRESSION_POLICY,
) -> SuppressedCell:
    """Apply a suppression policy to a single derived cell."""
    return policy.apply(unit_count)


def suppress_mapping(
    cells: Mapping[CellKey, Decimal | float | int | None],
    policy: SuppressionPolicy = CENSUS_SUPPRESSION_POLICY,
) -> dict[CellKey, SuppressedCell]:
    """Apply a suppression policy to every cell of a breakdown."""
    return {key: policy.apply(value) for key, value in cells.items()}


def suppress_measure(
    unit_count: Decimal | float | int | None,
    share: Decimal | float | int | None = None,
    policy: SuppressionPolicy = CENSUS_SUPPRESSION_POLICY,
) -> tuple[Decimal | None, Decimal | None, bool]:
    """Return the publishable ``(value, share, suppressed)`` triple for one cell.

    A derived share must be withheld together with its count: publishing a
    percentage alongside a known denominator reconstructs the suppressed
    numerator exactly, which would defeat the threshold.
    """
    cell = policy.apply(unit_count)
    if cell.suppressed:
        return None, None, True
    published_share = None if share is None else _as_decimal(share)
    return cell.value, published_share, False


def suppressed_count(cells: Mapping[CellKey, SuppressedCell]) -> int:
    """Count how many cells of an already-suppressed breakdown were withheld."""
    return sum(1 for cell in cells.values() if cell.suppressed)
