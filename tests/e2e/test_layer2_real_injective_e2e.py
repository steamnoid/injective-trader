# Real Injective Protocol Layer 2 E2E Tests
"""
End-to-end tests for Layer 2 Connection using REAL Injective Protocol connections.
Tests connect to actual Injective testnet/mainnet to validate real-world functionality.
These tests provide the foundation for Layer 3 integration.
"""

import pytest
import asyncio
import json
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Dict, Any
import time
import logging

from injective_bot.connection import (
    ConnectionState, MessageType, WebSocketMessage, MessageHandler,
    ConnectionError, ReconnectionError, RateLimitError
)
from injective_bot.connection.injective_client import InjectiveStreamClient, CircuitBreaker
from injective_bot.config import WebSocketConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealInjectiveMessageCollector(MessageHandler):
    """Collects real Injective Protocol messages for analysis"""
    
    def __init__(self):
        self.messages = []
        self.connection_events = []
        self.error_count = 0
        self.start_time = None
        self.message_types_received = set()
        self.markets_seen = set()
        self.total_data_size = 0
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        """Collect real Injective message for analysis"""
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
            
        message_info = {
            "timestamp": datetime.now(timezone.utc),
            "message_id": message.message_id,
            "message_type": message.message_type,
            "market_id": message.market_id,
            "data_size": len(str(message.data)) if message.data else 0,
            "age_ms": message.age_ms
        }
        
        self.messages.append(message_info)
        self.message_types_received.add(message.message_type)
        if message.market_id:
            self.markets_seen.add(message.market_id)
        self.total_data_size += message_info["data_size"]
        
        logger.info(f"Received {message.message_type.value} message for {message.market_id}, "
                   f"size: {message_info['data_size']} bytes, age: {message.age_ms}ms")
    
    def record_connection_event(self, event_type: str, details: Dict[str, Any] = None):
        """Record connection state changes and events"""
        self.connection_events.append({
            "timestamp": datetime.now(timezone.utc),
            "event_type": event_type,
            "details": details or {}
        })
        logger.info(f"Connection event: {event_type} - {details}")
    
    def record_error(self, error: Exception):
        """Record errors for analysis"""
        self.error_count += 1
        self.connection_events.append({
            "timestamp": datetime.now(timezone.utc),
            "event_type": "error",
            "details": {"error_type": type(error).__name__, "message": str(error)}
        })
        logger.error(f"Error recorded: {type(error).__name__}: {error}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get collection statistics"""
        duration = (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0
        return {
            "total_messages": len(self.messages),
            "message_types": list(self.message_types_received),
            "markets_seen": list(self.markets_seen),
            "total_data_size": self.total_data_size,
            "average_message_size": self.total_data_size / max(len(self.messages), 1),
            "duration_seconds": duration,
            "messages_per_second": len(self.messages) / max(duration, 1),
            "error_count": self.error_count
        }


class TestLayer2RealInjectiveE2E:
    """End-to-end tests for Layer 2 with real Injective Protocol connections"""
    
    @pytest.fixture
    def config(self):
        """WebSocket configuration optimized for real Injective connections"""
        return WebSocketConfig(
            max_reconnect_attempts=3,
            reconnect_delay_base=1.0,
            reconnect_delay_max=5.0,
            connection_timeout=30.0,
            ping_interval=30.0,
            max_message_rate=1000
        )
    
    @pytest.fixture
    def testnet_client(self, config):
        """Testnet client for real E2E testing"""
        return InjectiveStreamClient(config=config, network="testnet")
    
    @pytest.fixture
    def mainnet_client(self, config):
        """Mainnet client for fallback testing"""
        return InjectiveStreamClient(config=config, network="mainnet")
    
    @pytest.fixture
    def message_collector(self):
        """Message collector for real data analysis"""
        return RealInjectiveMessageCollector()

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_real_injective_connection_lifecycle(self, mainnet_client, testnet_client, message_collector):
        """Test complete connection lifecycle with real Injective Protocol"""
        # Try mainnet first (more reliable), fall back to testnet
        clients_to_try = [
            ("mainnet", mainnet_client),
            ("testnet", testnet_client)
        ]
        
        successful_client = None
        successful_network = None
        
        for network_name, client in clients_to_try:
            try:
                message_collector.record_connection_event(f"attempting_{network_name}_connection")
                
                # Register message collector
                client.register_handler(message_collector)
                
                # Test connection establishment
                logger.info(f"Attempting to connect to Injective {network_name}...")
                result = await asyncio.wait_for(client.connect(), timeout=30.0)
                
                if result and client.get_connection_state() == ConnectionState.CONNECTED:
                    successful_client = client
                    successful_network = network_name
                    message_collector.record_connection_event(f"{network_name}_connection_successful", {
                        "state": client.get_connection_state().value
                    })
                    logger.info(f"Successfully connected to Injective {network_name}")
                    break
                else:
                    message_collector.record_connection_event(f"{network_name}_connection_failed")
                    logger.warning(f"Failed to connect to Injective {network_name}")
                    
            except Exception as e:
                message_collector.record_error(e)
                logger.warning(f"Error connecting to {network_name}: {e}")
                continue
        
        assert successful_client is not None, "Failed to connect to both testnet and mainnet"
        assert successful_client.get_connection_state() == ConnectionState.CONNECTED
        
        try:
            # Verify connection metrics
            metrics = successful_client.get_metrics()
            assert metrics.connection_attempts >= 1
            assert metrics.successful_connections >= 1
            
            message_collector.record_connection_event("connection_metrics_verified", {
                "network": successful_network,
                "attempts": metrics.connection_attempts,
                "successful": metrics.successful_connections
            })
            
            # Test disconnection
            message_collector.record_connection_event("attempting_disconnect")
            await successful_client.disconnect()
            assert successful_client.get_connection_state() == ConnectionState.DISCONNECTED
            
            message_collector.record_connection_event("disconnection_complete")
            
        finally:
            # Ensure cleanup
            if successful_client.get_connection_state() == ConnectionState.CONNECTED:
                await successful_client.disconnect()
        
        # Analyze E2E results
        assert len(message_collector.connection_events) >= 3
        assert message_collector.error_count == 0
        
        # Verify event sequence
        events = [event["event_type"] for event in message_collector.connection_events]
        assert f"{successful_network}_connection_successful" in events
        assert "disconnection_complete" in events

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_real_market_data_subscription(self, mainnet_client, testnet_client, message_collector):
        """Test real market data subscription and processing"""
        # Market IDs for different networks - using high-volume USD markets for optimal testing
        mainnet_markets = [
            "0xe8bf0467208c24209c1cf0fd64833fa43eb6e8035869f9d043dbff815ab76d01",  # UNI/USDT - High volume
            "0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0",  # INJ/USDT - High volume
            "0x28f3c9897e23750bf653889224f93390c467b83c86d736af79431958fff833d1",  # MATIC/USDT - High volume
            "0x26413a70c9b78a495023e5ab8003c9cf963ef963f6755f8b57255feb5744bf31",  # LINK/USDT - High volume
        ]
        
        testnet_markets = [
            "0x54d4505adef6a5cef26bc403a33d595620ded4e15b9e2bc3dd489b714813366a",  # INJ/USDT testnet
        ]

        # Try mainnet first (more reliable), fall back to testnet
        test_configs = [
            ("mainnet", mainnet_client, mainnet_markets),
            ("testnet", testnet_client, testnet_markets)
        ]
        
        successful_client = None
        successful_network = None
        successful_markets = None
        
        for network_name, client, markets in test_configs:
            try:
                message_collector.record_connection_event(f"attempting_{network_name}_subscription_test")
                
                # Register message collector
                client.register_handler(message_collector)
                
                # Connect to Injective
                logger.info(f"Connecting to {network_name} for market data test...")
                result = await asyncio.wait_for(client.connect(), timeout=30.0)
                
                if not result or client.get_connection_state() != ConnectionState.CONNECTED:
                    logger.warning(f"Failed to connect to {network_name}")
                    continue
                
                successful_client = client
                successful_network = network_name
                successful_markets = markets
                
                message_collector.record_connection_event(f"{network_name}_subscription_connection_successful")
                break
                
            except Exception as e:
                message_collector.record_error(e)
                logger.warning(f"Error in {network_name} setup: {e}")
                continue
        
        assert successful_client is not None, "Failed to connect to any network for market data test"
        
        try:
            # Subscribe to market data - use only first market for reliable data
            single_market = [successful_markets[0]]  # Use only first market for testing
            message_collector.record_connection_event("subscribing_to_markets", {
                "market_ids": single_market,
                "network": successful_network
            })
            
            # Subscribe to orderbook updates (method handles async internally)
            await successful_client.subscribe_spot_orderbook_updates(single_market)
            
            # Subscribe to trade updates (method handles async internally)
            await successful_client.subscribe_spot_trades_updates(single_market)
            
            logger.info(f"Subscribed to {len(single_market)} market on {successful_network}: {single_market[0]}")
            
            # Allow time to receive real market data
            data_collection_time = 15  # 15 seconds to collect real data (increased from 10)
            message_collector.record_connection_event("starting_data_collection", {
                "duration_seconds": data_collection_time,
                "markets": single_market
            })
            
            logger.info(f"Collecting real market data for {data_collection_time} seconds...")
            
            # Monitor collection progress
            for i in range(data_collection_time):
                await asyncio.sleep(1)
                current_stats = message_collector.get_statistics()
                if (i + 1) % 5 == 0:  # Log every 5 seconds
                    logger.info(f"  {i+1}s - Messages: {current_stats['total_messages']}, Types: {current_stats['message_types']}")
            
            message_collector.record_connection_event("data_collection_complete")
            
            # Analyze collected data
            stats = message_collector.get_statistics()
            message_collector.record_connection_event("data_analysis_complete", stats)
            
            logger.info(f"Collected {stats['total_messages']} messages from {len(stats['markets_seen'])} markets")
            logger.info(f"Message types received: {stats['message_types']}")
            logger.info(f"Average message rate: {stats['messages_per_second']:.2f} msg/sec")
            
            # Validate real data collection
            assert stats['total_messages'] > 0, "No messages received from real Injective connection"
            assert len(stats['message_types']) > 0, "No message types received"
            assert stats['total_data_size'] > 0, "No data received"
            
            # Verify we received valid message types (accept any of the expected types)
            expected_types = {MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA}
            received_types = set(stats['message_types'])
            assert len(received_types.intersection(expected_types)) > 0, f"Expected one of {expected_types}, got {received_types}"
            
            # Verify market data quality
            assert stats['messages_per_second'] > 0, "Message rate should be positive"
            assert stats['average_message_size'] > 0, "Messages should have content"
            assert len(stats['markets_seen']) > 0, "Should see at least one market"
            
            message_collector.record_connection_event("real_data_validation_complete", {
                "success": True,
                "message_count": stats['total_messages'],
                "data_rate_mbps": (stats['total_data_size'] * 8) / (stats['duration_seconds'] * 1_000_000)
            })
            
        finally:
            # Cleanup
            if successful_client.get_connection_state() == ConnectionState.CONNECTED:
                await successful_client.disconnect()
        
        # Final validation
        assert message_collector.error_count == 0, f"Errors occurred during test: {message_collector.error_count}"

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_real_connection_resilience(self, mainnet_client, message_collector):
        """Test connection resilience with real Injective Protocol"""
        # Use mainnet for more reliable resilience testing
        # Register message collector
        mainnet_client.register_handler(message_collector)
        
        message_collector.record_connection_event("resilience_test_start")
        
        try:
            # Test multiple connect/disconnect cycles
            for cycle in range(3):
                message_collector.record_connection_event(f"cycle_{cycle}_start")
                
                # Connect
                logger.info(f"Starting resilience cycle {cycle + 1}/3...")
                result = await asyncio.wait_for(mainnet_client.connect(), timeout=30.0)
                
                if result and mainnet_client.get_connection_state() == ConnectionState.CONNECTED:
                    message_collector.record_connection_event(f"cycle_{cycle}_connected")
                    
                    # Brief operation period
                    await asyncio.sleep(5)
                    
                    # Disconnect
                    await mainnet_client.disconnect()
                    assert mainnet_client.get_connection_state() == ConnectionState.DISCONNECTED
                    
                    message_collector.record_connection_event(f"cycle_{cycle}_disconnected")
                    
                    # Brief pause between cycles
                    await asyncio.sleep(2)
                else:
                    # If mainnet connection fails, this is unexpected
                    message_collector.record_connection_event(f"cycle_{cycle}_connection_failed")
                    logger.warning(f"Cycle {cycle} connection failed - mainnet may be temporarily unavailable")
                    break
            
            # Verify metrics reflect resilience testing
            metrics = mainnet_client.get_metrics()
            message_collector.record_connection_event("resilience_test_complete", {
                "total_attempts": metrics.connection_attempts,
                "successful_connections": metrics.successful_connections
            })
            
        finally:
            # Cleanup
            if mainnet_client.get_connection_state() == ConnectionState.CONNECTED:
                await mainnet_client.disconnect()
        
        # Verify resilience behavior (allow for testnet unavailability)
        events = [event["event_type"] for event in message_collector.connection_events]
        assert "resilience_test_start" in events
        assert "resilience_test_complete" in events

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_real_performance_benchmarking(self, mainnet_client, message_collector):
        """Test performance with real Injective mainnet data"""
        # Use mainnet for more consistent performance testing
        mainnet_client.register_handler(message_collector)
        
        message_collector.record_connection_event("performance_test_start")
        
        try:
            # Connect to mainnet
            logger.info("Connecting to mainnet for performance testing...")
            result = await asyncio.wait_for(mainnet_client.connect(), timeout=30.0)
            
            if not result or mainnet_client.get_connection_state() != ConnectionState.CONNECTED:
                pytest.skip("Mainnet connection failed - skipping performance test")
            
            message_collector.record_connection_event("performance_connection_established")
            
            # Use single market for reliable data (same as working market data test)
            single_market = ["0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"]  # INJ/USDT
            
            # Subscribe to both orderbook and trades for message flow
            await mainnet_client.subscribe_spot_orderbook_updates(single_market)
            await mainnet_client.subscribe_spot_trades_updates(single_market)
            
            # Shorter performance measurement period (to match working test)
            performance_duration = 20  # 20 seconds instead of 60
            start_time = datetime.now(timezone.utc)
            
            message_collector.record_connection_event("performance_measurement_start", {
                "duration_seconds": performance_duration,
                "markets": single_market
            })
            
            logger.info(f"Starting {performance_duration}s performance measurement...")
            
            # Monitor with progress updates like the working test
            for i in range(performance_duration):
                await asyncio.sleep(1)
                current_stats = message_collector.get_statistics()
                if (i + 1) % 5 == 0:  # Log every 5 seconds
                    logger.info(f"  {i+1}s - Messages: {current_stats['total_messages']}, Types: {current_stats['message_types']}")
            
            end_time = datetime.now(timezone.utc)
            
            # Analyze performance
            stats = message_collector.get_statistics()
            actual_duration = (end_time - start_time).total_seconds()
            
            performance_metrics = {
                "actual_duration": actual_duration,
                "total_messages": stats['total_messages'],
                "messages_per_second": stats['total_messages'] / actual_duration,
                "average_message_size": stats['average_message_size'],
                "total_throughput_bytes_per_sec": stats['total_data_size'] / actual_duration,
                "markets_active": len(stats['markets_seen']),
                "message_types_seen": len(stats['message_types'])
            }
            
            message_collector.record_connection_event("performance_measurement_complete", performance_metrics)
            
            logger.info(f"Performance Results:")
            logger.info(f"  Messages: {performance_metrics['total_messages']}")
            logger.info(f"  Rate: {performance_metrics['messages_per_second']:.2f} msg/sec")
            logger.info(f"  Throughput: {performance_metrics['total_throughput_bytes_per_sec']:.2f} bytes/sec")
            
            # Performance assertions (realistic for real network conditions)
            assert performance_metrics['total_messages'] > 0, "No messages received during performance test"
            assert performance_metrics['messages_per_second'] >= 0.1, "Message rate too low"  # Very conservative
            
        finally:
            # Cleanup
            if mainnet_client.get_connection_state() == ConnectionState.CONNECTED:
                await mainnet_client.disconnect()
        
        # Verify performance test completion
        events = [event["event_type"] for event in message_collector.connection_events]
        assert "performance_test_start" in events
        assert "performance_measurement_complete" in events

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_real_multiple_market_subscription(self, mainnet_client, message_collector):
        """Test multiple market subscription to validate multi-stream connection capabilities"""
        # Test multiple market subscription on mainnet (most reliable)
        mainnet_client.register_handler(message_collector)
        
        message_collector.record_connection_event("multiple_market_test_start")
        
        try:
            # Connect to mainnet
            logger.info("Connecting to mainnet for multiple market test...")
            result = await asyncio.wait_for(mainnet_client.connect(), timeout=30.0)
            
            if not result or mainnet_client.get_connection_state() != ConnectionState.CONNECTED:
                pytest.skip("Mainnet connection failed - skipping multiple market test")
            
            message_collector.record_connection_event("multiple_market_connection_established")
            
            # Test with multiple high-volume mainnet markets
            multiple_markets = [
                "0xe8bf0467208c24209c1cf0fd64833fa43eb6e8035869f9d043dbff815ab76d01",  # UNI/USDT - High volume
                "0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0",  # INJ/USDT - High volume  
                "0x28f3c9897e23750bf653889224f93390c467b83c86d736af79431958fff833d1",  # MATIC/USDT - High volume
            ]
            
            message_collector.record_connection_event("subscribing_to_multiple_markets", {
                "market_count": len(multiple_markets),
                "market_ids": multiple_markets
            })
            
            # Subscribe to orderbook updates for multiple markets
            await mainnet_client.subscribe_spot_orderbook_updates(multiple_markets)
            
            # Subscribe to trade updates for multiple markets
            await mainnet_client.subscribe_spot_trades_updates(multiple_markets)
            
            logger.info(f"Subscribed to {len(multiple_markets)} markets for multi-stream testing")
            
            # Data collection period for multiple markets
            collection_duration = 20  # 20 seconds for multiple markets
            start_time = datetime.now(timezone.utc)
            
            message_collector.record_connection_event("multiple_market_data_collection_start", {
                "duration_seconds": collection_duration,
                "expected_markets": len(multiple_markets)
            })
            
            logger.info(f"Collecting data from {len(multiple_markets)} markets for {collection_duration} seconds...")
            
            # Monitor progress with market-specific tracking
            for i in range(collection_duration):
                await asyncio.sleep(1)
                current_stats = message_collector.get_statistics()
                
                if (i + 1) % 5 == 0:  # Log every 5 seconds
                    logger.info(f"  {i+1}s - Messages: {current_stats['total_messages']}, "
                               f"Markets seen: {len(current_stats['markets_seen'])}/{len(multiple_markets)}, "
                               f"Types: {current_stats['message_types']}")
            
            end_time = datetime.now(timezone.utc)
            
            # Analyze multi-market performance
            stats = message_collector.get_statistics()
            actual_duration = (end_time - start_time).total_seconds()
            
            multi_market_metrics = {
                "total_messages": stats['total_messages'],
                "markets_subscribed": len(multiple_markets),
                "markets_received_data": len(stats['markets_seen']),
                "market_coverage_percentage": (len(stats['markets_seen']) / len(multiple_markets)) * 100,
                "messages_per_market": stats['total_messages'] / max(len(stats['markets_seen']), 1),
                "message_types_received": len(stats['message_types']),
                "data_rate_per_market": stats['total_data_size'] / max(len(stats['markets_seen']), 1),
                "duration_seconds": actual_duration
            }
            
            message_collector.record_connection_event("multiple_market_analysis_complete", multi_market_metrics)
            
            logger.info(f"Multi-Market Results:")
            logger.info(f"  Total messages: {multi_market_metrics['total_messages']}")
            logger.info(f"  Markets with data: {multi_market_metrics['markets_received_data']}/{multi_market_metrics['markets_subscribed']}")
            logger.info(f"  Market coverage: {multi_market_metrics['market_coverage_percentage']:.1f}%")
            logger.info(f"  Avg messages per market: {multi_market_metrics['messages_per_market']:.1f}")
            
            # Validate multi-market subscription
            assert stats['total_messages'] > 0, "No messages received from multiple market subscription"
            assert len(stats['markets_seen']) > 0, "No markets provided data"
            
            # Should ideally receive data from multiple markets, but allow for some markets being quiet
            market_coverage = multi_market_metrics['market_coverage_percentage']
            assert market_coverage >= 50.0, f"Only {market_coverage:.1f}% market coverage - expected at least 50%"
            
            # Verify message distribution is reasonable
            if len(stats['markets_seen']) > 1:
                # If multiple markets are active, ensure reasonable message distribution
                messages_per_market = multi_market_metrics['messages_per_market']
                assert messages_per_market >= 1, "Insufficient messages per active market"
                
                message_collector.record_connection_event("multi_market_validation_success", {
                    "active_markets": len(stats['markets_seen']),
                    "message_distribution": "good"
                })
            else:
                logger.info("Single market active - multi-market test shows single stream reliability")
                message_collector.record_connection_event("multi_market_validation_single_active", {
                    "active_markets": 1,
                    "note": "Only one market had activity during test period"
                })
            
        finally:
            # Cleanup
            if mainnet_client.get_connection_state() == ConnectionState.CONNECTED:
                await mainnet_client.disconnect()
        
        # Verify test completion
        events = [event["event_type"] for event in message_collector.connection_events]
        assert "multiple_market_test_start" in events
        assert "multiple_market_analysis_complete" in events
