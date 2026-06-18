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


class WorkerConfigValidationTest(unittest.TestCase):
    def test_valid_config_passes_without_network(self) -> None:
        config = {
            "request_delay_seconds": 5,
            "timeout_seconds": 20,
            "jobs": [
                {
                    "code": "job1",
                    "position_name": "Job 1",
                    "source": "avito",
                    "search_url": "https://www.avito.ru/all?q=Job+1",
                    "required_terms": ["job"],
                    "negative_terms": ["запчасти"],
                    "price_min": 1,
                    "price_max": 100,
                }
            ],
        }

        is_valid, errors, summary = worker.validate_config(config)

        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
        self.assertEqual(summary["job_codes"], ["job1"])

    def test_invalid_config_reports_errors(self) -> None:
        config = {
            "jobs": [
                {
                    "code": "job1",
                    "position_name": "Job 1",
                    "source": "avito",
                    "search_url": "http://example.com/no-query",
                    "required_terms": "job",
                    "negative_terms": [],
                    "price_min": 100,
                    "price_max": 1,
                },
                {
                    "code": "job1",
                    "position_name": "Job 2",
                    "source": "avito",
                    "search_url": "https://www.avito.ru/all?q=Job+2",
                    "required_terms": [],
                    "negative_terms": [],
                    "price_min": 1,
                    "price_max": 100,
                },
            ]
        }

        is_valid, errors, _summary = worker.validate_config(config)

        self.assertFalse(is_valid)
        self.assertIn("jobs[0].search_url must use https", errors)
        self.assertIn("jobs[0].search_url must point to www.avito.ru", errors)
        self.assertIn("jobs[0].search_url must include a query string", errors)
        self.assertIn("jobs[0].required_terms must be a list of strings", errors)
        self.assertIn("jobs[0].price_min must be lower than price_max", errors)
        self.assertIn("jobs[1].code is duplicated: job1", errors)


class WorkerMarkdownReportTest(unittest.TestCase):
    def test_render_markdown_report_includes_summary_table_and_reasons(self) -> None:
        analysis = {
            "run_id": "run1",
            "status": "partial_success",
            "started_at": "2026-06-18T00:00:00Z",
            "finished_at": "2026-06-18T00:00:01Z",
            "jobs_total": 1,
            "jobs": [
                {
                    "job_code": "lenovo_t14",
                    "status": "success",
                    "http_status": 200,
                    "raw_count": 50,
                    "normalized_count": 50,
                    "relevant_count": 30,
                    "unknown_count": 0,
                    "rejected_count": 20,
                    "min_price": 16990,
                    "max_price": 99000,
                    "median_price": 29450.0,
                    "html_findings": [],
                    "rejected_reason_counts": {"negative_term:экран": 7},
                    "unknown_reason_counts": {},
                }
            ],
        }

        markdown = worker.render_markdown_report(analysis)

        self.assertIn("# Price Monitoring Run Report: run1", markdown)
        self.assertIn("| `lenovo_t14` | 200 | `success` | 50 | 50 | 30 | 0 | 20 |", markdown)
        self.assertIn("- `negative_term:экран`: 7", markdown)


class WorkerEnduranceDocTest(unittest.TestCase):
    def test_render_endurance_doc_includes_decision_and_observations(self) -> None:
        analysis = {
            "run_id": "run2",
            "status": "partial_success",
            "started_at": "2026-06-19T00:00:00Z",
            "finished_at": "2026-06-19T00:00:10Z",
            "jobs_total": 1,
            "jobs": [
                {
                    "job_code": "kyocera_m2040dn",
                    "status": "blocked",
                    "http_status": 403,
                    "block_reason": "http_403",
                    "error": None,
                    "raw_count": 0,
                    "normalized_count": 0,
                    "relevant_count": 0,
                    "unknown_count": 0,
                    "rejected_count": 0,
                    "min_price": None,
                    "max_price": None,
                    "median_price": None,
                    "html_findings": ["access_restricted_ip"],
                    "rejected_reason_counts": {},
                    "unknown_reason_counts": {},
                }
            ],
        }

        markdown = worker.render_endurance_doc(
            analysis,
            day="2",
            date="2026-06-19",
            decision="hold_http_unstable_candidate",
            next_action="Не делать повторный запуск.",
        )

        self.assertIn("# Endurance Test Оценщика: День 2", markdown)
        self.assertIn("| `kyocera_m2040dn` | 403 | `blocked` |", markdown)
        self.assertIn("hold_http_unstable_candidate", markdown)
        self.assertIn("Не делать повторный запуск.", markdown)


class WorkerLiveRunGuardTest(unittest.TestCase):
    def test_live_run_exists_for_date_ignores_offline_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            offline_dir = runs_dir / "20260618T010000Z_offline"
            offline_dir.mkdir()
            (offline_dir / "run_report.json").write_text(
                json.dumps(
                    {
                        "run_id": "20260618T010000Z_offline",
                        "started_at": "2026-06-18T01:00:00Z",
                        "status": "success",
                    }
                ),
                encoding="utf-8",
            )

            run_exists, existing_run = worker.live_run_exists_for_date(runs_dir, "2026-06-18")

        self.assertFalse(run_exists)
        self.assertIsNone(existing_run)

    def test_live_run_exists_for_date_detects_live_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            live_dir = runs_dir / "20260618T010000Z"
            live_dir.mkdir()
            (live_dir / "run_report.json").write_text(
                json.dumps(
                    {
                        "run_id": "20260618T010000Z",
                        "started_at": "2026-06-18T01:00:00Z",
                        "status": "partial_success",
                    }
                ),
                encoding="utf-8",
            )

            run_exists, existing_run = worker.live_run_exists_for_date(runs_dir, "2026-06-18")

        self.assertTrue(run_exists)
        self.assertIsNotNone(existing_run)
        assert existing_run is not None
        self.assertEqual(existing_run["run_id"], "20260618T010000Z")
        self.assertEqual(existing_run["status"], "partial_success")


if __name__ == "__main__":
    unittest.main()
