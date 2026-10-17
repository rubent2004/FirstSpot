"""DIGESTYC/BCR-CNR territorial code hierarchy and sentinel-row detection.

The census geographic key is a set of zero-padded nested strings whose hierarchy
is expressed by concatenation, and whose level is encoded by string length:

    id_depto    "01"            2 characters -> departamento
    id_mun      "0101"          4 characters -> municipio
    id_distrito "010101"        6 characters -> distrito
    idsegmento  "0101010001"   10 characters -> segmento censal

This is the DIGESTYC/BCR-CNR code, *not* ISO 3166-2:SV. A separate mapping table
is required to interoperate with ISO codes.

The CPV 2024 distribution also ships rows that are not territories and must
never reach the database:

* ``id_depto = '15'`` ("Otros" / "RRAA"): 107,055 people with no geometry.
* ``'AAA'`` and ``'RRAA'``: aggregate-total placeholder rows repeated per parent.
* all-zero codes (``'00'``, ``'0000'``, ``'000000'``, ``'0000000000'``):
  national rollup rows that would double-count every measure.
"""

from collections.abc import Iterable
from enum import StrEnum

CENSUS_SOURCE_ATTRIBUTION = "BCR/ONEC, CPV 2024"
"""Mandatory credit line for every published census figure."""


class CensusLevel(StrEnum):
    """Administrative level of a census territorial code."""

    DEPARTAMENTO = "departamento"
    MUNICIPIO = "municipio"
    DISTRITO = "distrito"
    SEGMENTO = "segmento"


CODE_WIDTH_BY_LEVEL: dict[CensusLevel, int] = {
    CensusLevel.DEPARTAMENTO: 2,
    CensusLevel.MUNICIPIO: 4,
    CensusLevel.DISTRITO: 6,
    CensusLevel.SEGMENTO: 10,
}

LEVEL_BY_CODE_WIDTH: dict[int, CensusLevel] = {
    width: level for level, width in CODE_WIDTH_BY_LEVEL.items()
}

ADMIN_LEVELS: tuple[CensusLevel, ...] = (
    CensusLevel.DEPARTAMENTO,
    CensusLevel.MUNICIPIO,
    CensusLevel.DISTRITO,
)
"""Levels stored in ``census_admin_unit``; segments live in their own table."""

UNLOCATED_DEPARTMENT_CODE = "15"
"""Pseudo-department "Otros"/"RRAA": real people, no geometry, never ingested as a unit."""

AGGREGATE_CODE_TOKENS: frozenset[str] = frozenset({"AAA", "RRAA"})
"""Aggregate-total placeholders that duplicate their parent's measures."""

NATIONAL_AGGREGATE_CODES: frozenset[str] = frozenset(
    {"00", "0000", "000000", "0000000000"}
)
"""All-zero national rollup codes, one per level width."""


class UnknownCensusCodeError(ValueError):
    """Raised when a code cannot be resolved to a census administrative level."""


def level_for_code(code: str) -> CensusLevel:
    """Resolve the administrative level encoded by the code's string length."""
    width = len(code or "")
    try:
        return LEVEL_BY_CODE_WIDTH[width]
    except KeyError as exc:
        raise UnknownCensusCodeError(
            f"Census code {code!r} has width {width}; "
            f"expected one of {sorted(LEVEL_BY_CODE_WIDTH)}"
        ) from exc


def parent_code(code: str) -> str | None:
    """Return the parent code, which is this code's shorter concatenation prefix."""
    level = level_for_code(code)
    if level is CensusLevel.DEPARTAMENTO:
        return None
    widths = sorted(LEVEL_BY_CODE_WIDTH)
    parent_width = widths[widths.index(len(code)) - 1]
    return code[:parent_width]


def normalize_code(raw: str | int | None, level: CensusLevel) -> str:
    """Zero-pad a numeric code to its level width, preserving non-numeric sentinels."""
    if raw is None:
        return ""
    text = str(raw).strip()
    width = CODE_WIDTH_BY_LEVEL[level]
    if not text.isdigit():
        return text
    if len(text) > width:
        raise UnknownCensusCodeError(
            f"Census code {text!r} is wider than {width} characters for level {level}"
        )
    return text.zfill(width)


def is_sentinel_code(code: str | None) -> bool:
    """Return True when the code is a sentinel row rather than a real territory."""
    if code is None:
        return True
    text = str(code).strip()
    if not text:
        return True
    if text.upper() in AGGREGATE_CODE_TOKENS:
        return True
    if text in NATIONAL_AGGREGATE_CODES:
        return True
    if text.isdigit() and set(text) == {"0"}:
        return True
    return text.startswith(UNLOCATED_DEPARTMENT_CODE)


def is_sentinel_row(*codes: str | None) -> bool:
    """Return True when any code column of a row is a sentinel."""
    return any(is_sentinel_code(code) for code in codes)


def iter_real_codes(codes: Iterable[str | None]) -> list[str]:
    """Return only the codes that identify a real territory, in input order."""
    return [str(code).strip() for code in codes if not is_sentinel_code(code)]
