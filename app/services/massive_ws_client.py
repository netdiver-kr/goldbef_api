import json
from typing import Dict, Any, Optional
from datetime import datetime
import ssl
from app.services.base_ws_client import BaseWebSocketClient
from app.utils.logger import app_logger as logger


class MassiveWebSocketClient(BaseWebSocketClient):
    """
    Massive.com API WebSocket Client

    Based on official documentation: https://massive.com/docs/websocket/quickstart
    """

    # Polygon.io Forex symbols (with slash format)
    SYMBOL_MAPPING = {
        'gold': 'XAU/USD',       # Gold vs USD
        'silver': 'XAG/USD',     # Silver vs USD
        'platinum': 'XPT/USD',   # Platinum vs USD
        'palladium': 'XPD/USD',  # Palladium vs USD
        'usd_krw': 'USD/KRW',    # USD to KRW
        'jpy_krw': 'JPY/KRW',    # JPY to KRW
        'cny_krw': 'CNY/KRW',    # CNY to KRW
        'eur_krw': 'EUR/KRW',    # EUR to KRW
        'hkd_krw': 'HKD/KRW'     # HKD to KRW
    }

    def __init__(self, api_key: str, on_message):
        super().__init__(api_key, on_message)
        self.authenticated = False
        self.subscribed = False

    @property
    def provider_name(self) -> str:
        return "massive"

    async def send_subscribe_after_auth(self):
        """Send subscribe message after successful authentication"""
        import asyncio
        await asyncio.sleep(0.1)  # Small delay to ensure auth is processed
        if self.ws and self.authenticated and not self.subscribed:
            self.subscribed = True
            subscribe_msg = {
                "action": "subscribe",
                "params": ','.join(self.SYMBOL_MAPPING.values())
            }
            msg_json = json.dumps(subscribe_msg)
            logger.info(f"[{self.provider_name}] Sending subscribe message: {msg_json}")
            await self.ws.send(msg_json)
            logger.info(f"[{self.provider_name}] Subscribe message sent")

    def get_websocket_url(self) -> str:
        """
        Get Massive.com (Polygon.io) Forex WebSocket URL

        For Gold, Silver, USD/KRW - use Forex endpoint
        """
        # Forex endpoint for currency/commodity pairs
        return "wss://socket.polygon.io/forex"

    def get_subscribe_message(self) -> Dict[str, Any]:
        """
        Massive.com requires authentication first, then subscription
        This returns the auth message
        """
        if not self.authenticated:
            # First message: authenticate
            return {
                "action": "auth",
                "params": self.api_key
            }
        else:
            # Second message: subscribe to symbols
            symbols = ','.join(self.SYMBOL_MAPPING.values())
            return {
                "action": "subscribe",
                "params": symbols
            }

    def parse_message(self, raw_message: str) -> Optional[Dict[str, Any]]:
        """
        Parse Massive.com WebSocket message

        Message formats:
        - Auth response: [{"ev":"status","status":"auth_success","message":"authenticated"}]
        - Data: [{"ev":"C","pair":"XAUUSD","p":2050.25,"t":1234567890,...}]
        """
        try:
            # Log raw message for debugging
            logger.info(f"[{self.provider_name}] Raw message: {raw_message[:300]}")

            # Messages come as JSON arrays
            messages = json.loads(raw_message)

            if not isinstance(messages, list):
                messages = [messages]

            for data in messages:
                # Handle authentication response
                if data.get('ev') == 'status':
                    if data.get('status') == 'auth_success':
                        logger.info(f"[{self.provider_name}] Authentication successful")
                        self.authenticated = True
                        # Send subscribe message asynchronously
                        import asyncio
                        asyncio.create_task(self.send_subscribe_after_auth())
                        return None
                    elif data.get('status') == 'auth_failed':
                        logger.error(f"[{self.provider_name}] Authentication failed: {data.get('message')}")
                        return None
                    continue

                # Handle subscription confirmation
                if data.get('ev') in ['status', 'subscription']:
                    logger.info(f"[{self.provider_name}] Status: {data}")
                    continue

                # Handle forex/crypto data (ev = "C" for Forex quotes)
                if data.get('ev') == 'C':
                    pair = data.get('pair')
                    if not pair:
                        continue

                    # Map pair back to asset_type
                    # Polygon sends pair in format like "XAU/USD" or "XAUUSD"
                    # Normalize to slash format for matching
                    if '/' not in pair and len(pair) == 6:
                        # Convert "XAUUSD" to "XAU/USD"
                        symbol = f"{pair[:3]}/{pair[3:]}"
                    else:
                        symbol = pair

                    asset_type = None
                    for asset, sym in self.SYMBOL_MAPPING.items():
                        if sym == symbol:
                            asset_type = asset
                            break

                    if not asset_type:
                        logger.debug(f"[{self.provider_name}] Unknown symbol: {symbol}")
                        continue

                    # Extract price data
                    price = data.get('p')  # Current price
                    if price is None:
                        continue

                    # Parse timestamp (milliseconds)
                    timestamp = None
                    if 't' in data:
                        ts_ms = data.get('t')
                        timestamp = datetime.fromtimestamp(ts_ms / 1000) if ts_ms else None

                    return {
                        'provider': self.provider_name,
                        'asset_type': asset_type,
                        'price': float(price),
                        'bid': float(data.get('b')) if 'b' in data else None,
                        'ask': float(data.get('a')) if 'a' in data else None,
                        'volume': float(data.get('v')) if 'v' in data else None,
                        'timestamp': timestamp,
                        'metadata': {
                            'symbol': symbol,
                            'pair': pair,
                            'raw_data': data
                        }
                    }

                # Handle other event types
                logger.debug(f"[{self.provider_name}] Unhandled event: {data.get('ev')}")

            return None

        except json.JSONDecodeError as e:
            logger.error(f"[{self.provider_name}] Failed to decode JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"[{self.provider_name}] Error parsing message: {e}")
            logger.debug(f"[{self.provider_name}] Raw message: {raw_message}")
            return None


# For standalone testing
if __name__ == "__main__":
    import asyncio
    from app.config import get_settings

    async def test_callback(data):
        print(f"Received data: {data}")

    async def main():
        settings = get_settings()
        client = MassiveWebSocketClient(
            api_key=settings.MASSIVE_API_KEY,
            on_message=test_callback
        )

        try:
            await client.start()
        except KeyboardInterrupt:
            await client.stop()

    asyncio.run(main())
