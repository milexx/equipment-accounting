import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.enums import PriceJobStatus, PriceRunStatus
from app.models.pricing import (
    DailyPriceSnapshot,
    MarketSource,
    MonitoredItem,
    ParserError,
    PriceObservation,
)
from app.services.pricing_service import PricingService


class PricingServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[
                Base.metadata.tables["price_categories"],
                Base.metadata.tables["market_sources"],
                Base.metadata.tables["monitored_items"],
                Base.metadata.tables["price_scrape_runs"],
                Base.metadata.tables["daily_price_snapshots"],
                Base.metadata.tables["parser_errors"],
                Base.metadata.tables["price_observations"],
            ],
        )
        self.session_factory = sessionmaker(bind=engine)
        self.db: Session = self.session_factory()
        self.service = PricingService(self.db)

    def tearDown(self) -> None:
        self.db.close()

    def test_import_poc_run_records_success_block_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _write_sample_run(Path(tmp))

            result = self.service.import_poc_run(run_dir)

        self.assertEqual(result.run.external_run_id, "run1")
        self.assertEqual(result.run.status, PriceRunStatus.partial_success)
        self.assertEqual(result.observations_created, 2)
        self.assertEqual(result.snapshots_saved, 2)
        self.assertEqual(result.parser_errors_created, 1)

        source = self.db.scalar(select(MarketSource).where(MarketSource.code == "avito"))
        self.assertIsNotNone(source)
        item = self.db.scalar(select(MonitoredItem).where(MonitoredItem.code == "lenovo_t14"))
        self.assertIsNotNone(item)

        observations = self.db.scalars(select(PriceObservation)).all()
        self.assertEqual(len(observations), 2)
        self.assertEqual({observation.external_id for observation in observations}, {"a1", "a2"})

        snapshot = self.db.scalar(
            select(DailyPriceSnapshot).where(DailyPriceSnapshot.monitored_item_id == item.id)
        )
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.status, PriceJobStatus.success)
        self.assertEqual(snapshot.snapshot_date, date(2026, 6, 20))
        self.assertEqual(snapshot.relevant_count, 2)
        self.assertEqual(snapshot.median_price, Decimal("30000.00"))

        parser_error = self.db.scalar(select(ParserError))
        self.assertIsNotNone(parser_error)
        self.assertEqual(parser_error.job_code, "dell_r740")
        self.assertEqual(parser_error.status, PriceJobStatus.blocked)
        self.assertEqual(parser_error.block_reason, "http_403")

    def test_import_poc_run_is_idempotent_for_same_external_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _write_sample_run(Path(tmp))

            first = self.service.import_poc_run(run_dir)
            second = self.service.import_poc_run(run_dir)

        self.assertEqual(first.run.id, second.run.id)
        self.assertEqual(len(self.db.scalars(select(PriceObservation)).all()), 2)
        self.assertEqual(len(self.db.scalars(select(DailyPriceSnapshot)).all()), 2)
        self.assertEqual(len(self.db.scalars(select(ParserError)).all()), 1)

    def test_import_preserves_multiple_snapshots_for_same_item_and_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_run_dir = _write_sample_run(Path(tmp), run_id="run1", lenovo_median=30000)
            second_run_dir = _write_sample_run(Path(tmp), run_id="run2", lenovo_median=32000)

            first = self.service.import_poc_run(first_run_dir)
            second = self.service.import_poc_run(second_run_dir)

        self.assertNotEqual(first.run.id, second.run.id)
        lenovo = self.db.scalar(select(MonitoredItem).where(MonitoredItem.code == "lenovo_t14"))
        snapshots = self.db.scalars(
            select(DailyPriceSnapshot)
            .where(DailyPriceSnapshot.monitored_item_id == lenovo.id)
            .order_by(DailyPriceSnapshot.scrape_run_id)
        ).all()

        self.assertEqual(len(snapshots), 2)
        self.assertEqual([snapshot.median_price for snapshot in snapshots], [Decimal("30000.00"), Decimal("32000.00")])

    def test_calculate_snapshot_uses_observation_prices(self) -> None:
        source = self.service.get_or_create_source(code="avito", name="Avito")
        category = self.service.get_or_create_category(code="used_equipment", name="Б/у оборудование")
        item = self.service.get_or_create_monitored_item(
            category=category,
            code="kyocera_m2040dn",
            name="Kyocera ECOSYS M2040dn",
        )
        run = self.service.create_or_update_run(
            source=source,
            external_run_id="manual1",
            status=PriceRunStatus.success,
            started_at=None,
            finished_at=None,
            jobs_total=1,
            jobs_success=1,
            jobs_blocked=0,
            jobs_failed=0,
            raw_report={},
        )
        observations = [
            self.service.add_observation(
                run=run,
                item=item,
                source=source,
                listing=_listing("k1", 10000),
            ),
            self.service.add_observation(
                run=run,
                item=item,
                source=source,
                listing=_listing("k2", 20000),
            ),
            self.service.add_observation(
                run=run,
                item=item,
                source=source,
                listing=_listing("k3", 90000),
            ),
        ]

        snapshot = self.service.calculate_snapshot(
            item=item,
            source=source,
            snapshot_date=date(2026, 6, 20),
            observations=observations,
        )

        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(snapshot["min_price"], Decimal("10000"))
        self.assertEqual(snapshot["max_price"], Decimal("90000"))
        self.assertEqual(snapshot["median_price"], Decimal("20000"))


def _write_sample_run(root: Path, *, run_id: str = "run1", lenovo_median: int = 30000) -> Path:
    run_dir = root / run_id
    lenovo_dir = run_dir / "lenovo_t14"
    dell_dir = run_dir / "dell_r740"
    lenovo_dir.mkdir(parents=True)
    dell_dir.mkdir(parents=True)

    _write_json(
        run_dir / "run_report.json",
        {
            "run_id": run_id,
            "started_at": "2026-06-20T08:00:00Z",
            "finished_at": "2026-06-20T08:01:00Z",
            "status": "partial_success",
            "jobs_total": 2,
            "jobs_success": 1,
            "jobs_blocked": 1,
            "jobs_failed": 0,
            "job_reports": [
                {
                    "job_code": "lenovo_t14",
                    "status": "success",
                    "http_status": 200,
                    "items_found": 2,
                    "items_normalized": 2,
                    "items_relevant": 2,
                    "items_unknown": 0,
                    "items_rejected": 0,
                    "fetched_at": "2026-06-20T08:00:10Z",
                },
                {
                    "job_code": "dell_r740",
                    "status": "blocked",
                    "block_reason": "http_403",
                    "http_status": 403,
                    "items_found": 0,
                    "items_relevant": 0,
                    "fetched_at": "2026-06-20T08:00:20Z",
                },
            ],
        },
    )
    _write_json(
        lenovo_dir / "daily_snapshot.json",
        {
            "job_code": "lenovo_t14",
            "position_name": "Lenovo ThinkPad T14",
            "snapshot_date": "2026-06-20",
            "source": "avito",
            "status": "success",
            "raw_count": 2,
            "normalized_count": 2,
            "relevant_count": 2,
            "unknown_count": 0,
            "rejected_count": 0,
            "min_price": 25000,
            "max_price": 35000,
            "median_price": lenovo_median,
            "currency": "RUB",
            "fetched_at": "2026-06-20T08:00:10Z",
        },
    )
    _write_json(
        lenovo_dir / "relevant_listings.json",
        [_listing("a1", 25000), _listing("a2", 35000)],
    )
    _write_json(
        dell_dir / "job_report.json",
        {
            "job_code": "dell_r740",
            "status": "blocked",
            "block_reason": "http_403",
            "http_status": 403,
            "items_found": 0,
            "items_relevant": 0,
            "fetched_at": "2026-06-20T08:00:20Z",
        },
    )
    return run_dir


def _listing(external_id: str, price: int) -> dict:
    return {
        "source": "avito",
        "job_code": "lenovo_t14",
        "external_id": external_id,
        "title": f"Listing {external_id}",
        "description": "Working equipment",
        "price": price,
        "currency": "RUB",
        "url": f"https://www.avito.ru/item/{external_id}",
        "location": "Москва",
        "published_at": "2026-06-19T08:00:00Z",
        "fetched_at": "2026-06-20T08:00:10Z",
        "relevance_status": "relevant",
        "reject_reasons": [],
        "raw_payload": {"id": external_id},
    }


def _write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
