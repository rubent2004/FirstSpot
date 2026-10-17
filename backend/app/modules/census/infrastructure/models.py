"""SQLAlchemy models for the CPV 2024 census corpus.

Four additive tables, none of which touches the pre-existing schema:

``census_admin_unit``
    One row per territory of the unified DIGESTYC/BCR-CNR hierarchy. The code
    length encodes the level, and ``parent_code`` is the code's own shorter
    prefix, so the hierarchy is self-describing.
``census_population_unit``
    The analysis unit: the DEGURBA sub-district polygon, 902 rows at Nivel 2.
    Finer than the district (262) and, unlike the census segment, it carries
    real population, household and dwelling counts.
``census_indicator``
    Long/EAV storage so a new census release adds rows, not columns.
``census_segment``
    The 10,290 official segment polygons. Geometry only: the segment layer
    publishes no population attribute, so it is urban/rural context and never a
    population join target.

Every geography column is ``GEOGRAPHY(MULTIPOLYGON, 4326)`` with an explicit
GIST index, matching the convention of migration 0001.
"""

from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.census.domain.geo_codes import CENSUS_SOURCE_ATTRIBUTION

MULTIPOLYGON_4326 = Geography(
    geometry_type="MULTIPOLYGON",
    srid=4326,
    spatial_index=False,
)
"""Shared geography type; the GIST index is declared explicitly per table."""


class CensusAdminUnitModel(Base):
    """A territory of the unified census administrative hierarchy."""

    __tablename__ = "census_admin_unit"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(
        String(10),
        ForeignKey("census_admin_unit.code", ondelete="RESTRICT"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    iso_3166_2: Mapped[str | None] = mapped_column(String(8), nullable=True)
    geom: Mapped[Any] = mapped_column(MULTIPOLYGON_4326, nullable=False)
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=CENSUS_SOURCE_ATTRIBUTION,
        server_default=text(f"'{CENSUS_SOURCE_ATTRIBUTION}'"),
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_census_admin_unit_geom", "geom", postgresql_using="gist"),
        Index("idx_census_admin_unit_level", "level"),
        Index("idx_census_admin_unit_parent", "parent_code"),
        CheckConstraint(
            "level IN ('departamento', 'municipio', 'distrito')",
            name="ck_census_admin_unit_level",
        ),
        CheckConstraint(
            "length(code) IN (2, 4, 6)",
            name="ck_census_admin_unit_code_width",
        ),
        CheckConstraint(
            "parent_code IS NULL OR code LIKE parent_code || '%'",
            name="ck_census_admin_unit_parent_is_prefix",
        ),
    )


class CensusPopulationUnitModel(Base):
    """A DEGURBA sub-district polygon: the fine-grain population analysis unit."""

    __tablename__ = "census_population_unit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(
        String(6),
        ForeignKey("census_admin_unit.code", ondelete="RESTRICT"),
        nullable=False,
    )
    dug_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dug_class: Mapped[str] = mapped_column(String(80), nullable=False)
    dug_code: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    population: Mapped[int] = mapped_column(Integer, nullable=False)
    households: Mapped[int] = mapped_column(Integer, nullable=False)
    dwellings: Mapped[int] = mapped_column(Integer, nullable=False)
    area_km2: Mapped[Any] = mapped_column(Numeric(14, 6), nullable=True)
    density: Mapped[Any] = mapped_column(Numeric(16, 6), nullable=True)
    geom: Mapped[Any] = mapped_column(MULTIPOLYGON_4326, nullable=False)
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=CENSUS_SOURCE_ATTRIBUTION,
        server_default=text(f"'{CENSUS_SOURCE_ATTRIBUTION}'"),
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "district_code",
            "dug_class",
            "dug_level",
            name="uq_census_population_unit_grain",
        ),
        Index("idx_census_population_unit_geom", "geom", postgresql_using="gist"),
        Index("idx_census_population_unit_district", "district_code"),
        Index("idx_census_population_unit_level", "dug_level"),
        CheckConstraint("dug_level IN (1, 2)", name="ck_census_population_unit_level"),
        CheckConstraint("population >= 0", name="ck_census_population_unit_population"),
        CheckConstraint("households >= 0", name="ck_census_population_unit_households"),
        CheckConstraint("dwellings >= 0", name="ck_census_population_unit_dwellings"),
    )


class CensusIndicatorModel(Base):
    """One derived census cell, in long format, already screened for secrecy."""

    __tablename__ = "census_indicator"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    unit_code: Mapped[str] = mapped_column(String(10), nullable=False)
    unit_level: Mapped[str] = mapped_column(String(16), nullable=False)
    topic: Mapped[str] = mapped_column(String(48), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    age_band: Mapped[str | None] = mapped_column(String(12), nullable=True)
    value: Mapped[Any] = mapped_column(Numeric(16, 4), nullable=True)
    share: Mapped[Any] = mapped_column(Numeric(10, 8), nullable=True)
    suppressed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"),
    )
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=CENSUS_SOURCE_ATTRIBUTION,
        server_default=text(f"'{CENSUS_SOURCE_ATTRIBUTION}'"),
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "unit_code",
            "unit_level",
            "topic",
            "category",
            "sex",
            "age_band",
            name="uq_census_indicator_cell",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_census_indicator_unit_topic", "unit_code", "topic"),
        Index("idx_census_indicator_topic_level", "topic", "unit_level"),
        CheckConstraint(
            "sex IS NULL OR sex IN ('H', 'M')",
            name="ck_census_indicator_sex",
        ),
        CheckConstraint(
            "suppressed = true OR value IS NOT NULL",
            name="ck_census_indicator_published_cell_has_value",
        ),
        CheckConstraint(
            "suppressed = false OR value IS NULL",
            name="ck_census_indicator_suppressed_cell_has_no_value",
        ),
    )


class CensusSegmentModel(Base):
    """An official census segment polygon: urban/rural context, no population."""

    __tablename__ = "census_segment"

    segment_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    district_code: Mapped[str] = mapped_column(
        String(6),
        ForeignKey("census_admin_unit.code", ondelete="RESTRICT"),
        nullable=False,
    )
    area_type: Mapped[str] = mapped_column(String(16), nullable=False)
    area_km2: Mapped[Any] = mapped_column(Numeric(14, 6), nullable=True)
    geom: Mapped[Any] = mapped_column(MULTIPOLYGON_4326, nullable=False)
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=CENSUS_SOURCE_ATTRIBUTION,
        server_default=text(f"'{CENSUS_SOURCE_ATTRIBUTION}'"),
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_census_segment_geom", "geom", postgresql_using="gist"),
        Index("idx_census_segment_district", "district_code"),
        CheckConstraint(
            "area_type IN ('URBANO', 'RURAL')",
            name="ck_census_segment_area_type",
        ),
        CheckConstraint(
            "length(segment_code) = 10",
            name="ck_census_segment_code_width",
        ),
    )
