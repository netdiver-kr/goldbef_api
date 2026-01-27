from typing import Dict, Any
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
        Save price data to database

        Expected data format:
        {
            'provider': 'eodhd',
            'asset_type': 'gold',
            'price': 2050.25,
            'bid': 2050.00,
            'ask': 2050.50,
            'volume': 12345.67,
            'timestamp': datetime.datetime(...),
            'metadata': {...}
        }
        """
        try:
            # Validate required fields
            if 'provider' not in data or 'asset_type' not in data or 'price' not in data:
                logger.warning(f"Invalid data format, missing required fields: {data}")
                return

            # Get database session
            async for session in get_db_session():
                repository = PriceRepository(session)

                # Insert price record
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

                logger.debug(
                    f"Saved price: {data['provider']} - {data['asset_type']} = {data['price']}"
                )

        except Exception as e:
            logger.error(f"Error saving price data: {e}")
            logger.debug(f"Data: {data}")
