import asyncio
import json
import traceback
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any
import websockets
from websockets.exceptions import WebSocketException
from app.config import get_settings
from app.utils.logger import app_logger as logger


class BaseWebSocketClient(ABC):
    """Base class for all API WebSocket clients"""

    def __init__(self, api_key: str, on_message: Callable):
        self.api_key = api_key
        self.on_message = on_message  # Callback when message is received
        self.ws = None
        self.running = False

        # Get settings
        settings = get_settings()
        self.reconnect_delay = settings.WS_RECONNECT_DELAY
        self.max_reconnect_delay = settings.WS_MAX_RECONNECT_DELAY
        self.current_reconnect_delay = self.reconnect_delay
        self.message_timeout = settings.WS_MESSAGE_TIMEOUT

        # Monitoring
        self._last_message_time: float = 0
        self._message_count: int = 0
        self._error_count: int = 0
        self._watchdog_task: Optional[asyncio.Task] = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name (e.g., 'eodhd', 'twelve_data', 'massive')"""
        pass

    @abstractmethod
    def get_websocket_url(self) -> str:
        """Get WebSocket URL for this API"""
        pass

    @abstractmethod
    def get_subscribe_message(self) -> Dict[str, Any]:
        """
        Get subscribe message to send after connection

        Should subscribe to: gold, silver, usd_krw
        """
        pass

    @abstractmethod
    def parse_message(self, raw_message: str) -> Optional[Dict[str, Any]]:
        """
        Parse raw WebSocket message to standard format

        Expected output format:
        {
            'provider': 'eodhd',
            'asset_type': 'gold',  # or 'silver', 'usd_krw'
            'price': 2050.25,
            'bid': 2050.00,        # optional
            'ask': 2050.50,        # optional
            'volume': 12345.67,    # optional
            'timestamp': '2024-01-23T12:34:56Z',  # optional, will default to now
            'metadata': {...}      # optional
        }

        Return None if message should be ignored (e.g., heartbeat, error)
        """
        pass

    async def _watchdog(self):
        """Monitor data receive timeout - force reconnect if no messages received"""
        while self.running:
            await asyncio.sleep(self.message_timeout)
            if not self.running or not self.ws:
                break

            elapsed = time.time() - self._last_message_time
            if self._last_message_time > 0 and elapsed > self.message_timeout:
                logger.warning(
                    f"[{self.provider_name}] No data received for {elapsed:.0f}s "
                    f"(timeout={self.message_timeout}s), forcing reconnect"
                )
                try:
                    await self.ws.close()
                except Exception:
                    pass
                break

    async def connect(self):
        """Connect to WebSocket and start receiving messages"""
        url = self.get_websocket_url()
        logger.info(f"[{self.provider_name}] Connecting to {url}")

        while self.running:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10
                ) as ws:
                    self.ws = ws
                    self._last_message_time = time.time()
                    logger.info(
                        f"[{self.provider_name}] Connected successfully "
                        f"(total msgs={self._message_count}, errors={self._error_count})"
                    )

                    # Send subscribe message
                    subscribe_msg = self.get_subscribe_message()
                    if subscribe_msg:
                        await ws.send(json.dumps(subscribe_msg))
                        logger.info(f"[{self.provider_name}] Sent subscribe message")

                    # Reset reconnect delay on successful connection
                    self.current_reconnect_delay = self.reconnect_delay

                    # Start watchdog for data timeout detection
                    self._watchdog_task = asyncio.create_task(self._watchdog())

                    try:
                        # Message receiving loop
                        async for message in ws:
                            if not self.running:
                                break

                            self._last_message_time = time.time()
                            self._message_count += 1

                            try:
                                # Parse message
                                parsed_data = self.parse_message(message)

                                if parsed_data:
                                    # Ensure provider is set
                                    if 'provider' not in parsed_data:
                                        parsed_data['provider'] = self.provider_name

                                    # Call callback
                                    await self.on_message(parsed_data)
                            except Exception as e:
                                self._error_count += 1
                                logger.error(
                                    f"[{self.provider_name}] Error parsing message: "
                                    f"{type(e).__name__}: {e}"
                                )
                                logger.debug(
                                    f"[{self.provider_name}] Raw message: "
                                    f"{str(message)[:500]}"
                                )
                    finally:
                        # Cancel watchdog when connection ends
                        if self._watchdog_task and not self._watchdog_task.done():
                            self._watchdog_task.cancel()
                            try:
                                await self._watchdog_task
                            except asyncio.CancelledError:
                                pass

            except WebSocketException as e:
                self._error_count += 1
                logger.error(
                    f"[{self.provider_name}] WebSocket error: "
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                )
                if self.running:
                    await self._reconnect()
            except Exception as e:
                self._error_count += 1
                logger.error(
                    f"[{self.provider_name}] Unexpected error: "
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                )
                if self.running:
                    await self._reconnect()

    async def _reconnect(self):
        """Reconnect with exponential backoff"""
        if not self.running:
            return

        logger.warning(
            f"[{self.provider_name}] Reconnecting in {self.current_reconnect_delay} seconds..."
        )
        await asyncio.sleep(self.current_reconnect_delay)

        # Exponential backoff
        self.current_reconnect_delay = min(
            self.current_reconnect_delay * 2,
            self.max_reconnect_delay
        )

    async def start(self):
        """Start the WebSocket client"""
        logger.info(f"[{self.provider_name}] Starting WebSocket client")
        self.running = True
        await self.connect()

    async def stop(self):
        """Stop the WebSocket client"""
        logger.info(
            f"[{self.provider_name}] Stopping WebSocket client "
            f"(total msgs={self._message_count}, errors={self._error_count})"
        )
        self.running = False
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        if self.ws:
            await self.ws.close()

    def is_connected(self) -> bool:
        """Check if WebSocket is currently connected"""
        return self.ws is not None and self.ws.open

    def get_health(self) -> Dict[str, Any]:
        """Get connection health metrics"""
        now = time.time()
        since_last = now - self._last_message_time if self._last_message_time > 0 else None
        return {
            "provider": self.provider_name,
            "connected": self.is_connected(),
            "running": self.running,
            "message_count": self._message_count,
            "error_count": self._error_count,
            "seconds_since_last_message": round(since_last, 1) if since_last else None,
            "message_timeout": self.message_timeout,
        }
