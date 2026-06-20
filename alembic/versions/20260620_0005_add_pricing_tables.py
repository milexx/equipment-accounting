"""add pricing tables

Revision ID: 20260620_0005
Revises: 20260613_0004
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260620_0005"
down_revision: str | None = "20260613_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


price_run_status = postgresql.ENUM(
    "success",
    "partial_success",
    "failed",
    name="price_run_status",
    create_type=False,
)
price_job_status = postgresql.ENUM(
    "success",
    "no_data",
    "blocked",
    "captcha",
    "parser_error",
    name="price_job_status",
    create_type=False,
)
price_observation_status = postgresql.ENUM(
    "relevant",
    "unknown",
    "rejected",
    name="price_observation_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    price_run_status.create(bind, checkfirst=True)
    price_job_status.create(bind, checkfirst=True)
    price_observation_status.create(bind, checkfirst=True)

    op.create_table(
        "price_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "market_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "monitored_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["price_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "price_scrape_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("external_run_id", sa.Text(), nullable=False),
        sa.Column("status", price_run_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("jobs_total", sa.Integer(), nullable=False),
        sa.Column("jobs_success", sa.Integer(), nullable=False),
        sa.Column("jobs_blocked", sa.Integer(), nullable=False),
        sa.Column("jobs_failed", sa.Integer(), nullable=False),
        sa.Column("raw_report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["market_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_run_id"),
    )
    op.create_table(
        "daily_price_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scrape_run_id", sa.Integer(), nullable=False),
        sa.Column("monitored_item_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("status", price_job_status, nullable=False),
        sa.Column("raw_count", sa.Integer(), nullable=False),
        sa.Column("normalized_count", sa.Integer(), nullable=False),
        sa.Column("relevant_count", sa.Integer(), nullable=False),
        sa.Column("unknown_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("min_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("median_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["monitored_item_id"], ["monitored_items.id"]),
        sa.ForeignKeyConstraint(["scrape_run_id"], ["price_scrape_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["market_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "monitored_item_id",
            "source_id",
            "snapshot_date",
            name="uq_daily_price_snapshots_item_source_date",
        ),
    )
    op.create_table(
        "parser_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scrape_run_id", sa.Integer(), nullable=False),
        sa.Column("monitored_item_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("job_code", sa.Text(), nullable=False),
        sa.Column("status", price_job_status, nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("raw_report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["monitored_item_id"], ["monitored_items.id"]),
        sa.ForeignKeyConstraint(["scrape_run_id"], ["price_scrape_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["market_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "price_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scrape_run_id", sa.Integer(), nullable=False),
        sa.Column("monitored_item_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("relevance_status", price_observation_status, nullable=False),
        sa.Column("reject_reasons", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["monitored_item_id"], ["monitored_items.id"]),
        sa.ForeignKeyConstraint(["scrape_run_id"], ["price_scrape_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["market_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scrape_run_id",
            "source_id",
            "external_id",
            name="uq_price_observations_run_source_external",
        ),
    )


def downgrade() -> None:
    op.drop_table("price_observations")
    op.drop_table("parser_errors")
    op.drop_table("daily_price_snapshots")
    op.drop_table("price_scrape_runs")
    op.drop_table("monitored_items")
    op.drop_table("market_sources")
    op.drop_table("price_categories")

    bind = op.get_bind()
    price_observation_status.drop(bind, checkfirst=True)
    price_job_status.drop(bind, checkfirst=True)
    price_run_status.drop(bind, checkfirst=True)
