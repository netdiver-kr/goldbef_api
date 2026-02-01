from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
from app.services.websocket_manager import get_ws_manager
from app.config import get_settings
from app.utils.logger import app_logger as logger

router = APIRouter()


async def event_generator(request: Request):
    """Generate Server-Sent Events stream"""
    ws_manager = get_ws_manager()
    settings = get_settings()

    # Send immediate heartbeat to force IIS ARR to flush response headers
    # This makes the browser's EventSource.onopen fire without delay
    yield ": connected\n\n"

    # Create queue for this client
    queue = asyncio.Queue(maxsize=settings.SSE_QUEUE_SIZE)
    ws_manager.add_sse_client(queue)

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info("SSE client disconnected")
                break

            try:
                # Wait for data with timeout (for heartbeat)
                data = await asyncio.wait_for(
                    queue.get(),
                    timeout=settings.SSE_HEARTBEAT_INTERVAL
                )

                # Send data as SSE
                yield f"data: {json.dumps(data)}\n\n"

            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield ": heartbeat\n\n"

            except Exception as e:
                logger.error(f"Error in event generator: {e}")
                break

    finally:
        # Remove client from broadcast list
        ws_manager.remove_sse_client(queue)


@router.get("/stream")
async def stream_prices(request: Request):
    """
    Stream real-time price updates via Server-Sent Events

    Returns:
        StreamingResponse: SSE stream with price updates
    """
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        }
    )


@router.get("/status")
async def get_websocket_status():
    """
    Get connection status of all WebSocket clients

    Returns:
        dict: Status of each provider
    """
    ws_manager = get_ws_manager()
    status = ws_manager.get_client_status()

    return {
        "websocket_connections": status,
        "sse_clients": len(ws_manager.broadcast_queues)
    }
