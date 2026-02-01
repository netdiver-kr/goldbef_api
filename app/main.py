from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import os

from app.config import get_settings
from app.database.connection import get_db_connection, get_db_session
from app.database.repository import PriceRepository
from app.services.websocket_manager import get_ws_manager
from app.services.london_fix_client import get_london_fix_client
from app.services.smbs_client import get_smbs_client
from app.routers import api, sse
from app.utils.logger import app_logger as logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events (startup and shutdown)"""
    # Startup
    logger.info("Starting application...")

    # Initialize database
    db = get_db_connection()
    await db.init_db()

    # Start WebSocket Manager in background
    ws_manager = get_ws_manager()
    asyncio.create_task(ws_manager.start())

    # Start London Fix client in background
    london_fix = get_london_fix_client()
    asyncio.create_task(london_fix.start())

    # Start SMBS exchange rate client in background
    smbs = get_smbs_client()
    asyncio.create_task(smbs.start())

    # Run initial DB cleanup on startup, then every 6 hours
    async def _db_cleanup_loop():
        try:
            # Initial cleanup on startup
            async for session in get_db_session():
                repo = PriceRepository(session)
                deleted = await repo.delete_old_records(days=settings.DATA_RETENTION_DAYS)
                if deleted > 0:
                    logger.info(f"DB startup cleanup: deleted {deleted} old records")
        except Exception as e:
            logger.error(f"DB startup cleanup error: {e}")

        while True:
            try:
                await asyncio.sleep(6 * 3600)  # every 6 hours
                async for session in get_db_session():
                    repo = PriceRepository(session)
                    deleted = await repo.delete_old_records(days=settings.DATA_RETENTION_DAYS)
                    if deleted > 0:
                        logger.info(f"DB cleanup: deleted {deleted} old records")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DB cleanup error: {e}")

    cleanup_task = asyncio.create_task(_db_cleanup_loop())

    logger.success("Application started successfully")

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Shutdown
    logger.info("Shutting down application...")

    # Stop WebSocket Manager
    await ws_manager.stop()

    # Stop London Fix client
    await london_fix.stop()

    # Stop SMBS client
    await smbs.stop()

    # Close database connection
    await db.close_db()

    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Real-Time Financial Data Comparison",
    description="Compare real-time Gold, Silver, and USD/KRW prices from multiple providers",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(sse.router, prefix="/api", tags=["SSE"])

# Mount static files
if os.path.exists("frontend/static"):
    app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Mount price dashboard static files
if os.path.exists("price/static"):
    app.mount("/price/static", StaticFiles(directory="price/static"), name="price-static")


@app.get("/price/", response_class=HTMLResponse)
async def price_dashboard():
    """Serve EurasiaMetal price dashboard"""
    try:
        if os.path.exists("price/index.html"):
            return FileResponse("price/index.html")
        return HTMLResponse(content="<h1>Price dashboard not found</h1>", status_code=404)
    except Exception as e:
        logger.error(f"Error serving price page: {e}")
        return HTMLResponse(content=f"<h1>Error: {e}</h1>", status_code=500)


@app.get("/price/settings", response_class=HTMLResponse)
async def price_settings():
    """Serve EurasiaMetal settings page"""
    try:
        if os.path.exists("price/settings.html"):
            return FileResponse("price/settings.html")
        return HTMLResponse(content="<h1>Settings page not found</h1>", status_code=404)
    except Exception as e:
        logger.error(f"Error serving settings page: {e}")
        return HTMLResponse(content=f"<h1>Error: {e}</h1>", status_code=500)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve main HTML page"""
    try:
        if os.path.exists("frontend/index.html"):
            return FileResponse("frontend/index.html")
        else:
            return HTMLResponse(
                content="""
                <html>
                    <head><title>Real-Time Financial Data</title></head>
                    <body>
                        <h1>Real-Time Financial Data Comparison</h1>
                        <p>Frontend not found. Please create frontend/index.html</p>
                        <p>API Documentation: <a href="/docs">/docs</a></p>
                    </body>
                </html>
                """,
                status_code=200
            )
    except Exception as e:
        logger.error(f"Error serving root page: {e}")
        return HTMLResponse(content=f"<h1>Error: {e}</h1>", status_code=500)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "Service is running"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
