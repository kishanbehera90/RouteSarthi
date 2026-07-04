"""App configuration, loaded from backend/.env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    redis_url: str = ""
    osrm_url: str = ""
    # RapidAPI (IRCTC1) — free tier is ~10 calls/month, so every use must be
    # budget-guarded. Used for train-validity spot checks / lazy refresh.
    rapidapi_key: str = ""


settings = Settings()
