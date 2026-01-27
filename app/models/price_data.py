from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field

Base = declarative_base()


class PriceRecord(Base):
    """SQLAlchemy model for price records"""

    __tablename__ = "price_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    provider = Column(String(50), nullable=False, index=True)  # 'eodhd', 'twelve_data', 'massive'
    asset_type = Column(String(20), nullable=False, index=True)  # 'gold', 'silver', 'usd_krw'
    price = Column(Numeric(18, 6), nullable=False)
    bid = Column(Numeric(18, 6), nullable=True)
    ask = Column(Numeric(18, 6), nullable=True)
    volume = Column(Numeric(18, 2), nullable=True)
    extra_data = Column(Text, nullable=True)  # JSON string for additional data
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Composite index for common queries
    __table_args__ = (
        Index('idx_provider_asset_time', 'provider', 'asset_type', 'timestamp'),
    )

    def __repr__(self):
        return f"<PriceRecord(provider='{self.provider}', asset='{self.asset_type}', price={self.price}, time={self.timestamp})>"


# Pydantic schemas for API validation

class PriceData(BaseModel):
    """Schema for price data received from WebSocket"""

    provider: str = Field(..., description="API provider name")
    asset_type: str = Field(..., description="Asset type (gold, silver, usd_krw)")
    price: float = Field(..., description="Current price")
    bid: Optional[float] = Field(None, description="Bid price")
    ask: Optional[float] = Field(None, description="Ask price")
    volume: Optional[float] = Field(None, description="Trading volume")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Timestamp")
    metadata: Optional[dict] = Field(None, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "eodhd",
                "asset_type": "gold",
                "price": 2050.25,
                "bid": 2050.00,
                "ask": 2050.50,
                "volume": 12345.67,
                "timestamp": "2024-01-23T12:34:56Z"
            }
        }


class PriceRecordResponse(BaseModel):
    """Schema for price record API response"""

    id: int
    timestamp: datetime
    provider: str
    asset_type: str
    price: float
    bid: Optional[float]
    ask: Optional[float]
    volume: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class HistoryResponse(BaseModel):
    """Schema for history endpoint response"""

    page: int
    page_size: int
    total: Optional[int] = None
    records: list[PriceRecordResponse]


class StatisticsResponse(BaseModel):
    """Schema for statistics endpoint response"""

    asset_type: str
    providers: dict[str, dict]  # provider -> {price, timestamp, ...}
    average: Optional[float]
    max_price: Optional[float]
    min_price: Optional[float]
    spread: Optional[float]
    last_updated: datetime
