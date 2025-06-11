"""
Unit tests for OrderbookProcessor - Layer 3 Market Data Processing

Test Coverage:
- Orderbook depth analysis
- Bid-ask spread calculations
- Price level aggregation
- Volume-weighted average price (VWAP)
- Market depth percentages
- Performance requirements
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

from injective_bot.models import OrderbookSnapshot, PriceLevel
from injective_bot.data.orderbook_processor import OrderbookProcessor, MarketDepthAnalysis, SpreadAnalysis


class TestOrderbookProcessor:
    """Test suite for OrderbookProcessor class."""

    @pytest.fixture
    def processor(self):
        """Create OrderbookProcessor instance for testing."""
        return OrderbookProcessor(
            depth_levels=10,
            spread_threshold=Decimal("0.01")
        )

    @pytest.fixture
    def sample_orderbook(self):
        """Generate sample orderbook snapshot for testing."""
        bids = [
            PriceLevel(price=Decimal("10.50"), quantity=Decimal("100")),
            PriceLevel(price=Decimal("10.49"), quantity=Decimal("200")),
            PriceLevel(price=Decimal("10.48"), quantity=Decimal("150")),
            PriceLevel(price=Decimal("10.47"), quantity=Decimal("300")),
            PriceLevel(price=Decimal("10.46"), quantity=Decimal("250"))
        ]
        
        asks = [
            PriceLevel(price=Decimal("10.51"), quantity=Decimal("120")),
            PriceLevel(price=Decimal("10.52"), quantity=Decimal("180")),
            PriceLevel(price=Decimal("10.53"), quantity=Decimal("160")),
            PriceLevel(price=Decimal("10.54"), quantity=Decimal("220")),
            PriceLevel(price=Decimal("10.55"), quantity=Decimal("190"))
        ]
        
        return OrderbookSnapshot(
            market_id="INJ/USDT",
            sequence=1,
            bids=bids,
            asks=asks,
            timestamp=datetime.now()
        )

    def test_processor_initialization(self, processor):
        """Test OrderbookProcessor initialization."""
        assert processor is not None
        assert processor.depth_levels == 10
        assert processor.spread_threshold == Decimal("0.01")

    def test_spread_calculation(self, processor, sample_orderbook):
        """Test bid-ask spread calculation."""
        spread_analysis = processor.calculate_spread(sample_orderbook)
        
        assert isinstance(spread_analysis, SpreadAnalysis)
        assert spread_analysis.absolute_spread == Decimal("0.01")  # 10.51 - 10.50
        assert spread_analysis.percentage_spread > Decimal("0")
        assert spread_analysis.mid_price == Decimal("10.505")  # (10.50 + 10.51) / 2

    def test_market_depth_analysis(self, processor, sample_orderbook):
        """Test market depth analysis."""
        depth_analysis = processor.analyze_market_depth(sample_orderbook)
        
        assert isinstance(depth_analysis, MarketDepthAnalysis)
        assert depth_analysis.total_bid_volume == Decimal("1000")  # Sum of bid quantities
        assert depth_analysis.total_ask_volume == Decimal("870")   # Sum of ask quantities
        assert depth_analysis.bid_ask_ratio > Decimal("1")        # More bids than asks

    def test_vwap_calculation(self, processor, sample_orderbook):
        """Test Volume Weighted Average Price calculation."""
        bid_vwap = processor.calculate_vwap(sample_orderbook.bids, depth=3)
        ask_vwap = processor.calculate_vwap(sample_orderbook.asks, depth=3)
        
        # VWAP should be weighted by volume
        assert isinstance(bid_vwap, Decimal)
        assert isinstance(ask_vwap, Decimal)
        assert bid_vwap < sample_orderbook.bids[0].price  # Should be lower due to weighting
        assert ask_vwap > sample_orderbook.asks[0].price  # Should be higher due to weighting

    def test_price_level_aggregation(self, processor, sample_orderbook):
        """Test price level aggregation within tick ranges."""
        aggregated_bids = processor.aggregate_price_levels(
            sample_orderbook.bids, 
            tick_size=Decimal("0.01")
        )
        
        assert isinstance(aggregated_bids, list)
        assert len(aggregated_bids) <= len(sample_orderbook.bids)
        
        # Verify aggregation maintains total volume
        original_volume = sum(level.quantity for level in sample_orderbook.bids)
        aggregated_volume = sum(level.quantity for level in aggregated_bids)
        assert original_volume == aggregated_volume

    def test_orderbook_imbalance(self, processor, sample_orderbook):
        """Test orderbook imbalance calculation."""
        imbalance = processor.calculate_imbalance(sample_orderbook)
        
        assert isinstance(imbalance, Decimal)
        assert Decimal("-1") <= imbalance <= Decimal("1")  # Should be normalized
        
        # Positive imbalance = more bid volume, negative = more ask volume
        total_bids = sum(level.quantity for level in sample_orderbook.bids)
        total_asks = sum(level.quantity for level in sample_orderbook.asks)
        
        if total_bids > total_asks:
            assert imbalance > Decimal("0")
        elif total_asks > total_bids:
            assert imbalance < Decimal("0")

    def test_performance_requirement(self, processor, sample_orderbook):
        """Test processing latency requirement (<50ms)."""
        import time
        
        start_time = time.perf_counter()
        
        # Process multiple operations
        processor.calculate_spread(sample_orderbook)
        processor.analyze_market_depth(sample_orderbook)
        processor.calculate_vwap(sample_orderbook.bids, depth=5)
        processor.calculate_vwap(sample_orderbook.asks, depth=5)
        processor.calculate_imbalance(sample_orderbook)
        
        end_time = time.perf_counter()
        
        processing_time_ms = (end_time - start_time) * 1000
        assert processing_time_ms < 50, f"Processing took {processing_time_ms:.2f}ms, exceeds 50ms limit"

    def test_empty_orderbook_handling(self, processor):
        """Test handling of empty orderbook."""
        empty_orderbook = OrderbookSnapshot(
            market_id="INJ/USDT",
            sequence=1,
            bids=[],
            asks=[],
            timestamp=datetime.now()
        )
        
        spread_analysis = processor.calculate_spread(empty_orderbook)
        assert spread_analysis.absolute_spread == Decimal("0")
        assert spread_analysis.mid_price == Decimal("0")

    def test_single_side_orderbook(self, processor):
        """Test handling of orderbook with only bids or asks."""
        bids_only = OrderbookSnapshot(
            market_id="INJ/USDT",
            sequence=1,
            bids=[PriceLevel(price=Decimal("10.50"), quantity=Decimal("100"))],
            asks=[],
            timestamp=datetime.now()
        )
        
        depth_analysis = processor.analyze_market_depth(bids_only)
        assert depth_analysis.total_bid_volume == Decimal("100")
        assert depth_analysis.total_ask_volume == Decimal("0")
        assert depth_analysis.bid_ask_ratio == Decimal("inf")  # Division by zero case

    def test_large_orderbook_processing(self, processor):
        """Test processing large orderbook (100+ levels)."""
        # Generate large orderbook
        large_bids = [
            PriceLevel(price=Decimal(f"{10.50 - i * 0.01:.2f}"), quantity=Decimal("100"))
            for i in range(50)
        ]
        large_asks = [
            PriceLevel(price=Decimal(f"{10.51 + i * 0.01:.2f}"), quantity=Decimal("100"))
            for i in range(50)
        ]
        
        large_orderbook = OrderbookSnapshot(
            market_id="INJ/USDT",
            sequence=1,
            bids=large_bids,
            asks=large_asks,
            timestamp=datetime.now()
        )
        
        # Should process without errors
        depth_analysis = processor.analyze_market_depth(large_orderbook)
        assert depth_analysis.total_bid_volume == Decimal("5000")
        assert depth_analysis.total_ask_volume == Decimal("5000")

    def test_precision_handling(self, processor):
        """Test handling of high-precision decimal calculations."""
        high_precision_bids = [
            PriceLevel(price=Decimal("10.123456789"), quantity=Decimal("100.987654321")),
            PriceLevel(price=Decimal("10.123456788"), quantity=Decimal("200.123456789"))
        ]
        
        # Should handle high precision without rounding errors
        vwap = processor.calculate_vwap(high_precision_bids, depth=2)
        assert isinstance(vwap, Decimal)
        assert vwap.as_tuple().exponent <= -9  # Maintains precision

    def test_market_depth_percentages(self, processor, sample_orderbook):
        """Test market depth percentage calculations."""
        depth_percentages = processor.calculate_depth_percentages(sample_orderbook)
        
        assert "1%" in depth_percentages
        assert "5%" in depth_percentages
        assert "10%" in depth_percentages
        
        # Each percentage should contain price range and volume
        for pct, data in depth_percentages.items():
            assert "price_range" in data
            assert "volume" in data
            assert isinstance(data["volume"], Decimal)

    def test_spread_classification(self, processor, sample_orderbook):
        """Test spread classification (tight, normal, wide)."""
        spread_analysis = processor.calculate_spread(sample_orderbook)
        classification = processor.classify_spread(spread_analysis)
        
        assert classification in ["tight", "normal", "wide"]
        
        # Test with artificially wide spread
        wide_asks = [PriceLevel(price=Decimal("11.00"), quantity=Decimal("100"))]
        wide_orderbook = OrderbookSnapshot(
            market_id="INJ/USDT",
            sequence=1,
            bids=sample_orderbook.bids,
            asks=wide_asks,
            timestamp=datetime.now()
        )
        
        wide_spread = processor.calculate_spread(wide_orderbook)
        wide_classification = processor.classify_spread(wide_spread)
        assert wide_classification == "wide"

    def test_concurrent_processing(self, processor, sample_orderbook):
        """Test concurrent orderbook processing."""
        import threading
        import time
        
        results = []
        errors = []
        
        def process_orderbook():
            try:
                result = processor.analyze_market_depth(sample_orderbook)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = [threading.Thread(target=process_orderbook) for _ in range(10)]
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0, f"Concurrent processing errors: {errors}"
        assert len(results) == 10
        
        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result.total_bid_volume == first_result.total_bid_volume
            assert result.total_ask_volume == first_result.total_ask_volume
