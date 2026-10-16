"""Initial vulnerable_places schema and PostGIS extension.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-16 11:05:00.000000
"""

from collections.abc import Sequence

from alembic import op
from geoalchemy2 import Geography
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable PostGIS extension and create vulnerable_places table with spatial and B-tree indexes."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    op.create_table(
        "vulnerable_places",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("osm_type", sa.String(length=16), nullable=False),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "name",
            sa.String(length=255),
            server_default=sa.text("'Unnamed place'"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("vulnerability_group", sa.String(length=50), nullable=False),
        sa.Column("zone_name", sa.String(length=100), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "location",
            Geography(
                geometry_type="POINT",
                srid=4326,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "osm_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "attention_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "urgency_level",
            sa.Integer(),
            server_default=sa.text("3"),
            nullable=False,
        ),
        sa.Column(
            "estimated_vulnerable_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("institution_notes", sa.Text(), nullable=True),
        sa.Column("category_weight", sa.Integer(), nullable=False),
        sa.Column(
            "priority_score",
            sa.Float(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "last_osm_sync_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("osm_type", "osm_id", name="uq_osm_element"),
        sa.CheckConstraint(
            "urgency_level BETWEEN 1 AND 5",
            name="ck_urgency_level_range",
        ),
        sa.CheckConstraint(
            "estimated_vulnerable_count >= 0",
            name="ck_vulnerable_count_non_negative",
        ),
    )

    op.create_index(
        "idx_vulnerable_places_location",
        "vulnerable_places",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_vulnerable_places_priority",
        "vulnerable_places",
        [sa.text("priority_score DESC")],
        unique=False,
    )
    op.create_index(
        "idx_vulnerable_places_zone_category",
        "vulnerable_places",
        ["zone_name", "category"],
        unique=False,
    )


def downgrade() -> None:
    """Drop indexes and vulnerable_places table."""
    op.drop_index(
        "idx_vulnerable_places_zone_category",
        table_name="vulnerable_places",
    )
    op.drop_index(
        "idx_vulnerable_places_priority",
        table_name="vulnerable_places",
    )
    op.drop_index(
        "idx_vulnerable_places_location",
        table_name="vulnerable_places",
    )
    op.drop_table("vulnerable_places")
