# Layer 1 Tests: Data Structures & Models - Signal Tests
"""
TDD tests for signal models
Following RED-GREEN-REFACTOR cycle
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import ValidationError

from injective_bot.models.signals import (
    SignalType, SignalStrength, IndicatorType,
    TechnicalIndicator, OrderbookSignal, VolumeSignal,
    PriceSignal, CompositeSignal
)


class TestTechnicalIndicator:
    """Test TechnicalIndicator model validation and behavior"""
    
    def test_technical_indicator_creation(self):
        """Test TechnicalIndicator creation with required fields"""
        indicator = TechnicalIndicator(
            name="RSI",
            type=IndicatorType.MOMENTUM,
            value=Decimal("45.5"),
            timeframe="1h",
            market_id="BTC-USD"
        )
        
        assert indicator.name == "RSI"
        assert indicator.type == IndicatorType.MOMENTUM
        assert indicator.value == Decimal("45.5")
        assert indicator.timeframe == "1h"
        assert indicator.market_id == "BTC-USD"
        assert indicator.confidence == Decimal("0.5")  # Default
        assert indicator.weight == Decimal("1.0")  # Default
    
    def test_technical_indicator_weighted_value(self):
        """Test weighted value calculation"""
        indicator = TechnicalIndicator(
            name="RSI",
            type=IndicatorType.MOMENTUM,
            value=Decimal("70"),
            normalized_value=Decimal("0.8"),
            confidence=Decimal("0.9"),
            weight=Decimal("2.0"),
            timeframe="1h",
            market_id="BTC-USD"
        )
        
        # weighted_value = normalized_value * confidence * weight
        expected = Decimal("0.8") * Decimal("0.9") * Decimal("2.0")
        assert indicator.weighted_value == expected


class TestOrderbookSignal:
    """Test OrderbookSignal model validation and behavior"""
    
    def test_orderbook_signal_creation(self):
        """Test OrderbookSignal creation"""
        signal = OrderbookSignal(
            market_id="BTC-USD",
            bid_ask_imbalance=Decimal("0.3"),
            volume_imbalance=Decimal("0.2"),
            depth_imbalance=Decimal("0.1"),
            buy_pressure=Decimal("0.6"),
            sell_pressure=Decimal("0.4"),
            total_liquidity=Decimal("1000000"),
            spread_percentage=Decimal("0.1"),
            signal_strength=Decimal("0.7"),
            confidence=Decimal("0.8")
        )
        
        assert signal.market_id == "BTC-USD"
        assert signal.bid_ask_imbalance == Decimal("0.3")
        assert signal.confidence == Decimal("0.8")
    
    def test_orderbook_signal_calculated_properties(self):
        """Test OrderbookSignal calculated properties"""
        signal = OrderbookSignal(
            market_id="BTC-USD",
            bid_ask_imbalance=Decimal("0.3"),
            volume_imbalance=Decimal("0.2"),
            depth_imbalance=Decimal("0.1"),
            buy_pressure=Decimal("0.6"),
            sell_pressure=Decimal("0.4"),
            total_liquidity=Decimal("1000000"),
            spread_percentage=Decimal("0.1"),
            signal_strength=Decimal("0.7"),
            confidence=Decimal("0.8")
        )
        
        # Test net pressure
        assert signal.net_pressure == Decimal("0.2")  # 0.6 - 0.4
        
        # Test overall imbalance
        expected_imbalance = (Decimal("0.3") + Decimal("0.2") + Decimal("0.1")) / 3
        assert signal.overall_imbalance == expected_imbalance
    
    def test_orderbook_signal_additional_properties(self):
        """Test additional OrderbookSignal calculated properties for coverage"""
        signal = OrderbookSignal(
            market_id="market_1",
            bid_ask_imbalance=Decimal("0.3"),
            volume_imbalance=Decimal("0.2"),
            depth_imbalance=Decimal("0.1"),
            buy_pressure=Decimal("0.6"),
            sell_pressure=Decimal("0.4"),
            total_liquidity=Decimal("1000000"),
            spread_percentage=Decimal("0.1"),
            signal_strength=Decimal("0.7"),
            confidence=Decimal("0.8")
        )
        # Test net pressure and overall imbalance already covered
        assert signal.net_pressure == Decimal("0.2")
        assert signal.overall_imbalance == Decimal("0.2")
    
    def test_price_signal_edge_cases(self):
        """Test PriceSignal edge cases for coverage"""
        # Test price position with valid support/resistance range
        price_signal = PriceSignal(
            market_id="market_1",
            timeframe="1h",
            current_price=Decimal("100"),
            support_level=Decimal("95"),
            resistance_level=Decimal("105")
        )
        expected_position = (Decimal("100") - Decimal("95")) / (Decimal("105") - Decimal("95"))
        assert price_signal.price_position_in_range == expected_position
        
        # Test trend strength with MA20 < MA50 (downtrend)
        downtrend_signal = PriceSignal(
            market_id="market_1",
            timeframe="1h",
            current_price=Decimal("100"),
            moving_average_20=Decimal("98"),
            moving_average_50=Decimal("102")
        )
        expected_strength = -(Decimal("102") - Decimal("98")) / Decimal("98")
        assert downtrend_signal.trend_strength == expected_strength


class TestVolumeSignal:
    """Test VolumeSignal model validation and behavior"""
    
    def test_volume_signal_creation(self):
        """Test VolumeSignal creation"""
        signal = VolumeSignal(
            market_id="BTC-USD",
            timeframe="1h",
            current_volume=Decimal("1000"),
            average_volume=Decimal("500"),
            volume_ratio=Decimal("2.0"),
            buy_volume=Decimal("600"),
            sell_volume=Decimal("400"),
            volume_imbalance=Decimal("0.2"),
            signal_strength=Decimal("0.8")
        )
        
        assert signal.market_id == "BTC-USD"
        assert signal.timeframe == "1h"
        assert signal.current_volume == Decimal("1000")
        assert signal.volume_ratio == Decimal("2.0")
    
    def test_volume_signal_calculated_properties(self):
        """Test VolumeSignal calculated properties"""
        signal = VolumeSignal(
            market_id="BTC-USD",
            timeframe="1h",
            current_volume=Decimal("1000"),
            average_volume=Decimal("500"),
            volume_ratio=Decimal("2.0"),
            buy_volume=Decimal("600"),
            sell_volume=Decimal("400"),
            volume_imbalance=Decimal("0.2"),
            signal_strength=Decimal("0.8")
        )
        
        # Test volume surge factor
        assert signal.volume_surge_factor == Decimal("2.0")  # 1000/500
        
        # Test net volume bias
        expected_bias = (Decimal("600") - Decimal("400")) / (Decimal("600") + Decimal("400"))
        assert signal.net_volume_bias == expected_bias
    
    def test_volume_signal_zero_average_volume(self):
        """Test volume surge factor with zero average volume"""
        signal = VolumeSignal(
            market_id="market_1",
            timeframe="1h",
            current_volume=Decimal("1000"),
            average_volume=Decimal("0"),  # Zero average
            volume_ratio=Decimal("1.0"),
            buy_volume=Decimal("600"),
            sell_volume=Decimal("400"),
            volume_imbalance=Decimal("0.2"),
            signal_strength=Decimal("0.8")
        )
        # Should return 1.0 when average volume is zero
        assert signal.volume_surge_factor == Decimal("1.0")
    
    def test_volume_signal_net_volume_bias_edge_cases(self):
        """Test net volume bias calculation edge cases"""
        # Equal buy and sell volume
        signal = VolumeSignal(
            market_id="market_1",
            timeframe="1h",
            current_volume=Decimal("1000"),
            average_volume=Decimal("500"),
            volume_ratio=Decimal("2.0"),
            buy_volume=Decimal("500"),
            sell_volume=Decimal("500"),
            volume_imbalance=Decimal("0.0"),
            signal_strength=Decimal("0.8")
        )
        assert signal.net_volume_bias == Decimal("0")
        
        # Zero total volume
        signal_zero = VolumeSignal(
            market_id="market_1",
            timeframe="1h",
            current_volume=Decimal("0"),
            average_volume=Decimal("500"),
            volume_ratio=Decimal("0.0"),
            buy_volume=Decimal("0"),
            sell_volume=Decimal("0"),
            volume_imbalance=Decimal("0.0"),
            signal_strength=Decimal("0.1")
        )
        assert signal_zero.net_volume_bias == Decimal("0")


class TestCompositeSignal:
    """Test CompositeSignal model validation and behavior"""
    
    def test_composite_signal_creation(self):
        """Test CompositeSignal creation"""
        signal = CompositeSignal(
            signal_id="signal_123",
            market_id="BTC-USD",
            signal_type=SignalType.BUY,
            signal_strength=SignalStrength.STRONG,
            confidence=Decimal("0.8"),
            risk_score=Decimal("0.3"),
            strategy_name="momentum_sniper"
        )
        
        assert signal.signal_id == "signal_123"
        assert signal.signal_type == SignalType.BUY
        assert signal.signal_strength == SignalStrength.STRONG
        assert signal.confidence == Decimal("0.8")
        assert signal.strategy_name == "momentum_sniper"
    
    def test_composite_signal_actionable_check(self):
        """Test if signal is actionable"""
        # Actionable signal
        signal = CompositeSignal(
            signal_id="signal_123",
            market_id="BTC-USD",
            signal_type=SignalType.BUY,
            signal_strength=SignalStrength.STRONG,
            confidence=Decimal("0.8"),
            risk_score=Decimal("0.2"),
            strategy_name="momentum_sniper"
        )
        
        # Should be actionable (composite_score >= 0.6, confidence >= 0.7, not HOLD)
        assert signal.is_actionable
        
        # Non-actionable signal (HOLD)
        hold_signal = CompositeSignal(
            signal_id="signal_124",
            market_id="BTC-USD",
            signal_type=SignalType.HOLD,
            signal_strength=SignalStrength.STRONG,
            confidence=Decimal("0.8"),
            risk_score=Decimal("0.2"),
            strategy_name="momentum_sniper"
        )
        
        assert not hold_signal.is_actionable


class TestSignalValidation:
    """Test signal model validation"""
    
    def test_timeframe_validation(self):
        """Test timeframe validation across signal models"""
        # Valid timeframes
        valid_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        
        for timeframe in valid_timeframes:
            indicator = TechnicalIndicator(
                name="RSI",
                type=IndicatorType.MOMENTUM,
                value=Decimal("50"),
                timeframe=timeframe,
                market_id="BTC-USD"
            )
            assert indicator.timeframe == timeframe
        
        # Invalid timeframe
        with pytest.raises(ValidationError):
            TechnicalIndicator(
                name="RSI",
                type=IndicatorType.MOMENTUM,
                value=Decimal("50"),
                timeframe="invalid",
                market_id="BTC-USD"
            )


# Performance Tests for Signal Models
class TestSignalPerformance:
    """Test signal model performance characteristics"""
    
    def test_composite_signal_memory_efficiency(self):
        """Test CompositeSignal memory efficiency"""
        import sys
        
        signal = CompositeSignal(
            signal_id="test",
            market_id="BTC-USD",
            signal_type=SignalType.BUY,
            signal_strength=SignalStrength.MODERATE,
            confidence=Decimal("0.7"),
            risk_score=Decimal("0.3"),
            strategy_name="test_strategy"
        )
        
        object_size = sys.getsizeof(signal)
        assert object_size < 5000, f"CompositeSignal object too large: {object_size} bytes"
