import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


WORKER_PATH = Path(__file__).resolve().parents[1] / "src" / "worker.py"
SPEC = importlib.util.spec_from_file_location("worker", WORKER_PATH)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(worker)


class WorkerClassificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.job = {
            "code": "lenovo_t14",
            "position_name": "Lenovo ThinkPad T14",
            "required_terms": ["thinkpad", "t14"],
            "negative_terms": ["экран", "плата", "ремонт"],
            "price_min": 10000,
            "price_max": 150000,
        }

    def test_relevant_listing(self) -> None:
        listing = {
            "title": "Lenovo ThinkPad T14 i5 16GB",
            "description": "Рабочий ноутбук без дефектов",
            "price": 30000,
        }

        status, reasons = worker.classify_listing(listing, self.job)

        self.assertEqual(status, "relevant")
        self.assertEqual(reasons, [])

    def test_negative_term_rejects_listing(self) -> None:
        listing = {
            "title": "Экран Lenovo ThinkPad T14",
            "description": "Запчасть для ремонта",
            "price": 12000,
        }

        status, reasons = worker.classify_listing(listing, self.job)

        self.assertEqual(status, "rejected")
        self.assertIn("negative_term:экран", reasons)

    def test_low_price_marks_unknown_when_required_terms_match(self) -> None:
        listing = {
            "title": "Lenovo ThinkPad T14",
            "description": "Рабочий ноутбук",
            "price": 5000,
        }

        status, reasons = worker.classify_listing(listing, self.job)

        self.assertEqual(status, "unknown")
        self.assertEqual(reasons, ["price_below_min"])

    def test_missing_required_rejects_listing(self) -> None:
        listing = {
            "title": "Lenovo ThinkPad X1 Carbon",
            "description": "Рабочий ноутбук",
            "price": 40000,
        }

        status, reasons = worker.classify_listing(listing, self.job)

        self.assertEqual(status, "rejected")
        self.assertIn("missing_required:t14", reasons)


class WorkerPageProblemTest(unittest.TestCase):
    def test_detects_nbsp_page_not_found(self) -> None:
        has_problem, reason = worker.detect_page_problem("Такой страницы не\xa0существует", {})

        self.assertTrue(has_problem)
        self.assertEqual(reason, "page_not_found")

    def test_detects_state_404_page_not_found(self) -> None:
        has_problem, reason = worker.detect_page_problem("", {"status": {"code": 404}})

        self.assertTrue(has_problem)
        self.assertEqual(reason, "page_not_found")

    def test_detects_blocked_ip_text(self) -> None:
        is_blocked, reason = worker.is_blocked(200, "Доступ ограничен: проблема с IP")

        self.assertTrue(is_blocked)
        self.assertEqual(reason, "access_restricted")


class WorkerSnapshotTest(unittest.TestCase):
    def test_snapshot_uses_relevant_prices_only(self) -> None:
        job = {"code": "test", "position_name": "Test"}
        classified = [
            {"price": 100, "relevance_status": "relevant"},
            {"price": 300, "relevance_status": "relevant"},
            {"price": 1, "relevance_status": "unknown"},
            {"price": 999, "relevance_status": "rejected"},
        ]
        relevant = classified[:2]

        snapshot = worker.calculate_snapshot(job, 4, classified, relevant, "2026-06-18T00:00:00Z")

        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(snapshot["min_price"], 100)
        self.assertEqual(snapshot["max_price"], 300)
        self.assertEqual(snapshot["median_price"], 200.0)
        self.assertEqual(snapshot["unknown_count"], 1)
        self.assertEqual(snapshot["rejected_count"], 1)

    def test_snapshot_records_no_data_explicitly(self) -> None:
        job = {"code": "test", "position_name": "Test"}

        snapshot = worker.calculate_snapshot(job, 0, [], [], "2026-06-18T00:00:00Z")

        self.assertEqual(snapshot["status"], "no_data")
        self.assertIsNone(snapshot["min_price"])
        self.assertIsNone(snapshot["max_price"])
        self.assertIsNone(snapshot["median_price"])


class WorkerAnalyzeRunTest(unittest.TestCase):
    def test_analyze_run_reports_html_findings_and_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            job_dir = run_dir / "job1"
            raw_dir = job_dir / "raw_pages"
            raw_dir.mkdir(parents=True)
            (run_dir / "run_report.json").write_text(
                json.dumps({"run_id": "run", "status": "partial_success", "jobs_total": 1}),
                encoding="utf-8",
            )
            (job_dir / "job_report.json").write_text(
                json.dumps({"status": "success", "http_status": 200}),
                encoding="utf-8",
            )
            (job_dir / "daily_snapshot.json").write_text(
                json.dumps(
                    {
                        "raw_count": 1,
                        "normalized_count": 1,
                        "relevant_count": 0,
                        "unknown_count": 0,
                        "rejected_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            (job_dir / "rejected_listings.json").write_text(
                json.dumps([{"reject_reasons": ["negative_term:экран"]}]),
                encoding="utf-8",
            )
            (job_dir / "unknown_listings.json").write_text("[]", encoding="utf-8")
            (raw_dir / "page_1.html").write_text("Такой страницы не\xa0существует", encoding="utf-8")

            report = worker.analyze_run(run_dir)

        self.assertEqual(report["run_id"], "run")
        self.assertEqual(report["jobs"][0]["html_findings"], ["page_not_found"])
        self.assertEqual(report["jobs"][0]["rejected_reason_counts"], {"negative_term:экран": 1})


if __name__ == "__main__":
    unittest.main()
