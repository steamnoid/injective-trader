# Layer 1: Data Structures & Models - Market Data Models
"""
Pydantic models for market data from Injective Protocol
Optimized for memory efficiency and validation performance
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict, computed_field
from enum import Enum
import numpy as np


class MarketStatus(str, Enum):
    """Market trading status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELISTED = "delisted"


class OrderSide(str, Enum):
    """Order side enumeration"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enumeration"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class MarketInfo(BaseModel):
    """Market metadata information"""
    
    market_id: str = Field(..., min_length=1, max_length=100)
    ticker: str = Field(..., min_length=1, max_length=20)
    base_denom: str = Field(..., min_length=1, max_length=50)
    quote_denom: str = Field(..., min_length=1, max_length=50)
    
    # Market parameters
    tick_size: Decimal = Field(..., gt=0)
    lot_size: Decimal = Field(..., gt=0)
    min_price_tick_size: Decimal = Field(..., gt=0)
    min_quantity_tick_size: Decimal = Field(..., gt=0)
    
    # Trading parameters
    maker_fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0)
    taker_fee_rate: Decimal = Field(default=Decimal("0.002"), ge=0)
    status: MarketStatus = Field(default=MarketStatus.ACTIVE)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class PriceLevel(BaseModel):
    """Individual price level in orderbook"""
    
    price: Decimal = Field(..., gt=0)
    quantity: Decimal = Field(..., ge=0)
    
    @property
    def notional_value(self) -> Decimal:
        """Calculate notional value of this price level"""
        return self.price * self.quantity
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class OrderbookSnapshot(BaseModel):
    """Orderbook snapshot with bids and asks"""
    
    market_id: str = Field(..., min_length=1)
    sequence: int = Field(..., ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    bids: List[PriceLevel] = Field(default_factory=list, max_length=100)
    asks: List[PriceLevel] = Field(default_factory=list, max_length=100)
    
    @property
    def best_bid(self) -> Optional[PriceLevel]:
        """Get best (highest) bid price level"""
        return self.bids[0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[PriceLevel]:
        """Get best (lowest) ask price level"""
        return self.asks[0] if self.asks else None
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread"""
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None
    
    @property
    def spread_percentage(self) -> Optional[Decimal]:
        """Calculate spread as percentage of mid price"""
        if self.best_bid and self.best_ask and self.spread:
            mid_price = (self.best_bid.price + self.best_ask.price) / 2
            return (self.spread / mid_price) * 100
        return None
    
    @property
    def total_bid_volume(self) -> Decimal:
        """Calculate total bid volume"""
        return sum(level.quantity for level in self.bids)
    
    @property
    def total_ask_volume(self) -> Decimal:
        """Calculate total ask volume"""
        return sum(level.quantity for level in self.asks)
    
    @field_validator('bids', 'asks')
    @classmethod
    def validate_price_levels_sorted(cls, v, info):
        """Ensure price levels are properly sorted"""
        if not v:
            return v
        
        field_name = info.field_name
        if field_name == 'bids':
            # Bids should be sorted from highest to lowest price
            for i in range(len(v) - 1):
                if v[i].price < v[i + 1].price:
                    raise ValueError("Bids must be sorted from highest to lowest price")
        else:  # asks
            # Asks should be sorted from lowest to highest price
            for i in range(len(v) - 1):
                if v[i].price > v[i + 1].price:
                    raise ValueError("Asks must be sorted from lowest to highest price")
        
        return v
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class OHLCVData(BaseModel):
    """OHLCV (candlestick) data for market analysis"""
    
    market_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(...)
    timeframe: str = Field(..., pattern="^(1m|5m|15m|1h|4h|1d)$")
    
    # OHLCV values
    open_price: Decimal = Field(..., gt=0)
    high_price: Decimal = Field(..., gt=0)
    low_price: Decimal = Field(..., gt=0)
    close_price: Decimal = Field(..., gt=0)
    volume: Decimal = Field(..., ge=0)
    
    # Derived metrics
    volume_usd: Optional[Decimal] = Field(default=None, ge=0)
    trades_count: Optional[int] = Field(default=None, ge=0)
    
    @property
    def price_range(self) -> Decimal:
        """Calculate high-low price range"""
        return self.high_price - self.low_price
    
    @property
    def price_change(self) -> Decimal:
        """Calculate price change (close - open)"""
        return self.close_price - self.open_price
    
    @property
    def price_change_percentage(self) -> Decimal:
        """Calculate price change percentage"""
        return (self.price_change / self.open_price) * 100
    
    @property
    def typical_price(self) -> Decimal:
        """Calculate typical price (HLC/3)"""
        return (self.high_price + self.low_price + self.close_price) / 3
    
    # Shorthand properties for backward compatibility with tests
    @property
    def open(self) -> Decimal:
        """Alias for open_price"""
        return self.open_price
    
    @property
    def high(self) -> Decimal:
        """Alias for high_price"""
        return self.high_price
    
    @property
    def low(self) -> Decimal:
        """Alias for low_price"""
        return self.low_price
    
    @property
    def close(self) -> Decimal:
        """Alias for close_price"""
        return self.close_price
    
    @field_validator('high_price')
    @classmethod
    def validate_high_price(cls, v, info):
        """Validate high is the highest price"""
        values = info.data
        if 'open_price' in values and v < values['open_price']:
            raise ValueError("High price must be >= open price")
        if 'low_price' in values and v < values['low_price']:
            raise ValueError("High price must be >= low price")
        if 'close_price' in values and v < values['close_price']:
            raise ValueError("High price must be >= close price")
        return v
    
    @field_validator('low_price')
    @classmethod
    def validate_low_price(cls, v, info):
        """Validate low is the lowest price"""
        values = info.data
        if 'open_price' in values and v > values['open_price']:
            raise ValueError("Low price must be <= open price")
        if 'close_price' in values and v > values['close_price']:
            raise ValueError("Low price must be <= close price")
        return v
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class TradeExecution(BaseModel):
    """Individual trade execution data"""
    
    trade_id: str = Field(..., min_length=1)
    market_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Trade details
    price: Decimal = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0)
    side: OrderSide
    
    # Optional fields
    fee_paid: Optional[Decimal] = Field(default=None, ge=0)
    
    @computed_field
    @property
    def notional_value(self) -> Decimal:
        """Calculate notional value of the trade"""
        return self.price * self.quantity
    
    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class MarketSummary(BaseModel):
    """24-hour market summary statistics"""
    
    market_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Price statistics
    last_price: Decimal = Field(..., gt=0)
    price_change_24h: Decimal = Field(...)
    price_change_percentage_24h: Decimal = Field(...)
    high_24h: Decimal = Field(..., gt=0)
    low_24h: Decimal = Field(..., gt=0)
    
    # Volume statistics
    volume_24h: Decimal = Field(..., ge=0)
    volume_usd_24h: Optional[Decimal] = Field(default=None, ge=0)
    trades_count_24h: Optional[int] = Field(default=None, ge=0)
    
    # Market depth
    best_bid: Optional[Decimal] = Field(default=None, gt=0)
    best_ask: Optional[Decimal] = Field(default=None, gt=0)
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate current spread"""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
