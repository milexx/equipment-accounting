"""add center admin role

Revision ID: 20260613_0004
Revises: 20260612_0003
Create Date: 2026-06-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260613_0004"
down_revision: str | None = "20260612_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'center_admin'")
    op.drop_constraint("chk_region_user_region", "users", type_="check")
    op.create_check_constraint(
        "chk_region_user_region",
        "users",
        "(role = 'region' AND region_id IS NOT NULL) OR role IN ('center', 'center_admin')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_region_user_region", "users", type_="check")
    op.create_check_constraint(
        "chk_region_user_region",
        "users",
        "(role = 'region' AND region_id IS NOT NULL) OR role = 'center'",
    )
