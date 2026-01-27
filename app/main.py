from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import os

from app.config import get_settings
from app.database.connection import get_db_connection
from app.services.websocket_manager import get_ws_manager
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

    logger.success("Application started successfully")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Stop WebSocket Manager
    await ws_manager.stop()

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
