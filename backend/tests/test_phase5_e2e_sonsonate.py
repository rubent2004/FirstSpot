"""Phase 5 End-to-End Integration Test: Complete Sonsonate geospatial workflow against PostGIS."""

from httpx import ASGITransport, AsyncClient
import pytest

from app.main import app
from app.modules.ingestion.infrastructure.overpass_client import (
    OverpassSyncPayload,
    SONSONATE_FALLBACK_ELEMENTS,
)
from app.modules.places.infrastructure.router import get_geospatial_provider


class SonsonateSeedProvider:
    """Deterministic Sonsonate geospatial provider for reproducible E2E verification."""

    async def fetch_elements(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> OverpassSyncPayload:
        """Return the 12 Sonsonate vulnerable places across all 10 OSM categories."""
        return OverpassSyncPayload(
            elements=SONSONATE_FALLBACK_ELEMENTS,
            source_endpoint="fallback://sonsonate-seed",
            used_fallback=True,
        )


class TestPhase5SonsonateEndToEnd:
    """Full-stack backend verification of the Sonsonate humanitarian prioritization workflow."""

    async def test_complete_sonsonate_sync_heatmap_and_triage_workflow(self) -> None:
        """Verify Sonsonate ingestion, 500m PostGIS clustering, heatmap matrix, and triage recalculation."""
        app.dependency_overrides[get_geospatial_provider] = (
            lambda: SonsonateSeedProvider()
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                # 1. Synchronize Sonsonate zone into PostGIS
                sync_resp = await client.post(
                    "/api/v1/places/sync",
                    json={"zone_key": "sonsonate"},
                )
                assert sync_resp.status_code == 200
                sync_payload = sync_resp.json()
                assert sync_payload["zone_name"] == "Sonsonate"
                assert sync_payload["synced_places_count"] >= 12

                # 2. List prioritized places in Sonsonate
                places_resp = await client.get(
                    "/api/v1/places",
                    params={"zone_name": "Sonsonate"},
                )
                assert places_resp.status_code == 200
                places = places_resp.json()
                assert len(places) >= 12

                # Verify descending priority_score order
                scores = [p["priority_score"] for p in places]
                assert scores == sorted(scores, reverse=True)

                # Verify Hospital in central Sonsonate has 500m spatial neighbors via ST_DWithin
                hospital = next(
                    p for p in places if p["category"] == "hospital"
                )
                assert hospital["nearby_places_count"] >= 3
                assert hospital["priority_score"] >= 115.0

                # 3. Verify Heatmap & KPIs before triage
                heatmap_before = (
                    await client.get(
                        "/api/v1/places/heatmap",
                        params={"zone_name": "Sonsonate"},
                    )
                ).json()
                assert heatmap_before["kpis"]["total_places"] == len(places)
                assert len(heatmap_before["matrix"]) == len(places)
                for lat, lon, intensity in heatmap_before["matrix"]:
                    assert 13.0 < lat < 14.5
                    assert -90.5 < lon < -88.0
                    assert 0.15 <= intensity <= 1.0

                # 4. Perform institutional triage on the hospital (L5 urgency + 300 vulnerable people)
                triage_resp = await client.patch(
                    f"/api/v1/places/{hospital['id']}",
                    json={
                        "attention_status": "in_progress",
                        "urgency_level": 5,
                        "estimated_vulnerable_count": 300,
                        "institution_notes": "Emergency medical brigade active in Sonsonate Hospital",
                    },
                )
                assert triage_resp.status_code == 200
                triaged_hospital = triage_resp.json()
                assert triaged_hospital["attention_status"] == "in_progress"
                assert triaged_hospital["urgency_level"] == 5
                assert triaged_hospital["estimated_vulnerable_count"] == 300
                assert (
                    triaged_hospital["priority_score"]
                    > hospital["priority_score"]
                )

                # 5. Mark a place as attended and verify 20% score attenuation
                pharmacy = next(
                    p for p in places if p["category"] == "pharmacy"
                )
                attended_resp = await client.patch(
                    f"/api/v1/places/{pharmacy['id']}",
                    json={"attention_status": "attended"},
                )
                assert attended_resp.status_code == 200
                attended_pharmacy = attended_resp.json()
                assert attended_pharmacy["attention_status"] == "attended"
                assert attended_pharmacy["priority_score"] == pytest.approx(
                    pharmacy["priority_score"] * 0.2,
                    abs=0.05,
                )

                # 6. Reset demo state back to clean pending defaults for Sonsonate
                await client.patch(
                    f"/api/v1/places/{hospital['id']}",
                    json={
                        "attention_status": "pending",
                        "urgency_level": 3,
                        "estimated_vulnerable_count": 0,
                        "institution_notes": None,
                    },
                )
                await client.patch(
                    f"/api/v1/places/{pharmacy['id']}",
                    json={"attention_status": "pending"},
                )
        finally:
            app.dependency_overrides.clear()
