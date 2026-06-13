from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

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
from app.schemas.equipment import EquipmentCreateData
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


def form_options(db: Session) -> dict:
    return {
        "regions": RegionRepository(db).list_active_regions(),
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


@router.get("/new", response_class=HTMLResponse)
def equipment_new(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "equipment/new.html",
        {
            **form_options(db),
            "errors": [],
            "form": {},
        },
    )


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
                **form_options(db),
                "errors": ["Для нерабочего оборудования приложите минимум одно фото дефекта."],
                "form": dict(form),
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
                **form_options(db),
                "errors": [str(exc)],
                "form": dict(form),
            },
            status_code=400,
        )

    return RedirectResponse(f"/equipment/{item.id}", status_code=303)


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
            "photo_purpose_labels": PHOTO_PURPOSE_LABELS,
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

PHOTO_PURPOSE_LABELS = {
    "general": "Общий вид",
    "serial": "Шильдик / серийный номер",
    "defect": "Дефект",
    "completeness": "Комплектность",
    "other": "Другое",
}
