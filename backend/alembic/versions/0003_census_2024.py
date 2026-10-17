"""Census 2024 corpus: administrative hierarchy, DEGURBA units, indicators, and segments.

Additive only: no pre-existing table, column, or index is touched.

Revision ID: 0003_census_2024
Revises: 0002_institutional_coordination
Create Date: 2026-10-16 23:55:00.000000
"""

from collections.abc import Sequence

from alembic import op
from geoalchemy2 import Geography
import sqlalchemy as sa

revision: str = "0003_census_2024"
down_revision: str | None = "0002_institutional_coordination"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_ATTRIBUTION = "BCR/ONEC, CPV 2024"


def _multipolygon() -> Geography:
    """Return the shared GEOGRAPHY(MULTIPOLYGON, 4326) type with no implicit index."""
    return Geography(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False)


def upgrade() -> None:
    """Create the four census tables with their GIST indexes and foreign keys."""
    op.create_table(
        "census_admin_unit",
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("parent_code", sa.String(length=10), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("iso_3166_2", sa.String(length=8), nullable=True),
        sa.Column("geom", _multipolygon(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=64),
            server_default=sa.text(f"'{SOURCE_ATTRIBUTION}'"),
            nullable=False,
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "level IN ('departamento', 'municipio', 'distrito')",
            name="ck_census_admin_unit_level",
        ),
        sa.CheckConstraint(
            "length(code) IN (2, 4, 6)",
            name="ck_census_admin_unit_code_width",
        ),
        sa.CheckConstraint(
            "parent_code IS NULL OR code LIKE parent_code || '%'",
            name="ck_census_admin_unit_parent_is_prefix",
        ),
        sa.ForeignKeyConstraint(
            ["parent_code"],
            ["census_admin_unit.code"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(
        "idx_census_admin_unit_geom",
        "census_admin_unit",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index("idx_census_admin_unit_level", "census_admin_unit", ["level"])
    op.create_index("idx_census_admin_unit_parent", "census_admin_unit", ["parent_code"])

    op.create_table(
        "census_population_unit",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("district_code", sa.String(length=6), nullable=False),
        sa.Column("dug_level", sa.SmallInteger(), nullable=False),
        sa.Column("dug_class", sa.String(length=80), nullable=False),
        sa.Column("dug_code", sa.SmallInteger(), nullable=True),
        sa.Column("population", sa.Integer(), nullable=False),
        sa.Column("households", sa.Integer(), nullable=False),
        sa.Column("dwellings", sa.Integer(), nullable=False),
        sa.Column("area_km2", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("density", sa.Numeric(precision=16, scale=6), nullable=True),
        sa.Column("geom", _multipolygon(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=64),
            server_default=sa.text(f"'{SOURCE_ATTRIBUTION}'"),
            nullable=False,
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("dug_level IN (1, 2)", name="ck_census_population_unit_level"),
        sa.CheckConstraint("population >= 0", name="ck_census_population_unit_population"),
        sa.CheckConstraint("households >= 0", name="ck_census_population_unit_households"),
        sa.CheckConstraint("dwellings >= 0", name="ck_census_population_unit_dwellings"),
        sa.ForeignKeyConstraint(
            ["district_code"],
            ["census_admin_unit.code"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "district_code",
            "dug_class",
            "dug_level",
            name="uq_census_population_unit_grain",
        ),
    )
    op.create_index(
        "idx_census_population_unit_geom",
        "census_population_unit",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_census_population_unit_district",
        "census_population_unit",
        ["district_code"],
    )
    op.create_index(
        "idx_census_population_unit_level",
        "census_population_unit",
        ["dug_level"],
    )

    op.create_table(
        "census_indicator",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("unit_code", sa.String(length=10), nullable=False),
        sa.Column("unit_level", sa.String(length=16), nullable=False),
        sa.Column("topic", sa.String(length=48), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("sex", sa.String(length=1), nullable=True),
        sa.Column("age_band", sa.String(length=12), nullable=True),
        sa.Column("value", sa.Numeric(precision=16, scale=4), nullable=True),
        sa.Column("share", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column(
            "suppressed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=64),
            server_default=sa.text(f"'{SOURCE_ATTRIBUTION}'"),
            nullable=False,
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("sex IS NULL OR sex IN ('H', 'M')", name="ck_census_indicator_sex"),
        sa.CheckConstraint(
            "suppressed = true OR value IS NOT NULL",
            name="ck_census_indicator_published_cell_has_value",
        ),
        sa.CheckConstraint(
            "suppressed = false OR value IS NULL",
            name="ck_census_indicator_suppressed_cell_has_no_value",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "unit_code",
            "unit_level",
            "topic",
            "category",
            "sex",
            "age_band",
            name="uq_census_indicator_cell",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "idx_census_indicator_unit_topic",
        "census_indicator",
        ["unit_code", "topic"],
    )
    op.create_index(
        "idx_census_indicator_topic_level",
        "census_indicator",
        ["topic", "unit_level"],
    )

    op.create_table(
        "census_segment",
        sa.Column("segment_code", sa.String(length=10), nullable=False),
        sa.Column("district_code", sa.String(length=6), nullable=False),
        sa.Column("area_type", sa.String(length=16), nullable=False),
        sa.Column("area_km2", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("geom", _multipolygon(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=64),
            server_default=sa.text(f"'{SOURCE_ATTRIBUTION}'"),
            nullable=False,
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "area_type IN ('URBANO', 'RURAL')",
            name="ck_census_segment_area_type",
        ),
        sa.CheckConstraint(
            "length(segment_code) = 10",
            name="ck_census_segment_code_width",
        ),
        sa.ForeignKeyConstraint(
            ["district_code"],
            ["census_admin_unit.code"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("segment_code"),
    )
    op.create_index(
        "idx_census_segment_geom",
        "census_segment",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index("idx_census_segment_district", "census_segment", ["district_code"])


def downgrade() -> None:
    """Drop the four census tables and their indexes in dependency order."""
    op.drop_index("idx_census_segment_district", table_name="census_segment")
    op.drop_index("idx_census_segment_geom", table_name="census_segment")
    op.drop_table("census_segment")

    op.drop_index("idx_census_indicator_topic_level", table_name="census_indicator")
    op.drop_index("idx_census_indicator_unit_topic", table_name="census_indicator")
    op.drop_table("census_indicator")

    op.drop_index(
        "idx_census_population_unit_level",
        table_name="census_population_unit",
    )
    op.drop_index(
        "idx_census_population_unit_district",
        table_name="census_population_unit",
    )
    op.drop_index(
        "idx_census_population_unit_geom",
        table_name="census_population_unit",
    )
    op.drop_table("census_population_unit")

    op.drop_index("idx_census_admin_unit_parent", table_name="census_admin_unit")
    op.drop_index("idx_census_admin_unit_level", table_name="census_admin_unit")
    op.drop_index("idx_census_admin_unit_geom", table_name="census_admin_unit")
    op.drop_table("census_admin_unit")
