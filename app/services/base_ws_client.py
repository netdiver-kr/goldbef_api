import asyncio
import json
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
                    logger.success(f"[{self.provider_name}] Connected successfully")

                    # Send subscribe message
                    subscribe_msg = self.get_subscribe_message()
                    if subscribe_msg:
                        await ws.send(json.dumps(subscribe_msg))
                        logger.info(f"[{self.provider_name}] Sent subscribe message")

                    # Reset reconnect delay on successful connection
                    self.current_reconnect_delay = self.reconnect_delay

                    # Message receiving loop
                    async for message in ws:
                        if not self.running:
                            break

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
                            logger.error(f"[{self.provider_name}] Error parsing message: {e}")
                            logger.debug(f"[{self.provider_name}] Raw message: {message}")

            except WebSocketException as e:
                logger.error(f"[{self.provider_name}] WebSocket error: {e}")
                if self.running:
                    await self._reconnect()
            except Exception as e:
                logger.error(f"[{self.provider_name}] Unexpected error: {e}")
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
        logger.info(f"[{self.provider_name}] Stopping WebSocket client")
        self.running = False
        if self.ws:
            await self.ws.close()

    def is_connected(self) -> bool:
        """Check if WebSocket is currently connected"""
        return self.ws is not None and self.ws.open
