from dataclasses import dataclass
from typing import Protocol

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import UserRole
from app.models.user import User


@dataclass(frozen=True)
class CurrentUser:
    id: int | None
    role: UserRole
    region_id: int | None = None
    display_name: str = "Demo user"

    @property
    def is_center(self) -> bool:
        return self.role in {UserRole.center, UserRole.center_admin}

    @property
    def is_center_admin(self) -> bool:
        return self.role == UserRole.center_admin


class AuthProvider(Protocol):
    def get_current_user(self, request: Request, db: Session) -> CurrentUser: ...


class DemoAuthProvider:
    def get_current_user(self, request: Request, db: Session) -> CurrentUser:
        login = request.query_params.get("as") or request.cookies.get("demo_user") or "center"
        return user_from_login(db, login) or CurrentUser(
            id=None,
            role=UserRole.center_admin,
            display_name="Demo center admin",
        )


class DatabaseAuthProvider:
    def get_current_user(self, request: Request, db: Session) -> CurrentUser:
        login = (
            request.query_params.get("as")
            or request.headers.get("x-demo-user")
            or request.cookies.get("demo_user")
            or "center"
        )
        return user_from_login(db, login) or CurrentUser(
            id=None,
            role=UserRole.center_admin,
            display_name="Local center admin",
        )


class KeycloakAuthProvider:
    def get_current_user(self, request: Request, db: Session) -> CurrentUser:
        raise NotImplementedError(
            "Keycloak provider is reserved but not implemented. Use AUTH_PROVIDER=demo or database."
        )


def get_auth_provider() -> AuthProvider:
    if settings.auth_provider == "demo":
        return DemoAuthProvider()
    if settings.auth_provider == "database":
        return DatabaseAuthProvider()
    if settings.auth_provider == "keycloak":
        return KeycloakAuthProvider()
    raise RuntimeError(f"Unsupported AUTH_PROVIDER={settings.auth_provider}")


def user_from_login(db: Session, login: str) -> CurrentUser | None:
    user = db.scalar(select(User).where(User.login == login, User.is_active.is_(True)))
    if user is None:
        return None
    return CurrentUser(
        id=user.id,
        role=user.role,
        region_id=user.region_id,
        display_name=user.display_name,
    )


def require_center(user: CurrentUser) -> None:
    if not user.is_center:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Доступно только центру.")


def can_access_equipment_region(user: CurrentUser, region_id: int) -> bool:
    return user.is_center or (user.role == UserRole.region and user.region_id == region_id)
