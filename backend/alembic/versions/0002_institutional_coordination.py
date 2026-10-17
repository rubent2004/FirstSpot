"""Verified organization accounts and immutable attributed place activity.

Revision ID: 0002_institutional_coordination
Revises: 0001_initial
Create Date: 2026-10-16 23:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_institutional_coordination"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=False),
        sa.Column("sector", sa.String(length=80), nullable=False),
        sa.Column("contact_email", sa.String(length=254), nullable=False),
        sa.Column("registration_code", sa.String(length=24), nullable=False),
        sa.Column("verification_status", sa.String(length=24), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "verification_status IN ('pending', 'verified', 'rejected')",
            name="ck_institutions_verification_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("registration_code"),
    )

    op.create_table(
        "institution_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), server_default=sa.text("'member'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'member')", name="ck_institution_users_role"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("id", "institution_id", name="uq_institution_user_membership"),
    )
    op.create_index("idx_institution_users_institution", "institution_users", ["institution_id"])

    op.create_table(
        "institution_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["institution_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index("idx_institution_invites_org", "institution_invites", ["institution_id"])

    op.create_table(
        "place_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("attention_status", sa.String(length=32), nullable=True),
        sa.Column("urgency_level", sa.Integer(), nullable=True),
        sa.Column("estimated_vulnerable_count", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "activity_type IN ('reported', 'en_route', 'on_scene', 'needs_support', 'resource_available', 'update', 'resolved')",
            name="ck_place_activities_type",
        ),
        sa.CheckConstraint(
            "attention_status IS NULL OR attention_status IN ('pending', 'in_progress', 'attended')",
            name="ck_place_activities_attention_status",
        ),
        sa.CheckConstraint("urgency_level IS NULL OR urgency_level BETWEEN 1 AND 5", name="ck_place_activities_urgency"),
        sa.CheckConstraint(
            "estimated_vulnerable_count IS NULL OR estimated_vulnerable_count >= 0",
            name="ck_place_activities_population",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["institutions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["place_id"], ["vulnerable_places.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["institution_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_place_activities_place_created", "place_activities", ["place_id", "created_at"])
    op.create_index("idx_place_activities_org_created", "place_activities", ["organization_id", "created_at"])

    op.execute(
        """
        CREATE FUNCTION reject_place_activity_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'place_activities is an append-only audit log';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER place_activities_immutable
        BEFORE UPDATE OR DELETE ON place_activities
        FOR EACH ROW EXECUTE FUNCTION reject_place_activity_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS place_activities_immutable ON place_activities")
    op.execute("DROP FUNCTION IF EXISTS reject_place_activity_mutation()")
    op.drop_index("idx_place_activities_org_created", table_name="place_activities")
    op.drop_index("idx_place_activities_place_created", table_name="place_activities")
    op.drop_table("place_activities")
    op.drop_index("idx_institution_invites_org", table_name="institution_invites")
    op.drop_table("institution_invites")
    op.drop_index("idx_institution_users_institution", table_name="institution_users")
    op.drop_table("institution_users")
    op.drop_table("institutions")
