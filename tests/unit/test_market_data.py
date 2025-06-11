# Layer 1 Tests: Data Structures & Models - Market Data Tests
"""
TDD tests for market data models
Following RED-GREEN-REFACTOR cycle
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import ValidationError

from injective_bot.models import (
    MarketInfo, MarketStatus, OrderSide, OrderType,
    PriceLevel, OrderbookSnapshot, OHLCVData,
    TradeExecution, MarketSummary
)


class TestMarketInfo:
    """Test MarketInfo model validation and behavior"""
    
    def test_market_info_creation_with_required_fields(self):
        """Test MarketInfo creation with all required fields"""
        market = MarketInfo(
            market_id="0x1234",
            ticker="BTC-USD",
            base_denom="BTC",
            quote_denom="USD",
            tick_size=Decimal("0.01"),
            lot_size=Decimal("0.001"),
            min_price_tick_size=Decimal("0.01"),
            min_quantity_tick_size=Decimal("0.001")
        )
        
        assert market.market_id == "0x1234"
        assert market.ticker == "BTC-USD"
        assert market.base_denom == "BTC"
        assert market.quote_denom == "USD"
        assert market.tick_size == Decimal("0.01")
        assert market.status == MarketStatus.ACTIVE  # Default value
    
    def test_market_info_default_values(self):
        """Test default values are set correctly"""
        market = MarketInfo(
            market_id="test",
            ticker="TEST",
            base_denom="TEST",
            quote_denom="USD",
            tick_size=Decimal("1"),
            lot_size=Decimal("1"),
            min_price_tick_size=Decimal("1"),
            min_quantity_tick_size=Decimal("1")
        )
        
        assert market.maker_fee_rate == Decimal("0.001")
        assert market.taker_fee_rate == Decimal("0.002")
        assert market.status == MarketStatus.ACTIVE
        assert isinstance(market.created_at, datetime)
        assert isinstance(market.updated_at, datetime)
    
    def test_market_info_validation_errors(self):
        """Test validation errors for invalid inputs"""
        # Test zero/negative tick size
        with pytest.raises(ValidationError):
            MarketInfo(
                market_id="test",
                ticker="TEST",
                base_denom="TEST",
                quote_denom="USD",
                tick_size=Decimal("0"),  # Must be > 0
                lot_size=Decimal("1"),
                min_price_tick_size=Decimal("1"),
                min_quantity_tick_size=Decimal("1")
            )
        
        # Test empty market_id
        with pytest.raises(ValidationError):
            MarketInfo(
                market_id="",  # Empty string not allowed
                ticker="TEST",
                base_denom="TEST",
                quote_denom="USD",
                tick_size=Decimal("1"),
                lot_size=Decimal("1"),
                min_price_tick_size=Decimal("1"),
                min_quantity_tick_size=Decimal("1")
            )


class TestPriceLevel:
    """Test PriceLevel model validation and behavior"""
    
    def test_price_level_creation(self):
        """Test PriceLevel creation and properties"""
        level = PriceLevel(
            price=Decimal("100.50"),
            quantity=Decimal("5.0")
        )
        
        assert level.price == Decimal("100.50")
        assert level.quantity == Decimal("5.0")
        assert level.notional_value == Decimal("502.50")
    
    def test_price_level_zero_quantity(self):
        """Test PriceLevel with zero quantity"""
        level = PriceLevel(
            price=Decimal("100"),
            quantity=Decimal("0")
        )
        
        assert level.notional_value == Decimal("0")
    
    def test_price_level_validation_errors(self):
        """Test validation errors for PriceLevel"""
        # Test zero price
        with pytest.raises(ValidationError):
            PriceLevel(price=Decimal("0"), quantity=Decimal("1"))
        
        # Test negative price
        with pytest.raises(ValidationError):
            PriceLevel(price=Decimal("-1"), quantity=Decimal("1"))
        
        # Test negative quantity
        with pytest.raises(ValidationError):
            PriceLevel(price=Decimal("1"), quantity=Decimal("-1"))


class TestOrderbookSnapshot:
    """Test OrderbookSnapshot model validation and behavior"""
    
    def test_orderbook_snapshot_creation(self):
        """Test basic OrderbookSnapshot creation"""
        bids = [
            PriceLevel(price=Decimal("99"), quantity=Decimal("10")),
            PriceLevel(price=Decimal("98"), quantity=Decimal("5"))
        ]
        asks = [
            PriceLevel(price=Decimal("101"), quantity=Decimal("8")),
            PriceLevel(price=Decimal("102"), quantity=Decimal("3"))
        ]
        
        orderbook = OrderbookSnapshot(
            market_id="BTC-USD",
            sequence=12345,
            bids=bids,
            asks=asks
        )
        
        assert orderbook.market_id == "BTC-USD"
        assert orderbook.sequence == 12345
        assert len(orderbook.bids) == 2
        assert len(orderbook.asks) == 2
    
    def test_orderbook_snapshot_properties(self):
        """Test OrderbookSnapshot calculated properties"""
        bids = [
            PriceLevel(price=Decimal("99"), quantity=Decimal("10")),
            PriceLevel(price=Decimal("98"), quantity=Decimal("5"))
        ]
        asks = [
            PriceLevel(price=Decimal("101"), quantity=Decimal("8")),
            PriceLevel(price=Decimal("102"), quantity=Decimal("3"))
        ]
        
        orderbook = OrderbookSnapshot(
            market_id="BTC-USD",
            sequence=1,
            bids=bids,
            asks=asks
        )
        
        # Test best bid/ask
        assert orderbook.best_bid.price == Decimal("99")
        assert orderbook.best_ask.price == Decimal("101")
        
        # Test spread
        assert orderbook.spread == Decimal("2")
        assert orderbook.spread_percentage == Decimal("2")  # (2/100)*100
        
        # Test volume calculations
        assert orderbook.total_bid_volume == Decimal("15")  # 10 + 5
        assert orderbook.total_ask_volume == Decimal("11")  # 8 + 3
    
    def test_orderbook_snapshot_empty_sides(self):
        """Test OrderbookSnapshot with empty bid or ask sides"""
        orderbook = OrderbookSnapshot(
            market_id="BTC-USD",
            sequence=1,
            bids=[],
            asks=[]
        )
        
        assert orderbook.best_bid is None
        assert orderbook.best_ask is None
        assert orderbook.spread is None
        assert orderbook.spread_percentage is None
        assert orderbook.total_bid_volume == Decimal("0")
        assert orderbook.total_ask_volume == Decimal("0")
    
    def test_orderbook_snapshot_bid_sorting_validation(self):
        """Test that bids must be sorted from highest to lowest price"""
        # Correctly sorted bids should pass
        correct_bids = [
            PriceLevel(price=Decimal("99"), quantity=Decimal("10")),
            PriceLevel(price=Decimal("98"), quantity=Decimal("5"))
        ]
        
        orderbook = OrderbookSnapshot(
            market_id="BTC-USD",
            sequence=1,
            bids=correct_bids,
            asks=[]
        )
        assert len(orderbook.bids) == 2
        
        # Incorrectly sorted bids should fail
        with pytest.raises(ValidationError) as exc_info:
            OrderbookSnapshot(
                market_id="BTC-USD",
                sequence=1,
                bids=[
                    PriceLevel(price=Decimal("98"), quantity=Decimal("10")),  # Lower price first
                    PriceLevel(price=Decimal("99"), quantity=Decimal("5"))   # Higher price second
                ],
                asks=[]
            )
        assert "highest to lowest price" in str(exc_info.value)
    
    def test_orderbook_snapshot_ask_sorting_validation(self):
        """Test that asks must be sorted from lowest to highest price"""
        # Correctly sorted asks should pass
        correct_asks = [
            PriceLevel(price=Decimal("101"), quantity=Decimal("8")),
            PriceLevel(price=Decimal("102"), quantity=Decimal("3"))
        ]
        
        orderbook = OrderbookSnapshot(
            market_id="BTC-USD",
            sequence=1,
            bids=[],
            asks=correct_asks
        )
        assert len(orderbook.asks) == 2
        
        # Incorrectly sorted asks should fail
        with pytest.raises(ValidationError) as exc_info:
            OrderbookSnapshot(
                market_id="BTC-USD",
                sequence=1,
                bids=[],
                asks=[
                    PriceLevel(price=Decimal("102"), quantity=Decimal("8")),  # Higher price first
                    PriceLevel(price=Decimal("101"), quantity=Decimal("3"))   # Lower price second
                ]
            )
        assert "lowest to highest price" in str(exc_info.value)


class TestOHLCVData:
    """Test OHLCVData model validation and behavior"""
    
    def test_ohlcv_data_creation(self):
        """Test OHLCV data creation with valid inputs"""
        ohlcv = OHLCVData(
            market_id="BTC-USD",
            timestamp=datetime.now(timezone.utc),
            timeframe="1h",
            open_price=Decimal("100"),
            high_price=Decimal("105"),
            low_price=Decimal("98"),
            close_price=Decimal("103"),
            volume=Decimal("1000")
        )
        
        assert ohlcv.market_id == "BTC-USD"
        assert ohlcv.timeframe == "1h"
        assert ohlcv.open_price == Decimal("100")
        assert ohlcv.high_price == Decimal("105")
        assert ohlcv.low_price == Decimal("98")
        assert ohlcv.close_price == Decimal("103")
        assert ohlcv.volume == Decimal("1000")
    
    def test_ohlcv_data_calculated_properties(self):
        """Test OHLCV calculated properties"""
        ohlcv = OHLCVData(
            market_id="BTC-USD",
            timestamp=datetime.now(timezone.utc),
            timeframe="1h",
            open_price=Decimal("100"),
            high_price=Decimal("110"),
            low_price=Decimal("95"),
            close_price=Decimal("105"),
            volume=Decimal("500")
        )
        
        # Test calculated properties
        assert ohlcv.price_range == Decimal("15")  # 110 - 95
        assert ohlcv.price_change == Decimal("5")  # 105 - 100
        assert ohlcv.price_change_percentage == Decimal("5")  # (5/100)*100
        assert ohlcv.typical_price == Decimal("103.3333333333333333333333333")  # (110+95+105)/3
    
    def test_ohlcv_data_timeframe_validation(self):
        """Test timeframe validation"""
        # Valid timeframes
        for timeframe in ["1m", "5m", "15m", "1h", "4h", "1d"]:
            ohlcv = OHLCVData(
                market_id="BTC-USD",
                timestamp=datetime.now(timezone.utc),
                timeframe=timeframe,
                open_price=Decimal("100"),
                high_price=Decimal("100"),
                low_price=Decimal("100"),
                close_price=Decimal("100"),
                volume=Decimal("0")
            )
            assert ohlcv.timeframe == timeframe
        
        # Invalid timeframe
        with pytest.raises(ValidationError):
            OHLCVData(
                market_id="BTC-USD",
                timestamp=datetime.now(timezone.utc),
                timeframe="invalid",  # Not in allowed list
                open_price=Decimal("100"),
                high_price=Decimal("100"),
                low_price=Decimal("100"),
                close_price=Decimal("100"),
                volume=Decimal("0")
            )
    
    def test_ohlcv_data_price_validation(self):
        """Test OHLCV price validation logic"""
        # Valid OHLCV where high >= all other prices and low <= all other prices
        ohlcv = OHLCVData(
            market_id="BTC-USD",
            timestamp=datetime.now(timezone.utc),
            timeframe="1h",
            open_price=Decimal("100"),
            high_price=Decimal("105"),  # Highest
            low_price=Decimal("98"),    # Lowest
            close_price=Decimal("103"),
            volume=Decimal("1000")
        )
        assert ohlcv.high_price == Decimal("105")
        assert ohlcv.low_price == Decimal("98")
        
        # Test high price validation - high must be >= open
        with pytest.raises(ValidationError):
            OHLCVData(
                market_id="BTC-USD",
                timestamp=datetime.now(timezone.utc),
                timeframe="1h",
                open_price=Decimal("100"),
                high_price=Decimal("95"),   # Less than open
                low_price=Decimal("90"),
                close_price=Decimal("98"),
                volume=Decimal("1000")
            )
        
        # Test low price validation - low must be <= open
        with pytest.raises(ValidationError):
            OHLCVData(
                market_id="BTC-USD",
                timestamp=datetime.now(timezone.utc),
                timeframe="1h",
                open_price=Decimal("100"),
                high_price=Decimal("105"),
                low_price=Decimal("102"),   # Greater than open
                close_price=Decimal("98"),
                volume=Decimal("1000")
            )
    
    def test_ohlcv_data_high_price_validation_errors(self):
        """Test high price validation errors"""
        # High price less than open price (first validation that triggers)
        with pytest.raises(ValidationError) as excinfo:
            OHLCVData(
                market_id="test_market",
                timeframe="1m",
                timestamp=datetime.now(timezone.utc),
                open_price=Decimal("100"),
                high_price=Decimal("94"),  # Less than open
                low_price=Decimal("95"),
                close_price=Decimal("98"),
                volume=Decimal("1000")
            )
        assert "High price must be >= open price" in str(excinfo.value)
    
    def test_ohlcv_data_low_price_validation_errors(self):
        """Test low price validation errors"""
        # Low price greater than open price (first validation that triggers)
        with pytest.raises(ValidationError) as excinfo:
            OHLCVData(
                market_id="test_market",
                timeframe="1m",
                timestamp=datetime.now(timezone.utc),
                open_price=Decimal("100"),
                high_price=Decimal("105"),
                low_price=Decimal("101"),  # Greater than open
                close_price=Decimal("98"),
                volume=Decimal("1000")
            )
        assert "Low price must be <= open price" in str(excinfo.value)
    



class TestTradeExecution:
    """Test TradeExecution model validation and behavior"""
    
    def test_trade_execution_creation(self):
        """Test TradeExecution creation"""
        trade = TradeExecution(
            trade_id="trade_123",
            market_id="BTC-USD",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            side=OrderSide.BUY
        )
        
        assert trade.trade_id == "trade_123"
        assert trade.market_id == "BTC-USD"
        assert trade.price == Decimal("50000")
        assert trade.quantity == Decimal("0.1")
        assert trade.side == OrderSide.BUY
        assert isinstance(trade.timestamp, datetime)
    
    def test_trade_execution_notional_value(self):
        """Test notional value calculation"""
        trade = TradeExecution(
            trade_id="trade_123",
            market_id="BTC-USD",
            price=Decimal("50000"),
            quantity=Decimal("0.5"),
            side=OrderSide.SELL
        )
        
        # Notional value should be calculated automatically
        assert trade.notional_value == Decimal("25000")  # 50000 * 0.5


class TestMarketSummary:
    """Test MarketSummary model validation and behavior"""
    
    def test_market_summary_creation(self):
        """Test MarketSummary creation"""
        summary = MarketSummary(
            market_id="BTC-USD",
            last_price=Decimal("50000"),
            price_change_24h=Decimal("1000"),
            price_change_percentage_24h=Decimal("2.0"),
            high_24h=Decimal("51000"),
            low_24h=Decimal("48000"),
            volume_24h=Decimal("1000000")
        )
        
        assert summary.market_id == "BTC-USD"
        assert summary.last_price == Decimal("50000")
        assert summary.price_change_24h == Decimal("1000")
        assert summary.volume_24h == Decimal("1000000")
    
    def test_market_summary_spread_calculation(self):
        """Test spread calculation when best bid/ask are available"""
        summary = MarketSummary(
            market_id="BTC-USD",
            last_price=Decimal("50000"),
            price_change_24h=Decimal("0"),
            price_change_percentage_24h=Decimal("0"),
            high_24h=Decimal("50000"),
            low_24h=Decimal("50000"),
            volume_24h=Decimal("0"),
            best_bid=Decimal("49950"),
            best_ask=Decimal("50050")
        )
        
        assert summary.spread == Decimal("100")  # 50050 - 49950
    
    def test_market_summary_no_spread_when_missing_prices(self):
        """Test spread is None when best bid/ask are missing"""
        summary = MarketSummary(
            market_id="BTC-USD",
            last_price=Decimal("50000"),
            price_change_24h=Decimal("0"),
            price_change_percentage_24h=Decimal("0"),
            high_24h=Decimal("50000"),
            low_24h=Decimal("50000"),
            volume_24h=Decimal("0")
            # No best_bid or best_ask
        )
        
        assert summary.spread is None


# Performance and Memory Tests for Market Data Models
class TestMarketDataPerformance:
    """Test market data model performance characteristics"""
    
    def test_orderbook_snapshot_performance(self):
        """Test OrderbookSnapshot performance with large data"""
        import time
        
        # Create large orderbook
        bids = [PriceLevel(price=Decimal(f"{100-i}"), quantity=Decimal("1")) for i in range(50)]
        asks = [PriceLevel(price=Decimal(f"{101+i}"), quantity=Decimal("1")) for i in range(50)]
        
        start_time = time.time()
        orderbook = OrderbookSnapshot(
            market_id="BTC-USD",
            sequence=1,
            bids=bids,
            asks=asks
        )
        creation_time = time.time() - start_time
        
        # Orderbook creation should be fast
        assert creation_time < 0.1, f"Orderbook creation too slow: {creation_time}s"
        
        # Property access should be fast
        start_time = time.time()
        for _ in range(1000):
            _ = orderbook.best_bid
            _ = orderbook.best_ask
            _ = orderbook.spread
        property_time = time.time() - start_time
        
        assert property_time < 0.1, f"Property access too slow: {property_time}s for 1000 calls"
    
    def test_ohlcv_data_memory_efficiency(self):
        """Test OHLCV data memory efficiency"""
        import sys
        
        ohlcv = OHLCVData(
            market_id="BTC-USD",
            timestamp=datetime.now(timezone.utc),
            timeframe="1h",
            open_price=Decimal("100"),
            high_price=Decimal("105"),
            low_price=Decimal("98"),
            close_price=Decimal("103"),
            volume=Decimal("1000")
        )
        
        object_size = sys.getsizeof(ohlcv)
        assert object_size < 5000, f"OHLCV object too large: {object_size} bytes"
