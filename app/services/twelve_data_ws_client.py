import json
from typing import Dict, Any, Optional
from datetime import datetime
from app.services.base_ws_client import BaseWebSocketClient
from app.utils.logger import app_logger as logger


class TwelveDataWebSocketClient(BaseWebSocketClient):
    """
    Twelve Data API WebSocket Client

    NOTE: You need to update this implementation based on actual Twelve Data WebSocket API documentation.
    This is a template that shows the structure. Please refer to:
    https://twelvedata.com/docs#websocket

    TODO:
    1. Verify WebSocket URL format
    2. Confirm subscribe message format
    3. Check actual message response format
    4. Map symbol names correctly
    """

    SYMBOL_MAPPING = {
        'gold': 'XAU/USD',     # Gold spot price vs USD
        'silver': 'XAG/USD',   # Silver spot price vs USD
        'usd_krw': 'USD/KRW'   # USD to KRW exchange rate
    }

    @property
    def provider_name(self) -> str:
        return "twelve_data"

    def get_websocket_url(self) -> str:
        """
        Get Twelve Data WebSocket URL
        """
        # Twelve Data WebSocket endpoint
        return f"wss://ws.twelvedata.com/v1/quotes/price?apikey={self.api_key}"

    def get_subscribe_message(self) -> Dict[str, Any]:
        """
        Get subscribe message for Twelve Data

        TODO: Verify actual subscribe message format from Twelve Data documentation
        """
        # Example format - VERIFY THIS WITH ACTUAL API DOCUMENTATION
        symbols = list(self.SYMBOL_MAPPING.values())

        return {
            "action": "subscribe",
            "params": {
                "symbols": ",".join(symbols)
            }
        }

    def parse_message(self, raw_message: str) -> Optional[Dict[str, Any]]:
        """
        Parse Twelve Data WebSocket message
        """
        try:
            data = json.loads(raw_message)

            # Log subscribe-status to see which symbols were accepted/rejected
            if data.get('event') == 'subscribe-status':
                logger.info(f"[{self.provider_name}] Subscribe status: {data}")
                return None

            # Log heartbeat (but don't spam)
            if data.get('event') == 'heartbeat':
                return None

            # Log any status or message responses
            if 'status' in data or 'message' in data:
                logger.info(f"[{self.provider_name}] Status message: {data}")
                return None

            # TODO: Verify actual field names from Twelve Data response
            # Example expected format:
            # {
            #   "event": "price",
            #   "symbol": "XAU/USD",
            #   "price": 2050.25,
            #   "bid": 2050.00,
            #   "ask": 2050.50,
            #   "timestamp": 1706012096
            # }

            symbol = data.get('symbol')
            if not symbol:
                # Log unexpected message format
                logger.debug(f"[{self.provider_name}] Message without symbol: {data}")
                return None

            # Map symbol back to asset_type
            asset_type = None
            for asset, sym in self.SYMBOL_MAPPING.items():
                if sym == symbol:
                    asset_type = asset
                    break

            if not asset_type:
                logger.warning(f"[{self.provider_name}] Unknown symbol received: {symbol}")
                return None

            # Extract price data
            price = data.get('price')
            if price is None:
                return None

            # Parse timestamp (if provided in seconds)
            timestamp = None
            if 'timestamp' in data:
                ts = data.get('timestamp')
                timestamp = datetime.fromtimestamp(ts) if ts else None

            return {
                'provider': self.provider_name,
                'asset_type': asset_type,
                'price': float(price),
                'bid': float(data.get('bid')) if 'bid' in data else None,
                'ask': float(data.get('ask')) if 'ask' in data else None,
                'volume': float(data.get('volume')) if 'volume' in data else None,
                'timestamp': timestamp,
                'metadata': {
                    'symbol': symbol,
                    'raw_data': data
                }
            }

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
        client = TwelveDataWebSocketClient(
            api_key=settings.TWELVE_DATA_API_KEY,
            on_message=test_callback
        )

        try:
            await client.start()
        except KeyboardInterrupt:
            await client.stop()

    asyncio.run(main())
