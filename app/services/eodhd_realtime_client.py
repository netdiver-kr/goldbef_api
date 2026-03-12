"""
EODHD Real-Time REST Polling Client

Polls EODHD Real-Time API for indices and commodity pairs not available
on the WebSocket channels. Updates every 5 minutes.

Assets handled:
  - INDX: S&P 500, VIX, KOSPI, KOSDAQ, Dollar Index (DXY)
  - FOREX commodities: Copper
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone
from app.utils.logger import app_logger as logger


class EODHDRealtimeClient:
    """
    HTTP polling client for EODHD Real-Time API.
    Handles indices (INDX) and commodity forex pairs not on WebSocket.
    """

    # asset_type -> EODHD ticker (INDX/FOREX format)
    SYMBOL_MAPPING = {
        'kospi': 'KS11.INDX',
        'kosdaq': 'KQ11.INDX',
        'sp500': 'GSPC.INDX',
        'vix': 'VIX.INDX',
        'dxy': 'DXY.INDX',
        'copper': 'XCUUSD.FOREX',
    }

    def __init__(self, api_key: str, callback: Optional[Callable] = None,
                 poll_interval: float = 300.0):
        self.provider_name = "eodhd_realtime"
        self.api_key = api_key
        self.callback = callback
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.poll_interval = poll_interval  # 5 minutes default
        self.base_url = "https://eodhd.com/api/real-time"

        # Reverse mapping for quick lookup
        self._reverse_map = {v: k for k, v in self.SYMBOL_MAPPING.items()}

    async def start(self):
        """Start the HTTP polling loop"""
        logger.info(f"[{self.provider_name}] Starting EODHD Real-Time client "
                     f"(interval: {self.poll_interval}s, symbols: {len(self.SYMBOL_MAPPING)})")
        self.running = True
        self.session = aiohttp.ClientSession()

        try:
            # Fetch immediately on start
            await self._fetch_quotes()

            while self.running:
                await asyncio.sleep(self.poll_interval)
                if self.running:
                    try:
                        await self._fetch_quotes()
                    except Exception as e:
                        logger.error(f"[{self.provider_name}] Fetch error: {e}")
        finally:
            if self.session:
                await self.session.close()

    async def stop(self):
        """Stop the polling client"""
        logger.info(f"[{self.provider_name}] Stopping EODHD Real-Time client")
        self.running = False

    async def _fetch_quotes(self):
        """Fetch real-time quotes for all symbols in a single batch request"""
        symbols = list(self.SYMBOL_MAPPING.values())
        if not symbols:
            return

        # EODHD batch: first symbol in URL path, rest via s= parameter
        primary = symbols[0]
        additional = ','.join(symbols[1:]) if len(symbols) > 1 else ''

        url = f"{self.base_url}/{primary}"
        params = {
            'api_token': self.api_key,
            'fmt': 'json',
        }
        if additional:
            params['s'] = additional

        try:
            async with self.session.get(
                url, params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    logger.warning(f"[{self.provider_name}] HTTP {response.status}")
                    return

                data = await response.json()
                await self._process_response(data)

        except asyncio.TimeoutError:
            logger.warning(f"[{self.provider_name}] Request timeout")
        except aiohttp.ClientError as e:
            logger.error(f"[{self.provider_name}] Client error: {e}")

    async def _process_response(self, data):
        """Process API response (single object or list of objects)"""
        # Single symbol returns dict, multiple returns list
        if isinstance(data, dict):
            items = [data]
        elif isinstance(data, list):
            items = data
        else:
            logger.warning(f"[{self.provider_name}] Unexpected response type: {type(data)}")
            return

        processed = 0
        for item in items:
            if not isinstance(item, dict):
                continue

            code = item.get('code')
            if not code:
                continue

            asset_type = self._reverse_map.get(code)
            if not asset_type:
                logger.debug(f"[{self.provider_name}] Unknown code: {code}")
                continue

            # Use close price, fall back to previousClose when market is closed
            close_val = item.get('close')
            used_prev_close = False
            if close_val is None or close_val == 'NA':
                prev_val = item.get('previousClose')
                if prev_val is not None and prev_val != 'NA':
                    close_val = prev_val
                    used_prev_close = True
                    logger.debug(f"[{self.provider_name}] {code}: using previousClose as fallback")
                else:
                    logger.debug(f"[{self.provider_name}] {code}: no data (NA)")
                    continue

            try:
                price = float(close_val)
            except (ValueError, TypeError):
                continue

            if price <= 0:
                continue

            # Parse timestamp
            timestamp = None
            ts_val = item.get('timestamp')
            if ts_val and ts_val != 'NA':
                try:
                    timestamp = datetime.fromtimestamp(int(ts_val), tz=timezone.utc)
                except (ValueError, TypeError, OSError):
                    pass

            # If using previousClose, timestamp is unavailable — use current time
            if used_prev_close and timestamp is None:
                timestamp = datetime.now(timezone.utc)

            # Build open/high/low for metadata
            metadata = {'symbol': code, 'source': 'eodhd-realtime'}
            for field in ('open', 'high', 'low', 'previousClose', 'change', 'change_p'):
                val = item.get(field)
                if val is not None and val != 'NA':
                    try:
                        metadata[field] = float(val)
                    except (ValueError, TypeError):
                        pass

            price_data = {
                'provider': 'eodhd',
                'asset_type': asset_type,
                'price': price,
                'bid': None,
                'ask': None,
                'volume': None,
                'timestamp': timestamp or datetime.now(timezone.utc),
                'metadata': metadata,
            }

            if self.callback:
                await self.callback(price_data)

            processed += 1
            logger.debug(f"[{self.provider_name}] {code} ({asset_type}): {price}")

        if processed > 0:
            logger.info(f"[{self.provider_name}] Updated {processed}/{len(items)} symbols")

    def is_connected(self) -> bool:
        return self.running


# For standalone testing
if __name__ == "__main__":
    from app.config import get_settings

    async def test_callback(data):
        print(f"  {data['asset_type']:15s} = {data['price']:.4f}  ({data['metadata'].get('symbol')})")

    async def main():
        settings = get_settings()
        client = EODHDRealtimeClient(
            api_key=settings.EODHD_API_KEY,
            callback=test_callback,
            poll_interval=10.0,  # shorter for testing
        )

        try:
            await asyncio.wait_for(client.start(), timeout=15)
        except asyncio.TimeoutError:
            await client.stop()

    asyncio.run(main())
