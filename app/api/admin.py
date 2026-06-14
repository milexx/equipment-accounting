from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.provider import get_auth_provider
from app.database import get_db
from app.models.enums import UserRole
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
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "current_user": current_user,
            "users": users,
            "regions": regions,
            "roles": UserRole,
            "role_labels": ROLE_LABELS,
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


def normalize_text(value: str) -> str:
    return value.strip()


def normalize_login(value: str) -> str:
    return value.strip().lower()


def normalize_code(value: str) -> str:
    return value.strip().upper()


def parse_role(value: str) -> UserRole | None:
    try:
        return UserRole(value)
    except ValueError:
        return None


def validate_region(region: Region) -> str | None:
    if not region.code:
        return "Заполните код региона."
    if not region.name:
        return "Заполните название региона."
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
