"""PostGIS repository adapter for vulnerable places persistence, spatial queries, and scoring."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import uuid

from geoalchemy2.elements import WKTElement
from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.places.domain.entities import (
    AttentionStatus,
    PlaceCategory,
    VulnerabilityGroup,
    VulnerablePlace,
    calculate_priority_score,
)
from app.modules.places.infrastructure.models import VulnerablePlaceModel

UPSERT_BATCH_SIZE = 400
NEIGHBOR_RADIUS_METERS = 500.0


@dataclass(slots=True)
class PlaceWithNeighbors:
    """Persistence model paired with its 500m spatial neighbor count."""

    model: VulnerablePlaceModel
    nearby_places_count: int


@dataclass(slots=True)
class HeatmapPointData:
    """Single weighted point for Leaflet heatmap rendering."""

    id: uuid.UUID
    name: str
    category: str
    vulnerability_group: str
    attention_status: str
    latitude: float
    longitude: float
    priority_score: float
    intensity: float


@dataclass(slots=True)
class DashboardKPIs:
    """Aggregated operational metrics for the institutional dashboard."""

    total_places: int
    pending_count: int
    in_progress_count: int
    attended_count: int
    critical_urgency_count: int
    total_estimated_vulnerable: int
    max_priority_score: float
    counts_by_group: dict[str, int]
    counts_by_category: dict[str, int]


class PlaceRepository:
    """PostgreSQL + PostGIS repository for VulnerablePlace entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _nearby_count_subquery() -> Any:
        """Build correlated PostGIS ST_DWithin(500m) neighbor count subquery."""
        neighbor = aliased(VulnerablePlaceModel)
        return (
            select(func.count(neighbor.id))
            .where(
                neighbor.id != VulnerablePlaceModel.id,
                neighbor.zone_name == VulnerablePlaceModel.zone_name,
                func.ST_DWithin(
                    VulnerablePlaceModel.location,
                    neighbor.location,
                    NEIGHBOR_RADIUS_METERS,
                ),
            )
            .correlate(VulnerablePlaceModel)
            .scalar_subquery()
        )

    async def upsert_osm_places(
        self,
        places: Sequence[VulnerablePlace],
        zone_name: str | None = None,
    ) -> int:
        """Idempotently insert or update OSM metadata while preserving institutional triage fields."""
        if not places:
            return 0

        now = datetime.now(timezone.utc)
        total_upserted = 0

        for start_idx in range(0, len(places), UPSERT_BATCH_SIZE):
            batch = places[start_idx : start_idx + UPSERT_BATCH_SIZE]
            values: list[dict[str, Any]] = []
            for place in batch:
                effective_zone = zone_name or place.zone_name
                values.append(
                    {
                        "id": place.id,
                        "osm_type": place.osm_type,
                        "osm_id": place.osm_id,
                        "name": place.name,
                        "category": str(place.category),
                        "vulnerability_group": str(place.vulnerability_group),
                        "zone_name": effective_zone,
                        "latitude": place.latitude,
                        "longitude": place.longitude,
                        "location": WKTElement(
                            f"POINT({place.longitude} {place.latitude})",
                            srid=4326,
                        ),
                        "osm_tags": place.osm_tags,
                        "category_weight": place.category_weight,
                        "priority_score": place.priority_score,
                        "last_osm_sync_at": now,
                    }
                )

            insert_stmt = pg_insert(VulnerablePlaceModel).values(values)
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=["osm_type", "osm_id"],
                set_={
                    "name": insert_stmt.excluded.name,
                    "category": insert_stmt.excluded.category,
                    "vulnerability_group": insert_stmt.excluded.vulnerability_group,
                    "zone_name": insert_stmt.excluded.zone_name,
                    "latitude": insert_stmt.excluded.latitude,
                    "longitude": insert_stmt.excluded.longitude,
                    "location": insert_stmt.excluded.location,
                    "osm_tags": insert_stmt.excluded.osm_tags,
                    "category_weight": insert_stmt.excluded.category_weight,
                    "last_osm_sync_at": insert_stmt.excluded.last_osm_sync_at,
                },
            )
            await self.session.execute(upsert_stmt)
            total_upserted += len(batch)

        await self.session.flush()
        self.session.expire_all()
        await self.recalculate_priority_scores(zone_name=zone_name)
        await self.session.commit()
        return total_upserted

    async def recalculate_priority_scores(
        self,
        zone_name: str | None = None,
        place_id: uuid.UUID | None = None,
    ) -> int:
        """Recalculate priority_score using PostGIS 500m neighbor density."""
        nearby_subq = self._nearby_count_subquery()
        stmt = select(VulnerablePlaceModel, nearby_subq.label("nearby_count"))

        if place_id is not None:
            stmt = stmt.where(VulnerablePlaceModel.id == place_id)
        elif zone_name is not None:
            stmt = stmt.where(
                func.lower(VulnerablePlaceModel.zone_name) == zone_name.strip().lower()
            )

        rows = (await self.session.execute(stmt)).all()
        updated_count = 0
        for model, nearby_count in rows:
            score = calculate_priority_score(
                category=PlaceCategory(model.category),
                urgency_level=model.urgency_level,
                estimated_vulnerable_count=model.estimated_vulnerable_count,
                nearby_places_count=int(nearby_count or 0),
                attention_status=AttentionStatus(model.attention_status),
            )
            model.priority_score = score
            updated_count += 1

        await self.session.flush()
        return updated_count

    def _apply_filters(
        self,
        stmt: Select[Any],
        zone_name: str | None = None,
        category: PlaceCategory | None = None,
        vulnerability_group: VulnerabilityGroup | None = None,
        attention_status: AttentionStatus | None = None,
        min_urgency: int | None = None,
        search: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_meters: int | None = None,
    ) -> Select[Any]:
        """Apply optional filtering criteria to a SQLAlchemy select statement."""
        if zone_name:
            stmt = stmt.where(
                func.lower(VulnerablePlaceModel.zone_name) == zone_name.strip().lower()
            )
        if category:
            stmt = stmt.where(VulnerablePlaceModel.category == str(category))
        if vulnerability_group:
            stmt = stmt.where(
                VulnerablePlaceModel.vulnerability_group == str(vulnerability_group)
            )
        if attention_status:
            stmt = stmt.where(
                VulnerablePlaceModel.attention_status == str(attention_status)
            )
        if min_urgency is not None:
            stmt = stmt.where(VulnerablePlaceModel.urgency_level >= min_urgency)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(VulnerablePlaceModel.name.ilike(pattern))
        if (
            latitude is not None
            and longitude is not None
            and radius_meters is not None
        ):
            target_point = WKTElement(
                f"POINT({longitude} {latitude})",
                srid=4326,
            )
            stmt = stmt.where(
                func.ST_DWithin(
                    VulnerablePlaceModel.location,
                    target_point,
                    float(radius_meters),
                )
            )
        return stmt

    async def list_places(
        self,
        zone_name: str | None = None,
        category: PlaceCategory | None = None,
        vulnerability_group: VulnerabilityGroup | None = None,
        attention_status: AttentionStatus | None = None,
        min_urgency: int | None = None,
        search: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_meters: int | None = None,
        limit: int = 500,
    ) -> list[PlaceWithNeighbors]:
        """Query prioritized vulnerable places with their 500m neighbor count."""
        nearby_subq = self._nearby_count_subquery()
        stmt = select(VulnerablePlaceModel, nearby_subq.label("nearby_count"))
        stmt = self._apply_filters(
            stmt,
            zone_name=zone_name,
            category=category,
            vulnerability_group=vulnerability_group,
            attention_status=attention_status,
            min_urgency=min_urgency,
            search=search,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
        )
        stmt = stmt.order_by(
            VulnerablePlaceModel.priority_score.desc(),
            VulnerablePlaceModel.name.asc(),
        ).limit(limit)

        rows = (await self.session.execute(stmt)).all()
        return [
            PlaceWithNeighbors(model=row[0], nearby_places_count=int(row[1] or 0))
            for row in rows
        ]

    async def get_place_by_id(
        self,
        place_id: uuid.UUID,
    ) -> PlaceWithNeighbors | None:
        """Retrieve a single vulnerable place by UUID with its 500m neighbor count."""
        nearby_subq = self._nearby_count_subquery()
        stmt = select(
            VulnerablePlaceModel,
            nearby_subq.label("nearby_count"),
        ).where(VulnerablePlaceModel.id == place_id)
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        return PlaceWithNeighbors(model=row[0], nearby_places_count=int(row[1] or 0))

    async def update_place_triage(
        self,
        place_id: uuid.UUID,
        attention_status: AttentionStatus | None = None,
        urgency_level: int | None = None,
        estimated_vulnerable_count: int | None = None,
        institution_notes: str | None = None,
        update_notes: bool = False,
        commit: bool = True,
    ) -> PlaceWithNeighbors | None:
        """Update institutional triage fields and recalculate priority_score with PostGIS density."""
        existing = await self.get_place_by_id(place_id)
        if existing is None:
            return None

        model = existing.model
        if attention_status is not None:
            model.attention_status = str(attention_status)
        if urgency_level is not None:
            model.urgency_level = urgency_level
        if estimated_vulnerable_count is not None:
            model.estimated_vulnerable_count = estimated_vulnerable_count
        if update_notes or institution_notes is not None:
            model.institution_notes = institution_notes

        model.updated_at = datetime.now(timezone.utc)
        model.priority_score = calculate_priority_score(
            category=PlaceCategory(model.category),
            urgency_level=model.urgency_level,
            estimated_vulnerable_count=model.estimated_vulnerable_count,
            nearby_places_count=existing.nearby_places_count,
            attention_status=AttentionStatus(model.attention_status),
        )

        await self.session.flush()
        if commit:
            await self.session.commit()
        await self.session.refresh(model)
        return PlaceWithNeighbors(
            model=model,
            nearby_places_count=existing.nearby_places_count,
        )

    async def get_heatmap_and_kpis(
        self,
        zone_name: str | None = None,
        category: PlaceCategory | None = None,
        vulnerability_group: VulnerabilityGroup | None = None,
        include_attended: bool = True,
    ) -> tuple[list[HeatmapPointData], DashboardKPIs]:
        """Compute normalized heatmap points and summary KPIs for the selected filters."""
        stmt = select(VulnerablePlaceModel)
        stmt = self._apply_filters(
            stmt,
            zone_name=zone_name,
            category=category,
            vulnerability_group=vulnerability_group,
        ).order_by(VulnerablePlaceModel.priority_score.desc())

        models = list((await self.session.execute(stmt)).scalars().all())

        total_places = len(models)
        pending_count = 0
        in_progress_count = 0
        attended_count = 0
        critical_urgency_count = 0
        total_estimated_vulnerable = 0
        counts_by_group: dict[str, int] = {g.value: 0 for g in VulnerabilityGroup}
        counts_by_category: dict[str, int] = {c.value: 0 for c in PlaceCategory}

        for m in models:
            if m.attention_status == AttentionStatus.PENDING.value:
                pending_count += 1
            elif m.attention_status == AttentionStatus.IN_PROGRESS.value:
                in_progress_count += 1
            elif m.attention_status == AttentionStatus.ATTENDED.value:
                attended_count += 1

            if m.urgency_level >= 4 and m.attention_status != AttentionStatus.ATTENDED.value:
                critical_urgency_count += 1

            total_estimated_vulnerable += m.estimated_vulnerable_count
            counts_by_group[m.vulnerability_group] = (
                counts_by_group.get(m.vulnerability_group, 0) + 1
            )
            counts_by_category[m.category] = (
                counts_by_category.get(m.category, 0) + 1
            )

        active_models = (
            models
            if include_attended
            else [
                m
                for m in models
                if m.attention_status != AttentionStatus.ATTENDED.value
            ]
        )

        max_score = max((m.priority_score for m in active_models), default=0.0)
        denom = max(max_score, 1.0)

        points: list[HeatmapPointData] = []
        for m in active_models:
            normalized = min(1.0, max(0.15, m.priority_score / denom))
            if m.attention_status == AttentionStatus.ATTENDED.value:
                normalized = min(normalized, 0.25)
            points.append(
                HeatmapPointData(
                    id=m.id,
                    name=m.name,
                    category=m.category,
                    vulnerability_group=m.vulnerability_group,
                    attention_status=m.attention_status,
                    latitude=m.latitude,
                    longitude=m.longitude,
                    priority_score=round(m.priority_score, 2),
                    intensity=round(normalized, 4),
                )
            )

        kpis = DashboardKPIs(
            total_places=total_places,
            pending_count=pending_count,
            in_progress_count=in_progress_count,
            attended_count=attended_count,
            critical_urgency_count=critical_urgency_count,
            total_estimated_vulnerable=total_estimated_vulnerable,
            max_priority_score=round(max_score, 2),
            counts_by_group=counts_by_group,
            counts_by_category=counts_by_category,
        )
        return points, kpis
