from __future__ import annotations

from functools import lru_cache
import os
import socket

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://nearby:nearby@localhost:5432/nearby_friends"
    redis_url: str = "redis://localhost:6379/0"
    instance_id: str = ""
    service_name: str = "api-server"
    location_ttl_seconds: int = 600
    max_friends: int = 50
    default_radius_miles: float = 5.0
    nearby_page_size: int = 20
    cors_origins: str = "http://localhost:8080,http://localhost:5173"
    demo_mode: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.instance_id:
        s.instance_id = os.environ.get("HOSTNAME") or socket.gethostname()
    return s
