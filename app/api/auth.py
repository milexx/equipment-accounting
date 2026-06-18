from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    users = list(
        db.scalars(
            select(User)
            .where(
                User.is_active.is_(True),
                User.role != UserRole.center_admin,
            )
            .order_by(User.role, User.login)
        )
    )
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "users": users,
            "role_labels": ROLE_LABELS,
        },
    )


@router.post("/login")
def login(
    login_name: Annotated[str, Form(alias="login")],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    user = db.scalar(select(User).where(User.login == login_name, User.is_active.is_(True)))
    redirect_to = "/"
    if user and user.role.value == "region":
        redirect_to = "/region"
    elif user and user.role.value == "center_admin":
        redirect_to = "/admin"
    elif user:
        redirect_to = "/equipment"

    response = RedirectResponse(redirect_to, status_code=303)
    response.set_cookie(
        "demo_user",
        login_name,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return response


@router.get("/logout")
def logout() -> Response:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("demo_user")
    return response


ROLE_LABELS = {
    "region": "Филиал",
    "center": "Центр",
    "center_admin": "Администратор центра",
}
