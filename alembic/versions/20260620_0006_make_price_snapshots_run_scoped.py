"""make price snapshots run scoped

Revision ID: 20260620_0006
Revises: 20260620_0005
Create Date: 2026-06-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260620_0006"
down_revision: str | None = "20260620_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_daily_price_snapshots_item_source_date",
        "daily_price_snapshots",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_daily_price_snapshots_run_item_source_date",
        "daily_price_snapshots",
        ["scrape_run_id", "monitored_item_id", "source_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_daily_price_snapshots_run_item_source_date",
        "daily_price_snapshots",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_daily_price_snapshots_item_source_date",
        "daily_price_snapshots",
        ["monitored_item_id", "source_id", "snapshot_date"],
    )
