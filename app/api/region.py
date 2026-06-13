from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.provider import get_auth_provider
from app.models.enums import EquipmentStatus
from app.repositories.region_repository import RegionRepository
from app.services.equipment_service import EquipmentService

router = APIRouter(prefix="/region", tags=["region"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def region_home(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    region_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    current_user = get_auth_provider().get_current_user(request, db)
    region_repository = RegionRepository(db)
    regions = region_repository.list_active_regions()
    if current_user.is_center:
        selected_region = region_repository.get(region_id) if region_id else (regions[0] if regions else None)
    else:
        selected_region = region_repository.get(current_user.region_id) if current_user.region_id else None
    if selected_region is None or not selected_region.is_active:
        selected_region = regions[0] if regions and current_user.is_center else None

    service = EquipmentService(db)
    parsed_status = parse_region_status(status)
    result = None
    counts = {}
    if selected_region:
        result = service.list_equipment(
            region_id=selected_region.id,
            status=parsed_status,
            page=1,
            page_size=20,
        )
        counts = service.region_status_counts(selected_region.id)

    return templates.TemplateResponse(
        request,
        "region/home.html",
        {
            "regions": regions,
            "selected_region": selected_region,
            "current_user": current_user,
            "can_switch_region": current_user.is_center,
            "status": status or "",
            "result": result,
            "counts": counts,
            "status_tabs": REGION_STATUS_TABS,
            "status_labels": REGION_STATUS_LABELS,
        },
    )


def parse_region_status(value: str | None) -> EquipmentStatus | None:
    if not value:
        return None
    allowed = {item.value for item in REGION_STATUS_TABS}
    if value not in allowed:
        return None
    return EquipmentStatus(value)


REGION_STATUS_TABS = [
    EquipmentStatus.draft,
    EquipmentStatus.submitted,
    EquipmentStatus.needs_revision,
    EquipmentStatus.accepted,
]

REGION_STATUS_LABELS = {
    "draft": "Черновики",
    "submitted": "Отправлено в центр",
    "needs_revision": "Вернули на доработку",
    "accepted": "Принято центром",
}
