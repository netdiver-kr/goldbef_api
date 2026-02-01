import asyncio
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
from app.services.eodhd_ws_client import EODHDWebSocketClient
from app.services.twelve_data_client import TwelveDataClient
from app.services.naugold_client import NaugoldClient
from app.services.data_processor import DataProcessor
from app.config import get_settings
from app.utils.logger import app_logger as logger

# Korean Standard Time (UTC+9)
KST = timezone(timedelta(hours=9))


class WebSocketManager:
    """Manage multiple WebSocket connections and broadcast data to SSE clients"""

    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.data_processor = DataProcessor()

        # WebSocket client (EODHD only) - uses buffered handler
        self.ws_clients = [
            EODHDWebSocketClient(
                api_key=settings.EODHD_API_KEY,
                on_message=self._handle_eodhd_message
            )
        ]

        # HTTP polling clients
        self.twelve_data_client = TwelveDataClient(
            api_key=settings.TWELVE_DATA_API_KEY,
            callback=self._handle_message
        )

        # NauGold HTTP polling client (replaces Massive MSSQL)
        self.massive_client = NaugoldClient(
            on_message=self._handle_massive_message
        )

        # SSE broadcast queues
        self.broadcast_queues: List[asyncio.Queue] = []

        # EODHD data buffer for averaging (3 second intervals)
        self.eodhd_buffer: Dict[str, List[Dict[str, Any]]] = {}
        self.eodhd_flush_interval = settings.PRICE_UPDATE_INTERVAL  # 3 seconds
        self.eodhd_flush_task = None

        # Massive data buffer for averaging (3 second intervals)
        self.massive_buffer: Dict[str, List[Dict[str, Any]]] = {}
        self.massive_flush_task = None

    async def _handle_eodhd_message(self, data: Dict[str, Any]):
        """
        Handle EODHD message - buffer for averaging
        """
        try:
            asset_type = data.get('asset_type')
            if not asset_type:
                return

            # Add to buffer
            if asset_type not in self.eodhd_buffer:
                self.eodhd_buffer[asset_type] = []

            self.eodhd_buffer[asset_type].append(data)

        except Exception as e:
            logger.error(f"Error buffering EODHD message: {e}")

    async def _handle_massive_message(self, data: Dict[str, Any]):
        """
        Handle Massive MSSQL message - buffer for averaging
        """
        try:
            asset_type = data.get('asset_type')
            if not asset_type:
                return

            # Add to buffer
            if asset_type not in self.massive_buffer:
                self.massive_buffer[asset_type] = []

            self.massive_buffer[asset_type].append(data)

        except Exception as e:
            logger.error(f"Error buffering Massive message: {e}")

    async def _flush_eodhd_buffer(self):
        """
        Periodically flush EODHD buffer with averaged values (batch save)
        """
        while True:
            try:
                await asyncio.sleep(self.eodhd_flush_interval)

                batch = []
                for asset_type, data_list in list(self.eodhd_buffer.items()):
                    if not data_list:
                        continue

                    # Calculate averages
                    prices = [d['price'] for d in data_list if d.get('price')]
                    bids = [d['bid'] for d in data_list if d.get('bid')]
                    asks = [d['ask'] for d in data_list if d.get('ask')]

                    if not prices:
                        continue

                    avg_data = {
                        'provider': 'eodhd',
                        'asset_type': asset_type,
                        'price': sum(prices) / len(prices),
                        'bid': sum(bids) / len(bids) if bids else None,
                        'ask': sum(asks) / len(asks) if asks else None,
                        'volume': data_list[-1].get('volume'),
                        'timestamp': data_list[-1].get('timestamp'),
                    }

                    batch.append(avg_data)
                    await self._broadcast_to_sse_clients(avg_data)

                    logger.debug(f"[eodhd] Flushed {len(data_list)} samples for {asset_type}, avg price: {avg_data['price']:.4f}")

                    # Clear buffer for this asset
                    self.eodhd_buffer[asset_type] = []

                # Batch save all averaged data in single transaction
                if batch:
                    await self.data_processor.save_prices_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error flushing EODHD buffer: {e}")

    async def _flush_massive_buffer(self):
        """
        Periodically flush Massive buffer with averaged values (batch save)
        """
        while True:
            try:
                await asyncio.sleep(self.eodhd_flush_interval)  # Same interval as EODHD

                batch = []
                for asset_type, data_list in list(self.massive_buffer.items()):
                    if not data_list:
                        continue

                    # Calculate averages
                    prices = [d['price'] for d in data_list if d.get('price')]
                    bids = [d['bid'] for d in data_list if d.get('bid')]
                    asks = [d['ask'] for d in data_list if d.get('ask')]

                    if not prices:
                        continue

                    avg_data = {
                        'provider': 'massive',
                        'asset_type': asset_type,
                        'price': sum(prices) / len(prices),
                        'bid': sum(bids) / len(bids) if bids else None,
                        'ask': sum(asks) / len(asks) if asks else None,
                        'volume': data_list[-1].get('volume'),
                        'timestamp': data_list[-1].get('timestamp'),
                    }

                    batch.append(avg_data)
                    await self._broadcast_to_sse_clients(avg_data)

                    logger.debug(f"[massive] Flushed {len(data_list)} samples for {asset_type}, avg price: {avg_data['price']:.4f}")

                    # Clear buffer for this asset
                    self.massive_buffer[asset_type] = []

                # Batch save all averaged data in single transaction
                if batch:
                    await self.data_processor.save_prices_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error flushing Massive buffer: {e}")

    async def _handle_message(self, data: Dict[str, Any]):
        """
        Handle message received from HTTP polling clients (Twelve Data, Massive)

        1. Save to database
        2. Broadcast to all SSE clients
        """
        try:
            # Save to database
            await self.data_processor.save_price(data)

            # Broadcast to SSE clients
            await self._broadcast_to_sse_clients(data)

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def _broadcast_to_sse_clients(self, data: Dict[str, Any]):
        """Send data to all connected SSE clients"""
        if not self.broadcast_queues:
            return

        # Convert timestamp to Korean Standard Time (KST)
        timestamp = data.get('timestamp')
        if timestamp:
            if timestamp.tzinfo is None:
                # Assume UTC if no timezone info
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            # Convert to KST
            timestamp_kst = timestamp.astimezone(KST)
            timestamp_str = timestamp_kst.isoformat()
        else:
            # Use current KST time if no timestamp provided
            timestamp_str = datetime.now(KST).isoformat()

        # Prepare data for JSON serialization
        broadcast_data = {
            'provider': data['provider'],
            'asset_type': data['asset_type'],
            'price': float(data['price']),
            'bid': float(data['bid']) if data.get('bid') else None,
            'ask': float(data['ask']) if data.get('ask') else None,
            'volume': float(data['volume']) if data.get('volume') else None,
            'timestamp': timestamp_str
        }

        # Send to all queues
        for queue in self.broadcast_queues[:]:  # Copy list to avoid modification during iteration
            try:
                queue.put_nowait(broadcast_data)
            except asyncio.QueueFull:
                # Queue is full, try to remove oldest item and add new one
                try:
                    queue.get_nowait()
                    queue.put_nowait(broadcast_data)
                except:
                    logger.warning("Failed to add data to full queue")

    async def start(self):
        """Start all data clients"""
        logger.info("Starting WebSocket Manager")

        # Start EODHD buffer flush task
        self.eodhd_flush_task = asyncio.create_task(self._flush_eodhd_buffer())
        logger.info(f"EODHD buffer flush started (interval: {self.eodhd_flush_interval}s)")

        # Start Massive buffer flush task
        self.massive_flush_task = asyncio.create_task(self._flush_massive_buffer())
        logger.info(f"Massive buffer flush started (interval: {self.eodhd_flush_interval}s)")

        # Create tasks for WebSocket clients
        ws_tasks = [client.start() for client in self.ws_clients]

        # Add HTTP polling client tasks
        twelve_data_task = self.twelve_data_client.start()
        massive_task = self.massive_client.start()

        # Run all clients concurrently
        await asyncio.gather(*ws_tasks, twelve_data_task, massive_task, return_exceptions=True)

    async def stop(self):
        """Stop all data clients"""
        logger.info("Stopping WebSocket Manager")

        # Stop EODHD buffer flush task
        if self.eodhd_flush_task:
            self.eodhd_flush_task.cancel()
            try:
                await self.eodhd_flush_task
            except asyncio.CancelledError:
                pass

        # Stop Massive buffer flush task
        if self.massive_flush_task:
            self.massive_flush_task.cancel()
            try:
                await self.massive_flush_task
            except asyncio.CancelledError:
                pass

        # Stop WebSocket clients
        ws_tasks = [client.stop() for client in self.ws_clients]

        # Stop HTTP polling clients
        twelve_data_task = self.twelve_data_client.stop()
        massive_task = self.massive_client.stop()

        await asyncio.gather(*ws_tasks, twelve_data_task, massive_task, return_exceptions=True)

    def add_sse_client(self, queue: asyncio.Queue):
        """Register a new SSE client"""
        self.broadcast_queues.append(queue)
        logger.info(f"SSE client connected (total: {len(self.broadcast_queues)})")

    def remove_sse_client(self, queue: asyncio.Queue):
        """Unregister an SSE client"""
        if queue in self.broadcast_queues:
            self.broadcast_queues.remove(queue)
            logger.info(f"SSE client disconnected (total: {len(self.broadcast_queues)})")

    def get_client_status(self) -> Dict[str, bool]:
        """Get connection status of all clients"""
        status = {
            client.provider_name: client.is_connected()
            for client in self.ws_clients
        }
        # HTTP polling clients
        status['twelve_data'] = self.twelve_data_client.is_connected()
        status['massive'] = self.massive_client.running
        return status


# Global instance
_ws_manager: WebSocketManager = None


def get_ws_manager() -> WebSocketManager:
    """Get global WebSocket Manager instance"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
