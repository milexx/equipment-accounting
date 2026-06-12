"""initial schema

Revision ID: 20260612_0001
Revises:
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260612_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_role = postgresql.ENUM("region", "center", name="user_role")
    equipment_status = postgresql.ENUM(
        "draft",
        "submitted",
        "needs_revision",
        "accepted",
        "diagnostics_required",
        "writeoff_review",
        "writeoff_approved",
        "disposal_pending",
        "disposed",
        "valuation_pending",
        "valued",
        "sale_ready",
        "listed_for_sale",
        "sold",
        "archived",
        "deleted",
        name="equipment_status",
    )
    equipment_condition = postgresql.ENUM(
        "unknown",
        "working",
        "broken",
        "partially_working",
        "requires_diagnostics",
        name="equipment_condition",
    )
    equipment_disposition = postgresql.ENUM(
        "undecided",
        "writeoff",
        "disposal",
        "valuation",
        "sale",
        name="equipment_disposition",
    )
    equipment_sale_status = postgresql.ENUM(
        "not_for_sale",
        "valuation_pending",
        "priced",
        "ready",
        "listed",
        "reserved",
        "sold",
        name="equipment_sale_status",
    )
    equipment_field_type = postgresql.ENUM(
        "string",
        "text",
        "integer",
        "decimal",
        "date",
        "boolean",
        "select",
        "multiselect",
        name="equipment_field_type",
    )
    equipment_photo_purpose = postgresql.ENUM(
        "general",
        "serial",
        "defect",
        "completeness",
        "other",
        name="equipment_photo_purpose",
    )

    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    equipment_status.create(bind, checkfirst=True)
    equipment_condition.create(bind, checkfirst=True)
    equipment_disposition.create(bind, checkfirst=True)
    equipment_sale_status.create(bind, checkfirst=True)
    equipment_field_type.create(bind, checkfirst=True)
    equipment_photo_purpose.create(bind, checkfirst=True)

    op.create_table(
        "regions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("region_id", sa.BigInteger(), sa.ForeignKey("regions.id")),
        sa.Column("role", postgresql.ENUM(name="user_role", create_type=False), nullable=False),
        sa.Column("login", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text()),
        sa.Column("api_token_hash", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "(role = 'region' AND region_id IS NOT NULL) OR role = 'center'",
            name="chk_region_user_region",
        ),
    )

    op.create_table(
        "equipment_types",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "equipment_type_fields",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "equipment_type_id",
            sa.BigInteger(),
            sa.ForeignKey("equipment_types.id"),
            nullable=False,
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("field_type", postgresql.ENUM(name="equipment_field_type", create_type=False), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_filterable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "validation_rules",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("help_text", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("equipment_type_id", "code"),
    )

    op.create_table(
        "equipment",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("region_id", sa.BigInteger(), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column(
            "equipment_type_id",
            sa.BigInteger(),
            sa.ForeignKey("equipment_types.id"),
            nullable=False,
        ),
        sa.Column("status", postgresql.ENUM(name="equipment_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("inventory_number", sa.Text()),
        sa.Column("serial_number", sa.Text()),
        sa.Column("condition", postgresql.ENUM(name="equipment_condition", create_type=False), nullable=False, server_default="unknown"),
        sa.Column("disposition", postgresql.ENUM(name="equipment_disposition", create_type=False), nullable=False, server_default="undecided"),
        sa.Column("sale_status", postgresql.ENUM(name="equipment_sale_status", create_type=False), nullable=False, server_default="not_for_sale"),
        sa.Column("comment", sa.Text()),
        sa.Column("revision_comment", sa.Text()),
        sa.Column("defect_description", sa.Text()),
        sa.Column("completeness", sa.Text()),
        sa.Column("valuation_amount", sa.Numeric(14, 2)),
        sa.Column("sale_price", sa.Numeric(14, 2)),
        sa.Column("sale_description", sa.Text()),
        sa.Column("is_public_listing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("updated_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "equipment_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "equipment_id",
            sa.BigInteger(),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_path", sa.Text(), nullable=False),
        sa.Column("thumbnail_path", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text()),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("purpose", postgresql.ENUM(name="equipment_photo_purpose", create_type=False), nullable=False, server_default="general"),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "equipment_audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("equipment_id", sa.BigInteger(), sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("actor_region_id", sa.BigInteger(), sa.ForeignKey("regions.id")),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("old_data", postgresql.JSONB()),
        sa.Column("new_data", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("idx_users_region_id", "users", ["region_id"])
    op.create_index("idx_users_role", "users", ["role"])
    op.create_index("idx_equipment_region_id", "equipment", ["region_id"])
    op.create_index("idx_equipment_status", "equipment", ["status"])
    op.create_index("idx_equipment_type_id", "equipment", ["equipment_type_id"])
    op.create_index("idx_equipment_inventory_number", "equipment", ["inventory_number"])
    op.create_index("idx_equipment_serial_number", "equipment", ["serial_number"])
    op.create_index("idx_equipment_condition", "equipment", ["condition"])
    op.create_index("idx_equipment_disposition", "equipment", ["disposition"])
    op.create_index("idx_equipment_sale_status", "equipment", ["sale_status"])
    op.create_index("idx_equipment_created_at", "equipment", [sa.text("created_at DESC")])
    op.create_index("idx_equipment_updated_at", "equipment", [sa.text("updated_at DESC")])
    op.create_index(
        "idx_equipment_region_type_status",
        "equipment",
        ["region_id", "equipment_type_id", "status"],
    )
    op.create_index(
        "idx_equipment_active_list",
        "equipment",
        ["region_id", "equipment_type_id", "status", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_equipment_not_deleted",
        "equipment",
        ["id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_equipment_attributes_gin",
        "equipment",
        ["attributes"],
        postgresql_using="gin",
    )
    op.create_index("idx_equipment_photos_equipment_id", "equipment_photos", ["equipment_id"])
    op.create_index(
        "idx_equipment_photos_purpose",
        "equipment_photos",
        ["equipment_id", "purpose"],
    )
    op.create_index(
        "idx_equipment_audit_equipment_id",
        "equipment_audit_log",
        ["equipment_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_equipment_audit_equipment_id", table_name="equipment_audit_log")
    op.drop_index("idx_equipment_photos_purpose", table_name="equipment_photos")
    op.drop_index("idx_equipment_photos_equipment_id", table_name="equipment_photos")
    op.drop_index("idx_equipment_attributes_gin", table_name="equipment")
    op.drop_index("idx_equipment_not_deleted", table_name="equipment")
    op.drop_index("idx_equipment_active_list", table_name="equipment")
    op.drop_index("idx_equipment_region_type_status", table_name="equipment")
    op.drop_index("idx_equipment_updated_at", table_name="equipment")
    op.drop_index("idx_equipment_created_at", table_name="equipment")
    op.drop_index("idx_equipment_sale_status", table_name="equipment")
    op.drop_index("idx_equipment_disposition", table_name="equipment")
    op.drop_index("idx_equipment_condition", table_name="equipment")
    op.drop_index("idx_equipment_serial_number", table_name="equipment")
    op.drop_index("idx_equipment_inventory_number", table_name="equipment")
    op.drop_index("idx_equipment_type_id", table_name="equipment")
    op.drop_index("idx_equipment_status", table_name="equipment")
    op.drop_index("idx_equipment_region_id", table_name="equipment")
    op.drop_index("idx_users_role", table_name="users")
    op.drop_index("idx_users_region_id", table_name="users")

    op.drop_table("equipment_audit_log")
    op.drop_table("equipment_photos")
    op.drop_table("equipment")
    op.drop_table("equipment_type_fields")
    op.drop_table("equipment_types")
    op.drop_table("users")
    op.drop_table("regions")

    bind = op.get_bind()
    postgresql.ENUM(name="equipment_photo_purpose").drop(bind, checkfirst=True)
    postgresql.ENUM(name="equipment_field_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="equipment_sale_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="equipment_disposition").drop(bind, checkfirst=True)
    postgresql.ENUM(name="equipment_condition").drop(bind, checkfirst=True)
    postgresql.ENUM(name="equipment_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="user_role").drop(bind, checkfirst=True)

