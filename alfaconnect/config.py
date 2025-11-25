from urllib.parse import urlparse
from typing import Optional, Dict, Any
import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Enhanced settings with environment-based configuration
    Based on fastapi-chat patterns
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    # Environment
    ENVIRONMENT: str = "development"  # development, production, test
    
    # Bot settings
    BOT_TOKEN: str
    BOT_USERNAME: Optional[str] = None  # For WebApp security checks
    BOT_ID: int
    ZAYAVKA_GROUP_ID: Optional[int] = None
    MANAGER_GROUP_ID: Optional[int] = None
    ADMINS_ID: int
    
    # Database settings
    DB_URL: str
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DATABASE_URL: Optional[str] = None  # FastAPI uchun (psycopg2 format)
    DB_SSL_MODE: Optional[str] = None  # SSL mode: 'require', 'disable', yoki None (default: disable)
    
    # Media
    MEDIA_ROOT: str = "media"
    
    # WebApp settings
    WEBAPP_URL: str
    WEBAPP_PORT: Optional[int] = None
    API_HOST: str
    API_PORT: int
    API_BIND_HOST: Optional[str] = None
    PUBLIC_HOST: Optional[str] = None
    WS_URL: Optional[str] = None
    
    # Redis settings (for PubSub and caching)
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    # Logging
    LOG_LEVEL: int = logging.INFO
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    WS_RATE_LIMIT_TIMES: int = 50  # Number of requests
    WS_RATE_LIMIT_SECONDS: int = 10  # Time window in seconds
    
    # CORS
    ALLOWED_ORIGINS: Optional[str] = None  # Comma-separated list of allowed origins

    @property
    def api_bind_host(self) -> str:
        # Default to 0.0.0.0 for network access if not specified
        if self.API_BIND_HOST:
            return self.API_BIND_HOST
        # If API_BIND_HOST is not set, default to 0.0.0.0 for network access
        # This allows connections from other computers on the network
        return "0.0.0.0"

    @property
    def public_host(self) -> str:
        return self.PUBLIC_HOST or self.API_HOST

    @property
    def backend_http_url(self) -> str:
        return f"http://{self.public_host}:{self.API_PORT}"

    @property
    def backend_ws_url(self) -> str:
        if self.WS_URL:
            return self.WS_URL
        return f"ws://{self.public_host}:{self.API_PORT}"

    @property
    def resolved_webapp_port(self) -> int:
        if self.WEBAPP_PORT is not None:
            return self.WEBAPP_PORT
        parsed = urlparse(self.WEBAPP_URL)
        if parsed.port:
            return parsed.port
        raise ValueError("WEBAPP_PORT must be defined in .env when WEBAPP_URL has no explicit port.")

    @property
    def api_bind_host(self) -> str:
        # Default to 0.0.0.0 for network access if not specified
        if self.API_BIND_HOST:
            return self.API_BIND_HOST
        # If API_BIND_HOST is not set, default to 0.0.0.0 for network access
        # This allows connections from other computers on the network
        return "0.0.0.0"

    @property
    def public_host(self) -> str:
        return self.PUBLIC_HOST or self.API_HOST

    @property
    def backend_http_url(self) -> str:
        return f"http://{self.public_host}:{self.API_PORT}"

    @property
    def backend_ws_url(self) -> str:
        if self.WS_URL:
            return self.WS_URL
        return f"ws://{self.public_host}:{self.API_PORT}"

    @property
    def resolved_webapp_port(self) -> int:
        if self.WEBAPP_PORT is not None:
            return self.WEBAPP_PORT
        parsed = urlparse(self.WEBAPP_URL)
        if parsed.port:
            return parsed.port
        raise ValueError("WEBAPP_PORT must be defined in .env when WEBAPP_URL has no explicit port.")

settings = Settings()

# DB_URL ni asyncpg uchun to'g'ri formatga o'zgartirish (postgresql+psycopg2:// -> postgresql://)
if settings.DB_URL and settings.DB_URL.startswith('postgresql+psycopg2://'):
    settings.DB_URL = settings.DB_URL.replace('postgresql+psycopg2://', 'postgresql://')

# Agar DB_URL bo'sh bo'lsa, DB_HOST, DB_USER, va boshqalardan yaratish
if not settings.DB_URL:
    # asyncpg uchun to'g'ri format
    settings.DB_URL = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

DB_CONFIG: Dict[str, Any] = {
    'host': settings.DB_HOST,
    'port': settings.DB_PORT,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD,
    'database': settings.DB_NAME
}
