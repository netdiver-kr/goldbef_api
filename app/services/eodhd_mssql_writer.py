"""
EODHD → MSSQL Writer

Writes EODHD averaged price data to MSSQL td_price_api table.
Replaces Massive.com as the data source for precious metals and USD/KRW.

Symbols handled: XAUUSD, XAGUSD, XPTUSD, XPDUSD, USDKRW
(Massive.com continues to handle: JPYKRW, CNHKRW, EURKRW, HKDKRW)
"""

import asyncio
from typing import Dict, Any, List, Optional
import pyodbc

from app.config import get_settings
from app.utils.logger import app_logger as logger


class EODHDMSSQLWriter:
    """Writes EODHD averaged data to MSSQL td_price_api table (UPDATE pattern)."""

    # asset_type → MSSQL symbol
    SYMBOL_MAPPING = {
        'gold': 'XAUUSD',
        'silver': 'XAGUSD',
        'platinum': 'XPTUSD',
        'palladium': 'XPDUSD',
        'usd_krw': 'USDKRW',
    }

    def __init__(self):
        self.settings = get_settings()
        self.connection: Optional[pyodbc.Connection] = None

    def _get_connection_string(self) -> str:
        return (
            f"DRIVER={{{self.settings.MSSQL_DRIVER}}};"
            f"SERVER={self.settings.MSSQL_SERVER};"
            f"DATABASE={self.settings.MSSQL_DATABASE};"
            f"Trusted_Connection={self.settings.MSSQL_TRUSTED_CONNECTION};"
        )

    def _connect(self) -> bool:
        try:
            if self.connection:
                try:
                    self.connection.close()
                except Exception:
                    pass

            self.connection = pyodbc.connect(
                self._get_connection_string(), timeout=10
            )
            logger.info("[EODHD-MSSQL] Connected to MSSQL database")
            return True
        except Exception as e:
            logger.error(f"[EODHD-MSSQL] Connection failed: {e}")
            self.connection = None
            return False

    def _execute_updates(self, records: List[Dict[str, Any]]):
        """Execute batch UPDATE on td_price_api (synchronous, called via executor)."""
        if not self.connection:
            if not self._connect():
                return

        try:
            cursor = self.connection.cursor()

            for record in records:
                asset_type = record.get('asset_type')
                symbol = self.SYMBOL_MAPPING.get(asset_type)
                if not symbol:
                    continue

                price = record.get('price')
                bid = record.get('bid')
                ask = record.get('ask')

                if price is None:
                    continue

                # Use mid-price if bid/ask missing
                if bid is None:
                    bid = price
                if ask is None:
                    ask = price

                cursor.execute(
                    "UPDATE [dbo].[td_price_api] "
                    "SET [price] = ?, [bid] = ?, [ask] = ? "
                    "WHERE [string] = ?",
                    (float(price), float(bid), float(ask), symbol)
                )

            self.connection.commit()
            cursor.close()

        except pyodbc.Error as e:
            logger.error(f"[EODHD-MSSQL] Database error: {e}")
            self.connection = None
        except Exception as e:
            logger.error(f"[EODHD-MSSQL] Write error: {e}")

    async def write_batch(self, batch: List[Dict[str, Any]]):
        """Async wrapper - write batch of averaged data to MSSQL."""
        # Filter to only symbols we handle
        relevant = [r for r in batch if r.get('asset_type') in self.SYMBOL_MAPPING]
        if not relevant:
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._execute_updates, relevant)

    def close(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
            logger.info("[EODHD-MSSQL] Connection closed")
