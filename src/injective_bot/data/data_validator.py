"""
Data Validator - Layer 3 Market Data Processing

Data quality validation for market data streams including outlier detection,
timestamp validation, and data integrity checks.
"""

from typing import List, Dict, Optional, Any, Tuple, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
import threading

from injective_bot.models import TradeExecution, OrderbookSnapshot, PriceLevel


class ValidationLevel(str, Enum):
    """Data validation severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationError:
    """Individual validation error"""
    field: str
    message: str
    severity: str = "error"
    value: Optional[Any] = None


@dataclass
class ValidationResult:
    """Data validation result"""
    is_valid: bool
    errors: List[ValidationError]
    data_type: str
    warnings: List[ValidationError] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class DataQualityReport:
    """Data quality statistics report"""
    total_items: int
    valid_items: int
    invalid_items: int
    error_rate: Decimal
    warnings_count: int = 0
    error_types: Dict[str, int] = None
    
    def __post_init__(self):
        if self.error_types is None:
            self.error_types = {}


class DataValidator:
    """
    Market data quality validator with outlier detection and integrity checks.
    
    Features:
    - Price and volume validation
    - Timestamp ordering validation
    - Outlier detection using statistical methods
    - Data completeness checks
    - Real-time validation with configurable thresholds
    """
    
    def __init__(
        self,
        price_precision: int = 2,
        quantity_precision: int = 3,
        max_price_deviation: Decimal = Decimal("0.10"),
        timestamp_tolerance: timedelta = timedelta(seconds=60)
    ):
        """
        Initialize data validator.
        
        Args:
            price_precision: Number of decimal places for price validation
            quantity_precision: Number of decimal places for quantity validation
            max_price_deviation: Maximum price deviation percentage (0.10 = 10%)
            timestamp_tolerance: Maximum timestamp drift tolerance
        """
        self.price_precision = price_precision
        self.quantity_precision = quantity_precision
        self.max_price_deviation = max_price_deviation
        self.timestamp_tolerance = timestamp_tolerance
        
        # Historical data for validation
        self._price_history: Dict[str, List[Decimal]] = {}
        self._volume_history: Dict[str, List[Decimal]] = {}
        self._last_timestamps: Dict[str, datetime] = {}
        
        # Statistics
        self._validation_count = 0
        self._error_count = 0
        self._warnings_count = 0
        
        # Custom validation rules
        self._custom_rules: Dict[str, List[Callable]] = {"trade": [], "orderbook": []}
        
        # Thread safety
        self._lock = threading.RLock()
        
    def validate_trade(self, trade: TradeExecution) -> ValidationResult:
        """
        Validate trade execution data.
        
        Args:
            trade: Trade execution to validate
            
        Returns:
            ValidationResult with errors and warnings
        """
        with self._lock:
            self._validation_count += 1
            errors = []
            warnings = []
            
            # Basic field validation
            errors.extend(self._validate_trade_fields(trade))
            
            # Price validation
            errors.extend(self._validate_price(trade))
            
            # Quantity validation
            errors.extend(self._validate_quantity(trade))
            
            # Timestamp validation
            errors.extend(self._validate_timestamp(trade.market_id, trade.timestamp))
            
            # Side validation
            errors.extend(self._validate_side(trade))
            
            # Market ID validation
            errors.extend(self._validate_market_id(trade))
            
            # Precision validation
            errors.extend(self._validate_precision(trade))
            
            # Custom rules
            for rule in self._custom_rules["trade"]:
                error = rule(trade)
                if error:
                    errors.append(error)
            
            # Update statistics
            if errors:
                self._error_count += 1
            if warnings:
                self._warnings_count += 1
                
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                data_type="trade"
            )
    
    def validate_orderbook(self, orderbook: OrderbookSnapshot) -> ValidationResult:
        """
        Validate orderbook snapshot data.
        
        Args:
            orderbook: Orderbook snapshot to validate
            
        Returns:
            ValidationResult with errors and warnings
        """
        with self._lock:
            self._validation_count += 1
            errors = []
            warnings = []
            
            # Basic field validation
            errors.extend(self._validate_orderbook_fields(orderbook))
            
            # Price level validation
            errors.extend(self._validate_price_levels(orderbook))
            
            # Spread validation
            errors.extend(self._validate_spread(orderbook))
            
            # Timestamp validation
            errors.extend(self._validate_timestamp(orderbook.market_id, orderbook.timestamp))
            
            # Custom rules
            for rule in self._custom_rules["orderbook"]:
                error = rule(orderbook)
                if error:
                    errors.append(error)
            
            # Update statistics
            if errors:
                self._error_count += 1
            if warnings:
                self._warnings_count += 1
                
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                data_type="orderbook"
            )
    
    def validate_batch(self, items: List[Any], data_type: str) -> List[ValidationResult]:
        """
        Validate batch of data items.
        
        Args:
            items: List of items to validate
            data_type: Type of data ("trade" or "orderbook")
            
        Returns:
            List of validation results
        """
        results = []
        for item in items:
            if data_type == "trade":
                results.append(self.validate_trade(item))
            elif data_type == "orderbook":
                results.append(self.validate_orderbook(item))
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
        return results
    
    def validate_trade_sequence(self, trades: List[TradeExecution]) -> ValidationResult:
        """
        Validate sequence of trades for outliers and patterns.
        
        Args:
            trades: List of trade executions
            
        Returns:
            ValidationResult for the sequence
        """
        errors = []
        warnings = []
        
        if len(trades) < 2:
            return ValidationResult(is_valid=True, errors=[], data_type="trade_sequence")
            
        # Check for price deviations
        prices = [trade.price for trade in trades]
        for i, trade in enumerate(trades[1:], 1):
            prev_price = prices[i-1]
            price_change = abs(trade.price - prev_price) / prev_price
            
            if price_change > self.max_price_deviation:
                errors.append(ValidationError(
                    field="price",
                    message=f"Price deviation {price_change:.1%} exceeds threshold {self.max_price_deviation:.1%}",
                    value=trade.price
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data_type="trade_sequence"
        )
    
    def add_custom_rule(self, data_type: str, rule: Callable) -> None:
        """
        Add custom validation rule.
        
        Args:
            data_type: Type of data ("trade" or "orderbook")
            rule: Validation function that returns ValidationError or None
        """
        if data_type not in self._custom_rules:
            raise ValueError(f"Unsupported data type: {data_type}")
        self._custom_rules[data_type].append(rule)
    
    def generate_quality_report(self) -> DataQualityReport:
        """
        Generate data quality report.
        
        Returns:
            DataQualityReport with statistics
        """
        with self._lock:
            valid_items = self._validation_count - self._error_count
            error_rate = Decimal(str(self._error_count)) / Decimal(str(max(self._validation_count, 1)))
            
            return DataQualityReport(
                total_items=self._validation_count,
                valid_items=valid_items,
                invalid_items=self._error_count,
                error_rate=error_rate,
                warnings_count=self._warnings_count
            )
    
    # Private validation methods
    def _validate_trade_fields(self, trade: TradeExecution) -> List[ValidationError]:
        """Validate basic trade fields"""
        errors = []
        
        if not trade.trade_id or not trade.trade_id.strip():
            errors.append(ValidationError(
                field="trade_id",
                message="Trade ID is required and cannot be empty"
            ))
        
        if not trade.market_id or not trade.market_id.strip():
            errors.append(ValidationError(
                field="market_id", 
                message="Market ID is required and cannot be empty"
            ))
        
        return errors
    
    def _validate_price(self, trade: TradeExecution) -> List[ValidationError]:
        """Validate trade price"""
        errors = []
        
        if trade.price <= 0:
            errors.append(ValidationError(
                field="price",
                message="Price must be positive",
                value=trade.price
            ))
        
        return errors
    
    def _validate_quantity(self, trade: TradeExecution) -> List[ValidationError]:
        """Validate trade quantity"""
        errors = []
        
        if trade.quantity <= 0:
            errors.append(ValidationError(
                field="quantity",
                message="Quantity must be positive",
                value=trade.quantity
            ))
        
        return errors
    
    def _validate_side(self, trade: TradeExecution) -> List[ValidationError]:
        """Validate trade side"""
        errors = []
        
        valid_sides = ["buy", "sell"]
        if trade.side not in valid_sides:
            errors.append(ValidationError(
                field="side",
                message=f"Side must be one of {valid_sides}",
                value=trade.side
            ))
        
        return errors
    
    def _validate_market_id(self, trade: TradeExecution) -> List[ValidationError]:
        """Validate market ID format"""
        errors = []
        
        # Check for format like "TOKEN/TOKEN"
        if "/" not in trade.market_id:
            errors.append(ValidationError(
                field="market_id",
                message="Market ID must be in format 'TOKEN/TOKEN'",
                value=trade.market_id
            ))
        
        return errors
    
    def _validate_precision(self, trade: TradeExecution) -> List[ValidationError]:
        """Validate price and quantity precision"""
        errors = []
        
        # Check price precision
        price_decimal = trade.price.as_tuple()
        if price_decimal.exponent < 0:  # Has decimal places
            decimal_places = -price_decimal.exponent
            if decimal_places > self.price_precision:
                errors.append(ValidationError(
                    field="price",
                    message=f"Price precision exceeds limit: {decimal_places} > {self.price_precision}",
                    value=trade.price
                ))
        
        # Check quantity precision  
        quantity_decimal = trade.quantity.as_tuple()
        if quantity_decimal.exponent < 0:  # Has decimal places
            decimal_places = -quantity_decimal.exponent
            if decimal_places > self.quantity_precision:
                errors.append(ValidationError(
                    field="quantity", 
                    message=f"Quantity precision exceeds limit: {decimal_places} > {self.quantity_precision}",
                    value=trade.quantity
                ))
        
        return errors
    
    def _validate_timestamp(self, market_id: str, timestamp: datetime) -> List[ValidationError]:
        """Validate timestamp"""
        errors = []
        
        # Handle timezone-aware vs naive datetime comparison
        if timestamp.tzinfo is not None:
            # Timestamp is timezone-aware, use UTC now
            from datetime import timezone
            now = datetime.now(timezone.utc)
        else:
            # Timestamp is naive, use naive now
            now = datetime.now()
        
        time_diff = abs(timestamp - now)
        
        if timestamp > now + self.timestamp_tolerance:
            errors.append(ValidationError(
                field="timestamp",
                message="Timestamp is too far in the future",
                value=timestamp
            ))
        elif timestamp < now - self.timestamp_tolerance:
            errors.append(ValidationError(
                field="timestamp", 
                message="Timestamp is too old",
                value=timestamp
            ))
        
        return errors
    
    def _validate_orderbook_fields(self, orderbook: OrderbookSnapshot) -> List[ValidationError]:
        """Validate basic orderbook fields"""
        errors = []
        
        if not orderbook.market_id or not orderbook.market_id.strip():
            errors.append(ValidationError(
                field="market_id",
                message="Market ID is required and cannot be empty"
            ))
        
        if not orderbook.bids and not orderbook.asks:
            errors.append(ValidationError(
                field="orderbook",
                message="Orderbook cannot be completely empty"
            ))
        elif not orderbook.bids:
            errors.append(ValidationError(
                field="bids",
                message="Orderbook must have at least one bid"
            ))
        elif not orderbook.asks:
            errors.append(ValidationError(
                field="asks", 
                message="Orderbook must have at least one ask"
            ))
        
        return errors
    
    def _validate_price_levels(self, orderbook: OrderbookSnapshot) -> List[ValidationError]:
        """Validate price level ordering and values"""
        errors = []
        
        # Validate bid ordering (highest to lowest)
        for i in range(len(orderbook.bids) - 1):
            if orderbook.bids[i].price < orderbook.bids[i + 1].price:
                errors.append(ValidationError(
                    field="bids",
                    message="Bid price ordering is incorrect (should be highest to lowest)"
                ))
                break
        
        # Validate ask ordering (lowest to highest)
        for i in range(len(orderbook.asks) - 1):
            if orderbook.asks[i].price > orderbook.asks[i + 1].price:
                errors.append(ValidationError(
                    field="asks",
                    message="Ask price ordering is incorrect (should be lowest to highest)"
                ))
                break
        
        # Validate positive prices and quantities
        for bid in orderbook.bids:
            if bid.price <= 0 or bid.quantity <= 0:
                errors.append(ValidationError(
                    field="bids",
                    message="All bid prices and quantities must be positive"
                ))
                break
        
        for ask in orderbook.asks:
            if ask.price <= 0 or ask.quantity <= 0:
                errors.append(ValidationError(
                    field="asks",
                    message="All ask prices and quantities must be positive"
                ))
                break
        
        return errors
    
    def _validate_spread(self, orderbook: OrderbookSnapshot) -> List[ValidationError]:
        """Validate bid-ask spread"""
        errors = []
        
        if orderbook.bids and orderbook.asks:
            best_bid = orderbook.bids[0].price
            best_ask = orderbook.asks[0].price
            
            # Check for crossed market
            if best_bid >= best_ask:
                errors.append(ValidationError(
                    field="spread",
                    message="Market is crossed (best bid >= best ask)"
                ))
        
        return errors
