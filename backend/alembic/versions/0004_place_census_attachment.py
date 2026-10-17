"""Cached place-to-census attachment and areal-weighted exposure estimates.

Adds to ``vulnerable_places``:

* ``census_unit_id`` -- the DEGURBA population unit containing the place,
  resolved with ``ST_Intersects`` and cached so the dispatch queue never pays
  for a spatial join per row. Nullable, because a place can legitimately fall
  outside CPV 2024 coverage, and ``ON DELETE SET NULL`` so re-ingesting the
  census cannot block on a dangling reference.
* six exposure cache columns, all nullable: NULL means withheld under
  statistical secrecy or outside census coverage, never zero.

Adds to ``census_population_unit`` a GIST index on ``(geom::geometry)``. The
exposure query tests buffer containment in geometry space; measured over 1,481
places, exact geography ``ST_Intersects`` took 24.2 s, geometry space without
this index 50.9 s, and geometry space with it 0.72 s.

No existing column, constraint or index is altered or dropped.

Revision ID: 0004_place_census_attachment
Revises: 0003_census_2024
Create Date: 2026-10-16 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_place_census_attachment"
down_revision: str | None = "0003_census_2024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPOSURE_COLUMNS: tuple[tuple[str, sa.types.TypeEngine[object]], ...] = (
    ("exposure_radius_meters", sa.Integer()),
    ("estimated_exposed_population", sa.Integer()),
    ("estimated_exposed_older_adults", sa.Integer()),
    ("estimated_exposed_young_children", sa.Integer()),
    ("estimated_exposed_persons_with_disability", sa.Integer()),
    ("exposure_estimated_at", sa.DateTime(timezone=True)),
)

NON_NEGATIVE_CHECKS: tuple[tuple[str, str], ...] = (
    ("ck_exposed_population_non_negative", "estimated_exposed_population"),
    ("ck_exposed_older_adults_non_negative", "estimated_exposed_older_adults"),
    ("ck_exposed_young_children_non_negative", "estimated_exposed_young_children"),
    (
        "ck_exposed_disability_non_negative",
        "estimated_exposed_persons_with_disability",
    ),
)


def upgrade() -> None:
    """Add the cached attachment column, the exposure cache, and both indexes."""
    op.add_column(
        "vulnerable_places",
        sa.Column("census_unit_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_vulnerable_places_census_unit",
        "vulnerable_places",
        "census_population_unit",
        ["census_unit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_vulnerable_places_census_unit",
        "vulnerable_places",
        ["census_unit_id"],
    )

    for column_name, column_type in EXPOSURE_COLUMNS:
        op.add_column(
            "vulnerable_places",
            sa.Column(column_name, column_type, nullable=True),
        )

    op.create_check_constraint(
        "ck_exposure_radius_positive",
        "vulnerable_places",
        "exposure_radius_meters IS NULL OR exposure_radius_meters > 0",
    )
    for constraint_name, column_name in NON_NEGATIVE_CHECKS:
        op.create_check_constraint(
            constraint_name,
            "vulnerable_places",
            f"{column_name} IS NULL OR {column_name} >= 0",
        )

    op.create_index(
        "idx_census_population_unit_geom_geometry",
        "census_population_unit",
        [sa.text("(geom::geometry)")],
        unique=False,
        postgresql_using="gist",
    )


def downgrade() -> None:
    """Drop everything this migration added, in reverse dependency order."""
    op.drop_index(
        "idx_census_population_unit_geom_geometry",
        table_name="census_population_unit",
    )

    for constraint_name, _ in NON_NEGATIVE_CHECKS:
        op.drop_constraint(constraint_name, "vulnerable_places", type_="check")
    op.drop_constraint("ck_exposure_radius_positive", "vulnerable_places", type_="check")

    for column_name, _ in reversed(EXPOSURE_COLUMNS):
        op.drop_column("vulnerable_places", column_name)

    op.drop_index("idx_vulnerable_places_census_unit", table_name="vulnerable_places")
    op.drop_constraint(
        "fk_vulnerable_places_census_unit", "vulnerable_places", type_="foreignkey"
    )
    op.drop_column("vulnerable_places", "census_unit_id")
