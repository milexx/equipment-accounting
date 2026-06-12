"""add equipment location

Revision ID: 20260612_0002
Revises: 20260612_0001
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260612_0002"
down_revision: str | None = "20260612_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("equipment", sa.Column("location", sa.Text()))
    op.create_index("idx_equipment_location", "equipment", ["location"])


def downgrade() -> None:
    op.drop_index("idx_equipment_location", table_name="equipment")
    op.drop_column("equipment", "location")

