from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "meridian-core-api"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://meridian:meridian@localhost:5433/meridian"

    cors_origins: str = "http://localhost:3000"

    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    redis_url: str = "redis://localhost:6380/0"

    # Optional — degrades gracefully when unset (holdings/watchlist
    # entries simply keep latest_price_minor=null, "no price yet").
    market_data_api_key: str = ""
    market_data_base_url: str = "https://api.twelvedata.com"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    def assert_safe_for_environment(self) -> None:
        """Refuse to boot in production with the placeholder JWT secret.

        The reference implementation shipped this exact default with no
        runtime check — nothing stopped a misconfigured prod deploy from
        signing tokens with a value anyone can read in this repo's history.
        """
        default_secret = type(self).model_fields["jwt_secret"].default
        if self.is_production and self.jwt_secret == default_secret:
            raise RuntimeError(
                "JWT_SECRET is still the placeholder default. Set a real "
                "secret via the JWT_SECRET environment variable before "
                "starting in production."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
