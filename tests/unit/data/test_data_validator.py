"""
Unit tests for DataValidator - Layer 3 Market Data Processing

Test Coverage:
- Data quality validation
- Price data validation
- Volume data validation
- Timestamp validation
- Market data consistency checks
- Outlier detection
- Data completeness validation
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from injective_bot.models import TradeExecution, OrderbookSnapshot, PriceLevel
from injective_bot.data.data_validator import DataValidator, ValidationResult, ValidationError, DataQualityReport


class TestDataValidator:
    """Test suite for DataValidator class."""

    @pytest.fixture
    def validator(self):
        """Create DataValidator instance for testing."""
        return DataValidator(
            price_precision=2,
            quantity_precision=3,
            max_price_deviation=Decimal("0.10"),  # 10% max deviation
            timestamp_tolerance=timedelta(seconds=30)
        )

    @pytest.fixture
    def valid_trade(self):
        """Generate valid trade execution for testing."""
        return TradeExecution(
            trade_id="trade_1",
            market_id="INJ/USDT",
            price=Decimal("10.50"),
            quantity=Decimal("100.000"),
            side="buy",
            timestamp=datetime.now(),
            message_id="msg_1"
        )

    @pytest.fixture
    def valid_orderbook(self):
        """Generate valid orderbook snapshot for testing."""
        bids = [
            PriceLevel(price=Decimal("10.50"), quantity=Decimal("100")),
            PriceLevel(price=Decimal("10.49"), quantity=Decimal("200")),
            PriceLevel(price=Decimal("10.48"), quantity=Decimal("150"))
        ]
        
        asks = [
            PriceLevel(price=Decimal("10.51"), quantity=Decimal("120")),
            PriceLevel(price=Decimal("10.52"), quantity=Decimal("180")),
            PriceLevel(price=Decimal("10.53"), quantity=Decimal("160"))
        ]
        
        return OrderbookSnapshot(
            market_id="INJ/USDT",
            sequence=1,
            bids=bids,
            asks=asks,
            timestamp=datetime.now()
        )

    def test_validator_initialization(self, validator):
        """Test DataValidator initialization."""
        assert validator is not None
        assert validator.price_precision == 2
        assert validator.quantity_precision == 3
        assert validator.max_price_deviation == Decimal("0.10")
        assert validator.timestamp_tolerance == timedelta(seconds=30)

    def test_valid_trade_validation(self, validator, valid_trade):
        """Test validation of valid trade data."""
        result = validator.validate_trade(valid_trade)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.data_type == "trade"

    def test_invalid_trade_price(self, validator, valid_trade):
        """Test validation of trade with invalid price."""
        # Negative price
        invalid_trade = valid_trade.model_copy()
        invalid_trade.price = Decimal("-10.50")
        
        result = validator.validate_trade(invalid_trade)
        assert result.is_valid is False
        assert any("price" in error.field for error in result.errors)

    def test_invalid_trade_quantity(self, validator, valid_trade):
        """Test validation of trade with invalid quantity."""
        # Zero quantity
        invalid_trade = valid_trade.model_copy()
        invalid_trade.quantity = Decimal("0")
        
        result = validator.validate_trade(invalid_trade)
        assert result.is_valid is False
        assert any("quantity" in error.field for error in result.errors)

    def test_invalid_trade_side(self, validator, valid_trade):
        """Test validation of trade with invalid side."""
        invalid_trade = valid_trade.model_copy()
        invalid_trade.side = "invalid_side"
        
        result = validator.validate_trade(invalid_trade)
        assert result.is_valid is False
        assert any("side" in error.field for error in result.errors)

    def test_future_timestamp_validation(self, validator, valid_trade):
        """Test validation of trade with future timestamp."""
        future_trade = valid_trade.model_copy()
        future_trade.timestamp = datetime.now() + timedelta(hours=1)
        
        result = validator.validate_trade(future_trade)
        assert result.is_valid is False
        assert any("timestamp" in error.field for error in result.errors)

    def test_old_timestamp_validation(self, validator, valid_trade):
        """Test validation of trade with very old timestamp."""
        old_trade = valid_trade.model_copy()
        old_trade.timestamp = datetime.now() - timedelta(hours=1)
        
        result = validator.validate_trade(old_trade)
        assert result.is_valid is False
        assert any("timestamp" in error.field for error in result.errors)

    def test_price_precision_validation(self, validator):
        """Test price precision validation."""
        # Too many decimal places
        high_precision_trade = TradeExecution(
            trade_id="trade_hp",
            market_id="INJ/USDT",
            price=Decimal("10.123456"),  # More than 2 decimal places
            quantity=Decimal("100.000"),
            side="buy",
            timestamp=datetime.now(),
            message_id="msg_hp"
        )
        
        result = validator.validate_trade(high_precision_trade)
        assert result.is_valid is False
        assert any("precision" in error.message for error in result.errors)

    def test_quantity_precision_validation(self, validator):
        """Test quantity precision validation."""
        # Too many decimal places
        high_precision_trade = TradeExecution(
            trade_id="trade_hq",
            market_id="INJ/USDT",
            price=Decimal("10.50"),
            quantity=Decimal("100.123456"),  # More than 3 decimal places
            side="buy",
            timestamp=datetime.now(),
            message_id="msg_hq"
        )
        
        result = validator.validate_trade(high_precision_trade)
        assert result.is_valid is False
        assert any("precision" in error.message for error in result.errors)

    def test_valid_orderbook_validation(self, validator, valid_orderbook):
        """Test validation of valid orderbook data."""
        result = validator.validate_orderbook(valid_orderbook)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.data_type == "orderbook"

    def test_orderbook_bid_ask_ordering(self, validator, valid_orderbook):
        """Test orderbook bid/ask price ordering validation."""
        # Create orderbook with incorrect bid ordering (not descending)
        invalid_bids = [
            PriceLevel(price=Decimal("10.48"), quantity=Decimal("100")),  # Should be highest
            PriceLevel(price=Decimal("10.50"), quantity=Decimal("200")),  # Wrong order
            PriceLevel(price=Decimal("10.49"), quantity=Decimal("150"))
        ]
        
        invalid_orderbook = valid_orderbook.model_copy()
        invalid_orderbook.bids = invalid_bids
        
        result = validator.validate_orderbook(invalid_orderbook)
        assert result.is_valid is False
        assert any("ordering" in error.message for error in result.errors)

    def test_orderbook_crossed_market(self, validator, valid_orderbook):
        """Test validation of crossed market (bid > ask)."""
        # Create crossed market scenario
        crossed_orderbook = valid_orderbook.model_copy()
        crossed_orderbook.bids[0].price = Decimal("10.55")  # Higher than best ask
        
        result = validator.validate_orderbook(crossed_orderbook)
        assert result.is_valid is False
        assert any("crossed" in error.message for error in result.errors)

    def test_empty_orderbook_validation(self, validator):
        """Test validation of empty orderbook."""
        empty_orderbook = OrderbookSnapshot(
            market_id="INJ/USDT",
            sequence=1,
            bids=[],
            asks=[],
            timestamp=datetime.now()
        )
        
        result = validator.validate_orderbook(empty_orderbook)
        assert result.is_valid is False
        assert any("empty" in error.message for error in result.errors)

    def test_price_deviation_detection(self, validator):
        """Test detection of price deviations (outliers)."""
        base_price = Decimal("10.50")
        
        # Create trade sequence with normal prices
        normal_trades = [
            TradeExecution(
                trade_id=f"trade_{i}",
                market_id="INJ/USDT",
                price=base_price + Decimal(str(i * 0.01)),  # Small increments
                quantity=Decimal("100"),
                side="buy",
                timestamp=datetime.now(),
                message_id=f"msg_{i}"
            ) for i in range(5)
        ]
        
        # Add outlier trade (>10% deviation)
        outlier_trade = TradeExecution(
            trade_id="outlier",
            market_id="INJ/USDT",
            price=base_price * Decimal("1.20"),  # 20% higher
            quantity=Decimal("100"),
            side="buy",
            timestamp=datetime.now(),
            message_id="msg_outlier"
        )
        
        # Validate sequence
        for trade in normal_trades:
            validator.validate_trade(trade)
        
        # Outlier should be detected
        result = validator.validate_trade_sequence(normal_trades + [outlier_trade])
        assert result.is_valid is False
        assert any("deviation" in error.message for error in result.errors)

    def test_data_completeness_validation(self, validator):
        """Test data completeness validation."""
        # Since Pydantic validates at creation, test with model_validate to bypass validation
        from pydantic import ValidationError as PydanticValidationError
        
        # Test that empty trade_id is caught by Pydantic
        with pytest.raises(PydanticValidationError):
            TradeExecution(
                trade_id="",  # Missing trade_id
                market_id="INJ/USDT",
                price=Decimal("10.50"),
                quantity=Decimal("100"),
                side="buy",
                timestamp=datetime.now(),
                message_id="msg_incomplete"
            )

    def test_market_id_validation(self, validator, valid_trade):
        """Test market ID format validation."""
        invalid_trade = valid_trade.model_copy()
        invalid_trade.market_id = "INVALID_FORMAT"  # Should be "TOKEN/TOKEN"
        
        result = validator.validate_trade(invalid_trade)
        assert result.is_valid is False
        assert any("market_id" in error.field for error in result.errors)

    def test_batch_validation(self, validator, valid_trade, valid_orderbook):
        """Test batch validation of multiple data items."""
        trades = [valid_trade.model_copy() for _ in range(10)]
        orderbooks = [valid_orderbook.model_copy() for _ in range(5)]
        
        # Inject some invalid data
        trades[5].price = Decimal("-1.00")  # Invalid price
        orderbooks[2].bids = []  # Empty bids
        
        trade_results = validator.validate_batch(trades, data_type="trade")
        orderbook_results = validator.validate_batch(orderbooks, data_type="orderbook")
        
        assert len(trade_results) == 10
        assert len(orderbook_results) == 5
        
        # Check specific validation results
        assert trade_results[5].is_valid is False  # Invalid trade
        assert orderbook_results[2].is_valid is False  # Invalid orderbook

    def test_data_quality_report(self, validator, valid_trade, valid_orderbook):
        """Test generation of data quality report."""
        # Process mixed valid/invalid data
        trades = [valid_trade.model_copy() for _ in range(20)]
        
        # Make some trades invalid
        trades[5].price = Decimal("-1.00")
        trades[10].quantity = Decimal("0")
        trades[15].side = "invalid"
        
        # Validate all trades
        for trade in trades:
            validator.validate_trade(trade)
        
        # Generate quality report
        report = validator.generate_quality_report()
        
        assert isinstance(report, DataQualityReport)
        assert report.total_items == 20
        assert report.valid_items == 17
        assert report.invalid_items == 3
        assert report.error_rate == Decimal("0.15")  # 3/20 = 0.15

    def test_performance_requirement(self, validator, valid_trade):
        """Test validation performance requirement."""
        import time
        
        # Test single validation performance
        start_time = time.perf_counter()
        for _ in range(1000):
            validator.validate_trade(valid_trade)
        single_validation_time = time.perf_counter() - start_time
        
        # Should validate 1000 trades quickly
        assert single_validation_time < 0.1, f"Validation took {single_validation_time:.3f}s"

    def test_concurrent_validation(self, validator, valid_trade):
        """Test concurrent validation operations."""
        import threading
        
        errors = []
        results = []
        
        def validate_trades():
            try:
                for _ in range(100):
                    result = validator.validate_trade(valid_trade)
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple validation threads
        threads = [threading.Thread(target=validate_trades) for _ in range(5)]
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0, f"Concurrent validation errors: {errors}"
        assert len(results) == 500  # 5 threads * 100 validations each

    def test_custom_validation_rules(self, validator):
        """Test custom validation rules."""
        # Add custom rule: minimum trade size
        def minimum_trade_size_rule(trade):
            min_size = Decimal("1000")  # $1000 minimum
            trade_value = trade.price * trade.quantity
            if trade_value < min_size:
                return ValidationError(
                    field="trade_value",
                    message=f"Trade value {trade_value} below minimum {min_size}"
                )
            return None
        
        validator.add_custom_rule("trade", minimum_trade_size_rule)
        
        # Test with small trade
        small_trade = TradeExecution(
            trade_id="small",
            market_id="INJ/USDT",
            price=Decimal("1.00"),
            quantity=Decimal("100.000"),  # $100 total value
            side="buy",
            timestamp=datetime.now(),
            message_id="msg_small"
        )
        
        result = validator.validate_trade(small_trade)
        assert result.is_valid is False
        assert any("trade_value" in error.field for error in result.errors)

    def test_validation_error_details(self, validator):
        """Test detailed validation error information."""
        from pydantic import ValidationError as PydanticValidationError
        
        # Test that Pydantic catches multiple validation errors during creation
        with pytest.raises(PydanticValidationError) as exc_info:
            bad_trade = TradeExecution(
                trade_id="",  # Missing ID
                market_id="INVALID",  # Invalid format
                price=Decimal("-10.50"),  # Negative price
                quantity=Decimal("0"),  # Zero quantity
                side="invalid_side",  # Invalid side
                timestamp=datetime.now() + timedelta(hours=1),  # Future timestamp
                message_id="msg_bad"
            )
        
        # Verify multiple validation errors were caught
        validation_error = exc_info.value
        assert len(validation_error.errors()) >= 4  # Multiple errors detected
