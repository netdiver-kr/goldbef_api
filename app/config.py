from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # API Keys
    EODHD_API_KEY: str
    TWELVE_DATA_API_KEY: str
    MASSIVE_API_KEY: str

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./price_data.db"

    # Application
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    DATA_RETENTION_DAYS: int = 30

    # WebSocket Configuration
    WS_RECONNECT_DELAY: int = 1  # seconds
    WS_MAX_RECONNECT_DELAY: int = 60  # seconds
    WS_MESSAGE_TIMEOUT: int = 60  # seconds

    # SSE Configuration
    SSE_QUEUE_SIZE: int = 100
    SSE_HEARTBEAT_INTERVAL: int = 30  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get cached settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
