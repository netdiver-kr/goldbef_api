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

    # Cache warmup: pre-populate latest-all and reference-prices caches
    async def _cache_warmup():
        import time
        from datetime import datetime as dt, timedelta as td
        try:
            await asyncio.sleep(2)  # Wait for DB init
            async for session in get_db_session():
                repo = PriceRepository(session)

                # Warmup latest-all cache
                providers = ['eodhd', 'twelve_data', 'massive']
                assets_list = ['gold', 'silver', 'usd_krw', 'platinum', 'palladium', 'jpy_krw', 'cny_krw', 'eur_krw']
                results = []
                for provider in providers:
                    for asset in assets_list:
                        record = await repo.get_latest_by_provider_and_asset(provider, asset)
                        if record:
                            results.append({
                                "provider": record.provider,
                                "asset_type": record.asset_type,
                                "price": float(record.price),
                                "bid": float(record.bid) if record.bid else None,
                                "ask": float(record.ask) if record.ask else None,
                                "volume": float(record.volume) if record.volume else None,
                                "timestamp": record.timestamp.isoformat()
                            })
                api._latest_all_cache['data'] = {"prices": results}
                api._latest_all_cache['expires'] = time.time() + 10  # Longer TTL for warmup

                # Warmup reference-prices cache
                now_utc = dt.utcnow()
                kst_today = (now_utc + td(hours=9)).date()
                today_start_utc = dt(kst_today.year, kst_today.month, kst_today.day, 8, 0) - td(hours=9)
                lse_close = api._most_recent_close_time(now_utc, 16, 30)
                lse_search_start = dt(lse_close.year, lse_close.month, lse_close.day, 0, 0)
                nyse_close = api._most_recent_close_time(now_utc, 22, 0)
                nyse_search_start = dt(nyse_close.year, nyse_close.month, nyse_close.day, 0, 0)
                ref_assets = ['gold', 'silver', 'platinum', 'palladium', 'usd_krw']
                ref_result = await repo.get_reference_prices_bulk(
                    assets=ref_assets,
                    today_start_utc=today_start_utc,
                    lse_close=lse_close, lse_search_start=lse_search_start,
                    nyse_close=nyse_close, nyse_search_start=nyse_search_start,
                )
                api._ref_price_cache['data'] = ref_result
                api._ref_price_cache['expires'] = time.time() + 60

                logger.info(f"Cache warmup: latest-all={len(results)} prices, reference-prices={len(ref_result)} assets")
        except Exception as e:
            logger.warning(f"Cache warmup failed (will populate on first request): {e}")

    asyncio.create_task(_cache_warmup())

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
