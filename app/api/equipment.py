import csv
from io import StringIO
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth.provider import can_access_equipment_region, get_auth_provider, require_center
from app.database import get_db
from app.models.audit import EquipmentAuditLog
from app.models.equipment import Equipment
from app.models.enums import (
    EquipmentCondition,
    EquipmentDisposition,
    EquipmentPhotoPurpose,
    EquipmentSaleStatus,
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
    region_id: Annotated[int | None, Query()] = None,
    equipment_type_id: Annotated[int | None, Query()] = None,
    location: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    condition: Annotated[str | None, Query()] = None,
    disposition: Annotated[str | None, Query()] = None,
    sale_status: Annotated[str | None, Query()] = None,
    queue: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> HTMLResponse:
    current_user = get_auth_provider().get_current_user(request, db)
    require_center(current_user)
    service = EquipmentService(db)
    active_queue = queue if queue in QUEUE_LABELS else ""
    attribute_filters = collect_attribute_filters(request)
    result = service.list_equipment(
        region_id=region_id,
        equipment_type_id=equipment_type_id,
        status=parse_enum(EquipmentStatus, status),
        condition=parse_enum(EquipmentCondition, condition),
        disposition=parse_enum(EquipmentDisposition, disposition),
        sale_status=parse_enum(EquipmentSaleStatus, sale_status),
        queue=active_queue,
        query=q,
        location=location,
        attribute_filters=attribute_filters,
        page=page,
        page_size=50,
    )
    equipment_types = EquipmentTypeRepository(db).list_active()
    return templates.TemplateResponse(
        request,
        "equipment/index.html",
        {
            "result": result,
            "q": q or "",
            "region_id": region_id,
            "equipment_type_id": equipment_type_id,
            "location": location or "",
            "status": status or "",
            "condition": condition or "",
            "disposition": disposition or "",
            "sale_status": sale_status or "",
            "queue": active_queue,
            "queues": QUEUE_LABELS,
            "queue_counts": service.queue_counts(),
            "regions": RegionRepository(db).list_active_regions(),
            "equipment_types": equipment_types,
            "filterable_fields": filterable_fields(equipment_types),
            "attribute_filters": attribute_filters,
            "statuses": EquipmentStatus,
            "conditions": EquipmentCondition,
            "dispositions": EquipmentDisposition,
            "sale_statuses": EquipmentSaleStatus,
            "status_labels": STATUS_LABELS,
            "condition_labels": CONDITION_LABELS,
            "disposition_labels": DISPOSITION_LABELS,
            "sale_status_labels": SALE_STATUS_LABELS,
        },
    )


@router.get("/export.csv")
def equipment_export_csv(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query()] = None,
    region_id: Annotated[int | None, Query()] = None,
    equipment_type_id: Annotated[int | None, Query()] = None,
    location: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    condition: Annotated[str | None, Query()] = None,
    disposition: Annotated[str | None, Query()] = None,
    sale_status: Annotated[str | None, Query()] = None,
    queue: Annotated[str | None, Query()] = None,
) -> Response:
    current_user = get_auth_provider().get_current_user(request, db)
    require_center(current_user)
    active_queue = queue if queue in QUEUE_LABELS else ""
    items = EquipmentService(db).export_equipment(
        region_id=region_id,
        equipment_type_id=equipment_type_id,
        status=parse_enum(EquipmentStatus, status),
        condition=parse_enum(EquipmentCondition, condition),
        disposition=parse_enum(EquipmentDisposition, disposition),
        sale_status=parse_enum(EquipmentSaleStatus, sale_status),
        queue=active_queue,
        query=q,
        location=location,
        attribute_filters=collect_attribute_filters(request),
    )
    content = equipment_csv(items)
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="equipment_export.csv"'},
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


def collect_attribute_filters(request: Request) -> dict[str, str]:
    return {
        key.removeprefix("attr_"): value
        for key, value in request.query_params.items()
        if key.startswith("attr_") and value.strip()
    }


def filterable_fields(equipment_types) -> list:
    fields = []
    seen = set()
    for equipment_type in equipment_types:
        for field in sorted(equipment_type.fields, key=lambda item: item.display_order):
            if not field.is_active or not field.is_filterable or field.code in seen:
                continue
            fields.append(field)
            seen.add(field.code)
    return fields


def equipment_csv(items: list[Equipment]) -> str:
    output = StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Статус",
            "Состояние",
            "Маршрут",
            "Статус продажи",
            "Регион",
            "Тип",
            "Наименование",
            "Местонахождение",
            "Инвентарный номер",
            "Серийный номер",
            "Комплектность",
            "Оценочная стоимость",
            "Цена продажи",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item.id,
                STATUS_LABELS[item.status.value],
                CONDITION_LABELS[item.condition.value],
                DISPOSITION_LABELS[item.disposition.value],
                SALE_STATUS_LABELS[item.sale_status.value],
                item.region.name,
                item.equipment_type.name,
                item.title,
                item.location or "",
                item.inventory_number or "",
                item.serial_number or "",
                item.completeness or "",
                item.valuation_amount or "",
                item.sale_price or "",
            ]
        )
    return output.getvalue()


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
    start_order: int = 0,
    commit: bool = True,
) -> list[EquipmentPhoto]:
    storage = PhotoStorage()
    photos: list[EquipmentPhoto] = []
    display_order = start_order
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
        if commit:
            db.commit()
    return photos


@router.post("/{equipment_id}/photos", response_class=HTMLResponse)
async def equipment_photos_update(
    equipment_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    action: Annotated[str, Form()],
    row_version: Annotated[int, Form()],
    photo_id: Annotated[UUID | None, Form()] = None,
    purpose: Annotated[str | None, Form()] = None,
) -> Response:
    current_user = get_auth_provider().get_current_user(request, db)
    item = db.scalar(
        select(Equipment)
        .where(Equipment.id == equipment_id, Equipment.deleted_at.is_(None))
        .options(selectinload(Equipment.photos))
        .with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    if not can_access_equipment_region(current_user, item.region_id):
        raise HTTPException(status_code=403, detail="Нет доступа к карточке чужого региона.")
    if item.row_version != row_version:
        return RedirectResponse(
            f"/equipment/{equipment_id}?error={quote('Карточку уже изменили. Обновите страницу и повторите действие.')}",
            status_code=303,
        )

    try:
        form = await request.form()
        old_photos = photo_audit_snapshot(item.photos)
        if action == "upload":
            uploads = collect_photo_uploads(form)
            next_order = max((photo.display_order for photo in item.photos), default=-1) + 1
            new_photos = await save_uploaded_photos(
                db,
                item.id,
                uploads,
                start_order=next_order,
                commit=False,
            )
            if not new_photos:
                raise ValueError("Выберите хотя бы одно фото для загрузки.")
            item.photos.extend(new_photos)
            audit_action = "photos.upload"
        elif action == "update":
            photo = require_photo(item, photo_id)
            parsed_purpose = parse_enum(EquipmentPhotoPurpose, purpose)
            if parsed_purpose is None:
                raise ValueError("Не выбрано назначение фото.")
            photo.purpose = parsed_purpose
            audit_action = "photos.update"
        elif action == "delete":
            photo = require_photo(item, photo_id)
            PhotoStorage().delete_paths([photo.original_path, photo.thumbnail_path])
            item.photos.remove(photo)
            EquipmentPhotoRepository(db).delete(photo)
            audit_action = "photos.delete"
        elif action == "reorder":
            if not apply_photo_order(item.photos, form):
                return RedirectResponse(f"/equipment/{equipment_id}", status_code=303)
            audit_action = "photos.reorder"
        else:
            raise ValueError("Неизвестное действие с фото.")

        item.row_version += 1
        item.updated_at = func.now()
        db.flush()
        EquipmentService(db).audit_repository.add(
            EquipmentAuditLog(
                equipment_id=item.id,
                actor_user_id=current_user.id,
                actor_region_id=current_user.region_id,
                action=audit_action,
                old_data={"photos": old_photos, "row_version": row_version},
                new_data={
                    "photos": photo_audit_snapshot(item.photos),
                    "row_version": item.row_version,
                },
            )
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/equipment/{equipment_id}?error={quote(str(exc))}", status_code=303)

    return RedirectResponse(f"/equipment/{equipment_id}", status_code=303)


def require_photo(item: Equipment, photo_id: UUID | None) -> EquipmentPhoto:
    if photo_id is None:
        raise ValueError("Фото не найдено.")
    for photo in item.photos:
        if photo.id == photo_id:
            return photo
    raise ValueError("Фото не найдено в этой карточке.")


def apply_photo_order(photos: list[EquipmentPhoto], form) -> bool:
    changed = False
    for photo in photos:
        raw_order = form.get(f"order_{photo.id}")
        if raw_order is None:
            continue
        try:
            display_order = int(raw_order)
        except (TypeError, ValueError) as exc:
            raise ValueError("Порядок фото должен быть числом.") from exc
        display_order = max(display_order, 0)
        if photo.display_order != display_order:
            photo.display_order = display_order
            changed = True
    return changed


def photo_audit_snapshot(photos: list[EquipmentPhoto]) -> list[dict]:
    return [
        {
            "id": str(photo.id),
            "purpose": photo.purpose.value,
            "display_order": photo.display_order,
            "original_filename": photo.original_filename,
        }
        for photo in sorted(photos, key=lambda item: (item.display_order, item.created_at))
    ]


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


@router.post("/{equipment_id}/business-action", response_class=HTMLResponse)
def equipment_business_action(
    equipment_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    action: Annotated[str, Form()],
    row_version: Annotated[int, Form()],
    valuation_amount: Annotated[str | None, Form()] = None,
    sale_price: Annotated[str | None, Form()] = None,
    sale_description: Annotated[str | None, Form()] = None,
    is_public_listing: Annotated[str | None, Form()] = None,
    comment: Annotated[str | None, Form()] = None,
) -> Response:
    current_user = get_auth_provider().get_current_user(request, db)
    require_center(current_user)
    try:
        item = EquipmentService(db).apply_business_action(
            equipment_id=equipment_id,
            action=action,
            expected_row_version=row_version,
            valuation_amount=valuation_amount,
            sale_price=sale_price,
            sale_description=sale_description,
            is_public_listing=is_public_listing == "on",
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
    "photos.upload": "Фото загружены",
    "photos.update": "Фото изменено",
    "photos.delete": "Фото удалено",
    "photos.reorder": "Порядок фото изменён",
    "business.valuation_save": "Оценка сохранена",
    "business.sale_ready": "Подготовлено к продаже",
    "business.list_for_sale": "Опубликовано к продаже",
    "business.sold": "Продано",
    "business.writeoff_approve": "Списание согласовано",
    "business.disposal_pending": "Отправлено на утилизацию",
    "business.disposed": "Утилизировано",
    "business.archive": "Архивировано",
    "business.delete": "Удалено",
    "center.accept": "Центр принял запись",
    "center.revision": "Центр вернул на доработку",
    "center.diagnostics": "Центр направил на диагностику",
    "center.writeoff": "Центр направил на списание",
    "center.valuation": "Центр направил на оценку",
    "center.sale": "Центр подготовил к продаже",
}
