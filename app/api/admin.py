from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth.provider import get_auth_provider
from app.database import get_db
from app.models.enums import EquipmentFieldType, UserRole
from app.models.equipment_type import EquipmentType, EquipmentTypeField
from app.models.region import Region
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def require_center_admin(request: Request, db: Session):
    current_user = get_auth_provider().get_current_user(request, db)
    if not current_user.is_center_admin:
        raise HTTPException(status_code=403, detail="Доступно только администратору центра.")
    return current_user


@router.get("", response_class=HTMLResponse)
def admin_index(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    error: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    current_user = require_center_admin(request, db)
    users = list(
        db.scalars(
            select(User)
            .options(joinedload(User.region))
            .order_by(User.is_active.desc(), User.role, User.login)
        )
    )
    regions = list(db.scalars(select(Region).order_by(Region.is_active.desc(), Region.name)))
    equipment_types = list(
        db.scalars(
            select(EquipmentType)
            .options(selectinload(EquipmentType.fields))
            .order_by(EquipmentType.is_active.desc(), EquipmentType.name)
        )
    )
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "current_user": current_user,
            "users": users,
            "regions": regions,
            "equipment_types": equipment_types,
            "roles": UserRole,
            "field_types": EquipmentFieldType,
            "role_labels": ROLE_LABELS,
            "field_type_labels": FIELD_TYPE_LABELS,
            "error": error,
        },
    )


@router.post("/regions")
def create_region(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str, Form()],
    name: Annotated[str, Form()],
    is_active: Annotated[str | None, Form()] = None,
) -> Response:
    require_center_admin(request, db)
    region = Region(
        code=normalize_code(code),
        name=normalize_text(name),
        is_active=is_active == "on",
    )
    error = validate_region(region)
    if error:
        return admin_error(error)
    db.add(region)
    return commit_or_error(db, "Регион с таким кодом уже существует.")


@router.post("/regions/{region_id}")
def update_region(
    region_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str, Form()],
    name: Annotated[str, Form()],
    is_active: Annotated[str | None, Form()] = None,
) -> Response:
    require_center_admin(request, db)
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    region.code = normalize_code(code)
    region.name = normalize_text(name)
    region.is_active = is_active == "on"
    error = validate_region(region)
    if error:
        return admin_error(error)
    return commit_or_error(db, "Регион с таким кодом уже существует.")


@router.post("/users")
def create_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    login: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    region_id: Annotated[int | None, Form()] = None,
    is_active: Annotated[str | None, Form()] = None,
) -> Response:
    require_center_admin(request, db)
    parsed_role = parse_role(role)
    if parsed_role is None:
        return admin_error("Не выбрана роль пользователя.")
    user = User(
        login=normalize_login(login),
        display_name=normalize_text(display_name),
        role=parsed_role,
        region_id=region_id if parsed_role == UserRole.region else None,
        is_active=is_active == "on",
    )
    error = validate_user(db, user)
    if error:
        return admin_error(error)
    db.add(user)
    return commit_or_error(db, "Пользователь с таким логином уже существует.")


@router.post("/users/{user_id}")
def update_user(
    user_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    login: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    region_id: Annotated[int | None, Form()] = None,
    is_active: Annotated[str | None, Form()] = None,
) -> Response:
    current_user = require_center_admin(request, db)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    parsed_role = parse_role(role)
    if parsed_role is None:
        return admin_error("Не выбрана роль пользователя.")
    if current_user.id == user.id and (parsed_role != UserRole.center_admin or is_active != "on"):
        return admin_error("Нельзя снять с себя роль администратора или отключить свою учётку.")

    user.login = normalize_login(login)
    user.display_name = normalize_text(display_name)
    user.role = parsed_role
    user.region_id = region_id if parsed_role == UserRole.region else None
    user.is_active = is_active == "on"
    error = validate_user(db, user)
    if error:
        return admin_error(error)
    return commit_or_error(db, "Пользователь с таким логином уже существует.")


@router.post("/equipment-types")
def create_equipment_type(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str, Form()],
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    is_active: Annotated[str | None, Form()] = None,
) -> Response:
    require_center_admin(request, db)
    equipment_type = EquipmentType(
        code=normalize_code(code).lower(),
        name=normalize_text(name),
        description=normalize_optional_text(description),
        is_active=is_active == "on",
    )
    error = validate_equipment_type(equipment_type)
    if error:
        return admin_error(error)
    db.add(equipment_type)
    return commit_or_error(db, "Тип оборудования с таким кодом уже существует.")


@router.post("/equipment-types/{equipment_type_id}")
def update_equipment_type(
    equipment_type_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str, Form()],
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    is_active: Annotated[str | None, Form()] = None,
) -> Response:
    require_center_admin(request, db)
    equipment_type = db.get(EquipmentType, equipment_type_id)
    if equipment_type is None:
        raise HTTPException(status_code=404, detail="Equipment type not found")
    equipment_type.code = normalize_code(code).lower()
    equipment_type.name = normalize_text(name)
    equipment_type.description = normalize_optional_text(description)
    equipment_type.is_active = is_active == "on"
    error = validate_equipment_type(equipment_type)
    if error:
        return admin_error(error)
    return commit_or_error(db, "Тип оборудования с таким кодом уже существует.")


@router.post("/equipment-type-fields")
def create_equipment_type_field(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    equipment_type_id: Annotated[int, Form()],
    code: Annotated[str, Form()],
    name: Annotated[str, Form()],
    field_type: Annotated[str, Form()],
    display_order: Annotated[int, Form()] = 0,
    help_text: Annotated[str | None, Form()] = None,
    options_text: Annotated[str | None, Form()] = None,
    is_required: Annotated[str | None, Form()] = None,
    is_filterable: Annotated[str | None, Form()] = None,
    is_active: Annotated[str | None, Form()] = None,
) -> Response:
    require_center_admin(request, db)
    parsed_field_type = parse_field_type(field_type)
    if parsed_field_type is None:
        return admin_error("Не выбран тип поля.")
    field = EquipmentTypeField(
        equipment_type_id=equipment_type_id,
        code=normalize_field_code(code),
        name=normalize_text(name),
        field_type=parsed_field_type,
        display_order=max(display_order, 0),
        help_text=normalize_optional_text(help_text),
        options=parse_options(options_text),
        is_required=is_required == "on",
        is_filterable=is_filterable == "on",
        is_active=is_active == "on",
        validation_rules={},
    )
    error = validate_equipment_type_field(db, field)
    if error:
        return admin_error(error)
    db.add(field)
    return commit_or_error(db, "Поле с таким кодом уже существует в выбранном типе.")


@router.post("/equipment-type-fields/{field_id}")
def update_equipment_type_field(
    field_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str, Form()],
    name: Annotated[str, Form()],
    field_type: Annotated[str, Form()],
    display_order: Annotated[int, Form()] = 0,
    help_text: Annotated[str | None, Form()] = None,
    options_text: Annotated[str | None, Form()] = None,
    is_required: Annotated[str | None, Form()] = None,
    is_filterable: Annotated[str | None, Form()] = None,
    is_active: Annotated[str | None, Form()] = None,
) -> Response:
    require_center_admin(request, db)
    field = db.get(EquipmentTypeField, field_id)
    if field is None:
        raise HTTPException(status_code=404, detail="Equipment type field not found")
    parsed_field_type = parse_field_type(field_type)
    if parsed_field_type is None:
        return admin_error("Не выбран тип поля.")

    field.code = normalize_field_code(code)
    field.name = normalize_text(name)
    field.field_type = parsed_field_type
    field.display_order = max(display_order, 0)
    field.help_text = normalize_optional_text(help_text)
    field.options = parse_options(options_text)
    field.is_required = is_required == "on"
    field.is_filterable = is_filterable == "on"
    field.is_active = is_active == "on"
    error = validate_equipment_type_field(db, field)
    if error:
        return admin_error(error)
    return commit_or_error(db, "Поле с таким кодом уже существует в выбранном типе.")


def normalize_text(value: str) -> str:
    return value.strip()


def normalize_optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def normalize_login(value: str) -> str:
    return value.strip().lower()


def normalize_code(value: str) -> str:
    return value.strip().upper()


def normalize_field_code(value: str) -> str:
    return value.strip().lower()


def parse_role(value: str) -> UserRole | None:
    try:
        return UserRole(value)
    except ValueError:
        return None


def parse_field_type(value: str) -> EquipmentFieldType | None:
    try:
        return EquipmentFieldType(value)
    except ValueError:
        return None


def parse_options(value: str | None) -> list[str]:
    options: list[str] = []
    seen: set[str] = set()
    for line in (value or "").splitlines():
        option = line.strip()
        if option and option not in seen:
            options.append(option)
            seen.add(option)
    return options


def validate_region(region: Region) -> str | None:
    if not region.code:
        return "Заполните код региона."
    if not region.name:
        return "Заполните название региона."
    return None


def validate_equipment_type(equipment_type: EquipmentType) -> str | None:
    if not equipment_type.code:
        return "Заполните код типа оборудования."
    if not equipment_type.name:
        return "Заполните название типа оборудования."
    return None


def validate_equipment_type_field(db: Session, field: EquipmentTypeField) -> str | None:
    if db.get(EquipmentType, field.equipment_type_id) is None:
        return "Выбранный тип оборудования не найден."
    if not field.code:
        return "Заполните код поля."
    if not field.name:
        return "Заполните название поля."
    if field.field_type in {EquipmentFieldType.select, EquipmentFieldType.multiselect} and not field.options:
        return "Для поля с выбором заполните варианты значений."
    return None


def validate_user(db: Session, user: User) -> str | None:
    if not user.login:
        return "Заполните логин пользователя."
    if not user.display_name:
        return "Заполните имя пользователя."
    if user.role == UserRole.region:
        if user.region_id is None:
            return "Для регионального пользователя выберите регион."
        region = db.get(Region, user.region_id)
        if region is None:
            return "Выбранный регион не найден."
    return None


def commit_or_error(db: Session, duplicate_message: str) -> Response:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return admin_error(duplicate_message)
    return RedirectResponse("/admin", status_code=303)


def admin_error(message: str) -> Response:
    return RedirectResponse(f"/admin?error={quote(message)}", status_code=303)


ROLE_LABELS = {
    "region": "Филиал",
    "center": "Центр",
    "center_admin": "Администратор центра",
}

FIELD_TYPE_LABELS = {
    "string": "Строка",
    "text": "Текст",
    "integer": "Целое число",
    "decimal": "Десятичное число",
    "date": "Дата",
    "boolean": "Да / нет",
    "select": "Выбор",
    "multiselect": "Множественный выбор",
}
