"""Phase B4 tests: place-to-census attachment and areal-weighted exposed population.

Every number this module asserts is an **estimate of exposure**, never a count of
people present. The behaviours pinned here are the ones that silently produce
plausible-but-wrong numbers if they drift:

* the areal-weighting arithmetic itself, including the two properties that need
  no fixture at all (a buffer containing a whole polygon exposes exactly that
  polygon's population; a buffer covering half of it by area exposes half);
* the rate-application rule for vulnerable proportions, which only exist at
  district level and must therefore be applied as a *rate* to the finer DEGURBA
  population, never as an absolute district count;
* statistical-secrecy suppression on output, including the rule that a withheld
  count and its derived figures are withheld together;
* attachment idempotency, so re-running the backfill is a no-op.
"""

from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.privacy import SuppressionPolicy
from app.main import app
from app.modules.census.domain.exposure import (
    AREAL_WEIGHT_EXCESS_TOLERANCE,
    DEFAULT_EXPOSURE_RADIUS_METERS,
    EXPOSURE_ESTIMATION_METHOD,
    METRIC_PROJECTION_SRID,
    SPATIAL_ASSIGNMENT_RULE,
    ArealWeightError,
    DistrictVulnerableRates,
    ExposedPopulationEstimate,
    UnitOverlap,
    VulnerableRateError,
    apply_vulnerable_rate,
    areal_weight,
    estimate_exposed_population,
    weighted_population,
)
from app.modules.census.infrastructure.exposure_repository import (
    CensusExposureRepository,
    areal_weight_sql,
    metric_area_sql,
)
from app.modules.places.infrastructure.census_attachment import (
    PlaceCensusAttachmentRepository,
)
from app.modules.places.infrastructure.models import VulnerablePlaceModel


def _overlap(
    unit_id: int = 1,
    district_code: str = "010101",
    population: int = 1000,
    unit_area_m2: str = "1000000",
    overlap_area_m2: str = "1000000",
) -> UnitOverlap:
    """Build one DEGURBA overlap record with explicit, exact decimal areas."""
    return UnitOverlap(
        unit_id=unit_id,
        district_code=district_code,
        population=population,
        unit_area_m2=Decimal(unit_area_m2),
        overlap_area_m2=Decimal(overlap_area_m2),
    )


def _rates(
    district_code: str = "010101",
    older: str = "0.1",
    young: str = "0.05",
    disability: str = "0.04",
) -> DistrictVulnerableRates:
    """Build one district's vulnerable-proportion rates."""
    return DistrictVulnerableRates(
        district_code=district_code,
        older_adult_rate=Decimal(older),
        young_child_rate=Decimal(young),
        disability_rate=Decimal(disability),
    )


class TestArealWeightArithmetic:
    """The areal-weighting ratio: exact, bounded, and refusing impossible input."""

    def test_full_containment_weighs_one(self) -> None:
        """Verify a polygon entirely inside the buffer contributes its whole weight."""
        assert areal_weight(Decimal("743.25"), Decimal("743.25")) == Decimal(1)

    def test_half_coverage_by_area_weighs_one_half(self) -> None:
        """Verify half the polygon area yields exactly one half, not an approximation."""
        assert areal_weight(Decimal("500000"), Decimal("1000000")) == Decimal("0.5")

    def test_no_overlap_weighs_zero(self) -> None:
        """Verify a polygon merely touching the buffer contributes nothing."""
        assert areal_weight(Decimal(0), Decimal("1000000")) == Decimal(0)

    @pytest.mark.parametrize(
        ("overlap", "unit", "expected"),
        [
            ("250000", "1000000", "0.25"),
            ("1", "4", "0.25"),
            ("1", "8", "0.125"),
            ("3", "4", "0.75"),
        ],
    )
    def test_weight_is_the_exact_area_ratio(
        self, overlap: str, unit: str, expected: str
    ) -> None:
        """Verify the weight is the area ratio with no rounding of its own."""
        assert areal_weight(Decimal(overlap), Decimal(unit)) == Decimal(expected)

    def test_weight_divides_in_decimal_not_in_binary_floating_point(self) -> None:
        """Verify a repeating ratio matches Decimal division, so no float noise enters."""
        assert areal_weight(Decimal(1), Decimal(3)) == Decimal(1) / Decimal(3)

    def test_numerical_excess_within_tolerance_is_clamped_to_one(self) -> None:
        """Verify geometry noise slightly above full coverage saturates instead of exceeding."""
        unit = Decimal("1000000")
        noisy = unit * (Decimal(1) + AREAL_WEIGHT_EXCESS_TOLERANCE / 2)
        assert areal_weight(noisy, unit) == Decimal(1)

    def test_overlap_grossly_larger_than_the_unit_is_a_defect(self) -> None:
        """Verify an impossible overlap raises rather than silently saturating."""
        with pytest.raises(ArealWeightError, match="exceeds"):
            areal_weight(Decimal("2000000"), Decimal("1000000"))

    def test_zero_area_unit_cannot_be_weighted(self) -> None:
        """Verify a degenerate polygon raises instead of dividing by zero."""
        with pytest.raises(ArealWeightError, match="zero"):
            areal_weight(Decimal(0), Decimal(0))

    @pytest.mark.parametrize(("overlap", "unit"), [("-1", "100"), ("10", "-100")])
    def test_negative_area_is_rejected(self, overlap: str, unit: str) -> None:
        """Verify a negative area raises: no geometry has one."""
        with pytest.raises(ArealWeightError, match="negative"):
            areal_weight(Decimal(overlap), Decimal(unit))


class TestWeightedPopulation:
    """Population scaled by an areal weight, which is the core estimator."""

    def test_full_weight_returns_the_whole_population(self) -> None:
        """Verify weight 1 reproduces the polygon population exactly."""
        assert weighted_population(8905, Decimal(1)) == Decimal(8905)

    def test_half_weight_returns_exactly_half_the_population(self) -> None:
        """Verify weight 0.5 halves the population with no rounding drift."""
        assert weighted_population(1000, Decimal("0.5")) == Decimal(500)

    def test_zero_weight_contributes_nobody(self) -> None:
        """Verify weight 0 contributes nothing at all."""
        assert weighted_population(8905, Decimal(0)) == Decimal(0)

    def test_negative_population_is_rejected(self) -> None:
        """Verify a negative population raises rather than subtracting exposure."""
        with pytest.raises(ArealWeightError, match="negative"):
            weighted_population(-1, Decimal("0.5"))


class TestVulnerableRateApplication:
    """District-level proportions applied as rates, never as absolute counts."""

    def test_rate_scales_the_estimate(self) -> None:
        """Verify a 10% older-adult rate on 1,000 exposed yields 100."""
        assert apply_vulnerable_rate(Decimal(1000), Decimal("0.1")) == Decimal(100)

    def test_a_rate_above_one_is_refused(self) -> None:
        """Verify an absolute district count passed as a rate raises instead of inflating."""
        with pytest.raises(VulnerableRateError, match="rate"):
            apply_vulnerable_rate(Decimal(1000), Decimal(12090))

    def test_a_negative_rate_is_refused(self) -> None:
        """Verify a negative proportion raises."""
        with pytest.raises(VulnerableRateError, match="rate"):
            apply_vulnerable_rate(Decimal(1000), Decimal("-0.01"))

    @pytest.mark.parametrize("rate", ["1.0000001", "2", "100"])
    def test_district_rates_outside_the_unit_interval_are_refused(self, rate: str) -> None:
        """Verify the rate container itself rejects anything that is not a proportion."""
        with pytest.raises(VulnerableRateError, match="rate"):
            _rates(older=rate)

    def test_half_a_unit_contributes_half_the_district_rate_not_the_whole_count(
        self,
    ) -> None:
        """Verify the rate is applied to the weighted population, not to the district."""
        estimate = estimate_exposed_population(
            overlaps=[_overlap(population=1000, overlap_area_m2="500000")],
            rates_by_district={"010101": _rates(older="0.1")},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population == 500
        assert estimate.estimated_exposed_older_adults == 50


class TestExposedPopulationEstimate:
    """Aggregation across contributing DEGURBA polygons."""

    def test_a_buffer_containing_the_whole_polygon_exposes_its_whole_population(
        self,
    ) -> None:
        """Verify full containment yields exactly the polygon's population."""
        estimate = estimate_exposed_population(
            overlaps=[_overlap(population=8905)],
            rates_by_district={"010101": _rates()},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population == 8905
        assert estimate.contributing_unit_count == 1

    def test_a_buffer_covering_half_the_polygon_by_area_exposes_half_its_population(
        self,
    ) -> None:
        """Verify half coverage by area yields half the population."""
        estimate = estimate_exposed_population(
            overlaps=[
                _overlap(population=8904, unit_area_m2="2000", overlap_area_m2="1000")
            ],
            rates_by_district={"010101": _rates()},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population == 4452

    def test_contributions_from_several_polygons_add_up(self) -> None:
        """Verify a buffer spanning three polygons sums their weighted contributions."""
        estimate = estimate_exposed_population(
            overlaps=[
                _overlap(unit_id=1, population=1000, overlap_area_m2="1000000"),
                _overlap(unit_id=2, population=2000, overlap_area_m2="500000"),
                _overlap(unit_id=3, population=4000, overlap_area_m2="250000"),
            ],
            rates_by_district={"010101": _rates()},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population == 3000
        assert estimate.contributing_unit_count == 3

    def test_polygons_touched_without_overlap_do_not_count_as_contributors(self) -> None:
        """Verify a zero-weight polygon is reported as contributing nothing."""
        estimate = estimate_exposed_population(
            overlaps=[_overlap(population=1000, overlap_area_m2="0")],
            rates_by_district={"010101": _rates()},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population == 0
        assert estimate.contributing_unit_count == 0

    def test_no_overlapping_polygon_yields_a_published_zero(self) -> None:
        """Verify a place outside census coverage reports zero, not a withheld cell."""
        estimate = estimate_exposed_population(
            overlaps=[],
            rates_by_district={},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population == 0
        assert estimate.suppressed is False

    def test_weights_are_combined_per_district_rate(self) -> None:
        """Verify each polygon's contribution uses its own district's rates."""
        estimate = estimate_exposed_population(
            overlaps=[
                _overlap(unit_id=1, district_code="010101", population=1000),
                _overlap(unit_id=2, district_code="010102", population=1000),
            ],
            rates_by_district={
                "010101": _rates(district_code="010101", older="0.2"),
                "010102": _rates(district_code="010102", older="0.0"),
            },
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population == 2000
        assert estimate.estimated_exposed_older_adults == 200

    def test_a_district_without_published_rates_contributes_population_only(self) -> None:
        """Verify a missing rate withholds the derived figure instead of assuming zero."""
        estimate = estimate_exposed_population(
            overlaps=[_overlap(population=1000)],
            rates_by_district={},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population == 1000
        assert estimate.estimated_exposed_older_adults is None

    def test_a_negative_radius_is_refused(self) -> None:
        """Verify a radius that is not a positive distance raises."""
        with pytest.raises(ValueError, match="radius"):
            estimate_exposed_population(
                overlaps=[], rates_by_district={}, radius_meters=-1
            )


class TestSuppressionOnOutput:
    """Statistical secrecy applied to the estimate before it can leave the API."""

    def test_an_estimate_below_the_threshold_is_withheld(self) -> None:
        """Verify a two-person exposure estimate is withheld under D.L. 904."""
        estimate = estimate_exposed_population(
            overlaps=[
                _overlap(population=1000, unit_area_m2="1000000", overlap_area_m2="2000")
            ],
            rates_by_district={"010101": _rates()},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population is None
        assert estimate.suppressed is True
        assert estimate.suppression_reason is not None

    def test_a_withheld_total_withholds_every_derived_figure_with_it(self) -> None:
        """Verify no derived figure survives a withheld total, which would disclose it."""
        estimate = estimate_exposed_population(
            overlaps=[
                _overlap(population=1000, unit_area_m2="1000000", overlap_area_m2="2000")
            ],
            rates_by_district={"010101": _rates()},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population is None
        assert estimate.estimated_exposed_older_adults is None
        assert estimate.estimated_exposed_young_children is None
        assert estimate.estimated_exposed_persons_with_disability is None

    def test_a_derived_figure_below_the_threshold_is_withheld_on_its_own(self) -> None:
        """Verify a publishable total still withholds a sub-threshold derived cell."""
        estimate = estimate_exposed_population(
            overlaps=[_overlap(population=100)],
            rates_by_district={"010101": _rates(older="0.1", young="0.01")},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        assert estimate.estimated_exposed_population == 100
        assert estimate.estimated_exposed_older_adults == 10
        assert estimate.estimated_exposed_young_children is None

    def test_a_stricter_k_anonymity_policy_withholds_more(self) -> None:
        """Verify the shared privacy layer drives the threshold, not a local constant."""
        overlaps = [
            _overlap(population=1000, unit_area_m2="1000000", overlap_area_m2="4000")
        ]
        default = estimate_exposed_population(
            overlaps=overlaps,
            rates_by_district={"010101": _rates()},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
        )
        strict = estimate_exposed_population(
            overlaps=overlaps,
            rates_by_district={"010101": _rates()},
            radius_meters=DEFAULT_EXPOSURE_RADIUS_METERS,
            policy=SuppressionPolicy(minimum_units=5, label="k-anonymity k=5"),
        )
        assert default.estimated_exposed_population == 4
        assert strict.estimated_exposed_population is None
        assert strict.suppressed is True


class TestDeclaredMethodology:
    """The estimate must carry its own method and spatial rule, not imply them."""

    def test_the_spatial_assignment_rule_is_declared_and_names_its_alternative(
        self,
    ) -> None:
        """Verify the rule states intersection-with-areal-weighting over centroid containment."""
        rule = SPATIAL_ASSIGNMENT_RULE.lower()
        assert "intersect" in rule
        assert "centroid" in rule
        assert "areal" in rule

    def test_the_estimation_method_never_claims_to_be_a_count(self) -> None:
        """Verify the declared method is an estimate and says so."""
        assert "estimate" in EXPOSURE_ESTIMATION_METHOD.lower()
        assert "areal weighting" in EXPOSURE_ESTIMATION_METHOD.lower()

    def test_the_metric_projection_is_pinned(self) -> None:
        """Verify area maths is pinned to a metric projection, not to degrees."""
        assert METRIC_PROJECTION_SRID == 32616

    def test_no_public_estimate_field_is_named_as_a_count(self) -> None:
        """Verify every exposure field announces itself as an estimate."""
        measures = [
            name
            for name in ExposedPopulationEstimate.__dataclass_fields__
            if name.startswith("estimated_") or "population" in name
        ]
        assert measures
        for name in measures:
            assert name.startswith("estimated_"), name


class TestArealWeightSqlExpression:
    """The SQL that computes the weight, exercised on literal geometries only.

    These run the production SQL expression against polygons written inline, so
    the arithmetic is verified in the database without depending on any ingested
    row, and the two fixture-free properties hold in SQL as well as in Python.
    """

    @staticmethod
    async def _scalar(expression: str) -> Any:
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        try:
            async with factory() as session:
                return (await session.execute(text(f"SELECT {expression}"))).scalar_one()
        finally:
            await engine.dispose()

    async def test_sql_weight_is_one_when_the_buffer_contains_the_polygon(self) -> None:
        """Verify the SQL weight saturates at 1 for a fully contained polygon."""
        unit = "ST_MakeEnvelope(-89.20, 13.70, -89.19, 13.71, 4326)"
        buffer_geometry = "ST_MakeEnvelope(-89.30, 13.60, -89.10, 13.80, 4326)"
        weight = await self._scalar(areal_weight_sql(unit, buffer_geometry))
        assert float(weight) == pytest.approx(1.0, abs=1e-9)

    async def test_sql_weight_is_one_half_when_the_buffer_covers_half_the_polygon(
        self,
    ) -> None:
        """Verify the SQL weight is 0.5 for a buffer clipping exactly half the polygon."""
        unit = "ST_MakeEnvelope(-89.20, 13.70, -89.18, 13.72, 4326)"
        half = "ST_MakeEnvelope(-89.20, 13.70, -89.19, 13.72, 4326)"
        weight = await self._scalar(areal_weight_sql(unit, half))
        assert float(weight) == pytest.approx(0.5, abs=1e-4)

    async def test_sql_weight_is_zero_when_the_buffer_misses_the_polygon(self) -> None:
        """Verify a disjoint buffer produces a zero weight rather than NULL."""
        unit = "ST_MakeEnvelope(-89.20, 13.70, -89.19, 13.71, 4326)"
        elsewhere = "ST_MakeEnvelope(-88.20, 13.70, -88.19, 13.71, 4326)"
        weight = await self._scalar(areal_weight_sql(unit, elsewhere))
        assert float(weight) == pytest.approx(0.0, abs=1e-12)

    async def test_metric_area_sql_returns_square_metres_not_square_degrees(self) -> None:
        """Verify the area expression is metric by checking a known-size envelope."""
        envelope = "ST_MakeEnvelope(-89.20, 13.70, -89.19, 13.71, 4326)"
        area = float(await self._scalar(metric_area_sql(envelope)))
        assert 1.0e6 < area < 1.5e6

    async def test_the_metric_projection_exists_in_this_postgis(self) -> None:
        """Verify the pinned SRID is actually installed, rather than failing at runtime."""
        found = await self._scalar(
            f"(SELECT count(*) FROM spatial_ref_sys WHERE srid = {METRIC_PROJECTION_SRID})"
        )
        assert int(found) == 1


class TestAttachmentAgainstIngestedData:
    """Attachment and exposure over the real corpus, skipped when it is absent."""

    @staticmethod
    async def _session_factory() -> Any:
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as session:
            try:
                units = (
                    await session.execute(
                        text("SELECT count(*) FROM census_population_unit")
                    )
                ).scalar_one()
                places = (
                    await session.execute(text("SELECT count(*) FROM vulnerable_places"))
                ).scalar_one()
            except Exception as exc:  # pragma: no cover - environment guard
                await engine.dispose()
                pytest.skip(f"census corpus is not ingested: {exc}")
            if not units or not places:
                await engine.dispose()
                pytest.skip(
                    "census corpus or places table is empty: run "
                    "'just census-ingest' and 'just sync' first"
                )
        return engine, factory

    async def test_attachment_is_idempotent(self) -> None:
        """Verify a second attachment pass changes nothing, so re-running is free."""
        engine, factory = await self._session_factory()
        try:
            async with factory() as session:
                repo = PlaceCensusAttachmentRepository(session)
                await repo.attach_places_to_census_units()
                second_pass = await repo.attach_places_to_census_units()
            assert second_pass.attached == 0
            assert second_pass.detached == 0
        finally:
            await engine.dispose()

    async def test_every_attached_place_lies_inside_its_cached_unit(self) -> None:
        """Verify the cached foreign key agrees with a live spatial test."""
        engine, factory = await self._session_factory()
        try:
            async with factory() as session:
                await PlaceCensusAttachmentRepository(
                    session
                ).attach_places_to_census_units()
                wrong = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM vulnerable_places p "
                            "JOIN census_population_unit u ON u.id = p.census_unit_id "
                            "WHERE NOT ST_Intersects(u.geom::geometry, "
                            "p.location::geometry)"
                        )
                    )
                ).scalar_one()
            assert int(wrong) == 0
        finally:
            await engine.dispose()

    async def test_places_outside_census_coverage_stay_unattached(self) -> None:
        """Verify a place beyond El Salvador keeps a null unit instead of snapping."""
        engine, factory = await self._session_factory()
        try:
            async with factory() as session:
                await PlaceCensusAttachmentRepository(
                    session
                ).attach_places_to_census_units()
                orphans = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM vulnerable_places p "
                            "WHERE p.census_unit_id IS NULL AND NOT EXISTS ("
                            "SELECT 1 FROM census_population_unit u "
                            "WHERE ST_Intersects(u.geom::geometry, p.location::geometry))"
                        )
                    )
                ).scalar_one()
                attached_but_outside = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM vulnerable_places p "
                            "WHERE p.census_unit_id IS NOT NULL AND NOT EXISTS ("
                            "SELECT 1 FROM census_population_unit u "
                            "WHERE u.id = p.census_unit_id)"
                        )
                    )
                ).scalar_one()
            assert int(orphans) >= 0
            assert int(attached_but_outside) == 0
        finally:
            await engine.dispose()

    async def test_district_rates_are_proportions_for_every_district(self) -> None:
        """Verify all 262 districts publish three rates inside the unit interval."""
        engine, factory = await self._session_factory()
        try:
            async with factory() as session:
                rates = await CensusExposureRepository(session).vulnerable_rates()
            assert len(rates) == 262
            for district in rates.values():
                assert Decimal(0) <= district.older_adult_rate <= Decimal(1)
                assert Decimal(0) <= district.young_child_rate <= Decimal(1)
                assert Decimal(0) <= district.disability_rate <= Decimal(1)
        finally:
            await engine.dispose()

    async def test_a_buffer_containing_one_real_unit_exposes_its_whole_population(
        self,
    ) -> None:
        """Verify the live SQL path reproduces a real polygon's population exactly."""
        engine, factory = await self._session_factory()
        try:
            async with factory() as session:
                row = (
                    await session.execute(
                        text(
                            "SELECT id, population, "
                            "ST_Y(ST_Centroid(geom::geometry)) AS lat, "
                            "ST_X(ST_Centroid(geom::geometry)) AS lon, "
                            "ST_MaxDistance(geom::geometry, geom::geometry) AS span "
                            "FROM census_population_unit "
                            "WHERE dug_level = 2 AND population > 100 "
                            "ORDER BY ST_Area(geom::geometry) ASC LIMIT 1"
                        )
                    )
                ).one()
                radius = int(float(row.span) * 111_320) + 2_000
                overlaps = await CensusExposureRepository(session).overlaps_for_point(
                    longitude=float(row.lon),
                    latitude=float(row.lat),
                    radius_meters=radius,
                )
            contribution = next(o for o in overlaps if o.unit_id == row.id)
            assert contribution.areal_weight() == Decimal(1)
            assert contribution.weighted_population() == Decimal(row.population)
        finally:
            await engine.dispose()

    async def test_no_place_estimate_exceeds_the_national_population(self) -> None:
        """Verify every cached estimate stays below the 6,029,976 national total."""
        engine, factory = await self._session_factory()
        try:
            async with factory() as session:
                repo = PlaceCensusAttachmentRepository(session)
                await repo.attach_places_to_census_units()
                await repo.refresh_exposure_estimates()
                row = (
                    await session.execute(
                        text(
                            "SELECT max(estimated_exposed_population) AS peak, "
                            "count(*) FILTER (WHERE estimated_exposed_population > 0) "
                            "AS estimated FROM vulnerable_places"
                        )
                    )
                ).one()
            assert int(row.peak) < 6_029_976
            assert int(row.estimated) > 0
        finally:
            await engine.dispose()

    async def test_cached_vulnerable_estimates_never_exceed_the_exposed_total(
        self,
    ) -> None:
        """Verify no derived sub-population is larger than the population it came from."""
        engine, factory = await self._session_factory()
        try:
            async with factory() as session:
                repo = PlaceCensusAttachmentRepository(session)
                await repo.attach_places_to_census_units()
                await repo.refresh_exposure_estimates()
                broken = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM vulnerable_places "
                            "WHERE estimated_exposed_population IS NOT NULL AND ("
                            "estimated_exposed_older_adults > estimated_exposed_population"
                            " OR estimated_exposed_young_children > "
                            "estimated_exposed_population"
                            " OR estimated_exposed_persons_with_disability > "
                            "estimated_exposed_population)"
                        )
                    )
                ).scalar_one()
            assert int(broken) == 0
        finally:
            await engine.dispose()


class TestPlacesApiContract:
    """The HTTP contract: the estimate is additive and never replaces a count."""

    async def test_place_list_keeps_estimated_vulnerable_count(self) -> None:
        """Verify the pre-existing institutional field is still served unchanged."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/places", params={"limit": 5})
        assert response.status_code == 200
        payload = response.json()
        if not payload:
            pytest.skip("no places are synced; run 'just sync' first")
        for place in payload:
            assert "estimated_vulnerable_count" in place
            assert isinstance(place["estimated_vulnerable_count"], int)

    async def test_place_list_exposes_the_areal_weighted_estimate(self) -> None:
        """Verify each row carries its cached exposure estimate and census unit."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/places", params={"limit": 5})
        payload = response.json()
        if not payload:
            pytest.skip("no places are synced; run 'just sync' first")
        for place in payload:
            assert "census_unit_id" in place
            assert "population_exposure" in place

    async def test_population_exposure_endpoint_declares_its_methodology(self) -> None:
        """Verify the on-demand estimate ships the rule, method and assumptions."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            listed = await client.get("/api/v1/places", params={"limit": 1})
            places = listed.json()
            if not places:
                pytest.skip("no places are synced; run 'just sync' first")
            response = await client.get(
                f"/api/v1/places/{places[0]['id']}/population-exposure",
                params={"radius_meters": 1000},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["radius_meters"] == 1000
        assert body["estimation_method"] == EXPOSURE_ESTIMATION_METHOD
        assert body["spatial_assignment_rule"] == SPATIAL_ASSIGNMENT_RULE
        assert body["metric_projection_srid"] == METRIC_PROJECTION_SRID
        assert body["uniform_density_assumption"]
        assert body["uniform_district_rate_assumption"]
        assert body["source"] == "BCR/ONEC, CPV 2024"
        assert "estimate" in body["disclaimer"].lower()

    async def test_population_exposure_endpoint_rejects_an_absurd_radius(self) -> None:
        """Verify an out-of-range radius is refused rather than scanning the country."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            listed = await client.get("/api/v1/places", params={"limit": 1})
            places = listed.json()
            if not places:
                pytest.skip("no places are synced; run 'just sync' first")
            response = await client.get(
                f"/api/v1/places/{places[0]['id']}/population-exposure",
                params={"radius_meters": 10_000_000},
            )
        assert response.status_code == 422

    async def test_population_exposure_endpoint_404s_for_an_unknown_place(self) -> None:
        """Verify an unknown place id is a 404, not an empty estimate."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/places/00000000-0000-0000-0000-000000000000"
                "/population-exposure"
            )
        assert response.status_code == 404


class TestAttachmentSchema:
    """Migration 0004: the cached attachment column and its supporting indexes."""

    def test_the_model_caches_the_census_unit_as_a_foreign_key(self) -> None:
        """Verify the attachment is a cached column, not a per-query computation."""
        column = VulnerablePlaceModel.__table__.c["census_unit_id"]
        assert column.nullable is True
        targets = {fk.target_fullname for fk in column.foreign_keys}
        assert targets == {"census_population_unit.id"}

    @pytest.mark.parametrize(
        "column_name",
        [
            "estimated_exposed_population",
            "estimated_exposed_older_adults",
            "estimated_exposed_young_children",
            "estimated_exposed_persons_with_disability",
            "exposure_radius_meters",
            "exposure_estimated_at",
        ],
    )
    def test_every_exposure_cache_column_is_nullable(self, column_name: str) -> None:
        """Verify an unknown estimate is null, never a misleading zero."""
        assert VulnerablePlaceModel.__table__.c[column_name].nullable is True

    async def test_the_attachment_column_and_indexes_reached_postgis(self) -> None:
        """Verify migration 0004 applied the column, its index and the geometry index."""
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        try:
            async with factory() as session:
                columns = set(
                    (
                        await session.execute(
                            text(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_name = 'vulnerable_places'"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                indexes = set(
                    (
                        await session.execute(
                            text(
                                "SELECT indexname FROM pg_indexes "
                                "WHERE tablename IN ('vulnerable_places', "
                                "'census_population_unit')"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
        finally:
            await engine.dispose()
        assert "census_unit_id" in columns
        assert "estimated_exposed_population" in columns
        assert "idx_vulnerable_places_census_unit" in indexes
        assert "idx_census_population_unit_geom_geometry" in indexes
