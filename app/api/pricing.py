from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request
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
    latest_date_label: str
    latest_run_id: str
    latest_success_date_label: str | None
    latest_success_median: Decimal | None


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
        )
        .join(DailyPriceSnapshot.monitored_item)
        .join(DailyPriceSnapshot.scrape_run)
        .order_by(MonitoredItem.code, DailyPriceSnapshot.snapshot_date, PriceScrapeRun.started_at)
    ).all()
    charts = build_charts(snapshots)
    return templates.TemplateResponse(
        request,
        "pricing/index.html",
        {
            "charts": charts,
            "snapshots": snapshots,
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


def build_charts(snapshots: list[DailyPriceSnapshot]) -> list[PricingChart]:
    grouped: dict[int, list[DailyPriceSnapshot]] = {}
    for snapshot in snapshots:
        grouped.setdefault(snapshot.monitored_item_id, []).append(snapshot)

    charts = []
    for item_snapshots in grouped.values():
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
        charts.append(
            PricingChart(
                item_code=item_snapshots[0].monitored_item.code,
                item_name=item_snapshots[0].monitored_item.name,
                y_min_label=format_price(min_price),
                y_max_label=format_price(max_price),
                min_polyline=polyline(points, "y_min"),
                median_polyline=polyline(points, "y_median"),
                max_polyline=polyline(points, "y_max"),
                points=points,
                latest_status=latest_snapshot.status.value,
                latest_date_label=latest_snapshot.snapshot_date.isoformat(),
                latest_run_id=latest_snapshot.scrape_run.external_run_id,
                latest_success_date_label=latest_success.snapshot_date.isoformat()
                if latest_success
                else None,
                latest_success_median=latest_success.median_price if latest_success else None,
            )
        )
    return charts


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
