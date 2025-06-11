"""
Unit tests for MarketDataAggregator - Layer 3 Market Data Processing

Test Coverage:
- OHLCV aggregation from trade data
- Multiple timeframe support (1m, 5m, 15m, 1h, 4h, 1d)
- Real-time candlestick updates
- Volume calculations
- Memory efficiency
- Performance requirements (<50ms)
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from injective_bot.models import TradeExecution, OHLCVData
from injective_bot.data.aggregator import MarketDataAggregator, OHLCVData, TimeFrame


class TestMarketDataAggregator:
    """Test suite for MarketDataAggregator class."""

    @pytest.fixture
    def aggregator(self):
        """Create MarketDataAggregator instance for testing."""
        return MarketDataAggregator(
            timeframes=[TimeFrame.ONE_MINUTE, TimeFrame.FIVE_MINUTE],
            buffer_size=1000
        )

    @pytest.fixture
    def sample_trades(self):
        """Generate sample trade executions for testing."""
        base_time = datetime.now().replace(second=0, microsecond=0)
        return [
            TradeExecution(
                trade_id="trade_1",
                market_id="INJ/USDT",
                price=Decimal("10.50"),
                quantity=Decimal("100"),
                side="buy",
                timestamp=base_time,
                message_id="msg_1"
            ),
            TradeExecution(
                trade_id="trade_2", 
                market_id="INJ/USDT",
                price=Decimal("10.55"),
                quantity=Decimal("200"),
                side="sell",
                timestamp=base_time + timedelta(seconds=30),
                message_id="msg_2"
            ),
            TradeExecution(
                trade_id="trade_3",
                market_id="INJ/USDT", 
                price=Decimal("10.48"),
                quantity=Decimal("150"),
                side="buy",
                timestamp=base_time + timedelta(seconds=45),
                message_id="msg_3"
            )
        ]

    def test_aggregator_initialization(self, aggregator):
        """Test MarketDataAggregator initialization."""
        assert aggregator is not None
        assert len(aggregator.timeframes) == 2
        assert TimeFrame.ONE_MINUTE in aggregator.timeframes
        assert TimeFrame.FIVE_MINUTE in aggregator.timeframes
        assert aggregator.buffer_size == 1000

    def test_process_single_trade(self, aggregator, sample_trades):
        """Test processing a single trade execution."""
        trade = sample_trades[0]
        result = aggregator.process_trade(trade)
        
        assert result is not None
        assert isinstance(result, dict)
        assert TimeFrame.ONE_MINUTE in result
        assert TimeFrame.FIVE_MINUTE in result

    def test_ohlcv_aggregation_accuracy(self, aggregator, sample_trades):
        """Test accurate OHLCV calculation from multiple trades."""
        for trade in sample_trades:
            aggregator.process_trade(trade)
        
        one_min_data = aggregator.get_ohlcv_data(TimeFrame.ONE_MINUTE)
        assert one_min_data is not None
        
        # Verify OHLCV calculations
        assert one_min_data.open == Decimal("10.50")  # First trade price
        assert one_min_data.high == Decimal("10.55")  # Highest price
        assert one_min_data.low == Decimal("10.48")   # Lowest price
        assert one_min_data.close == Decimal("10.48") # Last trade price
        assert one_min_data.volume == Decimal("450")  # Total volume

    def test_multiple_timeframe_aggregation(self, aggregator, sample_trades):
        """Test simultaneous aggregation across multiple timeframes."""
        for trade in sample_trades:
            aggregator.process_trade(trade)
        
        one_min = aggregator.get_ohlcv_data(TimeFrame.ONE_MINUTE)
        five_min = aggregator.get_ohlcv_data(TimeFrame.FIVE_MINUTE)
        
        assert one_min is not None
        assert five_min is not None
        assert one_min.volume == five_min.volume  # Same trades in both
        assert one_min.open == five_min.open
        assert one_min.high == five_min.high

    def test_candlestick_completion(self, aggregator):
        """Test candlestick completion and new candle creation."""
        base_time = datetime.now().replace(second=0, microsecond=0)
        
        # Trade in first minute
        trade1 = TradeExecution(
            trade_id="trade_1",
            market_id="INJ/USDT",
            price=Decimal("10.50"),
            quantity=Decimal("100"),
            side="buy",
            timestamp=base_time,
            message_id="msg_1"
        )
        
        # Trade in next minute (should create new candle)
        trade2 = TradeExecution(
            trade_id="trade_2",
            market_id="INJ/USDT", 
            price=Decimal("10.60"),
            quantity=Decimal("200"),
            side="sell",
            timestamp=base_time + timedelta(minutes=1),
            message_id="msg_2"
        )
        
        aggregator.process_trade(trade1)
        aggregator.process_trade(trade2)
        
        # Should have 2 completed candles
        candles = aggregator.get_completed_candles(TimeFrame.ONE_MINUTE)
        assert len(candles) >= 1  # At least one completed candle

    def test_performance_requirement(self, aggregator, sample_trades):
        """Test processing latency requirement (<50ms)."""
        import time
        
        start_time = time.perf_counter()
        for trade in sample_trades:
            aggregator.process_trade(trade)
        end_time = time.perf_counter()
        
        processing_time_ms = (end_time - start_time) * 1000
        assert processing_time_ms < 50, f"Processing took {processing_time_ms:.2f}ms, exceeds 50ms limit"

    def test_volume_calculation_accuracy(self, aggregator):
        """Test accurate volume calculation with different trade sizes."""
        trades = [
            TradeExecution(
                trade_id=f"trade_{i}",
                market_id="INJ/USDT",
                price=Decimal("10.50"),
                quantity=Decimal(str(100 * (i + 1))),  # 100, 200, 300, etc.
                side="buy" if i % 2 == 0 else "sell",
                timestamp=datetime.now(),
                message_id=f"msg_{i}"
            ) for i in range(5)
        ]
        
        for trade in trades:
            aggregator.process_trade(trade)
        
        ohlcv = aggregator.get_ohlcv_data(TimeFrame.ONE_MINUTE)
        expected_volume = Decimal("1500")  # 100+200+300+400+500
        assert ohlcv.volume == expected_volume

    def test_memory_efficiency(self, aggregator):
        """Test memory efficiency with large number of trades."""
        # Simulate 1000 trades
        for i in range(1000):
            trade = TradeExecution(
                trade_id=f"trade_{i}",
                market_id="INJ/USDT",
                price=Decimal("10.50"),
                quantity=Decimal("100"),
                side="buy",
                timestamp=datetime.now(),
                message_id=f"msg_{i}"
            )
            aggregator.process_trade(trade)
        
        # Should not exceed buffer size
        assert len(aggregator._data_buffer) <= aggregator.buffer_size

    def test_high_frequency_processing(self, aggregator):
        """Test processing 1000+ trades per second."""
        import time
        
        start_time = time.perf_counter()
        for i in range(1000):
            trade = TradeExecution(
                trade_id=f"trade_{i}",
                market_id="INJ/USDT",
                price=Decimal("10.50"),
                quantity=Decimal("100"),
                side="buy",
                timestamp=datetime.now(),
                message_id=f"msg_{i}"
            )
            aggregator.process_trade(trade)
        end_time = time.perf_counter()
        
        processing_time = end_time - start_time
        trades_per_second = 1000 / processing_time
        assert trades_per_second >= 1000, f"Only processed {trades_per_second:.0f} trades/sec"

    def test_invalid_trade_handling(self, aggregator):
        """Test handling of invalid or malformed trade data."""
        # Test with None
        result = aggregator.process_trade(None)
        assert result is None
        
        # Test with invalid market_id - should fail during model creation
        with pytest.raises(ValueError):  # Pydantic ValidationError is a subclass of ValueError
            invalid_trade = TradeExecution(
                trade_id="invalid",
                market_id="",  # Empty market ID
                price=Decimal("10.50"),
                quantity=Decimal("100"),
                side="buy",
                timestamp=datetime.now(),
                message_id="msg_invalid"
            )

    def test_get_historical_data(self, aggregator, sample_trades):
        """Test retrieval of historical OHLCV data."""
        for trade in sample_trades:
            aggregator.process_trade(trade)
        
        # Get last N candles
        historical = aggregator.get_historical_ohlcv(TimeFrame.ONE_MINUTE, limit=10)
        assert isinstance(historical, list)
        assert len(historical) <= 10
        
        # Each item should be OHLCVData
        for candle in historical:
            assert isinstance(candle, OHLCVData)

    def test_timeframe_enum_support(self):
        """Test support for all required timeframes."""
        required_timeframes = [
            TimeFrame.ONE_MINUTE,
            TimeFrame.FIVE_MINUTE, 
            TimeFrame.FIFTEEN_MINUTE,
            TimeFrame.ONE_HOUR,
            TimeFrame.FOUR_HOUR,
            TimeFrame.ONE_DAY
        ]
        
        aggregator = MarketDataAggregator(timeframes=required_timeframes)
        assert len(aggregator.timeframes) == 6
        
        for tf in required_timeframes:
            assert tf in aggregator.timeframes
