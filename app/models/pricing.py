from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import PriceJobStatus, PriceObservationStatus, PriceRunStatus


class PriceCategory(Base):
    __tablename__ = "price_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    monitored_items = relationship("MonitoredItem", back_populates="category")


class MonitoredItem(Base):
    __tablename__ = "monitored_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("price_categories.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category = relationship("PriceCategory", back_populates="monitored_items")
    observations = relationship("PriceObservation", back_populates="monitored_item")
    snapshots = relationship("DailyPriceSnapshot", back_populates="monitored_item")


class MarketSource(Base):
    __tablename__ = "market_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    runs = relationship("PriceScrapeRun", back_populates="source")
    observations = relationship("PriceObservation", back_populates="source")
    snapshots = relationship("DailyPriceSnapshot", back_populates="source")


class PriceScrapeRun(Base):
    __tablename__ = "price_scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("market_sources.id"), nullable=False)
    external_run_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[PriceRunStatus] = mapped_column(
        Enum(PriceRunStatus, name="price_run_status"),
        nullable=False,
        default=PriceRunStatus.success,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    jobs_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_blocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_report: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source = relationship("MarketSource", back_populates="runs")
    observations = relationship(
        "PriceObservation",
        back_populates="scrape_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    snapshots = relationship(
        "DailyPriceSnapshot",
        back_populates="scrape_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    parser_errors = relationship(
        "ParserError",
        back_populates="scrape_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (
        UniqueConstraint(
            "scrape_run_id",
            "source_id",
            "external_id",
            name="uq_price_observations_run_source_external",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scrape_run_id: Mapped[int] = mapped_column(ForeignKey("price_scrape_runs.id", ondelete="CASCADE"), nullable=False)
    monitored_item_id: Mapped[int] = mapped_column(ForeignKey("monitored_items.id"), nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("market_sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="RUB")
    url: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    relevance_status: Mapped[PriceObservationStatus] = mapped_column(
        Enum(PriceObservationStatus, name="price_observation_status"),
        nullable=False,
        default=PriceObservationStatus.relevant,
    )
    reject_reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scrape_run = relationship("PriceScrapeRun", back_populates="observations")
    monitored_item = relationship("MonitoredItem", back_populates="observations")
    source = relationship("MarketSource", back_populates="observations")


class DailyPriceSnapshot(Base):
    __tablename__ = "daily_price_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "monitored_item_id",
            "source_id",
            "snapshot_date",
            name="uq_daily_price_snapshots_item_source_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scrape_run_id: Mapped[int] = mapped_column(ForeignKey("price_scrape_runs.id", ondelete="CASCADE"), nullable=False)
    monitored_item_id: Mapped[int] = mapped_column(ForeignKey("monitored_items.id"), nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("market_sources.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PriceJobStatus] = mapped_column(
        Enum(PriceJobStatus, name="price_job_status"),
        nullable=False,
        default=PriceJobStatus.success,
    )
    raw_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    normalized_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relevant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    median_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="RUB")
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scrape_run = relationship("PriceScrapeRun", back_populates="snapshots")
    monitored_item = relationship("MonitoredItem", back_populates="snapshots")
    source = relationship("MarketSource", back_populates="snapshots")


class ParserError(Base):
    __tablename__ = "parser_errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    scrape_run_id: Mapped[int] = mapped_column(ForeignKey("price_scrape_runs.id", ondelete="CASCADE"), nullable=False)
    monitored_item_id: Mapped[int | None] = mapped_column(ForeignKey("monitored_items.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("market_sources.id"), nullable=False)
    job_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PriceJobStatus] = mapped_column(Enum(PriceJobStatus, name="price_job_status"), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    block_reason: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    raw_report: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scrape_run = relationship("PriceScrapeRun", back_populates="parser_errors")
    monitored_item = relationship("MonitoredItem")
    source = relationship("MarketSource")
