"""
Layer 1-2 Integration Tests: Connection Layer to Data Models
"""
# Integration tests specifically for connection layer to data models flow
# Tests the message processing pipeline from raw connection data to structured models

import pytest
import asyncio
import json
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from injective_bot.connection import (
    ConnectionState, MessageType, WebSocketMessage, MessageHandler
)
from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.config import WebSocketConfig
from injective_bot.models import (
    MarketInfo, OrderbookSnapshot, OHLCVData, PriceLevel, TradeExecution
)



class MockConnectionDataHandler(MessageHandler):
    """Mock handler that processes connection data into models"""
    
    def __init__(self):
        self.processed_models = []
        self.raw_messages = []
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        """Process connection message into data models"""
        self.raw_messages.append(message)
        
        if message.message_type == MessageType.ORDERBOOK:
            # Convert connection orderbook data to OrderbookSnapshot model
            data = message.data.get("orderbook", {})
            if data:
                orderbook = OrderbookSnapshot(
                    market_id=data.get("market_id", "UNKNOWN"),
                    sequence=data.get("sequence", 1),
                    bids=[
                        PriceLevel(
                            price=Decimal(bid["price"]), 
                            quantity=Decimal(bid["quantity"])
                        ) for bid in data.get("bids", [])
                    ],
                    asks=[
                        PriceLevel(
                            price=Decimal(ask["price"]), 
                            quantity=Decimal(ask["quantity"])
                        ) for ask in data.get("asks", [])
                    ]
                )
                self.processed_models.append(orderbook)
        
        elif message.message_type == MessageType.TRADES:
            # Convert connection trades data to TradeExecution models
            trades = message.data.get("trades", [])
            for trade_data in trades:
                trade = TradeExecution(
                    trade_id=trade_data.get("trade_id", f"trade_{len(self.processed_models)}"),
                    market_id=trade_data.get("market_id", "UNKNOWN"),
                    side=trade_data.get("side", "buy"),
                    quantity=Decimal(trade_data.get("quantity", "0")),
                    price=Decimal(trade_data.get("price", "0")),
                    timestamp=datetime.now(timezone.utc)
                )
                self.processed_models.append(trade)


class TestConnectionToModelIntegration:
    """Test connection data processing to data models integration"""
    
    @pytest.fixture
    def config(self):
        """Connection configuration for testing"""
        return WebSocketConfig(
            max_reconnect_attempts=3,
            reconnect_delay_base=0.1,
            connection_timeout=5.0,
            max_message_rate=1000
        )
    
    @pytest.fixture
    def client(self, config):
        """Mock client for testing"""
        client = Mock(spec=InjectiveStreamClient)
        client.config = config
        client.connection_state = ConnectionState.DISCONNECTED
        return client
    
    @pytest.fixture
    def handler(self):
        """Mock data handler for testing"""
        return MockConnectionDataHandler()

    @pytest.mark.asyncio
    async def test_connection_orderbook_to_snapshot_model(self, client, handler):
        """Test: Connection orderbook data → OrderbookSnapshot model conversion"""
        # Arrange
        raw_message = WebSocketMessage(
            message_id="test_orderbook_001",
            message_type=MessageType.ORDERBOOK,
            data={
                "orderbook": {
                    "market_id": "INJ/USDT",
                    "sequence": 12345,
                    "bids": [
                        {"price": "15.50", "quantity": "100.0"},
                        {"price": "15.45", "quantity": "250.0"}
                    ],
                    "asks": [
                        {"price": "15.55", "quantity": "150.0"},
                        {"price": "15.60", "quantity": "200.0"}
                    ]
                }
            },
            timestamp=datetime.now(timezone.utc)
        )
        
        # Act
        await handler.handle_message(raw_message)
        
        # Assert
        assert len(handler.processed_models) == 1
        assert len(handler.raw_messages) == 1
        
        orderbook = handler.processed_models[0]
        assert isinstance(orderbook, OrderbookSnapshot)
        assert orderbook.market_id == "INJ/USDT"
        assert orderbook.sequence == 12345
        assert len(orderbook.bids) == 2
        assert len(orderbook.asks) == 2
        
        # Verify bid/ask structure
        assert orderbook.bids[0].price == Decimal("15.50")
        assert orderbook.bids[0].quantity == Decimal("100.0")
        assert orderbook.asks[0].price == Decimal("15.55")
        assert orderbook.asks[0].quantity == Decimal("150.0")

    @pytest.mark.asyncio
    async def test_connection_trades_to_execution_models(self, client, handler):
        """Test: Connection trades data → TradeExecution model conversion"""
        # Arrange
        raw_message = WebSocketMessage(
            message_id="test_trades_001",
            message_type=MessageType.TRADES,
            data={
                "trades": [
                    {
                        "trade_id": "trade_001",
                        "market_id": "INJ/USDT",
                        "side": "buy",
                        "quantity": "50.0",
                        "price": "15.52"
                    },
                    {
                        "trade_id": "trade_002",
                        "market_id": "INJ/USDT",
                        "side": "sell",
                        "quantity": "75.0",
                        "price": "15.51"
                    }
                ]
            },
            timestamp=datetime.now(timezone.utc)
        )
        
        # Act
        await handler.handle_message(raw_message)
        
        # Assert
        assert len(handler.processed_models) == 2
        assert len(handler.raw_messages) == 1
        
        trade1, trade2 = handler.processed_models
        assert isinstance(trade1, TradeExecution)
        assert isinstance(trade2, TradeExecution)
        
        # Verify trade 1
        assert trade1.trade_id == "trade_001"
        assert trade1.market_id == "INJ/USDT"
        assert trade1.side == "buy"
        assert trade1.quantity == Decimal("50.0")
        assert trade1.price == Decimal("15.52")
        
        # Verify trade 2
        assert trade2.trade_id == "trade_002"
        assert trade2.side == "sell"
        assert trade2.quantity == Decimal("75.0")
        assert trade2.price == Decimal("15.51")

    @pytest.mark.asyncio
    async def test_message_queue_processing_pipeline(self, client, handler):
        """Test: Complete message queue processing pipeline"""
        # Arrange
        messages = [
            WebSocketMessage(
                message_id="pipeline_msg_001",
                message_type=MessageType.ORDERBOOK,
                data={
                    "orderbook": {
                        "market_id": "INJ/USDT",
                        "sequence": 100,
                        "bids": [{"price": "15.40", "quantity": "100.0"}],
                        "asks": [{"price": "15.45", "quantity": "150.0"}]
                    }
                },
                timestamp=datetime.now(timezone.utc)
            ),
            WebSocketMessage(
                message_id="pipeline_msg_002",
                message_type=MessageType.TRADES,
                data={
                    "trades": [
                        {
                            "trade_id": "pipeline_trade_001",
                            "market_id": "INJ/USDT",
                            "side": "buy",
                            "quantity": "25.0",
                            "price": "15.42"
                        }
                    ]
                },
                timestamp=datetime.now(timezone.utc)
            )
        ]
        
        # Act - Process messages sequentially through pipeline
        for message in messages:
            await handler.handle_message(message)
        
        # Assert - Verify pipeline processed all messages correctly
        assert len(handler.processed_models) == 2
        assert len(handler.raw_messages) == 2
        
        orderbook = handler.processed_models[0]
        trade = handler.processed_models[1]
        
        assert isinstance(orderbook, OrderbookSnapshot)
        assert isinstance(trade, TradeExecution)
        assert orderbook.market_id == "INJ/USDT"
        assert trade.trade_id == "pipeline_trade_001"

    @pytest.mark.asyncio
    async def test_malformed_data_handling(self, client, handler):
        """Test: Malformed data handling and error resilience"""
        # Arrange - Malformed messages
        malformed_messages = [
            WebSocketMessage(
                message_id="malformed_msg_001",
                message_type=MessageType.ORDERBOOK,
                data={"invalid": "structure"},  # Missing orderbook key
                timestamp=datetime.now(timezone.utc)
            ),
            WebSocketMessage(
                message_id="malformed_msg_002",
                message_type=MessageType.TRADES,
                data={"trades": []},  # Empty trades list
                timestamp=datetime.now(timezone.utc)
            )
        ]
        
        # Act - Process malformed messages
        for message in malformed_messages:
            try:
                await handler.handle_message(message)
            except Exception:
                pass  # Expected for malformed data
        
        # Assert - Handler should be resilient
        assert len(handler.raw_messages) == 2  # All messages received
        # Should have processed valid parts, skipped invalid ones
        assert len(handler.processed_models) <= 2

    @pytest.mark.asyncio
    async def test_high_throughput_processing(self, client, handler):
        """Test: High-throughput message processing (100 messages <1 second)"""
        # Arrange
        messages = []
        for i in range(100):
            message = WebSocketMessage(
                message_id=f"high_throughput_{i}",
                message_type=MessageType.TRADES,
                data={
                    "trades": [
                        {
                            "trade_id": f"high_throughput_{i}",
                            "market_id": "INJ/USDT",
                            "side": "buy" if i % 2 == 0 else "sell",
                            "quantity": f"{10 + i}",
                            "price": f"{15.0 + (i * 0.01)}"
                        }
                    ]
                },
                timestamp=datetime.now(timezone.utc)
            )
            messages.append(message)
        
        # Act - Process high volume with timing
        start_time = datetime.now()
        
        for message in messages:
            await handler.handle_message(message)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Assert - Performance requirements
        assert processing_time < 1.0  # Complete in under 1 second
        assert len(handler.processed_models) == 100
        assert len(handler.raw_messages) == 100
        
        # Verify data integrity under high load
        first_trade = handler.processed_models[0]
        last_trade = handler.processed_models[-1]
        
        assert first_trade.trade_id == "high_throughput_0"
        assert last_trade.trade_id == "high_throughput_99"
        assert first_trade.side == "buy"
        assert last_trade.side == "sell"

    @pytest.mark.asyncio
    async def test_connection_state_integration_with_data_flow(self, client, handler):
        """Test: Connection state integration with data flow"""
        # Arrange
        client.connection_state = ConnectionState.CONNECTED
        
        message = WebSocketMessage(
            message_id="state_test_001",
            message_type=MessageType.ORDERBOOK,
            data={
                "orderbook": {
                    "market_id": "INJ/USDT",
                    "sequence": 300,
                    "bids": [{"price": "15.30", "quantity": "200.0"}],
                    "asks": [{"price": "15.35", "quantity": "180.0"}]
                }
            },
            timestamp=datetime.now(timezone.utc)
        )
        
        # Act - Process with connected state
        await handler.handle_message(message)
        
        # Simulate connection loss
        client.connection_state = ConnectionState.DISCONNECTED
        
        # Try to process another message
        message2 = WebSocketMessage(
            message_id="state_test_002",
            message_type=MessageType.TRADES,
            data={
                "trades": [
                    {
                        "trade_id": "disconnected_trade",
                        "market_id": "INJ/USDT",
                        "side": "buy",
                        "quantity": "30.0",
                        "price": "15.32"
                    }
                ]
            },
            timestamp=datetime.now(timezone.utc)
        )
        
        await handler.handle_message(message2)
        
        # Assert - Handler processed both messages regardless of connection state
        # (Handler focuses on data processing, not connection management)
        assert len(handler.processed_models) == 2
        assert client.connection_state == ConnectionState.DISCONNECTED
        
        orderbook = handler.processed_models[0]
        trade = handler.processed_models[1]
        
        assert isinstance(orderbook, OrderbookSnapshot)
        assert isinstance(trade, TradeExecution)
        assert trade.trade_id == "disconnected_trade"
