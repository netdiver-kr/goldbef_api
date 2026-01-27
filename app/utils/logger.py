import sys
from loguru import logger
from app.config import get_settings


def setup_logger():
    """Configure loguru logger"""
    settings = get_settings()

    # Remove default logger
    logger.remove()

    # Add console logger
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True
    )

    # Add file logger
    logger.add(
        "logs/app.log",
        rotation="1 day",
        retention="7 days",
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    return logger


# Create logger instance
app_logger = setup_logger()
