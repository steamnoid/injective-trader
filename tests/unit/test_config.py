# Layer 1 Tests: Data Structures & Models - Configuration Tests
"""
TDD tests for configuration management
Following RED-GREEN-REFACTOR cycle
"""

import pytest
from decimal import Decimal
from pydantic import ValidationError
import os

from injective_bot.config import (
    WebSocketConfig, TradingConfig, PerformanceConfig, 
    InjectiveConfig, BotConfig
)


class TestWebSocketConfig:
    """Test WebSocket configuration validation and behavior"""
    
    def test_websocket_config_default_values(self):
        """Test default configuration values are set correctly"""
        config = WebSocketConfig()
        
        assert config.max_reconnect_attempts == 10
        assert config.reconnect_delay_base == 1.0
        assert config.reconnect_delay_max == 30.0
        assert config.connection_timeout == 30.0
        assert config.ping_interval == 30.0
        assert config.max_message_rate == 1000
    
    def test_websocket_config_validation_ranges(self):
        """Test field validation ranges"""
        # Test valid boundary values
        config = WebSocketConfig(
            max_reconnect_attempts=1,
            reconnect_delay_base=0.1,
            reconnect_delay_max=1.0,
            connection_timeout=1.0,
            ping_interval=5.0,
            max_message_rate=10
        )
        assert config.max_reconnect_attempts == 1
        
        # Test invalid values raise ValidationError
        with pytest.raises(ValidationError):
            WebSocketConfig(max_reconnect_attempts=0)  # Below minimum
        
        with pytest.raises(ValidationError):
            WebSocketConfig(max_reconnect_attempts=101)  # Above maximum
        
        with pytest.raises(ValidationError):
            WebSocketConfig(reconnect_delay_base=0.05)  # Below minimum
        
        with pytest.raises(ValidationError):
            WebSocketConfig(ping_interval=4.0)  # Below minimum


class TestTradingConfig:
    """Test trading configuration validation and behavior"""
    
    def test_trading_config_default_values(self):
        """Test default trading configuration values"""
        config = TradingConfig()
        
        assert config.max_position_size_pct == Decimal("0.05")
        assert config.base_position_size_pct == Decimal("0.02")
        assert config.stop_loss_pct == Decimal("0.03")
        assert config.take_profit_pct == Decimal("0.06")
        assert config.max_daily_loss_pct == Decimal("0.05")
        assert config.max_leverage == Decimal("5.0")
        assert config.min_signal_strength == Decimal("0.6")
    
    def test_trading_config_decimal_precision(self):
        """Test Decimal precision is maintained"""
        config = TradingConfig(
            max_position_size_pct=Decimal("0.123456"),
            stop_loss_pct=Decimal("0.025")
        )
        
        assert config.max_position_size_pct == Decimal("0.123456")
        assert config.stop_loss_pct == Decimal("0.025")
    
    def test_trading_config_validation_errors(self):
        """Test trading configuration validation failures"""
        # Test negative values
        with pytest.raises(ValidationError):
            TradingConfig(max_position_size_pct=Decimal("-0.01"))
        
        # Test values outside allowed ranges
        with pytest.raises(ValidationError):
            TradingConfig(max_leverage=Decimal("25.0"))  # Above maximum
        
        with pytest.raises(ValidationError):
            TradingConfig(min_signal_strength=Decimal("1.5"))  # Above maximum


class TestBotConfig:
    """Test main bot configuration validation and composition"""
    
    def test_bot_config_default_composition(self):
        """Test bot configuration includes all sub-configurations"""
        config = BotConfig()
        
        assert isinstance(config.websocket, WebSocketConfig)
        assert isinstance(config.trading, TradingConfig)
        assert isinstance(config.performance, PerformanceConfig)
        assert isinstance(config.injective, InjectiveConfig)
        
        assert config.environment == "development"
        assert config.log_level == "INFO"
    
    def test_bot_config_trading_validation(self):
        """Test cross-field trading configuration validation"""
        # Valid configuration should pass
        valid_trading = TradingConfig(
            max_position_size_pct=Decimal("0.1"),
            base_position_size_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
            take_profit_pct=Decimal("0.04")
        )
        
        config = BotConfig(trading=valid_trading)
        assert config.trading.max_position_size_pct > config.trading.base_position_size_pct
        
        # Invalid configuration should fail
        with pytest.raises(ValidationError) as exc_info:
            invalid_trading = TradingConfig(
                max_position_size_pct=Decimal("0.02"),  # Less than base
                base_position_size_pct=Decimal("0.05")
            )
            BotConfig(trading=invalid_trading)
        
        assert "max_position_size_pct must be greater than base_position_size_pct" in str(exc_info.value)
    
    def test_bot_config_stop_loss_take_profit_validation(self):
        """Test stop loss vs take profit validation"""
        with pytest.raises(ValidationError) as exc_info:
            invalid_trading = TradingConfig(
                stop_loss_pct=Decimal("0.05"),    # Greater than take profit
                take_profit_pct=Decimal("0.03")
            )
            BotConfig(trading=invalid_trading)
        
        assert "stop_loss_pct must be less than take_profit_pct" in str(exc_info.value)
    
    def test_bot_config_environment_validation(self):
        """Test environment field validation"""
        # Valid environments
        for env in ["development", "production", "testing"]:
            config = BotConfig(environment=env)
            assert config.environment == env
        
        # Invalid environment
        with pytest.raises(ValidationError):
            BotConfig(environment="invalid_env")
    
    def test_bot_config_log_level_validation(self):
        """Test log level field validation"""
        # Valid log levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = BotConfig(log_level=level)
            assert config.log_level == level
        
        # Invalid log level
        with pytest.raises(ValidationError):
            BotConfig(log_level="INVALID")
    
    def test_bot_config_from_env(self):
        """Test configuration creation from environment variables"""
        # Set environment variables
        os.environ["BOT_ENVIRONMENT"] = "production"
        os.environ["BOT_LOG_LEVEL"] = "WARNING"
        
        try:
            config = BotConfig.from_env()
            assert config.environment == "production"
            assert config.log_level == "WARNING"
        finally:
            # Clean up environment variables
            os.environ.pop("BOT_ENVIRONMENT", None)
            os.environ.pop("BOT_LOG_LEVEL", None)
    
    def test_bot_config_from_env_defaults(self):
        """Test configuration uses defaults when env vars not set"""
        # Ensure env vars are not set
        os.environ.pop("BOT_ENVIRONMENT", None)
        os.environ.pop("BOT_LOG_LEVEL", None)
        
        config = BotConfig.from_env()
        assert config.environment == "development"
        assert config.log_level == "INFO"


class TestPerformanceConfig:
    """Test performance configuration validation"""
    
    def test_performance_config_memory_limits(self):
        """Test memory configuration limits"""
        config = PerformanceConfig()
        
        assert config.max_memory_mb == 512
        assert config.circular_buffer_size == 10000
        assert config.gc_threshold_mb == 400
        
        # Test validation ranges
        with pytest.raises(ValidationError):
            PerformanceConfig(max_memory_mb=50)  # Below minimum
        
        with pytest.raises(ValidationError):
            PerformanceConfig(circular_buffer_size=500)  # Below minimum
    
    def test_performance_config_latency_targets(self):
        """Test latency target validation"""
        config = PerformanceConfig()
        
        assert config.websocket_processing_target_ms == 10
        assert config.signal_generation_target_ms == 50
        assert config.dashboard_refresh_target_ms == 100
        
        # Test reasonable ranges
        assert 1 <= config.websocket_processing_target_ms <= 100
        assert 10 <= config.signal_generation_target_ms <= 500


class TestInjectiveConfig:
    """Test Injective Protocol configuration"""
    
    def test_injective_config_defaults(self):
        """Test default Injective configuration"""
        config = InjectiveConfig()
        
        assert config.network == "mainnet"
        assert "injective.network" in config.grpc_endpoint
        assert "injective.network" in config.lcd_endpoint
        assert config.monitored_markets == ["*-USD"]
        assert config.paper_trading_balance == Decimal("10000")
    
    def test_injective_config_network_validation(self):
        """Test network field validation"""
        # Valid networks
        for network in ["mainnet", "testnet"]:
            config = InjectiveConfig(network=network)
            assert config.network == network
        
        # Invalid network
        with pytest.raises(ValidationError):
            InjectiveConfig(network="invalid_network")
    
    def test_injective_config_balance_validation(self):
        """Test paper trading balance validation"""
        config = InjectiveConfig(paper_trading_balance=Decimal("1000"))
        assert config.paper_trading_balance == Decimal("1000")
        
        # Test minimum balance
        with pytest.raises(ValidationError):
            InjectiveConfig(paper_trading_balance=Decimal("50"))  # Below minimum


# Performance and Memory Tests
class TestConfigPerformance:
    """Test configuration performance characteristics"""
    
    def test_config_creation_performance(self):
        """Test configuration creation is fast"""
        import time
        
        start_time = time.time()
        for _ in range(1000):
            config = BotConfig()
        end_time = time.time()
        
        creation_time = end_time - start_time
        assert creation_time < 1.0, f"Config creation too slow: {creation_time}s for 1000 instances"
    
    def test_config_memory_efficiency(self):
        """Test configuration objects are memory efficient"""
        import sys
        
        config = BotConfig()
        config_size = sys.getsizeof(config)
        
        # Configuration should be reasonably sized
        assert config_size < 10000, f"Config object too large: {config_size} bytes"
    
    def test_config_validation_performance(self):
        """Test validation doesn't significantly impact performance"""
        import time
        
        valid_data = {
            "environment": "production",
            "log_level": "INFO",
            "trading": {
                "max_position_size_pct": "0.1",
                "base_position_size_pct": "0.05"
            }
        }
        
        start_time = time.time()
        for _ in range(100):
            config = BotConfig(**valid_data)
        end_time = time.time()
        
        validation_time = end_time - start_time
        assert validation_time < 0.5, f"Validation too slow: {validation_time}s for 100 instances"
