"""Idempotent loaders for the CPV 2024 corpus, with every verified defect enforced.

Each loader streams one published layer, drops the rows that are not territories,
derives measures from the columns that are actually correct, screens every derived
cell against the statistical-secrecy threshold, and upserts on a natural key so a
re-run converges instead of duplicating.

The defects enforced here are listed in
``app.modules.census.domain.population`` and
``app.modules.census.domain.geo_codes``; the thresholds in
``app.core.privacy``. Three further rules are specific to
loading:

* **Census segments carry no population.** The segment layer publishes geometry
  and an urban/rural label only, and the microdata's finest geographic variable
  is the 6-digit district, so attaching population to a segment would require
  dasymetric modelling rather than a join. ``SEGMENT_SOURCE_FIELDS`` is the
  explicit field contract that keeps the loader honest.
* **The unlocated pseudo-department is harvested, never stored.** Its 107,055
  people are real but have no geometry, so the population loader returns the
  figure for the reconciliation assertion and stores no row for it.
* **DEGURBA Nivel 1 and Nivel 2 both total 5,922,921.** They are two
  classifications of the same territory, so only the analysis level is loaded by
  default; loading both would double-count any unfiltered sum.
"""

from collections.abc import Iterator, Mapping, Sequence
import csv
from dataclasses import dataclass, field
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import (
    CENSUS_SUPPRESSION_POLICY,
    SuppressionPolicy,
    suppress_measure,
)
from app.modules.census.domain.geo_codes import (
    CENSUS_SOURCE_ATTRIBUTION,
    CensusLevel,
    UNLOCATED_DEPARTMENT_CODE,
    is_sentinel_code,
    is_sentinel_row,
    level_for_code,
    normalize_code,
    parent_code,
)
from app.modules.census.domain.population import (
    AGE_BANDS,
    CensusReconciliationError,
    assert_national_reconciliation,
    assert_no_forbidden_fields,
    derive_population_by_age_band,
    derive_population_by_sex,
    derive_total_population,
    normalize_share,
)
from app.modules.census.infrastructure.geojson_stream import iter_geojson_features
from app.modules.census.infrastructure.repository import (
    CensusLoadReport,
    CensusRepository,
)

DEFAULT_RAW_DIR = Path(__file__).resolve().parents[4].parent / "data" / "census" / "raw"
"""Default corpus location: ``<repo>/data/census/raw`` (gitignored, regenerable)."""

DEGURBA_ANALYSIS_LEVEL = 2
"""The DEGURBA level used as the analysis unit: 902 sub-district polygons."""

_DEGURBA_LEVEL_PATTERN = re.compile(r"(\d+)")

SEGMENT_SOURCE_FIELDS: frozenset[str] = frozenset(
    {"idsegmento", "id_distrito", "areadesc", "area_km2"}
)
"""The only fields the segment loader may read. The segment layer publishes no
population attribute, so none can appear here."""


class CensusIngestionError(RuntimeError):
    """Raised when an observed layer shape contradicts the published census."""


@dataclass(frozen=True, slots=True)
class PopulationTotals:
    """The two components of the national population reconciliation."""

    georeferenced: int
    unlocated: int

    @property
    def national(self) -> int:
        """Return the sum of both components."""
        return self.georeferenced + self.unlocated


@dataclass(slots=True)
class CensusIngestionReport:
    """Aggregate outcome of a full census ingestion run."""

    datasets: list[CensusLoadReport] = field(default_factory=list)
    table_counts: dict[str, int] = field(default_factory=dict)
    totals: PopulationTotals | None = None

    def lines(self) -> list[str]:
        """Return a log-friendly, line-per-fact rendering of the whole run."""
        rendered = [str(report) for report in self.datasets]
        rendered += [
            f"table {name}: {count} rows"
            for name, count in sorted(self.table_counts.items())
        ]
        if self.totals is not None:
            rendered.append(
                f"reconciliation: georeferenced={self.totals.georeferenced:,} "
                f"+ unlocated={self.totals.unlocated:,} "
                f"= {self.totals.national:,}"
            )
        return rendered


# --------------------------------------------------------------------------- #
# Administrative hierarchy
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class BoundarySource:
    """One CNR SIRGAS boundary layer and the level it populates."""

    filename: str
    level: CensusLevel
    code_field: str
    name_field: str
    context_code_fields: tuple[str, ...]


BOUNDARY_SOURCES: tuple[BoundarySource, ...] = (
    BoundarySource(
        filename="limites_departamentos_cnr_sirgas.geojson",
        level=CensusLevel.DEPARTAMENTO,
        code_field="id_depto",
        name_field="depto",
        context_code_fields=(),
    ),
    BoundarySource(
        filename="limites_municipios_cnr_sirgas.geojson",
        level=CensusLevel.MUNICIPIO,
        code_field="id_mun",
        name_field="mun",
        context_code_fields=("id_depto",),
    ),
    BoundarySource(
        filename="limites_distritos_cnr_sirgas.geojson",
        level=CensusLevel.DISTRITO,
        code_field="id_distrito",
        name_field="distrito",
        context_code_fields=("id_depto", "id_mun"),
    ),
)

EXPECTED_ADMIN_UNITS: dict[CensusLevel, int] = {
    CensusLevel.DEPARTAMENTO: 14,
    CensusLevel.MUNICIPIO: 44,
    CensusLevel.DISTRITO: 262,
}
"""Verified unit counts after the 2023 territorial reorganisation (D.L. 57/2023).
The published layers carry 15/59/307 features; the surplus is sentinel rows."""


async def load_admin_units(
    repository: CensusRepository,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    expected_units: Mapping[CensusLevel, int] | None = None,
) -> CensusLoadReport:
    """Load the unified administrative hierarchy from the CNR SIRGAS boundaries."""
    raw_path = Path(raw_dir)
    expected = dict(expected_units or EXPECTED_ADMIN_UNITS)
    report = CensusLoadReport(dataset="census_admin_unit")

    for source in BOUNDARY_SOURCES:
        rows: list[dict[str, Any]] = []
        for feature in iter_geojson_features(raw_path / source.filename):
            report.rows_read += 1
            properties = feature.get("properties") or {}
            code_values = [
                properties.get(name) for name in source.context_code_fields
            ]
            code_values.append(properties.get(source.code_field))
            if is_sentinel_row(*code_values):
                report.rows_skipped_sentinel += 1
                continue

            code = normalize_code(properties.get(source.code_field), source.level)
            geometry = feature.get("geometry")
            if geometry is None:
                raise CensusIngestionError(
                    f"{source.filename}: unit {code!r} has no geometry; "
                    f"a real territory must be georeferenced"
                )
            rows.append(
                {
                    "code": code,
                    "level": str(source.level),
                    "parent_code": parent_code(code),
                    "name": _clean_name(properties.get(source.name_field), code),
                    "iso_3166_2": None,
                    "geom_json": json.dumps(geometry),
                    "source": CENSUS_SOURCE_ATTRIBUTION,
                }
            )

        _assert_expected(
            source.filename,
            observed=len(rows),
            expected=expected.get(source.level),
        )
        report.rows_written += await repository.upsert_admin_units(rows)

    return report


def _clean_name(raw: Any, code: str) -> str:
    """Return a non-empty display name, falling back to the code itself."""
    name = str(raw).strip() if raw is not None else ""
    return name or code


def _assert_expected(label: str, observed: int, expected: int | None) -> None:
    """Fail loudly when an observed row count contradicts the published census."""
    if expected is not None and observed != expected:
        raise CensusIngestionError(
            f"{label}: loaded {observed} rows but the published census has "
            f"{expected}. Refusing to ingest a corpus that drifted."
        )


# --------------------------------------------------------------------------- #
# DEGURBA population units: the analysis grain
# --------------------------------------------------------------------------- #

DEGURBA_FILENAME = "degurba_densidad.geojson"
EXPECTED_DEGURBA_UNITS: dict[int, int] = {1: 443, 2: 902}
"""Verified DEGURBA polygon counts per level; both levels total 5,922,921 people."""


async def load_population_units(
    repository: CensusRepository,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    dug_levels: Sequence[int] = (DEGURBA_ANALYSIS_LEVEL,),
    expected_units: Mapping[int, int] | None = None,
) -> CensusLoadReport:
    """Load DEGURBA sub-district polygons, by default only the analysis level."""
    raw_path = Path(raw_dir)
    expected = dict(expected_units or EXPECTED_DEGURBA_UNITS)
    wanted = set(dug_levels)
    report = CensusLoadReport(dataset="census_population_unit")
    rows: list[dict[str, Any]] = []
    per_level: dict[int, int] = {level: 0 for level in wanted}

    for feature in iter_geojson_features(raw_path / DEGURBA_FILENAME):
        report.rows_read += 1
        properties = feature.get("properties") or {}
        district_code = properties.get("id_distrito")
        if is_sentinel_row(
            properties.get("id_depto"), properties.get("id_mun"), district_code
        ):
            report.rows_skipped_sentinel += 1
            continue

        dug_level = _degurba_level(properties.get("nivel"))
        if dug_level not in wanted:
            continue

        geometry = feature.get("geometry")
        if geometry is None:
            raise CensusIngestionError(
                f"{DEGURBA_FILENAME}: district {district_code!r} level {dug_level} "
                f"has no geometry"
            )

        per_level[dug_level] = per_level.get(dug_level, 0) + 1
        rows.append(
            {
                "district_code": normalize_code(district_code, CensusLevel.DISTRITO),
                "dug_level": dug_level,
                "dug_class": str(properties.get("class") or "").strip() or "sin clase",
                "dug_code": _optional_int(properties.get("cod")),
                "population": _non_negative_int(properties.get("SUM_personas")),
                "households": _non_negative_int(properties.get("SUM_hogares")),
                "dwellings": _non_negative_int(properties.get("SUM_viviendas")),
                "area_km2": _optional_decimal(properties.get("SUM_area_km2")),
                "density": _optional_decimal(properties.get("densidad")),
                "geom_json": json.dumps(geometry),
                "source": CENSUS_SOURCE_ATTRIBUTION,
            }
        )

    for level, observed in per_level.items():
        _assert_expected(
            f"{DEGURBA_FILENAME} (Nivel {level})",
            observed=observed,
            expected=expected.get(level),
        )

    report.rows_written += await repository.upsert_population_units(rows)
    return report


def _degurba_level(raw: Any) -> int:
    """Parse the ``Nivel N`` label into its integer level."""
    match = _DEGURBA_LEVEL_PATTERN.search(str(raw or ""))
    if match is None:
        raise CensusIngestionError(f"Unparseable DEGURBA level {raw!r}")
    return int(match.group(1))


# --------------------------------------------------------------------------- #
# Census segments: geometry-only context
# --------------------------------------------------------------------------- #

SEGMENTS_FILENAME = "segmentos_censales_2024.geojson"
EXPECTED_SEGMENTS = 10_290
"""Real segment polygons. The layer ships 10,291 features: one is a national rollup."""


async def load_segments(
    repository: CensusRepository,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    expected_segments: int | None = EXPECTED_SEGMENTS,
    known_district_codes: set[str] | None = None,
) -> CensusLoadReport:
    """Load the official census segment polygons as urban/rural context only."""
    raw_path = Path(raw_dir)
    report = CensusLoadReport(dataset="census_segment")
    districts = known_district_codes
    if districts is None:
        districts = await repository.existing_admin_codes()
    rows: list[dict[str, Any]] = []

    for feature in iter_geojson_features(raw_path / SEGMENTS_FILENAME):
        report.rows_read += 1
        properties = feature.get("properties") or {}
        # Read only the declared contract: the segment layer has no population.
        attributes = {
            name: properties.get(name) for name in sorted(SEGMENT_SOURCE_FIELDS)
        }
        segment_code = attributes["idsegmento"]
        district_code = attributes["id_distrito"]
        if is_sentinel_row(properties.get("id_depto"), district_code, segment_code):
            report.rows_skipped_sentinel += 1
            continue

        normalized_district = normalize_code(district_code, CensusLevel.DISTRITO)
        if normalized_district not in districts:
            raise CensusIngestionError(
                f"{SEGMENTS_FILENAME}: segment {segment_code!r} references unknown "
                f"district {normalized_district!r}. Load the administrative "
                f"hierarchy first; non-matching codes are reported, never dropped."
            )

        geometry = feature.get("geometry")
        if geometry is None:
            raise CensusIngestionError(
                f"{SEGMENTS_FILENAME}: segment {segment_code!r} has no geometry"
            )

        rows.append(
            {
                "segment_code": normalize_code(segment_code, CensusLevel.SEGMENTO),
                "district_code": normalized_district,
                "area_type": str(attributes["areadesc"] or "").strip().upper(),
                "area_km2": _optional_decimal(attributes["area_km2"]),
                "geom_json": json.dumps(geometry),
                "source": CENSUS_SOURCE_ATTRIBUTION,
            }
        )

    _assert_expected(SEGMENTS_FILENAME, observed=len(rows), expected=expected_segments)
    report.rows_written += await repository.upsert_segments(rows)
    return report


# --------------------------------------------------------------------------- #
# Indicators: long/EAV storage with secrecy screening
# --------------------------------------------------------------------------- #

POPULATION_TOPIC = "poblacion"
AGE_SEX_TOPIC = "edad_sexo"
DISABILITY_TOPIC = "discapacidad"
DISABILITY_TYPE_TOPIC = "discapacidad_tipo"
DWELLING_TOPIC = "viviendas_particulares"
STRUCTURE_TOPIC = "estructuras"
HOUSEHOLD_TOPIC = "hogar_parentesco"


def _indicator_row(
    unit_code: str,
    unit_level: CensusLevel,
    topic: str,
    category: str,
    value: Any,
    sex: str | None = None,
    age_band: str | None = None,
    share: Any = None,
    policy: SuppressionPolicy = CENSUS_SUPPRESSION_POLICY,
) -> dict[str, Any]:
    """Build one screened indicator cell, suppressing value and share together."""
    published_value, published_share, suppressed = suppress_measure(
        value, share=normalize_share(share), policy=policy
    )
    return {
        "unit_code": unit_code,
        "unit_level": str(unit_level),
        "topic": topic,
        "category": category,
        "sex": sex,
        "age_band": age_band,
        "value": published_value,
        "share": published_share,
        "suppressed": suppressed,
        "source": CENSUS_SOURCE_ATTRIBUTION,
    }


@dataclass(frozen=True, slots=True)
class PopulationIndicatorSource:
    """One age-and-sex layer and the level it describes."""

    filename: str
    level: CensusLevel
    code_field: str
    context_code_fields: tuple[str, ...]


POPULATION_SOURCES: tuple[PopulationIndicatorSource, ...] = (
    PopulationIndicatorSource(
        filename="departamentos_poblacion_edad_sexo.geojson",
        level=CensusLevel.DEPARTAMENTO,
        code_field="dep_id",
        context_code_fields=(),
    ),
    PopulationIndicatorSource(
        filename="municipios_poblacion_edad_sexo.geojson",
        level=CensusLevel.MUNICIPIO,
        code_field="mun_id",
        context_code_fields=("dep_id",),
    ),
    PopulationIndicatorSource(
        filename="distritos_poblacion_edad_sexo.geojson",
        level=CensusLevel.DISTRITO,
        code_field="Dis_id",
        context_code_fields=("Dep_id", "Mun_id"),
    ),
)

_SOURCES_BY_FILENAME = {source.filename: source for source in POPULATION_SOURCES}

RECONCILIATION_LEVEL = CensusLevel.DISTRITO
"""The level whose georeferenced total is asserted against the published figure."""


async def load_population_indicators(
    repository: CensusRepository,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    filenames: Sequence[str] | None = None,
    expected_units: Mapping[CensusLevel, int] | None = None,
) -> tuple[CensusLoadReport, PopulationTotals]:
    """Load population by age and sex, harvesting the unlocated total on the way.

    Population is derived from the sex columns and cross-checked against the
    age bands; ``Total_Personas`` is never read. The "Otros" pseudo-department
    is not stored, but its population is returned so the caller can assert the
    national reconciliation.
    """
    raw_path = Path(raw_dir)
    expected = dict(expected_units or EXPECTED_ADMIN_UNITS)
    selected = [
        _SOURCES_BY_FILENAME[name]
        for name in (filenames or [source.filename for source in POPULATION_SOURCES])
    ]
    report = CensusLoadReport(dataset="census_indicator/poblacion+edad_sexo")
    georeferenced_by_level: dict[CensusLevel, int] = {}
    unlocated_total = 0

    for source in selected:
        rows: list[dict[str, Any]] = []
        units = 0
        level_total = 0
        for feature in iter_geojson_features(raw_path / source.filename):
            report.rows_read += 1
            properties = feature.get("properties") or {}
            code = properties.get(source.code_field)
            context = [properties.get(name) for name in source.context_code_fields]

            if _is_unlocated_row(properties, source):
                # Real people with no geometry: harvest, never store.
                unlocated_total = max(
                    unlocated_total, derive_total_population(properties)
                )
                report.rows_skipped_sentinel += 1
                continue
            if is_sentinel_row(*context, code):
                report.rows_skipped_sentinel += 1
                continue

            unit_code = normalize_code(code, source.level)
            total = derive_total_population(properties)
            by_sex = derive_population_by_sex(properties)
            by_band = derive_population_by_age_band(properties)
            units += 1
            level_total += total

            rows.append(
                _indicator_row(unit_code, source.level, POPULATION_TOPIC, "total", total)
            )
            for sex, sex_total in by_sex.items():
                rows.append(
                    _indicator_row(
                        unit_code,
                        source.level,
                        POPULATION_TOPIC,
                        "total",
                        sex_total,
                        sex=sex,
                    )
                )
            for (sex, band), band_total in by_band.items():
                rows.append(
                    _indicator_row(
                        unit_code,
                        source.level,
                        AGE_SEX_TOPIC,
                        "grupo_edad",
                        band_total,
                        sex=sex,
                        age_band=band,
                        share=_safe_ratio(band_total, total),
                    )
                )

        _assert_expected(source.filename, observed=units, expected=expected.get(source.level))
        georeferenced_by_level[source.level] = level_total
        report.rows_suppressed += sum(1 for row in rows if row["suppressed"])
        report.rows_written += await repository.upsert_indicators(rows)

    georeferenced = georeferenced_by_level.get(
        RECONCILIATION_LEVEL,
        next(iter(georeferenced_by_level.values()), 0),
    )
    _assert_levels_agree(georeferenced_by_level)
    return report, PopulationTotals(
        georeferenced=georeferenced, unlocated=unlocated_total
    )


def _is_unlocated_row(
    properties: Mapping[str, Any],
    source: PopulationIndicatorSource,
) -> bool:
    """Return True for the "Otros"/"RRAA" pseudo-department row of a layer."""
    department_field = (
        source.code_field
        if source.level is CensusLevel.DEPARTAMENTO
        else source.context_code_fields[0]
    )
    department = str(properties.get(department_field) or "").strip()
    return department == UNLOCATED_DEPARTMENT_CODE


def _assert_levels_agree(totals_by_level: Mapping[CensusLevel, int]) -> None:
    """Fail loudly when two aggregation levels disagree on the national total.

    The department layer and the district layer split 6 people differently
    between the sexes, but their grand totals agree exactly; a disagreement in
    the grand total would mean the layers describe different populations.
    """
    distinct = set(totals_by_level.values())
    if len(distinct) > 1:
        raise CensusReconciliationError(
            "Aggregation levels disagree on the georeferenced population: "
            + ", ".join(
                f"{level}={total:,}" for level, total in sorted(totals_by_level.items())
            )
        )


# --------------------------------------------------------------------------- #
# Disability, dwellings and structures
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SimpleIndicatorSource:
    """One layer or table holding a single measure, possibly across several levels."""

    filename: str
    topic: str
    category: str
    value_field: str
    share_field: str | None
    code_fields: tuple[str, ...]
    category_field: str | None = None
    secondary_category_field: str | None = None
    expected_rows: int | None = None


DISABILITY_SOURCES: tuple[SimpleIndicatorSource, ...] = (
    SimpleIndicatorSource(
        filename="discapacidad_departamentos.geojson",
        topic=DISABILITY_TOPIC,
        category="con_dificultad",
        value_field="Valor",
        share_field="Porcentaje",
        code_fields=("id_depto",),
        expected_rows=14,
    ),
    SimpleIndicatorSource(
        filename="discapacidad_municipios.geojson",
        topic=DISABILITY_TOPIC,
        category="con_dificultad",
        value_field="Valor",
        share_field="Porcentaje",
        code_fields=("id_depto", "id_mun"),
        expected_rows=44,
    ),
    SimpleIndicatorSource(
        filename="discapacidad_distritos.geojson",
        topic=DISABILITY_TOPIC,
        category="con_dificultad",
        value_field="Valor",
        share_field="Porcentaje",
        code_fields=("id_depto", "id_mun", "id_distrito"),
        expected_rows=262,
    ),
)

LONG_FORMAT_SOURCES: tuple[SimpleIndicatorSource, ...] = (
    SimpleIndicatorSource(
        filename="viviendas_particulares_distritos.geojson",
        topic=DWELLING_TOPIC,
        category="total",
        value_field="cantidad",
        share_field="porcentaje",
        code_fields=("id_depto", "id_mun", "id_distrito"),
        expected_rows=320,
    ),
    SimpleIndicatorSource(
        filename="estructuras_distritos.geojson",
        topic=STRUCTURE_TOPIC,
        category="total",
        value_field="cantidad",
        share_field="porcentaje",
        code_fields=("id_depto", "id_mun", "id_distrito"),
        expected_rows=320,
    ),
)

CSV_SOURCES: tuple[SimpleIndicatorSource, ...] = (
    SimpleIndicatorSource(
        filename="tabla_discapacidad_por_tipo_distrito.csv",
        topic=DISABILITY_TYPE_TOPIC,
        category="",
        value_field="Valor_discap",
        share_field="Tipo_disc_porcent",
        code_fields=("id_depto", "id_mun", "id_distrito"),
        category_field="Discapacidad",
        expected_rows=2240,
    ),
    SimpleIndicatorSource(
        filename="tabla_parentesco_hogar_distrito.csv",
        topic=HOUSEHOLD_TOPIC,
        category="",
        value_field="cantidad",
        share_field="porcentaje",
        code_fields=("id_depto", "id_mun", "id_distrito"),
        category_field="tipo_de_hogar",
        secondary_category_field="categoria",
    ),
)


def _resolve_level(
    properties: Mapping[str, Any],
    code_fields: Sequence[str],
) -> tuple[str, CensusLevel] | None:
    """Return the finest non-sentinel code of a long-format row and its level.

    A long-format layer repeats the same measure at department, municipality and
    district level in one file, padding the unused code columns with sentinels.
    The finest real code therefore identifies both the unit and its level.
    """
    for name in reversed(list(code_fields)):
        raw = properties.get(name)
        if is_sentinel_code(raw):
            continue
        code = str(raw).strip()
        try:
            return code, level_for_code(code)
        except ValueError:
            return None
    return None


async def load_simple_indicators(
    repository: CensusRepository,
    sources: Sequence[SimpleIndicatorSource],
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    dataset_label: str = "census_indicator",
) -> CensusLoadReport:
    """Load single-measure indicator layers or tables, screening every cell."""
    raw_path = Path(raw_dir)
    report = CensusLoadReport(dataset=dataset_label)

    for source in sources:
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for properties in _iter_source_rows(raw_path / source.filename):
            report.rows_read += 1
            resolved = _resolve_level(properties, source.code_fields)
            if resolved is None:
                report.rows_skipped_sentinel += 1
                continue
            unit_code, level = resolved
            category = _compose_category(properties, source)
            grain = (unit_code, str(level), source.topic, category)
            if grain in seen:
                # Duplicated department rows exist in the structure and dwelling
                # layers; the later one is identical, so the first wins.
                report.rows_skipped_sentinel += 1
                continue
            seen.add(grain)
            rows.append(
                _indicator_row(
                    unit_code,
                    level,
                    source.topic,
                    category,
                    properties.get(source.value_field),
                    share=(
                        properties.get(source.share_field)
                        if source.share_field
                        else None
                    ),
                )
            )

        _assert_expected(source.filename, observed=len(rows), expected=source.expected_rows)
        report.rows_suppressed += sum(1 for row in rows if row["suppressed"])
        report.rows_written += await repository.upsert_indicators(rows)

    return report


def _compose_category(
    properties: Mapping[str, Any],
    source: SimpleIndicatorSource,
) -> str:
    """Build the EAV category label of a row, joining two columns when needed."""
    parts: list[str] = []
    if source.category_field:
        parts.append(str(properties.get(source.category_field) or "").strip())
    if source.secondary_category_field:
        parts.append(str(properties.get(source.secondary_category_field) or "").strip())
    label = " / ".join(part for part in parts if part)
    return (label or source.category or "total")[:120]


def _iter_source_rows(path: Path) -> Iterator[Mapping[str, Any]]:
    """Yield attribute mappings from either a GeoJSON layer or a CSV table."""
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
        return
    for feature in iter_geojson_features(path):
        yield feature.get("properties") or {}


# --------------------------------------------------------------------------- #
# Numeric helpers
# --------------------------------------------------------------------------- #


def _optional_int(raw: Any) -> int | None:
    """Parse an optional integer, treating blank and null as absent."""
    if raw is None or raw == "":
        return None
    return int(float(raw))


def _non_negative_int(raw: Any) -> int:
    """Parse a required count, rejecting a negative value."""
    value = _optional_int(raw) or 0
    if value < 0:
        raise CensusIngestionError(f"Census count cannot be negative, got {raw!r}")
    return value


def _optional_decimal(raw: Any) -> Decimal | None:
    """Parse an optional decimal measure, treating blank and null as absent."""
    if raw is None or raw == "":
        return None
    return Decimal(str(raw))


def _safe_ratio(numerator: int, denominator: int) -> Decimal | None:
    """Return numerator/denominator as a Decimal, or None when undefined."""
    if not denominator:
        return None
    return Decimal(numerator) / Decimal(denominator)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


async def ingest_census(
    session: AsyncSession,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    include_segments: bool = True,
    commit: bool = True,
) -> CensusIngestionReport:
    """Run the full census ingestion and assert the national reconciliation.

    The order is dictated by referential integrity: administrative units first,
    then everything that references a district code.
    """
    repository = CensusRepository(session)
    report = CensusIngestionReport()

    report.datasets.append(await load_admin_units(repository, raw_dir))
    report.datasets.append(await load_population_units(repository, raw_dir))

    population_report, totals = await load_population_indicators(repository, raw_dir)
    report.datasets.append(population_report)
    report.totals = totals

    report.datasets.append(
        await load_simple_indicators(
            repository,
            DISABILITY_SOURCES,
            raw_dir,
            dataset_label="census_indicator/discapacidad",
        )
    )
    report.datasets.append(
        await load_simple_indicators(
            repository,
            LONG_FORMAT_SOURCES,
            raw_dir,
            dataset_label="census_indicator/viviendas+estructuras",
        )
    )
    report.datasets.append(
        await load_simple_indicators(
            repository,
            CSV_SOURCES,
            raw_dir,
            dataset_label="census_indicator/tablas",
        )
    )

    if include_segments:
        report.datasets.append(await load_segments(repository, raw_dir))

    # The DEGURBA analysis level must agree with the district population layer,
    # and both must reconcile with the published national total.
    degurba_total = await repository.georeferenced_population_total()
    if degurba_total != totals.georeferenced:
        raise CensusReconciliationError(
            f"DEGURBA level {DEGURBA_ANALYSIS_LEVEL} sums {degurba_total:,} but the "
            f"district population layer sums {totals.georeferenced:,}"
        )
    assert_national_reconciliation(
        georeferenced=totals.georeferenced,
        unlocated=totals.unlocated,
    )

    for table in (
        "census_admin_unit",
        "census_population_unit",
        "census_indicator",
        "census_segment",
    ):
        report.table_counts[table] = await repository.count_rows(table)

    if commit:
        await session.commit()
    return report


__all__ = [
    "AGE_BANDS",
    "BOUNDARY_SOURCES",
    "CSV_SOURCES",
    "DEFAULT_RAW_DIR",
    "DISABILITY_SOURCES",
    "EXPECTED_ADMIN_UNITS",
    "EXPECTED_DEGURBA_UNITS",
    "EXPECTED_SEGMENTS",
    "LONG_FORMAT_SOURCES",
    "POPULATION_SOURCES",
    "SEGMENT_SOURCE_FIELDS",
    "CensusIngestionError",
    "CensusIngestionReport",
    "PopulationTotals",
    "ingest_census",
    "load_admin_units",
    "load_population_indicators",
    "load_population_units",
    "load_segments",
    "load_simple_indicators",
]
