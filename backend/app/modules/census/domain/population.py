"""Population derivation guards for the verified CPV 2024 data defects.

Three defects of the published distribution are enforced here instead of being
re-discovered per loader:

1. ``Total_Personas`` is wrong. Across the 262 real district rows of
   ``distritos_poblacion_edad_sexo`` it sums 5,843,393, while ``Hombre + Mujer``
   sums 5,922,921. 255 of the 262 rows disagree. The same defective column
   appears in ``municipios_poblacion_edad_sexo``. The column is therefore
   declared forbidden: population is always derived from the sex columns and
   cross-checked against the 20 five-year age bands.
2. The age bands and the sex columns agree exactly at all three levels
   (department, municipality, district), so any row where they disagree is
   corrupt and must fail loudly rather than be averaged.
3. The national figure reconciles exactly as
   5,922,921 georeferenced + 107,055 unlocated ("Otros", ``id_depto='15'``,
   no geometry) = 6,029,976. Ingestion asserts this and refuses to proceed on drift.
"""

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

NATIONAL_POPULATION_TOTAL = 6_029_976
"""Published total population of El Salvador, CPV 2024."""

GEOREFERENCED_POPULATION_TOTAL = 5_922_921
"""Population attached to a real territory, derived from the sex columns."""

UNLOCATED_POPULATION_TOTAL = 107_055
"""Population in the "Otros"/"RRAA" pseudo-department, which has no geometry."""

DEFECTIVE_TOTAL_PERSONAS_SUM = 5_843_393
"""What ``Total_Personas`` sums to over the real districts: the defect's signature."""

FORBIDDEN_POPULATION_FIELDS: frozenset[str] = frozenset({"Total_Personas"})
"""Columns that must never be read as a population measure."""

SEX_CODES: tuple[str, ...] = ("H", "M")
"""Canonical sex codes used by ``census_indicator.sex``."""

SEX_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "H": ("Hombre", "Hombres"),
    "M": ("Mujer", "Mujeres"),
}
"""Published spellings per sex: district and municipality layers use the singular,
the department layer uses the plural."""

AGE_BANDS: tuple[str, ...] = (
    "0_4",
    "5_9",
    "10_14",
    "15_19",
    "20_24",
    "25_29",
    "30_34",
    "35_39",
    "40_44",
    "45_49",
    "50_54",
    "55_59",
    "60_64",
    "65_69",
    "70_74",
    "75_79",
    "80_84",
    "85_89",
    "90_94",
    "95_o_mas",
)
"""The 20 five-year age bands published per sex, as ``H_<band>`` / ``M_<band>``."""

YOUNG_CHILD_BANDS: tuple[str, ...] = ("0_4",)
"""Age bands counted as children under five for the vulnerable-groups dimension."""

OLDER_ADULT_BANDS: tuple[str, ...] = (
    "65_69",
    "70_74",
    "75_79",
    "80_84",
    "85_89",
    "90_94",
    "95_o_mas",
)
"""Age bands counted as 65 and over for the vulnerable-groups dimension."""


class ForbiddenCensusFieldError(ValueError):
    """Raised when an ingestion path tries to read a known-defective column."""


class CensusReconciliationError(ValueError):
    """Raised when derived population figures do not reconcile with the census."""


def assert_no_forbidden_fields(field_names: Iterable[str]) -> None:
    """Fail loudly when a forbidden population column is about to be read."""
    offending = sorted(FORBIDDEN_POPULATION_FIELDS.intersection(field_names))
    if offending:
        raise ForbiddenCensusFieldError(
            f"Refusing to read defective census column(s) {offending}: "
            f"{sorted(FORBIDDEN_POPULATION_FIELDS)} sums "
            f"{DEFECTIVE_TOTAL_PERSONAS_SUM:,} instead of "
            f"{GEOREFERENCED_POPULATION_TOTAL:,}. Derive population from "
            f"{sorted(SEX_FIELD_CANDIDATES)} or the age bands instead."
        )


def _read_int(properties: Mapping[str, Any], field: str) -> int:
    """Read an integer measure, treating null and blank as zero."""
    value = properties.get(field)
    if value is None or value == "":
        return 0
    return int(value)


def derive_population_by_sex(properties: Mapping[str, Any]) -> dict[str, int]:
    """Return population per sex code, read from the published sex columns."""
    by_sex: dict[str, int] = {}
    for sex, candidates in SEX_FIELD_CANDIDATES.items():
        field = next((name for name in candidates if name in properties), None)
        if field is None:
            raise CensusReconciliationError(
                f"No population column for sex {sex!r}: expected one of "
                f"{list(candidates)} in {sorted(properties)[:12]}"
            )
        by_sex[sex] = _read_int(properties, field)
    return by_sex


def derive_population_by_age_band(
    properties: Mapping[str, Any],
) -> dict[tuple[str, str], int]:
    """Return population per (sex, age band), spanning all 20 published bands."""
    return {
        (sex, band): _read_int(properties, f"{sex}_{band}")
        for sex in SEX_CODES
        for band in AGE_BANDS
    }


def derive_total_population(properties: Mapping[str, Any]) -> int:
    """Return the authoritative total population of a census row.

    The value is ``Hombre + Mujer`` cross-checked against the sum of the 20 age
    bands per sex. ``Total_Personas`` is never consulted.
    """
    by_sex = derive_population_by_sex(properties)
    by_band = derive_population_by_age_band(properties)
    sex_total = sum(by_sex.values())
    band_total = sum(by_band.values())
    if sex_total != band_total:
        raise CensusReconciliationError(
            f"Census row is internally inconsistent: sex columns sum "
            f"{sex_total:,} but the age band columns sum {band_total:,}. "
            f"Refusing to guess a population for this row."
        )
    return sex_total


def normalize_share(raw: Any) -> Decimal | None:
    """Return a published share only when it is a genuine fraction of the whole.

    ``viviendas_particulares_distritos`` ships a fourth defect: on the correctly
    coded department rows the ``porcentaje`` column holds a raw dwelling count
    (175656, 52184, 238121) rather than a fraction, and only the mislabelled
    ``id_depto='00'`` twin carries the real share. A value outside [0, 1] is
    therefore not a share, and storing it would corrupt every derived rate.

    Returns:
        The share as a Decimal, or None when it is absent or out of range.
    """
    if raw is None or raw == "":
        return None
    try:
        share = Decimal(str(raw))
    except InvalidOperation:
        return None
    if share < 0 or share > 1:
        return None
    return share


def assert_national_reconciliation(
    georeferenced: int,
    unlocated: int,
    expected_total: int = NATIONAL_POPULATION_TOTAL,
) -> None:
    """Assert the national population reconciliation, failing loudly on any drift.

    Args:
        georeferenced: Population summed over rows that carry a real geometry.
        unlocated: Population of the "Otros" pseudo-department.
        expected_total: Published national total.

    Raises:
        CensusReconciliationError: If either component or the grand total drifts.
    """
    observed_total = georeferenced + unlocated
    detail = (
        f"georeferenced={georeferenced:,} "
        f"(expected {GEOREFERENCED_POPULATION_TOTAL:,}), "
        f"unlocated={unlocated:,} (expected {UNLOCATED_POPULATION_TOTAL:,}), "
        f"total={observed_total:,} (expected {expected_total:,})"
    )
    if georeferenced != GEOREFERENCED_POPULATION_TOTAL:
        raise CensusReconciliationError(
            f"Georeferenced census population drifted: {detail}"
        )
    if unlocated != UNLOCATED_POPULATION_TOTAL:
        raise CensusReconciliationError(
            f"Unlocated census population drifted: {detail}"
        )
    if observed_total != expected_total:
        raise CensusReconciliationError(
            f"National census population drifted: {detail}"
        )
