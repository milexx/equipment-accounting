import json
import statistics
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.enums import PriceJobStatus, PriceObservationStatus, PriceRunStatus
from app.models.pricing import (
    DailyPriceSnapshot,
    MarketSource,
    MonitoredItem,
    ParserError,
    PriceCategory,
    PriceObservation,
    PriceScrapeRun,
)


class PricingImportResult:
    def __init__(
        self,
        *,
        run: PriceScrapeRun,
        observations_created: int,
        snapshots_saved: int,
        parser_errors_created: int,
    ) -> None:
        self.run = run
        self.observations_created = observations_created
        self.snapshots_saved = snapshots_saved
        self.parser_errors_created = parser_errors_created


class PricingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_source(
        self,
        *,
        code: str,
        name: str,
        base_url: str | None = None,
    ) -> MarketSource:
        source = self.db.scalar(select(MarketSource).where(MarketSource.code == code))
        if source is not None:
            return source
        source = MarketSource(code=code, name=name, base_url=base_url)
        self.db.add(source)
        self.db.flush()
        return source

    def get_or_create_source_by_code(self, code: str | None) -> MarketSource:
        source_code = code or "avito"
        metadata = _source_metadata(source_code)
        return self.get_or_create_source(
            code=source_code,
            name=metadata["name"],
            base_url=metadata["base_url"],
        )

    def get_or_create_category(self, *, code: str, name: str) -> PriceCategory:
        category = self.db.scalar(select(PriceCategory).where(PriceCategory.code == code))
        if category is not None:
            return category
        category = PriceCategory(code=code, name=name)
        self.db.add(category)
        self.db.flush()
        return category

    def get_or_create_monitored_item(
        self,
        *,
        category: PriceCategory,
        code: str,
        name: str,
    ) -> MonitoredItem:
        item = self.db.scalar(select(MonitoredItem).where(MonitoredItem.code == code))
        if item is not None:
            if item.name != name:
                item.name = name
            return item
        item = MonitoredItem(category_id=category.id, code=code, name=name)
        self.db.add(item)
        self.db.flush()
        return item

    def create_or_update_run(
        self,
        *,
        source: MarketSource,
        external_run_id: str,
        status: PriceRunStatus,
        started_at: datetime | None,
        finished_at: datetime | None,
        jobs_total: int,
        jobs_success: int,
        jobs_blocked: int,
        jobs_failed: int,
        raw_report: dict[str, Any],
    ) -> PriceScrapeRun:
        run = self.db.scalar(
            select(PriceScrapeRun).where(PriceScrapeRun.external_run_id == external_run_id)
        )
        if run is None:
            run = PriceScrapeRun(source_id=source.id, external_run_id=external_run_id)
            self.db.add(run)
            self.db.flush()
        else:
            self._clear_run_children(run)

        run.source_id = source.id
        run.status = status
        run.started_at = started_at
        run.finished_at = finished_at
        run.jobs_total = jobs_total
        run.jobs_success = jobs_success
        run.jobs_blocked = jobs_blocked
        run.jobs_failed = jobs_failed
        run.raw_report = raw_report
        self.db.flush()
        return run

    def add_observation(
        self,
        *,
        run: PriceScrapeRun,
        item: MonitoredItem,
        source: MarketSource,
        listing: dict[str, Any],
    ) -> PriceObservation:
        observation = PriceObservation(
            scrape_run_id=run.id,
            monitored_item_id=item.id,
            source_id=source.id,
            external_id=str(listing["external_id"]),
            title=listing["title"],
            description=listing.get("description"),
            price=_decimal_or_none(listing.get("price")) or Decimal("0"),
            currency=listing.get("currency") or "RUB",
            url=listing["url"],
            location=listing.get("location"),
            published_at=_parse_datetime(listing.get("published_at")),
            fetched_at=_parse_datetime(listing.get("fetched_at")) or datetime.now(timezone.utc),
            relevance_status=PriceObservationStatus(listing.get("relevance_status", "relevant")),
            reject_reasons=listing.get("reject_reasons") or [],
            raw_payload=listing.get("raw_payload") or {},
        )
        self.db.add(observation)
        return observation

    def save_parser_error(
        self,
        *,
        run: PriceScrapeRun,
        item: MonitoredItem | None,
        source: MarketSource,
        job_code: str,
        status: PriceJobStatus,
        raw_report: dict[str, Any],
    ) -> ParserError:
        parser_error = ParserError(
            scrape_run_id=run.id,
            monitored_item_id=item.id if item else None,
            source_id=source.id,
            job_code=job_code,
            status=status,
            http_status=raw_report.get("http_status"),
            block_reason=raw_report.get("block_reason"),
            error=raw_report.get("error"),
            raw_report=raw_report,
        )
        self.db.add(parser_error)
        return parser_error

    def save_snapshot(
        self,
        *,
        run: PriceScrapeRun,
        item: MonitoredItem,
        source: MarketSource,
        snapshot: dict[str, Any],
    ) -> DailyPriceSnapshot:
        snapshot_date = _parse_date(snapshot.get("snapshot_date"))
        if snapshot_date is None:
            fetched_at = _parse_datetime(snapshot.get("fetched_at"))
            snapshot_date = fetched_at.date() if fetched_at else date.today()

        daily_snapshot = self.db.scalar(
            select(DailyPriceSnapshot).where(
                DailyPriceSnapshot.scrape_run_id == run.id,
                DailyPriceSnapshot.monitored_item_id == item.id,
                DailyPriceSnapshot.source_id == source.id,
                DailyPriceSnapshot.snapshot_date == snapshot_date,
            )
        )
        if daily_snapshot is None:
            daily_snapshot = DailyPriceSnapshot(
                monitored_item_id=item.id,
                source_id=source.id,
                snapshot_date=snapshot_date,
            )
            self.db.add(daily_snapshot)

        daily_snapshot.scrape_run_id = run.id
        daily_snapshot.status = PriceJobStatus(snapshot.get("status", "no_data"))
        daily_snapshot.raw_count = int(snapshot.get("raw_count") or 0)
        daily_snapshot.normalized_count = int(snapshot.get("normalized_count") or 0)
        daily_snapshot.relevant_count = int(snapshot.get("relevant_count") or 0)
        daily_snapshot.unknown_count = int(snapshot.get("unknown_count") or 0)
        daily_snapshot.rejected_count = int(snapshot.get("rejected_count") or 0)
        daily_snapshot.min_price = _decimal_or_none(snapshot.get("min_price"))
        daily_snapshot.max_price = _decimal_or_none(snapshot.get("max_price"))
        daily_snapshot.median_price = _decimal_or_none(snapshot.get("median_price"))
        daily_snapshot.currency = snapshot.get("currency") or "RUB"
        daily_snapshot.fetched_at = _parse_datetime(snapshot.get("fetched_at"))
        return daily_snapshot

    def calculate_snapshot(
        self,
        *,
        item: MonitoredItem,
        source: MarketSource,
        snapshot_date: date,
        observations: list[PriceObservation],
    ) -> dict[str, Any]:
        prices = [observation.price for observation in observations]
        return {
            "job_code": item.code,
            "source": source.code,
            "snapshot_date": snapshot_date.isoformat(),
            "status": "success" if prices else "no_data",
            "raw_count": len(observations),
            "normalized_count": len(observations),
            "relevant_count": len(observations),
            "unknown_count": 0,
            "rejected_count": 0,
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "median_price": Decimal(str(statistics.median(prices))) if prices else None,
            "currency": observations[0].currency if observations else "RUB",
        }

    def import_poc_run(self, run_dir: Path) -> PricingImportResult:
        run_report = _read_json(run_dir / "run_report.json")
        source = self.get_or_create_source_by_code(run_report.get("source") or "avito")
        category = self.get_or_create_category(code="used_equipment", name="Б/у оборудование")

        run = self.create_or_update_run(
            source=source,
            external_run_id=run_report.get("run_id") or run_dir.name,
            status=PriceRunStatus(run_report.get("status", "failed")),
            started_at=_parse_datetime(run_report.get("started_at")),
            finished_at=_parse_datetime(run_report.get("finished_at")),
            jobs_total=int(run_report.get("jobs_total") or 0),
            jobs_success=int(run_report.get("jobs_success") or 0),
            jobs_blocked=int(run_report.get("jobs_blocked") or 0),
            jobs_failed=int(run_report.get("jobs_failed") or 0),
            raw_report=run_report,
        )

        observations_created = 0
        snapshots_saved = 0
        parser_errors_created = 0

        for job_report in run_report.get("job_reports", []):
            job_code = job_report["job_code"]
            job_dir = run_dir / job_code
            snapshot = _read_json(job_dir / "daily_snapshot.json", default={})
            item_name = snapshot.get("position_name") or job_code
            item = self.get_or_create_monitored_item(category=category, code=job_code, name=item_name)
            status = PriceJobStatus(job_report.get("status", "parser_error"))
            snapshot_source = self.get_or_create_source_by_code(
                snapshot.get("source") or job_report.get("source") or "avito"
            )

            if status == PriceJobStatus.success:
                listings = _read_json(job_dir / "relevant_listings.json", default=[])
                for listing in listings:
                    listing_source = self.get_or_create_source_by_code(
                        listing.get("source") or snapshot_source.code
                    )
                    self.add_observation(run=run, item=item, source=listing_source, listing=listing)
                    observations_created += 1

            if snapshot:
                self.save_snapshot(run=run, item=item, source=snapshot_source, snapshot=snapshot)
                snapshots_saved += 1
            else:
                fallback_snapshot = _snapshot_from_job_report(job_report)
                fallback_source = self.get_or_create_source_by_code(fallback_snapshot.get("source"))
                self.save_snapshot(
                    run=run,
                    item=item,
                    source=fallback_source,
                    snapshot=fallback_snapshot,
                )
                snapshots_saved += 1

            if status not in {PriceJobStatus.success, PriceJobStatus.no_data}:
                error_source = self.get_or_create_source_by_code(job_report.get("source") or "avito")
                self.save_parser_error(
                    run=run,
                    item=item,
                    source=error_source,
                    job_code=job_code,
                    status=status,
                    raw_report=job_report,
                )
                parser_errors_created += 1

        self.db.commit()
        self.db.refresh(run)
        return PricingImportResult(
            run=run,
            observations_created=observations_created,
            snapshots_saved=snapshots_saved,
            parser_errors_created=parser_errors_created,
        )

    def _clear_run_children(self, run: PriceScrapeRun) -> None:
        self.db.execute(delete(PriceObservation).where(PriceObservation.scrape_run_id == run.id))
        self.db.execute(delete(ParserError).where(ParserError.scrape_run_id == run.id))
        self.db.execute(delete(DailyPriceSnapshot).where(DailyPriceSnapshot.scrape_run_id == run.id))
        self.db.flush()


def _read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _parse_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    return date.fromisoformat(value)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _snapshot_from_job_report(job_report: dict[str, Any]) -> dict[str, Any]:
    fetched_at = job_report.get("fetched_at")
    return {
        "job_code": job_report["job_code"],
        "snapshot_date": fetched_at[:10] if isinstance(fetched_at, str) else None,
        "source": job_report.get("source") or "avito",
        "status": job_report.get("status", "parser_error"),
        "raw_count": job_report.get("items_found", 0),
        "normalized_count": job_report.get("items_normalized", 0),
        "relevant_count": job_report.get("items_relevant", 0),
        "unknown_count": job_report.get("items_unknown", 0),
        "rejected_count": job_report.get("items_rejected", 0),
        "min_price": None,
        "max_price": None,
        "median_price": None,
        "currency": "RUB",
        "fetched_at": fetched_at,
    }


def _source_metadata(code: str) -> dict[str, str | None]:
    metadata = {
        "avito": {"name": "Avito", "base_url": "https://www.avito.ru"},
        "avito_duff89": {"name": "Avito via Duff89", "base_url": "https://www.avito.ru"},
        "youla": {"name": "Youla", "base_url": "https://youla.ru"},
    }
    return metadata.get(code, {"name": code, "base_url": None})
