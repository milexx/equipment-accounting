from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.provider import get_auth_provider, require_center
from app.database import get_db
from app.models.pricing import DailyPriceSnapshot, MonitoredItem, PriceScrapeRun

router = APIRouter(prefix="/pricing", tags=["pricing"])
templates = Jinja2Templates(directory="app/templates")


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
    return templates.TemplateResponse(
        request,
        "pricing/detail.html",
        {
            "chart": chart,
            "snapshots": list(reversed(snapshots)),
            "format_price": format_price,
            "status_labels": {
                "success": "Успех",
                "no_data": "Нет данных",
                "blocked": "Блокировка",
                "captcha": "CAPTCHA",
                "parser_error": "Ошибка",
            },
        },
    )


def group_snapshots(
    snapshots: list[DailyPriceSnapshot],
) -> dict[int, list[DailyPriceSnapshot]]:
    grouped: dict[int, list[DailyPriceSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        grouped[snapshot.monitored_item_id].append(snapshot)
    return grouped


def build_summary_rows(
    grouped: dict[int, list[DailyPriceSnapshot]],
) -> list[PricingSummaryRow]:
    rows: list[PricingSummaryRow] = []
    for item_snapshots in grouped.values():
        latest_snapshot = item_snapshots[-1]
        latest_success = next(
            (snapshot for snapshot in reversed(item_snapshots) if snapshot.median_price is not None),
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
                    1 for snapshot in item_snapshots if snapshot.median_price is not None
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
            1 for row in summary_rows if row.latest_status in {"blocked", "captcha", "parser_error"}
        ),
        latest_snapshot_date_label=max(latest_dates) if latest_dates else None,
    )


def build_chart(item_snapshots: list[DailyPriceSnapshot]) -> PricingChart:
    value_snapshots = [
        snapshot
        for snapshot in item_snapshots
        if snapshot.min_price is not None
        or snapshot.median_price is not None
        or snapshot.max_price is not None
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
        (snapshot for snapshot in reversed(item_snapshots) if snapshot.median_price is not None),
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
