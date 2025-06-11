"""
Layer 3 Performance Integration Tests: Layer 2-3 Pipeline Performance Validation

Tests the performance characteristics of the complete Layer 2-3 pipeline:
- WebSocket message processing → Layer 3 processing latency
- Memory efficiency across the Layer 2-3 boundary
- Throughput validation under realistic loads
- Resource utilization monitoring
- Performance degradation detection
"""

import pytest
import asyncio
import time
import psutil
import gc
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock
from typing import List, Dict, Any

from injective_bot.connection import WebSocketMessage, MessageType, MessageHandler
from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.models import OrderbookSnapshot, PriceLevel, TradeExecution
from injective_bot.data import (
    MarketDataAggregator, OrderbookProcessor, DataValidator,
    CircularBuffer, PerformanceMonitor
)
from injective_bot.data.aggregator import TimeFrame


class PerformanceMetricsCollector:
    """Collects detailed performance metrics for Layer 2-3 pipeline"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all metrics"""
        self.latency_measurements = []
        self.memory_measurements = []
        self.throughput_measurements = []
        self.cpu_measurements = []
        self.error_counts = 0
        self.processed_messages = 0
        
        # Performance thresholds (Layer 3 requirements)
        self.max_latency_ms = 50.0
        self.max_memory_mb = 100.0
        self.min_throughput_msg_sec = 100.0
        
    def record_message_latency(self, latency_ms: float):
        """Record message processing latency"""
        self.latency_measurements.append({
            "latency_ms": latency_ms,
            "timestamp": time.perf_counter()
        })
    
    def record_memory_usage(self):
        """Record current memory usage"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        self.memory_measurements.append({
            "memory_mb": memory_mb,
            "timestamp": time.perf_counter()
        })
    
    def record_cpu_usage(self):
        """Record CPU usage"""
        cpu_percent = psutil.cpu_percent(interval=None)
        self.cpu_measurements.append({
            "cpu_percent": cpu_percent,
            "timestamp": time.perf_counter()
        })
    
    def calculate_throughput(self, messages_processed: int, duration_seconds: float):
        """Calculate and record throughput"""
        throughput = messages_processed / duration_seconds
        self.throughput_measurements.append({
            "throughput_msg_sec": throughput,
            "messages": messages_processed,
            "duration": duration_seconds,
            "timestamp": time.perf_counter()
        })
        return throughput
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        if not self.latency_measurements:
            return {"error": "No measurements recorded"}
        
        latencies = [m["latency_ms"] for m in self.latency_measurements]
        
        summary = {
            "latency": {
                "avg_ms": sum(latencies) / len(latencies),
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
                "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0,
                "violations": len([l for l in latencies if l > self.max_latency_ms])
            },
            "memory": {
                "peak_mb": max([m["memory_mb"] for m in self.memory_measurements]) if self.memory_measurements else 0,
                "avg_mb": sum([m["memory_mb"] for m in self.memory_measurements]) / len(self.memory_measurements) if self.memory_measurements else 0
            },
            "throughput": {
                "peak_msg_sec": max([t["throughput_msg_sec"] for t in self.throughput_measurements]) if self.throughput_measurements else 0,
                "avg_msg_sec": sum([t["throughput_msg_sec"] for t in self.throughput_measurements]) / len(self.throughput_measurements) if self.throughput_measurements else 0
            },
            "errors": self.error_counts,
            "processed_messages": self.processed_messages,
            "meets_requirements": self._check_requirements()
        }
        
        return summary
    
    def _check_requirements(self) -> bool:
        """Check if performance meets Layer 3 requirements"""
        if not self.latency_measurements:
            return False
        
        latencies = [m["latency_ms"] for m in self.latency_measurements]
        avg_latency = sum(latencies) / len(latencies)
        
        # Requirements:
        # 1. Average latency < 50ms
        # 2. <5% of messages exceed 50ms
        # 3. Memory usage reasonable
        
        violation_rate = len([l for l in latencies if l > self.max_latency_ms]) / len(latencies)
        
        return (
            avg_latency < self.max_latency_ms and
            violation_rate < 0.05 and
            (not self.memory_measurements or 
             max([m["memory_mb"] for m in self.memory_measurements]) < self.max_memory_mb * 2)  # 2x headroom
        )


class Layer3PerformanceHandler(MessageHandler):
    """Message handler with integrated performance monitoring"""
    
    def __init__(self, metrics_collector: PerformanceMetricsCollector):
        self.metrics = metrics_collector
        self.data_validator = DataValidator()
        self.aggregator = MarketDataAggregator(
            timeframes=[TimeFrame.ONE_MINUTE, TimeFrame.FIVE_MINUTE],
            buffer_size=2000
        )
        self.orderbook_processor = OrderbookProcessor()
        self.performance_monitor = PerformanceMonitor()
        
        # Results
        self.processed_trades = []
        self.processed_orderbooks = []
        self.generated_ohlcv = []

    def get_supported_message_types(self) -> List[MessageType]:
        """Get supported message types for performance monitoring"""
        return [MessageType.TRADES, MessageType.ORDERBOOK, MessageType.MARKET_DATA]
        
    async def handle_message(self, message: WebSocketMessage) -> None:
        """Handle message with performance monitoring"""
        start_time = time.perf_counter()
        
        try:
            # Record CPU usage before processing
            self.metrics.record_cpu_usage()
            
            # Process message through Layer 3 pipeline
            if message.message_type == MessageType.TRADES:
                await self._process_trades(message)
            elif message.message_type == MessageType.ORDERBOOK:
                await self._process_orderbook(message)
            
            self.metrics.processed_messages += 1
            
            # Record memory usage periodically
            if self.metrics.processed_messages % 50 == 0:
                self.metrics.record_memory_usage()
                
        except Exception as e:
            self.metrics.error_counts += 1
            raise
        finally:
            # Record processing latency
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            self.metrics.record_message_latency(latency_ms)
    
    async def _process_trades(self, message: WebSocketMessage):
        """Process trades with performance tracking"""
        trades_data = message.data.get("trades", [])
        
        for trade_data in trades_data:
            trade = TradeExecution(
                trade_id=trade_data.get("trade_id", f"trade_{len(self.processed_trades)}"),
                market_id=trade_data.get("market_id", "UNKNOWN"),
                side=trade_data.get("side", "buy"),
                quantity=Decimal(trade_data.get("quantity", "0")),
                price=Decimal(trade_data.get("price", "0")),
                timestamp=datetime.now(timezone.utc),
                message_id=message.message_id
            )
            
            if self.data_validator.validate_trade(trade):
                self.processed_trades.append(trade)
                
                # Process through aggregator
                start_agg = time.perf_counter()
                ohlcv_result = self.aggregator.process_trade(trade)
                agg_time = (time.perf_counter() - start_agg) * 1000
                
                self.performance_monitor.record_latency("aggregation", agg_time)
                
                if ohlcv_result:
                    self.generated_ohlcv.extend([
                        ohlcv for ohlcv in ohlcv_result.values() if ohlcv is not None
                    ])
    
    async def _process_orderbook(self, message: WebSocketMessage):
        """Process orderbook with performance tracking"""
        orderbook_data = message.data.get("orderbook", {})
        
        if orderbook_data:
            orderbook = OrderbookSnapshot(
                market_id=orderbook_data.get("market_id", "UNKNOWN"),
                sequence=orderbook_data.get("sequence", 1),
                bids=[
                    PriceLevel(
                        price=Decimal(bid["price"]),
                        quantity=Decimal(bid["quantity"])
                    ) for bid in orderbook_data.get("bids", [])
                ],
                asks=[
                    PriceLevel(
                        price=Decimal(ask["price"]),
                        quantity=Decimal(ask["quantity"])
                    ) for ask in orderbook_data.get("asks", [])
                ]
            )
            
            if self.data_validator.validate_orderbook(orderbook):
                self.processed_orderbooks.append(orderbook)
                
                # Process through orderbook processor
                start_ob = time.perf_counter()
                spread_analysis = self.orderbook_processor.calculate_spread(orderbook)
                depth_analysis = self.orderbook_processor.analyze_market_depth(orderbook)
                ob_time = (time.perf_counter() - start_ob) * 1000
                
                self.performance_monitor.record_latency("orderbook_analysis", ob_time)


class TestLayer3PerformanceIntegration:
    """Performance integration tests for Layer 2-3 pipeline"""

    @pytest.fixture
    def metrics_collector(self):
        """Create performance metrics collector"""
        return PerformanceMetricsCollector()

    @pytest.fixture
    def performance_handler(self, metrics_collector):
        """Create performance monitoring handler"""
        return Layer3PerformanceHandler(metrics_collector)

    @pytest.fixture
    def client(self):
        """Create mock WebSocket client"""
        return Mock(spec=InjectiveStreamClient)

    @pytest.mark.asyncio
    async def test_layer3_latency_requirements_integration(self, client, performance_handler, metrics_collector):
        """Test: Layer 3 latency requirements under integration load"""
        # Arrange - 200 messages for statistical significance
        messages = []
        for i in range(200):
            if i % 2 == 0:  # Trade message
                message = WebSocketMessage(
                    message_id=f"latency_trade_{i}",
                    message_type=MessageType.TRADES,
                    data={
                        "trades": [{
                            "trade_id": f"trade_{i}",
                            "market_id": "INJ/USDT",
                            "side": "buy" if i % 4 == 0 else "sell",
                            "quantity": f"{100 + i}",
                            "price": f"{15.50 + (i * 0.001)}"
                        }]
                    },
                    timestamp=datetime.now(timezone.utc)
                )
            else:  # Orderbook message
                message = WebSocketMessage(
                    message_id=f"latency_orderbook_{i}",
                    message_type=MessageType.ORDERBOOK,
                    data={
                        "orderbook": {
                            "market_id": "INJ/USDT",
                            "sequence": i,
                            "bids": [{"price": f"{15.50 + (i * 0.001)}", "quantity": "1000.0"}],
                            "asks": [{"price": f"{15.51 + (i * 0.001)}", "quantity": "1000.0"}]
                        }
                    },
                    timestamp=datetime.now(timezone.utc)
                )
            messages.append(message)

        # Act - Process messages with latency monitoring
        start_time = time.perf_counter()
        for message in messages:
            await performance_handler.handle_message(message)
        end_time = time.perf_counter()

        # Calculate throughput
        duration = end_time - start_time
        throughput = metrics_collector.calculate_throughput(len(messages), duration)

        # Assert - Latency requirements
        summary = metrics_collector.get_performance_summary()
        
        assert summary["meets_requirements"] is True, f"Performance requirements not met: {summary}"
        assert summary["latency"]["avg_ms"] < 50.0, f"Average latency too high: {summary['latency']['avg_ms']:.2f}ms"
        assert summary["latency"]["p95_ms"] < 100.0, f"P95 latency too high: {summary['latency']['p95_ms']:.2f}ms"
        assert summary["latency"]["violations"] < len(messages) * 0.05, f"Too many latency violations: {summary['latency']['violations']}"

        # Throughput requirement
        assert throughput >= 40.0, f"Throughput too low: {throughput:.2f} msg/sec"

    @pytest.mark.asyncio
    async def test_layer3_memory_efficiency_integration(self, client, performance_handler, metrics_collector):
        """Test: Memory efficiency in Layer 2-3 pipeline under sustained load"""
        # Arrange - Extended processing to test memory growth
        batch_size = 100
        num_batches = 5
        
        baseline_memory = None
        memory_growth_rates = []

        # Act - Process multiple batches and monitor memory
        for batch in range(num_batches):
            # Generate batch of messages
            messages = []
            for i in range(batch_size):
                message_id = batch * batch_size + i
                message = WebSocketMessage(
                    message_id=f"memory_test_{message_id}",
                    message_type=MessageType.TRADES if i % 2 == 0 else MessageType.ORDERBOOK,
                    data={
                        "trades" if i % 2 == 0 else "orderbook": 
                        [{
                            "trade_id": f"trade_{message_id}",
                            "market_id": "INJ/USDT",
                            "side": "buy",
                            "quantity": "100.0",
                            "price": "15.50"
                        }] if i % 2 == 0 else {
                            "market_id": "INJ/USDT",
                            "sequence": message_id,
                            "bids": [{"price": "15.50", "quantity": "1000.0"}],
                            "asks": [{"price": "15.51", "quantity": "1000.0"}]
                        }
                    },
                    timestamp=datetime.now(timezone.utc)
                )
                messages.append(message)
            
            # Process batch
            batch_start_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            for message in messages:
                await performance_handler.handle_message(message)
            
            # Force garbage collection and measure memory
            gc.collect()
            batch_end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            if baseline_memory is None:
                baseline_memory = batch_end_memory
            else:
                growth_rate = (batch_end_memory - baseline_memory) / baseline_memory
                memory_growth_rates.append(growth_rate)
            
            metrics_collector.record_memory_usage()

        # Assert - Memory efficiency
        summary = metrics_collector.get_performance_summary()
        
        # Memory should not grow excessively
        if memory_growth_rates:
            avg_growth_rate = sum(memory_growth_rates) / len(memory_growth_rates)
            assert avg_growth_rate < 0.5, f"Memory growth too high: {avg_growth_rate:.2%}"
        
        # Peak memory should be reasonable
        assert summary["memory"]["peak_mb"] < 200.0, f"Peak memory too high: {summary['memory']['peak_mb']:.2f}MB"
        
        # Circular buffers should maintain size limits
        assert len(performance_handler.aggregator._data_buffer) <= 10  # Reasonable number of markets

    @pytest.mark.asyncio
    async def test_layer3_throughput_scalability_integration(self, client, performance_handler, metrics_collector):
        """Test: Throughput scalability with increasing message rates"""
        # Arrange - Test different message rates
        test_rates = [50, 100, 200, 300]  # messages per batch
        throughput_results = []
        
        for rate in test_rates:
            # Reset metrics for this test
            handler_metrics = PerformanceMetricsCollector()
            handler = Layer3PerformanceHandler(handler_metrics)
            
            # Generate messages for this rate
            messages = []
            for i in range(rate):
                message = WebSocketMessage(
                    message_id=f"throughput_{rate}_{i}",
                    message_type=MessageType.TRADES if i % 2 == 0 else MessageType.ORDERBOOK,
                    data={
                        "trades" if i % 2 == 0 else "orderbook":
                        [{
                            "trade_id": f"trade_{i}",
                            "market_id": "INJ/USDT",
                            "side": "buy",
                            "quantity": "100.0",
                            "price": "15.50"
                        }] if i % 2 == 0 else {
                            "market_id": "INJ/USDT",
                            "sequence": i,
                            "bids": [{"price": "15.50", "quantity": "1000.0"}],
                            "asks": [{"price": "15.51", "quantity": "1000.0"}]
                        }
                    },
                    timestamp=datetime.now(timezone.utc)
                )
                messages.append(message)
            
            # Act - Process messages and measure throughput
            start_time = time.perf_counter()
            for message in messages:
                await handler.handle_message(message)
            end_time = time.perf_counter()
            
            duration = end_time - start_time
            throughput = rate / duration
            
            # Get performance summary
            summary = handler_metrics.get_performance_summary()
            
            throughput_results.append({
                "rate": rate,
                "throughput": throughput,
                "avg_latency": summary["latency"]["avg_ms"],
                "meets_requirements": summary["meets_requirements"]
            })

        # Assert - Throughput scalability
        for i, result in enumerate(throughput_results):
            rate = result["rate"]
            throughput = result["throughput"]
            avg_latency = result["avg_latency"]
            
            # Minimum throughput requirement
            min_expected_throughput = min(rate / 2.0, 50.0)  # At least 50 msg/sec or half the input rate
            assert throughput >= min_expected_throughput, \
                f"Throughput too low at rate {rate}: {throughput:.2f} msg/sec"
            
            # Latency should not degrade significantly with higher rates
            assert avg_latency < 100.0, \
                f"Latency too high at rate {rate}: {avg_latency:.2f}ms"
            
            # Performance requirements should be met across all rates
            if rate <= 200:  # Reasonable expectation for Layer 3
                assert result["meets_requirements"] is True, \
                    f"Performance requirements not met at rate {rate}"

    @pytest.mark.asyncio
    async def test_layer3_concurrent_market_performance_integration(self, client, performance_handler, metrics_collector):
        """Test: Performance with concurrent multi-market processing"""
        # Arrange - Multiple markets with interleaved messages
        markets = ["INJ/USDT", "BTC/USDT", "ETH/USDT", "ATOM/USDT", "DOT/USDT"]
        messages_per_market = 40
        total_messages = len(markets) * messages_per_market
        
        # Interleave messages from different markets
        messages = []
        for i in range(messages_per_market):
            for market in markets:
                message_id = f"concurrent_{market}_{i}"
                
                if i % 2 == 0:  # Trade
                    message = WebSocketMessage(
                        message_id=message_id,
                        message_type=MessageType.TRADES,
                        data={
                            "trades": [{
                                "trade_id": f"trade_{market}_{i}",
                                "market_id": market,
                                "side": "buy" if i % 4 == 0 else "sell",
                                "quantity": f"{100 + i}",
                                "price": f"{15.50 + (i * 0.001)}"
                            }]
                        },
                        timestamp=datetime.now(timezone.utc)
                    )
                else:  # Orderbook
                    message = WebSocketMessage(
                        message_id=message_id,
                        message_type=MessageType.ORDERBOOK,
                        data={
                            "orderbook": {
                                "market_id": market,
                                "sequence": i,
                                "bids": [{"price": f"{15.50 + (i * 0.001)}", "quantity": "1000.0"}],
                                "asks": [{"price": f"{15.51 + (i * 0.001)}", "quantity": "1000.0"}]
                            }
                        },
                        timestamp=datetime.now(timezone.utc)
                    )
                messages.append(message)

        # Act - Process concurrent multi-market data
        start_time = time.perf_counter()
        for message in messages:
            await performance_handler.handle_message(message)
        end_time = time.perf_counter()

        duration = end_time - start_time
        throughput = metrics_collector.calculate_throughput(total_messages, duration)

        # Assert - Multi-market performance
        summary = metrics_collector.get_performance_summary()
        
        # Overall performance requirements
        assert summary["meets_requirements"] is True, \
            f"Multi-market performance requirements not met: {summary}"
        
        # Throughput should handle multi-market load
        assert throughput >= 30.0, f"Multi-market throughput too low: {throughput:.2f} msg/sec"
        
        # Latency should remain reasonable
        assert summary["latency"]["avg_ms"] < 75.0, \
            f"Multi-market latency too high: {summary['latency']['avg_ms']:.2f}ms"
        
        # Verify data processing across markets
        processed_markets = set()
        for trade in performance_handler.processed_trades:
            processed_markets.add(trade.market_id)
        
        for orderbook in performance_handler.processed_orderbooks:
            processed_markets.add(orderbook.market_id)
        
        assert len(processed_markets) >= 4, f"Not enough markets processed: {processed_markets}"

    @pytest.mark.asyncio
    async def test_layer3_performance_degradation_detection_integration(self, client, performance_handler, metrics_collector):
        """Test: Detection of performance degradation over time"""
        # Arrange - Process messages in phases to detect degradation
        phase_size = 100
        num_phases = 5
        phase_results = []

        # Act - Process multiple phases and monitor performance trends
        for phase in range(num_phases):
            phase_start_time = time.perf_counter()
            phase_latencies = []
            
            # Process phase messages
            for i in range(phase_size):
                message_id = phase * phase_size + i
                message = WebSocketMessage(
                    message_id=f"degradation_test_{message_id}",
                    message_type=MessageType.TRADES if i % 2 == 0 else MessageType.ORDERBOOK,
                    data={
                        "trades" if i % 2 == 0 else "orderbook":
                        [{
                            "trade_id": f"trade_{message_id}",
                            "market_id": "INJ/USDT",
                            "side": "buy",
                            "quantity": "100.0",
                            "price": "15.50"
                        }] if i % 2 == 0 else {
                            "market_id": "INJ/USDT",
                            "sequence": message_id,
                            "bids": [{"price": "15.50", "quantity": "1000.0"}],
                            "asks": [{"price": "15.51", "quantity": "1000.0"}]
                        }
                    },
                    timestamp=datetime.now(timezone.utc)
                )
                
                msg_start = time.perf_counter()
                await performance_handler.handle_message(message)
                msg_end = time.perf_counter()
                
                phase_latencies.append((msg_end - msg_start) * 1000)
            
            phase_end_time = time.perf_counter()
            
            # Calculate phase metrics
            phase_duration = phase_end_time - phase_start_time
            phase_throughput = phase_size / phase_duration
            phase_avg_latency = sum(phase_latencies) / len(phase_latencies)
            
            phase_results.append({
                "phase": phase,
                "avg_latency_ms": phase_avg_latency,
                "throughput_msg_sec": phase_throughput,
                "latencies": phase_latencies
            })

        # Assert - No significant performance degradation
        first_phase = phase_results[0]
        last_phase = phase_results[-1]
        
        # Latency should not increase significantly
        latency_degradation = (last_phase["avg_latency_ms"] - first_phase["avg_latency_ms"]) / first_phase["avg_latency_ms"]
        assert latency_degradation < 0.5, f"Latency degraded by {latency_degradation:.2%}"
        
        # Throughput should not decrease significantly
        throughput_degradation = (first_phase["throughput_msg_sec"] - last_phase["throughput_msg_sec"]) / first_phase["throughput_msg_sec"]
        assert throughput_degradation < 0.3, f"Throughput degraded by {throughput_degradation:.2%}"
        
        # All phases should meet basic performance requirements
        for phase_result in phase_results:
            assert phase_result["avg_latency_ms"] < 75.0, \
                f"Phase {phase_result['phase']} latency too high: {phase_result['avg_latency_ms']:.2f}ms"
            assert phase_result["throughput_msg_sec"] >= 20.0, \
                f"Phase {phase_result['phase']} throughput too low: {phase_result['throughput_msg_sec']:.2f} msg/sec"
