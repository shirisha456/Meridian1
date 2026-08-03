from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    redis_url: str = "redis://localhost:6380/0"
    kafka_bootstrap_servers: str = "localhost:19092"
    consumer_group_id: str = "notification-service"

    health_check_port: int = 8082


@lru_cache
def get_settings() -> Settings:
    return Settings()
