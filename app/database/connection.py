from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.config import get_settings
from app.models.price_data import Base
from app.utils.logger import app_logger as logger


class DatabaseConnection:
    """Database connection manager"""

    def __init__(self):
        self.settings = get_settings()
        self.engine = None
        self.session_maker = None

    async def init_db(self):
        """Initialize database connection and create tables"""
        logger.info(f"Initializing database: {self.settings.DATABASE_URL}")

        # Create async engine
        self.engine = create_async_engine(
            self.settings.DATABASE_URL,
            echo=self.settings.DEBUG,
            poolclass=NullPool if "sqlite" in self.settings.DATABASE_URL else None,
            pool_pre_ping=True
        )

        # Create session maker
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")

    async def close_db(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")

    async def get_session(self) -> AsyncSession:
        """Get database session"""
        if not self.session_maker:
            await self.init_db()

        async with self.session_maker() as session:
            yield session


# Global database connection instance
_db_connection: DatabaseConnection = None


def get_db_connection() -> DatabaseConnection:
    """Get cached database connection instance"""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection


async def get_db_session():
    """Dependency for FastAPI to get database session"""
    db = get_db_connection()
    async for session in db.get_session():
        yield session
