import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.provider import get_auth_provider, require_center
from app.database import get_db
from app.models.enums import PriceJobStatus
from app.models.pricing import DailyPriceSnapshot, MonitoredItem, PriceScrapeRun

router = APIRouter(prefix="/pricing", tags=["pricing"])
templates = Jinja2Templates(directory="app/templates")
PRICING_RUNS_DIR = Path("research/avito-monitor-worker-poc/runs")
MIN_AWARE_DATETIME = datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class PricingPoint:
    run_id: str
    date_label: str
    source_code: str
    status: str
    min_price: Decimal | None
    median_price: Decimal | None
    max_price: Decimal | None
    x: int
    y_min: int | None
    y_median: int | None
    y_max: int | None


@dataclass
class PricingChart:
    item_code: str
    item_name: str
    y_min_label: str
    y_max_label: str
    min_polyline: str
    median_polyline: str
    max_polyline: str
    points: list[PricingPoint]
    latest_status: str
    latest_source_code: str
    latest_date_label: str
    latest_run_id: str
    latest_success_date_label: str | None
    latest_success_median: Decimal | None
    latest_success_source_code: str | None


@dataclass
class PricingSummaryRow:
    item_code: str
    item_name: str
    detail_url: str
    latest_status: str
    latest_source_code: str
    latest_date_label: str
    latest_run_id: str
    latest_relevant_count: int
    latest_unknown_count: int
    latest_rejected_count: int
    snapshots_total: int
    success_snapshots_total: int
    latest_success_date_label: str | None
    latest_success_median: Decimal | None
    latest_success_min: Decimal | None
    latest_success_max: Decimal | None
    latest_success_source_code: str | None


@dataclass
class PricingOverview:
    items_total: int
    latest_runs_total: int
    success_items_total: int
    blocked_items_total: int
    latest_snapshot_date_label: str | None


@dataclass
class PricingEvidenceArtifact:
    label: str
    format: str
    url: str


@dataclass
class PricingEvidenceBundle:
    run_id: str
    item_code: str
    source: str
    snapshot_date: str | None
    fetched_at: str | None
    status: str
    artifacts: list[PricingEvidenceArtifact]


@router.get("", response_class=HTMLResponse)
def pricing_index(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    current_user = get_auth_provider().get_current_user(request, db)
    require_center(current_user)

    snapshots = db.scalars(
        select(DailyPriceSnapshot)
        .options(
            selectinload(DailyPriceSnapshot.monitored_item),
            selectinload(DailyPriceSnapshot.scrape_run),
            selectinload(DailyPriceSnapshot.source),
        )
        .join(DailyPriceSnapshot.monitored_item)
        .join(DailyPriceSnapshot.scrape_run)
        .order_by(MonitoredItem.code, DailyPriceSnapshot.snapshot_date, PriceScrapeRun.started_at)
    ).all()
    grouped = group_snapshots(snapshots)
    summary_rows = build_summary_rows(grouped)
    return templates.TemplateResponse(
        request,
        "pricing/index.html",
        {
            "overview": build_overview(summary_rows),
            "summary_rows": summary_rows,
            "format_price": format_price,
            "status_labels": {
                "success": "Успех",
                "low_sample": "Слабая выборка",
                "no_data": "Нет данных",
                "blocked": "Блокировка",
                "captcha": "CAPTCHA",
                "parser_error": "Ошибка",
            },
        },
    )


@router.get("/items/{item_code}", response_class=HTMLResponse)
def pricing_item_detail(
    item_code: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    current_user = get_auth_provider().get_current_user(request, db)
    require_center(current_user)

    snapshots = db.scalars(
        select(DailyPriceSnapshot)
        .options(
            selectinload(DailyPriceSnapshot.monitored_item),
            selectinload(DailyPriceSnapshot.scrape_run),
            selectinload(DailyPriceSnapshot.source),
        )
        .join(DailyPriceSnapshot.monitored_item)
        .join(DailyPriceSnapshot.scrape_run)
        .where(MonitoredItem.code == item_code)
        .order_by(DailyPriceSnapshot.snapshot_date, PriceScrapeRun.started_at)
    ).all()
    if not snapshots:
        raise HTTPException(status_code=404, detail="Pricing item not found")

    chart = build_chart(snapshots)
    evidence_by_run_id = build_evidence_index(snapshots)
    return templates.TemplateResponse(
        request,
        "pricing/detail.html",
        {
            "chart": chart,
            "snapshots": list(reversed(snapshots)),
            "evidence_by_run_id": evidence_by_run_id,
            "latest_evidence": evidence_by_run_id.get(chart.latest_run_id),
            "format_price": format_price,
            "status_labels": {
                "success": "Успех",
                "low_sample": "Слабая выборка",
                "no_data": "Нет данных",
                "blocked": "Блокировка",
                "captcha": "CAPTCHA",
                "parser_error": "Ошибка",
            },
        },
    )


@router.get("/evidence/{run_id}/{item_code}/{artifact_name}")
def pricing_evidence_artifact(
    run_id: str,
    item_code: str,
    artifact_name: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    current_user = get_auth_provider().get_current_user(request, db)
    require_center(current_user)

    evidence_dir = PRICING_RUNS_DIR / run_id / "evidence" / item_code
    manifest_path = evidence_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Evidence bundle not found")

    if artifact_name == "manifest.json":
        target_path = manifest_path
    else:
        manifest = _read_evidence_manifest(manifest_path)
        allowed_names = {
            Path(artifact.get("path", "")).name
            for artifact in manifest.get("artifacts", [])
            if isinstance(artifact, dict)
        }
        if artifact_name not in allowed_names:
            raise HTTPException(status_code=404, detail="Evidence artifact not found")
        target_path = evidence_dir / artifact_name

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="Evidence artifact file missing")
    if target_path.suffix.lower() == ".html":
        return HTMLResponse(render_evidence_html_preview(evidence_dir, target_path, manifest))
    return FileResponse(target_path)


def group_snapshots(
    snapshots: list[DailyPriceSnapshot],
) -> dict[int, list[DailyPriceSnapshot]]:
    grouped: dict[int, list[DailyPriceSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        grouped[snapshot.monitored_item_id].append(snapshot)
    for monitored_item_id, item_snapshots in grouped.items():
        grouped[monitored_item_id] = sorted(item_snapshots, key=snapshot_sort_key)
    return grouped


def build_evidence_index(
    snapshots: list[DailyPriceSnapshot],
) -> dict[str, PricingEvidenceBundle]:
    evidence_by_run_id: dict[str, PricingEvidenceBundle] = {}
    for snapshot in snapshots:
        run_id = snapshot.scrape_run.external_run_id
        if run_id in evidence_by_run_id:
            continue
        bundle = load_evidence_bundle(run_id, snapshot.monitored_item.code)
        if bundle is not None:
            evidence_by_run_id[run_id] = bundle
    return evidence_by_run_id


def snapshot_sort_key(snapshot: DailyPriceSnapshot) -> tuple:
    scrape_run_started_at = snapshot.scrape_run.started_at or MIN_AWARE_DATETIME
    db_freshness = snapshot.updated_at or snapshot.created_at or MIN_AWARE_DATETIME
    return (
        snapshot.snapshot_date,
        db_freshness,
        scrape_run_started_at,
        snapshot.id,
    )


def load_evidence_bundle(run_id: str, item_code: str) -> PricingEvidenceBundle | None:
    manifest_path = PRICING_RUNS_DIR / run_id / "evidence" / item_code / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = _read_evidence_manifest(manifest_path)
    artifacts = [
        PricingEvidenceArtifact(
            label=_artifact_label(artifact.get("kind"), artifact.get("format")),
            format=str(artifact.get("format") or "").upper(),
            url=f"/pricing/evidence/{run_id}/{item_code}/{Path(str(artifact.get('path') or '')).name}",
        )
        for artifact in manifest.get("artifacts", [])
        if isinstance(artifact, dict)
        and artifact.get("path")
        and artifact.get("kind") == "search_html"
    ]
    return PricingEvidenceBundle(
        run_id=run_id,
        item_code=item_code,
        source=str(manifest.get("source") or "avito"),
        snapshot_date=manifest.get("snapshot_date"),
        fetched_at=manifest.get("fetched_at"),
        status=str(manifest.get("status") or "unknown"),
        artifacts=artifacts,
    )


def _read_evidence_manifest(manifest_path: Path) -> dict[str, object]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _artifact_label(kind: str | None, fmt: str | None) -> str:
    if kind == "search_html":
        return "Ссылки"
    if kind == "search_json":
        return "JSON срез"
    return (fmt or "artifact").upper()


def render_evidence_html_preview(evidence_dir: Path, html_path: Path, manifest: dict[str, object]) -> str:
    json_path = evidence_dir / "search_result.json"
    if json_path.exists():
        preview = render_structured_evidence_preview(evidence_dir, json_path, manifest)
        if preview is not None:
            return preview
    return render_safe_evidence_html(html_path, manifest)


def render_structured_evidence_preview(
    evidence_dir: Path,
    json_path: Path,
    manifest: dict[str, object],
) -> str | None:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    items = extract_preview_items(payload)
    if not items:
        return None

    relevant_urls = load_relevant_preview_urls(evidence_dir)
    highlight_map = build_preview_highlight_map(evidence_dir)
    if relevant_urls:
        items = [item for item in items if str(item.get("url") or "") in relevant_urls]
        if not items:
            return None
    highlighted_rows: dict[str, str] = {}
    regular_rows: list[str] = []
    for item in items[:50]:
        title = escape(str(item.get("title") or "Без названия"))
        price = escape(str(item.get("price") or "-"))
        url = escape(str(item.get("url") or ""))
        location = escape(str(item.get("location") or "-"))
        highlights = highlight_map.get(str(item.get("url") or ""), [])
        badges = "".join(
            f"<span class='preview-badge preview-badge-{escape(code.lower())}'>{escape(code)}</span>"
            for code in highlights
        )
        note = ""
        if highlights:
            note = (
                "<div class='preview-note'>"
                + ", ".join(describe_highlight(code) for code in highlights)
                + "</div>"
            )
        card_html = (
            "<article class='preview-card'>"
            f"<div class='preview-badges'>{badges}</div>"
            f"<h3>{title}</h3>"
            f"<div class='preview-price'>{price}</div>"
            f"<div class='preview-meta'>Локация: {location}</div>"
            f"<div class='preview-meta'>URL: {url}</div>"
            f"{note}"
            "</article>"
        )
        if highlights:
            for code in highlights:
                highlighted_rows.setdefault(code, card_html)
        else:
            regular_rows.append(card_html)

    ordered_rows: list[str] = []
    seen_rows: set[str] = set()
    for code in ("MIN", "MEDIAN", "MAX"):
        row = highlighted_rows.get(code)
        if row and row not in seen_rows:
            ordered_rows.append(row)
            seen_rows.add(row)
    ordered_rows.extend(row for row in regular_rows if row not in seen_rows)

    reminder = build_monitoring_reminder(manifest)
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow'>"
        "<title>Offline preview</title>"
        "<style>"
        "body{margin:0;background:#f5f7fa;color:#13202b;font:14px/1.45 sans-serif;}"
        ".wrap{max-width:1200px;margin:0 auto;padding:16px;}"
        ".reminder{padding:10px 14px;margin:0 0 16px 0;"
        "background:#eef4fa;border:1px solid #cfdae6;border-radius:10px;color:#304254;}"
        ".grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));}"
        ".preview-card{padding:14px;border:1px solid #d8e0e8;border-radius:12px;background:#fff;position:relative;}"
        ".preview-badges{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 10px 0;}"
        ".preview-badge{display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.04em;}"
        ".preview-badge-min{background:#dbeafe;color:#1d4ed8;}"
        ".preview-badge-median{background:#dcfce7;color:#166534;}"
        ".preview-badge-max{background:#fef3c7;color:#b45309;}"
        ".preview-card h3{margin:0 0 8px 0;font-size:15px;line-height:1.35;}"
        ".preview-price{font-size:18px;font-weight:700;margin-bottom:8px;}"
        ".preview-meta{color:#52606d;word-break:break-word;}"
        ".preview-note{margin-top:10px;color:#304254;font-size:12px;font-weight:600;}"
        "</style></head><body><div class='wrap'>"
        f"<div class='reminder'>{escape(reminder)}</div>"
        f"<div class='grid'>{''.join(ordered_rows)}</div>"
        "</div></body></html>"
    )


def extract_preview_items(payload: dict) -> list[dict[str, str | int | None]]:
    catalog_items = ((payload.get("catalog") or {}).get("items") or [])
    if catalog_items:
        return [
            {
                "title": item.get("title"),
                "price": ((item.get("priceDetailed") or {}).get("fullString") or (item.get("priceDetailed") or {}).get("value")),
                "url": "https://www.avito.ru/" + str(item.get("urlPath") or "").lstrip("/"),
                "location": ((item.get("location") or {}).get("name") if isinstance(item.get("location"), dict) else None),
            }
            for item in catalog_items
            if isinstance(item, dict) and item.get("title") and item.get("urlPath")
        ]

    feed_items = (((payload.get("data") or {}).get("feed") or {}).get("items") or [])
    youla_items: list[dict[str, str | int | None]] = []
    for item in feed_items:
        if not isinstance(item, dict):
            continue
        product = item.get("product") or item.get("productPromoted")
        if not isinstance(product, dict):
            continue
        raw_price = (((product.get("price") or {}).get("realPrice") or {}).get("price"))
        price = int(raw_price / 100) if isinstance(raw_price, (int, float)) else None
        url = product.get("url")
        youla_items.append(
            {
                "title": product.get("name"),
                "price": price,
                "url": f"https://youla.ru{url}" if isinstance(url, str) and url.startswith("/") else url,
                "location": ((product.get("location") or {}).get("cityName") if isinstance(product.get("location"), dict) else None),
            }
        )
    return [item for item in youla_items if item.get("title") and item.get("url")]


def render_safe_evidence_html(path: Path, manifest: dict[str, object]) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<script\b[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<(?:iframe|object|embed|img|source|video|audio)\b[^>]*>.*?</(?:iframe|object|embed|video|audio)>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<(?:img|source)\b[^>]*?/?>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<link\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s(?:src|href|srcset|poster|data-src)\s*=\s*(['\"]).*?\1", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"\son[a-zA-Z-]+\s*=\s*(['\"]).*?\1", "", text, flags=re.IGNORECASE | re.DOTALL)

    head_injection = (
        '<meta name="robots" content="noindex,nofollow">'
        "<style>"
        "body{margin:0 auto;max-width:1280px;padding:16px;background:#f5f7fa;}"
        "*{animation:none!important;transition:none!important;}"
        "a{pointer-events:none;cursor:default;}"
        "</style>"
    )
    reminder = (
        '<div style="padding:10px 14px;margin:0 0 12px 0;'
        'background:#eef4fa;border:1px solid #cfdae6;border-radius:10px;color:#304254;'
        'font:14px/1.4 sans-serif;">'
        f"{escape(build_monitoring_reminder(manifest))}"
        "</div>"
    )

    if "</head>" in text:
        text = text.replace("</head>", head_injection + "</head>", 1)
    else:
        text = head_injection + text
    if "<body" in text:
        text = re.sub(r"(<body\b[^>]*>)", r"\1" + reminder, text, count=1, flags=re.IGNORECASE)
    else:
        text = reminder + text
    return text


def build_monitoring_reminder(manifest: dict[str, object]) -> str:
    source = str(manifest.get("source") or "unknown")
    fetched_at = format_preview_timestamp(
        manifest.get("fetched_at") or manifest.get("snapshot_date") or "unknown time"
    )
    return f"Это результат мониторинга цен {source} по состоянию на {fetched_at}."


def upper_median_price(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def build_preview_highlight_map(evidence_dir: Path) -> dict[str, list[str]]:
    relevant = load_relevant_preview_items(evidence_dir)
    listings = [item for item in relevant if isinstance(item, dict) and item.get("url") and item.get("price") is not None]
    if not listings:
        return {}

    prices = sorted(int(item["price"]) for item in listings)
    min_price = prices[0]
    max_price = prices[-1]
    median_price = upper_median_price(prices)
    median_listing = min(
        listings,
        key=lambda item: (int(item["price"]) != median_price, int(item["price"]), str(item.get("url"))),
    )

    highlights: dict[str, list[str]] = {}
    for item in listings:
        url = str(item["url"])
        codes: list[str] = []
        if int(item["price"]) == min_price:
            codes.append("MIN")
        if url == str(median_listing["url"]):
            codes.append("MEDIAN")
        if int(item["price"]) == max_price:
            codes.append("MAX")
        if codes:
            highlights[url] = codes
    return highlights


def load_relevant_preview_urls(evidence_dir: Path) -> set[str]:
    return {
        str(item.get("url"))
        for item in load_relevant_preview_items(evidence_dir)
        if isinstance(item, dict) and item.get("url")
    }


def load_relevant_preview_items(evidence_dir: Path) -> list[dict]:
    relevant_path = evidence_dir.parent.parent / evidence_dir.name / "relevant_listings.json"
    if not relevant_path.exists():
        return []
    payload = json.loads(relevant_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def describe_highlight(code: str) -> str:
    return {
        "MIN": "минимальная цена выборки",
        "MEDIAN": "медианный ориентир",
        "MAX": "максимальная цена выборки",
    }.get(code, code)


def format_preview_timestamp(value: object) -> str:
    text = str(value)
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text


def build_summary_rows(
    grouped: dict[int, list[DailyPriceSnapshot]],
) -> list[PricingSummaryRow]:
    rows: list[PricingSummaryRow] = []
    for item_snapshots in grouped.values():
        latest_snapshot = item_snapshots[-1]
        latest_success = next(
            (
                snapshot
                for snapshot in reversed(item_snapshots)
                if snapshot.status == PriceJobStatus.success and snapshot.median_price is not None
            ),
            None,
        )
        rows.append(
            PricingSummaryRow(
                item_code=item_snapshots[0].monitored_item.code,
                item_name=item_snapshots[0].monitored_item.name,
                detail_url=f"/pricing/items/{item_snapshots[0].monitored_item.code}",
                latest_status=latest_snapshot.status.value,
                latest_source_code=latest_snapshot.source.code,
                latest_date_label=latest_snapshot.snapshot_date.isoformat(),
                latest_run_id=latest_snapshot.scrape_run.external_run_id,
                latest_relevant_count=latest_snapshot.relevant_count,
                latest_unknown_count=latest_snapshot.unknown_count,
                latest_rejected_count=latest_snapshot.rejected_count,
                snapshots_total=len(item_snapshots),
                success_snapshots_total=sum(
                    1
                    for snapshot in item_snapshots
                    if snapshot.status == PriceJobStatus.success and snapshot.median_price is not None
                ),
                latest_success_date_label=latest_success.snapshot_date.isoformat()
                if latest_success
                else None,
                latest_success_median=latest_success.median_price if latest_success else None,
                latest_success_min=latest_success.min_price if latest_success else None,
                latest_success_max=latest_success.max_price if latest_success else None,
                latest_success_source_code=latest_success.source.code if latest_success else None,
            )
        )
    return sorted(rows, key=lambda row: row.item_name.lower())


def build_overview(summary_rows: list[PricingSummaryRow]) -> PricingOverview:
    latest_dates = [row.latest_date_label for row in summary_rows if row.latest_date_label]
    latest_runs = {row.latest_run_id for row in summary_rows}
    return PricingOverview(
        items_total=len(summary_rows),
        latest_runs_total=len(latest_runs),
        success_items_total=sum(1 for row in summary_rows if row.latest_status == "success"),
        blocked_items_total=sum(
            1
            for row in summary_rows
            if row.latest_status in {"low_sample", "blocked", "captcha", "parser_error"}
        ),
        latest_snapshot_date_label=max(latest_dates) if latest_dates else None,
    )


def build_chart(item_snapshots: list[DailyPriceSnapshot]) -> PricingChart:
    value_snapshots = [
        snapshot
        for snapshot in item_snapshots
        if snapshot.status == PriceJobStatus.success
        and (
            snapshot.min_price is not None
            or snapshot.median_price is not None
            or snapshot.max_price is not None
        )
    ]
    prices = [
        price
        for snapshot in value_snapshots
        for price in (snapshot.min_price, snapshot.median_price, snapshot.max_price)
        if price is not None
    ]
    min_price = min(prices) if prices else Decimal("0")
    max_price = max(prices) if prices else Decimal("1")
    if min_price == max_price:
        min_price -= Decimal("1")
        max_price += Decimal("1")

    points = [
        build_point(
            snapshot=snapshot,
            index=index,
            total=len(value_snapshots),
            min_price=min_price,
            max_price=max_price,
        )
        for index, snapshot in enumerate(value_snapshots)
    ]
    latest_snapshot = item_snapshots[-1]
    latest_success = next(
        (
            snapshot
            for snapshot in reversed(item_snapshots)
            if snapshot.status == PriceJobStatus.success and snapshot.median_price is not None
        ),
        None,
    )
    return PricingChart(
        item_code=item_snapshots[0].monitored_item.code,
        item_name=item_snapshots[0].monitored_item.name,
        y_min_label=format_price(min_price),
        y_max_label=format_price(max_price),
        min_polyline=polyline(points, "y_min"),
        median_polyline=polyline(points, "y_median"),
        max_polyline=polyline(points, "y_max"),
        points=points,
        latest_status=latest_snapshot.status.value,
        latest_source_code=latest_snapshot.source.code,
        latest_date_label=latest_snapshot.snapshot_date.isoformat(),
        latest_run_id=latest_snapshot.scrape_run.external_run_id,
        latest_success_date_label=latest_success.snapshot_date.isoformat() if latest_success else None,
        latest_success_median=latest_success.median_price if latest_success else None,
        latest_success_source_code=latest_success.source.code if latest_success else None,
    )


def build_point(
    *,
    snapshot: DailyPriceSnapshot,
    index: int,
    total: int,
    min_price: Decimal,
    max_price: Decimal,
) -> PricingPoint:
    x = 56 if total == 1 else 56 + round((index / (total - 1)) * 648)
    return PricingPoint(
        run_id=snapshot.scrape_run.external_run_id,
        date_label=snapshot.snapshot_date.isoformat(),
        source_code=snapshot.source.code,
        status=snapshot.status.value,
        min_price=snapshot.min_price,
        median_price=snapshot.median_price,
        max_price=snapshot.max_price,
        x=x,
        y_min=price_y(snapshot.min_price, min_price, max_price),
        y_median=price_y(snapshot.median_price, min_price, max_price),
        y_max=price_y(snapshot.max_price, min_price, max_price),
    )


def price_y(price: Decimal | None, min_price: Decimal, max_price: Decimal) -> int | None:
    if price is None:
        return None
    ratio = float((price - min_price) / (max_price - min_price))
    return 232 - round(ratio * 176)


def polyline(points: list[PricingPoint], attr: str) -> str:
    coords = []
    for point in points:
        y = getattr(point, attr)
        if y is not None:
            coords.append(f"{point.x},{y}")
    return " ".join(coords)


def format_price(value: Decimal | None) -> str:
    if value is None:
        return "-"
    return f"{int(value):,}".replace(",", " ")
