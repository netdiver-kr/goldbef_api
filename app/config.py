from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # API Keys
    EODHD_API_KEY: str
    TWELVE_DATA_API_KEY: str
    MASSIVE_API_KEY: str
    METALS_DEV_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./price_data.db"

    # MSSQL Database (for Massive price data)
    MSSQL_DRIVER: str = "ODBC Driver 17 for SQL Server"
    MSSQL_SERVER: str = "(local)\\SQLEXPRESS"
    MSSQL_DATABASE: str = "goldbef"
    MSSQL_TRUSTED_CONNECTION: str = "yes"

    # Data Processing
    PRICE_UPDATE_INTERVAL: float = 3.0  # seconds (3-second averaging)

    # Application
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"
    DATA_RETENTION_DAYS: int = 7

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
