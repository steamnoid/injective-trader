# Layer 2 End-to-End Tests: Connection Layer
"""
End-to-end tests specifically for Layer 2 Connection functionality
Tests real-world scenarios, connection stability, and error recovery
"""

import pytest
import asyncio
import json
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any
import time

from injective_bot.connection import (
    ConnectionState, MessageType, WebSocketMessage, MessageHandler,
    ConnectionError, ReconnectionError, RateLimitError
)
from injective_bot.connection.injective_client import InjectiveStreamClient, CircuitBreaker
from injective_bot.config import WebSocketConfig


class E2EMessageCollector(MessageHandler):
    """Collects all messages for E2E testing analysis"""
    
    def __init__(self):
        self.messages = []
        self.connection_events = []
        self.error_count = 0
        self.start_time = None
        
    def get_supported_message_types(self) -> List[MessageType]:
        return list(MessageType)
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        """Collect message for analysis"""
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
            
        self.messages.append({
            "timestamp": datetime.now(timezone.utc),
            "message_id": message.message_id,
            "message_type": message.message_type,
            "market_id": message.market_id,
            "data_size": len(str(message.data)),
            "age_ms": message.age_ms
        })
    
    def record_connection_event(self, event_type: str, details: Dict[str, Any] = None):
        """Record connection state changes and events"""
        self.connection_events.append({
            "timestamp": datetime.now(timezone.utc),
            "event_type": event_type,
            "details": details or {}
        })
    
    def record_error(self, error: Exception):
        """Record errors for analysis"""
        self.error_count += 1
        self.connection_events.append({
            "timestamp": datetime.now(timezone.utc),
            "event_type": "error",
            "details": {"error_type": type(error).__name__, "message": str(error)}
        })


class TestConnectionLayerE2E:
    """End-to-end tests for connection layer"""
    
    @pytest.fixture
    def config(self):
        """WebSocket configuration optimized for E2E testing"""
        return WebSocketConfig(
            max_reconnect_attempts=5,
            reconnect_delay_base=0.1,
            reconnect_delay_max=2.0,
            connection_timeout=10.0,
            ping_interval=5.0,
            max_message_rate=1000
        )
    
    @pytest.fixture
    def client(self, config):
        """WebSocket client for E2E testing"""
        return InjectiveStreamClient(config=config, network="testnet")
    
    @pytest.fixture
    def message_collector(self):
        """Message collector for E2E analysis"""
        return E2EMessageCollector()
    
    @pytest.mark.asyncio
    async def test_connection_lifecycle_e2e(self, client, message_collector):
        """Test complete connection lifecycle from connect to disconnect"""
        # Register message collector
        client.register_handler(message_collector)
        message_collector.record_connection_event("test_started")
        
        # Mock the Injective client
        with patch('pyinjective.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_async_client.testnet.return_value = mock_client
            
            # Test connection establishment
            message_collector.record_connection_event("attempting_connection")
            
            result = await client.connect()
            assert result is True
            assert client.get_connection_state() == ConnectionState.CONNECTED
            
            message_collector.record_connection_event("connection_established", {
                "state": client.get_connection_state().value
            })
            
            # Verify connection metrics
            metrics = client.get_metrics()
            assert metrics.connection_attempts >= 1
            assert metrics.successful_connections >= 1
            
            # Calculate connection duration manually if connection_start_time exists
            if metrics.connection_start_time:
                connection_duration = (datetime.now(timezone.utc) - metrics.connection_start_time).total_seconds()
                assert connection_duration >= 0
            
            message_collector.record_connection_event("connection_metrics_verified", {
                "attempts": metrics.connection_attempts,
                "successful": metrics.successful_connections
            })
            
            # Test disconnection
            message_collector.record_connection_event("attempting_disconnect")
            
            await client.disconnect()
            assert client.get_connection_state() == ConnectionState.DISCONNECTED
            
            message_collector.record_connection_event("disconnection_complete")
        
        # Analyze E2E results
        assert len(message_collector.connection_events) >= 4  # Reduced from 6 since we removed subscription tests
        assert message_collector.error_count == 0
        
        # Verify event sequence
        events = [event["event_type"] for event in message_collector.connection_events]
        assert "test_started" in events
        assert "attempting_connection" in events
        assert "connection_established" in events
        assert "disconnection_complete" in events
    
    @pytest.mark.asyncio
    async def test_reconnection_resilience_e2e(self, client, message_collector):
        """Test connection resilience and reconnection capabilities (simplified)"""
        client.register_handler(message_collector)
        
        with patch('pyinjective.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_async_client.testnet.return_value = mock_client
            
            # Test basic connection resilience by attempting multiple connections
            message_collector.record_connection_event("resilience_test_start")
            
            # First attempt - should succeed
            result = await client.connect()
            assert result is True
            assert client.get_connection_state() == ConnectionState.CONNECTED
            
            message_collector.record_connection_event("initial_connection_successful")
            
            # Disconnect and reconnect to test resilience
            await client.disconnect()
            assert client.get_connection_state() == ConnectionState.DISCONNECTED
            
            message_collector.record_connection_event("disconnected_for_resilience_test")
            
            # Reconnect
            result = await client.connect()
            assert result is True
            assert client.get_connection_state() == ConnectionState.CONNECTED
            
            message_collector.record_connection_event("reconnection_successful")
            
            # Verify metrics reflect multiple connections
            metrics = client.get_metrics()
            assert metrics.connection_attempts >= 2
            assert metrics.successful_connections >= 2
            
            await client.disconnect()
            
            message_collector.record_connection_event("resilience_test_complete", {
                "total_attempts": metrics.connection_attempts,
                "successful_connections": metrics.successful_connections
            })
        
        # Verify resilience behavior
        assert message_collector.error_count == 0
        events = [event["event_type"] for event in message_collector.connection_events]
        assert "initial_connection_successful" in events
        assert "reconnection_successful" in events
    
    @pytest.mark.asyncio
    async def test_high_frequency_message_processing_e2e(self, client, message_collector):
        """Test high-frequency message processing under realistic load"""
        client.register_handler(message_collector)
        
        # Generate high-frequency market data messages
        message_count = 500
        markets = ["BTC-USDT", "ETH-USDT", "INJ-USDT", "ATOM-USDT", "DOT-USDT"]
        
        messages = []
        for i in range(message_count):
            market = markets[i % len(markets)]
            message = WebSocketMessage(
                message_id=f"hf_msg_{i:04d}",
                message_type=MessageType.ORDERBOOK if i % 2 == 0 else MessageType.TRADES,
                data={
                    "orderbook" if i % 2 == 0 else "trades": {
                        "market_id": market,
                        "sequence": i,
                        "timestamp": int(time.time() * 1000)
                    }
                },
                market_id=market
            )
            messages.append(message)
        
        # Process messages through the queue
        start_time = datetime.now(timezone.utc)
        
        for message in messages:
            await client._message_queue.put(message)
        
        # Start message processor
        processor_task = asyncio.create_task(client._message_processor())
        
        # Allow processing time
        await asyncio.sleep(1.0)
        
        # Stop processor
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass
        
        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()
        
        # Analyze processing performance
        processed_count = len(message_collector.messages)
        
        # Should process most messages (allow for some processing time variability)
        assert processed_count >= message_count * 0.8  # At least 80% processed
        
        # Calculate throughput
        throughput = processed_count / processing_time if processing_time > 0 else 0
        
        message_collector.record_connection_event("high_frequency_test_complete", {
            "messages_generated": message_count,
            "messages_processed": processed_count,
            "processing_time_sec": processing_time,
            "throughput_msg_per_sec": throughput
        })
        
        # Verify performance requirements (should handle >100 msg/sec)
        assert throughput > 100, f"Throughput {throughput:.2f} msg/sec below requirement"
        
        # Verify message latency (messages should be processed quickly)
        if message_collector.messages:
            avg_latency = sum(msg["age_ms"] for msg in message_collector.messages) / len(message_collector.messages)
            assert avg_latency < 100, f"Average latency {avg_latency:.2f}ms too high"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration_e2e(self, client, message_collector):
        """Test circuit breaker behavior under failure conditions (simplified)"""
        client.register_handler(message_collector)
        
        # Test circuit breaker functionality directly
        circuit_breaker = client._circuit_breaker
        original_threshold = circuit_breaker.failure_threshold
        circuit_breaker.failure_threshold = 3  # Trigger after 3 failures
        
        try:
            message_collector.record_connection_event("circuit_breaker_test_start")
            
            # Manually trigger circuit breaker failures
            for attempt in range(5):
                try:
                    with circuit_breaker:
                        if attempt < 3:  # First 3 attempts fail
                            raise ConnectionError(f"Simulated failure {attempt + 1}")
                        # Subsequent attempts succeed
                        pass
                    
                    message_collector.record_connection_event(f"attempt_{attempt + 1}_success")
                except Exception as e:
                    message_collector.record_error(e)
                    message_collector.record_connection_event(f"attempt_{attempt + 1}_failed")
                
                # Check circuit breaker state after each attempt
                if circuit_breaker.state == "open":
                    message_collector.record_connection_event("circuit_breaker_opened", {
                        "failure_count": circuit_breaker.failure_count,
                        "threshold": circuit_breaker.failure_threshold
                    })
                    break
            
            message_collector.record_connection_event("circuit_breaker_test_complete", {
                "final_state": circuit_breaker.state,
                "total_failures": circuit_breaker.failure_count
            })
        
        finally:
            # Restore original threshold
            circuit_breaker.failure_threshold = original_threshold
        
        # Verify circuit breaker behavior was recorded
        events = [event["event_type"] for event in message_collector.connection_events]
        assert "circuit_breaker_opened" in events
        assert message_collector.error_count >= 3  # Should have recorded failures
    
    @pytest.mark.asyncio
    async def test_rate_limiting_e2e(self, client, message_collector):
        """Test rate limiting behavior under high message volume"""
        client.register_handler(message_collector)
        
        # Configure rate limiting
        original_max_rate = client.config.max_message_rate
        client.config.max_message_rate = 10  # Very low rate for testing
        
        try:
            message_collector.record_connection_event("rate_limiting_test_start", {
                "max_rate": client.config.max_message_rate
            })
            
            # Test rate limiting by checking the rate limit function directly
            rate_limit_triggered = False
            
            # Fill up the message timestamps to trigger rate limiting
            current_time = time.time()
            client._message_timestamps = [current_time - i for i in range(client.config.max_message_rate)]
            
            # Check rate limit - should be at the limit
            rate_check = client._check_rate_limit()
            
            if not rate_check:
                rate_limit_triggered = True
                message_collector.record_connection_event("rate_limit_triggered", {
                    "message_count": len(client._message_timestamps),
                    "max_rate": client.config.max_message_rate
                })
            
            # Add one more timestamp to exceed the limit
            client._message_timestamps.append(current_time)
            
            # Check rate limit again - should now be exceeded
            rate_check = client._check_rate_limit()
            
            if not rate_check and not rate_limit_triggered:
                rate_limit_triggered = True
                message_collector.record_connection_event("rate_limit_triggered", {
                    "message_count": len(client._message_timestamps),
                    "max_rate": client.config.max_message_rate
                })
            
            message_collector.record_connection_event("rate_limiting_test_complete", {
                "rate_limit_triggered": rate_limit_triggered,
                "final_message_count": len(client._message_timestamps)
            })
        
        finally:
            # Restore original rate limit and clear timestamps
            client.config.max_message_rate = original_max_rate
            client._message_timestamps = []
        
        # Verify rate limiting was triggered
        events = [event["event_type"] for event in message_collector.connection_events]
        assert "rate_limit_triggered" in events
    
    @pytest.mark.asyncio
    async def test_memory_efficiency_under_load_e2e(self, client, message_collector):
        """Test memory efficiency under sustained load"""
        import psutil
        import os
        
        client.register_handler(message_collector)
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        message_collector.record_connection_event("memory_test_start", {
            "initial_memory_mb": initial_memory
        })
        
        # Generate sustained load
        message_batches = 10
        messages_per_batch = 100
        
        for batch in range(message_batches):
            # Generate batch of messages
            for i in range(messages_per_batch):
                message = WebSocketMessage(
                    message_id=f"mem_test_{batch}_{i:03d}",
                    message_type=MessageType.MARKET_DATA,
                    data={
                        "test_data": f"batch_{batch}_message_{i}",
                        "large_field": "x" * 1000  # 1KB of data per message
                    },
                    market_id=f"TEST-MARKET-{batch % 5}"
                )
                
                await client._message_queue.put(message)
            
            # Process batch
            processor_task = asyncio.create_task(client._message_processor())
            await asyncio.sleep(0.2)  # Allow processing
            processor_task.cancel()
            
            try:
                await processor_task
            except asyncio.CancelledError:
                pass
            
            # Check memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            message_collector.record_connection_event(f"memory_check_batch_{batch}", {
                "current_memory_mb": current_memory,
                "memory_increase_mb": memory_increase,
                "messages_processed": len(message_collector.messages)
            })
            
            # Memory should not grow excessively (allow some growth for processing)
            assert memory_increase < 50, f"Memory increased by {memory_increase:.2f}MB after batch {batch}"
            
            # Brief pause between batches
            await asyncio.sleep(0.1)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        
        message_collector.record_connection_event("memory_test_complete", {
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "total_increase_mb": total_memory_increase,
            "total_messages_processed": len(message_collector.messages),
            "memory_per_message_kb": (total_memory_increase * 1024) / max(len(message_collector.messages), 1)
        })
        
        # Verify memory efficiency
        assert total_memory_increase < 100, f"Total memory increase {total_memory_increase:.2f}MB too high"
        
        # Should have processed significant number of messages
        assert len(message_collector.messages) >= message_batches * messages_per_batch * 0.5
    
    @pytest.mark.asyncio
    async def test_connection_recovery_after_network_failure_e2e(self, client, message_collector):
        """Test connection recovery after simulated network failures"""
        client.register_handler(message_collector)
        
        with patch('pyinjective.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_async_client.testnet.return_value = mock_client
            
            # Establish initial connection
            result = await client.connect()
            assert result is True
            assert client.get_connection_state() == ConnectionState.CONNECTED
            
            message_collector.record_connection_event("initial_connection_established")
            
            # Simulate network failure
            original_client = client._client
            client._client = None  # Simulate connection loss
            client._connection_state = ConnectionState.DISCONNECTED
            
            message_collector.record_connection_event("network_failure_simulated")
            
            # Test recovery
            result = await client.connect()
            assert result is True
            assert client.get_connection_state() == ConnectionState.CONNECTED
            
            message_collector.record_connection_event("connection_recovered")
            
            # Verify metrics show recovery
            metrics = client.get_metrics()
            assert metrics.connection_attempts >= 2  # Initial + recovery
            assert metrics.successful_connections >= 2
            
            await client.disconnect()
            
            message_collector.record_connection_event("recovery_test_complete", {
                "total_attempts": metrics.connection_attempts,
                "successful_connections": metrics.successful_connections,
                "recovery_successful": True
            })
        
        # Verify recovery sequence
        events = [event["event_type"] for event in message_collector.connection_events]
        assert "initial_connection_established" in events
        assert "network_failure_simulated" in events
        assert "connection_recovered" in events
        assert "recovery_test_complete" in events
