import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def test_snapshot_can_record_fallback_source(self) -> None:
        job = {"code": "test", "position_name": "Test"}

        snapshot = worker.calculate_snapshot(
            job,
            1,
            [{"price": 100, "relevance_status": "relevant"}],
            [{"price": 100, "relevance_status": "relevant"}],
            "2026-06-18T00:00:00Z",
            source="youla",
        )

        self.assertEqual(snapshot["source"], "youla")


class WorkerPrimaryRequestProfileTest(unittest.TestCase):
    def test_primary_request_profile_defaults_to_fixed_fingerprint(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            impersonate, user_agent = worker.primary_request_profile()

        self.assertEqual(impersonate, "safari")
        self.assertEqual(user_agent, worker.PRIMARY_USER_AGENTS["safari"])

    def test_primary_request_profile_honors_env_override(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AVITO_PRIMARY_IMPERSONATE": "chrome",
                "AVITO_PRIMARY_USER_AGENT": "test-agent",
            },
            clear=True,
        ):
            impersonate, user_agent = worker.primary_request_profile()

        self.assertEqual(impersonate, "chrome")
        self.assertEqual(user_agent, "test-agent")


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
                        "source": "youla",
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
        self.assertEqual(report["jobs"][0]["source"], "youla")
        self.assertEqual(report["jobs"][0]["html_findings"], ["page_not_found"])
        self.assertEqual(report["jobs"][0]["rejected_reason_counts"], {"negative_term:экран": 1})

    def test_analyze_run_includes_block_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            job_dir = run_dir / "job1"
            job_dir.mkdir(parents=True)
            (run_dir / "run_report.json").write_text(
                json.dumps({"run_id": "run", "status": "partial_success", "jobs_total": 1}),
                encoding="utf-8",
            )
            (job_dir / "job_report.json").write_text(
                json.dumps({"status": "blocked", "block_diagnostic": {"status": "success"}}),
                encoding="utf-8",
            )

            report = worker.analyze_run(run_dir)

        self.assertEqual(report["jobs"][0]["block_diagnostic"]["status"], "success")


class WorkerBlockDiagnosticTest(unittest.TestCase):
    def test_run_block_diagnostic_executes_configured_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job1"
            job_dir.mkdir()
            job = {
                "code": "job1",
                "search_url": "https://www.avito.ru/all?q=Job+1",
            }
            diagnostic = {
                "enabled": True,
                "timeout_seconds": 10,
                "command": [
                    sys.executable,
                    "-c",
                    "import os; print('probe ' + os.environ['AVITO_DIAGNOSTIC_JOB_CODE'])",
                ],
            }

            result = worker.run_block_diagnostic(job, job_dir, diagnostic)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "success")
        self.assertIn("probe job1", result["stdout_tail"])

    def test_process_html_runs_block_diagnostic_on_403(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job1"
            job = {
                "code": "job1",
                "search_url": "https://www.avito.ru/all?q=Job+1",
            }
            diagnostic = {
                "enabled": True,
                "timeout_seconds": 10,
                "command": [
                    sys.executable,
                    "-c",
                    "print('diagnostic ok')",
                ],
            }

            report = worker.process_html(
                job,
                "2026-06-21T00:00:00Z",
                job_dir,
                403,
                {},
                "blocked",
                diagnostic,
                {"impersonate": "chrome", "headers": {"user-agent": "test-agent"}},
            )

            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["block_diagnostic"]["status"], "success")
            self.assertTrue((job_dir / "block_diagnostic.json").exists())
            response_meta = json.loads((job_dir / "response_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(response_meta["request"]["impersonate"], "chrome")
            self.assertEqual(response_meta["request"]["headers"]["user-agent"], "test-agent")

    def test_format_diagnostic_command_accepts_relative_job_dir(self) -> None:
        job = {"code": "job1", "search_url": "https://www.avito.ru/all?q=Job+1"}
        command = ["probe", "--job-dir", "{job_dir}", "--url", "{search_url}"]

        rendered = worker.format_diagnostic_command(command, job, Path("runs/run1/job1"))

        self.assertEqual(rendered[2], "runs/run1/job1")


class Duff89ProbePathTest(unittest.TestCase):
    def test_probe_resolves_job_dir_before_chdir(self) -> None:
        probe_path = Path(__file__).resolve().parents[1] / "scripts" / "duff89_probe.py"
        spec = importlib.util.spec_from_file_location("duff89_probe", probe_path)
        probe = importlib.util.module_from_spec(spec)
        assert spec is not None
        assert spec.loader is not None
        spec.loader.exec_module(probe)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            job_dir = root / "job"
            job_dir.mkdir()

            class FakeParser:
                def __init__(self, _config):
                    self.good_request_count = 1
                    self.bad_request_count = 0

                def parse(self):
                    return None

            fake_dto = type(sys)("dto")
            fake_dto.AvitoConfig = lambda **kwargs: kwargs
            fake_parser_cls = type(sys)("parser_cls")
            fake_parser_cls.AvitoParse = FakeParser
            argv = [
                "duff89_probe.py",
                "--repo",
                str(repo),
                "--url",
                "https://www.avito.ru/all?q=Job+1",
                "--job-code",
                "job1",
                "--job-dir",
                str(job_dir.relative_to(root)),
            ]

            with patch.object(sys, "argv", argv), patch.dict(
                sys.modules,
                {"dto": fake_dto, "parser_cls": fake_parser_cls},
            ), patch.object(probe, "read_xlsx_listings", return_value=[{"title": "Job"}]):
                current = Path.cwd()
                try:
                    os.chdir(root)
                    exit_code = probe.main()
                finally:
                    os.chdir(current)

            output = job_dir / "duff89_normalized_listings.json"
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.exists())


class WorkerFallbackChainTest(unittest.TestCase):
    def test_normalize_youla_item_converts_kopecks_to_rubles(self) -> None:
        item = {
            "product": {
                "id": "1",
                "name": "Lenovo ThinkPad T14",
                "price": {"realPrice": {"price": 4500000}, "realPriceText": "45 000 ₽"},
                "url": "/moskva/test",
                "location": {"cityName": "Москва"},
            }
        }

        listing = worker.normalize_youla_item(item)

        self.assertIsNotNone(listing)
        assert listing is not None
        self.assertEqual(listing["source"], "youla")
        self.assertEqual(listing["price"], 45000)
        self.assertEqual(listing["url"], "https://youla.ru/moskva/test")

    def test_duff89_fallback_builds_success_snapshot_from_probe_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job1"
            job_dir.mkdir()
            job = {
                "code": "job1",
                "position_name": "Lenovo ThinkPad T14",
                "search_url": "https://www.avito.ru/all?q=Lenovo+ThinkPad+T14",
                "required_terms": ["thinkpad", "t14"],
                "negative_terms": [],
                "price_min": 10000,
                "price_max": 150000,
            }
            (job_dir / "duff89_normalized_listings.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "source": "avito_duff89",
                                "title": "Lenovo ThinkPad T14",
                                "description": "Рабочий ноутбук",
                                "price": 45000,
                                "currency": "RUB",
                                "url": "https://www.avito.ru/item",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            report = worker.try_duff89_fallback(
                job,
                "2026-06-21T00:00:00Z",
                job_dir,
                None,
                {"status": "blocked", "http_status": 403, "block_diagnostic": {"status": "success"}},
            )

        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["source"], "avito_duff89")
        self.assertEqual(report["items_relevant"], 1)


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


class WorkerPreflightTest(unittest.TestCase):
    def valid_config_path(self, root: Path) -> Path:
        config_path = root / "search_jobs.json"
        config_path.write_text(
            json.dumps(
                {
                    "request_delay_seconds": 5,
                    "timeout_seconds": 20,
                    "jobs": [
                        {
                            "code": "job1",
                            "position_name": "Job 1",
                            "source": "avito",
                            "search_url": "https://www.avito.ru/all?q=Job+1",
                            "required_terms": ["job"],
                            "negative_terms": [],
                            "price_min": 1,
                            "price_max": 100,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return config_path

    def test_preflight_ready_without_same_day_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self.valid_config_path(root)
            runs_dir = root / "runs"
            runs_dir.mkdir()

            exit_code, payload = worker.build_preflight(config_path, runs_dir)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["config"]["valid"])

    def test_preflight_blocks_same_day_live_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self.valid_config_path(root)
            runs_dir = root / "runs"
            today = worker.utc_now().date().isoformat()
            run_dir = runs_dir / f"{today.replace('-', '')}T010000Z"
            run_dir.mkdir(parents=True)
            (run_dir / "run_report.json").write_text(
                json.dumps(
                    {
                        "run_id": run_dir.name,
                        "started_at": f"{today}T01:00:00Z",
                        "status": "partial_success",
                    }
                ),
                encoding="utf-8",
            )

            exit_code, payload = worker.build_preflight(config_path, runs_dir)

        self.assertEqual(exit_code, 3)
        self.assertEqual(payload["status"], "blocked_by_same_day_guard")
        self.assertTrue(payload["same_day_guard"]["live_run_exists"])


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
                    "source": "avito_duff89",
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
        self.assertIn("| `lenovo_t14` | `avito_duff89` | 200 | `success` | 50 | 50 | 30 | 0 | 20 |", markdown)
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
                    "source": "avito",
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
        self.assertIn("| `kyocera_m2040dn` | `avito` | 403 | `blocked` |", markdown)
        self.assertIn("hold_http_unstable_candidate", markdown)
        self.assertIn("Не делать повторный запуск.", markdown)


class WorkerGateSummaryTest(unittest.TestCase):
    def test_render_gate_summary_recommends_continue_with_one_run(self) -> None:
        summary = {
            "runs_seen_total": 1,
            "runs_total": 1,
            "runs_excluded": 0,
            "runs_with_two_successes": 0,
            "runs_with_majority_blocked_or_failed": 0,
            "recommendation": "continue_endurance",
            "runs": [
                {
                    "run_id": "run1",
                    "started_at": "2026-06-18T00:00:00Z",
                    "status": "partial_success",
                    "jobs": [
                        {"status": "success"},
                        {"status": "blocked"},
                        {"status": "no_data"},
                    ],
                }
            ],
            "excluded_runs": [],
            "job_totals": {
                "lenovo_t14": {"success": 1},
                "kyocera_m2040dn": {"blocked": 1},
            },
        }

        markdown = worker.render_gate_summary(summary)

        self.assertIn("Recommendation: `continue_endurance`.", markdown)
        self.assertIn("| `run1` | 2026-06-18T00:00:00Z | `partial_success` | 1 | 1 | 0 |", markdown)
        self.assertIn("- `lenovo_t14`: `success`: 1", markdown)

    def test_summarize_gate_recommends_hold_when_failures_dominate_two_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            for index in [1, 2]:
                run_dir = runs_dir / f"2026061{index}T010000Z"
                run_dir.mkdir()
                (run_dir / "run_report.json").write_text(
                    json.dumps(
                        {
                            "run_id": run_dir.name,
                            "started_at": f"2026-06-1{index}T01:00:00Z",
                            "status": "partial_success",
                        }
                    ),
                    encoding="utf-8",
                )
                for job_code, status in [
                    ("job_a", "blocked"),
                    ("job_b", "parser_error"),
                    ("job_c", "success"),
                ]:
                    job_dir = run_dir / job_code
                    job_dir.mkdir()
                    (job_dir / "job_report.json").write_text(
                        json.dumps({"status": status}),
                        encoding="utf-8",
                    )

            summary = worker.summarize_gate(runs_dir)

        self.assertEqual(summary["recommendation"], "hold_http_unstable_candidate")
        self.assertEqual(summary["runs_total"], 2)
        self.assertEqual(summary["runs_with_majority_blocked_or_failed"], 2)

    def test_summarize_gate_excludes_infrastructure_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            infrastructure_run = runs_dir / "20260618T075301Z"
            infrastructure_run.mkdir()
            (infrastructure_run / "run_report.json").write_text(
                json.dumps(
                    {
                        "run_id": infrastructure_run.name,
                        "started_at": "2026-06-18T07:53:01Z",
                        "status": "partial_success",
                    }
                ),
                encoding="utf-8",
            )
            for job_code in ["job_a", "job_b", "job_c"]:
                job_dir = infrastructure_run / job_code
                job_dir.mkdir()
                (job_dir / "job_report.json").write_text(
                    json.dumps(
                        {
                            "status": "parser_error",
                            "error": "DNSError: Could not resolve host: www.avito.ru",
                        }
                    ),
                    encoding="utf-8",
                )

            for index, statuses in enumerate(
                [
                    ["success", "blocked", "no_data"],
                    ["success", "success", "success"],
                ],
                start=1,
            ):
                run_dir = runs_dir / f"2026061{index}T010000Z"
                run_dir.mkdir()
                (run_dir / "run_report.json").write_text(
                    json.dumps(
                        {
                            "run_id": run_dir.name,
                            "started_at": f"2026-06-1{index}T01:00:00Z",
                            "status": "success" if index == 2 else "partial_success",
                        }
                    ),
                    encoding="utf-8",
                )
                for job_index, status in enumerate(statuses):
                    job_dir = run_dir / f"job_{job_index}"
                    job_dir.mkdir()
                    (job_dir / "job_report.json").write_text(
                        json.dumps({"status": status, "http_status": 200}),
                        encoding="utf-8",
                    )

            summary = worker.summarize_gate(runs_dir)
            markdown = worker.render_gate_summary(summary)

        self.assertEqual(summary["runs_seen_total"], 3)
        self.assertEqual(summary["runs_total"], 2)
        self.assertEqual(summary["runs_excluded"], 1)
        self.assertEqual(summary["excluded_runs"][0]["run_id"], "20260618T075301Z")
        self.assertEqual(summary["recommendation"], "continue_endurance")
        self.assertIn("## Excluded Runs", markdown)
        self.assertIn("| `20260618T075301Z` | 2026-06-18T07:53:01Z | `partial_success` | `infrastructure_attempt` |", markdown)


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
