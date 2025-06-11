# Layer 1 Tests: Data Structures & Models - Paper Trading Tests
"""
TDD tests for paper trading models
Following RED-GREEN-REFACTOR cycle
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import ValidationError

from injective_bot.models.paper_trading import (
    PositionSide, OrderStatus, PaperOrder, PaperPosition, 
    PaperAccount, TradingPerformance
)
from injective_bot.models import OrderSide, OrderType


class TestPaperOrder:
    """Test PaperOrder model validation and behavior"""
    
    def test_paper_order_creation_with_required_fields(self):
        """Test PaperOrder creation with all required fields"""
        order = PaperOrder(
            order_id="order_123",
            market_id="BTC-USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.5"),
            price=Decimal("50000")
        )
        
        assert order.order_id == "order_123"
        assert order.market_id == "BTC-USD"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.LIMIT
        assert order.quantity == Decimal("1.5")
        assert order.price == Decimal("50000")
        assert order.status == OrderStatus.PENDING  # Default
        assert order.filled_quantity == Decimal("0")  # Default
    
    def test_paper_order_properties_calculation(self):
        """Test PaperOrder calculated properties"""
        order = PaperOrder(
            order_id="order_123",
            market_id="BTC-USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.0"),
            price=Decimal("50000"),
            filled_quantity=Decimal("0.5"),
            average_fill_price=Decimal("49950")
        )
        
        # Test remaining quantity
        assert order.remaining_quantity == Decimal("1.5")  # 2.0 - 0.5
        
        # Test fill percentage
        assert order.fill_percentage == Decimal("25")  # (0.5/2.0)*100
        
        # Test notional value with average fill price
        assert order.notional_value == Decimal("24975")  # 0.5 * 49950
        
        # Test is_filled
        assert not order.is_filled
    
    def test_paper_order_validation_errors(self):
        """Test validation errors for PaperOrder"""
        # Test negative quantity
        with pytest.raises(ValidationError):
            PaperOrder(
                order_id="test",
                market_id="BTC-USD",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("-1"),  # Invalid
                price=Decimal("50000")
            )
        
        # Test filled quantity exceeding total quantity
        with pytest.raises(ValidationError):
            PaperOrder(
                order_id="test",
                market_id="BTC-USD",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1.0"),
                price=Decimal("50000"),
                filled_quantity=Decimal("1.5")  # Exceeds quantity
            )
    
    def test_paper_order_filled_quantity_validation(self):
        """Test filled quantity validation"""
        # Filled quantity exceeds total quantity
        with pytest.raises(ValidationError) as excinfo:
            PaperOrder(
                order_id="test_order_1",
                market_id="market_1",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("100"),
                price=Decimal("50.00"),
                filled_quantity=Decimal("150"),  # Exceeds quantity
                status=OrderStatus.PARTIALLY_FILLED,
                created_at=datetime.now(timezone.utc)
            )
        assert "Filled quantity cannot exceed total quantity" in str(excinfo.value)
    
    def test_paper_order_notional_value_with_average_fill(self):
        """Test notional value calculation with average fill price"""
        order = PaperOrder(
            order_id="test_order_1",
            market_id="market_1",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            price=Decimal("50.00"),
            filled_quantity=Decimal("75"),
            average_fill_price=Decimal("49.50"),  # Different from limit price
            status=OrderStatus.PARTIALLY_FILLED,
            created_at=datetime.now(timezone.utc)
        )
        # Should use average_fill_price * filled_quantity
        assert order.notional_value == Decimal("3712.50")  # 75 * 49.50
    
    def test_paper_order_notional_value_no_fill(self):
        """Test notional value calculation with no fills"""
        order = PaperOrder(
            order_id="test_order_1",
            market_id="market_1",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            price=Decimal("50.00"),
            filled_quantity=Decimal("0"),
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        # Should use price * quantity when no fills
        assert order.notional_value == Decimal("5000.00")  # 100 * 50.00
    
    def test_paper_order_notional_value_none_case(self):
        """Test notional value returns None when no price or average fill price"""
        order = PaperOrder(
            order_id="test_order_1",
            market_id="market_1",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,  # Market order with no price
            quantity=Decimal("100"),
            price=None,  # No price set
            filled_quantity=Decimal("0"),
            average_fill_price=None,  # No average fill price
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        # Should return None when no price information is available
        assert order.notional_value is None


class TestPaperPosition:
    """Test PaperPosition model validation and behavior"""
    
    def test_paper_position_creation_long(self):
        """Test PaperPosition creation for long position"""
        position = PaperPosition(
            position_id="pos_123",
            market_id="BTC-USD",
            side=PositionSide.LONG,
            quantity=Decimal("1.0"),
            entry_price=Decimal("50000"),
            current_price=Decimal("52000")
        )
        
        assert position.position_id == "pos_123"
        assert position.side == PositionSide.LONG
        assert position.quantity == Decimal("1.0")
        assert position.entry_price == Decimal("50000")
        assert position.current_price == Decimal("52000")
    
    def test_paper_position_pnl_calculation_long(self):
        """Test P&L calculations for long position"""
        position = PaperPosition(
            position_id="pos_123",
            market_id="BTC-USD",
            side=PositionSide.LONG,
            quantity=Decimal("1.0"),
            entry_price=Decimal("50000"),
            current_price=Decimal("52000")
        )
        
        # Test unrealized P&L
        assert position.unrealized_pnl == Decimal("2000")  # (52000-50000)*1.0
        
        # Test unrealized P&L percentage
        assert position.unrealized_pnl_percentage == Decimal("4")  # (2000/50000)*100
        
        # Test profitability
        assert position.is_profitable
        
        # Test notional value
        assert position.notional_value == Decimal("52000")  # 1.0 * 52000
    
    def test_paper_position_pnl_calculation_short(self):
        """Test P&L calculations for short position"""
        position = PaperPosition(
            position_id="pos_123",
            market_id="BTC-USD",
            side=PositionSide.SHORT,
            quantity=Decimal("1.0"),
            entry_price=Decimal("50000"),
            current_price=Decimal("48000")  # Price went down
        )
        
        # Test unrealized P&L for short
        assert position.unrealized_pnl == Decimal("2000")  # (50000-48000)*1.0
        
        # Test profitability
        assert position.is_profitable
    
    def test_paper_position_stop_loss_triggers(self):
        """Test stop loss trigger conditions"""
        # Long position with stop loss
        long_position = PaperPosition(
            position_id="pos_1",
            market_id="market_1",
            side=PositionSide.LONG,
            quantity=Decimal("100"),
            entry_price=Decimal("50.00"),
            current_price=Decimal("45.00"),  # Below stop loss
            stop_loss_price=Decimal("47.00"),
            leverage=Decimal("1")
        )
        assert long_position.should_stop_loss() is True
        
        # Long position above stop loss
        long_position.current_price = Decimal("48.00")
        assert long_position.should_stop_loss() is False
        
        # Short position with stop loss
        short_position = PaperPosition(
            position_id="pos_2",
            market_id="market_1",
            side=PositionSide.SHORT,
            quantity=Decimal("100"),
            entry_price=Decimal("50.00"),
            current_price=Decimal("55.00"),  # Above stop loss
            stop_loss_price=Decimal("53.00"),
            leverage=Decimal("1")
        )
        assert short_position.should_stop_loss() is True
        
        # Short position below stop loss
        short_position.current_price = Decimal("52.00")
        assert short_position.should_stop_loss() is False
        
        # No stop loss set
        no_stop_position = PaperPosition(
            position_id="pos_3",
            market_id="market_1",
            side=PositionSide.LONG,
            quantity=Decimal("100"),
            entry_price=Decimal("50.00"),
            current_price=Decimal("45.00"),
            leverage=Decimal("1")
        )
        assert no_stop_position.should_stop_loss() is False
    
    def test_paper_position_take_profit_triggers(self):
        """Test take profit trigger conditions"""
        # Long position with take profit
        long_position = PaperPosition(
            position_id="pos_1",
            market_id="market_1",
            side=PositionSide.LONG,
            quantity=Decimal("100"),
            entry_price=Decimal("50.00"),
            current_price=Decimal("55.00"),  # Above take profit
            take_profit_price=Decimal("53.00"),
            leverage=Decimal("1")
        )
        assert long_position.should_take_profit() is True
        
        # Long position below take profit
        long_position.current_price = Decimal("52.00")
        assert long_position.should_take_profit() is False
        
        # Short position with take profit
        short_position = PaperPosition(
            position_id="pos_2",
            market_id="market_1",
            side=PositionSide.SHORT,
            quantity=Decimal("100"),
            entry_price=Decimal("50.00"),
            current_price=Decimal("45.00"),  # Below take profit
            take_profit_price=Decimal("47.00"),
            leverage=Decimal("1")
        )
        assert short_position.should_take_profit() is True
        
        # Short position above take profit
        short_position.current_price = Decimal("48.00")
        assert short_position.should_take_profit() is False
        
        # No take profit set
        no_tp_position = PaperPosition(
            position_id="pos_3",
            market_id="market_1",
            side=PositionSide.LONG,
            quantity=Decimal("100"),
            entry_price=Decimal("50.00"),
            current_price=Decimal("55.00"),
            leverage=Decimal("1")
        )
        assert no_tp_position.should_take_profit() is False
    
    def test_paper_position_margin_used(self):
        """Test margin used calculation"""
        position = PaperPosition(
            position_id="pos_1",
            market_id="market_1",
            side=PositionSide.LONG,
            quantity=Decimal("100"),
            entry_price=Decimal("50.00"),
            current_price=Decimal("55.00"),
            leverage=Decimal("2")
        )
        # Margin used = (quantity * entry_price) / leverage
        expected_margin = (Decimal("100") * Decimal("50.00")) / Decimal("2")
        assert position.margin_used == expected_margin


class TestPaperAccount:
    """Test PaperAccount model validation and behavior"""
    
    def test_paper_account_creation(self):
        """Test PaperAccount creation"""
        account = PaperAccount(
            account_id="acc_123",
            balance=Decimal("10000"),
            available_balance=Decimal("8000")
        )
        
        assert account.account_id == "acc_123"
        assert account.balance == Decimal("10000")
        assert account.available_balance == Decimal("8000")
        assert account.total_trades == 0  # Default
        assert account.realized_pnl == Decimal("0")  # Default
    
    def test_paper_account_calculated_properties(self):
        """Test PaperAccount calculated properties"""
        account = PaperAccount(
            account_id="acc_123",
            balance=Decimal("10000"),
            available_balance=Decimal("8000"),
            margin_used=Decimal("2000"),
            unrealized_pnl=Decimal("500"),
            total_trades=10,
            winning_trades=6
        )
        
        # Test total equity
        assert account.total_equity == Decimal("10500")  # 10000 + 500
        
        # Test free margin
        assert account.free_margin == Decimal("6000")  # 8000 - 2000
        
        # Test margin ratio
        assert account.margin_ratio == Decimal("25")  # (2000/8000)*100
        
        # Test win rate
        assert account.win_rate == Decimal("60")  # (6/10)*100
    
    def test_paper_account_validation_errors(self):
        """Test validation errors for PaperAccount"""
        # Test available balance exceeding total balance
        with pytest.raises(ValidationError):
            PaperAccount(
                account_id="acc_123",
                balance=Decimal("10000"),
                available_balance=Decimal("12000")  # Exceeds balance
            )


class TestTradingPerformance:
    """Test TradingPerformance model validation and behavior"""
    
    def test_trading_performance_creation(self):
        """Test TradingPerformance creation"""
        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)
        
        performance = TradingPerformance(
            period_start=start_time,
            period_end=end_time,
            total_trades=20,
            winning_trades=12,
            losing_trades=8,
            total_pnl=Decimal("1000")
        )
        
        assert performance.total_trades == 20
        assert performance.winning_trades == 12
        assert performance.losing_trades == 8
        assert performance.total_pnl == Decimal("1000")
    
    def test_trading_performance_calculated_properties(self):
        """Test TradingPerformance calculated properties"""
        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)
        
        performance = TradingPerformance(
            period_start=start_time,
            period_end=end_time,
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            total_pnl=Decimal("500")
        )
        
        # Test win rate
        assert performance.win_rate == Decimal("60")  # (6/10)*100
        
        # Test average trade
        assert performance.average_trade == Decimal("50")  # 500/10


# Performance Tests for Paper Trading Models
class TestPaperTradingPerformance:
    """Test paper trading model performance characteristics"""
    
    def test_paper_order_memory_efficiency(self):
        """Test PaperOrder memory efficiency"""
        import sys
        
        order = PaperOrder(
            order_id="test",
            market_id="BTC-USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("50000")
        )
        
        object_size = sys.getsizeof(order)
        assert object_size < 5000, f"PaperOrder object too large: {object_size} bytes"
