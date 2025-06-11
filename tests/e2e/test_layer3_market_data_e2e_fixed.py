"""
Layer 3 End-to-End Tests: Market Data Processing Pipeline

Tests Layer 3 components with realistic data patterns:
- Data processing performance validation
- System behavior under sustained load
- Integration with market data patterns
- Memory stability under extended operation
- Error recovery scenarios
"""

import pytest
import asyncio
import time
import random
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from injective_bot.connection import WebSocketMessage, MessageType
from injective_bot.models import OrderbookSnapshot, PriceLevel, TradeExecution
from injective_bot.data import (
    MarketDataAggregator, OrderbookProcessor, DataValidator,
    CircularBuffer, PerformanceMonitor
)
from injective_bot.data.aggregator import TimeFrame, OHLCVData


class RealisticDataGenerator:
    """Generates realistic market data patterns for E2E testing"""
    
    def __init__(self, markets: List[str] = None):
        self.markets = markets or ["INJ/USDT", "BTC/USDT", "ETH/USDT"]
        self.base_prices = {market: Decimal("100.0") for market in self.markets}
        self.trade_counter = 0
        self.sequence_counter = 0
    
    def generate_trade_sequence_across_time(self, market_id: str, count: int = 10) -> List[WebSocketMessage]:
        """Generate trades across different time periods to trigger OHLCV completion"""
        messages = []
        base_time = datetime.now(timezone.utc)
        
        for i in range(count):
            # Spread trades across 2+ minutes to trigger candle completion
            time_offset = timedelta(seconds=i * 15)  # 15 seconds apart
            trade_time = base_time + time_offset
            
            # Small realistic price movements
            price_change_pct = Decimal(str(random.uniform(-0.002, 0.002)))  # 0.2% max
            self.base_prices[market_id] *= (1 + price_change_pct)
            
            trade_data = {
                "trades": [{
                    "trade_id": f"time_spread_{self.trade_counter:06d}",
                    "market_id": market_id,
                    "side": random.choice(["buy", "sell"]),
                    "quantity": str(Decimal(str(random.uniform(100, 500)))),
                    "price": str(self.base_prices[market_id].quantize(Decimal("0.01"))),
                    "timestamp": trade_time.isoformat()
                }]
            }
            
            message = WebSocketMessage(
                message_id=f"trade_time_{self.trade_counter}",
                message_type=MessageType.TRADES,
                data=trade_data,
                timestamp=trade_time,
                market_id=market_id
            )
            
            messages.append(message)
            self.trade_counter += 1
        
        return messages
    
    def generate_multi_market_data(self, duration_seconds: int = 30) -> List[WebSocketMessage]:
        """Generate data for multiple markets"""
        messages = []
        
        for market in self.markets:
            # Generate trades for each market
            trade_messages = self.generate_trade_sequence_across_time(market, count=10)
            messages.extend(trade_messages)
            
            # Generate orderbook for each market
            orderbook_message = self.generate_realistic_orderbook(market)
            messages.append(orderbook_message)
        
        return messages
    
    def generate_realistic_orderbook(self, market_id: str) -> WebSocketMessage:
        """Generate realistic orderbook data"""
        current_price = self.base_prices[market_id]
        
        # Generate realistic bid/ask spread (0.1-0.5%)
        spread_pct = Decimal(str(random.uniform(0.001, 0.005)))
        mid_spread = current_price * spread_pct / 2
        
        bids = []
        asks = []
        
        # Generate 5 levels each side
        for i in range(5):
            bid_price = current_price - mid_spread - (Decimal(str(i)) * mid_spread / 5)
            ask_price = current_price + mid_spread + (Decimal(str(i)) * mid_spread / 5)
            
            bids.append({
                "price": str(bid_price.quantize(Decimal("0.01"))),
                "quantity": str(Decimal(str(random.uniform(100, 1000))))
            })
            
            asks.append({
                "price": str(ask_price.quantize(Decimal("0.01"))),
                "quantity": str(Decimal(str(random.uniform(100, 1000))))
            })
        
        orderbook_data = {
            "orderbook": {
                "market_id": market_id,
                "sequence": self.sequence_counter,
                "bids": bids,
                "asks": asks
            }
        }
        
        self.sequence_counter += 1
        
        return WebSocketMessage(
            message_id=f"orderbook_{self.sequence_counter}",
            message_type=MessageType.ORDERBOOK,
            data=orderbook_data,
            timestamp=datetime.now(timezone.utc),
            market_id=market_id
        )


class Layer3E2EProcessor:
    """End-to-end processor for Layer 3 components"""
    
    def __init__(self):
        self.aggregator = MarketDataAggregator(
            timeframes=[TimeFrame.ONE_MINUTE, TimeFrame.FIVE_MINUTES]
        )
        self.validator = DataValidator()
        self.orderbook_processor = OrderbookProcessor()
        self.performance_monitor = PerformanceMonitor()
        
        self.processed_trades = []
        self.processed_orderbooks = []
        self.validation_errors = []
        self.performance_metrics = []
    
    async def process_message_stream(self, messages: List[WebSocketMessage]) -> Dict[str, Any]:
        """Process a stream of messages through Layer 3 pipeline"""
        start_time = time.time()
        
        for message in messages:
            processing_start = time.time()
            
            try:
                timer_start = self.performance_monitor.start_timer("e2e_processing")
                await self._process_single_message(message)
                processing_time = self.performance_monitor.end_timer("e2e_processing", timer_start)
                    
                self.performance_metrics.append({
                    "message_id": message.message_id,
                    "processing_time_ms": processing_time,
                    "message_type": message.message_type.value
                })
                
            except Exception as e:
                self.validation_errors.append(f"Processing error: {str(e)}")
        
        total_time = time.time() - start_time
        
        return {
            "total_processing_time_seconds": total_time,
            "messages_processed": len(messages),
            "trades_processed": len(self.processed_trades),
            "orderbooks_processed": len(self.processed_orderbooks),
            "validation_errors": len(self.validation_errors),
            "avg_processing_time_ms": sum(m["processing_time_ms"] for m in self.performance_metrics) / len(self.performance_metrics) if self.performance_metrics else 0,
            "ohlcv_generated": self._count_total_ohlcv(),
            "performance_grade": self.performance_monitor.get_performance_report().get("grade", "N/A")
        }
    
    async def _process_single_message(self, message: WebSocketMessage) -> None:
        """Process a single message through the Layer 3 pipeline"""
        if message.message_type == MessageType.TRADES:
            await self._process_trades_message(message)
        elif message.message_type == MessageType.ORDERBOOK:
            await self._process_orderbook_message(message)
    
    async def _process_trades_message(self, message: WebSocketMessage) -> None:
        """Process trades through Layer 3 pipeline"""
        if "trades" in message.data:
            trades_data = message.data["trades"]
            if isinstance(trades_data, list):
                for trade_data in trades_data:
                    # Validate
                    validation_result = await self.validator.validate_trade_data(trade_data)
                    if validation_result.is_valid:
                        # Convert to model
                        trade = TradeExecution(
                            trade_id=trade_data.get("trade_id", f"e2e_{int(time.time()*1000)}"),
                            market_id=trade_data.get("market_id", message.market_id or "UNKNOWN"),
                            side=trade_data.get("side", "buy"),
                            quantity=Decimal(str(trade_data.get("quantity", "0"))),
                            price=Decimal(str(trade_data.get("price", "0"))),
                            timestamp=datetime.fromisoformat(trade_data.get("timestamp", datetime.now(timezone.utc).isoformat())) if "timestamp" in trade_data else datetime.now(timezone.utc)
                        )
                        
                        # Process through aggregator
                        completed_candles = await self.aggregator.process_trade(trade)
                        self.processed_trades.append(trade)
    
    async def _process_orderbook_message(self, message: WebSocketMessage) -> None:
        """Process orderbook through Layer 3 pipeline"""
        if "orderbook" in message.data:
            orderbook_data = message.data["orderbook"]
            
            # Validate
            validation_result = await self.validator.validate_orderbook_data(orderbook_data)
            if validation_result.is_valid:
                # Convert to model
                bids = []
                asks = []
                
                for bid_data in orderbook_data.get("bids", []):
                    bids.append(PriceLevel(
                        price=Decimal(str(bid_data.get("price", "0"))),
                        quantity=Decimal(str(bid_data.get("quantity", "0")))
                    ))
                
                for ask_data in orderbook_data.get("asks", []):
                    asks.append(PriceLevel(
                        price=Decimal(str(ask_data.get("price", "0"))),
                        quantity=Decimal(str(ask_data.get("quantity", "0")))
                    ))
                
                orderbook = OrderbookSnapshot(
                    market_id=orderbook_data.get("market_id", message.market_id or "UNKNOWN"),
                    bids=bids,
                    asks=asks,
                    sequence=orderbook_data.get("sequence", 0),
                    timestamp=message.timestamp
                )
                
                # Process through orderbook processor
                analysis = await self.orderbook_processor.process_orderbook(orderbook)
                self.processed_orderbooks.append(orderbook)
    
    def _count_total_ohlcv(self) -> int:
        """Count total OHLCV candles generated across all timeframes"""
        total = 0
        for timeframe in [TimeFrame.ONE_MINUTE, TimeFrame.FIVE_MINUTES]:
            historical_data = self.aggregator.get_historical_data(timeframe)
            total += len(historical_data)
        return total


@pytest.mark.e2e
class TestLayer3E2EDataProcessing:
    """E2E tests for Layer 3 data processing pipeline"""
    
    @pytest.fixture
    def data_generator(self):
        return RealisticDataGenerator()
    
    @pytest.fixture
    def e2e_processor(self):
        return Layer3E2EProcessor()
    
    @pytest.mark.asyncio
    async def test_realistic_market_data_processing_e2e(self, data_generator, e2e_processor):
        """Test: Realistic market data processing pipeline E2E"""
        # Arrange - Generate trades across time to trigger OHLCV completion
        messages = data_generator.generate_trade_sequence_across_time("INJ/USDT", count=50)
        
        # Add some orderbook messages
        for i in range(5):
            orderbook_msg = data_generator.generate_realistic_orderbook("INJ/USDT")
            messages.append(orderbook_msg)
        
        # Act - Process realistic message stream
        report = await e2e_processor.process_message_stream(messages)
        
        # Assert - Comprehensive validation
        assert report["messages_processed"] == len(messages)
        assert report["validation_errors"] == 0
        assert report["avg_processing_time_ms"] < 50.0  # Layer 3 requirement
        
        # Should generate OHLCV data with time-spread trades
        assert report["ohlcv_generated"] >= 1  # At least some OHLCV generated
        assert report["trades_processed"] >= 40  # Most trades processed
        assert report["orderbooks_processed"] >= 4  # Most orderbooks processed
    
    @pytest.mark.asyncio
    async def test_high_frequency_trading_load_e2e(self, data_generator, e2e_processor):
        """Test: High frequency data processing capability"""
        # Arrange - Generate high volume of messages
        messages = []
        
        # 100 trades across time
        for market in ["INJ/USDT", "BTC/USDT"]:
            market_messages = data_generator.generate_trade_sequence_across_time(market, count=50)
            messages.extend(market_messages)
        
        # Act - Process high frequency stream
        start_time = time.time()
        report = await e2e_processor.process_message_stream(messages)
        total_time = time.time() - start_time
        
        # Assert - Performance under load
        assert report["avg_processing_time_ms"] < 50.0  # Maintain performance
        assert report["validation_errors"] == 0  # No errors under load
        assert total_time < 10.0  # Complete processing within 10 seconds
        
        # Throughput calculation
        throughput = len(messages) / total_time
        assert throughput > 10  # At least 10 messages/second
    
    @pytest.mark.asyncio
    async def test_multi_market_concurrent_processing_e2e(self, data_generator, e2e_processor):
        """Test: Concurrent multi-market processing"""
        # Arrange - Generate data for multiple markets
        messages = data_generator.generate_multi_market_data(duration_seconds=30)
        
        # Act - Process multi-market stream
        report = await e2e_processor.process_message_stream(messages)
        
        # Assert - Multi-market handling
        processed_markets = set()
        for trade in e2e_processor.processed_trades:
            processed_markets.add(trade.market_id)
        
        for orderbook in e2e_processor.processed_orderbooks:
            processed_markets.add(orderbook.market_id)
        
        assert len(processed_markets) >= 2  # At least 2 markets processed
        assert report["validation_errors"] == 0
        assert report["avg_processing_time_ms"] < 50.0
    
    @pytest.mark.asyncio
    async def test_extended_operation_memory_stability_e2e(self, data_generator, e2e_processor):
        """Test: Memory stability under extended operation"""
        import psutil
        process = psutil.Process()
        
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Arrange - Extended data processing
        for batch in range(5):  # 5 batches
            messages = data_generator.generate_trade_sequence_across_time("INJ/USDT", count=20)
            await e2e_processor.process_message_stream(messages)
            
            # Check memory after each batch
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory
            
            # Memory should not grow excessively
            assert memory_growth < 50, f"Memory growth {memory_growth:.1f}MB exceeds limit after batch {batch}"
    
    @pytest.mark.asyncio
    async def test_layer3_performance_sla_compliance_e2e(self, data_generator, e2e_processor):
        """Test: Layer 3 performance SLA compliance"""
        # Arrange - Performance test data
        messages = data_generator.generate_trade_sequence_across_time("INJ/USDT", count=30)
        
        # Act - Process with performance monitoring
        report = await e2e_processor.process_message_stream(messages)
        performance_report = e2e_processor.performance_monitor.get_performance_report()
        
        # Assert - SLA compliance
        assert report["avg_processing_time_ms"] < 50.0  # Core requirement
        
        if "e2e_processing" in performance_report["metrics"]:
            e2e_metrics = performance_report["metrics"]["e2e_processing"]
            assert e2e_metrics["avg_latency_ms"] < 50.0  # Average latency
            assert e2e_metrics["p95_latency_ms"] < 100.0  # 95th percentile
        
        # Performance grade should be good
        assert performance_report["grade"] in ["A", "B", "C"]
        
        # SLA compliance check
        sla_compliance = e2e_processor.performance_monitor.check_sla_compliance()
        assert sla_compliance["overall_compliance"] >= 0.95  # 95% SLA compliance
