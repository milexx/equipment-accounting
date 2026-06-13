from dataclasses import dataclass
from typing import Protocol

from app.config import settings
from app.models.enums import UserRole


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
    def get_current_user(self) -> CurrentUser: ...


class DemoAuthProvider:
    def get_current_user(self) -> CurrentUser:
        return CurrentUser(id=None, role=UserRole.center_admin, display_name="Demo center admin")


class DatabaseAuthProvider:
    def get_current_user(self) -> CurrentUser:
        # Placeholder for MVP local users. It keeps route code independent from Keycloak.
        return CurrentUser(id=None, role=UserRole.center_admin, display_name="Local center admin")


class KeycloakAuthProvider:
    def get_current_user(self) -> CurrentUser:
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
