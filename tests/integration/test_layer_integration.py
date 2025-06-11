# Layer 1-3 Integration Tests
"""
Integration tests for Data Structures -> Market Data Processing flow
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock
from typing import List, Dict, Any

from injective_bot.config import BotConfig, TradingConfig, WebSocketConfig, PerformanceConfig
from injective_bot.models import (
    MarketInfo, OrderbookSnapshot, OHLCVData, PriceLevel, TradeExecution,
    MarketSummary
)
from injective_bot.models.paper_trading import PaperOrder, PaperPosition, PaperAccount
from injective_bot.models.signals import (
    TechnicalIndicator, OrderbookSignal, VolumeSignal, 
    CompositeSignal, SignalType, SignalStrength
)


class TestConfigModelIntegration:
    """Test configuration integration with model validation"""
    
    def test_trading_config_with_paper_order_limits(self):
        """Test trading config limits apply to paper order validation"""
        config = TradingConfig(
            max_position_size_pct=Decimal("0.05"),
            base_position_size_pct=Decimal("0.02")
        )
        
        # Create paper account with config-based limits
        account = PaperAccount(
            account_id="test_account",
            balance=Decimal("10000"),
            available_balance=Decimal("10000")
        )
        
        # Test position size validation against config
        max_position_value = account.available_balance * config.max_position_size_pct
        assert max_position_value == Decimal("500")  # 10000 * 0.05
        
        # Test that position sizing respects config limits
        position_size = min(
            config.base_position_size_pct * account.available_balance,
            config.max_position_size_pct * account.available_balance
        )
        assert position_size == Decimal("200")  # 10000 * 0.02
    
    def test_performance_config_with_data_structures(self):
        """Test performance config limits with circular buffer sizes"""
        perf_config = PerformanceConfig(
            circular_buffer_size=1000,
            max_memory_mb=512
        )
        
        # Simulate OHLCV data buffer with config size
        ohlcv_buffer = []
        for i in range(perf_config.circular_buffer_size + 100):  # Exceed buffer size
            ohlcv = OHLCVData(
                market_id=f"market_{i % 10}",
                timeframe="1m",
                timestamp=datetime.now(timezone.utc),
                open_price=Decimal("100"),
                high_price=Decimal("105"),
                low_price=Decimal("95"),
                close_price=Decimal("102"),
                volume=Decimal("1000")
            )
            ohlcv_buffer.append(ohlcv)
            
            # Maintain circular buffer size
            if len(ohlcv_buffer) > perf_config.circular_buffer_size:
                ohlcv_buffer.pop(0)
        
        # Verify buffer size constraint is maintained
        assert len(ohlcv_buffer) == perf_config.circular_buffer_size


class TestMarketDataSignalIntegration:
    """Test integration between market data and signal generation"""
    
    def test_orderbook_to_orderbook_signal_flow(self):
        """Test orderbook data flowing into orderbook signals"""
        # Create realistic orderbook
        bids = [
            PriceLevel(price=Decimal("99.50"), quantity=Decimal("100")),
            PriceLevel(price=Decimal("99.00"), quantity=Decimal("200")),
            PriceLevel(price=Decimal("98.50"), quantity=Decimal("150"))
        ]
        asks = [
            PriceLevel(price=Decimal("100.50"), quantity=Decimal("80")),
            PriceLevel(price=Decimal("101.00"), quantity=Decimal("120")),
            PriceLevel(price=Decimal("101.50"), quantity=Decimal("90"))
        ]
        
        orderbook = OrderbookSnapshot(
            market_id="BTC-USD",
            sequence=12345,
            bids=bids,
            asks=asks
        )
        
        # Calculate imbalance metrics from orderbook
        total_bid_volume = orderbook.total_bid_volume  # 450
        total_ask_volume = orderbook.total_ask_volume  # 290
        
        # Create orderbook signal based on calculated metrics
        bid_ask_imbalance = (total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume)
        
        signal = OrderbookSignal(
            market_id="BTC-USD",
            bid_ask_imbalance=bid_ask_imbalance,
            volume_imbalance=Decimal("0.2"),
            depth_imbalance=Decimal("0.1"),
            buy_pressure=Decimal("0.6"),
            sell_pressure=Decimal("0.4"),
            total_liquidity=total_bid_volume + total_ask_volume,
            spread_percentage=orderbook.spread_percentage or Decimal("1.0"),
            signal_strength=Decimal("0.7"),
            confidence=Decimal("0.8")
        )
        
        # Verify signal reflects orderbook state
        assert signal.total_liquidity == Decimal("740")  # 450 + 290
        assert signal.bid_ask_imbalance > 0  # More bids than asks
        assert signal.net_pressure == Decimal("0.2")  # 0.6 - 0.4
    
    def test_ohlcv_to_technical_indicator_flow(self):
        """Test OHLCV data flowing into technical indicators"""
        # Create series of OHLCV data
        ohlcv_data = []
        for i in range(20):  # 20 periods for MA calculation
            ohlcv = OHLCVData(
                market_id="ETH-USD",
                timeframe="1h",
                timestamp=datetime.now(timezone.utc),
                open_price=Decimal(str(100 + i)),
                high_price=Decimal(str(105 + i)),
                low_price=Decimal(str(95 + i)),
                close_price=Decimal(str(102 + i)),
                volume=Decimal("1000")
            )
            ohlcv_data.append(ohlcv)
        
        # Calculate moving average from OHLCV data
        recent_closes = [data.close_price for data in ohlcv_data[-10:]]
        ma_10 = sum(recent_closes) / len(recent_closes)
        
        # Create technical indicator based on calculation
        indicator = TechnicalIndicator(
            name="MA_10",
            type="trend",
            value=ma_10,
            timeframe="1h",
            market_id="ETH-USD",
            weight=Decimal("1.0")
        )
        
        # Verify indicator reflects OHLCV data
        expected_ma = sum(Decimal(str(102 + i)) for i in range(10, 20)) / 10
        assert indicator.value == expected_ma
        assert indicator.market_id == "ETH-USD"


class TestSignalStrategyIntegration:
    """Test integration between signal generation and strategy decisions"""
    
    def test_multiple_signals_to_composite_signal(self):
        """Test combining multiple signal types into composite signal"""
        # Create various signal types
        volume_signal = VolumeSignal(
            market_id="BTC-USD",
            timeframe="1h",
            current_volume=Decimal("2000"),
            average_volume=Decimal("1000"),
            volume_ratio=Decimal("2.0"),
            buy_volume=Decimal("1200"),
            sell_volume=Decimal("800"),
            volume_imbalance=Decimal("0.2"),
            signal_strength=Decimal("0.8")
        )
        
        orderbook_signal = OrderbookSignal(
            market_id="BTC-USD",
            bid_ask_imbalance=Decimal("0.3"),
            volume_imbalance=Decimal("0.2"),
            depth_imbalance=Decimal("0.1"),
            buy_pressure=Decimal("0.7"),
            sell_pressure=Decimal("0.3"),
            total_liquidity=Decimal("1000000"),
            spread_percentage=Decimal("0.1"),
            signal_strength=Decimal("0.9"),
            confidence=Decimal("0.85")
        )
        
        technical_indicators = [
            TechnicalIndicator(
                name="RSI",
                type="momentum",
                value=Decimal("65"),
                timeframe="1h",
                market_id="BTC-USD"
            ),
            TechnicalIndicator(
                name="MACD",
                type="trend",
                value=Decimal("1.5"),
                timeframe="1h",
                market_id="BTC-USD"
            )
        ]
        
        # Create composite signal combining all signals
        composite = CompositeSignal(
            signal_id="composite_001",
            market_id="BTC-USD",
            signal_type=SignalType.BUY,
            signal_strength=SignalStrength.STRONG,
            confidence=Decimal("0.8"),
            risk_score=Decimal("0.3"),
            volume_signal=volume_signal,
            orderbook_signal=orderbook_signal,
            technical_indicators=technical_indicators,
            strategy_name="momentum_sniper"
        )
        
        # Verify composite signal aggregates individual signals
        assert composite.volume_signal.signal_strength == Decimal("0.8")
        assert composite.orderbook_signal.signal_strength == Decimal("0.9")
        assert len(composite.technical_indicators) == 2
        assert composite.is_actionable  # Should be actionable with strong signals


class TestPaperTradingIntegration:
    """Test integration between signals and paper trading execution"""
    
    def test_signal_to_paper_order_flow(self):
        """Test signal triggering paper order creation"""
        # Strong buy signal
        composite_signal = CompositeSignal(
            signal_id="signal_123",
            market_id="BTC-USD",
            signal_type=SignalType.BUY,
            signal_strength=SignalStrength.STRONG,
            confidence=Decimal("0.85"),
            risk_score=Decimal("0.2"),
            strategy_name="momentum_sniper"
        )
        
        # Create paper account
        account = PaperAccount(
            account_id="test_account",
            balance=Decimal("10000"),
            available_balance=Decimal("10000")
        )
        
        # Create trading config
        config = TradingConfig(
            base_position_size_pct=Decimal("0.02"),
            stop_loss_pct=Decimal("0.03"),
            take_profit_pct=Decimal("0.06")
        )
        
        # Calculate position size based on signal confidence and config
        base_size = account.available_balance * config.base_position_size_pct
        confidence_multiplier = composite_signal.confidence
        position_size = base_size * confidence_multiplier
        
        current_price = Decimal("45000")
        quantity = position_size / current_price
        
        # Create paper order based on signal
        order = PaperOrder(
            order_id="order_123",
            market_id="BTC-USD",
            side="buy",
            order_type="market",
            quantity=quantity,
            price=current_price,
            status="pending",
            created_at=datetime.now(timezone.utc)
        )
        
        # Verify order reflects signal characteristics
        assert order.market_id == composite_signal.market_id
        assert order.side == "buy"  # Matches signal type
        expected_position_value = Decimal("170")  # 10000 * 0.02 * 0.85
        assert abs(order.notional_value - expected_position_value) < Decimal("1")
    
    def test_paper_position_risk_integration(self):
        """Test paper position with risk management integration"""
        # Create position
        position = PaperPosition(
            position_id="pos_001",
            market_id="BTC-USD",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("45000"),
            current_price=Decimal("46000"),
            leverage=Decimal("2")
        )
        
        # Create risk config
        config = TradingConfig(
            stop_loss_pct=Decimal("0.03"),
            take_profit_pct=Decimal("0.06")
        )
        
        # Set stop-loss and take-profit based on config
        stop_loss_price = position.entry_price * (Decimal("1") - config.stop_loss_pct)
        take_profit_price = position.entry_price * (Decimal("1") + config.take_profit_pct)
        
        position_with_risk = PaperPosition(
            position_id="pos_001",
            market_id="BTC-USD",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("45000"),
            current_price=Decimal("46000"),
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            leverage=Decimal("2")
        )
        
        # Verify risk levels are set correctly
        assert position_with_risk.stop_loss_price == Decimal("43650")  # 45000 * 0.97
        assert position_with_risk.take_profit_price == Decimal("47700")  # 45000 * 1.06
        
        # Test risk trigger logic
        assert not position_with_risk.should_stop_loss()  # Current price above stop loss
        assert not position_with_risk.should_take_profit()  # Current price below take profit


class TestMemoryPerformanceIntegration:
    """Test memory efficiency across integrated components"""
    
    def test_integrated_memory_efficiency(self):
        """Test memory usage of integrated component workflow"""
        import sys
        
        # Create full workflow objects
        config = BotConfig()
        
        # Market data
        orderbook = OrderbookSnapshot(
            market_id="BTC-USD",
            sequence=1,
            bids=[PriceLevel(price=Decimal("99"), quantity=Decimal("10"))],
            asks=[PriceLevel(price=Decimal("101"), quantity=Decimal("8"))]
        )
        
        # Signal
        signal = CompositeSignal(
            signal_id="signal_001",
            market_id="BTC-USD",
            signal_type=SignalType.BUY,
            signal_strength=SignalStrength.MODERATE,
            confidence=Decimal("0.7"),
            risk_score=Decimal("0.3"),
            strategy_name="test_strategy"
        )
        
        # Paper trading
        account = PaperAccount(
            account_id="account_001",
            balance=Decimal("10000"),
            available_balance=Decimal("10000")
        )
        
        # Calculate total memory usage
        total_size = (
            sys.getsizeof(config) +
            sys.getsizeof(orderbook) +
            sys.getsizeof(signal) +
            sys.getsizeof(account)
        )
        
        # Verify integrated components stay within memory limits
        assert total_size < 10000  # <10KB for integrated components
