"""Phase 2 & 3 tests: Overpass ingestion, tag classification, PostGIS UPSERT idempotency, spatial density scoring, and FastAPI REST + OpenAPI 3.1 contract."""

import math
from typing import Any

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import delete

from app.core.database import async_session_factory
from app.main import app, export_openapi_schema
from app.modules.ingestion.domain.classifier import (
    build_overpass_query,
    classify_osm_tags,
    parse_overpass_element,
    parse_overpass_elements,
)
from app.modules.ingestion.domain.zones import PREDEFINED_ZONES, get_predefined_zone
from app.modules.ingestion.infrastructure.overpass_client import (
    OverpassSyncPayload,
    SONSONATE_FALLBACK_ELEMENTS,
)
from app.modules.places.domain.entities import (
    AttentionStatus,
    PlaceCategory,
    VulnerabilityGroup,
)
from app.modules.places.infrastructure.models import VulnerablePlaceModel
from app.modules.places.infrastructure.repository import PlaceRepository
from app.modules.places.infrastructure.router import get_geospatial_provider


class FakeOverpassProvider:
    """Deterministic fake geospatial provider for fast and reproducible API tests."""

    def __init__(
        self,
        elements: list[dict[str, Any]],
        used_fallback: bool = False,
    ) -> None:
        self.elements = elements
        self.used_fallback = used_fallback

    async def fetch_elements(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> OverpassSyncPayload:
        """Return preconfigured OSM elements without network I/O."""
        return OverpassSyncPayload(
            elements=self.elements,
            source_endpoint="https://fake-overpass.test/api/interpreter",
            used_fallback=self.used_fallback,
        )


class TestPredefinedZonesAndOverpassClassifier:
    """Unit tests for El Salvador zones, Overpass QL builder, and tag classification."""

    def test_predefined_zones_include_el_salvador_municipalities(self) -> None:
        """Verify all 6 predefined zones are registered and resolvable by key or name."""
        expected_keys = {
            "sonsonate",
            "san_salvador",
            "santa_ana",
            "san_miguel",
            "santa_tecla",
            "acajutla",
        }
        assert expected_keys.issubset(set(PREDEFINED_ZONES.keys()))
        sonsonate = get_predefined_zone("Sonsonate")
        assert sonsonate is not None
        assert sonsonate.latitude == pytest.approx(13.7222)
        assert sonsonate.longitude == pytest.approx(-89.7236)
        assert sonsonate.default_radius_meters == 10000

    def test_overpass_query_builder_uses_nwr_and_timeout_60(self) -> None:
        """Verify Overpass QL includes [out:json][timeout:60], nwr quantifiers, and out center tags."""
        query = build_overpass_query(13.7222, -89.7236, 10000)
        assert "[out:json][timeout:60];" in query
        assert 'nwr["amenity"~' in query
        assert 'nwr["shop"="mall"](around:10000,13.7222,-89.7236);' in query
        assert "out center tags;" in query

    @pytest.mark.parametrize(
        ("tags", "expected_category"),
        [
            ({"amenity": "hospital"}, PlaceCategory.HOSPITAL),
            ({"amenity": "clinic"}, PlaceCategory.CLINIC),
            ({"amenity": "social_facility"}, PlaceCategory.SOCIAL_FACILITY),
            ({"amenity": "kindergarten"}, PlaceCategory.KINDERGARTEN),
            ({"amenity": "school"}, PlaceCategory.SCHOOL),
            ({"amenity": "community_centre"}, PlaceCategory.COMMUNITY_CENTRE),
            ({"amenity": "university"}, PlaceCategory.UNIVERSITY),
            ({"amenity": "pharmacy"}, PlaceCategory.PHARMACY),
            ({"amenity": "marketplace"}, PlaceCategory.COMMERCIAL_HUB),
            ({"shop": "mall"}, PlaceCategory.COMMERCIAL_HUB),
            ({"amenity": "place_of_worship"}, PlaceCategory.PLACE_OF_WORSHIP),
        ],
    )
    def test_classify_all_ten_vulnerability_categories(
        self,
        tags: dict[str, str],
        expected_category: PlaceCategory,
    ) -> None:
        """Verify every target OSM tag maps to the exact PlaceCategory."""
        assert classify_osm_tags(tags) == expected_category

    def test_parse_overpass_element_handles_way_center_and_fallback_name(self) -> None:
        """Verify ways/relations extract center coordinates and unnamed elements get fallback names."""
        raw_way = {
            "type": "way",
            "id": 777888,
            "center": {"lat": 13.7205, "lon": -89.7240},
            "tags": {"amenity": "hospital"},
        }
        place = parse_overpass_element(raw_way, zone_name="Sonsonate")
        assert place is not None
        assert place.osm_type == "way"
        assert place.osm_id == 777888
        assert place.name == "Unnamed Hospital (#777888)"
        assert place.category == PlaceCategory.HOSPITAL
        assert place.vulnerability_group == VulnerabilityGroup.HEALTH
        assert place.latitude == pytest.approx(13.7205)
        assert place.longitude == pytest.approx(-89.7240)

    def test_sonsonate_fallback_seed_covers_all_ten_categories(self) -> None:
        """Verify fallback seed elements parse cleanly and span all 10 categories."""
        parsed = parse_overpass_elements(
            SONSONATE_FALLBACK_ELEMENTS,
            zone_name="Sonsonate",
        )
        assert len(parsed) == len(SONSONATE_FALLBACK_ELEMENTS)
        categories_present = {p.category for p in parsed}
        assert categories_present == set(PlaceCategory)


class TestPostGISRepositoryAndUpsertIdempotency:
    """Database integration tests for PostGIS UPSERT idempotency and 500m spatial density."""

    async def test_upsert_preserves_institutional_triage_and_computes_500m_density(
        self,
    ) -> None:
        """Verify re-syncing OSM places updates cartographic metadata while preserving triage fields."""
        test_zone = "Sonsonate_Upsert_Test"
        raw_initial = [
            {
                "type": "way",
                "id": 8800101,
                "center": {"lat": 13.7201, "lon": -89.7245},
                "tags": {
                    "amenity": "hospital",
                    "name": "Initial Regional Hospital",
                },
            },
            {
                "type": "node",
                "id": 8800102,
                "lat": 13.7210,
                "lon": -89.7245,
                "tags": {
                    "amenity": "school",
                    "name": "Neighboring School Within 500m",
                },
            },
        ]

        async with async_session_factory() as session:
            await session.execute(
                delete(VulnerablePlaceModel).where(
                    VulnerablePlaceModel.zone_name == test_zone
                )
            )
            await session.commit()

            try:
                repo = PlaceRepository(session)
                initial_places = parse_overpass_elements(
                    raw_initial,
                    zone_name=test_zone,
                )
                count = await repo.upsert_osm_places(
                    initial_places,
                    zone_name=test_zone,
                )
                assert count == 2

                listed = await repo.list_places(zone_name=test_zone)
                assert len(listed) == 2
                hospital_entry = next(
                    item for item in listed if item.model.osm_id == 8800101
                )
                # 1 neighbor within 500m -> base_score = (100 * 1.0) + 0 + (5 * 1) = 105.0
                assert hospital_entry.nearby_places_count == 1
                assert hospital_entry.model.priority_score == pytest.approx(105.0)

                # Simulate institutional triage update
                updated = await repo.update_place_triage(
                    place_id=hospital_entry.model.id,
                    attention_status=AttentionStatus.IN_PROGRESS,
                    urgency_level=5,
                    estimated_vulnerable_count=250,
                    institution_notes="Priority medical brigade dispatched",
                )
                assert updated is not None
                expected_triaged_score = (
                    (100 * 1.6) + (15.0 * math.log(251)) + (5.0 * 1)
                )
                assert updated.model.priority_score == pytest.approx(
                    expected_triaged_score
                )

                # Re-sync same OSM element with updated OSM name and tags
                raw_resync = [
                    {
                        "type": "way",
                        "id": 8800101,
                        "center": {"lat": 13.7201, "lon": -89.7245},
                        "tags": {
                            "amenity": "hospital",
                            "name": "Renamed Regional Hospital v2",
                            "phone": "+503 2451-0000",
                        },
                    },
                    {
                        "type": "node",
                        "id": 8800102,
                        "lat": 13.7210,
                        "lon": -89.7245,
                        "tags": {
                            "amenity": "school",
                            "name": "Neighboring School Within 500m",
                        },
                    },
                ]
                resync_places = parse_overpass_elements(
                    raw_resync,
                    zone_name=test_zone,
                )
                await repo.upsert_osm_places(resync_places, zone_name=test_zone)

                reloaded = await repo.get_place_by_id(hospital_entry.model.id)
                assert reloaded is not None
                # Cartographic metadata updated:
                assert reloaded.model.name == "Renamed Regional Hospital v2"
                assert reloaded.model.osm_tags.get("phone") == "+503 2451-0000"
                # Operational triage preserved:
                assert (
                    reloaded.model.attention_status
                    == AttentionStatus.IN_PROGRESS.value
                )
                assert reloaded.model.urgency_level == 5
                assert reloaded.model.estimated_vulnerable_count == 250
                assert (
                    reloaded.model.institution_notes
                    == "Priority medical brigade dispatched"
                )
                assert reloaded.model.priority_score == pytest.approx(
                    expected_triaged_score
                )
            finally:
                await session.execute(
                    delete(VulnerablePlaceModel).where(
                        VulnerablePlaceModel.zone_name == test_zone
                    )
                )
                await session.commit()


class TestFastAPIEndpointsAndOpenAPIContract:
    """End-to-end HTTP tests for Phase 3 REST endpoints and OpenAPI 3.1 schema."""

    async def test_rest_endpoints_workflow_and_openapi_operation_ids(
        self,
        tmp_path: Any,
    ) -> None:
        """Verify /zones, /places/sync, /places, /places/{id}, /places/heatmap, and OpenAPI schema."""
        test_zone = "Sonsonate_API_Test"
        fake_provider = FakeOverpassProvider(
            elements=SONSONATE_FALLBACK_ELEMENTS,
            used_fallback=True,
        )
        app.dependency_overrides[get_geospatial_provider] = lambda: fake_provider

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                # 1. GET /api/v1/zones
                zones_resp = await client.get("/api/v1/zones")
                assert zones_resp.status_code == 200
                zones_data = zones_resp.json()
                assert len(zones_data) >= 6
                assert any(z["key"] == "sonsonate" for z in zones_data)

                # 2. POST /api/v1/places/sync
                sync_resp = await client.post(
                    "/api/v1/places/sync",
                    json={
                        "zone_name": test_zone,
                        "latitude": 13.7222,
                        "longitude": -89.7236,
                        "radius_meters": 5000,
                    },
                )
                assert sync_resp.status_code == 200
                sync_data = sync_resp.json()
                assert sync_data["zone_name"] == test_zone
                assert sync_data["synced_places_count"] == len(
                    SONSONATE_FALLBACK_ELEMENTS
                )
                assert sync_data["used_fallback"] is True

                # 3. GET /api/v1/places
                list_resp = await client.get(
                    "/api/v1/places",
                    params={"zone_name": test_zone},
                )
                assert list_resp.status_code == 200
                places_data = list_resp.json()
                assert len(places_data) == len(SONSONATE_FALLBACK_ELEMENTS)
                scores = [p["priority_score"] for p in places_data]
                assert scores == sorted(scores, reverse=True)

                top_place = places_data[0]
                place_id = top_place["id"]

                # 4. PATCH /api/v1/places/{place_id}
                patch_resp = await client.patch(
                    f"/api/v1/places/{place_id}",
                    json={
                        "attention_status": "in_progress",
                        "urgency_level": 5,
                        "estimated_vulnerable_count": 180,
                        "institution_notes": "Evacuation bus assigned",
                    },
                )
                assert patch_resp.status_code == 200
                patched = patch_resp.json()
                assert patched["attention_status"] == "in_progress"
                assert patched["urgency_level"] == 5
                assert patched["estimated_vulnerable_count"] == 180
                assert patched["institution_notes"] == "Evacuation bus assigned"
                assert patched["priority_score"] > top_place["priority_score"]

                # 5. GET /api/v1/places/{place_id}
                get_one_resp = await client.get(f"/api/v1/places/{place_id}")
                assert get_one_resp.status_code == 200
                assert get_one_resp.json()["id"] == place_id

                # 6. GET /api/v1/places/heatmap
                heatmap_resp = await client.get(
                    "/api/v1/places/heatmap",
                    params={"zone_name": test_zone},
                )
                assert heatmap_resp.status_code == 200
                heatmap_data = heatmap_resp.json()
                assert len(heatmap_data["points"]) == len(
                    SONSONATE_FALLBACK_ELEMENTS
                )
                assert len(heatmap_data["matrix"]) == len(
                    SONSONATE_FALLBACK_ELEMENTS
                )
                assert heatmap_data["kpis"]["total_places"] == len(
                    SONSONATE_FALLBACK_ELEMENTS
                )
                assert heatmap_data["kpis"]["in_progress_count"] == 1
                assert heatmap_data["kpis"]["total_estimated_vulnerable"] == 180

            # 7. Verify OpenAPI 3.1 operationIds and export helper
            schema = app.openapi()
            operation_ids = sorted(
                op.get("operationId")
                for path_item in schema["paths"].values()
                for op in path_item.values()
                if isinstance(op, dict) and op.get("operationId")
            )
            assert operation_ids == [
                "getHealthStatus",
                "getHeatmapData",
                "getPlaceById",
                "listPredefinedZones",
                "listPrioritizedPlaces",
                "syncPlacesFromOverpass",
                "updatePlaceTriage",
            ]

            exported_file = export_openapi_schema(tmp_path / "openapi.json")
            assert exported_file.exists()
        finally:
            app.dependency_overrides.clear()
            async with async_session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(VulnerablePlaceModel).where(
                        VulnerablePlaceModel.zone_name == test_zone
                    )
                )
                await cleanup_session.commit()

    async def test_hazards_active_simulation_scenarios_and_spatial_bonus(self) -> None:
        """Verify /api/v1/hazards/active returns USGS/Open-Meteo/EONET simulation presets and bonus."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            quake_resp = await client.get(
                "/api/v1/hazards/active",
                params={
                    "latitude": 13.7222,
                    "longitude": -89.7236,
                    "scenario": "sonsonate_earthquake_m64",
                },
            )
            assert quake_resp.status_code == 200
            quake_data = quake_resp.json()
            assert quake_data["scenario"] == "sonsonate_earthquake_m64"
            assert quake_data["overall_alert_level"] == "red"
            assert quake_data["zone_hazard_bonus"] > 20.0
            assert len(quake_data["events"]) == 2
            assert "USGS" in quake_data["events"][0]["source"]

            tecla_quake_resp = await client.get(
                "/api/v1/hazards/active",
                params={
                    "zone_key": "santa_tecla",
                    "latitude": 13.6769,
                    "longitude": -89.2797,
                    "scenario": "sonsonate_earthquake_m64",
                },
            )
            assert tecla_quake_resp.status_code == 200
            tecla_quake_data = tecla_quake_resp.json()
            assert tecla_quake_data["zone_name"] == "Santa Tecla"
            assert all(
                "sonsonate" not in event["title"].lower()
                for event in tecla_quake_data["events"]
            )
            assert tecla_quake_data["events"][0]["latitude"] == pytest.approx(
                13.6769 - 0.008
            )

            storm_resp = await client.get(
                "/api/v1/hazards/active",
                params={
                    "latitude": 13.7222,
                    "longitude": -89.7236,
                    "scenario": "pacific_tropical_storm",
                },
            )
            assert storm_resp.status_code == 200
            storm_data = storm_resp.json()
            assert storm_data["overall_alert_level"] == "red"
            assert storm_data["weather"]["precipitation_mm"] >= 25.0

    async def test_live_hazards_are_filtered_to_selected_zone_impact_area(self) -> None:
        """Regional feed events outside Santa Tecla's modeled impact reach must not show on its map."""
        from app.modules.hazards.domain.entities import (
            HazardAlertLevel,
            HazardEvent,
            HazardScenarioPreset,
            HazardType,
            WeatherCondition,
        )
        from app.modules.hazards.infrastructure.router import get_hazard_feeds_provider

        local_event = HazardEvent(
            id="local-quake",
            hazard_type=HazardType.EARTHQUAKE,
            title="M 4.5 near Santa Tecla",
            source="USGS",
            alert_level=HazardAlertLevel.YELLOW,
            latitude=13.6769,
            longitude=-89.2797,
            radius_km=13.5,
            magnitude=4.5,
        )
        distant_event = HazardEvent(
            id="sonsonate-quake",
            hazard_type=HazardType.EARTHQUAKE,
            title="M 4.3 south of Acajutla, Sonsonate",
            source="USGS",
            alert_level=HazardAlertLevel.YELLOW,
            latitude=12.8476,
            longitude=-89.7841,
            radius_km=12.9,
            magnitude=4.3,
        )
        weather = WeatherCondition(
            temperature_c=25.0,
            precipitation_mm=0.0,
            rain_mm=0.0,
            wind_speed_kmh=10.0,
            wind_gusts_kmh=15.0,
            weather_code=1,
            weather_label="Clear",
            alert_level=HazardAlertLevel.GREEN,
        )

        class FakeHazardProvider:
            async def fetch_active_hazards(
                self,
                latitude: float,
                longitude: float,
                scenario: HazardScenarioPreset = HazardScenarioPreset.NONE,
            ) -> tuple[list[HazardEvent], WeatherCondition, list[str]]:
                assert (latitude, longitude) == (13.6769, -89.2797)
                return [local_event, distant_event], weather, ["test://feeds"]

        app.dependency_overrides[get_hazard_feeds_provider] = (
            lambda: FakeHazardProvider()
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    "/api/v1/hazards/active",
                    params={
                        "zone_key": "santa_tecla",
                        "latitude": 13.6769,
                        "longitude": -89.2797,
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["zone_name"] == "Santa Tecla"
            assert [event["id"] for event in data["events"]] == ["local-quake"]
        finally:
            app.dependency_overrides.pop(get_hazard_feeds_provider, None)

    async def test_live_hazard_feeds_client_in_memory_ttl_caching(self) -> None:
        """Verify LiveHazardFeedsClient caches responses and avoids repeated network calls."""
        from app.modules.hazards.domain.entities import HazardAlertLevel, WeatherCondition
        from app.modules.hazards.infrastructure.feeds_client import (
            LiveHazardFeedsClient,
            _set_cache,
        )

        client = LiveHazardFeedsClient(timeout_seconds=2.0)
        # Pre-seed cache
        dummy_weather = WeatherCondition(
            temperature_c=29.5,
            precipitation_mm=1.2,
            rain_mm=1.2,
            wind_speed_kmh=15.0,
            wind_gusts_kmh=22.0,
            weather_code=2,
            weather_label="Partly cloudy",
            alert_level=HazardAlertLevel.GREEN,
            is_simulated=False,
        )
        _set_cache("weather:13.72:-89.72", dummy_weather, ttl_seconds=60.0)
        _set_cache("usgs_ca_quakes", [], ttl_seconds=60.0)
        _set_cache("nasa_eonet_ca", [], ttl_seconds=60.0)

        # Calling fetch_active_hazards must hit cache immediately
        events, weather, sources = await client.fetch_active_hazards(13.7222, -89.7236)
        assert weather.temperature_c == 29.5
        assert "cache://open-meteo" in sources
        assert "cache://usgs-earthquakes" in sources


