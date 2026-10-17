"""SQLAlchemy models for vulnerable places and their public activity trail."""

from datetime import datetime, timezone
from typing import Any
import uuid

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VulnerablePlaceModel(Base):
    """PostGIS-backed persistence model for vulnerable places."""

    __tablename__ = "vulnerable_places"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    osm_type: Mapped[str] = mapped_column(String(16), nullable=False)
    osm_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Unnamed place",
        server_default=text("'Unnamed place'"),
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    vulnerability_group: Mapped[str] = mapped_column(String(50), nullable=False)
    zone_name: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    osm_tags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"),
    )
    attention_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default=text("'pending'"),
    )
    urgency_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default=text("3"),
    )
    estimated_vulnerable_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"),
    )
    institution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0"),
    )
    last_osm_sync_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("osm_type", "osm_id", name="uq_osm_element"),
        Index("idx_vulnerable_places_priority", priority_score.desc()),
        Index("idx_vulnerable_places_zone_category", "zone_name", "category"),
        CheckConstraint("urgency_level BETWEEN 1 AND 5", name="ck_urgency_level_range"),
        CheckConstraint(
            "estimated_vulnerable_count >= 0", name="ck_vulnerable_count_non_negative",
        ),
    )


class PlaceActivityModel(Base):
    """Append-only, publicly attributable institutional activity at a place."""

    __tablename__ = "place_activities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vulnerable_places.id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institution_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    activity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    attention_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    urgency_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_vulnerable_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_place_activities_place_created", "place_id", "created_at"),
        Index("idx_place_activities_org_created", "organization_id", "created_at"),
        CheckConstraint(
            "activity_type IN ('reported', 'en_route', 'on_scene', 'needs_support', 'resource_available', 'update', 'resolved')",
            name="ck_place_activities_type",
        ),
        CheckConstraint(
            "attention_status IS NULL OR attention_status IN ('pending', 'in_progress', 'attended')",
            name="ck_place_activities_attention_status",
        ),
        CheckConstraint(
            "urgency_level IS NULL OR urgency_level BETWEEN 1 AND 5",
            name="ck_place_activities_urgency",
        ),
        CheckConstraint(
            "estimated_vulnerable_count IS NULL OR estimated_vulnerable_count >= 0",
            name="ck_place_activities_population",
        ),
    )
