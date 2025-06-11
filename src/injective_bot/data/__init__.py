"""
Layer 3: Market Data Processing

Core module for real-time market data processing, OHLCV aggregation,
orderbook analysis, and memory-efficient data storage.

Exports:
    - MarketDataAggregator: OHLCV data aggregation
    - OrderbookProcessor: Orderbook depth and spread analysis
    - CircularBuffer: Memory-efficient historical data storage
    - DataValidator: Data quality validation
    - PerformanceMonitor: Processing performance tracking
"""

from .aggregator import MarketDataAggregator
from .orderbook_processor import OrderbookProcessor
from .circular_buffer import CircularBuffer
from .data_validator import DataValidator
from .performance_monitor import PerformanceMonitor

__all__ = [
    "MarketDataAggregator",
    "OrderbookProcessor", 
    "CircularBuffer",
    "DataValidator",
    "PerformanceMonitor"
]
