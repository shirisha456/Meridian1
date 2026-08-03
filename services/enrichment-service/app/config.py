from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://meridian:meridian@localhost:5433/meridian"
    redis_url: str = "redis://localhost:6380/0"
    kafka_bootstrap_servers: str = "localhost:19092"
    consumer_group_id: str = "enrichment-service"

    # Optional — degrades to rules-only categorization when unset,
    # matching every other optional integration in this project.
    openai_api_key: str = ""

    health_check_port: int = 8080


@lru_cache
def get_settings() -> Settings:
    return Settings()
