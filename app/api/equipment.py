from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import EquipmentCondition, EquipmentDisposition, EquipmentStatus
from app.services.equipment_service import EquipmentService

router = APIRouter(prefix="/equipment", tags=["equipment"])
templates = Jinja2Templates(directory="app/templates")


def parse_enum(enum_cls, value: str | None):
    if not value:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return None


@router.get("", response_class=HTMLResponse)
def equipment_index(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    condition: Annotated[str | None, Query()] = None,
    disposition: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> HTMLResponse:
    service = EquipmentService(db)
    result = service.list_equipment(
        status=parse_enum(EquipmentStatus, status),
        condition=parse_enum(EquipmentCondition, condition),
        disposition=parse_enum(EquipmentDisposition, disposition),
        query=q,
        page=page,
        page_size=50,
    )
    return templates.TemplateResponse(
        request,
        "equipment/index.html",
        {
            "result": result,
            "q": q or "",
            "status": status or "",
            "condition": condition or "",
            "disposition": disposition or "",
            "statuses": EquipmentStatus,
            "conditions": EquipmentCondition,
            "dispositions": EquipmentDisposition,
            "status_labels": STATUS_LABELS,
            "condition_labels": CONDITION_LABELS,
            "disposition_labels": DISPOSITION_LABELS,
        },
    )


@router.get("/{equipment_id}", response_class=HTMLResponse)
def equipment_detail(
    equipment_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    service = EquipmentService(db)
    item = service.get_equipment(equipment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Equipment not found")

    return templates.TemplateResponse(
        request,
        "equipment/detail.html",
        {
            "item": item,
            "status_labels": STATUS_LABELS,
            "condition_labels": CONDITION_LABELS,
            "disposition_labels": DISPOSITION_LABELS,
            "sale_status_labels": SALE_STATUS_LABELS,
        },
    )


STATUS_LABELS = {
    "draft": "Черновик",
    "submitted": "На проверке",
    "needs_revision": "Доработка",
    "accepted": "Принято",
    "diagnostics_required": "Диагностика",
    "writeoff_review": "К списанию",
    "writeoff_approved": "Списание согласовано",
    "disposal_pending": "К утилизации",
    "disposed": "Утилизировано",
    "valuation_pending": "На оценке",
    "valued": "Оценено",
    "sale_ready": "Готово к продаже",
    "listed_for_sale": "Опубликовано",
    "sold": "Продано",
    "archived": "Архив",
    "deleted": "Удалено",
}

CONDITION_LABELS = {
    "unknown": "Не подтверждено",
    "working": "Рабочее",
    "broken": "Нерабочее",
    "partially_working": "Частично рабочее",
    "requires_diagnostics": "Нужна диагностика",
}

DISPOSITION_LABELS = {
    "undecided": "Не решено",
    "writeoff": "Списание",
    "disposal": "Утилизация",
    "valuation": "Оценка",
    "sale": "Продажа",
}

SALE_STATUS_LABELS = {
    "not_for_sale": "Не продаётся",
    "valuation_pending": "Ожидает оценки",
    "priced": "Есть цена",
    "ready": "Готово",
    "listed": "Опубликовано",
    "reserved": "Зарезервировано",
    "sold": "Продано",
}
