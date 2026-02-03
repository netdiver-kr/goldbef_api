"""
Price Aggregator

Collects price data and emits 3-second averages to reduce noise
and provide smoother price updates.
"""

import asyncio
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from app.config import get_settings
from app.utils.logger import app_logger as logger


@dataclass
class PriceBuffer:
    """Buffer for collecting prices within an interval"""
    prices: List[float] = field(default_factory=list)
    bids: List[float] = field(default_factory=list)
    asks: List[float] = field(default_factory=list)
    volumes: List[float] = field(default_factory=list)
    last_metadata: Optional[Dict] = None
    last_timestamp: Optional[datetime] = None

    def add(self, price: float, bid: float = None, ask: float = None,
            volume: float = None, metadata: Dict = None, timestamp: datetime = None):
        """Add a price point to the buffer"""
        if price is not None:
            self.prices.append(price)
        if bid is not None:
            self.bids.append(bid)
        if ask is not None:
            self.asks.append(ask)
        if volume is not None:
            self.volumes.append(volume)
        if metadata:
            self.last_metadata = metadata
        if timestamp:
            self.last_timestamp = timestamp

    def get_average(self) -> Dict[str, Any]:
        """Calculate averages from buffered data"""
        result = {}

        if self.prices:
            result['price'] = sum(self.prices) / len(self.prices)
        if self.bids:
            result['bid'] = sum(self.bids) / len(self.bids)
        if self.asks:
            result['ask'] = sum(self.asks) / len(self.asks)
        if self.volumes:
            result['volume'] = sum(self.volumes) / len(self.volumes)
        if self.last_metadata:
            result['metadata'] = self.last_metadata
        if self.last_timestamp:
            result['timestamp'] = self.last_timestamp
        else:
            result['timestamp'] = datetime.now()

        return result

    def clear(self):
        """Clear the buffer"""
        self.prices.clear()
        self.bids.clear()
        self.asks.clear()
        self.volumes.clear()
        self.last_metadata = None
        self.last_timestamp = None

    def has_data(self) -> bool:
        """Check if buffer has any data"""
        return len(self.prices) > 0


class PriceAggregator:
    """
    Aggregates price data over a configurable interval and emits averages.

    This helps reduce noise from high-frequency price updates and provides
    smoother data for the frontend.
    """

    def __init__(self, on_aggregated: Callable, interval: float = None):
        """
        Initialize the aggregator.

        Args:
            on_aggregated: Callback function to receive aggregated data
            interval: Aggregation interval in seconds (default: from settings)
        """
        self.settings = get_settings()
        self.interval = interval or self.settings.PRICE_UPDATE_INTERVAL
        self.on_aggregated = on_aggregated

        # Buffers: {(provider, asset_type): PriceBuffer}
        self.buffers: Dict[tuple, PriceBuffer] = defaultdict(PriceBuffer)

        # Track last emitted values to avoid duplicates
        self.last_emitted: Dict[tuple, Dict] = {}

        self.running = False
        self._task = None

    async def add_price(self, data: Dict[str, Any]):
        """
        Add a price data point to the buffer.

        Args:
            data: Price data dict with provider, asset_type, price, etc.
        """
        try:
            provider = data.get('provider')
            asset_type = data.get('asset_type')
            price = data.get('price')

            if not all([provider, asset_type, price]):
                return

            key = (provider, asset_type)
            buffer = self.buffers[key]

            buffer.add(
                price=price,
                bid=data.get('bid'),
                ask=data.get('ask'),
                volume=data.get('volume'),
                metadata=data.get('metadata'),
                timestamp=data.get('timestamp')
            )

        except Exception as e:
            logger.error(f"[Aggregator] Error adding price: {e}")

    async def _emit_aggregates(self):
        """Calculate and emit aggregated data for all buffers"""
        for key, buffer in list(self.buffers.items()):
            if not buffer.has_data():
                continue

            try:
                provider, asset_type = key
                avg_data = buffer.get_average()

                # Check if data actually changed significantly
                last = self.last_emitted.get(key)
                if last:
                    price_change = abs(avg_data.get('price', 0) - last.get('price', 0))
                    # Skip if price change is negligible (less than 0.0001%)
                    if last.get('price') and price_change / last['price'] < 0.000001:
                        buffer.clear()
                        continue

                # Build aggregated data
                aggregated = {
                    'provider': provider,
                    'asset_type': asset_type,
                    **avg_data
                }

                # Store for comparison
                self.last_emitted[key] = avg_data

                # Emit the aggregated data
                await self.on_aggregated(aggregated)

                logger.debug(
                    f"[Aggregator] Emitted: {provider}/{asset_type} = {avg_data.get('price', 0):.4f} "
                    f"(samples: {len(buffer.prices)})"
                )

            except Exception as e:
                logger.error(f"[Aggregator] Error emitting aggregate for {key}: {e}")

            finally:
                buffer.clear()

    async def _aggregation_loop(self):
        """Main loop that periodically emits aggregated data"""
        logger.info(f"[Aggregator] Starting with {self.interval}s interval")

        while self.running:
            try:
                await asyncio.sleep(self.interval)
                await self._emit_aggregates()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Aggregator] Loop error: {e}")

    async def start(self):
        """Start the aggregation loop"""
        if self.running:
            return

        self.running = True
        self._task = asyncio.create_task(self._aggregation_loop())
        logger.info("[Aggregator] Started")

    async def stop(self):
        """Stop the aggregation loop"""
        self.running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Emit any remaining data
        await self._emit_aggregates()

        self.buffers.clear()
        self.last_emitted.clear()

        logger.info("[Aggregator] Stopped")
