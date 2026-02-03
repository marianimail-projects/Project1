from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # OpenAI
    openai_api_key: str = Field(default="", repr=False, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_MODEL")
    openai_embed_model: str = Field(
        default="text-embedding-3-small", validation_alias="OPENAI_EMBED_MODEL"
    )

    # KB
    kb_excel_path: str = Field(default="data/kb.xlsx", validation_alias="KB_EXCEL_PATH")
    kb_top_k: int = Field(default=6, validation_alias="KB_TOP_K")
    kb_min_score: float = Field(default=0.80, validation_alias="KB_MIN_SCORE")

    # DB
    sqlite_path: str = Field(default="data/app.sqlite3", validation_alias="SQLITE_PATH")

    # Admin
    admin_api_key: str = Field(default="", repr=False, validation_alias="ADMIN_API_KEY")

    # CiaoBooking integration
    mock_ciao_booking: bool = Field(default=True, validation_alias="MOCK_CIAO_BOOKING")
    ciao_booking_base_url: str = Field(default="", validation_alias="CIAO_BOOKING_BASE_URL")
    ciao_booking_api_key: str = Field(default="", repr=False, validation_alias="CIAO_BOOKING_API_KEY")
    ciao_booking_timeout_s: float = Field(default=10.0, validation_alias="CIAO_BOOKING_TIMEOUT_S")

    # Human handoff
    niccolo_notify_webhook_url: str = Field(
        default="", repr=False, validation_alias="NICCOLO_NOTIFY_WEBHOOK_URL"
    )


settings = Settings()

