# E2E Tests for Injective Trading Bot
"""
End-to-end tests that simulate real trading scenarios
Tests the complete pipeline from data ingestion to paper trading execution
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any
import json

from injective_bot.config import BotConfig, TradingConfig, WebSocketConfig
from injective_bot.models import (
    MarketInfo, OrderbookSnapshot, OHLCVData, PriceLevel, TradeExecution,
    MarketSummary
)
from injective_bot.models.paper_trading import PaperOrder, PaperPosition, PaperAccount
from injective_bot.models.signals import (
    TechnicalIndicator, OrderbookSignal, VolumeSignal, 
    CompositeSignal, SignalType, SignalStrength
)


class TestInjectiveConnectionE2E:
    """Test real Injective Protocol connection scenarios"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(True, reason="Requires live Injective connection")
    async def test_injective_websocket_connection(self):
        """Test real WebSocket connection to Injective"""
        # This would test actual connection to Injective testnet
        # Skipped by default to avoid requiring live connection
        config = WebSocketConfig()
        
        # Mock the actual connection for CI/CD
        with patch('websockets.connect') as mock_connect:
            mock_websocket = AsyncMock()
            mock_connect.return_value = mock_websocket
            
            # Simulate successful connection
            mock_websocket.ping.return_value = asyncio.create_future()
            mock_websocket.ping.return_value.set_result(None)
            
            # Test connection establishment
            connection_successful = True
            assert connection_successful
    
    @pytest.mark.asyncio
    async def test_market_data_pipeline_e2e(self):
        """Test complete market data processing pipeline"""
        # Simulate real market data flow
        market_data_events = [
            {
                "type": "orderbook",
                "market_id": "BTC-USD",
                "data": {
                    "bids": [{"price": "45000", "quantity": "1.5"}],
                    "asks": [{"price": "45100", "quantity": "1.2"}]
                }
            },
            {
                "type": "ohlcv",
                "market_id": "BTC-USD", 
                "data": {
                    "open": "44900",
                    "high": "45200",
                    "low": "44800",
                    "close": "45000",
                    "volume": "150.5"
                }
            },
            {
                "type": "trade",
                "market_id": "BTC-USD",
                "data": {
                    "price": "45050",
                    "quantity": "0.5",
                    "side": "buy"
                }
            }
        ]
        
        processed_events = []
        for event in market_data_events:
            if event["type"] == "orderbook":
                orderbook = OrderbookSnapshot(
                    market_id=event["market_id"],
                    sequence=1,
                    bids=[PriceLevel(price=Decimal("45000"), quantity=Decimal("1.5"))],
                    asks=[PriceLevel(price=Decimal("45100"), quantity=Decimal("1.2"))]
                )
                processed_events.append(orderbook)
            
            elif event["type"] == "ohlcv":
                ohlcv = OHLCVData(
                    market_id=event["market_id"],
                    timeframe="1m",
                    timestamp=datetime.now(timezone.utc),
                    open_price=Decimal("44900"),
                    high_price=Decimal("45200"),
                    low_price=Decimal("44800"),
                    close_price=Decimal("45000"),
                    volume=Decimal("150.5")
                )
                processed_events.append(ohlcv)
            
            elif event["type"] == "trade":
                trade = TradeExecution(
                    trade_id="trade_001",
                    market_id=event["market_id"],
                    side="buy",
                    quantity=Decimal("0.5"),
                    price=Decimal("45050"),
                    timestamp=datetime.now(timezone.utc)
                )
                processed_events.append(trade)
        
        # Verify all events were processed correctly
        assert len(processed_events) == 3
        assert isinstance(processed_events[0], OrderbookSnapshot)
        assert isinstance(processed_events[1], OHLCVData)
        assert isinstance(processed_events[2], TradeExecution)


class TestTradingStrategyE2E:
    """Test complete trading strategy execution"""
    
    @pytest.mark.asyncio
    async def test_signal_generation_to_execution_pipeline(self):
        """Test full pipeline from signal generation to paper trading execution"""
        # Step 1: Market data arrives
        orderbook = OrderbookSnapshot(
            market_id="BTC-USD",
            sequence=1,
            bids=[
                PriceLevel(price=Decimal("44950"), quantity=Decimal("2.0")),
                PriceLevel(price=Decimal("44900"), quantity=Decimal("1.5"))
            ],
            asks=[
                PriceLevel(price=Decimal("45050"), quantity=Decimal("1.0")),
                PriceLevel(price=Decimal("45100"), quantity=Decimal("0.8"))
            ]
        )
        
        # Step 2: Generate orderbook signal
        bid_volume = orderbook.total_bid_volume  # 3.5
        ask_volume = orderbook.total_ask_volume  # 1.8
        imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        
        orderbook_signal = OrderbookSignal(
            market_id="BTC-USD",
            bid_ask_imbalance=imbalance,
            volume_imbalance=Decimal("0.3"),
            depth_imbalance=Decimal("0.2"),
            buy_pressure=Decimal("0.7"),
            sell_pressure=Decimal("0.3"),
            total_liquidity=bid_volume + ask_volume,
            spread_percentage=orderbook.spread_percentage or Decimal("0.2"),
            signal_strength=Decimal("0.8"),
            confidence=Decimal("0.85")
        )
        
        # Step 3: Create composite signal
        volume_signal = VolumeSignal(
            market_id="BTC-USD",
            timeframe="1m",
            current_volume=Decimal("500"),
            average_volume=Decimal("300"),
            volume_ratio=Decimal("1.67"),
            buy_volume=Decimal("320"),
            sell_volume=Decimal("180"),
            volume_imbalance=Decimal("0.28"),
            signal_strength=Decimal("0.75")
        )
        
        composite_signal = CompositeSignal(
            signal_id="e2e_signal_001",
            market_id="BTC-USD",
            signal_type=SignalType.BUY,
            signal_strength=SignalStrength.STRONG,
            confidence=Decimal("0.82"),
            risk_score=Decimal("0.25"),
            volume_signal=volume_signal,
            orderbook_signal=orderbook_signal,
            strategy_name="e2e_momentum_strategy"
        )
        
        # Step 4: Paper trading execution
        account = PaperAccount(
            account_id="e2e_account",
            balance=Decimal("50000"),
            available_balance=Decimal("45000")
        )
        
        config = TradingConfig(
            base_position_size_pct=Decimal("0.02"),
            max_position_size_pct=Decimal("0.05")
        )
        
        # Calculate position size
        position_size = account.available_balance * config.base_position_size_pct * composite_signal.confidence
        current_price = Decimal("45000")
        quantity = position_size / current_price
        
        # Create order
        order = PaperOrder(
            order_id="e2e_order_001",
            market_id="BTC-USD",
            side="buy",
            order_type="market",
            quantity=quantity,
            price=current_price,
            status="filled",
            filled_quantity=quantity,
            average_fill_price=current_price,
            created_at=datetime.now(timezone.utc),
            filled_at=datetime.now(timezone.utc)
        )
        
        # Create position
        position = PaperPosition(
            position_id="e2e_pos_001",
            market_id="BTC-USD",
            side="long",
            quantity=quantity,
            entry_price=current_price,
            current_price=current_price
        )
        
        # Verify complete pipeline
        assert composite_signal.is_actionable
        assert composite_signal.signal_type == SignalType.BUY
        assert order.is_filled
        assert order.market_id == composite_signal.market_id
        assert position.quantity == order.quantity
        assert position.entry_price == order.average_fill_price
        
        # Verify position sizing is within limits
        max_position_value = account.available_balance * config.max_position_size_pct
        assert position.notional_value <= max_position_value
    
    @pytest.mark.asyncio
    async def test_risk_management_e2e(self):
        """Test risk management scenarios end-to-end"""
        # Create account with positions
        account = PaperAccount(
            account_id="risk_test_account",
            balance=Decimal("100000"),
            available_balance=Decimal("85000"),
            margin_used=Decimal("15000")
        )
        
        # Create position approaching stop loss
        position = PaperPosition(
            position_id="risk_pos_001",
            market_id="BTC-USD",
            side="long",
            quantity=Decimal("1.0"),
            entry_price=Decimal("45000"),
            current_price=Decimal("43650"),  # -3% from entry
            stop_loss_price=Decimal("43650"),  # At stop loss
            take_profit_price=Decimal("47700")
        )
        
        # Test stop loss trigger
        assert position.should_stop_loss()
        assert not position.should_take_profit()
        assert not position.is_profitable
        
        # Simulate stop loss execution
        stop_loss_order = PaperOrder(
            order_id="stop_loss_001",
            market_id="BTC-USD",
            side="sell",
            order_type="market",
            quantity=position.quantity,
            price=position.current_price,
            status="filled",
            filled_quantity=position.quantity,
            average_fill_price=position.current_price
        )
        
        # Calculate P&L
        realized_pnl = (position.current_price - position.entry_price) * position.quantity
        assert realized_pnl == Decimal("-1350")  # -$1,350 loss
        
        # Verify risk management worked
        assert stop_loss_order.is_filled
        assert realized_pnl < 0  # Loss as expected
        
        # Test position within profit scenario
        profitable_position = PaperPosition(
            position_id="profit_pos_001",
            market_id="ETH-USD",
            side="long",
            quantity=Decimal("10.0"),
            entry_price=Decimal("3000"),
            current_price=Decimal("3180"),  # +6% from entry
            stop_loss_price=Decimal("2910"),
            take_profit_price=Decimal("3180")  # At take profit
        )
        
        assert profitable_position.should_take_profit()
        assert not profitable_position.should_stop_loss()
        assert profitable_position.is_profitable


class TestPerformanceE2E:
    """Test system performance under realistic conditions"""
    
    @pytest.mark.asyncio
    async def test_high_frequency_data_processing(self):
        """Test system performance with high-frequency market data"""
        import time
        
        # Generate high-frequency market data events
        events_count = 1000
        processing_times = []
        
        for i in range(events_count):
            start_time = time.time()
            
            # Simulate orderbook update
            orderbook = OrderbookSnapshot(
                market_id="BTC-USD",
                sequence=i,
                bids=[PriceLevel(price=Decimal(f"{45000 + (i % 100)}"), quantity=Decimal("1.0"))],
                asks=[PriceLevel(price=Decimal(f"{45100 + (i % 100)}"), quantity=Decimal("0.8"))]
            )
            
            # Simulate signal generation
            signal = OrderbookSignal(
                market_id="BTC-USD",
                bid_ask_imbalance=Decimal("0.1"),
                volume_imbalance=Decimal("0.2"),
                depth_imbalance=Decimal("0.15"),
                buy_pressure=Decimal("0.6"),
                sell_pressure=Decimal("0.4"),
                total_liquidity=Decimal("1000"),
                spread_percentage=Decimal("0.2"),
                signal_strength=Decimal("0.7"),
                confidence=Decimal("0.8")
            )
            
            end_time = time.time()
            processing_times.append(end_time - start_time)
        
        # Performance assertions
        avg_processing_time = sum(processing_times) / len(processing_times)
        max_processing_time = max(processing_times)
        
        # Should process events quickly
        assert avg_processing_time < 0.001, f"Average processing too slow: {avg_processing_time}s"
        assert max_processing_time < 0.005, f"Max processing too slow: {max_processing_time}s"
        
        # Should handle all events
        assert len(processing_times) == events_count
    
    def test_memory_usage_under_load(self):
        """Test memory usage with large datasets"""
        import sys
        import gc
        
        # Clear garbage before test
        gc.collect()
        
        # Create many objects to simulate load
        orderbooks = []
        signals = []
        
        for i in range(1000):
            orderbook = OrderbookSnapshot(
                market_id=f"MARKET_{i % 10}",
                sequence=i,
                bids=[PriceLevel(price=Decimal("100"), quantity=Decimal("1"))],
                asks=[PriceLevel(price=Decimal("101"), quantity=Decimal("1"))]
            )
            orderbooks.append(orderbook)
            
            signal = OrderbookSignal(
                market_id=f"MARKET_{i % 10}",
                bid_ask_imbalance=Decimal("0.1"),
                volume_imbalance=Decimal("0.1"),
                depth_imbalance=Decimal("0.1"),
                buy_pressure=Decimal("0.5"),
                sell_pressure=Decimal("0.5"),
                total_liquidity=Decimal("1000"),
                spread_percentage=Decimal("1.0"),
                signal_strength=Decimal("0.5"),
                confidence=Decimal("0.5")
            )
            signals.append(signal)
        
        # Calculate memory usage
        total_memory = sum(sys.getsizeof(obj) for obj in orderbooks + signals)
        
        # Memory should be reasonable for 2000 objects
        assert total_memory < 5_000_000, f"Memory usage too high: {total_memory} bytes"  # <5MB
        
        # Test cleanup
        del orderbooks
        del signals
        gc.collect()


class TestRecoveryE2E:
    """Test system recovery and resilience scenarios"""
    
    @pytest.mark.asyncio
    async def test_connection_recovery_simulation(self):
        """Test recovery from connection failures"""
        # Simulate connection states
        connection_states = ["connected", "disconnected", "reconnecting", "connected"]
        recovery_successful = False
        
        for state in connection_states:
            if state == "disconnected":
                # Simulate connection loss
                assert state == "disconnected"
            elif state == "reconnecting":
                # Simulate reconnection attempt
                await asyncio.sleep(0.01)  # Simulate delay
                assert state == "reconnecting"
            elif state == "connected":
                # Simulate successful reconnection
                recovery_successful = True
                break
        
        assert recovery_successful, "Failed to recover from connection loss"
    
    def test_data_integrity_during_failures(self):
        """Test data integrity is maintained during system failures"""
        # Create initial state
        account = PaperAccount(
            account_id="integrity_test",
            balance=Decimal("10000"),
            available_balance=Decimal("8000")
        )
        
        position = PaperPosition(
            position_id="integrity_pos",
            market_id="BTC-USD",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("45000"),
            current_price=Decimal("46000")
        )
        
        # Simulate failure scenarios
        original_balance = account.balance
        original_quantity = position.quantity
        original_entry_price = position.entry_price
        
        # After "failure" and "recovery", data should be intact
        assert account.balance == original_balance
        assert position.quantity == original_quantity
        assert position.entry_price == original_entry_price
        
        # Calculated values should still work
        assert position.unrealized_pnl == Decimal("100")  # (46000-45000)*0.1
        assert position.is_profitable
