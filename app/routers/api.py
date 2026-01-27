from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db_session
from app.database.repository import PriceRepository
from app.models.price_data import HistoryResponse, PriceRecordResponse, StatisticsResponse
from app.utils.logger import app_logger as logger

router = APIRouter()


@router.get("/history", response_model=HistoryResponse)
async def get_price_history(
    page: int = Query(0, ge=0, description="Page number (0-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Number of records per page"),
    asset: Optional[str] = Query(None, description="Filter by asset type (gold, silver, usd_krw)"),
    provider: Optional[str] = Query(None, description="Filter by provider (eodhd, twelve_data, massive)"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get price history with pagination and filtering

    - **page**: Page number (starting from 0)
    - **page_size**: Number of records per page (1-500)
    - **asset**: Filter by asset type (optional)
    - **provider**: Filter by provider (optional)
    - **start_date**: Filter records after this date (optional)
    - **end_date**: Filter records before this date (optional)
    """
    try:
        repository = PriceRepository(session)

        # Get records
        records = await repository.get_price_records(
            page=page,
            page_size=page_size,
            asset_type=asset,
            provider=provider,
            start_date=start_date,
            end_date=end_date
        )

        # Get total count (for pagination info)
        total = await repository.get_record_count(
            asset_type=asset,
            provider=provider
        )

        # Convert to response models
        record_responses = [
            PriceRecordResponse(
                id=record.id,
                timestamp=record.timestamp,
                provider=record.provider,
                asset_type=record.asset_type,
                price=float(record.price),
                bid=float(record.bid) if record.bid else None,
                ask=float(record.ask) if record.ask else None,
                volume=float(record.volume) if record.volume else None,
                created_at=record.created_at
            )
            for record in records
        ]

        return HistoryResponse(
            page=page,
            page_size=page_size,
            total=total,
            records=record_responses
        )

    except Exception as e:
        logger.error(f"Error fetching price history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    asset: str = Query(..., description="Asset type (gold, silver, usd_krw)"),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get latest statistics for a specific asset

    Returns price comparison across all providers with statistics:
    - Average price
    - Maximum price
    - Minimum price
    - Spread (difference between max and min)

    - **asset**: Asset type (gold, silver, or usd_krw)
    """
    try:
        # Validate asset type
        valid_assets = ['gold', 'silver', 'usd_krw']
        if asset not in valid_assets:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid asset type. Must be one of: {', '.join(valid_assets)}"
            )

        repository = PriceRepository(session)

        # Get statistics
        stats = await repository.get_latest_statistics(asset)

        return StatisticsResponse(**stats)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest-all")
async def get_all_latest_prices(
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the latest prices for all providers and assets

    Returns a list of the most recent price for each provider-asset combination
    """
    try:
        repository = PriceRepository(session)

        providers = ['eodhd', 'twelve_data', 'massive']
        assets = ['gold', 'silver', 'usd_krw', 'platinum', 'palladium', 'jpy_krw', 'cny_krw', 'eur_krw']

        results = []
        for provider in providers:
            for asset in assets:
                record = await repository.get_latest_by_provider_and_asset(provider, asset)
                if record:
                    results.append({
                        "provider": record.provider,
                        "asset_type": record.asset_type,
                        "price": float(record.price),
                        "bid": float(record.bid) if record.bid else None,
                        "ask": float(record.ask) if record.ask else None,
                        "volume": float(record.volume) if record.volume else None,
                        "timestamp": record.timestamp.isoformat()
                    })

        return {"prices": results}

    except Exception as e:
        logger.error(f"Error fetching all latest prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest/{provider}/{asset}")
async def get_latest_price(
    provider: str,
    asset: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the latest price for a specific provider and asset

    - **provider**: Provider name (eodhd, twelve_data, massive)
    - **asset**: Asset type (gold, silver, usd_krw)
    """
    try:
        repository = PriceRepository(session)

        record = await repository.get_latest_by_provider_and_asset(provider, asset)

        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {provider} - {asset}"
            )

        return PriceRecordResponse(
            id=record.id,
            timestamp=record.timestamp,
            provider=record.provider,
            asset_type=record.asset_type,
            price=float(record.price),
            bid=float(record.bid) if record.bid else None,
            ask=float(record.ask) if record.ask else None,
            volume=float(record.volume) if record.volume else None,
            created_at=record.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching latest price: {e}")
        raise HTTPException(status_code=500, detail=str(e))
