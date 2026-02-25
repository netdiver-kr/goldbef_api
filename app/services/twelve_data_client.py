"""
Twelve Data HTTP Polling Client

Uses REST API instead of WebSocket for broader symbol support.
Fetches real-time quotes for Gold, Silver, and USD/KRW.
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from loguru import logger


class TwelveDataClient:
    """
    HTTP-based client that polls Twelve Data REST API for real-time quotes
    """

    # Symbol mapping: asset_type -> API symbol
    SYMBOL_MAPPING = {
        'gold': 'XAU/USD',
        'silver': 'XAG/USD',
        'platinum': 'XPT/USD',
        'palladium': 'XPD/USD',
        'usd_krw': 'USD/KRW',
        'btc_usd': 'BTC/USD',
        'usd_jpy': 'USD/JPY',
    }

    def __init__(self, api_key: str, callback: Optional[Callable] = None):
        self.provider_name = "twelve_data"
        self.api_key = api_key
        self.callback = callback
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.fetch_interval = 30.0  # 30 second interval
        self.base_url = "https://api.twelvedata.com"

    async def start(self):
        """Start the HTTP polling client"""
        logger.info(f"[{self.provider_name}] Starting Twelve Data HTTP client")
        self.running = True
        self.session = aiohttp.ClientSession()

        try:
            while self.running:
                try:
                    await self._fetch_quotes()
                except Exception as e:
                    logger.error(f"[{self.provider_name}] Fetch error: {e}")

                await asyncio.sleep(self.fetch_interval)
        finally:
            if self.session:
                await self.session.close()

    async def stop(self):
        """Stop the client"""
        logger.info(f"[{self.provider_name}] Stopping Twelve Data HTTP client")
        self.running = False

    async def _fetch_quotes(self):
        """Fetch real-time quotes for all symbols"""
        symbols = ",".join(self.SYMBOL_MAPPING.values())
        url = f"{self.base_url}/price"

        params = {
            "symbol": symbols,
            "apikey": self.api_key
        }

        try:
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.warning(f"[{self.provider_name}] HTTP {response.status}")
                    return

                data = await response.json()

                # Handle API errors
                if "code" in data and data.get("status") == "error":
                    logger.warning(f"[{self.provider_name}] API error: {data.get('message')}")
                    return

                await self._process_response(data)

        except asyncio.TimeoutError:
            logger.warning(f"[{self.provider_name}] Request timeout")
        except aiohttp.ClientError as e:
            logger.error(f"[{self.provider_name}] Client error: {e}")

    async def _process_response(self, data: Dict[str, Any]):
        """Process API response and call callback for each price"""
        timestamp = datetime.utcnow()

        # When requesting multiple symbols, response is a dict with symbol keys
        # When requesting single symbol, response is a single object
        if isinstance(data, dict) and "price" in data:
            # Single symbol response
            await self._process_single_quote(data, timestamp)
        elif isinstance(data, dict):
            # Multiple symbols response
            for symbol, quote_data in data.items():
                if isinstance(quote_data, dict) and "price" in quote_data:
                    await self._process_single_quote(quote_data, timestamp, symbol)
                elif isinstance(quote_data, dict) and quote_data.get("status") == "error":
                    logger.debug(f"[{self.provider_name}] Symbol {symbol} error: {quote_data.get('message')}")

    async def _process_single_quote(self, quote_data: Dict[str, Any], timestamp: datetime, symbol: str = None):
        """Process a single quote and call callback"""
        try:
            # Get symbol from response or parameter
            sym = symbol or quote_data.get("symbol")
            if not sym:
                return

            # Map symbol back to asset_type
            asset_type = None
            for asset, api_symbol in self.SYMBOL_MAPPING.items():
                if api_symbol == sym:
                    asset_type = asset
                    break

            if not asset_type:
                logger.debug(f"[{self.provider_name}] Unknown symbol: {sym}")
                return

            price = float(quote_data.get("price", 0))
            if price <= 0:
                return

            price_data = {
                'provider': self.provider_name,
                'asset_type': asset_type,
                'price': price,
                'bid': None,  # REST API doesn't provide bid/ask
                'ask': None,
                'volume': None,
                'timestamp': timestamp,
                'metadata': {
                    'symbol': sym,
                    'source': 'twelvedata.com'
                }
            }

            if self.callback:
                await self.callback(price_data)

            logger.debug(f"[{self.provider_name}] {sym}: {price:.4f}")

        except Exception as e:
            logger.error(f"[{self.provider_name}] Error processing quote: {e}")

    def is_connected(self) -> bool:
        """Check if client is running"""
        return self.running


# For standalone testing
if __name__ == "__main__":
    from app.config import get_settings

    async def test_callback(data):
        print(f"Received: {data['asset_type']} = {data['price']:.4f}")

    async def main():
        settings = get_settings()
        client = TwelveDataClient(
            api_key=settings.TWELVE_DATA_API_KEY,
            callback=test_callback
        )

        try:
            await asyncio.wait_for(client.start(), timeout=10)
        except asyncio.TimeoutError:
            await client.stop()

    asyncio.run(main())
