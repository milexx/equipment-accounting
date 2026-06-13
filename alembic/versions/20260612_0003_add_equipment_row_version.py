"""add equipment row version

Revision ID: 20260612_0003
Revises: 20260612_0002
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260612_0003"
down_revision: str | None = "20260612_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "equipment",
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("equipment", "row_version", server_default=None)


def downgrade() -> None:
    op.drop_column("equipment", "row_version")
