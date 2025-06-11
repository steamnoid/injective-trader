# Layer 1: Data Structures & Models - Signal Models
"""
Pydantic models for trading signals and strategy components
"""

from typing import Optional, Dict, List, Any
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class SignalType(str, Enum):
    """Trading signal type enumeration"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class SignalStrength(str, Enum):
    """Signal strength classification"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class IndicatorType(str, Enum):
    """Technical indicator type enumeration"""
    MOMENTUM = "momentum"
    TREND = "trend"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    SUPPORT_RESISTANCE = "support_resistance"
    ORDERBOOK = "orderbook"


class TechnicalIndicator(BaseModel):
    """Individual technical indicator value"""
    
    name: str = Field(..., min_length=1, max_length=50)
    type: IndicatorType
    value: Decimal = Field(...)
    normalized_value: Optional[Decimal] = Field(default=None, ge=-1, le=1)
    
    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timeframe: str = Field(..., pattern="^(1m|5m|15m|1h|4h|1d)$")
    market_id: str = Field(..., min_length=1)
    
    # Confidence and weight
    confidence: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    weight: Decimal = Field(default=Decimal("1.0"), ge=0, le=10)
    
    @property
    def weighted_value(self) -> Decimal:
        """Calculate confidence-weighted value"""
        base_value = self.normalized_value if self.normalized_value is not None else self.value
        return base_value * self.confidence * self.weight
    
    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class OrderbookSignal(BaseModel):
    """Orderbook-derived trading signal"""
    
    market_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Imbalance metrics
    bid_ask_imbalance: Decimal = Field(..., ge=-1, le=1)
    volume_imbalance: Decimal = Field(..., ge=-1, le=1)
    depth_imbalance: Decimal = Field(..., ge=-1, le=1)
    
    # Pressure metrics
    buy_pressure: Decimal = Field(..., ge=0, le=1)
    sell_pressure: Decimal = Field(..., ge=0, le=1)
    
    # Liquidity metrics
    total_liquidity: Decimal = Field(..., ge=0)
    spread_percentage: Decimal = Field(..., ge=0)
    
    # Signal derivation
    signal_strength: Decimal = Field(..., ge=0, le=1)
    confidence: Decimal = Field(..., ge=0, le=1)
    
    @property
    def net_pressure(self) -> Decimal:
        """Calculate net buying/selling pressure"""
        return self.buy_pressure - self.sell_pressure
    
    @property
    def overall_imbalance(self) -> Decimal:
        """Calculate overall orderbook imbalance"""
        return (self.bid_ask_imbalance + self.volume_imbalance + self.depth_imbalance) / 3
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class VolumeSignal(BaseModel):
    """Volume-based trading signal"""
    
    market_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timeframe: str = Field(..., pattern="^(1m|5m|15m|1h|4h|1d)$")
    
    # Volume metrics
    current_volume: Decimal = Field(..., ge=0)
    average_volume: Decimal = Field(..., ge=0)
    volume_ratio: Decimal = Field(..., ge=0)
    
    # Volume profile
    buy_volume: Decimal = Field(..., ge=0)
    sell_volume: Decimal = Field(..., ge=0)
    volume_imbalance: Decimal = Field(..., ge=-1, le=1)
    
    # Derived signals
    volume_spike: bool = Field(default=False)
    abnormal_volume: bool = Field(default=False)
    signal_strength: Decimal = Field(..., ge=0, le=1)
    
    @property
    def volume_surge_factor(self) -> Decimal:
        """Calculate volume surge factor"""
        if self.average_volume > 0:
            return self.current_volume / self.average_volume
        return Decimal("1.0")
    
    @property
    def net_volume_bias(self) -> Decimal:
        """Calculate net volume bias (buy vs sell)"""
        total_volume = self.buy_volume + self.sell_volume
        if total_volume > 0:
            return (self.buy_volume - self.sell_volume) / total_volume
        return Decimal("0")
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class PriceSignal(BaseModel):
    """Price-based trading signal"""
    
    market_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timeframe: str = Field(..., pattern="^(1m|5m|15m|1h|4h|1d)$")
    
    # Price levels
    current_price: Decimal = Field(..., gt=0)
    support_level: Optional[Decimal] = Field(default=None, gt=0)
    resistance_level: Optional[Decimal] = Field(default=None, gt=0)
    
    # Momentum indicators
    rsi: Optional[Decimal] = Field(default=None, ge=0, le=100)
    macd_signal: Optional[Decimal] = Field(default=None)
    stochastic: Optional[Decimal] = Field(default=None, ge=0, le=100)
    
    # Trend indicators
    moving_average_20: Optional[Decimal] = Field(default=None, gt=0)
    moving_average_50: Optional[Decimal] = Field(default=None, gt=0)
    trend_direction: Optional[SignalType] = Field(default=None)
    
    # Volatility
    bollinger_position: Optional[Decimal] = Field(default=None, ge=0, le=1)
    atr_ratio: Optional[Decimal] = Field(default=None, ge=0)
    
    @property
    def price_position_in_range(self) -> Optional[Decimal]:
        """Calculate price position within support-resistance range"""
        if self.support_level and self.resistance_level and self.support_level < self.resistance_level:
            range_size = self.resistance_level - self.support_level
            return (self.current_price - self.support_level) / range_size
        return None
    
    @property
    def trend_strength(self) -> Optional[Decimal]:
        """Calculate trend strength based on moving averages"""
        if self.moving_average_20 and self.moving_average_50:
            if self.moving_average_20 > self.moving_average_50:
                return (self.moving_average_20 - self.moving_average_50) / self.moving_average_50
            else:
                return -(self.moving_average_50 - self.moving_average_20) / self.moving_average_20
        return None
    
    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class CompositeSignal(BaseModel):
    """Composite trading signal combining multiple indicators"""
    
    signal_id: str = Field(..., min_length=1)
    market_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Main signal
    signal_type: SignalType
    signal_strength: SignalStrength
    confidence: Decimal = Field(..., ge=0, le=1)
    
    # Component signals
    price_signal: Optional[PriceSignal] = Field(default=None)
    volume_signal: Optional[VolumeSignal] = Field(default=None)
    orderbook_signal: Optional[OrderbookSignal] = Field(default=None)
    technical_indicators: List[TechnicalIndicator] = Field(default_factory=list)
    
    # Risk assessment
    risk_score: Decimal = Field(..., ge=0, le=1)
    expected_move: Optional[Decimal] = Field(default=None)
    time_horizon: Optional[str] = Field(default=None, pattern="^(1m|5m|15m|1h|4h|1d)$")
    
    # Metadata
    strategy_name: str = Field(..., min_length=1, max_length=50)
    version: str = Field(default="1.0.0")
    
    @property
    def composite_score(self) -> Decimal:
        """Calculate composite signal score"""
        base_score = self.confidence
        
        # Adjust based on signal strength
        strength_multiplier = {
            SignalStrength.WEAK: Decimal("0.5"),
            SignalStrength.MODERATE: Decimal("1.0"),
            SignalStrength.STRONG: Decimal("1.5"),
            SignalStrength.VERY_STRONG: Decimal("2.0")
        }
        
        score = base_score * strength_multiplier[self.signal_strength]
        
        # Apply risk adjustment
        risk_adjusted_score = score * (1 - self.risk_score * Decimal("0.5"))
        
        return min(risk_adjusted_score, Decimal("1.0"))
    
    @property
    def is_actionable(self) -> bool:
        """Check if signal is strong enough to be actionable"""
        return (
            self.composite_score >= Decimal("0.6") and 
            self.confidence >= Decimal("0.7") and
            self.signal_type != SignalType.HOLD
        )
    
    @property
    def indicator_consensus(self) -> Decimal:
        """Calculate consensus among technical indicators"""
        if not self.technical_indicators:
            return Decimal("0.5")
        
        weighted_sum = sum(indicator.weighted_value for indicator in self.technical_indicators)
        total_weight = sum(indicator.weight for indicator in self.technical_indicators)
        
        if total_weight > 0:
            return weighted_sum / total_weight
        return Decimal("0.5")
    
    @field_validator('technical_indicators')
    @classmethod
    def validate_max_indicators(cls, v):
        """Limit number of technical indicators"""
        if len(v) > 20:
            raise ValueError("Maximum 20 technical indicators allowed")
        return v
    
    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class SignalHistory(BaseModel):
    """Historical signal tracking for performance analysis"""
    
    signal_id: str = Field(..., min_length=1)
    original_signal: CompositeSignal
    
    # Outcome tracking
    signal_triggered: bool = Field(default=False)
    trigger_price: Optional[Decimal] = Field(default=None)
    trigger_time: Optional[datetime] = Field(default=None)
    
    # Performance metrics
    max_favorable_move: Optional[Decimal] = Field(default=None)
    max_adverse_move: Optional[Decimal] = Field(default=None)
    final_outcome: Optional[Decimal] = Field(default=None)
    
    # Analysis
    accuracy_score: Optional[Decimal] = Field(default=None, ge=0, le=1)
    timing_score: Optional[Decimal] = Field(default=None, ge=0, le=1)
    
    @property
    def signal_quality(self) -> Optional[Decimal]:
        """Calculate overall signal quality score"""
        if self.accuracy_score is not None and self.timing_score is not None:
            return (self.accuracy_score + self.timing_score) / 2
        return None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
