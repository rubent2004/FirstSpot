"""Public place activity timeline and authenticated, attributed field updates."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.institutions.infrastructure.models import (
    InstitutionModel,
    InstitutionUserModel,
)
from app.modules.institutions.infrastructure.security import require_verified_institution
from app.modules.places.domain.entities import AttentionStatus
from app.modules.places.infrastructure.models import PlaceActivityModel
from app.modules.places.infrastructure.repository import PlaceRepository

router = APIRouter(tags=["place-activity"])


class PlaceActivityType(StrEnum):
    """Operational activity labels shared by responders, hospitals, and NGOs."""

    REPORTED = "reported"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    NEEDS_SUPPORT = "needs_support"
    RESOURCE_AVAILABLE = "resource_available"
    UPDATE = "update"
    RESOLVED = "resolved"


class PlaceActivityCreate(BaseModel):
    """One new public timeline entry; entries are never edited in place."""

    activity_type: PlaceActivityType = PlaceActivityType.UPDATE
    attention_status: AttentionStatus | None = None
    urgency_level: int | None = Field(default=None, ge=1, le=5)
    estimated_vulnerable_count: int | None = Field(default=None, ge=0, le=1_000_000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_content(self) -> "PlaceActivityCreate":
        if (
            self.attention_status is None
            and self.urgency_level is None
            and self.estimated_vulnerable_count is None
            and not (self.notes and self.notes.strip())
            and "notes" not in self.model_fields_set
        ):
            raise ValueError("An activity requires a note or at least one operational field.")
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class ActivityOrganizationRead(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    sector: str
    verification_status: str


class PlaceActivityRead(BaseModel):
    id: uuid.UUID
    place_id: uuid.UUID
    activity_type: PlaceActivityType
    attention_status: AttentionStatus | None
    urgency_level: int | None
    estimated_vulnerable_count: int | None
    notes: str | None
    actor_name: str
    organization: ActivityOrganizationRead
    created_at: datetime


def _to_activity_read(
    activity: PlaceActivityModel,
    institution: InstitutionModel,
    actor: InstitutionUserModel,
) -> PlaceActivityRead:
    return PlaceActivityRead(
        id=activity.id,
        place_id=activity.place_id,
        activity_type=activity.activity_type,
        attention_status=activity.attention_status,
        urgency_level=activity.urgency_level,
        estimated_vulnerable_count=activity.estimated_vulnerable_count,
        notes=activity.notes,
        actor_name=actor.display_name,
        organization=ActivityOrganizationRead(
            id=institution.id,
            name=institution.name,
            country=institution.country,
            sector=institution.sector,
            verification_status=institution.verification_status,
        ),
        created_at=activity.created_at,
    )


async def _write_activity(
    *,
    place_id: uuid.UUID,
    payload: PlaceActivityCreate,
    session: AsyncSession,
    actor: InstitutionUserModel,
) -> PlaceActivityRead:
    """Update the current operational snapshot and append its attribution atomically."""
    repository = PlaceRepository(session)
    status_for_action = payload.attention_status
    if status_for_action is None:
        if payload.activity_type in {
            PlaceActivityType.EN_ROUTE,
            PlaceActivityType.ON_SCENE,
            PlaceActivityType.NEEDS_SUPPORT,
        }:
            status_for_action = AttentionStatus.IN_PROGRESS
        elif payload.activity_type == PlaceActivityType.RESOLVED:
            status_for_action = AttentionStatus.ATTENDED
    updated = await repository.update_place_triage(
        place_id=place_id,
        attention_status=status_for_action,
        urgency_level=payload.urgency_level,
        estimated_vulnerable_count=payload.estimated_vulnerable_count,
        institution_notes=payload.notes,
        update_notes=payload.notes is not None,
        commit=False,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vulnerable place {place_id} not found",
        )

    activity = PlaceActivityModel(
        place_id=place_id,
        organization_id=actor.institution_id,
        user_id=actor.id,
        activity_type=str(payload.activity_type),
        attention_status=(str(status_for_action) if status_for_action else None),
        urgency_level=payload.urgency_level,
        estimated_vulnerable_count=payload.estimated_vulnerable_count,
        notes=payload.notes,
        created_at=datetime.now(timezone.utc),
    )
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return _to_activity_read(activity, actor.institution, actor)


@router.get(
    "/places/{place_id}/activities",
    response_model=list[PlaceActivityRead],
    operation_id="listPlaceActivities",
    summary="Read the public, attributed activity timeline for a place",
)
async def list_place_activities(
    place_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[PlaceActivityRead]:
    stmt = (
        select(PlaceActivityModel, InstitutionModel, InstitutionUserModel)
        .join(InstitutionModel, InstitutionModel.id == PlaceActivityModel.organization_id)
        .join(InstitutionUserModel, InstitutionUserModel.id == PlaceActivityModel.user_id)
        .where(PlaceActivityModel.place_id == place_id)
        .order_by(PlaceActivityModel.created_at.desc(), PlaceActivityModel.id.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        exists = await PlaceRepository(session).get_place_by_id(place_id)
        if exists is None:
            raise HTTPException(status_code=404, detail=f"Vulnerable place {place_id} not found")
    return [_to_activity_read(activity, org, actor) for activity, org, actor in rows]


@router.post(
    "/places/{place_id}/activities",
    response_model=PlaceActivityRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createPlaceActivity",
    summary="Append an activity with the verified organization and individual author",
)
async def create_place_activity(
    place_id: uuid.UUID,
    payload: PlaceActivityCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    actor: Annotated[InstitutionUserModel, Depends(require_verified_institution)],
) -> PlaceActivityRead:
    return await _write_activity(
        place_id=place_id,
        payload=payload,
        session=session,
        actor=actor,
    )
