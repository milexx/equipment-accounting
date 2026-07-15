"""add low_sample price job status

Revision ID: 20260630_0007
Revises: 20260620_0006
Create Date: 2026-06-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260630_0007"
down_revision: str | None = "20260620_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE price_job_status ADD VALUE IF NOT EXISTS 'low_sample'")


def downgrade() -> None:
    pass
