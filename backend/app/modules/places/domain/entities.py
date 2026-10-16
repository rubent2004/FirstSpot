"""Pure domain entities, enums, taxonomy mappings, and priority scoring rules."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import math
from typing import Any
import uuid


class PlaceCategory(StrEnum):
    """Supported vulnerable place categories derived from OpenStreetMap taxonomy."""

    HOSPITAL = "hospital"
    CLINIC = "clinic"
    SOCIAL_FACILITY = "social_facility"
    KINDERGARTEN = "kindergarten"
    SCHOOL = "school"
    COMMUNITY_CENTRE = "community_centre"
    UNIVERSITY = "university"
    PHARMACY = "pharmacy"
    COMMERCIAL_HUB = "commercial_hub"
    PLACE_OF_WORSHIP = "place_of_worship"


class VulnerabilityGroup(StrEnum):
    """High-level vulnerability axis for institutional triage."""

    HEALTH = "health"
    EDUCATION = "education"
    SHELTER = "shelter"
    CONCURRENCY = "concurrency"


class AttentionStatus(StrEnum):
    """Operational dispatch status managed by response institutions."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ATTENDED = "attended"


CATEGORY_BASE_WEIGHTS: dict[PlaceCategory, int] = {
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

CATEGORY_GROUP_MAP: dict[PlaceCategory, VulnerabilityGroup] = {
    PlaceCategory.HOSPITAL: VulnerabilityGroup.HEALTH,
    PlaceCategory.CLINIC: VulnerabilityGroup.HEALTH,
    PlaceCategory.PHARMACY: VulnerabilityGroup.HEALTH,
    PlaceCategory.KINDERGARTEN: VulnerabilityGroup.EDUCATION,
    PlaceCategory.SCHOOL: VulnerabilityGroup.EDUCATION,
    PlaceCategory.UNIVERSITY: VulnerabilityGroup.EDUCATION,
    PlaceCategory.SOCIAL_FACILITY: VulnerabilityGroup.SHELTER,
    PlaceCategory.COMMUNITY_CENTRE: VulnerabilityGroup.SHELTER,
    PlaceCategory.COMMERCIAL_HUB: VulnerabilityGroup.CONCURRENCY,
    PlaceCategory.PLACE_OF_WORSHIP: VulnerabilityGroup.CONCURRENCY,
}

URGENCY_MULTIPLIERS: dict[int, float] = {
    1: 0.6,
    2: 0.8,
    3: 1.0,
    4: 1.3,
    5: 1.6,
}

ATTENDED_ATTENUATION_FACTOR: float = 0.2


def calculate_priority_score(
    category: PlaceCategory,
    urgency_level: int,
    estimated_vulnerable_count: int,
    nearby_places_count: int,
    attention_status: AttentionStatus = AttentionStatus.PENDING,
) -> float:
    """Calculate the multi-criteria priority score for a vulnerable place.

    Formula:
        base_score = (W_cat * M_urg) + (15.0 * ln(1 + P_vuln)) + (5.0 * N_500m)
        If attention_status is ATTENDED, returns 0.2 * base_score.
    """
    if urgency_level not in URGENCY_MULTIPLIERS:
        raise ValueError(f"urgency_level must be between 1 and 5, got {urgency_level}")
    if estimated_vulnerable_count < 0:
        raise ValueError("estimated_vulnerable_count must be non-negative")
    if nearby_places_count < 0:
        raise ValueError("nearby_places_count must be non-negative")

    w_cat = CATEGORY_BASE_WEIGHTS[PlaceCategory(category)]
    m_urg = URGENCY_MULTIPLIERS[urgency_level]

    base_score = (
        (w_cat * m_urg)
        + (15.0 * math.log(1 + estimated_vulnerable_count))
        + (5.0 * nearby_places_count)
    )

    if AttentionStatus(attention_status) == AttentionStatus.ATTENDED:
        return base_score * ATTENDED_ATTENUATION_FACTOR

    return base_score


@dataclass(slots=True)
class VulnerablePlace:
    """Pure domain entity representing a geospatial vulnerable location."""

    osm_type: str
    osm_id: int
    name: str
    category: PlaceCategory
    vulnerability_group: VulnerabilityGroup
    zone_name: str
    latitude: float
    longitude: float
    osm_tags: dict[str, Any] = field(default_factory=dict)
    attention_status: AttentionStatus = AttentionStatus.PENDING
    urgency_level: int = 3
    estimated_vulnerable_count: int = 0
    institution_notes: str | None = None
    category_weight: int = field(init=False)
    priority_score: float = 0.0
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    last_osm_sync_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        """Initialize derived category weight and default priority score."""
        self.category = PlaceCategory(self.category)
        self.vulnerability_group = VulnerabilityGroup(self.vulnerability_group)
        self.attention_status = AttentionStatus(self.attention_status)
        self.category_weight = CATEGORY_BASE_WEIGHTS[self.category]
        if self.priority_score == 0.0:
            self.priority_score = calculate_priority_score(
                category=self.category,
                urgency_level=self.urgency_level,
                estimated_vulnerable_count=self.estimated_vulnerable_count,
                nearby_places_count=0,
                attention_status=self.attention_status,
            )
