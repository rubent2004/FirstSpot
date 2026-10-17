"""National OpenStreetMap corpus and cached access measurements behind LCC.

Three additive tables. No existing column, constraint or index is altered or
dropped.

``osm_coping_facility``
    Response-capacity points from the pinned Geofabrik country extract:
    hospitals, clinics, fire stations, schools and community centres,
    nationally rather than per queried zone. Deliberately **not**
    ``vulnerable_places``: a fire station is a responder asset, not a population
    to evacuate, it carries no ``priority_score``, and it belongs to none of the
    four ``VulnerabilityGroup`` axes the dispatch queue colours by. Putting it
    there would have cascaded into the frontend's ``GROUP_COLORS``, which lives
    outside this task's authorised surface.
``osm_road_segment``
    The classified primary network -- ``highway`` in motorway, trunk, primary.
    Stored as geometry rather than as a derived distance so the same rows can be
    built into a routable topology the day pgRouting is available, without
    re-reading the 35 MB extract.
``osm_unit_access``
    Access measurements cached per DEGURBA Nivel 2 polygon. Measured on the real
    corpus the national areal pass takes about 5 s and the nearest-facility pass
    longer, while the Vulnerability dimension recomputes per request in about
    100 ms. Serving LCC live would have made it two orders of magnitude slower
    than its sibling, so this follows the decision B4 already made for
    ``census_unit_id``: measure once at ingest, read cheaply per request.

Why the distance columns are called ``geodesic_metres_*``
--------------------------------------------------------
pgRouting is absent from ``pg_available_extensions`` in the pinned
``postgis/postgis:16-3.4-alpine`` image, so these are ``ST_Distance`` on
``GEOGRAPHY`` -- true ellipsoidal metres, but straight lines, and therefore
**lower bounds on travel distance**. A column named ``distance_to_hospital``
would eventually be read by somebody as ambulance minutes, which in a district
whose only bridge fell is a dangerously wrong number. The name carries the
caveat so the schema cannot be misread without reading the word "geodesic".

These tables are owned by this migration rather than by a SQLAlchemy model, as
the census read paths of the prioritization module already are: every consumer
reads them through explicit ``text()`` SQL in
``app.modules.prioritization.infrastructure.coping_repository``.

Revision ID: 0005_osm_coping_capacity
Revises: 0004_place_census_attachment
Create Date: 2026-10-16 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
from geoalchemy2 import Geography
import sqlalchemy as sa

revision: str = "0005_osm_coping_capacity"
down_revision: str | None = "0004_place_census_attachment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OSM_SOURCE = "OpenStreetMap via Geofabrik, el-salvador-latest.osm.pbf"
OSM_LICENCE = "ODbL 1.0"

POINT_4326 = Geography(geometry_type="POINT", srid=4326, spatial_index=False)
LINESTRING_4326 = Geography(
    geometry_type="LINESTRING", srid=4326, spatial_index=False
)


def upgrade() -> None:
    """Create the OSM facility, road and cached-access tables with their indexes."""
    op.create_table(
        "osm_coping_facility",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("osm_type", sa.String(length=10), nullable=False),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "name",
            sa.String(length=200),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column("geom", POINT_4326, nullable=False),
        sa.Column(
            "source",
            sa.String(length=80),
            server_default=sa.text(f"'{OSM_SOURCE}'"),
            nullable=False,
        ),
        sa.Column(
            "licence",
            sa.String(length=24),
            server_default=sa.text(f"'{OSM_LICENCE}'"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="osm_coping_facility_pkey"),
        # One row per upstream object per capability, so re-ingesting the daily
        # extract updates in place instead of duplicating the country.
        sa.UniqueConstraint(
            "osm_type", "osm_id", "kind", name="uq_osm_coping_facility_object"
        ),
        sa.CheckConstraint(
            "osm_type IN ('node', 'way', 'relation')",
            name="ck_osm_coping_facility_osm_type",
        ),
    )
    op.create_index(
        "idx_osm_coping_facility_geom",
        "osm_coping_facility",
        ["geom"],
        postgresql_using="gist",
    )
    # Every nearest-facility search filters by kind first, so this index lets the
    # hospital-or-clinic pass read one index instead of scanning the table twice.
    op.create_index(
        "idx_osm_coping_facility_kind", "osm_coping_facility", ["kind"]
    )

    op.create_table(
        "osm_road_segment",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("road_class", sa.String(length=16), nullable=False),
        sa.Column("highway_tag", sa.String(length=24), nullable=False),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column("geom", LINESTRING_4326, nullable=False),
        sa.Column(
            "source",
            sa.String(length=80),
            server_default=sa.text(f"'{OSM_SOURCE}'"),
            nullable=False,
        ),
        sa.Column(
            "licence",
            sa.String(length=24),
            server_default=sa.text(f"'{OSM_LICENCE}'"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="osm_road_segment_pkey"),
        sa.UniqueConstraint("osm_id", name="uq_osm_road_segment_object"),
    )
    op.create_index(
        "idx_osm_road_segment_geom",
        "osm_road_segment",
        ["geom"],
        postgresql_using="gist",
    )
    # The areal pass buffers and intersects in projected geometry space, for the
    # same reason B4 does: measured on this corpus the geometry-space pass with
    # this index runs in about 5 s against minutes without it.
    op.execute(
        "CREATE INDEX idx_osm_road_segment_geom_geometry "
        "ON osm_road_segment USING gist ((geom::geometry))"
    )
    op.create_index("idx_osm_road_segment_class", "osm_road_segment", ["road_class"])

    op.create_table(
        "osm_unit_access",
        sa.Column("population_unit_id", sa.BigInteger(), nullable=False),
        # Nullable throughout: NULL means "not measurable on this corpus", never
        # zero metres. Zero would be the single most dangerous value here,
        # because it reads as "a hospital is on the doorstep".
        sa.Column(
            "geodesic_metres_to_nearest_health", sa.Numeric(12, 2), nullable=True
        ),
        sa.Column(
            "geodesic_metres_to_nearest_road", sa.Numeric(12, 2), nullable=True
        ),
        sa.Column(
            "geodesic_metres_to_nearest_fire_station",
            sa.Numeric(12, 2),
            nullable=True,
        ),
        sa.Column("area_m2", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "area_beyond_health_threshold_m2", sa.Numeric(18, 2), nullable=False
        ),
        sa.Column(
            "area_beyond_road_threshold_m2", sa.Numeric(18, 2), nullable=False
        ),
        sa.Column(
            "shelter_facility_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("access_threshold_metres", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("population_unit_id", name="osm_unit_access_pkey"),
        sa.ForeignKeyConstraint(
            ["population_unit_id"],
            ["census_population_unit.id"],
            name="fk_osm_unit_access_population_unit",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("area_m2 > 0", name="ck_osm_unit_access_area_positive"),
        sa.CheckConstraint(
            "area_beyond_health_threshold_m2 >= 0 "
            "AND area_beyond_health_threshold_m2 <= area_m2",
            name="ck_osm_unit_access_health_area_within_unit",
        ),
        sa.CheckConstraint(
            "area_beyond_road_threshold_m2 >= 0 "
            "AND area_beyond_road_threshold_m2 <= area_m2",
            name="ck_osm_unit_access_road_area_within_unit",
        ),
        sa.CheckConstraint(
            "shelter_facility_count >= 0",
            name="ck_osm_unit_access_shelter_non_negative",
        ),
        sa.CheckConstraint(
            "access_threshold_metres > 0",
            name="ck_osm_unit_access_threshold_positive",
        ),
        # Every distance here is a lower bound on travel distance, but it is
        # still a distance: a negative one is a defect upstream, not a short trip.
        sa.CheckConstraint(
            "geodesic_metres_to_nearest_health IS NULL "
            "OR geodesic_metres_to_nearest_health >= 0",
            name="ck_osm_unit_access_health_distance_non_negative",
        ),
        sa.CheckConstraint(
            "geodesic_metres_to_nearest_road IS NULL "
            "OR geodesic_metres_to_nearest_road >= 0",
            name="ck_osm_unit_access_road_distance_non_negative",
        ),
        sa.CheckConstraint(
            "geodesic_metres_to_nearest_fire_station IS NULL "
            "OR geodesic_metres_to_nearest_fire_station >= 0",
            name="ck_osm_unit_access_fire_distance_non_negative",
        ),
    )


def downgrade() -> None:
    """Drop the three tables, newest dependency first."""
    op.drop_table("osm_unit_access")
    op.drop_index("idx_osm_road_segment_class", table_name="osm_road_segment")
    op.execute("DROP INDEX IF EXISTS idx_osm_road_segment_geom_geometry")
    op.drop_index("idx_osm_road_segment_geom", table_name="osm_road_segment")
    op.drop_table("osm_road_segment")
    op.drop_index("idx_osm_coping_facility_kind", table_name="osm_coping_facility")
    op.drop_index("idx_osm_coping_facility_geom", table_name="osm_coping_facility")
    op.drop_table("osm_coping_facility")
