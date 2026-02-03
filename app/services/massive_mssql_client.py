"""
Massive.com MSSQL Client

Reads price data from MSSQL database (td_price_api table) that is
populated by a separate data collection service.
"""

import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import pyodbc

from app.config import get_settings
from app.utils.logger import app_logger as logger


class MassiveMSSQLClient:
    """
    Client that reads Massive.com price data from MSSQL database.

    The data is collected by massive_mssql_rest.py and stored in td_price_api table.
    This client polls the database periodically to get the latest prices.
    """

    # Symbol mapping: MSSQL symbol -> (asset_type, display_symbol)
    SYMBOL_MAPPING = {
        'XAUUSD': ('gold', 'XAU/USD'),
        'XAGUSD': ('silver', 'XAG/USD'),
        'XPTUSD': ('platinum', 'XPT/USD'),
        'XPDUSD': ('palladium', 'XPD/USD'),
        'USDKRW': ('usd_krw', 'USD/KRW'),
        'JPYKRW': ('jpy_krw', 'JPY/KRW'),
        'CNHKRW': ('cny_krw', 'CNY/KRW'),
        'EURKRW': ('eur_krw', 'EUR/KRW'),
        'HKDKRW': ('hkd_krw', 'HKD/KRW'),
    }

    def __init__(self, on_message: Callable):
        self.on_message = on_message
        self.settings = get_settings()
        self.running = False
        self.connection = None
        self.poll_interval = self.settings.PRICE_UPDATE_INTERVAL
        self.last_prices: Dict[str, Dict] = {}

    @property
    def provider_name(self) -> str:
        return "massive"

    def _get_connection_string(self) -> str:
        """Build MSSQL connection string"""
        return (
            f"DRIVER={{{self.settings.MSSQL_DRIVER}}};"
            f"SERVER={self.settings.MSSQL_SERVER};"
            f"DATABASE={self.settings.MSSQL_DATABASE};"
            f"Trusted_Connection={self.settings.MSSQL_TRUSTED_CONNECTION};"
        )

    def _connect(self) -> bool:
        """Establish connection to MSSQL database"""
        try:
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass

            connection_string = self._get_connection_string()
            self.connection = pyodbc.connect(connection_string, timeout=10)
            logger.info(f"[{self.provider_name}] Connected to MSSQL database")
            return True
        except Exception as e:
            logger.error(f"[{self.provider_name}] Failed to connect to MSSQL: {e}")
            return False

    def _fetch_prices(self) -> list:
        """Fetch latest prices from td_price_api table"""
        try:
            if not self.connection:
                if not self._connect():
                    return []

            cursor = self.connection.cursor()

            # Build query for symbols we care about
            symbols = list(self.SYMBOL_MAPPING.keys())
            placeholders = ','.join(['?' for _ in symbols])

            query = f"""
                SELECT [string], [price], [bid], [ask]
                FROM [dbo].[td_price_api]
                WHERE [string] IN ({placeholders})
            """

            cursor.execute(query, symbols)
            rows = cursor.fetchall()
            cursor.close()

            return rows
        except pyodbc.Error as e:
            logger.error(f"[{self.provider_name}] Database error: {e}")
            # Try to reconnect on next poll
            self.connection = None
            return []
        except Exception as e:
            logger.error(f"[{self.provider_name}] Error fetching prices: {e}")
            return []

    def _process_row(self, row) -> Optional[Dict[str, Any]]:
        """Process a database row into price data format"""
        try:
            symbol = row[0]  # string column
            price = row[1]
            bid = row[2]
            ask = row[3]

            if symbol not in self.SYMBOL_MAPPING:
                return None

            asset_type, display_symbol = self.SYMBOL_MAPPING[symbol]

            # Check if price actually changed
            last = self.last_prices.get(symbol)
            if last and last.get('price') == price and last.get('bid') == bid and last.get('ask') == ask:
                return None

            # Store current price
            self.last_prices[symbol] = {'price': price, 'bid': bid, 'ask': ask}

            return {
                'provider': self.provider_name,
                'asset_type': asset_type,
                'price': float(price) if price else None,
                'bid': float(bid) if bid else None,
                'ask': float(ask) if ask else None,
                'volume': None,
                'timestamp': datetime.now(),
                'metadata': {
                    'symbol': display_symbol,
                    'source': 'mssql'
                }
            }
        except Exception as e:
            logger.error(f"[{self.provider_name}] Error processing row: {e}")
            return None

    async def _poll_loop(self):
        """Main polling loop"""
        logger.info(f"[{self.provider_name}] Starting MSSQL polling (interval: {self.poll_interval}s)")

        while self.running:
            try:
                # Fetch prices from database (run in executor to avoid blocking)
                loop = asyncio.get_event_loop()
                rows = await loop.run_in_executor(None, self._fetch_prices)

                for row in rows:
                    data = self._process_row(row)
                    if data:
                        await self.on_message(data)

            except Exception as e:
                logger.error(f"[{self.provider_name}] Poll error: {e}")

            # Wait for next poll
            await asyncio.sleep(self.poll_interval)

    async def start(self):
        """Start the MSSQL polling client"""
        if self.running:
            return

        self.running = True
        logger.info(f"[{self.provider_name}] Starting MSSQL client")

        # Initial connection
        loop = asyncio.get_event_loop()
        connected = await loop.run_in_executor(None, self._connect)

        if not connected:
            logger.warning(f"[{self.provider_name}] Initial connection failed, will retry in poll loop")

        # Start polling loop
        await self._poll_loop()

    async def stop(self):
        """Stop the MSSQL polling client"""
        self.running = False

        if self.connection:
            try:
                self.connection.close()
                logger.info(f"[{self.provider_name}] Database connection closed")
            except:
                pass
            self.connection = None

        logger.info(f"[{self.provider_name}] MSSQL client stopped")


# For standalone testing
if __name__ == "__main__":
    async def test_callback(data):
        print(f"Received data: {data}")

    async def main():
        client = MassiveMSSQLClient(on_message=test_callback)
        try:
            await client.start()
        except KeyboardInterrupt:
            await client.stop()

    asyncio.run(main())
