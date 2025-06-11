"""
Layer 2-3 Integration Tests: WebSocket to Market Data Processing Pipeline

Tests the complete data flow from WebSocket messages through Layer 3 processing:
- WebSocket → DataValidator → Aggregator → CircularBuffer
- WebSocket → DataValidator → OrderbookProcessor → Analysis
- Performance integration testing
- Error handling and recovery integration
"""

import pytest
import asyncio
import time
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock
from typing import List, Dict, Any

from injective_bot.connection import (
    ConnectionState, MessageType, WebSocketMessage, MessageHandler
)
from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.models import (
    OrderbookSnapshot, PriceLevel, TradeExecution, OHLCVData
)
from injective_bot.data import (
    MarketDataAggregator, OrderbookProcessor, DataValidator, 
    CircularBuffer, PerformanceMonitor
)
from injective_bot.data.aggregator import TimeFrame


class Layer3IntegrationHandler(MessageHandler):
    """Integration handler that processes WebSocket data through Layer 3 components"""
    
    def __init__(self):
        self.data_validator = DataValidator()
        self.aggregator = MarketDataAggregator(
            timeframes=[TimeFrame.ONE_MINUTE, TimeFrame.FIVE_MINUTE],
            buffer_size=1000
        )
        self.orderbook_processor = OrderbookProcessor()
        self.performance_monitor = PerformanceMonitor()
        
        # Track processed results
        self.processed_trades = []
        self.processed_orderbooks = []
        self.ohlcv_data = []
        self.orderbook_analyses = []
        self.validation_errors = []
        self.performance_metrics = []

    def get_current_candles_count(self) -> int:
        """Get count of current incomplete candles across all markets/timeframes"""
        total_candles = 0
        for market_candles in self.aggregator._current_candles.values():
            total_candles += len(market_candles)
        return total_candles
        
    def get_total_ohlcv_count(self) -> int:
        """Get total OHLCV data count (completed + current incomplete)"""
        return len(self.ohlcv_data) + self.get_current_candles_count()

    def get_supported_message_types(self) -> List[MessageType]:
        """Get supported message types for Layer 3 processing"""
        return [MessageType.TRADES, MessageType.ORDERBOOK, MessageType.MARKET_DATA]

    async def handle_message(self, message: WebSocketMessage) -> None:
        """Process WebSocket message through complete Layer 3 pipeline"""
        start_time = time.perf_counter()
        
        try:
            # Time the complete Layer 3 processing pipeline
            timer_start = self.performance_monitor.start_timer("layer3_integration")
            
            if message.message_type == MessageType.TRADES:
                await self._process_trades_integration(message)
            elif message.message_type == MessageType.ORDERBOOK:
                await self._process_orderbook_integration(message)
            elif message.message_type == MessageType.MARKET_DATA:
                await self._process_market_data_integration(message)
            
            # Record successful processing
            processing_time = self.performance_monitor.end_timer("layer3_integration", timer_start)
            self.performance_metrics.append({
                "message_id": message.message_id,
                "message_type": message.message_type.value,
                "processing_time_ms": processing_time,
                "timestamp": datetime.now(timezone.utc)
            })
            
        except Exception as e:
            self.validation_errors.append(f"Integration processing error: {str(e)}")
        finally:
            # Always record total processing time
            total_time = (time.perf_counter() - start_time) * 1000
            self.performance_metrics.append({
                "total_time_ms": total_time,
                "message_id": message.message_id
            })

    async def _process_trades_integration(self, message: WebSocketMessage) -> None:
        """Process trades through complete Layer 3 integration pipeline"""
        if "trades" in message.data:
            trades_data = message.data["trades"]
            if isinstance(trades_data, list):
                for trade_data in trades_data:
                    try:
                        # Step 1: Convert to model
                        trade = TradeExecution(
                            trade_id=trade_data.get("trade_id", f"integ_{int(time.time()*1000)}"),
                            market_id=trade_data.get("market_id", message.market_id or "UNKNOWN"),
                            side=trade_data.get("side", "buy"),
                            quantity=Decimal(str(trade_data.get("quantity", "0"))),
                            price=Decimal(str(trade_data.get("price", "0"))),
                            timestamp=datetime.now(timezone.utc)
                        )
                        
                        # Step 2: Validate with DataValidator
                        validation_result = self.data_validator.validate_trade(trade)
                        if validation_result.is_valid:
                            # Step 3: Process through MarketDataAggregator
                            completed_candles = self.aggregator.process_trade(trade)
                            if completed_candles:
                                self.ohlcv_data.extend(completed_candles)
                            
                            self.processed_trades.append(trade)
                        else:
                            self.validation_errors.extend(validation_result.errors)
                            
                    except Exception as e:
                        self.validation_errors.append(f"Trade integration error: {str(e)}")

    async def _process_orderbook_integration(self, message: WebSocketMessage) -> None:
        """Process orderbook through complete Layer 3 integration pipeline"""
        if "orderbook" in message.data:
            orderbook_data = message.data["orderbook"]
            
            try:
                # Step 1: Convert to model
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
                
                # Step 2: Validate with DataValidator
                validation_result = self.data_validator.validate_orderbook(orderbook)
                if validation_result.is_valid:
                    # Step 3: Process through OrderbookProcessor
                    spread_analysis = self.orderbook_processor.calculate_spread(orderbook)
                    depth_analysis = self.orderbook_processor.analyze_market_depth(orderbook)
                    
                    self.orderbook_analyses.append({
                        "spread": spread_analysis,
                        "depth": depth_analysis,
                        "orderbook": orderbook
                    })
                    
                    self.processed_orderbooks.append(orderbook)
                else:
                    self.validation_errors.extend(validation_result.errors)
                    
            except Exception as e:
                self.validation_errors.append(f"Orderbook integration error: {str(e)}")

    async def _process_market_data_integration(self, message: WebSocketMessage) -> None:
        """Process market data through Layer 3 integration pipeline"""
        # Handle market data updates that might contain both trades and orderbook
        if "trades" in message.data:
            await self._process_trades_integration(message)
        if "orderbook" in message.data:
            await self._process_orderbook_integration(message)

    def get_integration_metrics(self) -> Dict[str, Any]:
        """Get comprehensive integration metrics"""
        return {
            "processed_trades": len(self.processed_trades),
            "processed_orderbooks": len(self.processed_orderbooks),
            "ohlcv_generated": len(self.ohlcv_data),
            "current_candles": self.get_current_candles_count(),
            "total_ohlcv": self.get_total_ohlcv_count(),
            "orderbook_analyses": len(self.orderbook_analyses),
            "validation_errors": len(self.validation_errors),
            "performance_metrics": len(self.performance_metrics),
            "avg_processing_time_ms": sum(
                m.get("processing_time_ms", 0) for m in self.performance_metrics
            ) / len(self.performance_metrics) if self.performance_metrics else 0,
            "performance_report": self.performance_monitor.get_performance_report()
        }


@pytest.mark.integration
class TestLayer3DataIntegration:
    """Integration tests for Layer 2-3 WebSocket to Market Data Processing pipeline"""
    
    @pytest.fixture
    def integration_handler(self):
        """Layer 3 integration handler for testing"""
        return Layer3IntegrationHandler()
    
    @pytest.fixture
    def sample_trade_message(self):
        """Sample trade message for integration testing"""
        return WebSocketMessage(
            message_id="integ_trade_001",
            message_type=MessageType.TRADES,
            data={
                "trades": [{
                    "trade_id": "test_trade_001",
                    "market_id": "INJ/USDT",
                    "side": "buy",
                    "quantity": "100.500",
                    "price": "25.75",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }]
            },
            timestamp=datetime.now(timezone.utc),
            market_id="INJ/USDT"
        )
    
    @pytest.fixture
    def sample_orderbook_message(self):
        """Sample orderbook message for integration testing"""
        return WebSocketMessage(
            message_id="integ_orderbook_001",
            message_type=MessageType.ORDERBOOK,
            data={
                "orderbook": {
                    "market_id": "INJ/USDT",
                    "sequence": 12345,
                    "bids": [
                        {"price": "25.74", "quantity": "500.000"},
                        {"price": "25.73", "quantity": "750.000"}
                    ],
                    "asks": [
                        {"price": "25.76", "quantity": "400.000"},
                        {"price": "25.77", "quantity": "600.000"}
                    ]
                }
            },
            timestamp=datetime.now(timezone.utc),
            market_id="INJ/USDT"
        )
    
    @pytest.mark.asyncio
    async def test_layer3_trade_processing_integration(self, integration_handler, sample_trade_message):
        """Test: Complete trade processing through Layer 2-3 integration"""
        # Act
        await integration_handler.handle_message(sample_trade_message)
        
        # Assert
        metrics = integration_handler.get_integration_metrics()
        
        assert metrics["processed_trades"] == 1
        assert metrics["validation_errors"] == 0
        assert metrics["avg_processing_time_ms"] < 50.0  # Performance requirement
        
        # Verify trade was processed through aggregator
        processed_trade = integration_handler.processed_trades[0]
        assert processed_trade.market_id == "INJ/USDT"
        assert processed_trade.quantity == Decimal("100.500")
        assert processed_trade.price == Decimal("25.75")
    
    @pytest.mark.asyncio
    async def test_layer3_orderbook_processing_integration(self, integration_handler, sample_orderbook_message):
        """Test: Complete orderbook processing through Layer 2-3 integration"""
        # Act
        await integration_handler.handle_message(sample_orderbook_message)
        
        # Assert
        metrics = integration_handler.get_integration_metrics()
        
        assert metrics["processed_orderbooks"] == 1
        assert metrics["orderbook_analyses"] == 1
        assert metrics["validation_errors"] == 0
        assert metrics["avg_processing_time_ms"] < 50.0
        
        # Verify orderbook analysis
        analysis = integration_handler.orderbook_analyses[0]
        assert "spread" in analysis
        assert "depth" in analysis
        assert analysis["spread"].market_id == "INJ/USDT"
    
    @pytest.mark.asyncio
    async def test_layer3_performance_integration(self, integration_handler):
        """Test: Layer 3 performance under integration load"""
        # Arrange - Create multiple messages
        messages = []
        for i in range(100):
            trade_msg = WebSocketMessage(
                message_id=f"perf_trade_{i:03d}",
                message_type=MessageType.TRADES,
                data={
                    "trades": [{
                        "trade_id": f"perf_trade_{i:03d}",
                        "market_id": "INJ/USDT",
                        "side": "buy" if i % 2 == 0 else "sell",
                        "quantity": f"{100 + i}.000",
                        "price": f"{25.00 + (i * 0.01):.2f}",
                        "timestamp": (datetime.now(timezone.utc) + timedelta(seconds=i)).isoformat()
                    }]
                },
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=i),
                market_id="INJ/USDT"
            )
            messages.append(trade_msg)
        
        # Act - Process all messages
        start_time = time.perf_counter()
        for message in messages:
            await integration_handler.handle_message(message)
        total_time = time.perf_counter() - start_time
        
        # Assert - Performance requirements
        metrics = integration_handler.get_integration_metrics()
        
        assert metrics["processed_trades"] == 100
        assert metrics["validation_errors"] == 0
        assert metrics["avg_processing_time_ms"] < 50.0
        assert total_time < 5.0  # Should process 100 messages in under 5 seconds
        
        # Memory efficiency check
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        assert memory_mb < 512  # Memory should stay under 512MB
    
    @pytest.mark.asyncio
    async def test_layer3_ohlcv_generation_integration(self, integration_handler):
        """Test: OHLCV generation through complete integration pipeline"""
        # Arrange - Create trade sequence that should trigger OHLCV completion
        base_time = datetime.now(timezone.utc) - timedelta(minutes=2)
        
        trades = []
        for i in range(10):
            trade_time = base_time + timedelta(seconds=i * 30)  # 30 seconds apart
            trade_msg = WebSocketMessage(
                message_id=f"ohlcv_trade_{i:03d}",
                message_type=MessageType.TRADES,
                data={
                    "trades": [{
                        "trade_id": f"ohlcv_trade_{i:03d}",
                        "market_id": "INJ/USDT",
                        "side": "buy" if i % 2 == 0 else "sell",
                        "quantity": "100.000",
                        "price": f"{25.00 + (i * 0.10):.2f}",
                        "timestamp": trade_time.isoformat()
                    }]
                },
                timestamp=trade_time,
                market_id="INJ/USDT"
            )
            trades.append(trade_msg)
        
        # Act - Process trades across time
        for trade in trades:
            await integration_handler.handle_message(trade)
        
        # Assert - OHLCV generation
        metrics = integration_handler.get_integration_metrics()
        
        assert metrics["processed_trades"] == 10
        assert metrics["total_ohlcv"] >= 1  # Should have at least some OHLCV data
        assert metrics["validation_errors"] == 0
    
    @pytest.mark.asyncio
    async def test_layer3_error_handling_integration(self, integration_handler):
        """Test: Error handling in Layer 3 integration pipeline"""
        # Arrange - Create invalid message
        invalid_message = WebSocketMessage(
            message_id="invalid_001",
            message_type=MessageType.TRADES,
            data={
                "trades": [{
                    "trade_id": "invalid_trade",
                    "market_id": "INJ/USDT",
                    "side": "invalid_side",  # Invalid side
                    "quantity": "not_a_number",  # Invalid quantity
                    "price": "-1.00",  # Invalid price
                    "timestamp": "invalid_timestamp"  # Invalid timestamp
                }]
            },
            timestamp=datetime.now(timezone.utc),
            market_id="INJ/USDT"
        )
        
        # Act
        await integration_handler.handle_message(invalid_message)
        
        # Assert - Error handling
        metrics = integration_handler.get_integration_metrics()
        
        assert metrics["processed_trades"] == 0  # No trades should be processed
        assert metrics["validation_errors"] > 0  # Should have validation errors
        assert metrics["avg_processing_time_ms"] < 50.0  # Should still meet performance requirements
    
    @pytest.mark.asyncio
    async def test_layer3_multi_market_integration(self, integration_handler):
        """Test: Multi-market processing through Layer 3 integration"""
        # Arrange - Messages from multiple markets
        markets = ["INJ/USDT", "BTC/USDT", "ETH/USDT"]
        messages = []
        
        for market in markets:
            for i in range(5):
                trade_msg = WebSocketMessage(
                    message_id=f"{market.replace('/', '')}_trade_{i:03d}",
                    message_type=MessageType.TRADES,
                    data={
                        "trades": [{
                            "trade_id": f"{market.replace('/', '')}_trade_{i:03d}",
                            "market_id": market,
                            "side": "buy",
                            "quantity": "100.000",
                            "price": f"{100.00 + i * 10:.2f}",
                            "timestamp": (datetime.now(timezone.utc) + timedelta(seconds=i)).isoformat()
                        }]
                    },
                    timestamp=datetime.now(timezone.utc) + timedelta(seconds=i),
                    market_id=market
                )
                messages.append(trade_msg)
        
        # Act - Process multi-market messages
        for message in messages:
            await integration_handler.handle_message(message)
        
        # Assert - Multi-market processing
        metrics = integration_handler.get_integration_metrics()
        
        assert metrics["processed_trades"] == 15  # 5 trades per market * 3 markets
        assert metrics["validation_errors"] == 0
        
        # Verify market diversity
        processed_markets = set(trade.market_id for trade in integration_handler.processed_trades)
        assert len(processed_markets) == 3
        assert processed_markets == set(markets)
