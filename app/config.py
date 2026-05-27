from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Google Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # Meta / Instagram
    meta_app_secret: str
    meta_access_token: str
    meta_verify_token: str
    meta_graph_api_url: str = "https://graph.facebook.com/v21.0"

    # Telegram
    telegram_bot_token: str
    telegram_group_id: str

    # Admin API
    api_secret_key: str

    # CORS
    cors_origins: Union[str, List[str]] = "http://localhost:3000"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return ["http://localhost:3000"]
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # App
    environment: str = "production"
    log_level: str = "INFO"

    # JWT
    jwt_secret_key: str = "change_this_to_a_long_random_secret_in_production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 hours

    # Rate limiting
    ig_daily_message_limit: int = 1000
    ig_daily_warning_threshold: int = 900

    # Set to true temporarily to bypass webhook signature check for debugging
    skip_webhook_signature: bool = False


settings = Settings()
