from typing import Dict, Any, List
from datetime import datetime
from app.database.repository import PriceRepository
from app.database.connection import get_db_session
from app.utils.logger import app_logger as logger


class DataProcessor:
    """Process and save price data from WebSocket clients"""

    def __init__(self):
        pass

    async def save_price(self, data: Dict[str, Any]):
        """
        Save a single price data to database
        """
        try:
            if 'provider' not in data or 'asset_type' not in data or 'price' not in data:
                logger.warning(f"Invalid data format, missing required fields: {data}")
                return

            async for session in get_db_session():
                repository = PriceRepository(session)
                await repository.insert_price_record(
                    provider=data['provider'],
                    asset_type=data['asset_type'],
                    price=data['price'],
                    bid=data.get('bid'),
                    ask=data.get('ask'),
                    volume=data.get('volume'),
                    timestamp=data.get('timestamp', datetime.utcnow()),
                    metadata=data.get('metadata')
                )

        except Exception as e:
            logger.error(f"Error saving price data: {e}")

    async def save_prices_batch(self, data_list: List[Dict[str, Any]]):
        """
        Save multiple price records in a single transaction
        """
        if not data_list:
            return

        try:
            valid_records = [
                d for d in data_list
                if 'provider' in d and 'asset_type' in d and 'price' in d
            ]

            if not valid_records:
                return

            async for session in get_db_session():
                repository = PriceRepository(session)
                await repository.insert_price_records_batch(valid_records)

            logger.debug(f"Batch saved {len(valid_records)} price records")

        except Exception as e:
            logger.error(f"Error batch saving price data: {e}")
