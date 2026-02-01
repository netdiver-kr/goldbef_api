"""
NauGold Client

Crawls https://naugold.com/naugold_td to get real-time price data.
Replaces the previous Massive MSSQL polling approach.
"""

import asyncio
import re
import aiohttp
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from app.utils.logger import app_logger as logger


class NaugoldClient:
    """
    Client that crawls naugold.com/naugold_td for real-time price data.

    Replaces MassiveMSSQLClient. Keeps provider name 'massive' for
    backward compatibility with database records and frontend config.
    """

    # HTML span ID prefix -> (asset_type, display_symbol)
    PRICE_FIELDS = {
        'xau': ('gold', 'XAU/USD'),
        'xag': ('silver', 'XAG/USD'),
        'xpt': ('platinum', 'XPT/USD'),
        'xpd': ('palladium', 'XPD/USD'),
        'krw': ('usd_krw', 'USD/KRW'),
        'jpy': ('jpy_krw', 'JPY/KRW'),
        'cny': ('cny_krw', 'CNY/KRW'),
        'eur': ('eur_krw', 'EUR/KRW'),
        'hkd': ('hkd_krw', 'HKD/KRW'),
    }

    URL = "https://naugold.com/naugold_td"

    def __init__(self, on_message: Callable):
        self.on_message = on_message
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.poll_interval = 3.0
        self.last_prices: Dict[str, Dict] = {}

    @property
    def provider_name(self) -> str:
        return "massive"

    def _parse_price(self, text: str) -> Optional[float]:
        """Parse a price string like '4,902.18' into a float"""
        try:
            return float(text.replace(',', ''))
        except (ValueError, TypeError):
            return None

    def _parse_html(self, html: str) -> list:
        """Parse HTML and extract bid/ask prices from span elements"""
        results = []
        timestamp = datetime.now()

        for prefix, (asset_type, display_symbol) in self.PRICE_FIELDS.items():
            bid_match = re.search(
                rf'id="{prefix}_bid"[^>]*>([\d,]+\.?\d*)</span>', html
            )
            ask_match = re.search(
                rf'id="{prefix}_ask"[^>]*>([\d,]+\.?\d*)</span>', html
            )

            if not (bid_match or ask_match):
                continue

            bid = self._parse_price(bid_match.group(1)) if bid_match else None
            ask = self._parse_price(ask_match.group(1)) if ask_match else None

            # Use ask as the price (fallback to bid if ask unavailable)
            if ask:
                price = ask
            elif bid:
                price = bid
            else:
                continue

            # Skip if price unchanged
            last = self.last_prices.get(prefix)
            if (last and last.get('price') == price
                    and last.get('bid') == bid and last.get('ask') == ask):
                continue

            self.last_prices[prefix] = {'price': price, 'bid': bid, 'ask': ask}

            results.append({
                'provider': self.provider_name,
                'asset_type': asset_type,
                'price': price,
                'bid': bid,
                'ask': ask,
                'volume': None,
                'timestamp': timestamp,
                'metadata': {
                    'symbol': display_symbol,
                    'source': 'naugold.com'
                }
            })

        return results

    async def _fetch_and_parse(self):
        """Fetch HTML and parse prices"""
        try:
            async with self.session.get(
                self.URL,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.warning(
                        f"[{self.provider_name}] HTTP {response.status} from naugold.com"
                    )
                    return

                html = await response.text()
                prices = self._parse_html(html)

                for data in prices:
                    await self.on_message(data)

                if prices:
                    logger.debug(
                        f"[{self.provider_name}] Parsed {len(prices)} updates from naugold.com"
                    )

        except asyncio.TimeoutError:
            logger.warning(f"[{self.provider_name}] Timeout fetching naugold.com")
        except aiohttp.ClientError as e:
            logger.error(f"[{self.provider_name}] Client error: {e}")
        except Exception as e:
            logger.error(f"[{self.provider_name}] Error: {e}")

    async def start(self):
        """Start the polling client"""
        if self.running:
            return

        self.running = True
        logger.info(
            f"[{self.provider_name}] Starting NauGold client "
            f"(url: {self.URL}, interval: {self.poll_interval}s)"
        )

        self.session = aiohttp.ClientSession()

        try:
            while self.running:
                await self._fetch_and_parse()
                await asyncio.sleep(self.poll_interval)
        finally:
            if self.session:
                await self.session.close()
                self.session = None

    async def stop(self):
        """Stop the polling client"""
        self.running = False
        logger.info(f"[{self.provider_name}] NauGold client stopped")


# For standalone testing
if __name__ == "__main__":
    async def test_callback(data):
        print(
            f"Received: {data['asset_type']} = {data['price']:.4f} "
            f"(bid: {data.get('bid')}, ask: {data.get('ask')})"
        )

    async def main():
        client = NaugoldClient(on_message=test_callback)
        try:
            await asyncio.wait_for(client.start(), timeout=10)
        except asyncio.TimeoutError:
            await client.stop()

    asyncio.run(main())
