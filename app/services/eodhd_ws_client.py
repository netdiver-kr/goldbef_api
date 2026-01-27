import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.services.base_ws_client import BaseWebSocketClient
from app.utils.logger import app_logger as logger


class EODHDWebSocketClient(BaseWebSocketClient):
    """
    EODHD API WebSocket Client

    NOTE: You need to update this implementation based on actual EODHD WebSocket API documentation.
    This is a template that shows the structure. Please refer to:
    https://eodhistoricaldata.com/financial-apis/

    TODO:
    1. Verify WebSocket URL format
    2. Confirm subscribe message format
    3. Check actual message response format
    4. Map symbol names correctly (e.g., XAUUSD for gold, XAGUSD for silver, USDKRW for exchange rate)
    """

    SYMBOL_MAPPING = {
        'gold': 'XAUUSD',     # Gold spot price vs USD
        'silver': 'XAGUSD',   # Silver spot price vs USD
        'usd_krw': 'USDKRW'   # USD to KRW exchange rate
    }

    @property
    def provider_name(self) -> str:
        return "eodhd"

    def get_websocket_url(self) -> str:
        """
        Get EODHD WebSocket URL
        """
        # EODHD WebSocket endpoint for real-time forex data
        return f"wss://ws.eodhistoricaldata.com/ws/forex?api_token={self.api_key}"

    def get_subscribe_message(self) -> Dict[str, Any]:
        """
        Get subscribe message for EODHD

        EODHD requires action and symbols as strings
        """
        # Symbols as comma-separated string
        symbols = ','.join(self.SYMBOL_MAPPING.values())

        return {
            "action": "subscribe",
            "symbols": symbols
        }

    def parse_message(self, raw_message: str) -> Optional[Dict[str, Any]]:
        """
        Parse EODHD WebSocket message

        TODO: Update this based on actual EODHD message format
        """
        try:
            # Log raw message for debugging (only first 200 chars to reduce noise)
            logger.debug(f"[{self.provider_name}] Raw message: {raw_message[:200]}")

            data = json.loads(raw_message)

            # Log subscription status/messages
            if 'status' in data or 'message' in data or 'status_code' in data:
                logger.info(f"[{self.provider_name}] Status: {data}")
                return None

            # TODO: Verify actual field names from EODHD response
            # Example expected format:
            # {
            #   "s": "XAUUSD",
            #   "p": 2050.25,
            #   "b": 2050.00,
            #   "a": 2050.50,
            #   "t": 1706012096000
            # }

            symbol = data.get('s') or data.get('symbol')
            if not symbol:
                return None

            # Map symbol back to asset_type
            asset_type = None
            for asset, sym in self.SYMBOL_MAPPING.items():
                if sym == symbol:
                    asset_type = asset
                    break

            if not asset_type:
                logger.warning(f"[{self.provider_name}] Unknown symbol: {symbol}")
                return None

            # Extract price data
            # EODHD provides 'a' (ask) and 'b' (bid), not direct 'p' (price)
            price = data.get('p') or data.get('price')
            if price is None:
                # Calculate mid-price from bid and ask
                bid = data.get('b') or data.get('bid')
                ask = data.get('a') or data.get('ask')
                if bid is not None and ask is not None:
                    price = (float(bid) + float(ask)) / 2
                elif bid is not None:
                    price = float(bid)
                elif ask is not None:
                    price = float(ask)
                else:
                    logger.debug(f"[{self.provider_name}] No price data in message: {data}")
                    return None

            # Parse timestamp (if provided in milliseconds) - use UTC
            timestamp = None
            if 't' in data or 'timestamp' in data:
                ts_ms = data.get('t') or data.get('timestamp')
                timestamp = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) if ts_ms else None

            return {
                'provider': self.provider_name,
                'asset_type': asset_type,
                'price': float(price),
                'bid': float(data.get('b') or data.get('bid')) if ('b' in data or 'bid' in data) else None,
                'ask': float(data.get('a') or data.get('ask')) if ('a' in data or 'ask' in data) else None,
                'volume': float(data.get('v') or data.get('volume')) if ('v' in data or 'volume' in data) else None,
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
        client = EODHDWebSocketClient(
            api_key=settings.EODHD_API_KEY,
            on_message=test_callback
        )

        try:
            await client.start()
        except KeyboardInterrupt:
            await client.stop()

    asyncio.run(main())
