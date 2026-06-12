from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    auth_provider: str = "database"
    photo_storage: str = "filesystem"
    photo_root: str = "./var/photos"
    max_photo_size_mb: int = 10
    export_sync_limit: int = 10000
    session_secret: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

