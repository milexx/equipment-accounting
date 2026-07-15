import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.api import pricing


class PricingEvidenceApiTest(unittest.TestCase):
    def test_load_evidence_bundle_builds_artifact_links(self) -> None:
        original_runs_dir = pricing.PRICING_RUNS_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                runs_dir = Path(tmp)
                pricing.PRICING_RUNS_DIR = runs_dir
                evidence_dir = runs_dir / "run123" / "evidence" / "lenovo_t14"
                evidence_dir.mkdir(parents=True)
                (evidence_dir / "manifest.json").write_text(
                    """
{
  "run_id": "run123",
  "job_code": "lenovo_t14",
  "position_name": "Lenovo ThinkPad T14",
  "source": "avito",
  "snapshot_date": "2026-06-30",
  "fetched_at": "2026-06-30T08:00:00Z",
  "status": "success",
  "artifacts": [
    {"kind": "search_html", "format": "html", "path": "evidence/lenovo_t14/search_result.html"},
    {"kind": "search_json", "format": "json", "path": "evidence/lenovo_t14/search_result.json"}
  ]
}
""".strip(),
                    encoding="utf-8",
                )

                bundle = pricing.load_evidence_bundle("run123", "lenovo_t14")

            self.assertIsNotNone(bundle)
            assert bundle is not None
            self.assertEqual(bundle.run_id, "run123")
            self.assertEqual(bundle.snapshot_date, "2026-06-30")
            self.assertEqual(
                [artifact.label for artifact in bundle.artifacts],
                ["Ссылки"],
            )
            self.assertEqual(
                [artifact.url for artifact in bundle.artifacts],
                [
                    "/pricing/evidence/run123/lenovo_t14/search_result.html",
                ],
            )
        finally:
            pricing.PRICING_RUNS_DIR = original_runs_dir

    def test_build_chart_ignores_low_sample_points_for_main_graph(self) -> None:
        item = SimpleNamespace(code="lenovo_t14", name="Lenovo ThinkPad T14")
        source = SimpleNamespace(code="youla")
        run1 = SimpleNamespace(external_run_id="run1")
        run2 = SimpleNamespace(external_run_id="run2")
        snapshots = [
            SimpleNamespace(
                monitored_item=item,
                source=source,
                scrape_run=run1,
                snapshot_date=__import__("datetime").date(2026, 6, 29),
                status=pricing.PriceJobStatus.low_sample,
                min_price=45000,
                median_price=45000,
                max_price=45000,
            ),
            SimpleNamespace(
                monitored_item=item,
                source=source,
                scrape_run=run2,
                snapshot_date=__import__("datetime").date(2026, 6, 30),
                status=pricing.PriceJobStatus.success,
                min_price=25000,
                median_price=30000,
                max_price=35000,
            ),
        ]

        chart = pricing.build_chart(snapshots)

        self.assertEqual(len(chart.points), 1)
        self.assertEqual(chart.points[0].run_id, "run2")
        self.assertEqual(chart.latest_status, "success")

    def test_render_safe_evidence_html_removes_external_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "search_result.html"
            path.write_text(
                """
<html>
  <head>
    <link rel="stylesheet" href="https://www.avito.st/app.css">
    <script src="https://www.avito.st/app.js"></script>
  </head>
  <body>
    <img src="https://www.avito.st/image.jpg">
    <a href="https://www.avito.ru/item/1">open</a>
    <div onclick="alert(1)">content</div>
  </body>
</html>
""".strip(),
                encoding="utf-8",
            )

            rendered = pricing.render_safe_evidence_html(
                path, {"source": "avito", "fetched_at": "2026-06-30T08:00:00Z"}
            )

        self.assertIn("Это результат мониторинга цен avito по состоянию на 2026-06-30 08:00.", rendered)
        self.assertNotIn("<script", rendered)
        self.assertNotIn("https://www.avito.st/app.css", rendered)
        self.assertNotIn("https://www.avito.st/image.jpg", rendered)
        self.assertNotIn('href="https://www.avito.ru/item/1"', rendered)
        self.assertNotIn("onclick=", rendered)

    def test_render_evidence_html_preview_prefers_structured_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            evidence_dir = run_dir / "evidence" / "lenovo_t14"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "search_result.html").write_text("<html><body></body></html>", encoding="utf-8")
            (evidence_dir / "search_result.json").write_text(
                """
{
  "catalog": {
    "items": [
      {
        "title": "Lenovo ThinkPad T14",
        "urlPath": "/moskva/noutbuki/lenovo_t14",
        "priceDetailed": {"fullString": "45 000 ₽"},
        "location": {"name": "Москва"}
      },
      {
        "title": "Lenovo ThinkPad T14 Gen 2",
        "urlPath": "/moskva/noutbuki/lenovo_t14_gen2",
        "priceDetailed": {"fullString": "55 000 ₽"},
        "location": {"name": "Москва"}
      },
      {
        "title": "Картридж для Lenovo",
        "urlPath": "/moskva/kompyutery/kartridzh_lenovo",
        "priceDetailed": {"fullString": "1 000 ₽"},
        "location": {"name": "Москва"}
      }
    ]
  }
}
""".strip(),
                encoding="utf-8",
            )
            (run_dir / "lenovo_t14").mkdir(parents=True)
            (run_dir / "lenovo_t14" / "relevant_listings.json").write_text(
                """
[
  {
    "title": "Lenovo ThinkPad T14",
    "price": 45000,
    "url": "https://www.avito.ru/moskva/noutbuki/lenovo_t14"
  },
  {
    "title": "Lenovo ThinkPad T14 Gen 2",
    "price": 55000,
    "url": "https://www.avito.ru/moskva/noutbuki/lenovo_t14_gen2"
  }
]
""".strip(),
                encoding="utf-8",
            )

            rendered = pricing.render_evidence_html_preview(
                evidence_dir,
                evidence_dir / "search_result.html",
                {"source": "avito", "fetched_at": "2026-06-30T08:00:00Z"},
            )

        self.assertIn("Это результат мониторинга цен avito по состоянию на 2026-06-30 08:00.", rendered)
        self.assertIn("Lenovo ThinkPad T14", rendered)
        self.assertIn("45 000 ₽", rendered)
        self.assertIn("https://www.avito.ru/moskva/noutbuki/lenovo_t14", rendered)
        self.assertIn("Lenovo ThinkPad T14 Gen 2", rendered)
        self.assertIn("MIN", rendered)
        self.assertIn("MEDIAN", rendered)
        self.assertIn("MAX", rendered)
        self.assertIn("минимальная цена выборки", rendered)
        self.assertNotIn("Картридж для Lenovo", rendered)
        self.assertIn(".preview-badge-median{background:#dcfce7;color:#166534;}", rendered)
        card_codes = re.findall(r"preview-badge-[^>]+>(MIN|MEDIAN|MAX)</span>", rendered)
        self.assertEqual(card_codes[:3], ["MIN", "MEDIAN", "MAX"])

    def test_build_preview_highlight_map_marks_min_median_max(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            evidence_dir = run_dir / "evidence" / "lenovo_t14"
            evidence_dir.mkdir(parents=True)
            (run_dir / "lenovo_t14").mkdir(parents=True)
            (run_dir / "lenovo_t14" / "relevant_listings.json").write_text(
                """
[
  {"price": 20000, "url": "u1"},
  {"price": 30000, "url": "u2"},
  {"price": 40000, "url": "u3"}
]
""".strip(),
                encoding="utf-8",
            )

            highlight_map = pricing.build_preview_highlight_map(evidence_dir)

        self.assertEqual(highlight_map["u1"], ["MIN"])
        self.assertEqual(highlight_map["u2"], ["MEDIAN"])
        self.assertEqual(highlight_map["u3"], ["MAX"])

    def test_build_preview_highlight_map_uses_upper_median_for_even_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            evidence_dir = run_dir / "evidence" / "hp_m426"
            evidence_dir.mkdir(parents=True)
            (run_dir / "hp_m426").mkdir(parents=True)
            (run_dir / "hp_m426" / "relevant_listings.json").write_text(
                """
[
  {"price": 19900, "url": "u1"},
  {"price": 20000, "url": "u2"},
  {"price": 22000, "url": "u3"},
  {"price": 30000, "url": "u4"}
]
""".strip(),
                encoding="utf-8",
            )

            highlight_map = pricing.build_preview_highlight_map(evidence_dir)

        self.assertEqual(highlight_map["u3"], ["MEDIAN"])
