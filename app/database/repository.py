from datetime import datetime, timedelta
from typing import Optional, List
import json
from sqlalchemy import select, delete, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.price_data import PriceRecord, PriceData
from app.utils.logger import app_logger as logger


class PriceRepository:
    """Repository for price data CRUD operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_price_record(
        self,
        provider: str,
        asset_type: str,
        price: float,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        volume: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        metadata: Optional[dict] = None
    ) -> None:
        """Insert a new price record"""
        record = PriceRecord(
            timestamp=timestamp or datetime.utcnow(),
            provider=provider,
            asset_type=asset_type,
            price=price,
            bid=bid,
            ask=ask,
            volume=volume,
            extra_data=json.dumps(metadata) if metadata else None
        )

        self.session.add(record)
        await self.session.commit()

        logger.debug(f"Inserted price record: {provider} - {asset_type} = {price}")

    async def insert_price_records_batch(
        self,
        records_data: List[dict]
    ) -> None:
        """Insert multiple price records in a single transaction"""
        if not records_data:
            return

        records = [
            PriceRecord(
                timestamp=data.get('timestamp') or datetime.utcnow(),
                provider=data['provider'],
                asset_type=data['asset_type'],
                price=data['price'],
                bid=data.get('bid'),
                ask=data.get('ask'),
                volume=data.get('volume'),
                extra_data=json.dumps(data.get('metadata')) if data.get('metadata') else None
            )
            for data in records_data
        ]

        self.session.add_all(records)
        await self.session.commit()

        logger.debug(f"Batch inserted {len(records)} price records")

    async def get_price_records(
        self,
        page: int = 0,
        page_size: int = 50,
        asset_type: Optional[str] = None,
        provider: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[PriceRecord]:
        """Get price records with pagination and filtering"""
        query = select(PriceRecord).order_by(desc(PriceRecord.timestamp))

        # Apply filters
        conditions = []
        if asset_type:
            conditions.append(PriceRecord.asset_type == asset_type)
        if provider:
            conditions.append(PriceRecord.provider == provider)
        if start_date:
            conditions.append(PriceRecord.timestamp >= start_date)
        if end_date:
            conditions.append(PriceRecord.timestamp <= end_date)

        if conditions:
            query = query.where(and_(*conditions))

        # Apply pagination
        query = query.offset(page * page_size).limit(page_size)

        result = await self.session.execute(query)
        records = result.scalars().all()

        logger.debug(f"Retrieved {len(records)} price records (page {page})")
        return records

    async def get_latest_by_provider_and_asset(
        self,
        provider: str,
        asset_type: str
    ) -> Optional[PriceRecord]:
        """Get the latest price record for a specific provider and asset"""
        query = select(PriceRecord).where(
            and_(
                PriceRecord.provider == provider,
                PriceRecord.asset_type == asset_type
            )
        ).order_by(desc(PriceRecord.timestamp)).limit(1)

        result = await self.session.execute(query)
        record = result.scalar_one_or_none()

        return record

    async def get_latest_statistics(self, asset_type: str) -> dict:
        """Get latest statistics for an asset across all providers"""
        providers = ['eodhd', 'twelve_data', 'massive']
        stats = {
            'asset_type': asset_type,
            'providers': {},
            'average': None,
            'max_price': None,
            'min_price': None,
            'spread': None,
            'last_updated': datetime.utcnow()
        }

        prices = []
        for provider in providers:
            record = await self.get_latest_by_provider_and_asset(provider, asset_type)
            if record:
                stats['providers'][provider] = {
                    'price': float(record.price),
                    'bid': float(record.bid) if record.bid else None,
                    'ask': float(record.ask) if record.ask else None,
                    'volume': float(record.volume) if record.volume else None,
                    'timestamp': record.timestamp.isoformat()
                }
                prices.append(float(record.price))

        # Calculate statistics
        if prices:
            stats['average'] = sum(prices) / len(prices)
            stats['max_price'] = max(prices)
            stats['min_price'] = min(prices)
            stats['spread'] = stats['max_price'] - stats['min_price']

        return stats

    async def get_first_price_after(
        self,
        asset_type: str,
        after_utc: datetime
    ) -> Optional[PriceRecord]:
        """Get the first price record after a given UTC time for any provider"""
        query = select(PriceRecord).where(
            and_(
                PriceRecord.asset_type == asset_type,
                PriceRecord.timestamp >= after_utc
            )
        ).order_by(PriceRecord.timestamp).limit(1)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_last_price_before(
        self,
        asset_type: str,
        before_utc: datetime,
        after_utc: datetime
    ) -> Optional[PriceRecord]:
        """Get the last price record in a time window for any provider"""
        query = select(PriceRecord).where(
            and_(
                PriceRecord.asset_type == asset_type,
                PriceRecord.timestamp <= before_utc,
                PriceRecord.timestamp >= after_utc
            )
        ).order_by(desc(PriceRecord.timestamp)).limit(1)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete_old_records(self, days: int = 30) -> int:
        """Delete records older than specified days using bulk DELETE"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Count before delete
        count_query = select(func.count(PriceRecord.id)).where(
            PriceRecord.timestamp < cutoff_date
        )
        result = await self.session.execute(count_query)
        count = result.scalar() or 0

        if count > 0:
            stmt = delete(PriceRecord).where(PriceRecord.timestamp < cutoff_date)
            await self.session.execute(stmt)
            await self.session.commit()

        logger.info(f"Deleted {count} old records (older than {days} days)")
        return count

    async def get_record_count(
        self,
        asset_type: Optional[str] = None,
        provider: Optional[str] = None
    ) -> int:
        """Get total count of records with optional filtering"""
        query = select(func.count(PriceRecord.id))

        conditions = []
        if asset_type:
            conditions.append(PriceRecord.asset_type == asset_type)
        if provider:
            conditions.append(PriceRecord.provider == provider)

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        count = result.scalar()

        return count or 0
