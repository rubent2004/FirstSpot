"""Phase B census ingestion tests: code hierarchy, data-defect guards, statistical secrecy, and PostGIS schema.

The behaviors asserted here are the verified defects of the VII Censo de Poblacion
y VI de Vivienda 2024 (BCR/ONEC) distribution, plus the statistical-secrecy
threshold imposed by the Ley Especial de Estadistica y Censos (D.L. 904).
"""

from decimal import Decimal
import json
from pathlib import Path
from typing import Any

from geoalchemy2 import Geography
import pytest
from sqlalchemy import Index, UniqueConstraint, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.census.domain.catalog import (
    CENSUS_LAYERS,
    CensusLayer,
    layer_by_filename,
)
from app.core.privacy import (
    CENSUS_SUPPRESSION_POLICY,
    MINIMUM_PUBLISHABLE_UNITS,
    STATISTICAL_SECRECY_REFERENCE,
    SuppressedCell,
    SuppressionPolicy,
    suppress_cell,
    suppress_mapping,
    suppress_measure,
)
from app.modules.census.domain.geo_codes import (
    CENSUS_SOURCE_ATTRIBUTION,
    AGGREGATE_CODE_TOKENS,
    CensusLevel,
    NATIONAL_AGGREGATE_CODES,
    UNLOCATED_DEPARTMENT_CODE,
    UnknownCensusCodeError,
    is_sentinel_code,
    is_sentinel_row,
    level_for_code,
    normalize_code,
    parent_code,
)
from app.modules.census.domain.population import (
    AGE_BANDS,
    CensusReconciliationError,
    DEFECTIVE_TOTAL_PERSONAS_SUM,
    FORBIDDEN_POPULATION_FIELDS,
    ForbiddenCensusFieldError,
    GEOREFERENCED_POPULATION_TOTAL,
    NATIONAL_POPULATION_TOTAL,
    UNLOCATED_POPULATION_TOTAL,
    assert_national_reconciliation,
    assert_no_forbidden_fields,
    derive_population_by_age_band,
    derive_population_by_sex,
    derive_total_population,
    normalize_share,
)
from app.modules.census.infrastructure.geojson_stream import (
    GeoJsonStreamError,
    count_geojson_features,
    iter_geojson_features,
)
from app.modules.census.infrastructure.models import (
    CensusAdminUnitModel,
    CensusIndicatorModel,
    CensusPopulationUnitModel,
    CensusSegmentModel,
)

# Verbatim first-feature properties of the Ahuachapan district as shipped by BCR.
# Total_Personas (126689) disagrees with Hombre + Mujer (127301): the defect under test.
AHUACHAPAN_DISTRICT_PROPERTIES: dict[str, object] = {
    "Dep_id": "01",
    "Mun_id": "0101",
    "Dis_id": "010101",
    "Dis_min": "Ahuachapán",
    "Hombre": 59268,
    "Mujer": 68033,
    "Total_Personas": 126689,
    "H_0_4": 4720, "H_5_9": 5543, "H_10_14": 5282, "H_15_19": 4935,
    "H_20_24": 5308, "H_25_29": 5161, "H_30_34": 4443, "H_35_39": 3854,
    "H_40_44": 3623, "H_45_49": 3351, "H_50_54": 2979, "H_55_59": 2476,
    "H_60_64": 2219, "H_65_69": 1758, "H_70_74": 1417, "H_75_79": 1025,
    "H_80_84": 616, "H_85_89": 368, "H_90_94": 137, "H_95_o_mas": 53,
    "M_0_4": 4634, "M_5_9": 5385, "M_10_14": 5019, "M_15_19": 4981,
    "M_20_24": 5844, "M_25_29": 6236, "M_30_34": 5538, "M_35_39": 4856,
    "M_40_44": 4608, "M_45_49": 4265, "M_50_54": 3855, "M_55_59": 3324,
    "M_60_64": 2772, "M_65_69": 2176, "M_70_74": 1681, "M_75_79": 1173,
    "M_80_84": 893, "M_85_89": 485, "M_90_94": 234, "M_95_o_mas": 74,
}


class TestCensusGeoCodeHierarchy:
    """Unit tests for the DIGESTYC/BCR-CNR zero-padded nested code hierarchy."""

    @pytest.mark.parametrize(
        ("code", "level"),
        [
            ("01", CensusLevel.DEPARTAMENTO),
            ("0101", CensusLevel.MUNICIPIO),
            ("010101", CensusLevel.DISTRITO),
            ("0101010001", CensusLevel.SEGMENTO),
        ],
    )
    def test_code_length_determines_hierarchy_level(
        self,
        code: str,
        level: CensusLevel,
    ) -> None:
        """Verify code string length alone resolves the administrative level."""
        assert level_for_code(code) is level

    @pytest.mark.parametrize("code", ["", "0", "012", "01010", "01010100012"])
    def test_unsupported_code_length_raises(self, code: str) -> None:
        """Verify a code of unsupported length is rejected instead of guessed."""
        with pytest.raises(UnknownCensusCodeError):
            level_for_code(code)

    @pytest.mark.parametrize(
        ("code", "expected_parent"),
        [
            ("01", None),
            ("0101", "01"),
            ("010101", "0101"),
            ("0101010001", "010101"),
        ],
    )
    def test_parent_code_is_the_concatenation_prefix(
        self,
        code: str,
        expected_parent: str | None,
    ) -> None:
        """Verify hierarchy by concatenation: the parent is the shorter prefix."""
        assert parent_code(code) == expected_parent

    def test_normalize_code_zero_pads_and_strips(self) -> None:
        """Verify numeric-looking codes are zero-padded to their level width."""
        assert normalize_code(1, CensusLevel.DEPARTAMENTO) == "01"
        assert normalize_code("101", CensusLevel.MUNICIPIO) == "0101"
        assert normalize_code(" 010101 ", CensusLevel.DISTRITO) == "010101"
        assert normalize_code("0101010001", CensusLevel.SEGMENTO) == "0101010001"

    def test_normalize_code_rejects_overlong_input(self) -> None:
        """Verify a code wider than its level is an error, never truncated."""
        with pytest.raises(UnknownCensusCodeError):
            normalize_code("01010101", CensusLevel.DISTRITO)

    def test_source_attribution_is_the_required_credit_line(self) -> None:
        """Verify the mandated attribution string for published census figures."""
        assert CENSUS_SOURCE_ATTRIBUTION == "BCR/ONEC, CPV 2024"


class TestCensusSentinelFiltering:
    """Unit tests for the sentinel rows that must never reach the database."""

    def test_unlocated_department_code_is_fifteen(self) -> None:
        """Verify the 'Otros' pseudo-department carrying 107,055 people is code 15."""
        assert UNLOCATED_DEPARTMENT_CODE == "15"

    @pytest.mark.parametrize("code", ["15", "1501", "150101"])
    def test_unlocated_department_and_its_children_are_sentinels(self, code: str) -> None:
        """Verify every code under department 15 is a sentinel: it has no geometry."""
        assert is_sentinel_code(code) is True

    @pytest.mark.parametrize("code", ["AAA", "RRAA", "aaa", " AAA "])
    def test_aggregate_total_tokens_are_sentinels(self, code: str) -> None:
        """Verify the 'AAA' and 'RRAA' aggregate-total placeholders are sentinels."""
        assert is_sentinel_code(code) is True

    @pytest.mark.parametrize("code", ["00", "0000", "000000", "0000000000"])
    def test_national_aggregate_codes_are_sentinels(self, code: str) -> None:
        """Verify the all-zero national rollup rows are sentinels."""
        assert code in NATIONAL_AGGREGATE_CODES
        assert is_sentinel_code(code) is True

    @pytest.mark.parametrize("code", [None, ""])
    def test_missing_code_is_a_sentinel(self, code: str | None) -> None:
        """Verify a null or empty code is treated as a sentinel, never ingested."""
        assert is_sentinel_code(code) is True

    @pytest.mark.parametrize("code", ["01", "0101", "010101", "0101010001", "14"])
    def test_real_territorial_codes_are_not_sentinels(self, code: str) -> None:
        """Verify genuine territorial codes survive sentinel filtering."""
        assert is_sentinel_code(code) is False

    def test_sentinel_row_detection_inspects_every_code_column(self) -> None:
        """Verify a row is rejected when any of its code columns is a sentinel."""
        assert is_sentinel_row("01", "0101", "010101") is False
        assert is_sentinel_row("15", "01", "01") is True
        assert is_sentinel_row("02", "AAA", "AAA") is True
        assert is_sentinel_row("00", "0000", "000000") is True
        assert is_sentinel_row("01", None, "010101") is True

    def test_aggregate_tokens_are_declared_as_constants(self) -> None:
        """Verify aggregate tokens are a named constant, not inline literals."""
        assert AGGREGATE_CODE_TOKENS == frozenset({"AAA", "RRAA"})


class TestTotalPersonasRejection:
    """Unit tests proving the defective Total_Personas column is never trusted."""

    def test_total_personas_is_declared_forbidden(self) -> None:
        """Verify Total_Personas is registered as a forbidden population source."""
        assert "Total_Personas" in FORBIDDEN_POPULATION_FIELDS

    def test_reading_a_forbidden_field_raises(self) -> None:
        """Verify an ingestion path that reads Total_Personas fails loudly."""
        with pytest.raises(ForbiddenCensusFieldError, match="Total_Personas"):
            assert_no_forbidden_fields(AHUACHAPAN_DISTRICT_PROPERTIES.keys())

    def test_clean_field_set_passes_the_forbidden_field_guard(self) -> None:
        """Verify the guard stays silent when no forbidden field is read."""
        assert_no_forbidden_fields(["Hombre", "Mujer", "H_0_4", "M_0_4"])

    def test_total_population_is_derived_from_sex_columns_not_total_personas(self) -> None:
        """Verify the derived total is Hombre + Mujer, never the defective column."""
        derived = derive_total_population(AHUACHAPAN_DISTRICT_PROPERTIES)
        assert derived == 127301
        assert derived != AHUACHAPAN_DISTRICT_PROPERTIES["Total_Personas"]

    def test_population_by_sex_matches_the_published_sex_columns(self) -> None:
        """Verify the per-sex breakdown reads Hombre and Mujer verbatim."""
        assert derive_population_by_sex(AHUACHAPAN_DISTRICT_PROPERTIES) == {
            "H": 59268,
            "M": 68033,
        }

    def test_population_by_age_band_covers_all_twenty_bands_per_sex(self) -> None:
        """Verify the age-band breakdown spans 0_4 through 95_o_mas for both sexes."""
        bands = derive_population_by_age_band(AHUACHAPAN_DISTRICT_PROPERTIES)
        assert len(AGE_BANDS) == 20
        assert len(bands) == 2 * len(AGE_BANDS)
        assert bands[("H", "0_4")] == 4720
        assert bands[("M", "95_o_mas")] == 74
        assert sum(bands.values()) == 127301

    def test_age_band_sum_disagreeing_with_sex_sum_raises(self) -> None:
        """Verify an internally inconsistent row is rejected, not silently averaged."""
        corrupted = dict(AHUACHAPAN_DISTRICT_PROPERTIES)
        corrupted["Hombre"] = 59269
        with pytest.raises(CensusReconciliationError, match="age band"):
            derive_total_population(corrupted)

    def test_plural_department_sex_columns_are_supported(self) -> None:
        """Verify the department layer's Hombres/Mujeres spelling is also derived."""
        department = {
            "dep_id": "01",
            "Hombres": 59268,
            "Mujeres": 68033,
            **{
                key: value
                for key, value in AHUACHAPAN_DISTRICT_PROPERTIES.items()
                if key.startswith(("H_", "M_"))
            },
        }
        assert derive_total_population(department) == 127301
        assert derive_population_by_sex(department) == {"H": 59268, "M": 68033}


class TestShareNormalization:
    """Unit tests for the published-share validity guard.

    In ``viviendas_particulares_distritos`` the correctly coded department rows
    carry a raw dwelling count in ``porcentaje`` (175656, 52184, 238121) instead
    of a fraction; only their ``id_depto='00'`` twin carries the real share.
    A value outside [0, 1] therefore cannot be a share and must not be stored.
    """

    @pytest.mark.parametrize("raw", [0.055357, 0, 1, "0.033811517"])
    def test_valid_fractions_are_kept(self, raw: object) -> None:
        """Verify a fraction inside the unit interval survives normalization."""
        assert normalize_share(raw) == Decimal(str(raw))

    @pytest.mark.parametrize("raw", [175656, 52184, 238121, 1.0000001, -0.2])
    def test_values_outside_the_unit_interval_are_discarded(self, raw: object) -> None:
        """Verify a count mislabelled as a percentage is dropped, not stored."""
        assert normalize_share(raw) is None

    def test_missing_share_stays_missing(self) -> None:
        """Verify an absent share is not invented as zero."""
        assert normalize_share(None) is None
        assert normalize_share("") is None


class TestNationalReconciliation:
    """Unit tests for the published national population reconciliation."""

    def test_published_reconciliation_constants(self) -> None:
        """Verify the three verified national figures of CPV 2024."""
        assert GEOREFERENCED_POPULATION_TOTAL == 5_922_921
        assert UNLOCATED_POPULATION_TOTAL == 107_055
        assert NATIONAL_POPULATION_TOTAL == 6_029_976
        assert DEFECTIVE_TOTAL_PERSONAS_SUM == 5_843_393

    def test_exact_reconciliation_passes(self) -> None:
        """Verify 5,922,921 georeferenced + 107,055 unlocated = 6,029,976."""
        assert_national_reconciliation(
            georeferenced=GEOREFERENCED_POPULATION_TOTAL,
            unlocated=UNLOCATED_POPULATION_TOTAL,
        )

    def test_drifted_reconciliation_fails_loudly_with_both_figures(self) -> None:
        """Verify any drift raises and reports observed against expected totals."""
        with pytest.raises(CensusReconciliationError) as excinfo:
            assert_national_reconciliation(
                georeferenced=DEFECTIVE_TOTAL_PERSONAS_SUM,
                unlocated=UNLOCATED_POPULATION_TOTAL,
            )
        message = str(excinfo.value)
        assert "5950448" in message.replace(",", "")
        assert "6029976" in message.replace(",", "")

    def test_georeferenced_component_is_itself_asserted(self) -> None:
        """Verify a wrong georeferenced subtotal fails even if the grand total matches."""
        with pytest.raises(CensusReconciliationError):
            assert_national_reconciliation(
                georeferenced=GEOREFERENCED_POPULATION_TOTAL - 1,
                unlocated=UNLOCATED_POPULATION_TOTAL + 1,
            )


class TestStatisticalSecrecySuppression:
    """Unit tests for the D.L. 904 minimum-cell-size suppression layer."""

    def test_threshold_is_three_units_and_named(self) -> None:
        """Verify the legal minimum of 3 units per published cell is a named constant."""
        assert MINIMUM_PUBLISHABLE_UNITS == 3
        assert CENSUS_SUPPRESSION_POLICY.minimum_units == MINIMUM_PUBLISHABLE_UNITS
        assert "904" in STATISTICAL_SECRECY_REFERENCE

    @pytest.mark.parametrize("units", [1, 2])
    def test_cells_below_the_threshold_are_suppressed(self, units: int) -> None:
        """Verify a cell with fewer than 3 units never carries a value out."""
        cell = suppress_cell(units)
        assert cell.suppressed is True
        assert cell.value is None

    @pytest.mark.parametrize("units", [3, 4, 126689])
    def test_cells_at_or_above_the_threshold_are_published(self, units: int) -> None:
        """Verify a cell with 3 or more units keeps its exact value."""
        cell = suppress_cell(units)
        assert cell.suppressed is False
        assert cell.value == Decimal(units)

    def test_structural_zero_is_published_by_default(self) -> None:
        """Verify an empty cell discloses nobody and is published as a true zero."""
        cell = suppress_cell(0)
        assert cell.suppressed is False
        assert cell.value == Decimal(0)

    def test_structural_zero_suppression_is_opt_in(self) -> None:
        """Verify a stricter policy can also suppress zeros to block differencing."""
        strict = SuppressionPolicy(suppress_structural_zero=True)
        assert strict.is_suppressed(0) is True
        assert suppress_cell(0, policy=strict) == SuppressedCell(value=None, suppressed=True)

    def test_missing_value_is_suppressed(self) -> None:
        """Verify an absent measure is suppressed rather than published as zero."""
        cell = suppress_cell(None)
        assert cell.suppressed is True
        assert cell.value is None

    def test_negative_units_are_rejected(self) -> None:
        """Verify a negative unit count is a data error, not a suppression case."""
        with pytest.raises(ValueError, match="negative"):
            suppress_cell(-1)

    def test_policy_is_reusable_for_k_anonymity_with_a_higher_k(self) -> None:
        """Verify the same mechanism serves voluntary-location k-anonymity."""
        k_anonymity = SuppressionPolicy(minimum_units=5, label="k-anonymity k=5")
        assert k_anonymity.is_suppressed(4) is True
        assert k_anonymity.is_suppressed(5) is False
        assert k_anonymity.label == "k-anonymity k=5"

    def test_suppressing_a_count_also_withholds_its_derived_share(self) -> None:
        """Verify a published share cannot be used to recover a suppressed count."""
        value, share, suppressed = suppress_measure(2, share=0.00042)
        assert suppressed is True
        assert value is None
        assert share is None

    def test_publishable_count_keeps_its_share(self) -> None:
        """Verify a cell above the threshold keeps both its count and its share."""
        value, share, suppressed = suppress_measure(4127, share=0.033811517)
        assert suppressed is False
        assert value == Decimal("4127")
        assert share == Decimal("0.033811517")

    def test_suppress_mapping_applies_the_policy_cell_by_cell(self) -> None:
        """Verify a whole breakdown is suppressed consistently in one call."""
        suppressed = suppress_mapping(
            {("H", "0_4"): 4720, ("M", "95_o_mas"): 2, ("H", "90_94"): None},
        )
        assert suppressed[("H", "0_4")].suppressed is False
        assert suppressed[("M", "95_o_mas")].suppressed is True
        assert suppressed[("H", "90_94")].suppressed is True


class TestGeoJsonFeatureStreaming:
    """Unit tests for the memory-bounded GeoJSON feature reader."""

    @staticmethod
    def _write(tmp_path: Path, payload: str) -> Path:
        target = tmp_path / "layer.geojson"
        target.write_text(payload, encoding="utf-8")
        return target

    def test_crs_block_is_not_yielded_as_a_feature(self, tmp_path: Path) -> None:
        """Verify the ArcGIS crs member is skipped, not counted as a feature."""
        payload = json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
                },
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id_depto": "01"},
                        "geometry": {"type": "Point", "coordinates": [-89.7, 13.7]},
                    }
                ],
            }
        )
        features = list(iter_geojson_features(self._write(tmp_path, payload)))
        assert len(features) == 1
        assert features[0]["properties"] == {"id_depto": "01"}

    def test_strings_containing_braces_and_escapes_do_not_break_scanning(
        self,
        tmp_path: Path,
    ) -> None:
        """Verify brace and quote characters inside property strings are tolerated."""
        payload = json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"distrito": 'A"{}\\ Ahuachapán', "n": 1},
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": [[[[-89.7, 13.7], [-89.6, 13.7], [-89.7, 13.8], [-89.7, 13.7]]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"distrito": "}}{{", "n": 2},
                        "geometry": None,
                    },
                ],
            }
        )
        features = list(iter_geojson_features(self._write(tmp_path, payload)))
        assert [f["properties"]["n"] for f in features] == [1, 2]
        assert features[0]["properties"]["distrito"] == 'A"{}\\ Ahuachapán'
        assert features[1]["geometry"] is None

    def test_empty_feature_collection_yields_nothing(self, tmp_path: Path) -> None:
        """Verify an empty features array is valid and yields no rows."""
        payload = json.dumps({"type": "FeatureCollection", "features": []})
        assert list(iter_geojson_features(self._write(tmp_path, payload))) == []

    def test_missing_features_member_raises(self, tmp_path: Path) -> None:
        """Verify a payload without a features array is rejected."""
        payload = json.dumps({"type": "FeatureCollection"})
        with pytest.raises(GeoJsonStreamError):
            list(iter_geojson_features(self._write(tmp_path, payload)))

    def test_truncated_payload_raises_instead_of_silently_stopping(
        self,
        tmp_path: Path,
    ) -> None:
        """Verify an interrupted download is detected, never partially ingested."""
        payload = '{"type":"FeatureCollection","features":[{"type":"Feature","prop'
        with pytest.raises(GeoJsonStreamError):
            list(iter_geojson_features(self._write(tmp_path, payload)))

    def test_feature_counting_matches_streamed_features(self, tmp_path: Path) -> None:
        """Verify the row-count helper agrees with the streaming iterator."""
        payload = json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"n": n}, "geometry": None}
                    for n in range(7)
                ],
            }
        )
        target = self._write(tmp_path, payload)
        assert count_geojson_features(target) == 7
        assert len(list(iter_geojson_features(target))) == 7

    def test_streaming_reads_a_small_buffer_at_a_time(self, tmp_path: Path) -> None:
        """Verify features spanning buffer boundaries are still parsed correctly."""
        payload = json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"n": n, "pad": "x" * 200},
                        "geometry": {"type": "Point", "coordinates": [-89.0, 13.0]},
                    }
                    for n in range(40)
                ],
            }
        )
        target = self._write(tmp_path, payload)
        features = list(iter_geojson_features(target, buffer_size=64))
        assert [f["properties"]["n"] for f in features] == list(range(40))


class TestCensusLayerCatalog:
    """Unit tests for the declarative census layer catalogue."""

    def test_every_layer_declares_a_filename_and_expected_count(self) -> None:
        """Verify the catalogue is complete enough to assert a regenerated download."""
        assert CENSUS_LAYERS
        for layer in CENSUS_LAYERS:
            assert isinstance(layer, CensusLayer)
            assert layer.filename.endswith((".geojson", ".csv"))
            assert layer.expected_feature_count > 0
            assert layer.service_name
            assert layer.layer_id >= 0

    def test_filenames_are_unique(self) -> None:
        """Verify no two catalogue entries fight over the same local file."""
        filenames = [layer.filename for layer in CENSUS_LAYERS]
        assert len(filenames) == len(set(filenames))

    def test_layer_lookup_by_filename(self) -> None:
        """Verify a catalogue entry can be resolved from its local filename."""
        layer = layer_by_filename("degurba_densidad.geojson")
        assert layer.expected_feature_count == 1345
        with pytest.raises(KeyError):
            layer_by_filename("not_a_census_layer.geojson")

    def test_query_url_requests_wgs84_and_pages(self) -> None:
        """Verify the generated query URL exports EPSG:4326 and honours paging."""
        layer = layer_by_filename("segmentos_censales_2024.geojson")
        url, params = layer.build_query(offset=2000, page_size=1000)
        assert url.endswith(f"/{layer.service_name}/FeatureServer/{layer.layer_id}/query")
        assert params["outSR"] == "4326"
        assert params["resultOffset"] == "2000"
        assert params["resultRecordCount"] == "1000"
        assert params["where"] == "1=1"
        assert params["outFields"] == "*"


class TestCensusModelSchema:
    """Inspection tests for the SQLAlchemy 2.0 + GeoAlchemy2 census tables."""

    def test_admin_unit_table_shape(self) -> None:
        """Verify census_admin_unit keys the unified hierarchy on its code."""
        table = CensusAdminUnitModel.__table__
        assert table.name == "census_admin_unit"
        assert [column.name for column in table.primary_key.columns] == ["code"]
        geom = table.columns["geom"]
        assert isinstance(geom.type, Geography)
        assert geom.type.geometry_type == "MULTIPOLYGON"
        assert geom.type.srid == 4326
        parent_fk = next(iter(table.columns["parent_code"].foreign_keys))
        assert parent_fk.column.table.name == "census_admin_unit"

    def test_population_unit_is_unique_per_district_class_and_level(self) -> None:
        """Verify the DEGURBA grain is one row per district, class and level."""
        table = CensusPopulationUnitModel.__table__
        assert table.name == "census_population_unit"
        unique = {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert ("district_code", "dug_class", "dug_level") in unique
        district_fk = next(iter(table.columns["district_code"].foreign_keys))
        assert district_fk.column.table.name == "census_admin_unit"

    def test_indicator_table_is_long_format(self) -> None:
        """Verify census_indicator stores one row per topic, category, sex and band."""
        table = CensusIndicatorModel.__table__
        assert table.name == "census_indicator"
        for column_name in (
            "unit_code",
            "unit_level",
            "topic",
            "category",
            "sex",
            "age_band",
            "value",
            "share",
            "suppressed",
        ):
            assert column_name in table.columns
        assert table.columns["sex"].nullable is True
        assert table.columns["age_band"].nullable is True
        assert table.columns["suppressed"].nullable is False

    def test_segment_table_carries_geometry_without_population(self) -> None:
        """Verify census_segment is geometry-only context, with no population column."""
        table = CensusSegmentModel.__table__
        assert table.name == "census_segment"
        assert [column.name for column in table.primary_key.columns] == ["segment_code"]
        assert "population" not in table.columns
        assert "households" not in table.columns

    def test_every_geography_column_has_a_gist_index(self) -> None:
        """Verify no geography column is left without its spatial index."""
        for model in (
            CensusAdminUnitModel,
            CensusPopulationUnitModel,
            CensusSegmentModel,
        ):
            table = model.__table__
            geography_columns = [
                column.name
                for column in table.columns
                if isinstance(column.type, Geography)
            ]
            assert geography_columns, f"{table.name} has no geography column"
            indexed: set[str] = set()
            for index in table.indexes:
                if index.kwargs.get("postgresql_using") == "gist":
                    indexed.update(column.name for column in index.columns)
            for column_name in geography_columns:
                assert column_name in indexed, f"{table.name}.{column_name} lacks a GIST index"


def _polygon(longitude: float, latitude: float) -> dict[str, object]:
    """Build a small valid square polygon anchored at the given corner."""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [longitude, latitude],
                [longitude + 0.1, latitude],
                [longitude + 0.1, latitude + 0.1],
                [longitude, latitude + 0.1],
                [longitude, latitude],
            ]
        ],
    }


def _feature_collection(features: list[dict[str, object]]) -> str:
    """Serialise features the way ArcGIS does, including the crs member."""
    return json.dumps(
        {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
            },
            "features": features,
        }
    )


class TestCensusLoadersAgainstPostGIS:
    """Integration tests for the loaders, rolled back so no residue is committed."""

    @staticmethod
    def _skip_unless_schema_present(tables: set[str]) -> None:
        if not {
            "census_admin_unit",
            "census_population_unit",
            "census_indicator",
            "census_segment",
        } <= tables:
            pytest.skip("census tables absent: run 'alembic upgrade head' first")

    @staticmethod
    def _write_boundary_fixtures(raw_dir: Path) -> None:
        """Write three boundary layers holding one real unit and every sentinel shape."""
        (raw_dir / "limites_departamentos_cnr_sirgas.geojson").write_text(
            _feature_collection(
                [
                    {
                        "type": "Feature",
                        "properties": {"id_depto": "91", "depto": "Testland"},
                        "geometry": _polygon(-89.0, 13.0),
                    },
                    {
                        "type": "Feature",
                        "properties": {"id_depto": "00", "depto": "Nacional"},
                        "geometry": _polygon(-89.0, 13.0),
                    },
                ]
            ),
            encoding="utf-8",
        )
        (raw_dir / "limites_municipios_cnr_sirgas.geojson").write_text(
            _feature_collection(
                [
                    {
                        "type": "Feature",
                        "properties": {"id_depto": "91", "id_mun": "9101", "mun": "Testville"},
                        "geometry": _polygon(-89.0, 13.0),
                    },
                    {
                        "type": "Feature",
                        "properties": {"id_depto": "91", "id_mun": "AAA", "mun": "Todos"},
                        "geometry": _polygon(-89.0, 13.0),
                    },
                    {
                        "type": "Feature",
                        "properties": {"id_depto": "00", "id_mun": "0000", "mun": "Nacional"},
                        "geometry": _polygon(-89.0, 13.0),
                    },
                ]
            ),
            encoding="utf-8",
        )
        (raw_dir / "limites_distritos_cnr_sirgas.geojson").write_text(
            _feature_collection(
                [
                    {
                        "type": "Feature",
                        "properties": {
                            "id_depto": "91",
                            "id_mun": "9101",
                            "id_distrito": "910101",
                            "distrito": "Test District",
                        },
                        "geometry": _polygon(-89.0, 13.0),
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id_depto": None,
                            "id_mun": "9101",
                            "id_distrito": "AAA",
                            "distrito": "Todos",
                        },
                        "geometry": _polygon(-89.0, 13.0),
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id_depto": "15",
                            "id_mun": "1501",
                            "id_distrito": "150101",
                            "distrito": "RRAA",
                        },
                        "geometry": None,
                    },
                ]
            ),
            encoding="utf-8",
        )

    async def test_boundary_loader_skips_every_sentinel_shape(self, tmp_path: Path) -> None:
        """Verify national, 'AAA' and department-15 rows never become admin units."""
        from app.modules.census.infrastructure.loaders import load_admin_units
        from app.modules.census.infrastructure.repository import CensusRepository

        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                try:
                    tables = set(
                        (
                            await session.execute(
                                text(
                                    "SELECT table_name FROM information_schema.tables "
                                    "WHERE table_schema='public' AND table_name LIKE 'census%'"
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                except Exception as exc:
                    pytest.skip(f"PostGIS container is not reachable: {exc}")
                self._skip_unless_schema_present(tables)

                self._write_boundary_fixtures(tmp_path)
                repository = CensusRepository(session)
                try:
                    report = await load_admin_units(
                        repository,
                        tmp_path,
                        expected_units={
                            CensusLevel.DEPARTAMENTO: 1,
                            CensusLevel.MUNICIPIO: 1,
                            CensusLevel.DISTRITO: 1,
                        },
                    )

                    assert report.rows_written == 3
                    assert report.rows_skipped_sentinel == 5

                    rows = (
                        await session.execute(
                            text(
                                "SELECT code, level, parent_code, name "
                                "FROM census_admin_unit WHERE code LIKE '91%' "
                                "ORDER BY length(code)"
                            )
                        )
                    ).all()
                    assert [(row.code, row.level, row.parent_code) for row in rows] == [
                        ("91", "departamento", None),
                        ("9101", "municipio", "91"),
                        ("910101", "distrito", "9101"),
                    ]

                    stored = (
                        await session.execute(
                            text(
                                "SELECT ST_GeometryType(geom::geometry) AS kind "
                                "FROM census_admin_unit WHERE code = '91'"
                            )
                        )
                    ).scalar_one()
                    assert stored == "ST_MultiPolygon"
                finally:
                    await session.rollback()
        finally:
            await engine.dispose()

    async def test_population_indicator_loader_enforces_every_data_defect(
        self,
        tmp_path: Path,
    ) -> None:
        """Verify defective totals, sentinels and sub-threshold cells are all handled."""
        from app.modules.census.infrastructure.loaders import (
            load_admin_units,
            load_population_indicators,
        )
        from app.modules.census.infrastructure.repository import CensusRepository

        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                try:
                    tables = set(
                        (
                            await session.execute(
                                text(
                                    "SELECT table_name FROM information_schema.tables "
                                    "WHERE table_schema='public' AND table_name LIKE 'census%'"
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                except Exception as exc:
                    pytest.skip(f"PostGIS container is not reachable: {exc}")
                self._skip_unless_schema_present(tables)

                self._write_boundary_fixtures(tmp_path)

                bands = {f"H_{band}": 0 for band in AGE_BANDS}
                bands.update({f"M_{band}": 0 for band in AGE_BANDS})
                # 300 men and 200 women, plus one deliberately sub-threshold cell.
                bands["H_30_34"] = 300
                bands["M_30_34"] = 198
                bands["M_95_o_mas"] = 2
                district = {
                    "Dep_id": "91",
                    "Mun_id": "9101",
                    "Dis_id": "910101",
                    "Dis_min": "Test District",
                    "Hombre": 300,
                    "Mujer": 200,
                    # Defective column: deliberately disagrees with Hombre + Mujer.
                    "Total_Personas": 499,
                    **bands,
                }
                unlocated_bands = {f"H_{band}": 0 for band in AGE_BANDS}
                unlocated_bands.update({f"M_{band}": 0 for band in AGE_BANDS})
                unlocated_bands["H_30_34"] = UNLOCATED_POPULATION_TOTAL
                unlocated = {
                    "Dep_id": "15",
                    "Mun_id": "1501",
                    "Dis_id": "150101",
                    "Dis_min": "RRAA",
                    "Hombre": UNLOCATED_POPULATION_TOTAL,
                    "Mujer": 0,
                    "Total_Personas": UNLOCATED_POPULATION_TOTAL,
                    **unlocated_bands,
                }
                (tmp_path / "distritos_poblacion_edad_sexo.geojson").write_text(
                    _feature_collection(
                        [
                            {
                                "type": "Feature",
                                "properties": district,
                                "geometry": _polygon(-89.0, 13.0),
                            },
                            {
                                "type": "Feature",
                                "properties": unlocated,
                                "geometry": None,
                            },
                        ]
                    ),
                    encoding="utf-8",
                )

                repository = CensusRepository(session)
                try:
                    await load_admin_units(
                        repository,
                        tmp_path,
                        expected_units={
                            CensusLevel.DEPARTAMENTO: 1,
                            CensusLevel.MUNICIPIO: 1,
                            CensusLevel.DISTRITO: 1,
                        },
                    )
                    report, totals = await load_population_indicators(
                        repository,
                        tmp_path,
                        filenames=("distritos_poblacion_edad_sexo.geojson",),
                        expected_units={CensusLevel.DISTRITO: 1},
                    )

                    # Defect 1: the total is Hombre + Mujer (500), never Total_Personas (499).
                    total_cell = (
                        await session.execute(
                            text(
                                "SELECT value FROM census_indicator "
                                "WHERE unit_code='910101' AND topic='poblacion' "
                                "AND category='total' AND sex IS NULL"
                            )
                        )
                    ).scalar_one()
                    assert int(total_cell) == 500

                    # Defect 2: the unlocated pseudo-department is harvested, not stored.
                    assert totals.unlocated == UNLOCATED_POPULATION_TOTAL
                    assert totals.georeferenced == 500
                    assert report.rows_skipped_sentinel == 1
                    orphan = (
                        await session.execute(
                            text(
                                "SELECT count(*) FROM census_indicator "
                                "WHERE unit_code LIKE '15%'"
                            )
                        )
                    ).scalar_one()
                    assert orphan == 0

                    # Statistical secrecy: the 2-woman cell is withheld, value and share.
                    withheld = (
                        await session.execute(
                            text(
                                "SELECT value, share, suppressed FROM census_indicator "
                                "WHERE unit_code='910101' AND topic='edad_sexo' "
                                "AND sex='M' AND age_band='95_o_mas'"
                            )
                        )
                    ).one()
                    assert withheld.suppressed is True
                    assert withheld.value is None
                    assert withheld.share is None
                    assert report.rows_suppressed >= 1

                    # A structural zero is published as a true zero, not suppressed.
                    zero_cell = (
                        await session.execute(
                            text(
                                "SELECT value, suppressed FROM census_indicator "
                                "WHERE unit_code='910101' AND topic='edad_sexo' "
                                "AND sex='H' AND age_band='0_4'"
                            )
                        )
                    ).one()
                    assert zero_cell.suppressed is False
                    assert int(zero_cell.value) == 0

                    # Attribution is stored with every cell.
                    attribution = (
                        await session.execute(
                            text(
                                "SELECT DISTINCT source FROM census_indicator "
                                "WHERE unit_code='910101'"
                            )
                        )
                    ).scalars().all()
                    assert attribution == [CENSUS_SOURCE_ATTRIBUTION]
                finally:
                    await session.rollback()
        finally:
            await engine.dispose()

    async def test_loaders_are_idempotent(self, tmp_path: Path) -> None:
        """Verify re-running a loader upserts instead of duplicating rows."""
        from app.modules.census.infrastructure.loaders import load_admin_units
        from app.modules.census.infrastructure.repository import CensusRepository

        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                try:
                    tables = set(
                        (
                            await session.execute(
                                text(
                                    "SELECT table_name FROM information_schema.tables "
                                    "WHERE table_schema='public' AND table_name LIKE 'census%'"
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                except Exception as exc:
                    pytest.skip(f"PostGIS container is not reachable: {exc}")
                self._skip_unless_schema_present(tables)

                self._write_boundary_fixtures(tmp_path)
                repository = CensusRepository(session)
                expected = {
                    CensusLevel.DEPARTAMENTO: 1,
                    CensusLevel.MUNICIPIO: 1,
                    CensusLevel.DISTRITO: 1,
                }
                try:
                    await load_admin_units(repository, tmp_path, expected_units=expected)
                    await load_admin_units(repository, tmp_path, expected_units=expected)
                    stored = (
                        await session.execute(
                            text(
                                "SELECT count(*) FROM census_admin_unit "
                                "WHERE code LIKE '91%'"
                            )
                        )
                    ).scalar_one()
                    assert stored == 3
                finally:
                    await session.rollback()
        finally:
            await engine.dispose()

    async def test_segment_loader_never_reads_a_population_attribute(self) -> None:
        """Verify the segment loader declares a field contract free of population."""
        from app.modules.census.infrastructure.loaders import SEGMENT_SOURCE_FIELDS

        population_like = {
            field
            for field in SEGMENT_SOURCE_FIELDS
            if "person" in field.lower()
            or "pobla" in field.lower()
            or "hogar" in field.lower()
            or "vivienda" in field.lower()
        }
        assert population_like == set()


class TestIngestedCorpusContract:
    """Contract tests over an already-ingested corpus, skipped when it is absent.

    These assert the published census figures against what is actually stored, so
    a regression in a loader shows up as a wrong national total rather than as a
    silently different number of rows.
    """

    @staticmethod
    async def _fetch(statement: str) -> Any:
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                try:
                    populated = (
                        await session.execute(
                            text("SELECT count(*) FROM census_population_unit")
                        )
                    ).scalar_one()
                except Exception as exc:
                    pytest.skip(f"census corpus is not ingested: {exc}")
                if not populated:
                    pytest.skip(
                        "census corpus is empty: run "
                        "'uv run python -m scripts.ingest_census' first"
                    )
                return (await session.execute(text(statement))).all()
        finally:
            await engine.dispose()

    async def test_degurba_analysis_level_totals_match_the_published_census(self) -> None:
        """Verify the 902 DEGURBA Nivel 2 units hold exactly the published figures."""
        rows = await self._fetch(
            "SELECT count(*) AS units, sum(population) AS population, "
            "sum(households) AS households, sum(dwellings) AS dwellings "
            "FROM census_population_unit WHERE dug_level = 2"
        )
        row = rows[0]
        assert row.units == 902
        assert row.population == GEOREFERENCED_POPULATION_TOTAL
        assert row.households == 1_922_420
        assert row.dwellings == 2_272_704

    async def test_administrative_hierarchy_matches_the_2023_reorganisation(self) -> None:
        """Verify 14 departments, 44 municipalities and 262 districts are stored."""
        rows = await self._fetch(
            "SELECT level, count(*) AS units FROM census_admin_unit "
            "GROUP BY level ORDER BY level"
        )
        assert {row.level: row.units for row in rows} == {
            "departamento": 14,
            "municipio": 44,
            "distrito": 262,
        }

    async def test_no_sentinel_territory_reached_the_database(self) -> None:
        """Verify no 'Otros', 'AAA' or national rollup row was ever stored."""
        rows = await self._fetch(
            "SELECT count(*) AS leaked FROM census_admin_unit "
            "WHERE code LIKE '15%' OR code ~ '^0+$' OR code IN ('AAA', 'RRAA') "
            "UNION ALL "
            "SELECT count(*) FROM census_indicator "
            "WHERE unit_code LIKE '15%' OR unit_code ~ '^0+$' "
            "UNION ALL "
            "SELECT count(*) FROM census_segment WHERE segment_code ~ '^0+$'"
        )
        assert [row.leaked for row in rows] == [0, 0, 0]

    async def test_no_suppressed_cell_leaks_its_value_or_share(self) -> None:
        """Verify every withheld cell is withheld in both columns."""
        rows = await self._fetch(
            "SELECT count(*) AS leaked FROM census_indicator "
            "WHERE suppressed AND (value IS NOT NULL OR share IS NOT NULL)"
        )
        assert rows[0].leaked == 0

    async def test_suppression_is_actually_exercised_by_the_corpus(self) -> None:
        """Verify the threshold genuinely withholds cells rather than being inert."""
        rows = await self._fetch(
            "SELECT count(*) AS withheld FROM census_indicator WHERE suppressed"
        )
        assert rows[0].withheld > 0

    async def test_every_stored_geometry_is_valid_and_multipolygon(self) -> None:
        """Verify the simplification pipeline never stored an invalid polygon."""
        rows = await self._fetch(
            "SELECT count(*) AS broken FROM ("
            "SELECT geom FROM census_admin_unit UNION ALL "
            "SELECT geom FROM census_population_unit UNION ALL "
            "SELECT geom FROM census_segment"
            ") AS geometries "
            "WHERE NOT ST_IsValid(geom::geometry) "
            "OR ST_GeometryType(geom::geometry) <> 'ST_MultiPolygon'"
        )
        assert rows[0].broken == 0

    async def test_stored_coordinates_are_rounded_to_six_decimals(self) -> None:
        """Verify no stored ordinate carries more precision than the 1e-6 grid."""
        rows = await self._fetch(
            "SELECT max(abs(ordinate * 1000000 - round(ordinate * 1000000))) "
            "AS grid_error FROM ("
            "SELECT ST_X((ST_DumpPoints(geom::geometry)).geom) AS ordinate "
            "FROM census_population_unit UNION ALL "
            "SELECT ST_Y((ST_DumpPoints(geom::geometry)).geom) "
            "FROM census_population_unit"
            ") AS ordinates"
        )
        assert float(rows[0].grid_error) < 1e-3

    async def test_segment_polygons_are_urban_or_rural_context_only(self) -> None:
        """Verify all 10,290 segments are stored and classified, with no population."""
        rows = await self._fetch(
            "SELECT area_type, count(*) AS segments FROM census_segment "
            "GROUP BY area_type ORDER BY area_type"
        )
        assert {row.area_type: row.segments for row in rows} == {
            "RURAL": 3066,
            "URBANO": 7224,
        }

    async def test_disability_total_agrees_across_all_three_levels(self) -> None:
        """Verify the 281,463 national disability figure reconciles at every level."""
        rows = await self._fetch(
            "SELECT unit_level, sum(value)::bigint AS people FROM census_indicator "
            "WHERE topic = 'discapacidad' GROUP BY unit_level"
        )
        assert {row.people for row in rows} == {281_463}

    async def test_every_stored_cell_carries_the_required_attribution(self) -> None:
        """Verify "BCR/ONEC, CPV 2024" is recorded on every census row."""
        rows = await self._fetch(
            "SELECT DISTINCT source FROM ("
            "SELECT source FROM census_admin_unit UNION "
            "SELECT source FROM census_population_unit UNION "
            "SELECT source FROM census_indicator UNION "
            "SELECT source FROM census_segment"
            ") AS sources"
        )
        assert [row.source for row in rows] == [CENSUS_SOURCE_ATTRIBUTION]


class TestCensusSchemaAppliedToPostGIS:
    """Live integration tests against the PostgreSQL 16 + PostGIS 3.4 container."""

    async def test_migration_created_all_four_census_tables_with_gist_indexes(self) -> None:
        """Verify migration 0003 applied the four census tables and their GIST indexes."""
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                try:
                    await session.execute(text("SELECT 1"))
                except Exception as exc:
                    pytest.skip(f"PostGIS container is not reachable: {exc}")

                tables = set(
                    (
                        await session.execute(
                            text(
                                "SELECT table_name FROM information_schema.tables "
                                "WHERE table_schema = 'public' "
                                "AND table_name LIKE 'census%'"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                if not tables:
                    pytest.skip("census tables absent: run 'alembic upgrade head' first")

                assert {
                    "census_admin_unit",
                    "census_population_unit",
                    "census_indicator",
                    "census_segment",
                } <= tables

                gist_indexes = set(
                    (
                        await session.execute(
                            text(
                                "SELECT indexname FROM pg_indexes "
                                "WHERE schemaname = 'public' "
                                "AND tablename LIKE 'census%' "
                                "AND indexdef ILIKE '%USING gist%'"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert {
                    "idx_census_admin_unit_geom",
                    "idx_census_population_unit_geom",
                    "idx_census_segment_geom",
                } <= gist_indexes
        finally:
            await engine.dispose()

    async def test_geometry_expression_snaps_coordinates_to_six_decimals(self) -> None:
        """Verify the stored-geometry expression rounds every ordinate to a 1e-6 grid."""
        from app.modules.census.infrastructure.repository import (
            GEOMETRY_GRID_SIZE,
            GEOMETRY_SIMPLIFY_TOLERANCE,
            simplified_geography_sql,
        )

        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                try:
                    await session.execute(text("SELECT 1"))
                except Exception as exc:
                    pytest.skip(f"PostGIS container is not reachable: {exc}")

                assert GEOMETRY_GRID_SIZE == 0.000001
                assert GEOMETRY_SIMPLIFY_TOLERANCE > 0

                raw = json.dumps(
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-89.70000012345678, 13.70000012345678],
                                [-89.60000087654321, 13.70000012345678],
                                [-89.60000087654321, 13.80000098765432],
                                [-89.70000012345678, 13.80000098765432],
                                [-89.70000012345678, 13.70000012345678],
                            ]
                        ],
                    }
                )
                geometry_sql = simplified_geography_sql(":geojson")
                result = await session.execute(
                    text(
                        "SELECT ST_GeometryType(stored::geometry) AS kind, "
                        "ST_SRID(stored::geometry) AS srid, "
                        "(SELECT max(abs(ordinate * 1000000 "
                        "- round(ordinate * 1000000))) FROM ("
                        "SELECT ST_X(point) AS ordinate FROM ("
                        "SELECT (ST_DumpPoints(stored::geometry)).geom AS point"
                        ") AS points "
                        "UNION ALL "
                        "SELECT ST_Y(point) FROM ("
                        "SELECT (ST_DumpPoints(stored::geometry)).geom AS point"
                        ") AS points"
                        ") AS ordinates) AS grid_error "
                        f"FROM (SELECT {geometry_sql} AS stored) AS computed"
                    ),
                    {"geojson": raw},
                )
                row = result.one()
                assert row.kind == "ST_MultiPolygon"
                assert row.srid == 4326
                assert float(row.grid_error) < 1e-3
        finally:
            await engine.dispose()

    async def test_geometry_expression_reduces_vertex_count(self) -> None:
        """Verify ST_SimplifyPreserveTopology actually drops redundant vertices."""
        from app.modules.census.infrastructure.repository import simplified_geography_sql

        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                try:
                    await session.execute(text("SELECT 1"))
                except Exception as exc:
                    pytest.skip(f"PostGIS container is not reachable: {exc}")

                # A dense, almost-straight edge: 200 vertices spanning 0.2 degrees.
                dense_edge = [[-90.0 + step * 0.001, 13.0 + step * 0.0000001] for step in range(200)]
                ring = [*dense_edge, [-89.8, 13.5], [-90.0, 13.5], [-90.0, 13.0]]
                raw = json.dumps({"type": "Polygon", "coordinates": [ring]})

                result = await session.execute(
                    text(
                        "SELECT ST_NPoints(ST_GeomFromGeoJSON(:geojson)) AS before, "
                        f"ST_NPoints({simplified_geography_sql(':geojson')}::geometry) AS after"
                    ),
                    {"geojson": raw},
                )
                row = result.one()
                assert row.before == len(ring)
                assert row.after < row.before
        finally:
            await engine.dispose()
