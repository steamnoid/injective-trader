# Layer 1: Data Structures & Models - Configuration
"""
Configuration management for the Injective Sniper Bot
"""

from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict
import os


class WebSocketConfig(BaseModel):
    """WebSocket connection configuration"""
    
    max_reconnect_attempts: int = Field(default=10, ge=1, le=100)
    reconnect_delay_base: float = Field(default=1.0, ge=0.1, le=60.0)
    reconnect_delay_max: float = Field(default=30.0, ge=1.0, le=300.0)
    connection_timeout: float = Field(default=30.0, ge=1.0, le=120.0)
    ping_interval: float = Field(default=30.0, ge=5.0, le=300.0)
    max_message_rate: int = Field(default=1000, ge=10, le=10000)

    model_config = ConfigDict()


class TradingConfig(BaseModel):
    """Trading strategy configuration"""
    
    # Position sizing
    max_position_size_pct: Decimal = Field(default=Decimal("0.05"), ge=Decimal("0.001"), le=Decimal("0.2"))
    base_position_size_pct: Decimal = Field(default=Decimal("0.02"), ge=Decimal("0.001"), le=Decimal("0.1"))
    
    # Risk management
    stop_loss_pct: Decimal = Field(default=Decimal("0.03"), ge=Decimal("0.005"), le=Decimal("0.1"))
    take_profit_pct: Decimal = Field(default=Decimal("0.06"), ge=Decimal("0.01"), le=Decimal("0.5"))
    max_daily_loss_pct: Decimal = Field(default=Decimal("0.05"), ge=Decimal("0.01"), le=Decimal("0.2"))
    
    # Leverage
    max_leverage: Decimal = Field(default=Decimal("5.0"), ge=Decimal("1.0"), le=Decimal("20.0"))
    leverage_confidence_multiplier: Decimal = Field(default=Decimal("1.5"), ge=Decimal("1.0"), le=Decimal("3.0"))
    
    # Signal thresholds
    min_signal_strength: Decimal = Field(default=Decimal("0.6"), ge=Decimal("0.1"), le=Decimal("1.0"))
    signal_confidence_threshold: Decimal = Field(default=Decimal("0.7"), ge=Decimal("0.1"), le=Decimal("1.0"))

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PerformanceConfig(BaseModel):
    """Performance optimization configuration"""
    
    # Memory management
    max_memory_mb: int = Field(default=512, ge=128, le=2048)
    circular_buffer_size: int = Field(default=10000, ge=1000, le=100000)
    gc_threshold_mb: int = Field(default=400, ge=100, le=1600)
    
    # CPU optimization
    max_cpu_percent: float = Field(default=25.0, ge=5.0, le=80.0)
    processing_batch_size: int = Field(default=100, ge=10, le=1000)
    signal_processing_timeout_ms: int = Field(default=50, ge=10, le=500)
    
    # Latency targets
    websocket_processing_target_ms: int = Field(default=10, ge=1, le=100)
    signal_generation_target_ms: int = Field(default=50, ge=10, le=500)
    dashboard_refresh_target_ms: int = Field(default=100, ge=50, le=1000)

    model_config = ConfigDict()


class InjectiveConfig(BaseModel):
    """Injective Protocol specific configuration"""
    
    # Network
    network: str = Field(default="mainnet", pattern="^(mainnet|testnet)$")
    grpc_endpoint: str = Field(default="sentry.chain.grpc.injective.network:443")
    lcd_endpoint: str = Field(default="sentry.lcd.injective.network:443")
    
    # Markets
    monitored_markets: List[str] = Field(default_factory=lambda: ["*-USD"])
    excluded_markets: List[str] = Field(default_factory=list)
    min_market_volume_24h: Decimal = Field(default=Decimal("100000"), ge=Decimal("1000"))
    
    # Account (for paper trading)
    paper_trading_balance: Decimal = Field(default=Decimal("10000"), ge=Decimal("100"))
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    

class BotConfig(BaseModel):
    """Main bot configuration combining all sub-configurations"""
    
    # Environment
    environment: str = Field(default="development", pattern="^(development|production|testing)$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    
    # Sub-configurations
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    injective: InjectiveConfig = Field(default_factory=InjectiveConfig)
    
    @field_validator('trading')
    @classmethod
    def validate_trading_config(cls, v):
        """Validate trading configuration consistency"""
        if v.max_position_size_pct <= v.base_position_size_pct:
            raise ValueError("max_position_size_pct must be greater than base_position_size_pct")
        
        if v.stop_loss_pct >= v.take_profit_pct:
            raise ValueError("stop_loss_pct must be less than take_profit_pct")
        
        return v
    
    @classmethod
    def from_env(cls) -> "BotConfig":
        """Create configuration from environment variables"""
        return cls(
            environment=os.getenv("BOT_ENVIRONMENT", "development"),
            log_level=os.getenv("BOT_LOG_LEVEL", "INFO"),
        )

    model_config = ConfigDict(arbitrary_types_allowed=True)
