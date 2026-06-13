from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.provider import can_access_equipment_region, get_auth_provider, require_center
from app.database import get_db
from app.models.enums import (
    EquipmentCondition,
    EquipmentDisposition,
    EquipmentPhotoPurpose,
    EquipmentStatus,
)
from app.models.photo import EquipmentPhoto
from app.repositories.photo_repository import EquipmentPhotoRepository
from app.repositories.equipment_type_repository import EquipmentTypeRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.equipment import EquipmentCreateData, EquipmentUpdateData
from app.services.equipment_service import EquipmentService
from app.media_storage.photo_storage import PhotoStorage

router = APIRouter(prefix="/equipment", tags=["equipment"])
templates = Jinja2Templates(directory="app/templates")


def parse_enum(enum_cls, value: str | None):
    if not value:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return None


def form_options(db: Session, current_user=None) -> dict:
    regions = RegionRepository(db).list_active_regions()
    if current_user and not current_user.is_center:
        regions = [region for region in regions if region.id == current_user.region_id]
    return {
        "regions": regions,
        "equipment_types": EquipmentTypeRepository(db).list_active(),
        "conditions": EquipmentCondition,
        "condition_labels": CONDITION_LABELS,
    }


@router.get("", response_class=HTMLResponse)
def equipment_index(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    condition: Annotated[str | None, Query()] = None,
    disposition: Annotated[str | None, Query()] = None,
    queue: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> HTMLResponse:
    current_user = get_auth_provider().get_current_user(request, db)
    require_center(current_user)
    service = EquipmentService(db)
    active_queue = queue if queue in QUEUE_LABELS else ""
    result = service.list_equipment(
        status=parse_enum(EquipmentStatus, status),
        condition=parse_enum(EquipmentCondition, condition),
        disposition=parse_enum(EquipmentDisposition, disposition),
        queue=active_queue,
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
            "queue": active_queue,
            "queues": QUEUE_LABELS,
            "queue_counts": service.queue_counts(),
            "statuses": EquipmentStatus,
            "conditions": EquipmentCondition,
            "dispositions": EquipmentDisposition,
            "status_labels": STATUS_LABELS,
            "condition_labels": CONDITION_LABELS,
            "disposition_labels": DISPOSITION_LABELS,
        },
    )


@router.get("/new", response_class=HTMLResponse)
def equipment_new(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    current_user = get_auth_provider().get_current_user(request, db)
    return templates.TemplateResponse(
        request,
        "equipment/new.html",
        {
            **form_options(db, current_user),
            "errors": [],
            "form": {},
            "current_user": current_user,
        },
    )


def edit_form_from_item(item) -> dict:
    form = {
        "title": item.title,
        "location": item.location or "",
        "inventory_number": item.inventory_number or "",
        "serial_number": item.serial_number or "",
        "completeness": item.completeness or "",
        "condition": item.condition.value,
        "defect_description": item.defect_description or "",
        "comment": item.comment or "",
        "row_version": str(item.row_version),
    }
    for key, value in (item.attributes or {}).items():
        form[f"attr_{key}"] = value
    return form


@router.post("", response_class=HTMLResponse)
async def equipment_create(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    region_id: Annotated[int, Form()],
    equipment_type_id: Annotated[int, Form()],
    title: Annotated[str, Form()],
    location: Annotated[str, Form()],
    condition: Annotated[str, Form()],
    inventory_number: Annotated[str | None, Form()] = None,
    serial_number: Annotated[str | None, Form()] = None,
    completeness: Annotated[str | None, Form()] = None,
    defect_description: Annotated[str | None, Form()] = None,
    comment: Annotated[str | None, Form()] = None,
    action: Annotated[str, Form()] = "draft",
) -> Response:
    current_user = get_auth_provider().get_current_user(request, db)
    if not current_user.is_center:
        if current_user.region_id is None:
            raise HTTPException(status_code=403, detail="Пользователь не привязан к региону.")
        region_id = current_user.region_id

    form = await request.form()
    attributes = {
        key.removeprefix("attr_"): value
        for key, value in form.items()
        if key.startswith("attr_")
    }
    uploads = collect_photo_uploads(form)
    target_status = (
        EquipmentStatus.submitted if action == "submit" else EquipmentStatus.draft
    )
    parsed_condition = parse_enum(EquipmentCondition, condition) or EquipmentCondition.unknown

    if (
        target_status == EquipmentStatus.submitted
        and parsed_condition == EquipmentCondition.broken
        and not uploads[EquipmentPhotoPurpose.defect]
    ):
        return templates.TemplateResponse(
            request,
            "equipment/new.html",
            {
                **form_options(db, current_user),
                "errors": ["Для нерабочего оборудования приложите минимум одно фото дефекта."],
                "form": dict(form),
                "current_user": current_user,
            },
            status_code=400,
        )

    data = EquipmentCreateData(
        region_id=region_id,
        equipment_type_id=equipment_type_id,
        title=title,
        location=location,
        condition=parsed_condition,
        status=target_status,
        inventory_number=inventory_number,
        serial_number=serial_number,
        completeness=completeness,
        defect_description=defect_description,
        comment=comment,
        attributes=attributes,
    )

    try:
        item = EquipmentService(db).create_equipment(data)
        await save_uploaded_photos(db, item.id, uploads)
    except (ValueError, TypeError) as exc:
        return templates.TemplateResponse(
            request,
            "equipment/new.html",
            {
                **form_options(db, current_user),
                "errors": [str(exc)],
                "form": dict(form),
                "current_user": current_user,
            },
            status_code=400,
        )

    return RedirectResponse(f"/equipment/{item.id}", status_code=303)


@router.get("/{equipment_id}/edit", response_class=HTMLResponse)
def equipment_edit(
    equipment_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    current_user = get_auth_provider().get_current_user(request, db)
    service = EquipmentService(db)
    item = service.get_equipment(equipment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    if not can_access_equipment_region(current_user, item.region_id):
        raise HTTPException(status_code=403, detail="Нет доступа к карточке чужого региона.")

    return templates.TemplateResponse(
        request,
        "equipment/edit.html",
        {
            **form_options(db, current_user),
            "item": item,
            "current_user": current_user,
            "errors": [],
            "form": edit_form_from_item(item),
        },
    )


@router.post("/{equipment_id}", response_class=HTMLResponse)
async def equipment_update(
    equipment_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    title: Annotated[str, Form()],
    location: Annotated[str, Form()],
    condition: Annotated[str, Form()],
    row_version: Annotated[int, Form()],
    inventory_number: Annotated[str | None, Form()] = None,
    serial_number: Annotated[str | None, Form()] = None,
    completeness: Annotated[str | None, Form()] = None,
    defect_description: Annotated[str | None, Form()] = None,
    comment: Annotated[str | None, Form()] = None,
    action: Annotated[str, Form()] = "save",
) -> Response:
    current_user = get_auth_provider().get_current_user(request, db)
    service = EquipmentService(db)
    item = service.get_equipment(equipment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    if not can_access_equipment_region(current_user, item.region_id):
        raise HTTPException(status_code=403, detail="Нет доступа к карточке чужого региона.")

    form = await request.form()
    attributes = {
        key.removeprefix("attr_"): value
        for key, value in form.items()
        if key.startswith("attr_")
    }
    data = EquipmentUpdateData(
        title=title,
        location=location,
        condition=parse_enum(EquipmentCondition, condition) or EquipmentCondition.unknown,
        row_version=row_version,
        submit_after_save=action == "submit",
        inventory_number=inventory_number,
        serial_number=serial_number,
        completeness=completeness,
        defect_description=defect_description,
        comment=comment,
        attributes=attributes,
    )
    try:
        updated_item = service.update_equipment(equipment_id, data)
    except (ValueError, TypeError) as exc:
        return templates.TemplateResponse(
            request,
            "equipment/edit.html",
            {
                **form_options(db, current_user),
                "item": item,
                "current_user": current_user,
                "errors": [str(exc)],
                "form": dict(form),
            },
            status_code=400,
        )

    return RedirectResponse(f"/equipment/{updated_item.id}", status_code=303)


def collect_photo_uploads(form) -> dict[EquipmentPhotoPurpose, list[UploadFile]]:
    uploads: dict[EquipmentPhotoPurpose, list[UploadFile]] = {
        EquipmentPhotoPurpose.general: [],
        EquipmentPhotoPurpose.serial: [],
        EquipmentPhotoPurpose.defect: [],
    }
    field_map = {
        "photos_general": EquipmentPhotoPurpose.general,
        "photos_serial": EquipmentPhotoPurpose.serial,
        "photos_defect": EquipmentPhotoPurpose.defect,
    }
    for field_name, purpose in field_map.items():
        for upload in form.getlist(field_name):
            if hasattr(upload, "filename") and upload.filename:
                uploads[purpose].append(upload)
    return uploads


async def save_uploaded_photos(
    db: Session,
    equipment_id: int,
    uploads: dict[EquipmentPhotoPurpose, list[UploadFile]],
) -> None:
    storage = PhotoStorage()
    photos: list[EquipmentPhoto] = []
    display_order = 0
    for purpose, files in uploads.items():
        for upload in files:
            stored = await storage.save_upload(
                equipment_id=equipment_id,
                upload=upload,
                purpose=purpose,
            )
            if stored is None:
                continue
            photos.append(
                EquipmentPhoto(
                    id=stored.id,
                    equipment_id=equipment_id,
                    original_path=stored.original_path,
                    thumbnail_path=stored.thumbnail_path,
                    original_filename=stored.original_filename,
                    content_type=stored.content_type,
                    purpose=stored.purpose,
                    file_size=stored.file_size,
                    width=stored.width,
                    height=stored.height,
                    display_order=display_order,
                )
            )
            display_order += 1
    if photos:
        EquipmentPhotoRepository(db).add_all(photos)
        db.commit()


@router.get("/{equipment_id}", response_class=HTMLResponse)
def equipment_detail(
    equipment_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    error: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    current_user = get_auth_provider().get_current_user(request, db)
    service = EquipmentService(db)
    item = service.get_equipment(equipment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    if not can_access_equipment_region(current_user, item.region_id):
        raise HTTPException(status_code=403, detail="Нет доступа к карточке чужого региона.")

    return templates.TemplateResponse(
        request,
        "equipment/detail.html",
        {
            "item": item,
            "current_user": current_user,
            "audit_logs": service.list_audit_log(equipment_id),
            "error": error,
            "status_labels": STATUS_LABELS,
            "condition_labels": CONDITION_LABELS,
            "disposition_labels": DISPOSITION_LABELS,
            "sale_status_labels": SALE_STATUS_LABELS,
            "photo_purpose_labels": PHOTO_PURPOSE_LABELS,
            "audit_action_labels": AUDIT_ACTION_LABELS,
        },
    )


@router.post("/{equipment_id}/center-action", response_class=HTMLResponse)
def equipment_center_action(
    equipment_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    action: Annotated[str, Form()],
    row_version: Annotated[int, Form()],
    comment: Annotated[str | None, Form()] = None,
) -> Response:
    current_user = get_auth_provider().get_current_user(request, db)
    require_center(current_user)
    try:
        item = EquipmentService(db).apply_center_action(
            equipment_id=equipment_id,
            action=action,
            expected_row_version=row_version,
            comment=comment,
        )
    except ValueError as exc:
        return RedirectResponse(f"/equipment/{equipment_id}?error={quote(str(exc))}", status_code=303)

    return RedirectResponse(f"/equipment/{item.id}", status_code=303)


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

PHOTO_PURPOSE_LABELS = {
    "general": "Общий вид",
    "serial": "Шильдик / серийный номер",
    "defect": "Дефект",
    "completeness": "Комплектность",
    "other": "Другое",
}

QUEUE_LABELS = {
    "review": "На проверке",
    "revision": "Доработка",
    "diagnostics": "Диагностика",
    "writeoff": "Списание",
    "sale": "Оценка / продажа",
}

AUDIT_ACTION_LABELS = {
    "equipment.update": "Карточка отредактирована",
    "center.accept": "Центр принял запись",
    "center.revision": "Центр вернул на доработку",
    "center.diagnostics": "Центр направил на диагностику",
    "center.writeoff": "Центр направил на списание",
    "center.valuation": "Центр направил на оценку",
    "center.sale": "Центр подготовил к продаже",
}
