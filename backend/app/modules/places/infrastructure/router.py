"""FastAPI REST adapters and Pydantic v2 OpenAPI 3.1 schemas for vulnerable places."""

from datetime import datetime
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.ingestion.domain.classifier import parse_overpass_elements
from app.modules.ingestion.domain.zones import PREDEFINED_ZONES, get_predefined_zone
from app.modules.ingestion.infrastructure.overpass_client import (
    GeospatialProviderPort,
    OverpassHttpClient,
)
from app.modules.places.domain.entities import (
    AttentionStatus,
    PlaceCategory,
    VulnerabilityGroup,
)
from app.modules.institutions.infrastructure.models import InstitutionUserModel
from app.modules.institutions.infrastructure.security import require_verified_institution
from app.modules.places.infrastructure.activity_router import (
    PlaceActivityCreate,
    PlaceActivityType,
    _write_activity,
)
from app.modules.places.infrastructure.repository import (
    PlaceRepository,
    PlaceWithNeighbors,
)

router = APIRouter(tags=["places"])


class PredefinedZoneRead(BaseModel):
    """Schema representing a predefined geographic zone in El Salvador."""

    model_config = ConfigDict(from_attributes=True)

    key: str = Field(description="Unique identifier key of the predefined zone.")
    name: str = Field(description="Display name of the municipality or zone.")
    department: str = Field(description="Department, province, or region.")
    country: str = Field(
        default="El Salvador", description="Country name in Latin America."
    )
    latitude: float = Field(description="Center latitude (WGS84).")
    longitude: float = Field(description="Center longitude (WGS84).")
    default_radius_meters: int = Field(
        description="Recommended search radius in meters."
    )


class SyncZoneRequest(BaseModel):
    """Request payload for synchronizing vulnerable places from Overpass API."""

    zone_key: str | None = Field(
        default=None,
        description="Predefined zone key (e.g., 'sonsonate', 'san_salvador').",
    )
    zone_name: str | None = Field(
        default=None,
        description="Custom or predefined zone display name.",
    )
    latitude: float | None = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Center latitude for custom point/radius synchronization.",
    )
    longitude: float | None = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Center longitude for custom point/radius synchronization.",
    )
    radius_meters: int | None = Field(
        default=None,
        ge=100,
        le=50000,
        description="Search radius in meters around the center coordinate.",
    )

    @model_validator(mode="after")
    def validate_target_location(self) -> "SyncZoneRequest":
        """Ensure either a predefined zone or valid coordinates are supplied."""
        has_coords = self.latitude is not None and self.longitude is not None
        has_partial_coords = (self.latitude is None) != (self.longitude is None)
        if has_partial_coords:
            raise ValueError(
                "Both latitude and longitude must be provided together."
            )
        if not has_coords and not self.zone_key and not self.zone_name:
            self.zone_key = "sonsonate"
        return self


class SyncPlacesResponse(BaseModel):
    """Response summary after synchronizing OSM places into PostGIS."""

    zone_name: str = Field(description="Target zone name persisted in PostGIS.")
    latitude: float = Field(description="Queried center latitude.")
    longitude: float = Field(description="Queried center longitude.")
    radius_meters: int = Field(description="Queried radius in meters.")
    fetched_elements_count: int = Field(
        description="Raw elements returned by Overpass or fallback seed."
    )
    synced_places_count: int = Field(
        description="Number of vulnerable places upserted into PostGIS."
    )
    used_fallback: bool = Field(
        description="True when offline/rate-limit fallback seed data was used."
    )
    source_endpoint: str = Field(
        description="Overpass endpoint or fallback identifier used for ingestion."
    )


class PlaceRead(BaseModel):
    """Complete representation of a prioritized vulnerable place."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    osm_type: str
    osm_id: int
    name: str
    category: PlaceCategory
    vulnerability_group: VulnerabilityGroup
    zone_name: str
    latitude: float
    longitude: float
    osm_tags: dict[str, Any]
    attention_status: AttentionStatus
    urgency_level: int = Field(ge=1, le=5)
    estimated_vulnerable_count: int = Field(ge=0)
    institution_notes: str | None = None
    category_weight: int
    nearby_places_count: int = Field(
        default=0,
        description="Count of other vulnerable places within 500m via PostGIS ST_DWithin.",
    )
    priority_score: float
    last_osm_sync_at: datetime
    updated_at: datetime


class PlaceTriageUpdate(BaseModel):
    """Patch payload for institutional triage updates."""

    attention_status: AttentionStatus | None = Field(
        default=None,
        description="Updated operational dispatch status.",
    )
    urgency_level: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Institutional urgency rating from 1 (low) to 5 (critical).",
    )
    estimated_vulnerable_count: int | None = Field(
        default=None,
        ge=0,
        description="Estimated number of vulnerable individuals at this location.",
    )
    institution_notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Field notes entered by response coordinators.",
    )
    activity_type: PlaceActivityType = Field(
        default=PlaceActivityType.UPDATE,
        description="Kind of attributed action to append to the public place timeline.",
    )

    @model_validator(mode="after")
    def require_changed_field(self) -> "PlaceTriageUpdate":
        if not self.model_fields_set.intersection(
            {
                "attention_status",
                "urgency_level",
                "estimated_vulnerable_count",
                "institution_notes",
            }
        ):
            raise ValueError("At least one operational field must be supplied.")
        return self


class HeatmapPointRead(BaseModel):
    """Weighted geospatial point for heatmap visualization."""

    id: uuid.UUID
    name: str
    category: PlaceCategory
    vulnerability_group: VulnerabilityGroup
    attention_status: AttentionStatus
    latitude: float
    longitude: float
    priority_score: float
    intensity: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized heatmap intensity between 0.0 and 1.0.",
    )


class DashboardKPIsRead(BaseModel):
    """Aggregated operational KPIs for the dashboard header and analytics."""

    total_places: int
    pending_count: int
    in_progress_count: int
    attended_count: int
    critical_urgency_count: int
    total_estimated_vulnerable: int
    max_priority_score: float
    counts_by_group: dict[str, int]
    counts_by_category: dict[str, int]


class HeatmapResponse(BaseModel):
    """Combined heatmap points, compact [lat, lon, intensity] matrix, and KPIs."""

    points: list[HeatmapPointRead]
    matrix: list[tuple[float, float, float]] = Field(
        description="Compact [latitude, longitude, normalized_intensity] tuples for Leaflet.heat."
    )
    kpis: DashboardKPIsRead


def get_geospatial_provider() -> GeospatialProviderPort:
    """Provide default Overpass HTTP adapter instance."""
    return OverpassHttpClient()


def _to_place_read(item: PlaceWithNeighbors) -> PlaceRead:
    """Map repository PlaceWithNeighbors record to PlaceRead schema."""
    m = item.model
    return PlaceRead(
        id=m.id,
        osm_type=m.osm_type,
        osm_id=m.osm_id,
        name=m.name,
        category=PlaceCategory(m.category),
        vulnerability_group=VulnerabilityGroup(m.vulnerability_group),
        zone_name=m.zone_name,
        latitude=m.latitude,
        longitude=m.longitude,
        osm_tags=m.osm_tags or {},
        attention_status=AttentionStatus(m.attention_status),
        urgency_level=m.urgency_level,
        estimated_vulnerable_count=m.estimated_vulnerable_count,
        institution_notes=m.institution_notes,
        category_weight=m.category_weight,
        nearby_places_count=item.nearby_places_count,
        priority_score=round(m.priority_score, 2),
        last_osm_sync_at=m.last_osm_sync_at,
        updated_at=m.updated_at,
    )


@router.get(
    "/zones",
    response_model=list[PredefinedZoneRead],
    operation_id="listPredefinedZones",
    summary="List predefined geographic zones in El Salvador",
)
async def list_predefined_zones() -> list[PredefinedZoneRead]:
    """Return all configured El Salvador zones with center coordinates and default radius."""
    return [
        PredefinedZoneRead(
            key=z.key,
            name=z.name,
            department=z.department,
            country=z.country,
            latitude=z.latitude,
            longitude=z.longitude,
            default_radius_meters=z.default_radius_meters,
        )
        for z in PREDEFINED_ZONES.values()
    ]


@router.post(
    "/places/sync",
    response_model=SyncPlacesResponse,
    operation_id="syncPlacesFromOverpass",
    summary="Synchronize vulnerable places from OpenStreetMap Overpass API",
)
async def sync_places_from_overpass(
    payload: SyncZoneRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    provider: Annotated[GeospatialProviderPort, Depends(get_geospatial_provider)],
) -> SyncPlacesResponse:
    """Query Overpass API and idempotently upsert vulnerable places into PostGIS."""
    zone = None
    if payload.zone_key:
        zone = get_predefined_zone(payload.zone_key)
        if zone is None and (payload.latitude is None or payload.longitude is None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown predefined zone_key: {payload.zone_key}",
            )
    elif payload.zone_name:
        zone = get_predefined_zone(payload.zone_name)

    latitude = (
        payload.latitude
        if payload.latitude is not None
        else (zone.latitude if zone else PREDEFINED_ZONES["sonsonate"].latitude)
    )
    longitude = (
        payload.longitude
        if payload.longitude is not None
        else (zone.longitude if zone else PREDEFINED_ZONES["sonsonate"].longitude)
    )
    radius_meters = (
        payload.radius_meters
        if payload.radius_meters is not None
        else (
            zone.default_radius_meters
            if zone
            else PREDEFINED_ZONES["sonsonate"].default_radius_meters
        )
    )
    resolved_zone_name = (
        payload.zone_name.strip()
        if payload.zone_name and payload.zone_name.strip()
        else (zone.name if zone else "Custom Area")
    )

    sync_payload = await provider.fetch_elements(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )
    places = parse_overpass_elements(
        sync_payload.elements,
        zone_name=resolved_zone_name,
    )

    repo = PlaceRepository(session)
    synced_count = await repo.upsert_osm_places(
        places=places,
        zone_name=resolved_zone_name,
    )

    return SyncPlacesResponse(
        zone_name=resolved_zone_name,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        fetched_elements_count=len(sync_payload.elements),
        synced_places_count=synced_count,
        used_fallback=sync_payload.used_fallback,
        source_endpoint=sync_payload.source_endpoint,
    )


@router.get(
    "/places",
    response_model=list[PlaceRead],
    operation_id="listPrioritizedPlaces",
    summary="List prioritized vulnerable places ordered by priority_score DESC",
)
async def list_prioritized_places(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    zone_name: Annotated[str | None, Query(description="Filter by zone name")] = None,
    category: Annotated[
        PlaceCategory | None, Query(description="Filter by OSM place category")
    ] = None,
    vulnerability_group: Annotated[
        VulnerabilityGroup | None,
        Query(description="Filter by high-level vulnerability group"),
    ] = None,
    attention_status: Annotated[
        AttentionStatus | None,
        Query(description="Filter by institutional attention status"),
    ] = None,
    min_urgency: Annotated[
        int | None,
        Query(ge=1, le=5, description="Minimum urgency level (1-5)"),
    ] = None,
    search: Annotated[
        str | None, Query(description="Case-insensitive name search")
    ] = None,
    latitude: Annotated[
        float | None,
        Query(ge=-90.0, le=90.0, description="Center latitude for spatial filter"),
    ] = None,
    longitude: Annotated[
        float | None,
        Query(ge=-180.0, le=180.0, description="Center longitude for spatial filter"),
    ] = None,
    radius_meters: Annotated[
        int | None,
        Query(ge=50, le=50000, description="Radius in meters for PostGIS ST_DWithin"),
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=2000, description="Maximum number of places to return")
    ] = 500,
) -> list[PlaceRead]:
    """Return vulnerable places filtered by attributes or spatial radius and ordered by priority_score DESC."""
    repo = PlaceRepository(session)
    items = await repo.list_places(
        zone_name=zone_name,
        category=category,
        vulnerability_group=vulnerability_group,
        attention_status=attention_status,
        min_urgency=min_urgency,
        search=search,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        limit=limit,
    )
    return [_to_place_read(item) for item in items]


@router.get(
    "/places/heatmap",
    response_model=HeatmapResponse,
    operation_id="getHeatmapData",
    summary="Get normalized heatmap coordinates and operational KPIs",
)
async def get_heatmap_data(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    zone_name: Annotated[str | None, Query(description="Filter by zone name")] = None,
    category: Annotated[
        PlaceCategory | None, Query(description="Filter by OSM place category")
    ] = None,
    vulnerability_group: Annotated[
        VulnerabilityGroup | None,
        Query(description="Filter by vulnerability group"),
    ] = None,
    include_attended: Annotated[
        bool,
        Query(description="Whether to include attended places in heatmap points"),
    ] = True,
) -> HeatmapResponse:
    """Return weighted heatmap points, compact [lat, lon, intensity] matrix, and KPIs."""
    repo = PlaceRepository(session)
    points, kpis = await repo.get_heatmap_and_kpis(
        zone_name=zone_name,
        category=category,
        vulnerability_group=vulnerability_group,
        include_attended=include_attended,
    )

    point_reads = [
        HeatmapPointRead(
            id=p.id,
            name=p.name,
            category=PlaceCategory(p.category),
            vulnerability_group=VulnerabilityGroup(p.vulnerability_group),
            attention_status=AttentionStatus(p.attention_status),
            latitude=p.latitude,
            longitude=p.longitude,
            priority_score=p.priority_score,
            intensity=p.intensity,
        )
        for p in points
    ]
    matrix: list[tuple[float, float, float]] = [
        (p.latitude, p.longitude, p.intensity) for p in points
    ]

    return HeatmapResponse(
        points=point_reads,
        matrix=matrix,
        kpis=DashboardKPIsRead(
            total_places=kpis.total_places,
            pending_count=kpis.pending_count,
            in_progress_count=kpis.in_progress_count,
            attended_count=kpis.attended_count,
            critical_urgency_count=kpis.critical_urgency_count,
            total_estimated_vulnerable=kpis.total_estimated_vulnerable,
            max_priority_score=kpis.max_priority_score,
            counts_by_group=kpis.counts_by_group,
            counts_by_category=kpis.counts_by_category,
        ),
    )


@router.get(
    "/places/{place_id}",
    response_model=PlaceRead,
    operation_id="getPlaceById",
    summary="Get a single vulnerable place by UUID",
)
async def get_place_by_id(
    place_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlaceRead:
    """Retrieve details and 500m neighbor count for a single vulnerable place."""
    repo = PlaceRepository(session)
    item = await repo.get_place_by_id(place_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vulnerable place {place_id} not found",
        )
    return _to_place_read(item)


@router.patch(
    "/places/{place_id}",
    response_model=PlaceRead,
    operation_id="updatePlaceTriage",
    summary="Update institutional triage fields and recalculate priority score",
)
async def update_place_triage(
    place_id: uuid.UUID,
    payload: PlaceTriageUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    actor: Annotated[InstitutionUserModel, Depends(require_verified_institution)],
) -> PlaceRead:
    """Record authenticated triage and an immutable public activity entry."""
    repo = PlaceRepository(session)
    await _write_activity(
        place_id=place_id,
        session=session,
        actor=actor,
        payload=PlaceActivityCreate(
            activity_type=payload.activity_type,
            attention_status=payload.attention_status,
            urgency_level=payload.urgency_level,
            estimated_vulnerable_count=payload.estimated_vulnerable_count,
            notes=payload.institution_notes,
        ),
    )
    updated = await repo.get_place_by_id(place_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vulnerable place {place_id} not found",
        )
    return _to_place_read(updated)
