from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Rental Operations - Module 1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "supersecretjwtkeyforlocaldevelopment123456"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DATABASE_URL: str = "postgresql://postgres:hitesh@localhost:5432/rental_ops_dev"

    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "./uploads"

    # Meta WhatsApp credentials (kept server-side only)
    META_ACCESS_TOKEN: Optional[str] = None
    META_VERIFY_TOKEN: str = "secure_verify_token_module1"
    META_APP_SECRET: Optional[str] = None
    META_API_VERSION: str = "v20.0"
    META_PHONE_NUMBER_ID: Optional[str] = None
    META_BUSINESS_ACCOUNT_ID: Optional[str] = None

    # AI Orchestration (Module 3)
    AI_PROVIDER: str = "mock"
    AI_MODEL: str = "gpt-4o-mini"
    AI_API_KEY: Optional[str] = None
    AI_API_BASE: str = "https://api.openai.com/v1"
    AI_TIMEOUT_SECONDS: float = 15.0
    AI_MAX_RETRIES: int = 3
    AI_TEMPERATURE: float = 0.0
    AI_MAX_OUTPUT_TOKENS: int = 1000
    AI_FALLBACK_PROVIDER: Optional[str] = None
    AI_FALLBACK_MODEL: Optional[str] = None


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
