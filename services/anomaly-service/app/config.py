from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://meridian:meridian@localhost:5433/meridian"
    kafka_bootstrap_servers: str = "localhost:19092"
    consumer_group_id: str = "anomaly-service"

    health_check_port: int = 8081


@lru_cache
def get_settings() -> Settings:
    return Settings()
