# Layer 1: Data Structures & Models - Paper Trading Models
"""
Pydantic models for paper trading simulation
"""

from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
from . import OrderSide, OrderType


class PositionSide(str, Enum):
    """Position side enumeration"""
    LONG = "long"
    SHORT = "short"


class OrderStatus(str, Enum):
    """Order status enumeration"""
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PaperOrder(BaseModel):
    """Paper trading order representation"""
    
    order_id: str = Field(..., min_length=1)
    market_id: str = Field(..., min_length=1)
    side: OrderSide
    order_type: OrderType
    status: OrderStatus = Field(default=OrderStatus.PENDING)
    
    # Order details
    quantity: Decimal = Field(..., gt=0)
    price: Optional[Decimal] = Field(default=None)  # None for market orders
    filled_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    average_fill_price: Optional[Decimal] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: Optional[datetime] = Field(default=None)
    
    # Fees and slippage
    estimated_fee: Decimal = Field(default=Decimal("0"), ge=0)
    actual_fee: Decimal = Field(default=Decimal("0"), ge=0)
    slippage: Optional[Decimal] = Field(default=None)
    
    @property
    def remaining_quantity(self) -> Decimal:
        """Calculate remaining unfilled quantity"""
        return self.quantity - self.filled_quantity
    
    @property
    def fill_percentage(self) -> Decimal:
        """Calculate fill percentage"""
        return (self.filled_quantity / self.quantity) * 100
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.status == OrderStatus.FILLED
    
    @property
    def notional_value(self) -> Optional[Decimal]:
        """Calculate notional value"""
        if self.average_fill_price:
            return self.filled_quantity * self.average_fill_price
        elif self.price:
            return self.quantity * self.price
        return None
    
    @field_validator('filled_quantity')
    @classmethod
    def validate_filled_quantity(cls, v, info):
        """Ensure filled quantity doesn't exceed total quantity"""
        values = info.data
        if 'quantity' in values and v > values['quantity']:
            raise ValueError("Filled quantity cannot exceed total quantity")
        return v
    
    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class PaperPosition(BaseModel):
    """Paper trading position representation"""
    
    position_id: str = Field(..., min_length=1)
    market_id: str = Field(..., min_length=1)
    side: PositionSide
    
    # Position details
    quantity: Decimal = Field(..., gt=0)
    entry_price: Decimal = Field(..., gt=0)
    current_price: Decimal = Field(..., gt=0)
    leverage: Decimal = Field(default=Decimal("1.0"), ge=Decimal("1.0"))
    
    # Risk management
    stop_loss_price: Optional[Decimal] = Field(default=None)
    take_profit_price: Optional[Decimal] = Field(default=None)
    
    # Timestamps
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = Field(default=None)
    
    # Fees and costs
    entry_fee: Decimal = Field(default=Decimal("0"), ge=0)
    funding_fee_paid: Decimal = Field(default=Decimal("0"))
    
    @property
    def notional_value(self) -> Decimal:
        """Calculate current notional value"""
        return self.quantity * self.current_price
    
    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P&L"""
        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) * self.quantity
        else:  # SHORT
            return (self.entry_price - self.current_price) * self.quantity
    
    @property
    def unrealized_pnl_percentage(self) -> Decimal:
        """Calculate unrealized P&L percentage"""
        entry_value = self.entry_price * self.quantity
        return (self.unrealized_pnl / entry_value) * 100
    
    @property
    def is_profitable(self) -> bool:
        """Check if position is currently profitable"""
        return self.unrealized_pnl > 0
    
    @property
    def margin_used(self) -> Decimal:
        """Calculate margin used for this position"""
        return (self.quantity * self.entry_price) / self.leverage
    
    def should_stop_loss(self) -> bool:
        """Check if stop loss should be triggered"""
        if not self.stop_loss_price:
            return False
        
        if self.side == PositionSide.LONG:
            return self.current_price <= self.stop_loss_price
        else:  # SHORT
            return self.current_price >= self.stop_loss_price
    
    def should_take_profit(self) -> bool:
        """Check if take profit should be triggered"""
        if not self.take_profit_price:
            return False
        
        if self.side == PositionSide.LONG:
            return self.current_price >= self.take_profit_price
        else:  # SHORT
            return self.current_price <= self.take_profit_price
    
    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class PaperAccount(BaseModel):
    """Paper trading account state"""
    
    account_id: str = Field(..., min_length=1)
    
    # Balance information
    balance: Decimal = Field(..., ge=0)
    available_balance: Decimal = Field(..., ge=0)
    margin_used: Decimal = Field(default=Decimal("0"), ge=0)
    
    # P&L tracking
    realized_pnl: Decimal = Field(default=Decimal("0"))
    unrealized_pnl: Decimal = Field(default=Decimal("0"))
    total_fees_paid: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Performance metrics
    total_trades: int = Field(default=0, ge=0)
    winning_trades: int = Field(default=0, ge=0)
    losing_trades: int = Field(default=0, ge=0)
    
    # Risk metrics
    max_drawdown: Decimal = Field(default=Decimal("0"), ge=0)
    peak_balance: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def total_equity(self) -> Decimal:
        """Calculate total account equity"""
        return self.balance + self.unrealized_pnl
    
    @property
    def free_margin(self) -> Decimal:
        """Calculate free margin available"""
        return self.available_balance - self.margin_used
    
    @property
    def margin_ratio(self) -> Decimal:
        """Calculate margin utilization ratio"""
        if self.available_balance > 0:
            return (self.margin_used / self.available_balance) * 100
        return Decimal("0")
    
    @property
    def win_rate(self) -> Decimal:
        """Calculate win rate percentage"""
        if self.total_trades > 0:
            return (self.winning_trades / self.total_trades) * 100
        return Decimal("0")
    
    @property
    def current_drawdown(self) -> Decimal:
        """Calculate current drawdown from peak"""
        if self.peak_balance > 0:
            return ((self.peak_balance - self.total_equity) / self.peak_balance) * 100
        return Decimal("0")
    
    @property
    def roi(self) -> Decimal:
        """Calculate return on investment"""
        initial_balance = self.balance - self.realized_pnl
        if initial_balance > 0:
            return (self.realized_pnl / initial_balance) * 100
        return Decimal("0")
    
    @field_validator('available_balance')
    @classmethod
    def validate_available_balance(cls, v, info):
        """Ensure available balance doesn't exceed total balance"""
        values = info.data
        if 'balance' in values and v > values['balance']:
            raise ValueError("Available balance cannot exceed total balance")
        return v
    
    @field_validator('winning_trades', 'losing_trades')
    @classmethod
    def validate_trade_counts(cls, v, info):
        """Ensure trade counts are consistent"""
        values = info.data
        field_name = info.field_name
        if field_name == 'winning_trades' and 'total_trades' in values:
            if v > values['total_trades']:
                raise ValueError("Winning trades cannot exceed total trades")
        elif field_name == 'losing_trades' and 'total_trades' in values and 'winning_trades' in values:
            if v + values['winning_trades'] > values['total_trades']:
                raise ValueError("Sum of winning and losing trades cannot exceed total trades")
        return v
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class TradingPerformance(BaseModel):
    """Trading performance metrics and statistics"""
    
    period_start: datetime
    period_end: datetime
    
    # Basic metrics
    total_trades: int = Field(default=0, ge=0)
    winning_trades: int = Field(default=0, ge=0)
    losing_trades: int = Field(default=0, ge=0)
    
    # P&L metrics
    total_pnl: Decimal = Field(default=Decimal("0"))
    average_win: Decimal = Field(default=Decimal("0"))
    average_loss: Decimal = Field(default=Decimal("0"))
    largest_win: Decimal = Field(default=Decimal("0"))
    largest_loss: Decimal = Field(default=Decimal("0"))
    
    # Risk metrics
    max_drawdown: Decimal = Field(default=Decimal("0"), ge=0)
    sharpe_ratio: Optional[Decimal] = Field(default=None)
    sortino_ratio: Optional[Decimal] = Field(default=None)
    
    # Efficiency metrics
    profit_factor: Optional[Decimal] = Field(default=None)
    recovery_factor: Optional[Decimal] = Field(default=None)
    
    @property
    def win_rate(self) -> Decimal:
        """Calculate win rate percentage"""
        if self.total_trades > 0:
            return (self.winning_trades / self.total_trades) * 100
        return Decimal("0")
    
    @property
    def average_trade(self) -> Decimal:
        """Calculate average P&L per trade"""
        if self.total_trades > 0:
            return self.total_pnl / self.total_trades
        return Decimal("0")
    
    @property
    def expectancy(self) -> Decimal:
        """Calculate expectancy per trade"""
        if self.total_trades > 0:
            win_rate = self.win_rate / 100
            loss_rate = 1 - win_rate
            return (win_rate * abs(self.average_win)) - (loss_rate * abs(self.average_loss))
        return Decimal("0")
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
