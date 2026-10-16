"""Phase 1 foundation tests: domain scoring, ORM PostGIS schema, OpenAPI contract, and live PostGIS integration."""

import math
import uuid

from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import verify_postgis_connection
from app.main import app
from app.modules.places.domain.entities import (
    AttentionStatus,
    CATEGORY_BASE_WEIGHTS,
    CATEGORY_GROUP_MAP,
    PlaceCategory,
    URGENCY_MULTIPLIERS,
    VulnerabilityGroup,
    VulnerablePlace,
    calculate_priority_score,
)
from app.modules.places.infrastructure.models import VulnerablePlaceModel


class TestDomainPriorityScoring:
    """Unit tests for the pure domain scoring engine and taxonomy mappings."""

    def test_category_weights_and_group_mappings_match_specification(self) -> None:
        """Verify all 10 OSM categories map to exact weights and vulnerability groups."""
        expected_weights = {
            PlaceCategory.HOSPITAL: 100,
            PlaceCategory.SOCIAL_FACILITY: 95,
            PlaceCategory.KINDERGARTEN: 90,
            PlaceCategory.CLINIC: 85,
            PlaceCategory.SCHOOL: 80,
            PlaceCategory.COMMUNITY_CENTRE: 75,
            PlaceCategory.UNIVERSITY: 65,
            PlaceCategory.PHARMACY: 60,
            PlaceCategory.COMMERCIAL_HUB: 55,
            PlaceCategory.PLACE_OF_WORSHIP: 50,
        }
        assert CATEGORY_BASE_WEIGHTS == expected_weights
        assert set(CATEGORY_GROUP_MAP.keys()) == set(PlaceCategory)
        assert CATEGORY_GROUP_MAP[PlaceCategory.HOSPITAL] == VulnerabilityGroup.HEALTH
        assert CATEGORY_GROUP_MAP[PlaceCategory.SOCIAL_FACILITY] == VulnerabilityGroup.SHELTER
        assert CATEGORY_GROUP_MAP[PlaceCategory.KINDERGARTEN] == VulnerabilityGroup.EDUCATION
        assert CATEGORY_GROUP_MAP[PlaceCategory.COMMERCIAL_HUB] == VulnerabilityGroup.CONCURRENCY

    @pytest.mark.parametrize(
        ("urgency_level", "multiplier"),
        [
            (1, 0.6),
            (2, 0.8),
            (3, 1.0),
            (4, 1.3),
            (5, 1.6),
        ],
    )
    def test_urgency_multipliers_scale_base_category_weight(
        self,
        urgency_level: int,
        multiplier: float,
    ) -> None:
        """Verify urgency level multipliers scale category weights accurately."""
        assert URGENCY_MULTIPLIERS[urgency_level] == multiplier
        score = calculate_priority_score(
            category=PlaceCategory.HOSPITAL,
            urgency_level=urgency_level,
            estimated_vulnerable_count=0,
            nearby_places_count=0,
            attention_status=AttentionStatus.PENDING,
        )
        assert score == pytest.approx(100 * multiplier)

    def test_logarithmic_population_and_neighbor_density_bonus(self) -> None:
        """Verify natural log dampening for vulnerable population and 500m neighbor bonus."""
        p_vuln = 250
        n_500m = 4
        expected = (90 * 1.3) + (15.0 * math.log(1 + p_vuln)) + (5.0 * n_500m)
        actual = calculate_priority_score(
            category=PlaceCategory.KINDERGARTEN,
            urgency_level=4,
            estimated_vulnerable_count=p_vuln,
            nearby_places_count=n_500m,
            attention_status=AttentionStatus.IN_PROGRESS,
        )
        assert actual == pytest.approx(expected)

    def test_attended_status_attenuates_score_to_twenty_percent(self) -> None:
        """Verify attended status reduces priority score to 20% of active score."""
        pending_score = calculate_priority_score(
            category=PlaceCategory.SOCIAL_FACILITY,
            urgency_level=5,
            estimated_vulnerable_count=120,
            nearby_places_count=3,
            attention_status=AttentionStatus.PENDING,
        )
        attended_score = calculate_priority_score(
            category=PlaceCategory.SOCIAL_FACILITY,
            urgency_level=5,
            estimated_vulnerable_count=120,
            nearby_places_count=3,
            attention_status=AttentionStatus.ATTENDED,
        )
        assert attended_score == pytest.approx(0.2 * pending_score)

    def test_invalid_scoring_inputs_raise_value_error(self) -> None:
        """Verify out-of-range urgency or negative counts raise ValueError."""
        with pytest.raises(ValueError, match="urgency_level"):
            calculate_priority_score(PlaceCategory.HOSPITAL, 6, 0, 0)
        with pytest.raises(ValueError, match="estimated_vulnerable_count"):
            calculate_priority_score(PlaceCategory.HOSPITAL, 3, -1, 0)
        with pytest.raises(ValueError, match="nearby_places_count"):
            calculate_priority_score(PlaceCategory.HOSPITAL, 3, 0, -2)

    def test_vulnerable_place_entity_initializes_weight_and_default_score(self) -> None:
        """Verify domain dataclass computes category_weight and default priority_score."""
        entity = VulnerablePlace(
            osm_type="way",
            osm_id=123456789,
            name="Central Regional Hospital",
            category=PlaceCategory.HOSPITAL,
            vulnerability_group=VulnerabilityGroup.HEALTH,
            zone_name="Sonsonate",
            latitude=13.7201,
            longitude=-89.7245,
            urgency_level=4,
            estimated_vulnerable_count=100,
        )
        assert entity.category_weight == 100
        expected_score = (100 * 1.3) + (15.0 * math.log(101))
        assert entity.priority_score == pytest.approx(expected_score)


class TestVulnerablePlaceModelSchema:
    """Inspection tests for SQLAlchemy 2.0 + GeoAlchemy2 table metadata."""

    def test_table_name_and_geography_column(self) -> None:
        """Verify table name and Geography(POINT, 4326) spatial column definition."""
        table = VulnerablePlaceModel.__table__
        assert table.name == "vulnerable_places"

        location_col = table.columns["location"]
        assert isinstance(location_col.type, Geography)
        assert location_col.type.geometry_type == "POINT"
        assert location_col.type.srid == 4326
        assert location_col.nullable is False

    def test_constraints_and_indexes_registered(self) -> None:
        """Verify unique constraint, check constraints, and indexes exist on table metadata."""
        table = VulnerablePlaceModel.__table__

        unique_names = {
            c.name for c in table.constraints if isinstance(c, UniqueConstraint)
        }
        assert "uq_osm_element" in unique_names

        check_names = {
            c.name for c in table.constraints if isinstance(c, CheckConstraint)
        }
        assert "ck_urgency_level_range" in check_names
        assert "ck_vulnerable_count_non_negative" in check_names

        index_names = {idx.name for idx in table.indexes}
        assert "idx_vulnerable_places_location" in index_names
        assert "idx_vulnerable_places_priority" in index_names
        assert "idx_vulnerable_places_zone_category" in index_names


class TestFastAPIHealthAndOpenAPIContract:
    """Contract tests for FastAPI health endpoint and OpenAPI 3.1 schema generation."""

    async def test_health_endpoint_returns_typed_payload(self) -> None:
        """Verify GET /api/v1/health responds with HTTP 200 and expected schema."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/v1/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["service"] == settings.app_name
        assert payload["version"] == "0.1.0"

    def test_openapi_schema_exposes_health_operation_id(self) -> None:
        """Verify OpenAPI 3.1 contract includes /api/v1/health with operationId getHealthStatus."""
        schema = app.openapi()
        assert schema["openapi"].startswith("3.1")
        assert "/api/v1/health" in schema["paths"]
        health_get = schema["paths"]["/api/v1/health"]["get"]
        assert health_get["operationId"] == "getHealthStatus"
        assert "HealthResponse" in schema["components"]["schemas"]


class TestPostGISSpatialIntegration:
    """Live database integration tests against the PostgreSQL 16 + PostGIS 3.4 container."""

    async def test_postgis_version_and_st_dwithin_spatial_query(self) -> None:
        """Verify PostGIS_Full_Version() and 500m ST_DWithin spatial query on vulnerable_places."""
        test_engine = create_async_engine(settings.database_url, echo=False)
        session_maker = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        try:
            async with session_maker() as session:
                try:
                    postgis_version = await verify_postgis_connection(session)
                except Exception as exc:
                    pytest.skip(f"PostGIS container is not reachable: {exc}")

                assert "POSTGIS=" in postgis_version.upper()

                hospital_id = uuid.uuid4()
                nearby_school_id = uuid.uuid4()
                distant_clinic_id = uuid.uuid4()

                # Sonsonate center (~13.7201, -89.7245)
                hospital = VulnerablePlaceModel(
                    id=hospital_id,
                    osm_type="test_node",
                    osm_id=9900001,
                    name="Central Regional Hospital Test",
                    category=PlaceCategory.HOSPITAL.value,
                    vulnerability_group=VulnerabilityGroup.HEALTH.value,
                    zone_name="Sonsonate",
                    latitude=13.7201,
                    longitude=-89.7245,
                    location=WKTElement("POINT(-89.7245 13.7201)", srid=4326),
                    osm_tags={"amenity": "hospital"},
                    category_weight=100,
                    priority_score=100.0,
                )
                # ~200 meters away
                nearby_school = VulnerablePlaceModel(
                    id=nearby_school_id,
                    osm_type="test_node",
                    osm_id=9900002,
                    name="Nearby Elementary School Test",
                    category=PlaceCategory.SCHOOL.value,
                    vulnerability_group=VulnerabilityGroup.EDUCATION.value,
                    zone_name="Sonsonate",
                    latitude=13.7215,
                    longitude=-89.7245,
                    location=WKTElement("POINT(-89.7245 13.7215)", srid=4326),
                    osm_tags={"amenity": "school"},
                    category_weight=80,
                    priority_score=80.0,
                )
                # ~3.5 km away
                distant_clinic = VulnerablePlaceModel(
                    id=distant_clinic_id,
                    osm_type="test_node",
                    osm_id=9900003,
                    name="Distant Community Clinic Test",
                    category=PlaceCategory.CLINIC.value,
                    vulnerability_group=VulnerabilityGroup.HEALTH.value,
                    zone_name="Sonsonate",
                    latitude=13.7500,
                    longitude=-89.7245,
                    location=WKTElement("POINT(-89.7245 13.7500)", srid=4326),
                    osm_tags={"amenity": "clinic"},
                    category_weight=85,
                    priority_score=85.0,
                )

                session.add_all([hospital, nearby_school, distant_clinic])
                await session.commit()

                try:
                    target_point = func.ST_GeogFromText(
                        "SRID=4326;POINT(-89.7245 13.7201)"
                    )
                    stmt = select(VulnerablePlaceModel.name).where(
                        VulnerablePlaceModel.osm_type == "test_node",
                        VulnerablePlaceModel.id != hospital_id,
                        func.ST_DWithin(
                            VulnerablePlaceModel.location,
                            target_point,
                            500.0,
                        ),
                    )
                    rows = (await session.execute(stmt)).scalars().all()
                    assert rows == ["Nearby Elementary School Test"]
                finally:
                    await session.execute(
                        delete(VulnerablePlaceModel).where(
                            VulnerablePlaceModel.osm_type == "test_node"
                        )
                    )
                    await session.commit()
        finally:
            await test_engine.dispose()
